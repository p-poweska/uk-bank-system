import html
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

import requests
from django.conf import settings


MONEY = Decimal("0.01")
RATE_SCALE = Decimal("0.00000001")


COUNTRY_CURRENCY = {
    "GB": "GBP",
    "US": "USD",
    "PL": "PLN",
    "DE": "EUR",
    "FR": "EUR",
}


CHARGE_TO_SWIFT = {
    "OUR": "DEBT",  # sender/debtor pays
    "SHA": "SHAR",  # shared
    "BEN": "CRED",  # receiver/creditor pays
    "DEBT": "DEBT",
    "SHAR": "SHAR",
    "CRED": "CRED",
}


SWIFT_TO_DISPLAY = {
    "DEBT": "OUR",
    "SHAR": "SHA",
    "CRED": "BEN",
}


class SwiftClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        payload: Optional[dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


@dataclass(frozen=True)
class SwiftPricing:
    sent_amount: Decimal
    sent_currency: str
    debited_amount: Decimal
    debited_currency: str
    exchange_rate: Decimal
    fee_amount: Decimal
    total_debit: Decimal
    charge_bearer: str
    swift_charge_bearer: str


@dataclass(frozen=True)
class SwiftSubmission:
    status: str
    message_id: str
    uetr: str
    receiver_bank: str
    route: list
    estimated_seconds: Decimal
    fee_breakdown: Dict
    auto_send_status: str
    auto_send_payload: Dict


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _rate(value) -> Decimal:
    return Decimal(str(value)).quantize(RATE_SCALE, rounding=ROUND_HALF_UP)


def currency_for_bic(bic: str) -> str:
    bic = (bic or "").strip().upper()

    if len(bic) < 6:
        return ""

    country_code = bic[4:6]
    return COUNTRY_CURRENCY.get(country_code, "")


def normalize_charge_bearer(value: str) -> str:
    value = (value or "SHA").strip().upper()

    if value in SWIFT_TO_DISPLAY:
        value = SWIFT_TO_DISPLAY[value]

    if value not in {"OUR", "SHA", "BEN"}:
        value = "SHA"

    return value


def exchange_rate(source_currency: str, target_currency: str) -> Decimal:
    source_currency = (source_currency or "GBP").upper()
    target_currency = (target_currency or "GBP").upper()

    if source_currency == target_currency:
        return Decimal("1.00000000")

    configured = getattr(settings, "SWIFT_EXCHANGE_RATES", {})

    raw = configured.get((source_currency, target_currency))
    if raw is not None:
        return _rate(raw)

    reverse = configured.get((target_currency, source_currency))
    if reverse is not None:
        reverse_rate = Decimal(str(reverse))

        if reverse_rate == 0:
            raise SwiftClientError(
                f"Invalid exchange rate for {target_currency}/{source_currency}."
            )

        return _rate(Decimal("1") / reverse_rate)

    raise SwiftClientError(
        f"No fixed SWIFT exchange rate for {source_currency} → {target_currency}."
    )


def local_fee(source_currency: str, charge_bearer: str) -> Decimal:
    source_currency = (source_currency or "GBP").upper()
    charge_bearer = normalize_charge_bearer(charge_bearer)

    if source_currency != "GBP":
        raise SwiftClientError(
            "Local SWIFT fees are configured only for GBP accounts in this project."
        )

    if charge_bearer == "OUR":
        return _money(getattr(settings, "SWIFT_FEE_OUR_GBP", "15.00"))

    if charge_bearer == "BEN":
        return _money(getattr(settings, "SWIFT_FEE_BEN_GBP", "0.00"))

    return _money(getattr(settings, "SWIFT_FEE_SHA_GBP", "5.00"))


def calculate_pricing(
    sent_amount,
    sent_currency: str,
    debited_currency: str = "GBP",
    charge_bearer: str = "SHA",
) -> SwiftPricing:
    sent_amount = _money(sent_amount)
    sent_currency = (sent_currency or "").upper()
    debited_currency = (debited_currency or "GBP").upper()
    charge_bearer = normalize_charge_bearer(charge_bearer)

    if sent_amount <= 0:
        raise SwiftClientError("SWIFT amount must be greater than zero.")

    if not sent_currency:
        raise SwiftClientError("SWIFT transfer currency is required.")

    fx = exchange_rate(debited_currency, sent_currency)
    debited_without_fee = _money(sent_amount / fx)
    fee = local_fee(debited_currency, charge_bearer)
    total = _money(debited_without_fee + fee)

    return SwiftPricing(
        sent_amount=sent_amount,
        sent_currency=sent_currency,
        debited_amount=debited_without_fee,
        debited_currency=debited_currency,
        exchange_rate=fx,
        fee_amount=fee,
        total_debit=total,
        charge_bearer=charge_bearer,
        swift_charge_bearer=CHARGE_TO_SWIFT[charge_bearer],
    )


def _swift_base_url() -> str:
    return getattr(settings, "SWIFT_BASE_URL", "http://host.docker.internal:3000").rstrip("/")


def _safe_json(response) -> dict:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def _get_access_token() -> str:
    url = f"{_swift_base_url()}/auth/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": getattr(settings, "SWIFT_CLIENT_ID", "bank-ukbkgb01"),
        "client_secret": getattr(settings, "SWIFT_CLIENT_SECRET", "secret-ukbkgb01"),
    }

    try:
        response = requests.post(
            url,
            data=data,
            timeout=getattr(settings, "SWIFT_TIMEOUT_SECONDS", 15),
        )
    except requests.RequestException as exc:
        raise SwiftClientError(
            f"Could not connect to SWIFT token endpoint: {exc}"
        ) from exc

    payload = _safe_json(response)

    if response.status_code >= 400:
        raise SwiftClientError(
            "SWIFT authentication failed.",
            status_code=response.status_code,
            payload=payload,
        )

    token = payload.get("access_token")

    if not token:
        raise SwiftClientError(
            "SWIFT token response did not contain access_token.",
            payload=payload,
        )

    return token


