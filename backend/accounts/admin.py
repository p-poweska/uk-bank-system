from django.contrib import admin

from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "account_number", "sort_code", "iban", "currency",
        "balance", "available_balance", "account_type", "status", "created_at",
    )
    list_filter = ("account_type", "status", "currency")
    search_fields = ("account_number", "iban", "sort_code")
    readonly_fields = ("created_at",)
