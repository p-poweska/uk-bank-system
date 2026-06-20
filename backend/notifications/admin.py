from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "read", "created_at")
    list_filter = ("read",)
    search_fields = ("title", "body")
    readonly_fields = ("created_at",)
