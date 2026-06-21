import os
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Wait until all configured UKPS services are reachable."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=int(os.environ.get("UKPS_WAIT_TIMEOUT", "0")),
            help="Timeout in seconds. Use 0 to wait forever.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=float(os.environ.get("UKPS_WAIT_INTERVAL", "2")),
            help="Retry interval in seconds.",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        interval = options["interval"]

        services = {
            "CHAPS": getattr(settings, "UKPS_CHAPS_URL", ""),
            "FPS": getattr(settings, "UKPS_FPS_URL", ""),
            "BACS": getattr(settings, "UKPS_BACS_URL", ""),
        }

        services = {
            name: url.rstrip("/")
            for name, url in services.items()
            if url
        }

        if not services:
            raise CommandError("No UKPS service URLs configured.")

        self.stdout.write("Waiting for UKPS services...")

        start_time = time.time()
        pending = set(services.keys())
        last_errors = {}

        while pending:
            for name in list(pending):
                base_url = services[name]
                probe_url = f"{base_url}/v1/participants/register"

                try:
                    request = urllib.request.Request(probe_url, method="GET")
                    with urllib.request.urlopen(request, timeout=3):
                        pass

                    self.stdout.write(
                        self.style.SUCCESS(f"UKPS {name} is reachable: {base_url}")
                    )
                    pending.remove(name)

                except urllib.error.HTTPError as exc:
                    # HTTP 404/405/401 means the service is reachable.
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"UKPS {name} is reachable: {base_url} HTTP {exc.code}"
                        )
                    )
                    pending.remove(name)

                except Exception as exc:
                    last_errors[name] = str(exc)

            if not pending:
                break

            if timeout > 0 and time.time() - start_time >= timeout:
                details = "; ".join(
                    f"{name}: {error}" for name, error in last_errors.items()
                )
                raise CommandError(f"Timed out waiting for UKPS services. {details}")

            waiting_for = ", ".join(sorted(pending))
            self.stdout.write(f"Still waiting for UKPS: {waiting_for}")
            time.sleep(interval)

        self.stdout.write(self.style.SUCCESS("All UKPS services are reachable."))