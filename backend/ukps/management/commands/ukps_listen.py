import threading
import time

from django.core.management.base import BaseCommand

from ukps import listener
from ukps.models import Scheme


class Command(BaseCommand):
    help = "Listen for inbound UKPS payments (CHAPS/FPS/BACS) over SSE and post them locally."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schemes",
            default="CHAPS,FPS,BACS",
            help="Comma-separated schemes to listen on (default: all).",
        )

    def handle(self, *args, **options):
        requested = [s.strip().upper() for s in options["schemes"].split(",") if s.strip()]
        schemes = [s for s in requested if s in (Scheme.CHAPS, Scheme.FPS, Scheme.BACS)]
        if not schemes:
            self.stderr.write(self.style.ERROR("No valid schemes given."))
            return

        stop = threading.Event()
        threads = []
        for scheme in schemes:
            t = threading.Thread(
                target=listener.run_stream, args=(scheme, stop),
                name=f"ukps-{scheme}", daemon=True,
            )
            t.start()
            threads.append(t)

        self.stdout.write(self.style.SUCCESS(
            f"UKPS listener started for: {', '.join(schemes)}"
        ))
        try:
            while any(t.is_alive() for t in threads):
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("Stopping UKPS listener...")
            stop.set()
            for t in threads:
                t.join(timeout=5)
