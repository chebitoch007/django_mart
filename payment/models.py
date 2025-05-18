from django.db import models
from orders.models import Order

class PaymentBase(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)  # Format: 2547XXXXXXXX
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

class PaymentTransaction(PaymentBase):
    PROVIDER_CHOICES = [
        ('MPESA', 'M-Pesa'),
        ('AIRTEL', 'Airtel Money'),
        ('PESALINK', 'PesaLink'),
        ('FLUTTERWAVE', 'Flutterwave'),
    ]

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    checkout_request_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.provider} Payment - {self.transaction_id}"

    class Meta(PaymentBase.Meta):
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"