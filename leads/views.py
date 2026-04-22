from rest_framework.decorators import api_view
from .models import Lead, LeadActivity
from .serializers import (LeadListSerializer,LeadStatusUpdateSerializer,CreateLeadSerializer)
from rest_framework import status,viewsets
from django.shortcuts import render
from .serializers import LeadDetailsSerializer, LeadActivitySerializer,LeadstageUpdateSerializer
from rest_framework.exceptions import NotFound

from api.responses import success_response


@api_view(['GET'])
def lead_list(request):
    leads = Lead.objects.all().order_by('-created_at')
    serializer = LeadListSerializer(leads, many=True)

    return success_response(
        message="Leads fetched successfully",
        data=serializer.data,
        meta={"total": leads.count()},
        status_code=status.HTTP_200_OK,
    )

@api_view(['POST'])
def create_lead(request):
    serializer = CreateLeadSerializer(data=request.data)

    serializer.is_valid(raise_exception=True)
    lead = serializer.save()
    return success_response(
        message="Lead created successfully",
        data={"id": lead.id},
        status_code=status.HTTP_201_CREATED,
    )


@api_view(['PATCH'])
def update_lead_status(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise NotFound("Lead not found")

    serializer = LeadStatusUpdateSerializer(
        lead,
        data=request.data,
        partial=True  
    )

    serializer.is_valid(raise_exception=True)
    serializer.save()
    return success_response(
        message="Lead status updated successfully",
        data={"id": lead.id, "status": lead.status},
        status_code=status.HTTP_200_OK,
    )




@api_view(['GET'])
def lead_details(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise NotFound("Lead not found")

    serializer = LeadDetailsSerializer(lead)
    return success_response(
        message="Lead fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(['POST'])
def create_activity(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise NotFound("Lead not found")

    serializer = LeadActivitySerializer(data=request.data)

    serializer.is_valid(raise_exception=True)
    serializer.save(lead=lead)
    return success_response(
        message="Activity created successfully",
        data=None,
        status_code=status.HTTP_201_CREATED,
    )

@api_view(['GET'])
def lead_activities(request, lead_id):
    activities = LeadActivity.objects.filter(lead_id=lead_id).order_by('-timestamp')

    serializer = LeadActivitySerializer(activities, many=True)

    return success_response(
        message="Lead activities fetched successfully",
        data=serializer.data,
        meta={"total": activities.count()},
        status_code=status.HTTP_200_OK,
    )


from rest_framework.views import APIView
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Lead


class ToggleFavoriteView(APIView):

    def post(self, request, id):
        lead = get_object_or_404(Lead, id=id)

        # Toggle logic
        lead.is_favorite = not lead.is_favorite
        lead.save()

        return success_response(
            message="Favorite status updated successfully",
            data={"id": lead.id, "is_favorite": lead.is_favorite},
            status_code=status.HTTP_200_OK,
        )
    


@api_view(['PATCH'])
def update_lead_stage(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise NotFound("Lead not found")

    serializer = LeadstageUpdateSerializer(
        lead,
        data=request.data,
        partial=True  
    )

    serializer.is_valid(raise_exception=True)
    serializer.save()
    return success_response(
        message="Lead stage updated successfully",
        data={"id": lead.id, "stage": lead.stage},
        status_code=status.HTTP_200_OK,
    )