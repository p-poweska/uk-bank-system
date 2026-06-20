from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "account", "amount", "title", "balance_after", "created_at")
    search_fields = ("title",)
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)
