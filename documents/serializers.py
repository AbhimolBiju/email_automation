from rest_framework import serializers

from .models import Document, OCRDocument
from .validators import validate_file_size


def title_case_status(value):
    if value == Document.STATUS_LOW_CONFIDENCE:
        return "Low-confidence"
    return value.replace("_", " ").title()


class OCRDocumentListSerializer(serializers.ModelSerializer):
    document_id = serializers.SerializerMethodField()
    lead_id = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    confidence_score = serializers.SerializerMethodField()
    upload_date = serializers.DateTimeField(source="uploaded_at", read_only=True)

    class Meta:
        model = Document
        fields = [
            "document_id",
            "lead_id",
            "first_name",
            "document_type",
            "product",
            "upload_date",
            "confidence_score",
            "status",
        ]

    def get_document_id(self, obj):
        return f"DOC-{obj.id:04d}"

    def get_lead_id(self, obj):
        lead = obj.lead
        return f"LD-{lead.id:04d}" if lead else None

    def get_first_name(self, obj):
        lead = obj.lead
        if not lead or not lead.name:
            return obj.name
        return lead.name

    def get_product(self, obj):
        return obj.product_label

    def get_confidence_score(self, obj):
        return int(round(obj.score or 0))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["status"] = title_case_status(instance.status)
        return data


class OCRDocumentDetailSerializer(serializers.ModelSerializer):
    document_id = serializers.SerializerMethodField()
    lead_id = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    confidence_score = serializers.SerializerMethodField()
    upload_date = serializers.DateTimeField(source="uploaded_at", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "document_id",
            "lead_id",
            "first_name",
            "name",
            "file_url",
            "file_type",
            "document_type",
            "path",
            "product",
            "upload_date",
            "confidence_score",
            "status",
            "ocr_status",
            "ocr_response",
            "ocr_data",
            "source",
            "reuploaded_from",
        ]

    def get_document_id(self, obj):
        return f"DOC-{obj.id:04d}"

    def get_lead_id(self, obj):
        lead = obj.lead
        return f"LD-{lead.id:04d}" if lead else None

    def get_first_name(self, obj):
        lead = obj.lead
        if not lead or not lead.name:
            return obj.name
        return lead.name

    def get_product(self, obj):
        return obj.product_label

    def get_file_url(self, obj):
        if not obj.file:
            return None
        url = obj.file.url
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_confidence_score(self, obj):
        return int(round(obj.score or 0))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["status"] = title_case_status(instance.status)
        data["ocr_status"] = instance.ocr_status.replace("_", " ").title()
        return data


class DocumentUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField(validators=[validate_file_size])

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "file",
            "path",
            "file_type",
            "document_type",
            "source",
            "score",
            "ocr_response",
            "ocr_data",
            "ocr_status",
            "status",
            "motor_deal",
            "general_product",
            "medical_product",
            "uploaded_at",
        ]
        read_only_fields = ["path", "uploaded_at"]


class LegacyOCRDocumentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = OCRDocument
        fields = [
            "document_id",
            "lead_id",
            "first_name",
            "document_type",
            "product",
            "upload_date",
            "confidence_score",
            "status",
        ]
