import uuid
import requests
from django.conf import settings


def klik_headers():
    return {
        "X-KLIK-Bank-Api-Key": settings.KLIK_BANK_API_KEY,
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }


def generate_klik_code(user_id: str):
    response = requests.post(
        f"{settings.KLIK_BASE_URL}/codes/generate",
        json={
            "user_id": str(user_id),
            "zone": settings.KLIK_ZONE,
        },
        headers=klik_headers(),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def confirm_klik_payment(transaction_id, decision: str, reject_reason: str | None = None):
    payload = {
        "transaction_id": str(transaction_id),
        "status": decision
    }

    if decision == "REJECTED":
        payload["reject_reason"] = reject_reason or "USER_DECLINED"

    response = requests.post(
        f"{settings.KLIK_BASE_URL}/payments/confirm",
        json=payload,
        headers=klik_headers(),
        timeout=10,
    )

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} Client Error: {response.text} for url: {response.url}",
            response=response,
        )

    return response.json()

def lookup_klik_alias(phone: str):
    response = requests.get(
        f"{settings.KLIK_BASE_URL}/aliases/lookup/{phone}",
        headers=klik_headers(),
        timeout=10,
    )

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} Client Error: {response.text} for url: {response.url}",
            response=response,
        )

    return response.json()

def register_klik_alias(phone: str, iban: str):
    response = requests.post(
        f"{settings.KLIK_BASE_URL}/aliases/register",
        json={
            "phone": phone,
            "iban": iban,
            "zone": settings.KLIK_ZONE,
        },
        headers=klik_headers(),
        timeout=10,
    )

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} Client Error: {response.text} for url: {response.url}",
            response=response,
        )

    return response.json()


def lookup_klik_alias(phone: str):
    response = requests.get(
        f"{settings.KLIK_BASE_URL}/aliases/lookup/{phone}",
        headers=klik_headers(),
        timeout=10,
    )

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} Client Error: {response.text} for url: {response.url}",
            response=response,
        )

    return response.json()


def delete_klik_alias(phone: str):
    response = requests.delete(
        f"{settings.KLIK_BASE_URL}/aliases/{phone}",
        headers=klik_headers(),
        timeout=10,
    )

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} Client Error: {response.text} for url: {response.url}",
            response=response,
        )

    if response.content:
        return response.json()

    return {}


def delete_klik_alias(phone: str):
    response = requests.delete(
        f"{settings.KLIK_BASE_URL}/aliases/{phone}",
        headers=klik_headers(),
        timeout=10,
    )

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} Client Error: {response.text} for url: {response.url}",
            response=response,
        )

    if response.content:
        return response.json()

    return {}

