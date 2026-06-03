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
from .services import confirm_klik_payment, generate_klik_code, register_klik_alias, delete_klik_alias, lookup_klik_alias



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
        print("KLIK WEBHOOK DATA:", data)

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
        now = timezone.now()

        KlikPayment.objects.filter(
            user=request.user,
            status=KlikPayment.Status.PENDING,
            expiry_time__isnull=False,
            expiry_time__lte=now,
        ).update(
            status=KlikPayment.Status.EXPIRED,
            decided_at=now,
        )

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

        if payment.expiry_time and payment.expiry_time <= timezone.now():
            try:
                confirm_klik_payment(
                    payment.transaction_id,
                    "REJECTED",
                    "TIMEOUT",
                )
            except Exception:
                pass

            payment.status = KlikPayment.Status.EXPIRED
            payment.decided_at = timezone.now()
            payment.save()

            return Response(
                {"error": "KLIK payment has expired."},
                status=status.HTTP_400_BAD_REQUEST,
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

        if payment.expiry_time and payment.expiry_time <= timezone.now():
            payment.status = KlikPayment.Status.EXPIRED
            payment.decided_at = timezone.now()
            payment.save()

            return Response(
                {"error": "KLIK payment has expired."},
                status=status.HTTP_400_BAD_REQUEST,
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

        
        notify(
            request.user,
            "KLIK payment rejected",
            f"Payment of {payment.amount} {payment.currency} to {payment.merchant_name} was rejected.",
        )

        return Response(result)


class MyKlikAliasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "phone": request.user.customer.klik_phone_alias
        })

class RegisterKlikAliasView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account = get_current_account(request.user)

        if not account:
            return Response(
                {"error": "KLIK aliases are available only for active current accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        phone = request.data.get("phone", "").strip()

        if not phone:
            return Response(
                {"error": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = register_klik_alias(phone=phone, iban=account.iban)
        except Exception as exc:
            return Response(
                {"error": "Could not register KLIK phone alias.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        customer = request.user.customer
        customer.klik_phone_alias = phone
        customer.save()

        return Response(result, status=status.HTTP_201_CREATED)


class RemoveKlikAliasView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        phone = request.data.get("phone", "").strip()

        if not phone:
            return Response(
                {"error": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = delete_klik_alias(phone=phone)
        except Exception as exc:
            return Response(
                {"error": "Could not remove KLIK phone alias.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        customer = request.user.customer
        customer.klik_phone_alias = None
        customer.save()

        return Response(result, status=status.HTTP_200_OK)

class SendKlikP2PView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        sender_account = get_current_account(request.user)

        if not sender_account:
            return Response(
                {"error": "KLIK P2P is available only for active current accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        phone = request.data.get("phone", "").strip()

        try:
            alias = lookup_klik_alias(phone)
        except Exception as exc:
            return Response(
                {"error": "Recipient phone number is not registered in KLIK."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            amount = Decimal(str(request.data.get("amount", "0")))
        except Exception:
            return Response(
                {"error": "Invalid amount format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not phone:
            return Response(
                {"error": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= 0:
            return Response(
                {"error": "Amount must be greater than zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sender_account = Account.objects.select_for_update().get(id=sender_account.id)

        if sender_account.available_balance < amount:
            return Response(
                {"error": "Insufficient funds."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            alias = lookup_klik_alias(phone)
        except Exception as exc:
            return Response(
                {"error": "Could not find KLIK phone alias.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        recipient_iban = alias.get("iban")

        if not recipient_iban:
            return Response(
                {"error": "KLIK alias does not contain recipient IBAN."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if recipient_iban == sender_account.iban:
            return Response(
                {"error": "You cannot send money to your own phone alias."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipient_account = Account.objects.select_for_update().filter(
            iban=recipient_iban,
            status="ACTIVE",
        ).first()

        sender_account.balance -= amount
        sender_account.available_balance -= amount
        sender_account.save()

        Transaction.objects.create(
            user=request.user,
            account=sender_account,
            amount=-amount,
            title=f"KLIK P2P transfer to {phone}",
            balance_after=sender_account.available_balance,
        )

        sender_phone = getattr(request.user.customer, "klik_phone_alias", None) or "another KLIK user"

        if recipient_account:
            recipient_account.balance += amount
            recipient_account.available_balance += amount
            recipient_account.save()

            Transaction.objects.create(
                user=recipient_account.customer.user,
                account=recipient_account,
                amount=amount,
                title=f"KLIK P2P transfer from {sender_phone}",
                balance_after=recipient_account.available_balance,
            )

            notify(
                recipient_account.customer.user,
                "KLIK P2P transfer received",
                f"You received {amount} {sender_account.currency} from {sender_phone}.",
            )

        notify(
            request.user,
            "KLIK P2P transfer sent",
            f"You sent {amount} {sender_account.currency} to {phone}.",
        )

        return Response(
            {
                "status": "COMPLETED",
                "phone": phone,
                "recipient_iban": recipient_iban,
                "amount": str(amount),
                "currency": sender_account.currency,
                "recipient_found_in_this_bank": bool(recipient_account),
            },
            status=status.HTTP_200_OK,
        )