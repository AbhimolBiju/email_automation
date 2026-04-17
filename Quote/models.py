from django.db import models

# Create your models here.

class Insurer(models.Model):
    insurer_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    premium = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.name

class QuoteRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    lead_id = models.CharField(max_length=100, unique=True)
    customer_name = models.CharField(max_length=255)
    product_type = models.CharField(max_length=255)

    insurers = models.ManyToManyField(Insurer, related_name='quote_requests')

    best_premium_currency = models.CharField(max_length=10)
    best_premium_amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer_name} - {self.product_type}"
    

from django.db import models

class Quote(models.Model):
    quote_request = models.ForeignKey(
        "QuoteRequest",
        on_delete=models.CASCADE,
        related_name="quotes"
    )

    response_json = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quote {self.id}"
