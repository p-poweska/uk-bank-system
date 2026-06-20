from django.db import models
from django.conf import settings
from accounts.models import Account 

class Transfer(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transfers_sent')
    
    recipient_name = models.CharField(max_length=255)
    recipient_account = models.CharField(max_length=34) 
    swift_bic = models.CharField(max_length=11, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    title = models.CharField(max_length=255)
    
    routing_method = models.CharField(max_length=10)
    # Extra accounting details for outgoing SWIFT transfers.
    # Domestic FPS/BACS/CHAPS transfers keep these fields empty.
    swift_uetr = models.CharField(max_length=36, null=True, blank=True, unique=True)
    swift_message_id = models.CharField(max_length=64, null=True, blank=True)

    sent_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sent_currency = models.CharField(max_length=3, null=True, blank=True)

    debited_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    debited_currency = models.CharField(max_length=3, null=True, blank=True)

    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    charge_bearer = models.CharField(max_length=4, null=True, blank=True) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transfer {self.id} to {self.recipient_account}"


class SavedRecipient(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_recipients')
    name = models.CharField(max_length=255)
    account = models.CharField(max_length=34)  # IBAN
    routing_method = models.CharField(max_length=10, default='FPS')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.account})"


class JuniorApproval(models.Model):
    STATUS_CHOICES = [
        ('PENDING',  'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    junior_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='junior_approvals'
    )
    parent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parent_approvals'
    )
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE)

    recipient_name    = models.CharField(max_length=255)
    recipient_account = models.CharField(max_length=34)
    swift_bic         = models.CharField(max_length=11, null=True, blank=True)
    amount            = models.DecimalField(max_digits=12, decimal_places=2)
    title             = models.CharField(max_length=255)
    routing_method    = models.CharField(max_length=10)

    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Approval #{self.id} — {self.junior_user} → £{self.amount} to {self.recipient_name}"