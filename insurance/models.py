from django.db import models
from leads.models import Lead
from django.conf import settings


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
    batch = models.ForeignKey(
        "QuoteBatch",
        on_delete=models.SET_NULL,
        related_name="request_logs",
        null=True,
        blank=True,
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
    STATUS_PROCESSING = "processing"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.CASCADE,
        related_name="quote_results",
    )
    batch = models.ForeignKey(
        "QuoteBatch",
        on_delete=models.CASCADE,
        related_name="results",
        null=True,
        blank=True,
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
    provider_name = models.CharField(max_length=255, blank=True)
    premium = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="AED")
    plan_name = models.CharField(max_length=255, blank=True)
    response_time_ms = models.PositiveIntegerField(default=0)
    ranking = models.PositiveIntegerField(null=True, blank=True)
    coverage_score = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    error_message = models.TextField(blank=True)
    normalized_response = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    is_recommended = models.BooleanField(default=False)
    is_cheapest = models.BooleanField(default=False)
    is_best_value = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["total", "provider__priority", "-created_at"]
        indexes = [
            models.Index(fields=["deal", "provider", "-created_at"], name="qres_deal_prov_ctd_idx"),
        ]

    def __str__(self):
        return f"QuoteResult(deal={self.deal_id}, provider={self.provider.code}, total={self.total})"


class QuoteBatch(models.Model):
    STATUS_PROCESSING = "processing"
    STATUS_SUCCESS = "success"
    STATUS_PARTIAL_SUCCESS = "partial_success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_PARTIAL_SUCCESS, "Partial Success"),
        (STATUS_FAILED, "Failed"),
    ]

    reference_no = models.CharField(max_length=32, unique=True, blank=True)
    deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.CASCADE,
        related_name="quote_batches",
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        related_name="quote_batches",
        null=True,
        blank=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="triggered_quote_batches",
        null=True,
        blank=True,
    )
    best_provider = models.ForeignKey(
        InsuranceProvider,
        on_delete=models.SET_NULL,
        related_name="best_quote_batches",
        null=True,
        blank=True,
    )
    best_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    cache_expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["deal", "-requested_at"], name="qbatch_deal_req_idx"),
            models.Index(fields=["status", "cache_expires_at"], name="qbatch_status_cache_idx"),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference_no:
            self.reference_no = f"QT-{self.pk:04d}"
            super().save(update_fields=["reference_no"])

    def __str__(self):
        return self.reference_no or f"QuoteBatch({self.pk})"


class PolicyIssuance(models.Model):
    """Queued policy checkout after user confirms add-ons (linked to deal / quote batch)."""

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_EXPIRED = "expired"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_EXPIRED, "Expired"),
    ]

    ISSUANCE_PENDING = "pending"
    ISSUANCE_PAYMENT_LINK_REQUESTED = "payment_link_requested"
    ISSUANCE_PAYMENT_LINK_RECEIVED = "payment_link_received"
    ISSUANCE_ISSUED = "issued"
    ISSUANCE_ACTIVE = "active"
    ISSUANCE_STATUS_CHOICES = [
        (ISSUANCE_PENDING, "Pending"),
        (ISSUANCE_PAYMENT_LINK_REQUESTED, "Payment link requested"),
        (ISSUANCE_PAYMENT_LINK_RECEIVED, "Payment link received"),
        (ISSUANCE_ISSUED, "Issued"),
        (ISSUANCE_ACTIVE, "Active"),
    ]

    deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.CASCADE,
        related_name="policy_issuances",
    )
    quote_batch = models.ForeignKey(
        QuoteBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="policy_issuances",
    )
    quote_result = models.ForeignKey(
        QuoteResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="policy_issuances",
    )

    customer_name = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_email = models.CharField(max_length=254, blank=True)
    product_type = models.CharField(max_length=255, blank=True)

    provider_code = models.CharField(max_length=50, blank=True)
    provider_display_name = models.CharField(max_length=255, blank=True)
    plan_name = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=10, default="AED")
    base_premium = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    addon_line_items = models.JSONField(default=list, blank=True)

    dic_scheme_payload = models.JSONField(null=True, blank=True)
    choose_scheme_response = models.JSONField(null=True, blank=True)
    quotation_no = models.CharField(max_length=128, blank=True)
    payment_url = models.CharField(max_length=2048, blank=True)

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
    )
    issuance_status = models.CharField(
        max_length=40,
        choices=ISSUANCE_STATUS_CHOICES,
        default=ISSUANCE_PENDING,
    )

    checkout_submit_skipped = models.BooleanField(default=False)
    choose_scheme_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["deal", "-created_at"], name="pissue_deal_ctd_idx"),
            models.Index(fields=["-created_at"], name="pissue_ctd_idx"),
        ]

    def __str__(self) -> str:
        return f"PolicyIssuance({self.pk}, deal={self.deal_id})"
