from django.contrib import admin

from .models import UKPSRegistration, UKPSPayment, UKPSInboundPayment


@admin.register(UKPSRegistration)
class UKPSRegistrationAdmin(admin.ModelAdmin):
    list_display = ("scheme", "bic", "sort_code", "registered_at")
    readonly_fields = ("registered_at",)


@admin.register(UKPSPayment)
class UKPSPaymentAdmin(admin.ModelAdmin):
    list_display = ("msg_id", "scheme", "receiver_bic", "amount", "status", "created_at")
    list_filter = ("scheme", "status")
    search_fields = ("msg_id", "receiver_bic", "external_id")
    readonly_fields = ("created_at",)


@admin.register(UKPSInboundPayment)
class UKPSInboundPaymentAdmin(admin.ModelAdmin):
    list_display = ("msg_id", "scheme", "sender_bic", "amount", "account_number", "status", "created_at")
    list_filter = ("scheme", "status")
    search_fields = ("msg_id", "sender_bic", "account_number")
    readonly_fields = ("created_at",)
