from django.conf import settings
from django.core.management.base import BaseCommand

from ukps.models import Scheme, UKPSRegistration


class Command(BaseCommand):
    help = "Print this bank's UKPS API key per scheme (use them in the UKPS viewer / curl)."

    def handle(self, *args, **options):
        base = {
            Scheme.CHAPS: settings.UKPS_CHAPS_URL,
            Scheme.FPS: settings.UKPS_FPS_URL,
            Scheme.BACS: settings.UKPS_BACS_URL,
        }
        payments_path = {
            Scheme.CHAPS: "/v1/payments/chaps",
            Scheme.FPS: "/v1/payments/fps",
            Scheme.BACS: "/v1/payments/bacs/submit",
        }

        regs = UKPSRegistration.objects.order_by("scheme")
        if not regs:
            self.stdout.write(self.style.WARNING(
                "No UKPS registrations yet. Send a transfer or run "
                "'python manage.py ukps_register' first."
            ))
            return

        for r in regs:
            url = base.get(r.scheme, "")
            self.stdout.write(self.style.SUCCESS(f"\n{r.scheme}  (BIC {r.bic}, sort {r.sort_code})"))
            self.stdout.write(f"  API key : {r.api_key}")
            self.stdout.write(f"  Service : {url}")
            self.stdout.write(
                f"  Check   : curl -s {url}{payments_path.get(r.scheme, '')} "
                f"-H 'Authorization: Bearer {r.api_key}'"
            )
