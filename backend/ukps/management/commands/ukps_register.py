from django.core.management.base import BaseCommand

from ukps.models import Scheme, UKPSRegistration
from ukps import services


class Command(BaseCommand):
    help = "Register this bank in the UKPS schemes (CHAPS, FPS, BACS)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-register even if a registration already exists.",
        )

    def handle(self, *args, **options):
        for scheme in (Scheme.CHAPS, Scheme.FPS, Scheme.BACS):
            exists = UKPSRegistration.objects.filter(scheme=scheme).exists()
            if exists and not options["force"]:
                self.stdout.write(f"{scheme}: already registered, skipping")
                continue
            try:
                reg = services.register(scheme)
            except services.UKPSError as exc:
                self.stderr.write(self.style.ERROR(f"{scheme}: {exc}"))
                continue
            self.stdout.write(self.style.SUCCESS(
                f"{scheme}: registered as {reg.bic} ({reg.sort_code})"
            ))
