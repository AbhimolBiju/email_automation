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


from rest_framework import serializers
from .models import Document
from .validators import validate_file_size

class OCRDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(validators=[validate_file_size])

    class Meta:
        model = Document
        fields = '__all__'