from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound

from api.responses import error_response, success_response
from deals.models import Deal
from leads.models import Lead

from .models import InsuranceInfo, InsuranceProvider, QuoteBatch
from .serializers import (
    InsuranceInfoSerializer,
    InsuranceProviderSerializer,
    QuoteBatchDetailSerializer,
    QuoteBatchListSerializer,
    QuoteResultSerializer,
)
from .services import get_best_quotes, get_latest_quote_batch, health_check_provider, list_quote_batches
from .tasks import enqueue_quote_generation


@api_view(["GET"])
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


@api_view(["GET"])
def list_insurance_providers(request):
    providers = InsuranceProvider.objects.all().order_by("priority", "name")
    serializer = InsuranceProviderSerializer(providers, many=True)
    return success_response(
        message="Insurance providers fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(["POST"])
def provider_health_check(request, provider_id):
    try:
        provider = InsuranceProvider.objects.get(id=provider_id)
    except InsuranceProvider.DoesNotExist:
        raise NotFound("Insurance provider not found")

    try:
        result = health_check_provider(provider)
    except Exception as exc:
        return error_response(
            message="Provider health check failed",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            errors={"provider": provider.code, "detail": str(exc)},
        )

    return success_response(
        message="Provider health check completed",
        data={"provider": provider.code, "result": result},
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
def list_quotes(request):
    serializer = QuoteBatchListSerializer(list_quote_batches(), many=True)
    return success_response(
        message="Quote batches fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
def quote_batch_detail(request, batch_id):
    batch = (
        QuoteBatch.objects.select_related("deal", "lead", "best_provider")
        .prefetch_related("results__provider")
        .filter(id=batch_id)
        .first()
    )
    if not batch:
        raise NotFound("Quote batch not found")

    serializer = QuoteBatchDetailSerializer(batch)
    return success_response(
        message="Quote batch fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
def quote_batch_results(request, batch_id):
    batch = (
        QuoteBatch.objects.prefetch_related("results__provider")
        .filter(id=batch_id)
        .first()
    )
    if not batch:
        raise NotFound("Quote batch not found")
    serializer = QuoteResultSerializer(batch.results.all().order_by("ranking", "provider__priority"), many=True)
    return success_response(
        message="Quote results fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
def latest_quote_for_deal(request, deal_id):
    try:
        Deal.objects.only("id").get(id=deal_id)
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")

    batch = get_latest_quote_batch(deal_id)
    if not batch:
        return success_response(
            message="No quote batch available for this deal yet",
            data=None,
            status_code=status.HTTP_200_OK,
        )
    serializer = QuoteBatchDetailSerializer(batch)
    return success_response(
        message="Latest quote batch fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(["POST"])
def refresh_quotes(request, deal_id):
    try:
        Deal.objects.only("id").get(id=deal_id)
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")

    triggered_by_id = getattr(request.user, "id", None) if getattr(request.user, "is_authenticated", False) else None
    payload = get_best_quotes(
        deal_id,
        force_refresh=True,
        triggered_by_id=triggered_by_id,
    )
    return success_response(
        message="Quote refresh completed successfully",
        data=payload,
        status_code=status.HTTP_200_OK,
    )


@api_view(["POST"])
def get_deal_quotes(request, deal_id):
    try:
        result = get_best_quotes(
            deal_id,
            force_refresh=bool(request.data.get("force_refresh", False)),
            triggered_by_id=getattr(request.user, "id", None) if getattr(request.user, "is_authenticated", False) else None,
        )
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")
    except Exception as exc:
        return error_response(
            message="Failed to fetch quotes",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            errors={"detail": str(exc)},
        )

    return success_response(
        message="Quotes fetched successfully",
        data=result,
        status_code=status.HTTP_200_OK,
    )
