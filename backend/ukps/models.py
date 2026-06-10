from django.db import models


class Scheme(models.TextChoices):
    CHAPS = "CHAPS", "CHAPS"
    FPS = "FPS", "Faster Payments"
    BACS = "BACS", "BACS"


class UKPSRegistration(models.Model):
    """This bank's participant registration in a single UKPS scheme.

    The API key is returned only once at registration, so it is persisted here
    and treated as the source of truth for authenticating outbound payments.
    """

    scheme = models.CharField(max_length=8, choices=Scheme.choices, unique=True)
    bic = models.CharField(max_length=11)
    name = models.CharField(max_length=255)
    sort_code = models.CharField(max_length=9)
    api_key = models.CharField(max_length=255)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.scheme} registration ({self.bic})"


class UKPSPayment(models.Model):
    """Record of one outbound interbank payment routed through UKPS."""

    STATUS_CHOICES = [
        ("SETTLED", "Settled"),
        ("QUEUED", "Queued"),
        ("RECEIVED", "Received"),   # BACS: accepted into a cycle, not yet settled
        ("REJECTED", "Rejected"),
        ("FAILED", "Failed"),
    ]

    transfer = models.ForeignKey(
        "transfers.Transfer",
        on_delete=models.CASCADE,
        related_name="ukps_payments",
        null=True,
        blank=True,
    )
    scheme = models.CharField(max_length=8, choices=Scheme.choices)
    msg_id = models.CharField(max_length=35, db_index=True)

    sender_bic = models.CharField(max_length=11)
    receiver_bic = models.CharField(max_length=11)
    receiver_sort_code = models.CharField(max_length=9, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES)
    reason_code = models.CharField(max_length=64, blank=True)
    external_id = models.CharField(max_length=64, blank=True)  # BACS submission id
    raw_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.scheme} {self.msg_id} -> {self.receiver_bic} [{self.status}]"
