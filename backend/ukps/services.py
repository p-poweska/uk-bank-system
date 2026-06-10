"""Client for the UK Payment Systems (UKPS) interbank schemes.

Outbound only: this bank submits CHAPS / FPS / BACS payments to the external
uk-payment-systems services. The bank auto-registers itself in each scheme on
first use and persists the returned API key.
"""
import uuid
import logging
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from . import standard18
from .models import Scheme, UKPSRegistration, UKPSPayment

logger = logging.getLogger(__name__)

TIMEOUT = 15


class UKPSError(Exception):
    """Raised when a scheme cannot accept a payment (rejection or transport)."""


def _base_url(scheme: str) -> str:
    return {
        Scheme.CHAPS: settings.UKPS_CHAPS_URL,
        Scheme.FPS: settings.UKPS_FPS_URL,
        Scheme.BACS: settings.UKPS_BACS_URL,
    }[scheme]


def _su_code() -> str:
    return getattr(settings, "UKPS_BANK_SU_CODE", settings.UKPS_BANK_BIC[:6])


def _configured_key(scheme: str) -> str:
    return {
        Scheme.CHAPS: getattr(settings, "UKPS_CHAPS_API_KEY", ""),
        Scheme.FPS: getattr(settings, "UKPS_FPS_API_KEY", ""),
        Scheme.BACS: getattr(settings, "UKPS_BACS_API_KEY", ""),
    }.get(scheme, "")


def new_msg_id() -> str:
    """A scheme message id, <= 35 chars."""
    return f"LYO{uuid.uuid4().hex[:20]}".upper()


# --------------------------------------------------------------------------- #
# Identifier helpers
# --------------------------------------------------------------------------- #
def sort_code_from_iban(iban: str) -> str:
    """Extract a dashed UK sort code from a GB IBAN (positions 8-14)."""
    iban = (iban or "").replace(" ", "").upper()
    if iban.startswith("GB") and len(iban) >= 14 and iban[8:14].isdigit():
        d = iban[8:14]
        return f"{d[0:2]}-{d[2:4]}-{d[4:6]}"
    return ""


def account_from_iban(iban: str) -> str:
    iban = (iban or "").replace(" ", "").upper()
    if iban.startswith("GB") and len(iban) >= 22:
        return iban[14:22]
    return ""


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register(scheme: str) -> UKPSRegistration:
    """Register this bank in a scheme and persist the API key (returned once)."""
    payload = {
        "bic": settings.UKPS_BANK_BIC,
        "name": settings.UKPS_BANK_NAME,
        "sort_code": settings.UKPS_BANK_SORT_CODE,
        "balance": float(settings.UKPS_INITIAL_LIQUIDITY),
        # FPS-specific (ignored by other schemes):
        "participant_type": "DIRECT",
        # BACS-specific (ignored by other schemes):
        "su_code": _su_code(),
        "is_service_user": True,
        "is_destination_user": True,
    }
    resp = requests.post(
        f"{_base_url(scheme)}/v1/participants/register", json=payload, timeout=TIMEOUT
    )
    if resp.status_code >= 400:
        raise UKPSError(
            f"{scheme} registration failed: {resp.status_code} {resp.text}"
        )
    data = resp.json()
    reg, _ = UKPSRegistration.objects.update_or_create(
        scheme=scheme,
        defaults={
            "bic": settings.UKPS_BANK_BIC,
            "name": settings.UKPS_BANK_NAME,
            "sort_code": settings.UKPS_BANK_SORT_CODE,
            "api_key": data["api_key"],
        },
    )
    logger.info("Registered bank in %s as %s", scheme, settings.UKPS_BANK_BIC)
    return reg


def ensure_registered(scheme: str) -> UKPSRegistration:
    """Return a usable registration for ``scheme``.

    Preference order: a stored registration, then a configured pre-seeded API
    key, then (only if UKPS_AUTO_REGISTER is on) dynamic self-registration.
    """
    reg = UKPSRegistration.objects.filter(scheme=scheme).first()
    if reg:
        return reg

    configured = _configured_key(scheme)
    if configured:
        reg, _ = UKPSRegistration.objects.update_or_create(
            scheme=scheme,
            defaults={
                "bic": settings.UKPS_BANK_BIC,
                "name": settings.UKPS_BANK_NAME,
                "sort_code": settings.UKPS_BANK_SORT_CODE,
                "api_key": configured,
            },
        )
        return reg

    if getattr(settings, "UKPS_AUTO_REGISTER", False):
        return register(scheme)

    raise UKPSError(
        f"No API key configured for {scheme} and auto-registration is disabled"
    )


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #
def _auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _send_json_scheme(scheme, api_key, *, receiver_bic, receiver_sort_code,
                      amount, msg_id, end_to_end_id):
    """CHAPS / FPS share the same JSON submission contract."""
    path = "/v1/payments/chaps" if scheme == Scheme.CHAPS else "/v1/payments/fps"
    resp = requests.post(
        f"{_base_url(scheme)}{path}",
        json={
            "msg_id": msg_id,
            "end_to_end_id": end_to_end_id,
            "receiver_bic": receiver_bic,
            "receiver_sort_code": receiver_sort_code,
            "amount": float(amount),
        },
        headers=_auth_headers(api_key),
        timeout=TIMEOUT,
    )
    return resp


