from django.shortcuts import render

# Create your views here.

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Lead, InsuranceInfo
from .serializers import InsuranceInfoSerializer

@api_view(['GET'])
def get_insurance_info(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response(
            {"error": "Lead not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        insurance_info = lead.insurance_info
    except InsuranceInfo.DoesNotExist:
        return Response(
            {"lead_id": str(lead.id), "data": {}},
            status=status.HTTP_200_OK
        )

    serializer = InsuranceInfoSerializer(insurance_info)
    return Response(
        {
            "lead_id": str(lead.id),
            "data": serializer.data
        },
        status=status.HTTP_200_OK
    )