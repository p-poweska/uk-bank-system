import uuid
from decimal import Decimal
from django.db import models

class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    account = models.ForeignKey(
        'accounts.Account', 
        on_delete=models.CASCADE, 
        related_name='cards'
    )
    
    
    external_card_id = models.CharField(max_length=100, blank=True, null=True) 
    
    
    class CardType(models.TextChoices):
        VIRTUAL = "VIRTUAL", "Virtual"
        PHYSICAL = "PHYSICAL", "Physical"
        PREPAID = "PREPAID", "Prepaid"

    card_type = models.CharField(
        max_length=20,
        choices=CardType.choices,
        default=CardType.VIRTUAL
    )

    # Wyświetlanie
    cardholder_name = models.CharField(max_length=100)
    masked_number = models.CharField(max_length=19) 
    expiry_date = models.CharField(max_length=5)    
    
    
    full_number = models.CharField(max_length=16, blank=True, null=True)
    cvv = models.CharField(max_length=3, blank=True, null=True)
    pin = models.CharField(max_length=4, blank=True, null=True)

    # Saldo karty Prepaid (wymóg dla konta Junior)
    prepaid_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal("0.00")
    )

    class CardStatus(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"     
        PROCESSING = "PROCESSING", "Processing"   
        SHIPPED = "SHIPPING", "Shipped"           
        ACTIVE = "ACTIVE", "Active"
        FROZEN = "FROZEN", "Frozen"
        BLOCKED = "BLOCKED", "Blocked"

    status = models.CharField(
        max_length=20,
        choices=CardStatus.choices,
        default=CardStatus.ACTIVE
    )

    is_archived = models.BooleanField(
    default=False,
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.card_type} ({self.masked_number}) - {self.status}"

class CardPaymentCapture(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="payment_captures",
    )

    local_transaction = models.OneToOneField(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="card_payment_capture",
    )

    provider_transaction_id = models.CharField(
        max_length=100,
        unique=True,
    )

    authorization_code = models.CharField(
        max_length=100,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="GBP",
    )

    merchant_id = models.CharField(
        max_length=100,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Capture {self.provider_transaction_id}: "
            f"{self.amount} {self.currency}"
        )