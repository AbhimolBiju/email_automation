import logging

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
from .services import (
    build_comparison_payload,
    get_best_quotes,
    get_latest_quote_batch,
    health_check_provider,
    list_quote_batches,
    refresh_quote_batch,
)
from .tasks import enqueue_quote_generation

logger = logging.getLogger(__name__)


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
        QuoteBatch.objects.select_related("deal", "lead", "best_provider")
        .prefetch_related("results__provider")
        .filter(id=batch_id)
        .first()
    )
    if not batch:
        raise NotFound("Quote batch not found")
    serializer = QuoteResultSerializer(
        batch.results.all().order_by("ranking", "provider__priority"),
        many=True,
    )
    comparison_payload = build_comparison_payload(batch)
    return success_response(
        message="Quote results fetched successfully",
        data={
            "results": serializer.data,
            "comparison_payload": comparison_payload,
        },
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
def refresh_quote_batch_view(request, batch_id):
    batch = (
        QuoteBatch.objects.select_related("deal")
        .filter(id=batch_id)
        .first()
    )
    if not batch:
        raise NotFound("Quote batch not found")

    triggered_by_id = (
        getattr(request.user, "id", None)
        if getattr(request.user, "is_authenticated", False)
        else None
    )
    try:
        payload = refresh_quote_batch(batch_id, triggered_by_id=triggered_by_id)
    except ValueError as exc:
        raise NotFound(str(exc)) from exc

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


# Provider codes that should always appear in the comparison response, even
# when one of them is inactive or did not return a quote. Keeping the order
# stable here also defines the column order on the comparison UI.
_COMPARISON_PROVIDER_CODES: tuple[str, ...] = ("DIC", "QIC", "NIA")


def _shape_comparison_provider(
    code: str,
    *,
    provider_name: str = "",
    logo: str = "",
    result: dict | None = None,
    error: str = "",
) -> dict:
    result = result or {}
    normalized = result.get("normalized_response") or {}
    status_value = str(result.get("status") or ("missing" if not result else "")).lower()
    return {
        "provider": code,
        "provider_name": (
            result.get("provider_name")
            or normalized.get("provider_name")
            or provider_name
            or code
        ),
        "logo": result.get("logo") or normalized.get("logo") or logo or "",
        "status": status_value or "missing",
        "premium": result.get("premium"),
        "vat": result.get("vat"),
        "total": result.get("total"),
        "currency": result.get("currency") or "AED",
        "plan_name": result.get("plan_name") or "",
        "response_time_ms": result.get("response_time_ms"),
        "ranking": result.get("ranking"),
        "coverage_score": result.get("coverage_score"),
        "is_cheapest": bool(result.get("is_cheapest")),
        "is_best_value": bool(result.get("is_best_value")),
        "is_recommended": bool(result.get("recommended")),
        "normalized_response": normalized,
        "raw_response": result.get("raw_response") or {},
        "error": result.get("error_message") or error or "",
        "result_id": result.get("id"),
    }


@api_view(["POST"])
def compare_quotes(request, deal_id):
    """
    Run the 3 active provider APIs (DIC, QIC, NIA) for the given deal and
    return their quotes side-by-side for comparison.

    Re-uses `get_best_quotes` which executes providers in parallel, persists
    a `QuoteBatch`, and ranks the results — this endpoint just re-shapes the
    payload so the frontend can render a comparison table directly.
    """
    try:
        Deal.objects.only("id").get(id=deal_id)
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")

    triggered_by_id = (
        getattr(request.user, "id", None)
        if getattr(request.user, "is_authenticated", False)
        else None
    )

    force_refresh = bool(request.data.get("force_refresh", False))
    active_codes = {
        str(p.code).upper()
        for p in InsuranceProvider.objects.filter(is_active=True)
    }

    def _run(force: bool) -> dict:
        return get_best_quotes(
            deal_id,
            force_refresh=force,
            triggered_by_id=triggered_by_id,
        )

    try:
        payload = _run(force_refresh)

        # Auto-heal stale cache: if any currently-active provider has no result
        # in the returned batch (e.g. the cached batch was created before the
        # provider was activated), re-run with force_refresh=True so the
        # comparison always reflects all active providers.
        if not force_refresh and active_codes:
            present_codes = {
                str(item.get("provider") or "").upper()
                for item in (payload.get("results") or [])
                if isinstance(item, dict)
            } | {
                str(p.get("provider") or "").upper()
                for p in (payload.get("providers") or [])
                if isinstance(p, dict)
                and str(p.get("status") or "").lower() != "missing"
            }
            if active_codes - present_codes:
                logger.info(
                    "compare_quotes: active providers %s missing from cached batch; forcing refresh",
                    sorted(active_codes - present_codes),
                )
                payload = _run(force=True)
    except Exception as exc:
        return error_response(
            message="Failed to compare quotes",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            errors={"detail": str(exc)},
        )

    results_by_provider: dict[str, dict] = {}
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("provider") or "").upper()
        if code and code not in results_by_provider:
            results_by_provider[code] = item

    provider_statuses: dict[str, dict] = {
        str(p.get("provider") or "").upper(): p
        for p in (payload.get("providers") or [])
        if isinstance(p, dict)
    }

    seen_codes: set[str] = set()
    providers_data: list[dict] = []
    for code in _COMPARISON_PROVIDER_CODES:
        seen_codes.add(code)
        result_item = results_by_provider.get(code)
        status_item = provider_statuses.get(code, {})

        if not result_item and code not in active_codes:
            error_msg = "Provider not configured or inactive."
            providers_data.append(
                _shape_comparison_provider(code, error=error_msg)
            )
            continue

        providers_data.append(
            _shape_comparison_provider(
                code,
                provider_name=str(status_item.get("provider_name") or ""),
                result=result_item,
                error=str(status_item.get("error") or ""),
            )
        )

    # Surface any extra providers that ran but aren't in the canonical 3
    # (defensive — keeps the response complete if a 4th provider is enabled).
    for code, result_item in results_by_provider.items():
        if code in seen_codes:
            continue
        status_item = provider_statuses.get(code, {})
        providers_data.append(
            _shape_comparison_provider(
                code,
                provider_name=str(status_item.get("provider_name") or ""),
                result=result_item,
                error=str(status_item.get("error") or ""),
            )
        )

    successful_count = sum(
        1 for p in providers_data if p["status"] == "success"
    )

    batch_meta = payload.get("batch") or {}
    response_data = {
        "deal_id": deal_id,
        "batch_id": batch_meta.get("id"),
        "reference_no": batch_meta.get("reference_no"),
        "customer_name": batch_meta.get("customer_name") or "",
        "product": batch_meta.get("product") or "",
        "vehicle": batch_meta.get("vehicle") or "",
        "requested_at": batch_meta.get("requested_at"),
        "best_provider": batch_meta.get("best_provider") or "",
        "best_total": batch_meta.get("best_total"),
        "providers_count": len(providers_data),
        "successful_count": successful_count,
        "providers": providers_data,
    }

    return success_response(
        message="Quotes comparison fetched successfully",
        data=response_data,
        status_code=status.HTTP_200_OK,
    )
