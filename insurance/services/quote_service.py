from __future__ import annotations

import logging
import mimetypes
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from deals.models import Deal
from insurance.models import InsuranceProvider, QuoteBatch, QuoteRequestLog, QuoteResult
from insurance.providers import build_provider
from insurance.providers.exceptions import InsuranceProviderError

from .provider_service import get_active_provider_configs

logger = logging.getLogger(__name__)

QUOTE_CACHE_TTL_SECONDS = 600
QUOTE_BATCH_CACHE_KEY = "insurance:quote-batch:deal:{deal_id}"


def _quote_cache_key(deal_id: int) -> str:
    return QUOTE_BATCH_CACHE_KEY.format(deal_id=deal_id)


def _as_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def build_deal_document_payloads(deal: Deal) -> list[dict[str, Any]]:
    try:
        from documents.models import Document
    except Exception:  # pragma: no cover - app import safety
        return []

    documents = Document.objects.filter(motor_deal=deal).order_by("document_type", "-uploaded_at", "-id")
    latest_by_type: dict[str, Any] = {}
    for document in documents:
        latest_by_type.setdefault(document.document_type, document)

    payloads: list[dict[str, Any]] = []
    for document in latest_by_type.values():
        if not document.file:
            continue
        with document.file.open("rb") as handle:
            file_bytes = handle.read()
        payloads.append(
            {
                "document_type": document.document_type,
                "name": document.name or document.file.name.rsplit("/", 1)[-1],
                "base64": b64encode(file_bytes).decode("ascii"),
                "type": (mimetypes.guess_extension(document.file_type or "") or ".png").lstrip("."),
            }
        )
    return payloads


def build_deal_quote_payload(deal: Deal) -> dict[str, Any]:
    lead = deal.lead
    return {
        "deal_id": deal.id,
        "stage_id": deal.stage_id,
        "product_type": "motor" if deal.insurance_type else (getattr(lead, "product_type", None) or "unknown"),
        "insurance_type": deal.insurance_type,
        "sub_type": deal.sub_type,
        "customer": {
            "lead_id": lead.id if lead else None,
            "name": lead.name if lead else "",
            "email": lead.email if lead else "",
            "mobile_number": lead.mobile_number if lead else "",
            "phone_number": lead.phone_number if lead else "",
            "nationality": deal.nationality,
            "gender": deal.gender,
            "date_of_birth": deal.date_of_birth.isoformat() if deal.date_of_birth else None,
            "emirates_id": deal.emirates_id,
            "emirates_id_expiry_date": deal.id_expiry_dt.isoformat() if deal.id_expiry_dt else None,
            "emirate": deal.emirate,
        },
        "vehicle": {
            "chassis_number": deal.chassis_number,
            "registration_number": deal.reg_number,
            "registration_date": deal.reg_dt.isoformat() if deal.reg_dt else None,
            "plate_code": deal.plate_code,
            "plate_source": deal.plate_source,
            "license_number": deal.license_no,
            "license_from_date": deal.license_from_dt.isoformat() if deal.license_from_dt else None,
            "license_to_date": deal.license_to_dt.isoformat() if deal.license_to_dt else None,
            "traffic_transaction_type": deal.traffic_tran_type,
            "is_vehicle_brand_new": deal.is_veh_brand_new,
            "agency_repair": deal.agency_repair,
            "model_year": deal.model_year,
            "make_id": deal.make_id,
            "model_id": deal.model_id,
            "trim_id": deal.trim_id,
            "body_type_id": deal.body_type_id,
            "engine_capacity_id": deal.engine_capacity_id,
            "transmission_id": deal.transmission_id,
            "is_gcc_spec": deal.is_gcc_spec,
            "mileage": deal.mileage,
            "valuation_date": deal.valuation_date.isoformat() if deal.valuation_date else None,
            "ncd_years": deal.ncd_years,
            "tcf_number": deal.tcf_number,
        },
        "documents": build_deal_document_payloads(deal),
    }


def _normalize_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "yes", "y", "1", "included", "success", "available", "unlimited", "tpl"}


