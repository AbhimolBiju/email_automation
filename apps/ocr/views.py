"""API views for the OCR microservice."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ocr.exceptions import OCRServiceError
from apps.ocr.models import OCRJob
from apps.ocr.serializers import (
    OCRErrorSerializer,
    OCRResultSerializer,
    OCRUploadSerializer,
)
from apps.ocr.services.azure_ocr_service import AzureOCRService
from apps.ocr.services.confidence_filter import filter_by_confidence
from apps.ocr.serialization import to_json_safe_dict
from apps.ocr.services.field_mapper import map_ocr_fields

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def extract_document(request) -> Response:
    """Extract CRM fields from an uploaded document via Azure OCR."""
    serializer = OCRUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    uploaded_file = validated["file"]
    document_type = validated["document_type"]
    target_schema = validated["target_schema"]

    job = OCRJob.objects.create(
        status=OCRJob.STATUS_PENDING,
        document_type=document_type,
        target_schema=target_schema,
        original_filename=uploaded_file.name,
        uploaded_file=uploaded_file,
    )

    try:
        job.mark_processing()
        uploaded_file.seek(0)
        ocr_result = AzureOCRService().analyze_document(
            uploaded_file,
            document_type=document_type,
        )
        mapped = map_ocr_fields(ocr_result, target_schema)
        filtered = filter_by_confidence(mapped)

        extracted_fields = to_json_safe_dict(filtered.high_confidence)
        needs_review_fields = to_json_safe_dict(filtered.needs_review)

        job.mark_completed(
            model_used=ocr_result.model_used,
            page_count=ocr_result.page_count,
            raw_response={
                "raw_fields": ocr_result.raw_fields,
                "provider": ocr_result.provider_payload,
            },
            extracted_fields=extracted_fields,
            needs_review_fields=needs_review_fields,
            confidence_scores=filtered.confidence_scores,
        )

        response_data = {
            "job_id": job.id,
            "extracted_fields": extracted_fields,
            "needs_review_fields": needs_review_fields,
            "confidence_scores": filtered.confidence_scores,
        }
        return Response(
            OCRResultSerializer(response_data).data,
            status=status.HTTP_200_OK,
        )
    except OCRServiceError as exc:
        logger.warning("OCR job %s failed: %s", job.id, exc)
        job.mark_failed(error_code=exc.error_code, error_message=str(exc))
        return Response(
            OCRErrorSerializer(exc.as_response_dict()).data,
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        logger.exception("Unexpected OCR failure for job %s", job.id)
        job.mark_failed(error_code="ocr_internal_error", error_message=str(exc))
        return Response(
            OCRErrorSerializer(
                {
                    "error_code": "ocr_internal_error",
                    "user_message": "An unexpected error occurred while processing the document.",
                }
            ).data,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