def build_pacs008_xml(
    *,
    sender_name: str,
    sender_account: str,
    receiver_name: str,
    receiver_account: str,
    receiver_bic: str,
    amount: Decimal,
    currency: str,
    charge_bearer: str,
    title: str,
    message_id: Optional[str] = None,
    instruction_id: Optional[str] = None,
    end_to_end_id: Optional[str] = None,
    uetr: Optional[str] = None,
) -> tuple[str, str, str]:
    now = datetime.now(timezone.utc)

    message_id = message_id or f"LYO-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    instruction_id = instruction_id or f"INST-{uuid.uuid4().hex[:12]}"
    end_to_end_id = end_to_end_id or f"E2E-{uuid.uuid4().hex[:12]}"
    uetr = uetr or str(uuid.uuid4())

    sender_bic = getattr(settings, "SWIFT_BANK_BIC", "UKBKGB01XXX")
    sender_bank_name = getattr(settings, "SWIFT_BANK_NAME", "Lyo Bank")

    amount = _money(amount)
    currency = currency.upper()
    receiver_bic = receiver_bic.upper()
    charge_bearer = CHARGE_TO_SWIFT.get(
        normalize_charge_bearer(charge_bearer),
        "SHAR",
    )

    esc = html.escape

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>{esc(message_id)}</MsgId>
      <CreDtTm>{now.strftime('%Y-%m-%dT%H:%M:%SZ')}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf>
        <SttlmMtd>INDA</SttlmMtd>
      </SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>{esc(instruction_id)}</InstrId>
        <EndToEndId>{esc(end_to_end_id)}</EndToEndId>
        <UETR>{esc(uetr)}</UETR>
      </PmtId>

      <IntrBkSttlmAmt Ccy="{esc(currency)}">{amount:.2f}</IntrBkSttlmAmt>
      <IntrBkSttlmDt>{date.today().isoformat()}</IntrBkSttlmDt>
      <InstdAmt Ccy="{esc(currency)}">{amount:.2f}</InstdAmt>
      <ChrgBr>{esc(charge_bearer)}</ChrgBr>

      <InstgAgt>
        <FinInstnId>
          <BICFI>{esc(sender_bic)}</BICFI>
        </FinInstnId>
      </InstgAgt>

      <InstdAgt>
        <FinInstnId>
          <BICFI>{esc(receiver_bic)}</BICFI>
        </FinInstnId>
      </InstdAgt>

      <Dbtr>
        <Nm>{esc(sender_name or sender_bank_name)}</Nm>
      </Dbtr>

      <DbtrAcct>
        <Id>
          <IBAN>{esc(sender_account)}</IBAN>
        </Id>
      </DbtrAcct>

      <DbtrAgt>
        <FinInstnId>
          <BICFI>{esc(sender_bic)}</BICFI>
        </FinInstnId>
      </DbtrAgt>

      <CdtrAgt>
        <FinInstnId>
          <BICFI>{esc(receiver_bic)}</BICFI>
        </FinInstnId>
      </CdtrAgt>

      <Cdtr>
        <Nm>{esc(receiver_name or "External payee")}</Nm>
      </Cdtr>

      <CdtrAcct>
        <Id>
          <Othr>
            <Id>{esc(receiver_account)}</Id>
          </Othr>
        </Id>
      </CdtrAcct>

      <RmtInf>
        <Ustrd>{esc(title or "SWIFT transfer")}</Ustrd>
      </RmtInf>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>'''

    return xml, message_id, uetr


def submit_message(xml: str) -> dict:
    token = _get_access_token()

    url = f"{_swift_base_url()}/swift/message"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/xml; charset=utf-8",
    }

    try:
        response = requests.post(
            url,
            data=xml.encode("utf-8"),
            headers=headers,
            timeout=getattr(settings, "SWIFT_TIMEOUT_SECONDS", 15),
        )
    except requests.RequestException as exc:
        raise SwiftClientError(
            f"Could not connect to SWIFT message endpoint: {exc}"
        ) from exc

    payload = _safe_json(response)

    if response.status_code >= 400:
        message = payload.get("error") or (
            f"SWIFT rejected the message with status {response.status_code}."
        )
        raise SwiftClientError(
            message,
            status_code=response.status_code,
            payload=payload,
        )

    return payload


def auto_send(uetr: str) -> tuple[str, Dict]:
    if not getattr(settings, "SWIFT_AUTO_SEND", True):
        return "manual", {}

    url = f"{_swift_base_url()}/api/send/{uetr}"

    try:
        response = requests.post(
            url,
            timeout=getattr(settings, "SWIFT_TIMEOUT_SECONDS", 15),
        )
    except requests.RequestException as exc:
        raise SwiftClientError(
            f"Could not schedule SWIFT message for sending: {exc}"
        ) from exc

    payload = _safe_json(response)

    if response.status_code >= 400:
        message = payload.get("error") or (
            f"SWIFT scheduling failed with status {response.status_code}."
        )
        raise SwiftClientError(
            message,
            status_code=response.status_code,
            payload=payload,
        )

    return payload.get("status", "scheduled"), payload


def send_payment(
    *,
    sender_name: str,
    sender_account: str,
    receiver_name: str,
    receiver_account: str,
    receiver_bic: str,
    amount: Decimal,
    currency: str,
    charge_bearer: str,
    title: str,
) -> SwiftSubmission:
    xml, message_id, uetr = build_pacs008_xml(
        sender_name=sender_name,
        sender_account=sender_account,
        receiver_name=receiver_name,
        receiver_account=receiver_account,
        receiver_bic=receiver_bic,
        amount=amount,
        currency=currency,
        charge_bearer=charge_bearer,
        title=title,
    )

    result = submit_message(xml)

    result_uetr = result.get("uetr") or uetr
    auto_status, auto_payload = auto_send(result_uetr)

    return SwiftSubmission(
        status=result.get("status", "accepted"),
        message_id=result.get("message_id") or message_id,
        uetr=result_uetr,
        receiver_bank=result.get("receiver_bank", ""),
        route=result.get("route", []),
        estimated_seconds=Decimal(str(result.get("estimated_seconds", "0"))),
        fee_breakdown=result.get("fee_breakdown", {}),
        auto_send_status=auto_status,
        auto_send_payload=auto_payload,
    )