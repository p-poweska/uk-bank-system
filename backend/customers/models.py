from django.conf import settings
from django.db import models


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    date_of_birth = models.DateField()
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=50)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=20)
    street = models.CharField(max_length=255)


    parent_customer = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children'
    )

    klik_phone_alias = models.CharField(
    max_length=16,
    blank=True,
    null=True
    )

    kyc_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)