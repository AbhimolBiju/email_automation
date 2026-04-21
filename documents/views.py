from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import OCRDocument
from .utils import get_date_filter
from django.core.paginator import Paginator
from rest_framework import status
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

    return Response({
        "total_documents": total,
        "verified_count": verified,
        "pending_review": pending,
        "rejected_count": rejected,
        "low_confidence_count": low_confidence
    })

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

    return Response({
        "results_found": paginator.count,
        "documents": serializer.data,
    },status=status.HTTP_200_OK)


@api_view(["GET"])
def document_detail(request, id):
    try:
        document = OCRDocument.objects.get(id=id)
    except OCRDocument.DoesNotExist:
        return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = OCRDocumentDetailSerializer(document)
    return Response(serializer.data)

@api_view(["PATCH"])
def verify_document(request, id):
    try:
        document = OCRDocument.objects.get(id=id)
    except OCRDocument.DoesNotExist:
        return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

    # update status
    document.status = "VERIFIED"
    document.save()

    return Response({
        "message": "Document verified successfully",
        "document_id": document.document_id,
        "status": document.status
    },status=status.HTTP_200_OK)

@api_view(["PATCH"])
def reject_document(request, id):
    try:
        document = OCRDocument.objects.get(id=id)
    except OCRDocument.DoesNotExist:
        return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

    # update status
    document.status = "REJECTED"
    document.save()

    return Response({
        "message": "Document Rejected",
        "document_id": document.document_id,
        "status": document.status
    }, status=status.HTTP_200_OK)