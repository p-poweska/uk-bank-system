from django.core.management.base import BaseCommand

from ukps import services


class Command(BaseCommand):
    help = "Settle/fail outbound UKPS payments that are still PENDING locally but have resolved upstream."

    def handle(self, *args, **options):
        res = services.reconcile_pending()
        self.stdout.write(self.style.SUCCESS(
            f"Reconciled: checked={res['checked']} "
            f"completed={res['completed']} failed={res['failed']}"
        ))
