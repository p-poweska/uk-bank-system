from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "first_name", "last_name", "user", "phone",
        "country", "city", "parent_customer", "kyc_verified", "created_at",
    )
    list_filter = ("country", "kyc_verified")
    search_fields = ("first_name", "last_name", "phone")
    readonly_fields = ("created_at",)
