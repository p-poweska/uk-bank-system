"""SSE listener for inbound UKPS payments.

Each scheme exposes a server-sent-events endpoint that pushes events addressed
to our BIC. We open one long-lived stream per scheme, decode events and post
them to the local ledger via :func:`ukps.services.record_inbound`.

Events are in-memory upstream (no replay), so the listener must be running when
a payment settles. CHAPS/FPS emit ``payment.received``; BACS emits
``cycle.settled`` (a signal only — per-account crediting would need the cycle
settlement report and is left as a follow-up).
"""
import json
import logging
import time

import requests
from django.conf import settings
from django.db import close_old_connections

from . import services
from .models import Scheme

logger = logging.getLogger(__name__)

_INCOMING_PATH = {
    Scheme.CHAPS: "/v1/payments/chaps/incoming",
    Scheme.FPS: "/v1/payments/fps/incoming",
    Scheme.BACS: "/v1/payments/bacs/incoming",
}

RECONNECT_DELAY = 3


def _stream_url_and_key(scheme):
    reg = services.ensure_registered(scheme)
    return services._base_url(scheme) + _INCOMING_PATH[scheme], reg.api_key


def handle_event(scheme, event):
    """Map one decoded SSE event to a local ledger posting."""
    etype = event.get("type")
    data = event.get("data") or {}

    if etype == "payment.received":
        if scheme == Scheme.CHAPS:
            account_number = data.get("receiver_account") or ""
        else:
            # FPS events carry no destination account — use the fallback.
            account_number = getattr(settings, "UKPS_INBOUND_FALLBACK_ACCOUNT", "") or ""
        services.record_inbound(
            scheme=scheme,
            msg_id=str(data.get("msg_id") or ""),
            sender_bic=data.get("sender", ""),
            amount=data.get("amount"),
            account_number=account_number,
            raw_event=data,
        )
    elif etype == "cycle.settled":
        services.record_inbound(
            scheme=scheme,
            msg_id=f"cycle-{int(time.time())}",
            amount=None,
            account_number="",
            raw_event=data,
        )
        # A settled cycle is the moment our queued outbound BACS payments clear.
        try:
            services.reconcile_pending()
        except Exception:
            logger.exception("UKPS %s: reconcile after cycle.settled failed", scheme)
    else:
        logger.debug("UKPS %s: ignoring event type %r", scheme, etype)


def run_reconciler(stop_event=None, interval=30):
    """Periodically settle/fail outbound payments still pending locally.

    A safety net for BACS (in case a cycle.settled event was missed while
    disconnected) and for CHAPS/FPS payments that were queued rather than
    settled on submission.
    """
    def stopped():
        return stop_event is not None and stop_event.is_set()

    while not stopped():
        close_old_connections()
        try:
            res = services.reconcile_pending()
            if res["completed"] or res["failed"]:
                logger.info("UKPS reconcile: %s", res)
        except Exception:
            logger.exception("UKPS reconcile loop error")
        for _ in range(interval):
            if stopped():
                return
            time.sleep(1)


def run_stream(scheme, stop_event=None):
    """Consume one scheme's SSE stream forever, reconnecting on failure."""
    def stopped():
        return stop_event is not None and stop_event.is_set()

    while not stopped():
        try:
            url, api_key = _stream_url_and_key(scheme)
        except Exception as exc:
            logger.warning("UKPS %s: cannot start stream: %s", scheme, exc)
            time.sleep(RECONNECT_DELAY)
            continue

        try:
            logger.info("UKPS %s: connecting to %s", scheme, url)
            with requests.get(
                url,
                headers={"Authorization": f"Bearer {api_key}",
                         "Accept": "text/event-stream"},
                stream=True,
                timeout=(10, None),
            ) as resp:
                if resp.status_code != 200:
                    logger.warning("UKPS %s: stream HTTP %s", scheme, resp.status_code)
                    time.sleep(RECONNECT_DELAY)
                    continue
                logger.info("UKPS %s: listening for inbound payments", scheme)
                for raw in resp.iter_lines(decode_unicode=True):
                    if stopped():
                        return
                    if not raw or not raw.startswith("data:"):
                        continue
                    payload = raw[len("data:"):].strip()
                    if not payload:
                        continue
                    try:
                        event = json.loads(payload)
                    except ValueError:
                        logger.debug("UKPS %s: non-JSON event %r", scheme, payload)
                        continue
                    close_old_connections()
                    try:
                        handle_event(scheme, event)
                    except Exception:
                        logger.exception("UKPS %s: error handling event", scheme)
        except requests.RequestException as exc:
            logger.info("UKPS %s: stream dropped (%s), reconnecting", scheme, exc)

        if not stopped():
            time.sleep(RECONNECT_DELAY)
