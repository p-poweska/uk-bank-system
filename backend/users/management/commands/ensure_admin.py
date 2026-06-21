import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or ensure a default Django admin user exists."

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@test.com").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin123").strip()
        reset_password = os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD", "False").lower() == "true"

        if not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_EMAIL or DJANGO_SUPERUSER_PASSWORD is empty. Admin was not created."
                )
            )
            return

        User = get_user_model()

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "role": "ADMIN",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Admin user created: {email}"))
            return

        changed = False

        if not user.is_active:
            user.is_active = True
            changed = True

        if not user.is_staff:
            user.is_staff = True
            changed = True

        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if getattr(user, "role", None) != "ADMIN":
            user.role = "ADMIN"
            changed = True

        if reset_password:
            user.set_password(password)
            changed = True

        if changed:
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Admin user updated: {email}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Admin user already exists: {email}"))