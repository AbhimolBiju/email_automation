"""Database models for OCR extraction jobs."""

from __future__ import annotations

from django.db import models


class OCRJob(models.Model):
    """Tracks a single document OCR extraction request and its outcome."""

    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    document_type = models.CharField(max_length=64)
    target_schema = models.CharField(max_length=64)
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_file = models.FileField(upload_to="ocr/uploads/%Y/%m/%d/")
    model_used = models.CharField(max_length=128, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    extracted_fields = models.JSONField(null=True, blank=True)
    needs_review_fields = models.JSONField(null=True, blank=True)
    confidence_scores = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        """Return a readable identifier for admin and logs."""
        return f"OCRJob({self.pk}, {self.status}, {self.document_type})"

    def mark_processing(self) -> None:
        """Transition the job to PROCESSING."""
        self.status = self.STATUS_PROCESSING
        self.save(update_fields=["status", "updated_at"])

    def mark_completed(
        self,
        *,
        model_used: str,
        page_count: int,
        raw_response: dict,
        extracted_fields: dict,
        needs_review_fields: dict,
        confidence_scores: dict,
    ) -> None:
        """Persist successful extraction results."""
        self.status = self.STATUS_COMPLETED
        self.model_used = model_used
        self.page_count = page_count
        self.raw_response = raw_response
        self.extracted_fields = extracted_fields
        self.needs_review_fields = needs_review_fields
        self.confidence_scores = confidence_scores
        self.error_code = ""
        self.error_message = ""
        self.save(
            update_fields=[
                "status",
                "model_used",
                "page_count",
                "raw_response",
                "extracted_fields",
                "needs_review_fields",
                "confidence_scores",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )

    def mark_failed(self, *, error_code: str, error_message: str) -> None:
        """Persist failure details for auditing and support."""
        self.status = self.STATUS_FAILED
        self.error_code = error_code
        self.error_message = error_message
        self.save(
            update_fields=["status", "error_code", "error_message", "updated_at"]
        )
