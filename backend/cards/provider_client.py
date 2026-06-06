import hashlib
import hmac
import json
import time
import requests
from django.conf import settings


def _signed_headers(body: str):
    timestamp = str(int(time.time()))

    signature = hmac.new(
        settings.CARD_GATEWAY_HMAC_SECRET.encode("utf-8"),
        f"{timestamp}{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "X-API-Key": settings.CARD_GATEWAY_API_KEY,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }


def issue_card(user_id: str, account_id: str, card_type: str):
    payload = {
        "user_id": str(user_id),
        "account_id": str(account_id),
        "card_type": card_type,
        "initial_balance": 0,
    }

    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    response = requests.post(
        f"{settings.CARD_GATEWAY_BASE_URL}/api/v1/cards/issue",
        data=body,
        headers=_signed_headers(body),
        timeout=15,
    )

    return response.json()