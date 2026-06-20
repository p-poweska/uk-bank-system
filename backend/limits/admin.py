from django.contrib import admin

from .models import AccountLimits


@admin.register(AccountLimits)
class AccountLimitsAdmin(admin.ModelAdmin):
    list_display = ("account", "channel", "per_transaction_limit", "daily_limit")
    list_filter = ("channel",)
    search_fields = ("account__account_number",)
