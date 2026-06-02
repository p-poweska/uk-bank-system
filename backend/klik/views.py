from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from notifications.utils import notify
from transactions.models import Transaction

from .models import KlikPayment
from .services import confirm_klik_payment, generate_klik_code


def get_current_account(user):
    return Account.objects.filter(
        customer=user.customer,
        account_type="CURRENT",
        status="ACTIVE",
    ).first()


class GenerateKlikCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account = get_current_account(request.user)

        if not account:
            return Response(
                {"error": "KLIK is available only for active current accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            result = generate_klik_code(str(request.user.id))
        except Exception as exc:
            return Response(
                {"error": "Could not generate KLIK code.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            "code": result.get("code"),
            "expires_in": result.get("expires_in", 120),
            "expires_at": result.get("expires_at"),
        })


class KlikAuthorizeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        transaction_id = data.get("transaction_id")
        amount = data.get("amount")
        currency = data.get("currency", "GBP")
        merchant_name = data.get("merchant_name", "")
        expiry_time = data.get("expiry_time")
        is_on_us = data.get("is_on_us", False)
        zone = data.get("zone", "UK")
        user_id = data.get("user_id")

        if not transaction_id or not amount:
            return Response(
                {"error": "transaction_id and amount are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user_id:
            account = Account.objects.filter(
                customer__user_id=user_id,
                account_type="CURRENT",
                status="ACTIVE",
                currency=currency,
            ).first()
        else:
            account = Account.objects.filter(
                account_type="CURRENT",
                status="ACTIVE",
                currency=currency,
            ).first()

        if not account:
            return Response(
                {"error": "Active current account not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = account.customer.user

        payment, _ = KlikPayment.objects.update_or_create(
            transaction_id=transaction_id,
            defaults={
                "user": user,
                "account": account,
                "amount": Decimal(str(amount)),
                "currency": currency,
                "merchant_name": merchant_name,
                "is_on_us": is_on_us,
                "zone": zone,
                "expiry_time": parse_datetime(expiry_time) if expiry_time else None,
                "status": KlikPayment.Status.PENDING,
            },
        )

        notify(
            user,
            "KLIK payment authorization",
            f"Payment of {amount} {currency} to {merchant_name} is waiting for confirmation.",
        )

        return Response({
            "received": True,
            "payment_id": str(payment.transaction_id),
            "will_prompt_user": True,
        })


class PendingKlikPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = KlikPayment.objects.filter(
            user=request.user,
            status=KlikPayment.Status.PENDING,
        ).order_by("-created_at")

        return Response([
            {
                "transaction_id": str(payment.transaction_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "merchant_name": payment.merchant_name,
                "expiry_time": payment.expiry_time,
                "status": payment.status,
            }
            for payment in payments
        ])


class AcceptKlikPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, transaction_id):
        payment = get_object_or_404(
            KlikPayment.objects.select_for_update(),
            transaction_id=transaction_id,
            user=request.user,
            status=KlikPayment.Status.PENDING,
        )

        account = Account.objects.select_for_update().get(id=payment.account_id)

        if account.available_balance < payment.amount:
            try:
                confirm_klik_payment(
                    payment.transaction_id,
                    "REJECTED",
                    "INSUFFICIENT_FUNDS",
                )
            except Exception:
                pass

            payment.status = KlikPayment.Status.REJECTED
            payment.decided_at = timezone.now()
            payment.save()

            return Response(
                {"error": "Insufficient funds"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = confirm_klik_payment(payment.transaction_id, "ACCEPTED")
        except Exception as exc:
            return Response(
                {"error": "Could not confirm KLIK payment.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        account.available_balance -= payment.amount
        account.balance -= payment.amount
        account.save()

        Transaction.objects.create(
            user=request.user,
            account=account,
            amount=-payment.amount,
            title=f"KLIK payment to {payment.merchant_name}",
            balance_after=account.available_balance,
        )

        payment.status = KlikPayment.Status.ACCEPTED
        payment.decided_at = timezone.now()
        payment.save()

        notify(
            request.user,
            "KLIK payment accepted",
            f"Payment of {payment.amount} {payment.currency} to {payment.merchant_name} was accepted.",
        )

        return Response(result)


class RejectKlikPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        payment = get_object_or_404(
            KlikPayment,
            transaction_id=transaction_id,
            user=request.user,
            status=KlikPayment.Status.PENDING,
        )

        try:
            result = confirm_klik_payment(
                payment.transaction_id,
                "REJECTED",
                "USER_DECLINED",
            )
        except Exception as exc:
            return Response(
                {"error": "Could not reject KLIK payment.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment.status = KlikPayment.Status.REJECTED
        payment.decided_at = timezone.now()
        payment.save()

        return Response(result)