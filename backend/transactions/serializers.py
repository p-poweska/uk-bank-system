from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    account_number = serializers.CharField(
        source="account.account_number",
        read_only=True,
    )

    recipient_name = serializers.SerializerMethodField()
    recipient_account = serializers.SerializerMethodField()
    routing_method = serializers.SerializerMethodField()

    transaction_category = serializers.SerializerMethodField()
    card_payment = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "title",
            "amount",
            "balance_after",
            "created_at",
            "type",
            "account_number",
            "recipient_name",
            "recipient_account",
            "routing_method",
            "transaction_category",
            "card_payment",
        ]

    def _get_card_payment_capture(self, obj):
        try:
            return obj.card_payment_capture
        except ObjectDoesNotExist:
            return None

    def get_title(self, obj):
        capture = self._get_card_payment_capture(obj)

        if capture:
            merchant_id = capture.merchant_id.strip()

            if merchant_id:
                return f"Card payment at {merchant_id}"

            return "Card payment"

        return obj.title

    def get_type(self, obj):
        return "CREDIT" if obj.amount > 0 else "DEBIT"

    def get_recipient_name(self, obj):
        return (
            obj.transfer.recipient_name
            if obj.transfer
            else None
        )

    def get_recipient_account(self, obj):
        return (
            obj.transfer.recipient_account
            if obj.transfer
            else None
        )

    def get_routing_method(self, obj):
        return (
            obj.transfer.routing_method
            if obj.transfer
            else None
        )

    def get_transaction_category(self, obj):
        capture = self._get_card_payment_capture(obj)

        if capture:
            return "CARD_PAYMENT"

        if obj.transfer:
            return "TRANSFER"

        title_lower = obj.title.lower()

        if "top-up prepaid card" in title_lower:
            return "CARD_TOP_UP"

        if title_lower == "add money":
            return "DEPOSIT"

        return "OTHER"

    def get_card_payment(self, obj):
        capture = self._get_card_payment_capture(obj)

        if not capture:
            return None

        return {
            "merchant_id": capture.merchant_id,
            "currency": capture.currency,
            "card_type": capture.card.card_type,
            "masked_number": capture.card.masked_number,
            "provider_transaction_id":
                capture.provider_transaction_id,
        }