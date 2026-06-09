from rest_framework import serializers
from .models import Card
from decimal import Decimal

class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = [
            'id', 'card_type', 'masked_number', 'full_number', 
            'expiry_date', 'cardholder_name', 'status', 
            'cvv', 'pin', 'prepaid_balance'
        ]

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