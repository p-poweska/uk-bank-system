from django.contrib import admin

from .models import Transfer, SavedRecipient, JuniorApproval


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "from_account", "recipient_name", "recipient_account",
        "amount", "routing_method", "status", "created_at",
    )
    list_filter = ("routing_method", "status")
    search_fields = ("recipient_name", "recipient_account", "swift_bic")
    readonly_fields = ("created_at",)


@admin.register(SavedRecipient)
class SavedRecipientAdmin(admin.ModelAdmin):
    list_display = ("name", "account", "user", "routing_method", "created_at")
    search_fields = ("name", "account")
    readonly_fields = ("created_at",)


@admin.register(JuniorApproval)
class JuniorApprovalAdmin(admin.ModelAdmin):
    list_display = (
        "id", "junior_user", "parent_user", "amount",
        "recipient_name", "status", "created_at",
    )
    list_filter = ("status",)
    search_fields = ("recipient_name", "recipient_account")
    readonly_fields = ("created_at", "decided_at")
