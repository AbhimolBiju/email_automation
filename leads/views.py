from datetime import timedelta


from invoice.models import Transaction
from rest_framework.decorators import api_view
from .models import Lead, LeadActivity
from deals.models import Deal
from .serializers import (LeadListSerializer,LeadStatusUpdateSerializer,CreateLeadSerializer)
from rest_framework import status,viewsets
from django.shortcuts import render
from .serializers import LeadDetailsSerializer, LeadActivitySerializer,LeadstageUpdateSerializer
from rest_framework.exceptions import NotFound
from django.utils.timezone import now
from rest_framework.response import Response
from django.db.models import Sum, Q, Count

from api.responses import success_response


@api_view(['GET'])
def lead_list(request):
    leads = (
        Lead.objects.exclude(stage="sales_qualified_lead").order_by("-created_at")
    )
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






class StatsView(APIView):
    def get(self, request):
        # Timeframe
        days = int(request.GET.get("days", 7))
        today = now().date()

        current_start = today - timedelta(days=days)
        previous_start = today - timedelta(days=days * 2)

        def get_diff_percent(current, previous):
            if previous == 0:
                return "+100%" if current > 0 else "0%"
            diff = ((current - previous) / previous) * 100
            return f"{'+' if diff > 0 else ''}{round(diff)}%"

        # -------------------------------
        # 1. Revenue
        # -------------------------------
        revenue_curr = Transaction.objects.filter(
            invoice_date__gte=current_start
        ).aggregate(total=Sum("net_due"))["total"] or 0

        revenue_prev = Transaction.objects.filter(
            invoice_date__gte=previous_start,
            invoice_date__lt=current_start
        ).aggregate(total=Sum("net_due"))["total"] or 0

        # -------------------------------
        # 2. Total Leads
        # -------------------------------
        leads_curr = Lead.objects.filter(
            created_at__gte=current_start
        ).count()

        leads_prev = Lead.objects.filter(
            created_at__gte=previous_start,
            created_at__lt=current_start
        ).count()

        # -------------------------------
        # 3. Qualified Leads
        # (using STATUS field)
        # -------------------------------
        qual_leads_curr = Lead.objects.filter(
            created_at__gte=current_start,
            status="QUALIFIED"
        ).count()

        qual_leads_prev = Lead.objects.filter(
            created_at__gte=previous_start,
            created_at__lt=current_start,
            status="QUALIFIED"
        ).count()

        # -------------------------------
        # 4. Pending Deals
        # (stage_id = 11 → "Payment Pending")
        # -------------------------------
        pending_curr = Deal.objects.filter(
            created_at__gte=current_start,
            stage_id=11
        ).count()

        pending_prev = Deal.objects.filter(
            created_at__gte=previous_start,
            created_at__lt=current_start,
            stage_id=11
        ).count()

        # -------------------------------
        # 5. Total Deals
        # -------------------------------
        deals_curr = Deal.objects.filter(
            created_at__gte=current_start
        ).count()

        deals_prev = Deal.objects.filter(
            created_at__gte=previous_start,
            created_at__lt=current_start
        ).count()

        # -------------------------------
        # 6. Policies Issued
        # -------------------------------
        policies_curr = Transaction.objects.filter(
            invoice_date__gte=current_start,
            policy_number__gt=""   # better than isnull
        ).count()

        policies_prev = Transaction.objects.filter(
            invoice_date__gte=previous_start,
            invoice_date__lt=current_start,
            policy_number__gt=""
        ).count()

        # -------------------------------
        # Final Response
        # -------------------------------
        data = [
            {
                "label": "Revenue",
                "value": f"AED {round(revenue_curr / 1000, 1)}k",
                "trend": get_diff_percent(revenue_curr, revenue_prev)
            },
            {
                "label": "Total Leads",
                "value": f"{round(leads_curr / 1000, 1)}k",
                "trend": get_diff_percent(leads_curr, leads_prev)
            },
            {
                "label": "Qualified Leads",
                "value": f"{round(qual_leads_curr / 1000, 1)}k",
                "trend": get_diff_percent(qual_leads_curr, qual_leads_prev)
            },
            {
                "label": "Pending Deals",
                "value": pending_curr,
                "trend": get_diff_percent(pending_curr, pending_prev)
            },
            {
                "label": "Total Deals",
                "value": f"{round(deals_curr / 1000, 1)}k",
                "trend": get_diff_percent(deals_curr, deals_prev)
            },
            {
                "label": "Policies Issued",
                "value": f"{round(policies_curr / 1000, 1)}k",
                "trend": get_diff_percent(policies_curr, policies_prev)
            },
        ]

        return Response({"success": True, "message": "Stats fetched successfully", "data": data}, status=status.HTTP_200_OK)