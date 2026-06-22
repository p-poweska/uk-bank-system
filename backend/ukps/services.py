"""Client for the UK Payment Systems (UKPS) interbank schemes.

Outbound only: this bank submits CHAPS / FPS / BACS payments to the external
uk-payment-systems services. The bank auto-registers itself in each scheme on
first use and persists the returned API key.
"""
import time
import uuid
import logging
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from . import standard18
from .models import Scheme, UKPSRegistration, UKPSPayment, UKPSInboundPayment

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

def normalize_sort_code(sort_code: str) -> str:
    digits = "".join(ch for ch in str(sort_code or "") if ch.isdigit())

    if len(digits) == 6:
        return f"{digits[0:2]}-{digits[2:4]}-{digits[4:6]}"

    return str(sort_code or "").strip()


def bic_from_sort_code(sort_code: str) -> str:
    sort_code = normalize_sort_code(sort_code)
    directory = getattr(settings, "UKPS_SORT_CODE_TO_BIC", {})
    return (directory.get(sort_code) or "").strip().upper()


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
                      receiver_account, amount, msg_id, end_to_end_id):
    """CHAPS / FPS share the same JSON submission contract."""
    path = "/v1/payments/chaps" if scheme == Scheme.CHAPS else "/v1/payments/fps"

    payload = {
        "msg_id": msg_id,
        "end_to_end_id": end_to_end_id,
        "receiver_bic": receiver_bic,
        "receiver_sort_code": receiver_sort_code,
        "receiver_account": receiver_account,
        "amount": float(amount),
    }

    resp = requests.post(
        f"{_base_url(scheme)}{path}",
        json=payload,
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
    if not receiver_sort_code:
        receiver_sort_code = sort_code_from_iban(recipient_account)

    receiver_sort_code = normalize_sort_code(receiver_sort_code)
    receiver_account = account_from_iban(recipient_account)

    if not receiver_bic:
        receiver_bic = bic_from_sort_code(receiver_sort_code)

    receiver_bic = (receiver_bic or "").strip().upper()

    if not receiver_bic:
        raise UKPSError(
            f"Could not resolve recipient bank BIC from sort code '{receiver_sort_code}'."
        )

    if not receiver_sort_code:
        raise UKPSError("Could not resolve recipient sort code from recipient account.")

    if scheme == Scheme.BACS and not receiver_account:
        raise UKPSError("BACS requires a UK IBAN containing an 8-digit account number.")

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
                scheme,
                reg.api_key,
                receiver_bic=receiver_bic,
                receiver_sort_code=receiver_sort_code,
                receiver_account=receiver_account,
                amount=amount,
                msg_id=msg_id,
                end_to_end_id=msg_id,
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


# --------------------------------------------------------------------------- #
# Receiving (inbound)
# --------------------------------------------------------------------------- #
def _account_owner(account):
    owner = account.customer.user
    if not owner and account.customer.parent_customer:
        owner = account.customer.parent_customer.user
    return owner


def record_inbound(*, scheme, msg_id, sender_bic="", amount=None,
                   account_number="", raw_event=None):
    """Idempotently record a received UKPS payment and credit it if possible.

    Returns (UKPSInboundPayment, created: bool). Dedupes on (scheme, msg_id)
    because the in-memory SSE bus can redeliver across reconnects.
    """
    from django.db import IntegrityError, transaction as db_tx
    from accounts.models import Account
    from transactions.models import Transaction
    from notifications.utils import notify

    scheme = str(scheme).upper()

    existing = UKPSInboundPayment.objects.filter(scheme=scheme, msg_id=msg_id).first()
    if existing:
        return existing, False

    amount_dec = Decimal(str(amount)) if amount is not None else None

    try:
        with db_tx.atomic():
            account = None
            if account_number:
                account = (
                    Account.objects.select_for_update()
                    .filter(account_number=account_number).first()
                )

            if account and amount_dec is not None:
                status = "CREDITED"
            elif scheme == Scheme.BACS and amount_dec is None:
                status = "CYCLE_SETTLED"
            else:
                status = "UNMATCHED"

            inbound = UKPSInboundPayment.objects.create(
                scheme=scheme, msg_id=msg_id, sender_bic=sender_bic or "",
                amount=amount_dec, account=account,
                account_number=account_number or "", status=status,
                raw_event=raw_event,
            )

            if status == "CREDITED":
                account.balance += amount_dec
                account.available_balance += amount_dec
                account.save()

                owner = _account_owner(account)
                if owner:
                    Transaction.objects.create(
                        user=owner, account=account, amount=amount_dec,
                        title=f"Inbound {scheme} from {sender_bic or 'bank'}",
                        balance_after=account.available_balance,
                    )
                    notify(owner, "Money received",
                           f"You received £{amount_dec} via {scheme}.")
    except IntegrityError:
        # Lost a race with another delivery of the same event.
        existing = UKPSInboundPayment.objects.filter(scheme=scheme, msg_id=msg_id).first()
        return existing, False

    logger.info("Inbound %s %s -> %s [%s]", scheme, msg_id, account_number, inbound.status)
    return inbound, True


# --------------------------------------------------------------------------- #
# Inbound BACS (credited from the settled-liquidity delta)
# --------------------------------------------------------------------------- #
def _bacs_balance():
    """Return (our current BACS liquidity, the BACS registration)."""
    reg = ensure_registered(Scheme.BACS)
    resp = requests.get(
        f"{_base_url(Scheme.BACS)}/v1/participants/positions",
        headers={"Authorization": f"Bearer {reg.api_key}"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return Decimal(str(resp.json().get("balance", 0))), reg


def credit_bacs_settlement():
    """Credit inbound BACS by the increase in our settled liquidity.

    The BACS ``cycle.settled`` event carries no amount/account, and the netting
    report cannot reliably target the just-settled cycle (same-day cycles share
    an input_date). Instead we track our BACS liquidity: any positive delta at a
    settlement is the net amount we received, which we post to the fallback
    account. (Net, not gross — exact when the bank only receives in a cycle.)
    """
    from django.db import transaction as db_tx
    from accounts.models import Account
    from transactions.models import Transaction
    from notifications.utils import notify

    try:
        balance, _ = _bacs_balance()
    except (requests.RequestException, UKPSError, ValueError) as exc:
        logger.warning("BACS settlement: cannot read position: %s", exc)
        return

    fallback = getattr(settings, "UKPS_INBOUND_FALLBACK_ACCOUNT", "") or ""

    with db_tx.atomic():
        reg = UKPSRegistration.objects.select_for_update().get(scheme=Scheme.BACS)

        # First observation just sets the baseline — never credit historical balance.
        if reg.bacs_settled_balance is None:
            reg.bacs_settled_balance = balance
            reg.save(update_fields=["bacs_settled_balance"])
            return

        delta = balance - reg.bacs_settled_balance
        reg.bacs_settled_balance = balance
        reg.save(update_fields=["bacs_settled_balance"])
        if delta <= 0:
            return  # net outflow (our own outbound) or nothing received

        account = (
            Account.objects.select_for_update().filter(account_number=fallback).first()
            if fallback else None
        )
        inbound = UKPSInboundPayment.objects.create(
            scheme=Scheme.BACS, msg_id=f"bacs-settle-{int(time.time()*1000)}",
            sender_bic="", amount=delta, account=account,
            account_number=fallback, status="CREDITED" if account else "UNMATCHED",
            raw_event={"source": "bacs_settlement_delta", "balance": str(balance)},
        )
        if account:
            account.balance += delta
            account.available_balance += delta
            account.save()
            owner = _account_owner(account)
            if owner:
                Transaction.objects.create(
                    user=owner, account=account, amount=delta,
                    title="Inbound BACS settlement",
                    balance_after=account.available_balance,
                )
                notify(owner, "Money received", f"You received £{delta} via BACS.")

    logger.info("BACS settlement: credited £%s to %s [%s]", delta, fallback, inbound.status)


# --------------------------------------------------------------------------- #
# Reconciliation of outbound payments that settle asynchronously
# --------------------------------------------------------------------------- #
def _finalise_outbound(payment, *, completed: bool, reason: str = ""):
    """Mark a PENDING outbound payment's transfer COMPLETED or FAILED.

    On failure the sender is refunded, since the funds were debited optimistically
    when the payment was accepted.
    """
    from django.db import transaction as db_tx
    from transactions.models import Transaction
    from notifications.utils import notify

    transfer = payment.transfer
    with db_tx.atomic():
        payment.status = "SETTLED" if completed else "FAILED"
        if reason:
            payment.reason_code = reason[:64]
        payment.save(update_fields=["status", "reason_code"])

        if not transfer or transfer.status != "PENDING":
            return

        if completed:
            transfer.status = "COMPLETED"
            transfer.save(update_fields=["status"])
            owner = _account_owner(transfer.from_account)
            if owner:
                notify(owner, "Transfer settled",
                       f"Your £{transfer.amount} {payment.scheme} transfer to "
                       f"{transfer.recipient_name} has settled.")
        else:
            transfer.status = "FAILED"
            transfer.save(update_fields=["status"])
            # Refund the optimistic debit.
            acc = transfer.from_account
            acc.balance += transfer.amount
            acc.available_balance += transfer.amount
            acc.save()
            owner = _account_owner(acc)
            if owner:
                Transaction.objects.create(
                    user=owner, account=acc, transfer=transfer,
                    amount=transfer.amount,
                    title=f"Refund: {payment.scheme} transfer not settled",
                    balance_after=acc.available_balance,
                )
                notify(owner, "Transfer failed",
                       f"Your £{transfer.amount} {payment.scheme} transfer to "
                       f"{transfer.recipient_name} could not be settled and was refunded.")


def _reconcile_bacs(payment) -> str | None:
    reg = ensure_registered(Scheme.BACS)
    headers = {"Authorization": f"Bearer {reg.api_key}"}
    if not payment.external_id:
        return None

    sub = requests.get(
        f"{_base_url(Scheme.BACS)}/v1/payments/bacs/submit/{payment.external_id}",
        headers=headers, timeout=TIMEOUT,
    )
    if sub.status_code != 200:
        return None
    sub_body = sub.json()
    if (sub_body.get("status") or "").upper() == "RECALLED":
        _finalise_outbound(payment, completed=False, reason="BACS submission recalled")
        return "failed"

    sub_cycle = sub_body.get("cycle_id")
    cur = requests.get(
        f"{_base_url(Scheme.BACS)}/v1/payments/bacs/cycle/current",
        headers=headers, timeout=TIMEOUT,
    )
    # No open cycle (briefly, between close and open) — try again later.
    if cur.status_code != 200:
        return None
    cur_id = cur.json().get("id")

    # The submission's cycle has been superseded by a newer open cycle, so it
    # has closed and settled.
    if sub_cycle and cur_id and int(sub_cycle) < int(cur_id):
        _finalise_outbound(payment, completed=True)
        return "completed"
    return None


def _reconcile_json(payment) -> str | None:
    """CHAPS / FPS: look our payment up by msg_id and read its current status."""
    reg = ensure_registered(payment.scheme)
    path = "/v1/payments/chaps" if payment.scheme == Scheme.CHAPS else "/v1/payments/fps"
    resp = requests.get(
        f"{_base_url(payment.scheme)}{path}",
        headers={"Authorization": f"Bearer {reg.api_key}"},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    body = resp.json()
    items = body if isinstance(body, list) else body.get("payments", [])
    match = next((p for p in items if str(p.get("msg_id")) == payment.msg_id), None)
    if not match:
        return None
    status = (match.get("status") or "").upper()
    if status in ("ACTC", "SETTLED", "COMPLETED"):
        _finalise_outbound(payment, completed=True)
        return "completed"
    if status in ("RJCT", "REJECTED", "FAILED"):
        _finalise_outbound(payment, completed=False, reason=f"{payment.scheme} {status}")
        return "failed"
    return None


def reconcile_pending() -> dict:
    """Settle/fail outbound payments still PENDING locally that have resolved upstream."""
    results = {"checked": 0, "completed": 0, "failed": 0}
    pending = UKPSPayment.objects.filter(
        status__in=["RECEIVED", "QUEUED"],
        transfer__status="PENDING",
    ).select_related("transfer", "transfer__from_account")

    for payment in pending:
        results["checked"] += 1
        try:
            if payment.scheme == Scheme.BACS:
                outcome = _reconcile_bacs(payment)
            else:
                outcome = _reconcile_json(payment)
        except (requests.RequestException, UKPSError, ValueError) as exc:
            logger.debug("reconcile %s skipped: %s", payment.msg_id, exc)
            continue
        if outcome == "completed":
            results["completed"] += 1
        elif outcome == "failed":
            results["failed"] += 1
    return results
