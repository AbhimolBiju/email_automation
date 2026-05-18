"""DRF serializers for invoice upload and result responses."""

from __future__ import annotations

import os

from django.conf import settings
from rest_framework import serializers

from apps.invoice.field_mappings import list_supported_schemas

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class InvoiceUploadSerializer(serializers.Serializer):
    """Validates multipart invoice extraction requests."""

    file = serializers.FileField()
    document_type = serializers.CharField(max_length=64)
    target_schema = serializers.CharField(max_length=64)

    def validate_target_schema(self, value: str) -> str:
        """Ensure the target schema is registered."""
        normalized = value.strip()
        if normalized not in list_supported_schemas():
            raise serializers.ValidationError(
                f"Unsupported target_schema. Supported: {', '.join(list_supported_schemas())}"
            )
        return normalized

    def validate_file(self, uploaded_file) -> object:
        """Validate file extension, content type, and size."""
        extension = os.path.splitext(uploaded_file.name or "")[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                "Only PDF, JPG, and PNG files are supported."
            )

        content_type = (uploaded_file.content_type or "").lower()
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Invalid file type. Upload a PDF, JPG, or PNG."
            )

        max_bytes = int(
            getattr(settings, "INVOICE_MAX_UPLOAD_BYTES", MAX_UPLOAD_BYTES)
        )
        if uploaded_file.size > max_bytes:
            raise serializers.ValidationError(
                f"File size must not exceed {max_bytes // (1024 * 1024)}MB."
            )

        return uploaded_file


class InvoiceResultSerializer(serializers.Serializer):
    """Serializes successful invoice extraction responses."""

    job_id = serializers.IntegerField()
    extracted_fields = serializers.DictField(child=serializers.JSONField())
    needs_review_fields = serializers.DictField(child=serializers.JSONField())
    confidence_scores = serializers.DictField(child=serializers.FloatField())


class InvoiceJobDetailSerializer(serializers.Serializer):
    """Serializes a persisted invoice extraction job for re-autofill."""

    job_id = serializers.IntegerField()
    status = serializers.CharField()
    document_type = serializers.CharField()
    target_schema = serializers.CharField()
    extracted_fields = serializers.DictField(child=serializers.JSONField())
    needs_review_fields = serializers.DictField(child=serializers.JSONField())
    confidence_scores = serializers.DictField(child=serializers.FloatField())
    error_code = serializers.CharField(required=False, allow_blank=True)
    user_message = serializers.CharField(required=False, allow_blank=True)


class InvoiceErrorSerializer(serializers.Serializer):
    """Serializes invoice extraction failure responses."""

    error_code = serializers.CharField()
    user_message = serializers.CharField()