def _calculate_coverage_score(data: dict[str, Any]) -> float:
    score = float(data.get("coverage_score", 0) or 0)
    for section_name in ("benefits", "optional_covers", "vehicle_details"):
        section = data.get(section_name)
        if not isinstance(section, dict):
            continue
        for value in section.values():
            if _normalize_flag(value):
                score += 1
            elif str(value).strip() and str(value).strip().lower() not in {"x", "false", "n/a", "na", "tba", "excluded"}:
                score += 0.5
    if data.get("coverage_amount"):
        score += 1
    if data.get("deductible") not in (None, "", "TBA"):
        score += 0.25
    return round(score, 2)


def _build_normalized_response(provider: InsuranceProvider, normalized_quote) -> dict[str, Any]:
    data = normalized_quote.as_dict(include_raw_response=False)
    data["provider_name"] = provider.name
    data["logo"] = (provider.extra_config or {}).get("logo_url", "")
    data["status"] = str(data.get("status", "SUCCESS")).upper()
    data["benefits"] = data.get("benefits") or {}
    data["optional_covers"] = data.get("optional_covers") or {}
    data["vehicle_details"] = data.get("vehicle_details") or {}
    data["coverage_score"] = _calculate_coverage_score(data)
    return data


def _serialize_batch(batch: QuoteBatch) -> dict[str, Any]:
    batch = (
        QuoteBatch.objects.select_related("deal", "lead", "best_provider")
        .prefetch_related("results__provider")
        .get(pk=batch.pk)
    )
    ordered_results = sorted(
        list(batch.results.all()),
        key=lambda item: (
            item.status != QuoteResult.STATUS_SUCCESS,
            item.ranking if item.ranking is not None else 9999,
            item.provider.priority,
            item.provider.name,
        ),
    )
    results = []
    for result in ordered_results:
        normalized = dict(result.normalized_response or {})
        normalized.setdefault("provider", result.provider.code)
        normalized.setdefault("provider_name", result.provider_name or result.provider.name)
        normalized.setdefault("logo", (result.provider.extra_config or {}).get("logo_url", ""))
        results.append(
            {
                "id": result.id,
                "provider": result.provider.code,
                "provider_name": result.provider_name or result.provider.name,
                "logo": (result.provider.extra_config or {}).get("logo_url", ""),
                "premium": float(result.premium) if result.premium is not None else None,
                "vat": float(result.vat) if result.vat is not None else None,
                "total": float(result.total) if result.total is not None else None,
                "currency": result.currency,
                "plan_name": result.plan_name,
                "response_time_ms": result.response_time_ms,
                "ranking": result.ranking,
                "coverage_score": result.coverage_score,
                "status": result.status.upper(),
                "error_message": result.error_message,
                "normalized_response": normalized,
                "raw_response": result.raw_response,
                "recommended": result.is_recommended,
                "is_cheapest": result.is_cheapest,
                "is_best_value": result.is_best_value,
                "created_at": result.created_at.isoformat(),
            }
        )

    return {
        "batch": {
            "id": batch.id,
            "reference_no": batch.reference_no,
            "deal_id": batch.deal_id,
            "lead_id": batch.lead_id,
            "customer_name": batch.lead.name if batch.lead else "",
            "vehicle": " ".join(
                str(value).strip()
                for value in [batch.deal.make_id, batch.deal.model_id, batch.deal.model_year]
                if value not in (None, "")
            )
            or (batch.deal.reg_number or ""),
            "product": batch.deal.get_sub_type_display()
            or batch.deal.get_insurance_type_display()
            or batch.deal.insurance_type
            or "Motor",
            "requested_at": batch.requested_at.isoformat(),
            "status": batch.status,
            "stage": batch.deal.get_stage_id_display(),
            "best_provider": batch.best_provider.name if batch.best_provider else "",
            "best_total": float(batch.best_total) if batch.best_total is not None else None,
            "cache_expires_at": batch.cache_expires_at.isoformat() if batch.cache_expires_at else None,
        },
        "results": results,
    }


