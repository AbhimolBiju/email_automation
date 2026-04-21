from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Lead, LeadActivity
from .serializers import (LeadListSerializer,LeadStatusUpdateSerializer,CreateLeadSerializer)
from rest_framework import status,viewsets
from django.shortcuts import render
from .serializers import LeadDetailsSerializer, LeadActivitySerializer,LeadstageUpdateSerializer


@api_view(['GET'])
def lead_list(request):
    leads = Lead.objects.all().order_by('-created_at')
    serializer = LeadListSerializer(leads, many=True)

    return Response({
        "total_count": leads.count(),
        "results": serializer.data
    })

@api_view(['POST'])
def create_lead(request):
    serializer = CreateLeadSerializer(data=request.data)

    if serializer.is_valid():
        lead = serializer.save()

        return Response(
            {
                "message": "Lead created successfully",
                "lead_id": lead.id
            },
            status=status.HTTP_201_CREATED
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
def update_lead_status(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = LeadStatusUpdateSerializer(
        lead,
        data=request.data,
        partial=True  
    )

    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "Lead status updated successfully",
            "id": lead.id,
            "status": lead.status
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@api_view(['GET'])
def lead_details(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"error": "Lead not found"}, status=404)

    serializer = LeadDetailsSerializer(lead)
    return Response(serializer.data)


@api_view(['POST'])
def create_activity(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = LeadActivitySerializer(data=request.data)

    if serializer.is_valid():
        serializer.save(lead=lead) 
        return Response(
    {"message": "Activity created successfully"},
    status=status.HTTP_201_CREATED
)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def lead_activities(request, lead_id):
    activities = LeadActivity.objects.filter(lead_id=lead_id).order_by('-timestamp')

    serializer = LeadActivitySerializer(activities, many=True)

    return Response({
        "timeline": serializer.data
    })


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Lead


class ToggleFavoriteView(APIView):

    def post(self, request, id):
        lead = get_object_or_404(Lead, id=id)

        # Toggle logic
        lead.is_favorite = not lead.is_favorite
        lead.save()

        return Response({
            "id": lead.id,
            "is_favorite": lead.is_favorite,
            "message": "Favorite status updated successfully"
        }, status=status.HTTP_200_OK)
    


@api_view(['PATCH'])
def update_lead_status(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = LeadstageUpdateSerializer(
        lead,
        data=request.data,
        partial=True  
    )

    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "Lead stage updated successfully",
            "id": lead.id,
            "status": lead.stage
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)