from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from django.db.models import Sum,Count
from .models import Deal
from leads.models import Lead
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
from rest_framework.exceptions import NotFound, ValidationError
from api.responses import success_response




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

    return success_response(
        message="Pipeline summary fetched successfully",
        data={"workflow_id": "insurance_v3", "stages": data},
        status_code=status.HTTP_200_OK,
    )
    
    
    
from rest_framework.response import Response
from rest_framework import status


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

    response_data = []

    # For stage_id=1 ("Potential Customer"), we want to show Leads that have
    # reached Lead.stage == "sales_qualified_lead" even if a Deal record doesn't exist yet.
    sales_qualified_leads = None
    if not stage_filter or 1 in (stage_ids if stage_filter else []):
        sales_qualified_leads = (
            Lead.objects.filter(stage="sales_qualified_lead")
            .exclude(deals__isnull=False)  # only those not already linked to a Deal
            .order_by("-updated_at")
        )

    for stage_id, label in stages.items():

        if stage_filter and stage_id not in stage_ids:
            continue

        stage_deals = deals.filter(stage_id=stage_id).select_related('lead')

        deal_list = []

        if stage_id == 1 and sales_qualified_leads is not None:
            for lead in sales_qualified_leads:
                deal_list.append(
                    {
                        # No Deal exists yet; use a stable synthetic id for UI
                        "deal_id": int(lead.id),
                        "lead": {
                            "id": lead.id,
                            "name": lead.name or "",
                            "email": lead.email or "",
                            "status": lead.status or "",
                            "mobile_number": lead.mobile_number or "",
                            "updated_at": DateFormat(lead.updated_at).format(
                                "Y-m-d H:i"
                            ),
                        },
                    }
                )

        for deal in stage_deals:
            lead = deal.lead

            deal_list.append({
                "deal_id": deal.id,
                "lead": {
                    "id": lead.id if lead else None,
                    "name": lead.name if lead else "",
                    "email": lead.email if lead else "",
                    "status": lead.status if lead else "",
                    "mobile_number": lead.mobile_number if lead else "",
                    "updated_at": DateFormat(lead.updated_at).format('Y-m-d H:i') if lead else ""
                    
                } if lead else None
            })

        response_data.append({
            "stage_id": stage_id,
            "label": label,
            "deal_count": len(deal_list),
            "deals": deal_list
        })

    return Response(response_data, status=status.HTTP_200_OK)




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

    return success_response(
        message="Deals fetched successfully",
        data=serializer.data,
        meta={"total": deals.count()},
        status_code=status.HTTP_200_OK,
    )





@api_view(['GET'])
@permission_classes([AllowAny])
def export_deals(request):

    deals = Deal.objects.all()

    serializer = DealExportSerializer(deals, many=True)

    return success_response(
        message="Deals exported successfully",
        data=serializer.data,
        meta={"total": deals.count()},
        status_code=status.HTTP_200_OK,
    )
    
    
    
    

@api_view(['PATCH'])
@permission_classes([AllowAny])
def update_deal_stage(request, id):

    try:
        deal = Deal.objects.get(id=id)
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")

    serializer = DealStageUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new_stage_id = serializer.validated_data["new_stage_id"]
    reason = serializer.validated_data.get("reason", "")

    old_stage_id = deal.stage_id
    deal.stage_id = new_stage_id
    deal.save(update_fields=["stage_id", "updated_at"])

    stage_map = dict(Deal.STAGE_CHOICES)

    return success_response(
        message="Deal stage updated successfully",
        data={
            "deal_id": deal.id,
            "from": {"id": old_stage_id, "name": stage_map.get(old_stage_id)},
            "to": {"id": new_stage_id, "name": stage_map.get(new_stage_id)},
            "reason": reason,
        },
        status_code=status.HTTP_200_OK,
    )







