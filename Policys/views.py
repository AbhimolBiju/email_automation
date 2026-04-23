from django.shortcuts import render

# Create your views here.

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from .models import Policy, PolicyInsurer
from .serializers import PolicyListSerializer


class PolicyQueueView(APIView):

    def get(self, request):
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
