from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import QuoteRequest, Insurer
from .serializers import QuoteRequestSerializer,ProviderSerializer
from rest_framework.exceptions import ValidationError
from api.responses import success_response


class QuoteRequestCreateView(APIView):
    """
    POST: Create a new Quote Request
    """

    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        quote_request = serializer.save()
        return success_response(
            message="Quote request created successfully",
            data=QuoteRequestSerializer(quote_request).data,
            status_code=status.HTTP_201_CREATED,
        )


class QuoteRequestListView(APIView):
    """
    GET: List all Quote Requests
    """

    def get(self, request):
        queryset = QuoteRequest.objects.all().order_by('-created_at')
        serializer = QuoteRequestSerializer(queryset, many=True)

        return success_response(
            message="Quote requests fetched successfully",
            data=serializer.data,
            meta={"total": queryset.count()},
            status_code=status.HTTP_200_OK,
        )

class QuoteRequestDetailView(APIView):
    """
    GET: Retrieve single Quote by quote_id
    """

    def get(self, request, quote_id):
        quote = get_object_or_404(QuoteRequest, id=quote_id)  # or quote_id field if exists
        serializer = QuoteRequestSerializer(quote)

        return success_response(
            message="Quote request fetched successfully",
            data=serializer.data,
            status_code=status.HTTP_200_OK,
        )


from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import QuoteRequest,Quote


from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

class QuoteComparisonView(APIView):

    def get(self, request, quote_id):
        quote_request = get_object_or_404(QuoteRequest, id=quote_id)

        insurers = Insurer.objects.all()  # or filter if needed

        providers = []

        for insurer in insurers:
            providers.append({
                "provider_name": insurer.name,
                "logo": "",
                "plan_name": "Sample Plan",
                "premium": float(insurer.premium or 0),
                "base_price": float(insurer.premium or 0),
                "vat": 0,
                "currency": "AED",
                "badge": "Best Value",
                "buy_now_url": f"http://localhost:8000/api/quotes/{quote_id}/select-scheme/",
                "vehicle_details": {
                    "excess": "TBA",
                    "ancillary_excess": "TBA",
                    "vehicle_value": "N/A"
                },
                "benefits": {
                    "third_party_liability": "Included"
                },
                "optional_covers": {
                    "driver_cover": "Optional"
                }
            })

        return success_response(
            message="Quote comparison fetched successfully",
            data={
                "customer": {
                    "name": quote_request.customer_name,
                    "product": quote_request.product_type,
                    "created_at": quote_request.created_at,
                },
                "providers": providers,
            },
            status_code=status.HTTP_200_OK,
        )
    

from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .models import QuoteRequest


class QuoteStatsView(APIView):
    """
    GET /api/v1/quotes/stats?period=7days|30days|90days|this_year
    """

    def get(self, request):
        period = request.GET.get('period', '7days')

        now = timezone.now()

        if period == '7days':
            start_date = now - timedelta(days=7)
        elif period == '30days':
            start_date = now - timedelta(days=30)
        elif period == '90days':
            start_date = now - timedelta(days=90)
        elif period == 'this_year':
            start_date = now.replace(month=1, day=1)
        else:
            raise ValidationError({"period": ["Invalid period"]})

        queryset = QuoteRequest.objects.filter(created_at__gte=start_date)

        total_quotes = queryset.count()
        pending_count = queryset.filter(status='pending').count()
        sent_count = queryset.filter(status='sent').count()
        accepted_count = queryset.filter(status='accepted').count()

        return success_response(
            message="Quote stats fetched successfully",
            data={
                "total_quotes": total_quotes,
                "pending_count": pending_count,
                "sent_count": sent_count,
                "accepted_count": accepted_count,
            },
            status_code=status.HTTP_200_OK,
        )