@api_view(['GET'])
@permission_classes([AllowAny])
def deals_by_stage(request):

    stage_id = request.GET.get('stage_id')

    if not stage_id:
        raise ValidationError({"stage_id": ["stage_id is required"]})

    try:
        stage_id = int(stage_id)
    except ValueError:
        raise ValidationError({"stage_id": ["Invalid stage_id"]})

    deals = Deal.objects.filter(stage_id=stage_id)

    serializer = DealListSerializer(deals, many=True)

    stage_name = dict(Deal.STAGE_CHOICES).get(stage_id)

    return success_response(
        message="Deals fetched successfully",
        data=serializer.data,
        meta={
            "stage_id": stage_id,
            "stage_name": stage_name,
            "total": deals.count(),
        },
        status_code=status.HTTP_200_OK,
    )
    
    
    
    
    
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

    return success_response(
        message="Deal filter options fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )





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

    return success_response(
        message="Deals fetched successfully",
        data=serializer.data,
        meta={"view": view, "total": deals.count()},
        status_code=status.HTTP_200_OK,
    )
    
    
    
    
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

    return success_response(
        message="Deals board fetched successfully",
        data={"columns": columns},
        meta={
            "offset_stage": offset_stage,
            "limit_columns": limit_columns,
            "columns_returned": len(columns),
        },
        status_code=status.HTTP_200_OK,
    )
    
    
    



@api_view(['GET'])
def grouped_deals(request):

   
    stages_param = request.GET.get('stages')
    limit = int(request.GET.get('limit', 5))

   
    if not stages_param:
        raise ValidationError({"stages": ["stages param is required"]})

    try:
        stage_ids = [int(s) for s in stages_param.split(',')]
    except:
        raise ValidationError({"stages": ["Invalid stages format"]})

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

    return success_response(
        message="Deals fetched successfully",
        data=response_data,
        meta={"total_stages": len(stage_ids), "limit_per_stage": limit},
        status_code=status.HTTP_200_OK,
    )
    
    
    
    
@api_view(['POST'])
@permission_classes([AllowAny])
def create_deal(request):
    data = request.data.copy()

    lead_id = data.get("lead") or data.get("lead_id")
    if not lead_id:
        # Create (or reuse) Lead from payload when lead id isn't provided.
        lead_name = (
            data.get("lead_name")
            or data.get("name")
            or data.get("customer_name")
            or data.get("full_name")
        )
        lead_email = data.get("lead_email") or data.get("email")
        lead_mobile = data.get("mobile_number") or data.get("phone_number") or data.get(
            "mobile"
        )

        if not lead_name or not lead_email:
            raise ValidationError(
                {
                    "lead": [
                        "Missing lead info. Provide lead_id/lead, or include name & email in payload."
                    ]
                }
            )

        lead_defaults = {
            "mobile_number": lead_mobile,
            "phone_number": lead_mobile,
            # Reasonable defaults for deals created from a qualified lead flow
            "stage": data.get("lead_stage") or "sales_qualified_lead",
            "status": data.get("lead_status") or "QUALIFIED",
        }

        lead, _created = Lead.objects.get_or_create(
            email=lead_email, defaults={"name": lead_name, **lead_defaults}
        )

        # Keep name/mobile in sync if the request provides them.
        changed = False
        if lead_name and lead.name != lead_name:
            lead.name = lead_name
            changed = True
        if lead_mobile and (lead.mobile_number != lead_mobile):
            lead.mobile_number = lead_mobile
            lead.phone_number = lead_mobile
            changed = True
        if changed:
            lead.save(update_fields=["name", "mobile_number", "phone_number", "updated_at"])

        data["lead"] = str(lead.id)

    serializer = DealCreateSerializer(data=data)

    serializer.is_valid(raise_exception=True)
    deal = serializer.save()
    return success_response(
        message="Deal created successfully",
        data={"id": deal.id},
        status_code=status.HTTP_201_CREATED,
    )




@api_view(['GET'])
@permission_classes([AllowAny])
def deal_underwriter_information(request, deal_id):
    try:
        deal = Deal.objects.get(id=deal_id)
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")

    serializer = DealGeneralInfoSerializer(deal)
    return success_response(
        message="Deal information fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )






@api_view(['PATCH'])
@permission_classes([AllowAny])
def update_additional_field(request, deal_id):
    try:
        deal = Deal.objects.get(id=deal_id)
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")

    serializer = DealAdditionalFieldSerializer(
        deal,
        data=request.data,
        partial=True 
    )

    serializer.is_valid(raise_exception=True)
    serializer.save()
    return success_response(
        message="Additional field updated successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )