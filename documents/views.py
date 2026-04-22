from django.shortcuts import render
from rest_framework.decorators import api_view
from .models import OCRDocument
from .utils import get_date_filter
from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from api.responses import success_response
# Create your views here.

@api_view(['GET'])
def ocr_stats(request):
    period = request.GET.get("period")

    queryset = OCRDocument.objects.all()
    date_filter = get_date_filter(period)
    if date_filter:
        queryset = queryset.filter(upload_date__gte=date_filter)

    total = queryset.count()
    verified = queryset.filter(status='VERIFIED').count()
    pending = queryset.filter(status='PENDING').count()
    rejected = queryset.filter(status='REJECTED').count()
    low_confidence = queryset.filter(status='LOW_CONFIDENCE').count()

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

from .serializers import OCRDocumentListSerializer,OCRDocumentDetailSerializer

@api_view(["GET"])
def document_list(request):
    queryset = OCRDocument.objects.all().order_by("-upload_date")

    status = request.GET.get("status", "all").lower()

    status_map = {
        "pending": "PENDING",
        "verified": "VERIFIED",
        "rejected": "REJECTED",
        "low_confidence": "LOW_CONFIDENCE",
    }

    if status in status_map:
        queryset = queryset.filter(status=status_map[status])

    search = request.GET.get("search")
    if search:
        queryset = queryset.filter(
            first_name__icontains=search
        ) | queryset.filter(
            document_id__icontains=search
        ) | queryset.filter(
            lead_id__icontains=search
        ) | queryset.filter(
            document_type__icontains=search
        ) 

    page_number = request.GET.get("page", 1)
    paginator = Paginator(queryset, 10)
    page = paginator.get_page(page_number)

    serializer = OCRDocumentListSerializer(page.object_list, many=True)

    return success_response(
        message="Documents fetched successfully",
        data=serializer.data,
        meta={
            "page": int(page.number),
            "limit": int(paginator.per_page),
            "total": int(paginator.count),
            "pages": int(paginator.num_pages),
        },
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
def document_detail(request, id):
    try:
        document = OCRDocument.objects.get(id=id)
    except OCRDocument.DoesNotExist:
        raise NotFound("Document not found")

    serializer = OCRDocumentDetailSerializer(document)
    return success_response(
        message="Document fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )

@api_view(["PATCH"])
def verify_document(request, id):
    try:
        document = OCRDocument.objects.get(id=id)
    except OCRDocument.DoesNotExist:
        raise NotFound("Document not found")

    # update status
    document.status = "VERIFIED"
    document.save()

    return success_response(
        message="Document verified successfully",
        data={"document_id": document.document_id, "status": document.status},
        status_code=status.HTTP_200_OK,
    )

@api_view(["PATCH"])
def reject_document(request, id):
    try:
        document = OCRDocument.objects.get(id=id)
    except OCRDocument.DoesNotExist:
        raise NotFound("Document not found")

    # update status
    document.status = "REJECTED"
    document.save()

    return success_response(
        message="Document rejected successfully",
        data={"document_id": document.document_id, "status": document.status},
        status_code=status.HTTP_200_OK,
    )