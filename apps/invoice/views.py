"""API views for the invoice extraction microservice."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.invoice.exceptions import InvoiceServiceError
from apps.invoice.models import InvoiceJob
from apps.invoice.serializers import (
    InvoiceErrorSerializer,
    InvoiceJobDetailSerializer,
    InvoiceResultSerializer,
    InvoiceUploadSerializer,
)
from apps.invoice.serialization import to_json_safe_dict
from apps.invoice.services.azure_invoice_service import AzureInvoiceService
from apps.invoice.services.confidence_filter import filter_by_confidence
from apps.invoice.services.billing_enrichment import enrich_extracted_fields
from apps.invoice.services.field_mapper import map_invoice_fields

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def extract_document(request) -> Response:
    """Extract CRM fields from an uploaded invoice via Azure Document Intelligence."""
    serializer = InvoiceUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    uploaded_file = validated["file"]
    document_type = validated["document_type"]
    target_schema = validated["target_schema"]

    job = InvoiceJob.objects.create(
        status=InvoiceJob.STATUS_PENDING,
        document_type=document_type,
        target_schema=target_schema,
        original_filename=uploaded_file.name,
        uploaded_file=uploaded_file,
    )

    try:
        job.mark_processing()
        uploaded_file.seek(0)
        invoice_result = AzureInvoiceService().analyze_document(
            uploaded_file,
            document_type=document_type,
        )
        mapped = map_invoice_fields(invoice_result, target_schema)
        filtered = filter_by_confidence(mapped)

        extracted_fields = enrich_extracted_fields(
            to_json_safe_dict(filtered.high_confidence),
            document_type=document_type,
            raw_content=str(invoice_result.raw_fields.get("content") or ""),
        )
        needs_review_fields = to_json_safe_dict(filtered.needs_review)

        job.mark_completed(
            model_used=invoice_result.model_used,
            page_count=invoice_result.page_count,
            raw_response={
                "raw_fields": invoice_result.raw_fields,
                "provider": invoice_result.provider_payload,
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
            InvoiceResultSerializer(response_data).data,
            status=status.HTTP_200_OK,
        )
    except InvoiceServiceError as exc:
        logger.warning("Invoice job %s failed: %s", job.id, exc)
        job.mark_failed(error_code=exc.error_code, error_message=str(exc))
        return Response(
            InvoiceErrorSerializer(exc.as_response_dict()).data,
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        logger.exception("Unexpected invoice extraction failure for job %s", job.id)
        job.mark_failed(error_code="invoice_internal_error", error_message=str(exc))
        return Response(
            InvoiceErrorSerializer(
                {
                    "error_code": "invoice_internal_error",
                    "user_message": "An unexpected error occurred while processing the invoice.",
                }
            ).data,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_job(request, job_id: int) -> Response:
    """Return stored OCR results for a completed invoice extraction job."""
    job = get_object_or_404(InvoiceJob, pk=job_id)

    if job.status == InvoiceJob.STATUS_FAILED:
        return Response(
            InvoiceErrorSerializer(
                {
                    "error_code": job.error_code or "invoice_job_failed",
                    "user_message": job.error_message
                    or "Invoice extraction failed for this document.",
                }
            ).data,
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if job.status != InvoiceJob.STATUS_COMPLETED:
        return Response(
            InvoiceErrorSerializer(
                {
                    "error_code": "invoice_job_not_ready",
                    "user_message": "Invoice extraction is still processing. Try again shortly.",
                }
            ).data,
            status=status.HTTP_409_CONFLICT,
        )

    response_data = {
        "job_id": job.id,
        "status": job.status,
        "document_type": job.document_type,
        "target_schema": job.target_schema,
        "extracted_fields": job.extracted_fields or {},
        "needs_review_fields": job.needs_review_fields or {},
        "confidence_scores": job.confidence_scores or {},
    }
    return Response(
        InvoiceJobDetailSerializer(response_data).data,
        status=status.HTTP_200_OK,
    )
