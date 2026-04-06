from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Lead, LeadActivity
from .serializers import LeadDetailsSerializer, LeadActivitySerializer


@api_view(['GET'])
def lead_details(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"error": "Lead not found"}, status=404)

    serializer = LeadDetailsSerializer(lead)
    return Response(serializer.data)




@api_view(['GET'])
def lead_activities(request, lead_id):
    activities = LeadActivity.objects.filter(lead_id=lead_id).order_by('-timestamp')

    serializer = LeadActivitySerializer(activities, many=True)

    return Response({
        "timeline": serializer.data
    })