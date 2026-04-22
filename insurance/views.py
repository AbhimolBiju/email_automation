from django.shortcuts import render

# Create your views here.

from rest_framework.decorators import api_view
from rest_framework import status
from .models import Lead, InsuranceInfo
from .serializers import InsuranceInfoSerializer
from rest_framework.exceptions import NotFound
from api.responses import success_response

@api_view(['GET'])
def get_insurance_info(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise NotFound("Lead not found")

    try:
        insurance_info = lead.insurance_info
    except InsuranceInfo.DoesNotExist:
        return success_response(
            message="Insurance info fetched successfully",
            data={},
            meta={"lead_id": str(lead.id)},
            status_code=status.HTTP_200_OK,
        )

    serializer = InsuranceInfoSerializer(insurance_info)
    return success_response(
        message="Insurance info fetched successfully",
        data=serializer.data,
        meta={"lead_id": str(lead.id)},
        status_code=status.HTTP_200_OK,
    )