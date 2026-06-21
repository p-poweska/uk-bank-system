from decimal import Decimal

from django.db import models
from django.db.models import Q


class PaymentChannel(models.TextChoices):
    CARD = "CARD", "Card"
    BLIK = "BLIK", "KLIK code payment"
    BLIK_PHONE = "BLIK_PHONE", "KLIK phone transfer"


class AccountLimits(models.Model):
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="limits",
    )

    # Null = limit konta, np. KLIK/BLIK.
    # Nie-null = limit konkretnej karty.
    card = models.ForeignKey(
        "cards.Card",
        on_delete=models.CASCADE,
        related_name="limits",
        null=True,
        blank=True,
    )

    channel = models.CharField(
        max_length=30,
        choices=PaymentChannel.choices,
    )

    per_transaction_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    daily_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "channel"],
                condition=Q(card__isnull=True),
                name="unique_account_channel_limit",
            ),
            models.UniqueConstraint(
                fields=["card", "channel"],
                condition=Q(card__isnull=False),
                name="unique_card_channel_limit",
            ),
        ]

    @staticmethod
    def defaults_for(account_type):
        if account_type == "JUNIOR":
            return {
                PaymentChannel.BLIK: {
                    "per_transaction_limit": Decimal("0.00"),
                    "daily_limit": Decimal("0.00"),
                },
                PaymentChannel.BLIK_PHONE: {
                    "per_transaction_limit": Decimal("0.00"),
                    "daily_limit": Decimal("0.00"),
                },
            }

        return {
            PaymentChannel.BLIK: {
                "per_transaction_limit": Decimal("100.00"),
                "daily_limit": Decimal("300.00"),
            },
            PaymentChannel.BLIK_PHONE: {
                "per_transaction_limit": Decimal("150.00"),
                "daily_limit": Decimal("500.00"),
            },
        }

    @staticmethod
    def card_defaults_for(account_type, card_type):
        if account_type == "JUNIOR":
            return {
                "per_transaction_limit": Decimal("20.00"),
                "daily_limit": Decimal("50.00"),
            }

        if card_type == "PREPAID":
            return {
                "per_transaction_limit": Decimal("100.00"),
                "daily_limit": Decimal("300.00"),
            }

        if card_type == "VIRTUAL":
            return {
                "per_transaction_limit": Decimal("250.00"),
                "daily_limit": Decimal("1000.00"),
            }

        return {
            "per_transaction_limit": Decimal("500.00"),
            "daily_limit": Decimal("2000.00"),
        }

    def __str__(self):
        if self.card_id:
            return f"{self.account.account_number} - {self.channel} - {self.card.masked_number}"

        return f"{self.account.account_number} - {self.channel}"