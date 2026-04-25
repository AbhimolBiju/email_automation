from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Q

from api.responses import success_response
from .models import Document
from .serializers import (
    DocumentUploadSerializer,
    OCRDocumentDetailSerializer,
    OCRDocumentListSerializer,
)
from .utils import get_date_filter


@api_view(["GET"])
@permission_classes([AllowAny])
def ocr_stats(request):
    period = request.GET.get("period")

    queryset = Document.objects.all()
    date_filter = get_date_filter(period)
    if date_filter:
        queryset = queryset.filter(uploaded_at__gte=date_filter)

    total = queryset.count()
    verified = queryset.filter(status=Document.STATUS_VERIFIED).count()
    pending = queryset.filter(status=Document.STATUS_PENDING).count()
    rejected = queryset.filter(status=Document.STATUS_REJECTED).count()
    low_confidence = queryset.filter(status=Document.STATUS_LOW_CONFIDENCE).count()

    return success_response(
        message="OCR stats fetched successfully",
        data={
            "total_documents": total,
            "verified_count": verified,
            "pending_review": pending,
            "rejected_count": rejected,
            "low_confidence_count": low_confidence,
        },
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def document_list(request):
    queryset = Document.objects.select_related(
        "motor_deal__lead",
        "general_product__lead",
        "medical_product__lead",
    ).order_by("-uploaded_at")

    status_param = request.GET.get("status", "all").lower()
    status_map = {
        "pending": Document.STATUS_PENDING,
        "verified": Document.STATUS_VERIFIED,
        "rejected": Document.STATUS_REJECTED,
        "low_confidence": Document.STATUS_LOW_CONFIDENCE,
    }
    if status_param in status_map:
        queryset = queryset.filter(status=status_map[status_param])

    search = request.GET.get("search")
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(document_type__icontains=search)
            | Q(path__icontains=search)
        )

    serializer = OCRDocumentListSerializer(queryset, many=True)

    return success_response(
        message="Documents fetched successfully",
        data=serializer.data,
        meta={
            "page": 1,
            "limit": len(serializer.data),
            "total": queryset.count(),
            "pages": 1,
        },
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def document_detail(request, id):
    try:
        document = Document.objects.select_related(
            "motor_deal__lead",
            "general_product__lead",
            "medical_product__lead",
        ).get(id=id)
    except Document.DoesNotExist:
        raise NotFound("Document not found")

    serializer = OCRDocumentDetailSerializer(document)
    return success_response(
        message="Document fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(["PATCH"])
@permission_classes([AllowAny])
def verify_document(request, id):
    try:
        document = Document.objects.get(id=id)
    except Document.DoesNotExist:
        raise NotFound("Document not found")

    document.status = Document.STATUS_VERIFIED
    document.save(update_fields=["status"])

    return success_response(
        message="Document verified successfully",
        data={"document_id": f"DOC-{document.id:04d}", "status": "Verified"},
        status_code=status.HTTP_200_OK,
    )


@api_view(["PATCH"])
@permission_classes([AllowAny])
def reject_document(request, id):
    try:
        document = Document.objects.get(id=id)
    except Document.DoesNotExist:
        raise NotFound("Document not found")

    document.status = Document.STATUS_REJECTED
    document.save(update_fields=["status"])

    return success_response(
        message="Document rejected successfully",
        data={"document_id": f"DOC-{document.id:04d}", "status": "Rejected"},
        status_code=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def upload_ocr_document(request):
    serializer = DocumentUploadSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response(
            {
                "message": "Document uploaded successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
