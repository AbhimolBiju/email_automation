from __future__ import annotations

import logging
import mimetypes
import json
import decimal
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
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


def _make_json_safe(obj):
    """Recursively convert non-JSON-serializable types (Decimal etc.) to safe equivalents."""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(i) for i in obj]
    return obj


def _quote_cache_key(deal_id: int) -> str:
    return QUOTE_BATCH_CACHE_KEY.format(deal_id=deal_id)


def _as_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _extract_sum_insured(deal: Deal) -> int:
    """
    Extract vehicle valuation (sum_insured) from deal for providers that require it (e.g. QIC/NIA).
    Priority:
      - deal.sum_insured (newly added field for Bayanaty valuation or manual entry)
      - Deal attributes if present (vehicle_value)
      - JSON encoded in additional_field (vehicle_value, declared_value, sum_insured)
      - fallback default (10000)
    """
    # First check the dedicated sum_insured field (highest priority)
    for attr in ("sum_insured", "vehicle_value"):
        value = getattr(deal, attr, None)
        if value not in (None, "", 0, "0"):
            try:
                # Handle Decimal from database
                if hasattr(value, '__float__'):
                    numeric = int(float(value))
                else:
                    numeric = int(value)
                if numeric > 0:
                    logger.info("Extracted sum_insured from deal.%s: %d", attr, numeric)
                    return numeric
            except Exception as e:
                logger.warning("Failed to extract %s from deal: %s", attr, e)
                pass

    # Check additional_field JSON (fallback)
    extra = getattr(deal, "additional_field", None)
    if isinstance(extra, str) and extra.strip():
        try:
            parsed = json.loads(extra)
            if isinstance(parsed, dict):
                for key in ("vehicle_value", "declared_value", "sum_insured"):
                    value = parsed.get(key)
                    if value not in (None, "", 0, "0"):
                        numeric = int(float(value))
                        if numeric > 0:
                            logger.info("Extracted sum_insured from additional_field.%s: %d", key, numeric)
                            return numeric
        except Exception as e:
            logger.warning("Failed to parse additional_field JSON: %s", e)
            pass

    logger.warning("No sum_insured found on deal %d; using default 10000", deal.id)
    return 10000


def _derive_first_registration_date(deal: Deal) -> str | None:
    """
    Best-effort `YYYY-MM-DD` for providers that require first registration date.
    Priority:
      - deal.reg_dt
      - fallback to deal.model_year-01-01
    Must not be future dated.
    """
    if deal.reg_dt:
        value = deal.reg_dt
    elif deal.model_year:
        try:
            value = date(int(deal.model_year), 1, 1)
        except Exception:
            value = None
    else:
        value = None

    if not value:
        return None
    if value > date.today():
        return None
    return value.isoformat()


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
    policy_from = timezone.now().date()
    policy_to = policy_from + timedelta(days=365)
    insured_age: int | None = None
    if deal.date_of_birth:
        try:
            insured_age = int((policy_from - deal.date_of_birth).days // 365.25)
        except Exception:
            insured_age = None
    sum_insured = _extract_sum_insured(deal)
    first_registration_date = _derive_first_registration_date(deal)
    return {
        "deal_id": deal.id,
        "stage_id": deal.stage_id,
        "product_type": "motor" if deal.insurance_type else (getattr(lead, "product_type", None) or "unknown"),
        "insurance_type": deal.insurance_type,
        "sub_type": deal.sub_type,
        "policy_from_date": policy_from.isoformat(),
        "policy_to_date": policy_to.isoformat(),
        "insured_age": insured_age or 0,
        "sum_insured": sum_insured,
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
            "registration_year": deal.reg_dt.year if deal.reg_dt else None,
            "first_registration_date": first_registration_date,
            "plate_code": deal.plate_code,
            "plate_source": deal.plate_source,
            "license_number": deal.license_no,
            "license_from_date": deal.license_from_dt.isoformat() if deal.license_from_dt else None,
            "license_to_date": deal.license_to_dt.isoformat() if deal.license_to_dt else None,
            "traffic_transaction_type": deal.traffic_tran_type,
            "is_vehicle_brand_new": deal.is_veh_brand_new,
            "agency_repair": deal.agency_repair,
            "model_year": deal.model_year,
            "year": deal.model_year,
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
            "sum_insured": sum_insured,
        },
        "documents": build_deal_document_payloads(deal),
    }