def get_latest_quote_batch(deal_id: int) -> QuoteBatch | None:
    cached_batch_id = cache.get(_quote_cache_key(deal_id))
    queryset = QuoteBatch.objects.select_related("deal", "lead", "best_provider").prefetch_related("results__provider")
    if cached_batch_id:
        batch = queryset.filter(pk=cached_batch_id, deal_id=deal_id).first()
        if batch:
            return batch
    return queryset.filter(deal_id=deal_id).order_by("-requested_at", "-id").first()


def _create_batch(deal: Deal, triggered_by_id: int | None) -> QuoteBatch:
    user_model = get_user_model()
    triggered_by = user_model.objects.filter(pk=triggered_by_id).first() if triggered_by_id else None
    return QuoteBatch.objects.create(
        deal=deal,
        lead=deal.lead,
        triggered_by=triggered_by,
        status=QuoteBatch.STATUS_PROCESSING,
        cache_expires_at=timezone.now() + timedelta(seconds=QUOTE_CACHE_TTL_SECONDS),
    )


def _persist_success(
    *,
    batch: QuoteBatch,
    deal: Deal,
    provider: InsuranceProvider,
    payload: dict[str, Any],
    normalized_quote,
) -> dict[str, Any]:
    normalized_response = _build_normalized_response(provider, normalized_quote)
    request_log = QuoteRequestLog.objects.create(
        deal=deal,
        provider=provider,
        batch=batch,
        request_payload=payload,
        response_payload=normalized_quote.raw_response,
        status=QuoteRequestLog.STATUS_SUCCESS,
        latency_ms=normalized_quote.response_time_ms,
        error_message="",
    )
    result = QuoteResult.objects.create(
        deal=deal,
        batch=batch,
        provider=provider,
        provider_name=provider.name,
        request_log=request_log,
        premium=normalized_quote.premium,
        vat=normalized_quote.vat,
        total=normalized_quote.total,
        currency=normalized_quote.currency,
        plan_name=normalized_quote.plan_name,
        response_time_ms=normalized_quote.response_time_ms,
        coverage_score=normalized_response["coverage_score"],
        status=QuoteResult.STATUS_SUCCESS,
        normalized_response=normalized_response,
        raw_response=normalized_quote.raw_response,
    )
    return {"result_id": result.id, **normalized_response}


def _persist_failure(
    *,
    batch: QuoteBatch,
    deal: Deal,
    provider: InsuranceProvider,
    payload: dict[str, Any],
    exc: Exception,
) -> dict[str, Any]:
    QuoteRequestLog.objects.create(
        deal=deal,
        provider=provider,
        batch=batch,
        request_payload=payload,
        response_payload={},
        status=QuoteRequestLog.STATUS_FAILED,
        error_message=str(exc),
    )
    result = QuoteResult.objects.create(
        deal=deal,
        batch=batch,
        provider=provider,
        provider_name=provider.name,
        status=QuoteResult.STATUS_FAILED,
        error_message=str(exc),
        normalized_response={},
        raw_response={},
    )
    return {
        "id": result.id,
        "provider": provider.code,
        "provider_name": provider.name,
        "status": QuoteResult.STATUS_FAILED.upper(),
        "error": str(exc),
    }


