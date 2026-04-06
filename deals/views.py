from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Sum

from .models import Deals
from .serializers import DealSerializer



@api_view(['GET'])
@permission_classes([AllowAny])
def pipeline_summary(request):

    stages = []

    for stage_id, label in Deals.STAGE_CHOICES:
        count = Deals.objects.filter(stage_id=stage_id).count()

        stages.append({
            "id": stage_id,
            "label": label,
            "count": count
        })

    return Response({
        "status": "success",
        "data": {
            "stages": stages
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def deals_board(request):

    columns = []

    for stage_id, label in Deals.STAGE_CHOICES:

        deals = Deals.objects.filter(stage_id=stage_id)

        total_value = deals.aggregate(total=Sum('premium_amount'))['total'] or 0

        deal_data = DealSerializer(deals, many=True).data

        columns.append({
            "stage_id": stage_id,
            "label": label,
            "total_value": total_value,
            "deal_count": deals.count(),
            "deals": deal_data
        })

    return Response({
        "columns": columns
    })