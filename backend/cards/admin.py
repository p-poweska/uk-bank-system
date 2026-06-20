from django.contrib import admin

from .models import Card, CardPaymentCapture


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = (
        "masked_number", "cardholder_name", "card_type",
        "account", "status", "is_archived", "created_at",
    )
    list_filter = ("card_type", "status", "is_archived")
    search_fields = ("masked_number", "cardholder_name", "external_card_id")
    readonly_fields = ("created_at",)


@admin.register(CardPaymentCapture)
class CardPaymentCaptureAdmin(admin.ModelAdmin):
    list_display = (
        "provider_transaction_id", "card", "amount",
        "currency", "merchant_id", "created_at",
    )
    search_fields = ("provider_transaction_id", "authorization_code", "merchant_id")
    readonly_fields = ("created_at",)
