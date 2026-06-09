# backend/cards/provider_client.py

import hashlib
import hmac
import json
import time

import requests
from django.conf import settings


def _signed_headers(body: str) -> dict:
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


def _post_signed(path: str, payload: dict) -> dict:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    response = requests.post(
        f"{settings.CARD_GATEWAY_BASE_URL}{path}",
        data=body,
        headers=_signed_headers(body),
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def _post_unsigned(path: str, payload: dict) -> dict:
    response = requests.post(
        f"{settings.CARD_GATEWAY_BASE_URL}{path}",
        json=payload,
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def _patch_with_api_key(path: str, payload: dict) -> dict:
    response = requests.patch(
        f"{settings.CARD_GATEWAY_BASE_URL}{path}",
        json=payload,
        headers={"X-API-Key": settings.CARD_GATEWAY_API_KEY},
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def _get(path: str) -> dict:
    response = requests.get(
        f"{settings.CARD_GATEWAY_BASE_URL}{path}",
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def issue_card(user_id: str, account_id: str, card_type: str, initial_balance=0) -> dict:
    return _post_signed(
        "/api/v1/cards/issue",
        {
            "user_id": str(user_id),
            "account_id": str(account_id),
            "card_type": card_type,
            "initial_balance": float(initial_balance),
        },
    )


def get_card(card_token: str) -> dict:
    return _get(f"/api/v1/cards/{card_token}")


def update_card_status(card_token: str, status: str, reason: str = "") -> dict:
    return _patch_with_api_key(
        f"/api/v1/cards/{card_token}/status",
        {
            "status": status,
            "reason": reason,
        },
    )


def activate_card(card_token: str) -> dict:
    return _post_unsigned(
        f"/api/v1/cards/{card_token}/activate",
        {
            "activated_by": "customer",
        },
    )


def topup_prepaid(card_token: str, amount, currency: str = "GBP") -> dict:
    return _post_unsigned(
        f"/api/v1/cards/{card_token}/topup",
        {
            "amount": float(amount),
            "currency": currency,
        },
    )