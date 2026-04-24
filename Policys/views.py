from django.shortcuts import render

# Create your views here.

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from .models import Policy, PolicyInsurer
from .serializers import PolicyListSerializer
from api.responses import success_response
from .utils import get_date_filter
from rest_framework import status
@api_view(['GET'])
def policy_stats(request):
    period = request.GET.get("period")

    queryset = PolicyInsurer.objects.all()

    # Filter by Policy issue_date
    date_filter = get_date_filter(period)
    if date_filter:
        queryset = queryset.filter(policy__issue_date__gte=date_filter)

    total = queryset.count()

    active = queryset.filter(status='active').count()
    payment_pending = queryset.filter(status='payment_pending').count()
    link_issued = queryset.filter(status='link_issued').count()
    pending_underwriter = queryset.filter(status='pending').count()

    return success_response(
        message="Policy stats fetched successfully",
        data={
            "total_policy": total,
            "active_count": active,
            "payment_pending": payment_pending,
            "Payment_link_issued": link_issued,
            "pending underwriter": pending_underwriter,
        },
        status_code=status.HTTP_200_OK,
    )
@api_view(['GET'])
def PolicyQueueView(request):
    search = request.GET.get('search')
    payment_status = request.GET.get('payment_status')
    status = request.GET.get('status')
    method = request.GET.get('method')

    policies = Policy.objects.prefetch_related('insurers', 'insurers__insurer')

    if search:
        policies = policies.filter(
            Q(policy_id__icontains=search) |
            Q(customer_name__icontains=search)
        )

    if payment_status:
        policies = policies.filter(insurers__payment_status=payment_status)

    if status:
        policies = policies.filter(insurers__status=status)

    if method:
        policies = policies.filter(insurers__method=method)

    policies = policies.distinct().order_by('-issue_date')

    serializer = PolicyListSerializer(policies, many=True)

    return Response({
        "success": True,
        "message": "Policy queue fetched successfully",
        "data": serializer.data
    })
    

from rest_framework.decorators import api_view
from rest_framework import status as drf_status

@api_view(['PATCH'])
def update_policy_status(request, pk):
    try:
        obj = PolicyInsurer.objects.get(id=pk)
    except PolicyInsurer.DoesNotExist:
        return Response({"message": "Not found"}, status=404)

    obj.payment_status = request.data.get('payment_status', obj.payment_status)
    obj.status = request.data.get('status', obj.status)

    obj.save()

    return Response({
        "success": True,
        "message": "Policy updated successfully"
    })

# views.py

from Quote.models import QuoteRequest
from Quote.serializers import QuoteRequestSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def view_quote(request, pk):
    try:
        quote = QuoteRequest.objects.get(id=pk)
    except QuoteRequest.DoesNotExist:
        return Response({"message": "Quote not found"}, status=404)

    serializer = QuoteRequestSerializer(quote)

    return Response({
        "success": True,
        "data": serializer.data
    })


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AdditionalDocument
from .serializers import AdditionalDocumentSerializer

class PolicyAdditionalDocumentView(APIView):

    def get(self, request, policy_id):
        docs = AdditionalDocument.objects.filter(policy_id=policy_id)
        serializer = AdditionalDocumentSerializer(docs, many=True)
        return Response(serializer.data)

    def post(self, request, policy_id):
        data = request.data.copy()
        data['policy'] = policy_id

        serializer = AdditionalDocumentSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Document uploaded successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)