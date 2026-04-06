from django.db import models
from django.conf import settings


class Lead(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Deals(models.Model):

   
    STAGE_CHOICES = [
        (1, "Potential Customer"),
        (2, "Awaiting Additional Documents"),
        (3, "Quotation"),
        (4, "Follow up"),
        (5, "High Value Leads"),
        (6, "Hot/Responded"),
        (7, "Documentation Request"),
        (8, "Insurer Submission"),
        (9, "Pending with Insurer"),
        (10, "Payment Collection"),
        (11, "Payment Pending"),
        (12, "Payment Done"),
        (13, "Policy Issuance"),
        (14, "Billing"),
        (15, "Lost Cases & Future Prospects"),
    ]

    POLICY_TYPE_CHOICES = [
        ('AUTO', 'Auto'),
        ('HOME', 'Home'),
        ('HEALTH', 'Health'),
        ('LIFE', 'Life'),
        ('BUSINESS', 'Business'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('UNDERWRITING', 'Underwriting'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ACTIVE', 'Active'),
        ('CANCELLED', 'Cancelled'),
    ]


    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='policies'
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_policies'
    )

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agent_policies'
    )

  
    stage_id = models.IntegerField(
        choices=STAGE_CHOICES,
        default=1
    )

    policy_type = models.CharField(
        max_length=20,
        choices=POLICY_TYPE_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    premium_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    coverage_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    effective_date = models.DateField()
    expiry_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Policy #{self.id} - {self.policy_type}"