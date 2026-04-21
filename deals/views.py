from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum,Count
from .models import Deal
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes
from .serializers import (
    DealListSerializer,
    DealStageUpdateSerializer,
    DealExportSerializer,
    FilterOptionsResponseSerializer,
    DealCreateSerializer,
    DealGeneralInfoSerializer,
    DealAdditionalFieldSerializer
)
from django.utils.dateformat import DateFormat




@api_view(['GET'])
@permission_classes([AllowAny])
def pipeline_summary(request):

    stages = dict(Deal.STAGE_CHOICES)

    stage_counts = (
        Deal.objects.values('stage_id')
        .annotate(count=Count('id'))
    )

    count_map = {item['stage_id']: item['count'] for item in stage_counts}

    data = []

    for stage_id, label in stages.items():
        data.append({
            "id": stage_id,
            "label": label,
            "count": count_map.get(stage_id, 0)
        })

    return Response({
        "status": "success",
        "data": {
            "workflow_id": "insurance_v3",
            "stages": data
        }
    }, status=status.HTTP_200_OK)
    
    



@api_view(['GET'])
@permission_classes([AllowAny])
def deals_board(request):

    stage_filter = request.GET.get('stages')

    if stage_filter:
        stage_ids = [int(s) for s in stage_filter.split(',')]
        deals = Deal.objects.filter(stage_id__in=stage_ids)
    else:
        deals = Deal.objects.all()

    stages = dict(Deal.STAGE_CHOICES)

    columns = []
    total_board_value = 0

    for stage_id, label in stages.items():

        if stage_filter and stage_id not in stage_ids:
            continue

        stage_deals = deals.filter(stage_id=stage_id)

        total_value = stage_deals.count()

        total_board_value += total_value

        deal_list = []

        for deal in stage_deals:
            deal_list.append({
                "id": str(deal.id),
                "title": f"Deal #{deal.id}",

                "client": {
                    "name": deal.lead.name if deal.lead else "",
                    "last_contact": "N/A"
                },

                "responsible_person": {
                    "id": str(deal.lead.responsible.id) if deal.lead and deal.lead.responsible else "",
                    "name": str(deal.lead.responsible) if deal.lead and deal.lead.responsible else "",
                    "avatar": ""
                },

                "source": deal.lead.delivery_channel if deal.lead else "",

                "modified_at": DateFormat(deal.updated_at).format("Y-m-d\\TH:i:s\\Z"),

                "activity_count": 0,
                "is_favorite": False,
                "actions": ["call", "email", "chat"]
            })

        columns.append({
            "stage_id": stage_id,
            "label": label,
            "total_value": total_value,
            "deal_count": stage_deals.count(),
            "color_theme": "blue",
            "deals": deal_list
        })

    return Response({
    "success": True,
    "data": {
        "total_board_value": total_board_value,
        "currency": "AED",
        "columns": columns
            }
    }, status=status.HTTP_200_OK)
    



from django.db.models import Q

@api_view(['GET'])
@permission_classes([AllowAny])
def search_deals(request):

    query = request.GET.get('q', '')

    deals = Deal.objects.filter(
       Q(lead__name__icontains=query) |
        Q(reg_number__icontains=query) |
        Q(emirates_id__icontains=query)
    )

    serializer = DealListSerializer(deals, many=True)

    return Response({
        "success": True,
        "data": serializer.data
    }, status=status.HTTP_200_OK)