def _validate_payload_for_provider(provider_code: str, payload: dict[str, Any]) -> None:
    """
    Validate the minimal fields per provider so we fail fast with clear errors,
    but without breaking other providers.
    """
    code = (provider_code or "").upper()
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else {}

    # Baseline (common in most motor quote flows).
    missing: list[str] = []
    if not str(customer.get("emirates_id") or "").strip():
        missing.append("customer.emirates_id")
    if not str(vehicle.get("chassis_number") or "").strip():
        missing.append("vehicle.chassis_number")
    if missing:
        raise InsuranceProviderError(f"{code} missing required fields: {', '.join(missing)}")

    # Provider-specific
    if code == "QIC":
        value = payload.get("sum_insured") or vehicle.get("sum_insured")
        try:
            if float(value or 0) <= 0:
                raise ValueError
        except Exception:
            raise InsuranceProviderError("QIC missing required field: sum_insured (> 0)")
        first_reg = vehicle.get("first_registration_date") or payload.get("first_registration_date")
        if not str(first_reg or "").strip():
            raise InsuranceProviderError("QIC missing required field: first_registration_date (YYYY-MM-DD)")
        try:
            parsed = date.fromisoformat(str(first_reg))
        except Exception:
            raise InsuranceProviderError("QIC invalid first_registration_date format (expected YYYY-MM-DD)")
        if parsed > date.today():
            raise InsuranceProviderError("QIC first_registration_date cannot be a future date")


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
        request_payload=_make_json_safe(payload),
        response_payload=_make_json_safe(normalized_quote.raw_response or {}),
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
        normalized_response=_make_json_safe(normalized_response),
        raw_response=_make_json_safe(normalized_quote.raw_response or {}),
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
        logger.info("Fetching quote for deal %s from provider %s", deal.id, provider.code)
        payload = dict(payload)
        payload["deal_id"] = deal.id
        # Only override sum_insured from deal if it has a real positive value.
        # If deal.sum_insured is missing/zero, keep whatever build_deal_quote_payload()
        # already set (which uses _extract_sum_insured() with a safe 10000 default).
        if deal.sum_insured is not None and float(deal.sum_insured or 0) > 0:
            _si = float(deal.sum_insured)
            payload["sum_insured"] = _si
            if isinstance(payload.get("vehicle"), dict):
                payload["vehicle"] = dict(payload["vehicle"])
                payload["vehicle"]["sum_insured"] = _si
        # else: do NOT touch payload["sum_insured"] — leave the default from
        # build_deal_quote_payload() / _extract_sum_insured() intact

        _validate_payload_for_provider(provider.code, payload)
        provider_instance = build_provider(provider)
        normalized_quote = provider_instance.get_quote(payload)
        try:
            quote_dict = normalized_quote.as_dict(include_raw_response=False)
            corrected_si = quote_dict.get("corrected_sum_insured")
            if provider_instance.__class__.__name__ == "NIAProvider" or corrected_si:
                if corrected_si:
                    Deal.objects.filter(id=deal.id).update(
                        sum_insured=Decimal(str(corrected_si))
                    )
                    logging.getLogger(__name__).info(
                        "[quote_service] Persisted NIA corrected sum_insured=%.2f "
                        "to deal %s",
                        float(corrected_si),
                        deal.id,
                    )
                    print(f"[quote_service] Saved corrected sum_insured={corrected_si} to deal {deal.id}")
        except Exception as e:
            logging.getLogger(__name__).warning(
                "[quote_service] Could not persist corrected sum_insured: %s", e
            )
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
    # Always include a per-provider status block so callers never have to infer
    # "missing provider" vs "provider attempted but failed".
    results_by_provider: dict[str, dict[str, Any]] = {
        str(item.get("provider") or "").upper(): item for item in (serialized.get("results") or []) if isinstance(item, dict)
    }
    provider_statuses: list[dict[str, Any]] = []
    for provider in providers:
        code = provider.code.upper()
        result = results_by_provider.get(code)
        if result:
            provider_statuses.append(
                {
                    "provider": code,
                    "provider_name": result.get("provider_name") or provider.name,
                    "status": str(result.get("status") or "").lower() or "unknown",
                    "result_id": result.get("id"),
                    "error": result.get("error_message") or "",
                }
            )
        else:
            provider_statuses.append(
                {
                    "provider": code,
                    "provider_name": provider.name,
                    "status": "missing",
                    "result_id": None,
                    "error": "Provider did not produce a persisted result.",
                }
            )
    serialized["providers"] = provider_statuses
    return serialized


