from rest_framework import serializers
from .models import OCRDocument

class OCRDocumentListSerializer(serializers.ModelSerializer):
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

class OCRDocumentDetailSerializer(serializers.ModelSerializer):
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