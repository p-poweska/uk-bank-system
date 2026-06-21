from rest_framework import serializers
from .models import Account
from decimal import Decimal
from limits.models import AccountLimits
from cards.serializers import CardSerializer

class AccountSerializer(serializers.ModelSerializer):

    owner_first_name = serializers.CharField(source='customer.first_name', read_only=True)
    owner_last_name = serializers.CharField(source='customer.last_name', read_only=True)

    limits = serializers.SerializerMethodField()

    cards = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = ['id', 'account_number', 'sort_code', 'iban', 'currency', 'balance', 'account_type',  'available_balance', 'status', 'owner_first_name','owner_last_name', 'limits','cards']

    def get_limits(self, obj):
        allowed_channels = {"BLIK", "BLIK_PHONE"}

        return {
            limit.channel: {
                "per_transaction_limit": limit.per_transaction_limit,
                "daily_limit": limit.daily_limit,
            }
            for limit in obj.limits.all()
            if limit.card_id is None and limit.channel in allowed_channels
        }

    def get_cards(self, obj):
        cards = getattr(
            obj,
            "visible_cards",
            None,
        )

        if cards is None:
            cards = obj.cards.filter(
                is_archived=False
            )

        return CardSerializer(
            cards,
            many=True,
        ).data

class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        min_value=Decimal('1.00')
    )  