def _send_bacs(reg, *, receiver_sort_code, receiver_account, amount, reference, msg_id):
    content = standard18.build_credit_file(
        originator_sort_code=settings.UKPS_BANK_SORT_CODE,
        originator_account="00000000",
        originator_name=settings.UKPS_BANK_NAME,
        su_code=_su_code(),
        date=date.today().strftime("%y%m%d"),
        credits=[{
            "dest_sort_code": receiver_sort_code,
            "dest_account": receiver_account,
            "amount": amount,
            "reference": (reference or msg_id)[:14],
        }],
    )
    resp = requests.post(
        f"{_base_url(Scheme.BACS)}/v1/payments/bacs/submit",
        params={"filename": f"{msg_id}.txt"},
        data=content.encode("ascii"),
        headers={
            "Authorization": f"Bearer {reg.api_key}",
            "Content-Type": "text/plain",
        },
        timeout=TIMEOUT,
    )
    return resp


# Statuses that mean the bank may safely debit the sender.
SUCCESS_STATUSES = {"SETTLED", "QUEUED", "RECEIVED"}


def send_payment(*, scheme, receiver_bic, amount, recipient_account="",
                 receiver_sort_code="", reference="", transfer=None) -> UKPSPayment:
    """Submit one outbound payment to a UKPS scheme and record the result.

    Returns a persisted :class:`UKPSPayment`. Check ``.status`` against
    :data:`SUCCESS_STATUSES` to decide whether to move funds locally.
    """
    scheme = str(scheme).upper()
    if scheme not in (Scheme.CHAPS, Scheme.FPS, Scheme.BACS):
        raise UKPSError(f"Unknown scheme {scheme!r}")

    if not receiver_sort_code:
        receiver_sort_code = sort_code_from_iban(recipient_account)
    receiver_account = account_from_iban(recipient_account)
    msg_id = new_msg_id()

    payment = UKPSPayment(
        transfer=transfer,
        scheme=scheme,
        msg_id=msg_id,
        sender_bic=settings.UKPS_BANK_BIC,
        receiver_bic=receiver_bic,
        receiver_sort_code=receiver_sort_code,
        amount=Decimal(str(amount)),
        status="FAILED",
    )

    try:
        reg = ensure_registered(scheme)
        if scheme == Scheme.BACS:
            resp = _send_bacs(
                reg, receiver_sort_code=receiver_sort_code,
                receiver_account=receiver_account, amount=amount,
                reference=reference, msg_id=msg_id,
            )
        else:
            resp = _send_json_scheme(
                scheme, reg.api_key, receiver_bic=receiver_bic,
                receiver_sort_code=receiver_sort_code, amount=amount,
                msg_id=msg_id, end_to_end_id=msg_id,
            )
    except (requests.RequestException, UKPSError) as exc:
        payment.reason_code = str(exc)[:64]
        payment.save()
        logger.warning("UKPS %s payment transport error: %s", scheme, exc)
        return payment

    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text[:500]}
    payment.raw_response = body

    if scheme == Scheme.BACS:
        if resp.status_code in (200, 201, 202):
            payment.status = "RECEIVED"
            payment.external_id = str(body.get("id", ""))
        else:
            payment.status = "FAILED"
            payment.reason_code = str(body.get("error", resp.status_code))[:64]
    else:
        status = (body.get("status") or "").upper()
        payment.reason_code = (body.get("reason_code") or "")[:64]
        if status in ("SETTLED", "QUEUED", "REJECTED"):
            payment.status = status
        elif resp.status_code == 200:
            payment.status = "SETTLED"
        else:
            payment.status = "FAILED"
            if not payment.reason_code:
                payment.reason_code = str(
                    body.get("error") or body.get("raw") or resp.status_code
                ).strip()[:64]

    payment.save()
    return payment
