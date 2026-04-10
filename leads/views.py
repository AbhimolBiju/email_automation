from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Lead, LeadActivity
from .serializers import (LeadListSerializer,LeadStatusUpdateSerializer,CreateLeadSerializer)
from rest_framework import status,viewsets
from django.shortcuts import render
from .serializers import LeadDetailsSerializer, LeadActivitySerializer,NoteSerializer


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
        return Response({"error": "Lead not found"}, status=404)

    serializer = LeadActivitySerializer(data=request.data)

    if serializer.is_valid():
        serializer.save(lead=lead) 
        return Response({"message": "Activity created successfully"})
    
    return Response(serializer.errors, status=400)

@api_view(['GET'])
def lead_activities(request, lead_id):
    activities = LeadActivity.objects.filter(lead_id=lead_id).order_by('-timestamp')

    serializer = LeadActivitySerializer(activities, many=True)

    return Response({
        "timeline": serializer.data
    })

from .models import Lead, Note


@api_view(["POST"])
def create_lead_comment(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response(
            {"error": "Lead not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = NoteSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save(
            lead=lead,
            created_by=request.user
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# @api_view(['POST'])
# def create_task(request, lead_id=None):  # <--- accept lead_id
#     data = request.data.copy()  # make mutable
#     if lead_id:
#         data['lead'] = lead_id  # attach lead_id to request data

#     serializer = TaskSerializer(data=data)
#     if serializer.is_valid():
#         serializer.save()
#         return Response(
#             {"message": "Task created successfully", "data": serializer.data},
#             status=201
#         )

#     return Response(serializer.errors, status=400)




# from rest_framework.decorators import api_view
# from rest_framework.response import Response
# from rest_framework import status
# from .models import Lead, InsuranceInfo
# from .serializers import InsuranceInfoSerializer

# @api_view(['GET'])
# def get_insurance_info(request, lead_id):
#     try:
#         lead = Lead.objects.get(id=lead_id)
#     except Lead.DoesNotExist:
#         return Response(
#             {"error": "Lead not found"},
#             status=status.HTTP_404_NOT_FOUND
#         )

#     # Use get_or_none pattern
#     try:
#         insurance_info = lead.insurance_info
#     except InsuranceInfo.DoesNotExist:
#         return Response(
#             {"lead_id": str(lead.id), "data": {}},
#             status=status.HTTP_200_OK
#         )

#     serializer = InsuranceInfoSerializer(insurance_info)
#     return Response(
#         {
#             "lead_id": str(lead.id),
#             "data": serializer.data
#         },
#         status=status.HTTP_200_OK
#     )