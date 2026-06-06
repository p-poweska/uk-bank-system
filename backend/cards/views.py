from decimal import Decimal

import requests
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from notifications.utils import notify
from transactions.models import Transaction

from .models import Card
from .provider_client import issue_card


class CreateCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account_id = request.data.get("account_id")
        requested_card_type = request.data.get("card_type", Card.CardType.VIRTUAL)

        account = get_object_or_404(Account, id=account_id)
        user_customer = request.user.customer

        if account.customer != user_customer and account.customer.parent_customer != user_customer:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if account.account_type == "JUNIOR":
            if account.cards.filter(card_type=Card.CardType.PREPAID).count() >= 1:
                return Response(
                    {"error": "Junior can only have 1 Prepaid card."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            card_type = Card.CardType.PREPAID
        else:
            card_type = requested_card_type

            if card_type not in Card.CardType.values:
                return Response(
                    {"error": "Invalid card type."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if account.cards.filter(card_type=card_type).count() >= 2:
                return Response(
                    {"error": f"You can only have 2 {card_type} cards."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        provider_card_type = "VIRTUAL" if card_type == Card.CardType.PREPAID else card_type

        try:
            provider_result = issue_card(
                user_id=str(request.user.id),
                account_id=str(account.id),
                card_type=provider_card_type,
            )
        except requests.HTTPError as exc:
            return Response(
                {
                    "error": "Could not issue card in external card system.",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response(
                {
                    "error": "Card provider is unavailable.",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        cardholder = f"{account.customer.first_name} {account.customer.last_name}".upper()

        masked_number = provider_result.get("masked_pan") or "**** **** **** ****"
        full_number = provider_result.get("full_pan")
        cvv = provider_result.get("cvv")

        expiry_month = provider_result.get("expiry_month")
        expiry_year = provider_result.get("expiry_year")

        if expiry_month and expiry_year:
            expiry_date = f"{int(expiry_month):02d}/{str(expiry_year)[-2:]}"
        else:
            expiry_date = ""

        provider_status = provider_result.get("status", Card.CardStatus.REQUESTED)

        if provider_status in Card.CardStatus.values:
            local_status = provider_status
        else:
            local_status = Card.CardStatus.REQUESTED

        card = Card.objects.create(
            account=account,
            external_card_id=provider_result.get("card_token"),
            card_type=card_type,
            cardholder_name=cardholder,
            masked_number=masked_number,
            full_number=full_number,
            cvv=cvv,
            pin=None,
            expiry_date=expiry_date,
            status=local_status,
        )

        notify(
            request.user,
            "Card issued",
            f"Your {card.card_type.lower()} card {card.masked_number} has been issued.",
        )

        return Response(
            {
                "message": "Card issued",
                "id": card.id,
                "external_card_id": card.external_card_id,
                "masked_number": card.masked_number,
                "full_number": card.full_number,
                "cvv": card.cvv,
                "expiry_date": card.expiry_date,
                "status": card.status,
                "provider_message": provider_result.get("message"),
            },
            status=status.HTTP_201_CREATED,
        )


class CardManageView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        card_id = request.data.get("card_id")
        card = get_object_or_404(Card, id=card_id)

        user_customer = request.user.customer

        if card.account.customer != user_customer and card.account.customer.parent_customer != user_customer:
            return Response(status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status")

        if new_status in Card.CardStatus.values:
            card.status = new_status
            card.save()
            return Response({"status": card.status})

        return Response(status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        card_id = request.data.get("card_id")
        card = get_object_or_404(Card, id=card_id)

        user_customer = request.user.customer

        if card.account.customer != user_customer and card.account.customer.parent_customer != user_customer:
            return Response(status=status.HTTP_403_FORBIDDEN)

        card.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class TopUpPrepaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        card_id = request.data.get("card_id")

        try:
            amount = Decimal(str(request.data.get("amount", "0")))
        except Exception:
            return Response({"error": "Invalid amount"}, status=400)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero"}, status=400)

        card = get_object_or_404(Card, id=card_id)
        account = card.account
        user_customer = request.user.customer

        if account.customer != user_customer and account.customer.parent_customer != user_customer:
            return Response({"error": "Unauthorized"}, status=403)

        if card.card_type != Card.CardType.PREPAID:
            return Response({"error": "Only prepaid cards can be topped up"}, status=400)

        if account.available_balance < amount:
            return Response({"error": "Insufficient funds on the main account"}, status=400)

        with transaction.atomic():
            account = Account.objects.select_for_update().get(id=account.id)
            card = Card.objects.select_for_update().get(id=card.id)

            if account.available_balance < amount:
                return Response({"error": "Insufficient funds on the main account"}, status=400)

            account.balance -= amount
            account.available_balance -= amount
            card.prepaid_balance += amount

            account.save()
            card.save()

            Transaction.objects.create(
                user=request.user,
                account=account,
                amount=-amount,
                title=f"Top-up Prepaid Card {card.masked_number}",
                balance_after=account.available_balance,
            )

            notify(
                request.user,
                "Card topped up",
                f"Your prepaid card {card.masked_number} has been topped up with £{amount}.",
            )

        return Response(
            {
                "message": "Card topped up successfully",
                "new_prepaid_balance": card.prepaid_balance,
                "new_account_balance": account.available_balance,
            },
            status=200,
        )