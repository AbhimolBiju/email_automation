import mimetypes
import os
from pathlib import Path
from uuid import uuid4

from django.db import models


def unique_document_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"documents/{uuid4().hex}{extension}"


class Document(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_VERIFIED = "VERIFIED"
    STATUS_REJECTED = "REJECTED"
    STATUS_LOW_CONFIDENCE = "LOW_CONFIDENCE"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_LOW_CONFIDENCE, "Low Confidence"),
    ]

    OCR_PENDING = "PENDING"
    OCR_SUCCESS = "SUCCESS"
    OCR_FAILED = "FAILED"
    OCR_STATUS_CHOICES = [
        (OCR_PENDING, "Pending"),
        (OCR_SUCCESS, "Success"),
        (OCR_FAILED, "Failed"),
    ]

    name = models.CharField(max_length=255, blank=True)
    file = models.FileField(
        upload_to=unique_document_upload_path,
        blank=True,
        null=True,
    )
    path = models.CharField(max_length=500, blank=True)
    file_type = models.CharField(max_length=100, blank=True, null=True)
    document_type = models.CharField(max_length=100, default="other")
    source = models.CharField(max_length=100, blank=True, null=True)
    score = models.FloatField(blank=True, null=True)
    ocr_response = models.JSONField(blank=True, null=True)
    ocr_status = models.CharField(
        max_length=20,
        choices=OCR_STATUS_CHOICES,
        default=OCR_PENDING,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    motor_deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="shared_documents",
    )
    general_product = models.ForeignKey(
        "leads.GeneralDetails",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documents",
    )
    medical_product = models.ForeignKey(
        "leads.MedicalDetails",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def save(self, *args, **kwargs):
        if self.file:
            file_name = self.file.name or ""
            if not self.name:
                self.name = os.path.basename(file_name)
            self.path = file_name
            if not self.file_type:
                guessed_type, _encoding = mimetypes.guess_type(file_name)
                self.file_type = guessed_type or "application/octet-stream"
        super().save(*args, **kwargs)

    @property
    def lead(self):
        if self.motor_deal_id and self.motor_deal:
            return self.motor_deal.lead
        if self.general_product_id:
            return getattr(self.general_product, "lead", None)
        if self.medical_product_id:
            return getattr(self.medical_product, "lead", None)
        return None

    @property
    def product_label(self):
        if self.motor_deal_id:
            return "Motor"
        if self.general_product_id:
            return "General"
        if self.medical_product_id:
            return "Medical"
        return "Unknown"



class OCRDocument(models.Model):

    STATUS_CHOICES = [
        ('VERIFIED', 'Verified'),
        ('PENDING', 'Pending'),
        ('REJECTED', 'Rejected'),
        ('LOW_CONFIDENCE', 'Low Confidence'),
    ]

    document_id = models.CharField(max_length=20, unique=True)
    lead_id = models.CharField(max_length=20)
    first_name = models.CharField(max_length=100)
    document_type = models.CharField(max_length=100)
    product = models.CharField(max_length=100)
    confidence_score = models.IntegerField(default=0)
    upload_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    def __str__(self):
        return self.document_id
