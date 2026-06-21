from rest_framework import serializers
from .models import Card
from decimal import Decimal
from limits.models import AccountLimits, PaymentChannel

class CardSerializer(serializers.ModelSerializer):
    limits = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = [
            'id',
            'card_type',
            'masked_number',
            'full_number',
            'expiry_date',
            'cardholder_name',
            'status',
            'cvv',
            'pin',
            'prepaid_balance',
            'is_archived',
            'limits',
        ]

    def get_limits(self, obj):
        limit = obj.limits.filter(
            channel=PaymentChannel.CARD,
        ).first()

        if not limit:
            defaults = AccountLimits.card_defaults_for(
                obj.account.account_type,
                obj.card_type,
            )

            return {
                "per_transaction_limit": str(defaults["per_transaction_limit"]),
                "daily_limit": str(defaults["daily_limit"]),
            }

        return {
            "per_transaction_limit": str(limit.per_transaction_limit),
            "daily_limit": str(limit.daily_limit),
        }

class SyncCardStatusSerializer(serializers.Serializer):
    local_card_id = serializers.UUIDField()

class ManageCardStatusSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=[
            Card.CardStatus.FROZEN,
            Card.CardStatus.ACTIVE,
        ]
    )

class TopUpPrepaidSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

class CardPaymentCaptureSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=100)
    authorization_code = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    currency = serializers.CharField(max_length=3)
    merchant_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    card_token = serializers.CharField(max_length=100)

class ActivateCardSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()

class CreateCardSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()

    card_type = serializers.ChoiceField(
        choices=Card.CardType.choices,
        required=False,
        default=Card.CardType.VIRTUAL,
    )

class ArchiveCardSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()