from django.db import models
from Quote.models import Insurer,QuoteRequest
# Create your models here.
# models.py

class Policy(models.Model):
    policy_id = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=255)
    product_type = models.CharField(max_length=100)
    issue_date = models.DateField()

    def __str__(self):
        return self.policy_id


class PolicyInsurer(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('not_initiated', 'Not Initiated'),
    ]

    POLICY_STATUS_CHOICES = [
        ('active', 'Active'),
        ('issued', 'Issued'),
        ('payment_pending', 'Payment Pending'),
        ('email_flow', 'Email Flow'),
        ('pending', 'Pending'),
    ]

    METHOD_CHOICES = [
        ('api', 'API'),
        ('email', 'Email'),
    ]

    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='insurers')
    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE)

    premium = models.DecimalField(max_digits=10, decimal_places=2)
    quote_request = models.ForeignKey(
        QuoteRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES)
    status = models.CharField(max_length=30, choices=POLICY_STATUS_CHOICES)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)

    def __str__(self):
        return f"{self.policy.policy_id} - {self.insurer}"