from decimal import Decimal

import requests
from django.db.models import Q
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from drf_spectacular.utils import extend_schema
from .serializers import (
    ActivateCardSerializer,
    CardPaymentCaptureSerializer,
    CardSerializer,
    CreateCardSerializer,
    ManageCardStatusSerializer,
    SyncCardStatusSerializer,
    TopUpPrepaidSerializer,
    ArchiveCardSerializer,
)

from accounts.models import Account
from notifications.utils import notify
from transactions.models import Transaction

from .models import Card, CardPaymentCapture
from .provider_client import get_card, issue_card, update_card_status, topup_prepaid, activate_card

PROVIDER_TO_LOCAL_CARD_STATUS = {
    "REQUESTED": Card.CardStatus.REQUESTED,
    "PRODUCING": Card.CardStatus.PROCESSING,
    "SHIPPED": Card.CardStatus.SHIPPED,
    "ACTIVE": Card.CardStatus.ACTIVE,
    "BLOCKED": Card.CardStatus.FROZEN,
}


def map_provider_card_status(provider_status: str):
    return PROVIDER_TO_LOCAL_CARD_STATUS.get(provider_status)


class CreateCardView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateCardSerializer

    @extend_schema(
        tags=["Cards"],
        summary="Issue a new card",
        description=(
            "Creates a card in the external card provider "
            "and saves its local representation in the bank."
        ),
    )
    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        account_id = serializer.validated_data[
            "account_id"
        ]

        requested_card_type = (
            serializer.validated_data[
                "card_type"
            ]
        )

        account = get_object_or_404(Account, id=account_id)
        user_customer = request.user.customer

        if account.customer != user_customer and account.customer.parent_customer != user_customer:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if account.account_type == "JUNIOR":
            if account.cards.filter(
                card_type=Card.CardType.PREPAID,
                is_archived=False,
            ).count() >= 1:
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

            if account.cards.filter(
                card_type=card_type,
                is_archived=False,
            ).count() >= 2:
                return Response(
                    {"error": f"You can only have 2 {card_type} cards."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        provider_card_type = card_type

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


class CardManageView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ManageCardStatusSerializer

    @extend_schema(
    tags=["Cards"],
    summary="Freeze or unfreeze a card",
    )

    def patch(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        card_id = serializer.validated_data["card_id"]
        requested_status = serializer.validated_data["status"]

        card = get_object_or_404(Card, id=card_id)

        if card.is_archived:
            return Response(
                {
                    "error":
                        "Card has been removed from the application"
                },
                status=
                    status.HTTP_400_BAD_REQUEST,
            )

        user_customer = request.user.customer

        if (
            card.account.customer != user_customer
            and card.account.customer.parent_customer != user_customer
        ):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not card.external_card_id:
            return Response(
                {"error": "Card is not connected to the external card system"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if requested_status == Card.CardStatus.FROZEN:
            provider_status = "BLOCKED"
            reason = "Frozen by customer in bank application"
            action = "frozen"
        else:
            provider_status = "ACTIVE"
            reason = ""
            action = "unfrozen"

        try:
            provider_result = update_card_status(
                card_token=card.external_card_id,
                status=provider_status,
                reason=reason,
            )
        except requests.HTTPError as exc:
            return Response(
                {
                    "error": "Could not update card status in external card system",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response(
                {
                    "error": "Card provider is unavailable",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not provider_result.get("success"):
            return Response(
                {
                    "error": "External card system rejected the status update",
                    "details": provider_result.get("message"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        card.status = requested_status
        card.save(update_fields=["status"])

        notify(
            request.user,
            "Card status changed",
            f"Your card {card.masked_number} has been {action}.",
        )

        return Response(
            {
                "message": f"Card successfully {action}",
                "card_id": str(card.id),
                "external_card_id": card.external_card_id,
                "status": card.status,
                "provider_status": provider_status,
            },
            status=status.HTTP_200_OK,
        )


class ArchiveCardView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ArchiveCardSerializer

    @extend_schema(
    tags=["Cards"],
    summary="Remove a card from the bank application",
    description=(
        "Blocks the card in the external provider and archives "
        "its local representation. The card remains in the "
        "database to preserve transaction history."
    ),
)

    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        card_id = serializer.validated_data[
            "card_id"
        ]

        card = get_object_or_404(
            Card.objects.select_related(
                "account__customer"
            ),
            id=card_id,
        )

        user_customer = request.user.customer

        if (
            card.account.customer != user_customer
            and
            card.account.customer.parent_customer
            != user_customer
        ):
            return Response(
                {
                    "error":
                        "Unauthorized"
                },
                status=
                    status.HTTP_403_FORBIDDEN,
            )

        if card.is_archived:
            return Response(
                {
                    "message":
                        "Card is already archived",
                    "card_id":
                        str(card.id),
                    "status":
                        card.status,
                    "is_archived":
                        True,
                },
                status=status.HTTP_200_OK,
            )

        if (
            card.card_type ==
            Card.CardType.PREPAID
            and
            card.prepaid_balance > Decimal("0.00")
        ):
            return Response(
                {
                    "error":
                        "Prepaid card balance must be empty before removing the card",
                    "prepaid_balance":
                        card.prepaid_balance,
                },
                status=
                    status.HTTP_400_BAD_REQUEST,
            )

        if not card.external_card_id:
            return Response(
                {
                    "error":
                        "Card is not connected to the external card system"
                },
                status=
                    status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider_card = get_card(
                card.external_card_id
            )

            provider_status = (
                provider_card.get("status")
            )

            if provider_status != "BLOCKED":
                provider_result = (
                    update_card_status(
                        card_token=
                            card.external_card_id,
                        status="BLOCKED",
                        reason=(
                            "Removed by customer "
                            "in bank application"
                        ),
                    )
                )

                if not provider_result.get(
                    "success"
                ):
                    return Response(
                        {
                            "error":
                                "External card system rejected the card removal",
                            "details":
                                provider_result.get(
                                    "message"
                                ),
                        },
                        status=
                            status.HTTP_502_BAD_GATEWAY,
                    )

        except requests.HTTPError as exc:
            return Response(
                {
                    "error":
                        "Could not block card in external card system",
                    "details":
                        str(exc),
                },
                status=
                    status.HTTP_502_BAD_GATEWAY,
            )

        except Exception as exc:
            return Response(
                {
                    "error":
                        "Card provider is unavailable",
                    "details":
                        str(exc),
                },
                status=
                    status.HTTP_502_BAD_GATEWAY,
            )

        card.status = Card.CardStatus.FROZEN
        card.is_archived = True

        card.save(
            update_fields=[
                "status",
                "is_archived",
            ]
        )

        notify(
            request.user,
            "Card removed",
            (
                f"Your card {card.masked_number} "
                "has been blocked and removed "
                "from the application."
            ),
        )

        return Response(
            {
                "message":
                    "Card removed successfully",
                "card_id":
                    str(card.id),
                "status":
                    card.status,
                "provider_status":
                    "BLOCKED",
                "is_archived":
                    card.is_archived,
            },
            status=status.HTTP_200_OK,
        )

class TopUpPrepaidView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TopUpPrepaidSerializer

    @extend_schema(
    tags=["Cards"],
    summary="Top up a prepaid card",
    )

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        card_id = serializer.validated_data["card_id"]
        amount = serializer.validated_data["amount"]

        card = get_object_or_404(
            Card.objects.select_related("account__customer"),
            id=card_id,
        )

        account = card.account

        if card.is_archived:
            return Response(
                {
                    "error":
                        "Card has been removed from the application"
                },
                status=
                    status.HTTP_400_BAD_REQUEST,
            )

        user_customer = request.user.customer

        if (
            account.customer != user_customer
            and account.customer.parent_customer != user_customer
        ):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if card.card_type != Card.CardType.PREPAID:
            return Response(
                {"error": "Only prepaid cards can be topped up"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not card.external_card_id:
            return Response(
                {"error": "Card is not connected to the external card system"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            account = Account.objects.select_for_update().get(id=account.id)
            card = Card.objects.select_for_update().get(id=card.id)

            if account.available_balance < amount:
                return Response(
                    {"error": "Insufficient funds on the main account"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                provider_result = topup_prepaid(
                    card_token=card.external_card_id,
                    amount=amount,
                    currency="GBP",
                )
            except requests.HTTPError as exc:
                try:
                    provider_details = exc.response.json().get("detail")
                except Exception:
                    provider_details = str(exc)

                return Response(
                    {
                        "error": "External card system rejected the top-up",
                        "details": provider_details,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as exc:
                return Response(
                    {
                        "error": "Card provider is unavailable",
                        "details": str(exc),
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            if not provider_result.get("success"):
                return Response(
                    {
                        "error": "External card system rejected the top-up",
                        "details": provider_result.get("message"),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            provider_balance = Decimal(str(provider_result["new_balance"]))

            account.balance -= amount
            account.available_balance -= amount
            card.prepaid_balance = provider_balance

            account.save(update_fields=["balance", "available_balance"])
            card.save(update_fields=["prepaid_balance"])

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
                "card_id": str(card.id),
                "external_card_id": card.external_card_id,
                "new_prepaid_balance": card.prepaid_balance,
                "new_account_balance": account.available_balance,
            },
            status=status.HTTP_200_OK,
        )

class SyncCardStatusView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SyncCardStatusSerializer

    @extend_schema(
    tags=["Cards"],
    summary="Synchronize one card status",
    )

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        local_card_id = serializer.validated_data["local_card_id"]

        card = get_object_or_404(Card, id=local_card_id)

        if card.is_archived:
            return Response(
                {
                    "error":
                        "Card has been removed from the application"
                },
                status=
                    status.HTTP_400_BAD_REQUEST,
            )

        user_customer = request.user.customer

        if (
            card.account.customer != user_customer
            and card.account.customer.parent_customer != user_customer
        ):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not card.external_card_id:
            return Response(
                {"error": "Card is not connected to the external card system"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider_result = get_card(card.external_card_id)
        except requests.HTTPError as exc:
            return Response(
                {
                    "error": "Could not fetch card status from external card system",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response(
                {
                    "error": "Card provider is unavailable",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        provider_status = provider_result.get("status")
        local_status = map_provider_card_status(provider_status)

        if not local_status:
            return Response(
                {
                    "error": "External card system returned an unsupported status",
                    "provider_status": provider_status,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        card.status = local_status
        card.save(update_fields=["status"])

        return Response(
            {
                "message": "Card status synchronized",
                "card_id": str(card.id),
                "external_card_id": card.external_card_id,
                "status": card.status,
                "provider_status": provider_status,
            },
            status=status.HTTP_200_OK,
        )

class CardPaymentCaptureView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = CardPaymentCaptureSerializer

    @extend_schema(
    tags=["Card provider callbacks"],
    summary="Settle a card payment",
    description=(
        "Callback used by the external card provider "
        "after payment settlement."
    ),
)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider_transaction_id = serializer.validated_data["transaction_id"]
        authorization_code = serializer.validated_data["authorization_code"]
        amount = serializer.validated_data["amount"]
        currency = serializer.validated_data["currency"]
        merchant_id = serializer.validated_data["merchant_id"]
        card_token = serializer.validated_data["card_token"]

        with transaction.atomic():
            existing_capture = (
                CardPaymentCapture.objects
                .select_for_update()
                .filter(provider_transaction_id=provider_transaction_id)
                .first()
            )

            if existing_capture:
                return Response(
                    {
                        "status": "CAPTURED",
                        "duplicate": True,
                        "transaction_id": provider_transaction_id,
                    },
                    status=status.HTTP_200_OK,
                )

            card = (
                Card.objects
                .select_for_update()
                .filter(external_card_id=card_token)
                .first()
            )

            if not card:
                return Response(
                    {"error": "Card not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            account = (
                Account.objects
                .select_for_update()
                .get(id=card.account_id)
            )

            if account.status != Account.AccountStatus.ACTIVE:
                return Response(
                    {"error": "Account is not active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            owner_user = account.customer.user

            if not owner_user:
                return Response(
                    {"error": "Card owner does not have a user account"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if card.card_type == Card.CardType.PREPAID:
                if card.prepaid_balance < amount:
                    return Response(
                        {"error": "Insufficient prepaid card balance"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                card.prepaid_balance -= amount
                card.save(update_fields=["prepaid_balance"])

            else:
                if account.available_balance < amount:
                    return Response(
                        {"error": "Insufficient account balance"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                account.balance -= amount
                account.available_balance -= amount

                account.save(
                    update_fields=[
                        "balance",
                        "available_balance",
                    ]
                )

            merchant_label = (
                merchant_id.strip()
                if merchant_id
                else "Unknown merchant"
            )

            transaction_title = (
                f"Card payment at {merchant_label}"
            )

            local_transaction = Transaction.objects.create(
                user=owner_user,
                account=account,
                amount=-amount,
                title=transaction_title,
                balance_after=account.available_balance,
            )

            CardPaymentCapture.objects.create(
                card=card,
                local_transaction=local_transaction,
                provider_transaction_id=provider_transaction_id,
                authorization_code=authorization_code,
                amount=amount,
                currency=currency,
                merchant_id=merchant_id,
            )

            notify(
                owner_user,
                "Card payment settled",
                (
                    f"Card payment of £{amount} "
                    f"at {merchant_label} has been settled."
                ),
            )

        return Response(
            {
                "status": "CAPTURED",
                "duplicate": False,
                "transaction_id": provider_transaction_id,
                "card_id": str(card.id),
                "new_account_balance": account.available_balance,
                "new_prepaid_balance": card.prepaid_balance,
            },
            status=status.HTTP_200_OK,
        )

class ActivateCardView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ActivateCardSerializer
    
    @extend_schema(
    tags=["Cards"],
    summary="Activate a shipped card",
    )

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        card_id = serializer.validated_data["card_id"]

        card = get_object_or_404(Card, id=card_id)

        if card.is_archived:
            return Response(
                {
                    "error":
                        "Card has been removed from the application"
                },
                status=
                    status.HTTP_400_BAD_REQUEST,
            )

        user_customer = request.user.customer

        if (
            card.account.customer != user_customer
            and card.account.customer.parent_customer != user_customer
        ):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not card.external_card_id:
            return Response(
                {
                    "error":
                        "Card is not connected to the external card system"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if card.card_type == Card.CardType.VIRTUAL:
            return Response(
                {
                    "error":
                        "Virtual cards are activated automatically"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider_result = activate_card(
                card_token=card.external_card_id,
            )
        except requests.HTTPError as exc:
            try:
                provider_details = (
                    exc.response
                    .json()
                    .get("detail")
                )
            except Exception:
                provider_details = str(exc)

            return Response(
                {
                    "error":
                        "External card system rejected the activation",
                    "details":
                        provider_details,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {
                    "error":
                        "Card provider is unavailable",
                    "details":
                        str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not provider_result.get("success"):
            return Response(
                {
                    "error":
                        "External card system rejected the activation",
                    "details":
                        provider_result.get("message"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        card.status = Card.CardStatus.ACTIVE
        card.save(update_fields=["status"])

        notify(
            request.user,
            "Card activated",
            (
                f"Your {card.card_type.lower()} card "
                f"{card.masked_number} has been activated."
            ),
        )

        return Response(
            {
                "message": "Card activated successfully",
                "card_id": str(card.id),
                "external_card_id": card.external_card_id,
                "status": card.status,
            },
            status=status.HTTP_200_OK,
        )

class SyncAllCardStatusesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
    tags=["Cards"],
    summary="Synchronize all card statuses",
    description=(
        "Fetches current statuses from the external "
        "card provider for all cards available to "
        "the authenticated user."
    ),
    request=None,
)

    def post(self, request):
        user_customer = request.user.customer

        cards = (
            Card.objects
            .filter(
                Q(account__customer=user_customer)
                | Q(
                    account__customer__parent_customer=
                    user_customer
                ),
                is_archived=False
            )
            .exclude(external_card_id__isnull=True)
            .exclude(external_card_id="")
            .select_related("account")
        )

        synchronized_cards = []
        errors = []

        for card in cards:
            try:
                provider_result = get_card(
                    card.external_card_id
                )

                provider_status = (
                    provider_result.get("status")
                )

                local_status = (
                    map_provider_card_status(
                        provider_status
                    )
                )

                if not local_status:
                    errors.append(
                        {
                            "card_id": str(card.id),
                            "external_card_id":
                                card.external_card_id,
                            "error":
                                "Unsupported provider status",
                            "provider_status":
                                provider_status,
                        }
                    )

                    continue

                if card.status != local_status:
                    card.status = local_status
                    card.save(
                        update_fields=["status"]
                    )

                synchronized_cards.append(
                    {
                        "card_id": str(card.id),
                        "external_card_id":
                            card.external_card_id,
                        "status": card.status,
                        "provider_status":
                            provider_status,
                    }
                )

            except requests.HTTPError as exc:
                errors.append(
                    {
                        "card_id": str(card.id),
                        "external_card_id":
                            card.external_card_id,
                        "error":
                            "Could not fetch card status",
                        "details": str(exc),
                    }
                )

            except Exception as exc:
                errors.append(
                    {
                        "card_id": str(card.id),
                        "external_card_id":
                            card.external_card_id,
                        "error":
                            "Card provider is unavailable",
                        "details": str(exc),
                    }
                )

        return Response(
            {
                "message":
                    "Card statuses synchronization completed",
                "synchronized_count":
                    len(synchronized_cards),
                "error_count":
                    len(errors),
                "cards":
                    synchronized_cards,
                "errors":
                    errors,
            },
            status=status.HTTP_200_OK,
        )