@api_view(['GET'])
@permission_classes([AllowAny])
def export_deals(request):

    deals = Deal.objects.all()

    serializer = DealExportSerializer(deals, many=True)

    return Response({
        "success": True,
        "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    
    
    

@api_view(['PATCH'])
@permission_classes([AllowAny])
def update_deal_stage(request, id):

    try:
        deal = Deal.objects.get(id=id)
    except Deal.DoesNotExist:
        return Response(
            {"message": "Deal not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = DealStageUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new_stage_id = serializer.validated_data["new_stage_id"]
    reason = serializer.validated_data.get("reason", "")

    old_stage_id = deal.stage_id
    deal.stage_id = new_stage_id
    deal.save(update_fields=["stage_id", "updated_at"])

    stage_map = dict(Deal.STAGE_CHOICES)

    return Response({
        "message": "Deal stage updated successfully",
        "deal_id": deal.id,
        "from": {
            "id": old_stage_id,
            "name": stage_map.get(old_stage_id)
        },
        "to": {
            "id": new_stage_id,
            "name": stage_map.get(new_stage_id)
        },
        "reason": reason
    }, status=status.HTTP_200_OK)







@api_view(['GET'])
@permission_classes([AllowAny])
def deals_by_stage(request):

    stage_id = request.GET.get('stage_id')

    if not stage_id:
        return Response({"message": "stage_id is required"}, status=400)

    try:
        stage_id = int(stage_id)
    except ValueError:
        return Response({"message": "Invalid stage_id"}, status=400)

    deals = Deal.objects.filter(stage_id=stage_id)

    serializer = DealListSerializer(deals, many=True)

    stage_name = dict(Deal.STAGE_CHOICES).get(stage_id)

    return Response({
    "success": True,
    "data": {
        "stage_id": stage_id,
        "stage_name": stage_name,
        "count": deals.count(),
        "results": serializer.data
        }
    }, status=status.HTTP_200_OK)
    
    
    
    
    
@api_view(['GET'])
@permission_classes([AllowAny])
def deal_filter_options(request):

    stages = [
        {"id": s[0], "label": s[1]}
        for s in Deal.STAGE_CHOICES
    ]

    data = {
        "sort_options": [
            {"key": "created_at", "label": "Created Date"},
            {"key": "updated_at", "label": "Last Modified"},
            {"key": "stage_id", "label": "Stage"},
        ],
        "filters": [
            {
                "key": "stage_id",
                "label": "Stage",
                "type": "multi_select",
                "options": stages
            },
            {
                "key": "is_favorite",
                "label": "Favorites",
                "type": "boolean"
            }
        ]
    }

    serializer = FilterOptionsResponseSerializer(data=data)
    serializer.is_valid(raise_exception=True)

    return Response({
    "success": True,
    "data": serializer.data
    }, status=status.HTTP_200_OK)





@api_view(['GET'])
def deal_list(request):

    deals = Deal.objects.all()

    search = request.GET.get('search')
    if search:
        deals = deals.filter(
            Q(lead__name__icontains=search) |
            Q(reg_number__icontains=search) |
            Q(emirates_id__icontains=search)
        )

    sort_by = request.GET.get('sort_by')

    if sort_by == "created_at_desc":
        deals = deals.order_by('-created_at')
    elif sort_by == "created_at_asc":
        deals = deals.order_by('created_at')
    elif sort_by == "updated_at_desc":
        deals = deals.order_by('-updated_at')
    elif sort_by == "updated_at_asc":
        deals = deals.order_by('updated_at')

    view = request.GET.get('view', 'list')

    serializer = DealListSerializer(deals, many=True)

    return Response({
    "success": True,
    "data": {
        "view": view,
        "count": deals.count(),
        "results": serializer.data
        }
    }, status=status.HTTP_200_OK)
    
    
    
    
@api_view(['GET'])
def deals_board_paginated(request):

  
    offset_stage = int(request.GET.get('offset_stage', 1))
    limit_columns = int(request.GET.get('limit_columns', 5))
    search = request.GET.get('search', '')

  
    stages = dict(Deal.STAGE_CHOICES)

   
    stage_items = list(stages.items())
    start_index = offset_stage - 1
    end_index = start_index + limit_columns
    selected_stages = stage_items[start_index:end_index]

  
    deals = Deal.objects.all()

 
    if search:
        deals = deals.filter(
            Q(lead__name__icontains=search) |
            Q(reg_number__icontains=search) |
            Q(emirates_id__icontains=search)
        )

    columns = []


    for stage_id, label in selected_stages:

        stage_deals = deals.filter(stage_id=stage_id)

        deal_list = []
        
        for deal in stage_deals:
            deal_list.append({
                "id": deal.id,
                "title": f"Deal #{deal.id}",
                "customer_name": deal.lead.name if deal.lead else "",
                "reg_number": deal.reg_number,
                "stage_id": deal.stage_id,
                "updated_at": deal.updated_at
            })

        columns.append({
            "stage_id": stage_id,
            "label": label,
            "deal_count": stage_deals.count(),
            "deals": deal_list
        })

    return Response({
    "success": True,
    "data": {
        "offset_stage": offset_stage,
        "limit_columns": limit_columns,
        "columns_returned": len(columns),
        "columns": columns
        }
    }, status=status.HTTP_200_OK)
    
    
    



@api_view(['GET'])
def grouped_deals(request):

   
    stages_param = request.GET.get('stages')
    limit = int(request.GET.get('limit', 5))

   
    if not stages_param:
        return Response({"message": "stages param is required"}, status=400)

    try:
        stage_ids = [int(s) for s in stages_param.split(',')]
    except:
        return Response({"message": "Invalid stages format"}, status=400)

    stage_map = dict(Deal.STAGE_CHOICES)

    response_data = []

    for stage_id in stage_ids:

        deals = Deal.objects.filter(stage_id=stage_id).order_by('-created_at')[:limit]

        serializer = DealListSerializer(deals, many=True)

        response_data.append({
            "stage_id": stage_id,
            "stage_name": stage_map.get(stage_id),
            "count": Deal.objects.filter(stage_id=stage_id).count(),
            "results": serializer.data
        })

    return Response({
    "success": True,
    "data": {
        "total_stages": len(stage_ids),
        "limit_per_stage": limit,
        "data": response_data
        }
    }, status=status.HTTP_200_OK)
    
    
    
    
@api_view(['POST'])
@permission_classes([AllowAny])
def create_deal(request):
    serializer = DealCreateSerializer(data=request.data)

    if serializer.is_valid():
        deal = serializer.save()
        return Response({
        "success": True,
        "message": "Deal created successfully",
        "data": {
        "deal_id": deal.id
        }
    }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@api_view(['GET'])
@permission_classes([AllowAny])
def deal_underwriter_information(request, deal_id):
    try:
        deal = Deal.objects.get(id=deal_id)
    except Deal.DoesNotExist:
        return Response(
            {"message": "Deal not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = DealGeneralInfoSerializer(deal)
    return Response({
    "success": True,
    "data": serializer.data
    }, status=status.HTTP_200_OK)






@api_view(['PATCH'])
@permission_classes([AllowAny])
def update_additional_field(request, deal_id):
    try:
        deal = Deal.objects.get(id=deal_id)
    except Deal.DoesNotExist:
        return Response(
            {"message": "Deal not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = DealAdditionalFieldSerializer(
        deal,
        data=request.data,
        partial=True 
    )

    if serializer.is_valid():
        serializer.save()
        return Response({
            "success": True,
            "message": "Additional field updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)