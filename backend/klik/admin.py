from django.contrib import admin

from .models import KlikPayment


@admin.register(KlikPayment)
class KlikPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id", "user", "account", "amount",
        "currency", "merchant_name", "status", "created_at",
    )
    list_filter = ("status", "zone", "is_on_us")
    search_fields = ("merchant_name",)
    readonly_fields = ("created_at", "decided_at")
