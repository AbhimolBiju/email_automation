from django.db import models
from leads.models import Lead


class InsuranceInfo(models.Model):
    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE,
        related_name="insurance_info"
    )

    type_of_health_insurance = models.CharField(max_length=100, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    currently_insured = models.BooleanField(null=True, blank=True)
    salary_band = models.CharField(max_length=50, null=True, blank=True)
    emirates_id = models.CharField(max_length=50, null=True, blank=True)
    preferred_hospitals_clinics = models.TextField(null=True, blank=True)
    specific_benefits = models.TextField(null=True, blank=True)
    basic_plan_type = models.CharField(max_length=50, null=True, blank=True)
    co_payment = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Insurance Info for Lead {self.lead.id}"


class InsuranceProvider(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    base_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    username = models.CharField(max_length=255, blank=True)
    password = models.CharField(max_length=255, blank=True)
    extra_config = models.JSONField(default=dict, blank=True)
    timeout = models.PositiveIntegerField(default=30)
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    provider_class = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]
        indexes = [
            models.Index(fields=["is_active", "priority"], name="insprov_act_prio_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def masked_api_key(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 4:
            return "*" * len(self.api_key)
        return f"{self.api_key[:2]}{'*' * (len(self.api_key) - 4)}{self.api_key[-2:]}"

    @property
    def masked_password(self) -> str:
        if not self.password:
            return ""
        return "*" * min(len(self.password), 12)


class QuoteRequestLog(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.CASCADE,
        related_name="quote_request_logs",
    )
    provider = models.ForeignKey(
        InsuranceProvider,
        on_delete=models.CASCADE,
        related_name="quote_request_logs",
    )
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["deal", "provider", "-created_at"], name="qreq_deal_prov_ctd_idx"),
        ]

    def __str__(self):
        return f"QuoteRequestLog(deal={self.deal_id}, provider={self.provider.code}, status={self.status})"


class QuoteResult(models.Model):
    deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.CASCADE,
        related_name="quote_results",
    )
    provider = models.ForeignKey(
        InsuranceProvider,
        on_delete=models.CASCADE,
        related_name="quote_results",
    )
    request_log = models.ForeignKey(
        QuoteRequestLog,
        on_delete=models.SET_NULL,
        related_name="quote_results",
        null=True,
        blank=True,
    )
    premium = models.DecimalField(max_digits=12, decimal_places=2)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="AED")
    plan_name = models.CharField(max_length=255)
    response_time_ms = models.PositiveIntegerField(default=0)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["total", "provider__priority", "-created_at"]
        indexes = [
            models.Index(fields=["deal", "provider", "-created_at"], name="qres_deal_prov_ctd_idx"),
        ]

    def __str__(self):
        return f"QuoteResult(deal={self.deal_id}, provider={self.provider.code}, total={self.total})"