def refresh_quote_batch(
    batch_id: int,
    *,
    triggered_by_id: int | None = None,
) -> dict[str, Any]:
    """Re-fetch insurer quotes for the deal tied to an existing batch."""
    batch = (
        QuoteBatch.objects.select_related("deal", "lead", "lead__responsible", "best_provider")
        .filter(id=batch_id)
        .first()
    )
    if not batch:
        raise ValueError(f"Quote batch {batch_id} not found")

    return get_best_quotes(
        batch.deal_id,
        force_refresh=True,
        triggered_by_id=triggered_by_id,
    )


def _extract_covers_qic(raw_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract covers from QIC raw_response tariff.schemes[0]."""
    covers = []
    try:
        tariff = raw_response.get("tariff") or {}
        schemes = tariff.get("schemes") or []
        if schemes:
            scheme = schemes[0]
            # Collect all covers: basicCovers + inclusiveCovers + optionalCovers
            for cover_list in [
                scheme.get("basicCovers") or [],
                scheme.get("inclusiveCovers") or [],
                scheme.get("optionalCovers") or [],
            ]:
                for cover in cover_list:
                    if isinstance(cover, dict):
                        covers.append(
                            {
                                "code": cover.get("code", ""),
                                "name": cover.get("name", ""),
                                "premium": float(cover.get("premium", 0) or 0),
                            }
                        )
    except Exception as e:
        logger.warning("Error extracting QIC covers: %s", e)
    return covers


def _extract_covers_dic(raw_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract covers from DIC raw_response selected_scheme.covers."""
    covers = []
    try:
        selected_scheme = raw_response.get("selected_scheme") or {}
        scheme_covers = selected_scheme.get("covers") or {}
        for cover_list in [
            scheme_covers.get("mandatory") or [],
            scheme_covers.get("optional") or [],
        ]:
            for cover in cover_list:
                if isinstance(cover, dict):
                    covers.append(
                        {
                            "code": cover.get("code", ""),
                            "name": cover.get("name", ""),
                            "premium": float(cover.get("premium", 0) or 0),
                        }
                    )
    except Exception as e:
        logger.warning("Error extracting DIC covers: %s", e)
    return covers


def _extract_covers_nia(raw_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract covers from NIA raw_response create_quote.Data.PlanDetails[0].Covers."""
    covers = []
    try:
        create_quote = raw_response.get("create_quote") or {}
        data = create_quote.get("Data") or {}
        plan_details = data.get("PlanDetails") or []
        if plan_details:
            plan = plan_details[0]
            for cover in plan.get("Covers") or []:
                if isinstance(cover, dict):
                    covers.append(
                        {
                            "code": cover.get("Code", ""),
                            "name": cover.get("Description", ""),
                            "premium": float(cover.get("CoverPremFc", 0) or 0),
                        }
                    )
    except Exception as e:
        logger.warning("Error extracting NIA covers: %s", e)
    return covers


def _cover_name_contains(cover_name: str, *patterns: str) -> bool:
    """Case-insensitive substring match: returns True if cover_name contains any pattern."""
    name_lower = str(cover_name or "").lower()
    return any(str(p).lower() in name_lower for p in patterns)


def _extract_benefits(covers: list[dict[str, Any]], plan_name: str = "") -> dict[str, Any]:
    """Extract benefits from covers list based on cover name matching rules."""
    benefits = {
        "loss_or_damage": False,
        "third_party_liability": "",
        "blood_money": "",
        "fire_theft": False,
        "storm_flood": False,
        "natural_perils": False,
        "repairs": "",
        "emergency_medical": False,
        "personal_belongings": False,
        "oman_cover": False,
        "off_road_cover": False,
        "guaranteed_repairs": False,
        "breakdown_recovery": False,
        "ambulance_cover": "",
        "windscreen_damage": False,
    }
    
    for cover in covers:
        if not isinstance(cover, dict):
            continue
        cover_name = cover.get("name", "")
        premium = cover.get("premium", 0)
        
        # loss_or_damage: "loss" AND ("damage" OR "vehicle") in cover name, AND premium > 0
        if _cover_name_contains(cover_name, "loss") and _cover_name_contains(cover_name, "damage", "vehicle") and premium > 0:
            benefits["loss_or_damage"] = True
        
        # third_party_liability: any cover with "third party" in name
        if _cover_name_contains(cover_name, "third party"):
            benefits["third_party_liability"] = "Included"
        
        # natural_perils: "natural" OR "calamity" OR "riot" OR "storm" OR "flood"
        if _cover_name_contains(cover_name, "natural", "calamity", "riot", "storm", "flood"):
            benefits["natural_perils"] = True
        
        # emergency_medical: "medical" OR "ambulance"
        if _cover_name_contains(cover_name, "medical", "ambulance"):
            benefits["emergency_medical"] = True
        
        # personal_belongings: "personal" AND ("effect" OR "belonging")
        if _cover_name_contains(cover_name, "personal") and _cover_name_contains(cover_name, "effect", "belonging"):
            benefits["personal_belongings"] = True
        
        # oman_cover: "oman" OR "orange card"
        if _cover_name_contains(cover_name, "oman", "orange card"):
            benefits["oman_cover"] = True
        
        # off_road_cover: "off road" OR "offroad"
        if _cover_name_contains(cover_name, "off road", "offroad"):
            benefits["off_road_cover"] = True
        
        # breakdown_recovery: "roadside" OR "breakdown" OR "towing"
        if _cover_name_contains(cover_name, "roadside", "breakdown", "towing"):
            benefits["breakdown_recovery"] = True
        
        # windscreen_damage: "windscreen"
        if _cover_name_contains(cover_name, "windscreen"):
            benefits["windscreen_damage"] = True
        
        # guaranteed_repairs: check for "guaranteed" + "repairs"
        if _cover_name_contains(cover_name, "guaranteed") and _cover_name_contains(cover_name, "repairs"):
            benefits["guaranteed_repairs"] = True
        
        # fire_theft: check for "fire" + "theft" or just fire/theft
        if _cover_name_contains(cover_name, "fire", "theft"):
            benefits["fire_theft"] = True
        
        # repairs: Agency/Non-Agency based on plan_name
        if not benefits["repairs"]:
            plan_name_lower = str(plan_name or "").lower()
            if "agency" in plan_name_lower and "non" not in plan_name_lower:
                benefits["repairs"] = "Agency"
            elif "non" in plan_name_lower and "agency" in plan_name_lower:
                benefits["repairs"] = "Non-Agency"
    
    return benefits


def _extract_optional_covers(covers: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract optional covers from covers list."""
    optional = {
        "driver_cover": False,
        "passenger_cover": False,
        "hire_car_benefit": False,
    }
    
    for cover in covers:
        if not isinstance(cover, dict):
            continue
        cover_name = cover.get("name", "")
        
        # driver_cover: "pab" AND "driver" OR "personal accident" AND "driver"
        if (_cover_name_contains(cover_name, "pab") or _cover_name_contains(cover_name, "personal accident")) and _cover_name_contains(cover_name, "driver"):
            optional["driver_cover"] = True
        
        # passenger_cover: "pab" AND "passenger" OR "personal accident" AND "passenger"
        if (_cover_name_contains(cover_name, "pab") or _cover_name_contains(cover_name, "personal accident")) and _cover_name_contains(cover_name, "passenger"):
            optional["passenger_cover"] = True
        
        # hire_car_benefit: "rent" OR "hire car"
        if _cover_name_contains(cover_name, "rent", "hire car"):
            optional["hire_car_benefit"] = True
    
    return optional


def _get_badge(result: QuoteResult) -> str:
    """Determine badge based on result flags."""
    if result.status != QuoteResult.STATUS_SUCCESS:
        return "Error"
    if result.is_best_value:
        return "Best Value"
    if result.is_cheapest:
        return "Cheapest"
    if result.is_recommended:
        return "Recommended"
    return ""


def _extract_buy_now_url(provider_code: str, raw_response: dict[str, Any]) -> str:
    """Extract buy_now_url from raw_response based on provider."""
    try:
        code = (provider_code or "").upper()
        if code == "QIC":
            # For QIC: use selected_premium or tariff quoteNo
            tariff = raw_response.get("tariff") or {}
            schemes = tariff.get("schemes") or []
            if schemes:
                quote_no = schemes[0].get("quoteNo") or raw_response.get("quote_no")
                if quote_no:
                    return f"qic-quote:{quote_no}"
        elif code == "DIC":
            # For DIC: use selected_scheme.paymentUrl
            selected_scheme = raw_response.get("selected_scheme") or {}
            payment_url = selected_scheme.get("paymentUrl")
            if payment_url:
                return str(payment_url)
        # For NIA or others: return empty (manual payment flow)
    except Exception as e:
        logger.warning("Error extracting buy_now_url for %s: %s", provider_code, e)
    return ""


def _extract_vehicle_details(result: QuoteResult, covers: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract vehicle details from raw_response and covers."""
    raw_response = result.raw_response or {}
    details = {
        "excess": "TBA",
        "ancillary_excess": "TBA",
        "vehicle_value": "N/A",
    }
    
    try:
        # Try to extract deductible/excess from raw_response
        for key in ["deductible", "excess", "policy_deductible"]:
            value = raw_response.get(key)
            if value and str(value).strip():
                details["excess"] = str(value)
                break
        
        # Try to extract sum_insured/vehicle_value from raw_response
        for key in ["sum_insured", "vehicle_value", "declared_value"]:
            value = raw_response.get(key)
            if value and str(value).strip():
                details["vehicle_value"] = str(value)
                break
    except Exception as e:
        logger.warning("Error extracting vehicle details: %s", e)
    
    return details


def build_comparison_payload(batch: QuoteBatch) -> dict[str, Any]:
    """
    Build a structured comparison payload from a QuoteBatch.
    
    Returns a dict with:
    - customer: { name, product, created_at }
    - providers: list of provider comparison objects
    - recommended_provider: name of recommended/best provider
    """
    # Ensure we have all related data
    batch = (
        QuoteBatch.objects.select_related("deal", "lead", "best_provider")
        .prefetch_related("results__provider")
        .get(pk=batch.pk)
    )
    
    # Customer info
    customer = {
        "name": batch.lead.name if batch.lead else "",
        "product": (
            batch.deal.get_sub_type_display()
            or batch.deal.get_insurance_type_display()
            or batch.deal.insurance_type
            or "Motor"
        ),
        "created_at": batch.requested_at.isoformat() if batch.requested_at else "",
    }
    
    # Process each quote result
    providers_data = []
    recommended_provider_name = batch.best_provider.name if batch.best_provider else ""
    
    for result in batch.results.all():
        if not result.provider:
            continue
        
        raw_response = result.raw_response or {}
        provider_code = result.provider.code.upper()
        
        # Extract covers based on provider type
        if provider_code == "QIC":
            covers = _extract_covers_qic(raw_response)
        elif provider_code == "DIC":
            covers = _extract_covers_dic(raw_response)
        elif provider_code == "NIA":
            covers = _extract_covers_nia(raw_response)
        else:
            covers = []
        
        # Extract benefits and optional covers
        benefits = _extract_benefits(covers, result.plan_name or "")
        optional_covers = _extract_optional_covers(covers)
        
        # Build provider object
        provider_obj = {
            "provider_name": result.provider.name,
            "logo": (result.provider.extra_config or {}).get("logo_url", "") if isinstance(result.provider.extra_config, dict) else "",
            "plan_name": result.plan_name or "",
            "premium": float(result.premium) if result.premium else 0.0,
            "base_price": float(result.premium - result.vat) if result.premium and result.vat else (float(result.premium) if result.premium else 0.0),
            "vat": float(result.vat) if result.vat else 0.0,
            "currency": result.currency or "AED",
            "badge": _get_badge(result),
            "buy_now_url": _extract_buy_now_url(result.provider.code, raw_response),
            "vehicle_details": _extract_vehicle_details(result, covers),
            "benefits": benefits,
            "optional_covers": optional_covers,
            "error": result.error_message if result.status != QuoteResult.STATUS_SUCCESS else "",
        }
        providers_data.append(provider_obj)
        
        # Update recommended_provider_name if this is the recommended one
        if result.is_recommended and not recommended_provider_name:
            recommended_provider_name = result.provider.name
    
    return {
        "customer": customer,
        "providers": providers_data,
        "recommended_provider": recommended_provider_name,
    }


def list_quote_batches() -> list[QuoteBatch]:
    return list(
        QuoteBatch.objects.select_related("deal", "lead", "best_provider")
        .annotate(result_count=Count("results"))
        .order_by("-requested_at", "-id")
    )