def _fetch_provider_quote(
    *,
    deal: Deal,
    provider: InsuranceProvider,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        provider_instance = build_provider(provider)
        normalized_quote = provider_instance.get_quote(payload)
        return {"provider": provider, "quote": normalized_quote}, None
    except InsuranceProviderError as exc:
        logger.warning(
            "Quote fetch failed for deal %s with provider %s: %s",
            deal.id,
            provider.code,
            exc,
        )
        return None, {"provider": provider, "error": exc}
    except Exception as exc:  # pragma: no cover
        logger.exception(
            "Unexpected quote fetch error for deal %s with provider %s",
            deal.id,
            provider.code,
        )
        return None, {"provider": provider, "error": exc}


def _rank_results(batch: QuoteBatch) -> None:
    success_results = list(
        batch.results.select_related("provider")
        .filter(status=QuoteResult.STATUS_SUCCESS)
        .order_by("provider__priority", "provider__name", "id")
    )
    success_results.sort(
        key=lambda item: (
            item.total if item.total is not None else Decimal("999999999"),
            -item.coverage_score,
            item.response_time_ms,
            item.provider.priority,
        )
    )
    cheapest_total = success_results[0].total if success_results else None
    for index, result in enumerate(success_results, start=1):
        result.ranking = index
        result.is_recommended = index == 1
        result.is_best_value = index == 1
        result.is_cheapest = cheapest_total is not None and result.total == cheapest_total
        normalized = dict(result.normalized_response or {})
        normalized.update(
            {
                "ranking": result.ranking,
                "recommended": result.is_recommended,
                "is_best_value": result.is_best_value,
                "is_cheapest": result.is_cheapest,
            }
        )
        result.normalized_response = normalized
        result.save(
            update_fields=[
                "ranking",
                "is_recommended",
                "is_best_value",
                "is_cheapest",
                "normalized_response",
            ]
        )

    if success_results:
        top = success_results[0]
        batch.best_provider = top.provider
        batch.best_total = top.total
        batch.status = (
            QuoteBatch.STATUS_SUCCESS
            if batch.results.filter(status=QuoteResult.STATUS_FAILED).count() == 0
            else QuoteBatch.STATUS_PARTIAL_SUCCESS
        )
    else:
        batch.best_provider = None
        batch.best_total = None
        batch.status = QuoteBatch.STATUS_FAILED
    batch.cache_expires_at = timezone.now() + timedelta(seconds=QUOTE_CACHE_TTL_SECONDS)
    batch.save(update_fields=["best_provider", "best_total", "status", "cache_expires_at", "updated_at"])
    cache.set(_quote_cache_key(batch.deal_id), batch.id, timeout=QUOTE_CACHE_TTL_SECONDS)


def _is_batch_fresh(batch: QuoteBatch | None) -> bool:
    return bool(
        batch
        and batch.status in {QuoteBatch.STATUS_SUCCESS, QuoteBatch.STATUS_PARTIAL_SUCCESS}
        and batch.cache_expires_at
        and batch.cache_expires_at > timezone.now()
    )


def get_best_quotes(
    deal_id: int,
    *,
    force_refresh: bool = False,
    triggered_by_id: int | None = None,
) -> dict[str, Any]:
    latest_batch = get_latest_quote_batch(deal_id)
    if latest_batch and latest_batch.status == QuoteBatch.STATUS_PROCESSING and not force_refresh:
        return _serialize_batch(latest_batch)
    if _is_batch_fresh(latest_batch) and not force_refresh:
        return _serialize_batch(latest_batch)

    deal = Deal.objects.select_related("lead", "lead__responsible").get(id=deal_id)
    providers = list(get_active_provider_configs())

    if not providers:
        batch = _create_batch(deal, triggered_by_id)
        batch.status = QuoteBatch.STATUS_FAILED
        batch.save(update_fields=["status", "updated_at"])
        return _serialize_batch(batch)

    payload = build_deal_quote_payload(deal)
    batch = _create_batch(deal, triggered_by_id)

    quotes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    max_workers = min(max(len(providers), 1), 8)

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"quote-batch-{deal.id}") as executor:
        futures = [
            executor.submit(
                _fetch_provider_quote,
                deal=deal,
                provider=provider,
                payload=payload,
            )
            for provider in providers
        ]
        for future in as_completed(futures):
            quote, failure = future.result()
            if quote:
                quotes.append(
                    _persist_success(
                        batch=batch,
                        deal=deal,
                        provider=quote["provider"],
                        payload=payload,
                        normalized_quote=quote["quote"],
                    )
                )
            if failure:
                failures.append(
                    _persist_failure(
                        batch=batch,
                        deal=deal,
                        provider=failure["provider"],
                        payload=payload,
                        exc=failure["error"],
                    )
                )

    _rank_results(batch)
    serialized = _serialize_batch(batch)
    serialized["requested_provider_count"] = len(providers)
    serialized["successful_provider_count"] = len(quotes)
    serialized["failures"] = failures
    return serialized


def list_quote_batches() -> list[QuoteBatch]:
    return list(
        QuoteBatch.objects.select_related("deal", "lead", "best_provider")
        .annotate(result_count=Count("results"))
        .order_by("-requested_at", "-id")
    )
