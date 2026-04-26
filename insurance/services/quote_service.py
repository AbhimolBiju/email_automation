from __future__ import annotations

import logging
import mimetypes
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Any

from deals.models import Deal
from insurance.models import InsuranceProvider, QuoteRequestLog, QuoteResult
from insurance.providers import build_provider
from insurance.providers.exceptions import InsuranceProviderError

from .provider_service import get_active_provider_configs

logger = logging.getLogger(__name__)


def build_deal_document_payloads(deal: Deal) -> list[dict[str, Any]]:
    try:
        from documents.models import Document
    except Exception:  # pragma: no cover - app import safety
        return []

    documents = (
        Document.objects.filter(motor_deal=deal)
        .order_by("document_type", "-uploaded_at", "-id")
    )
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
                "type": (
                    mimetypes.guess_extension(document.file_type or "") or ".png"
                ).lstrip("."),
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


def _persist_success(
    *,
    deal: Deal,
    provider: InsuranceProvider,
    payload: dict[str, Any],
    normalized_quote,
) -> dict[str, Any]:
    request_log = QuoteRequestLog.objects.create(
        deal=deal,
        provider=provider,
        request_payload=payload,
        response_payload=normalized_quote.raw_response,
        status=QuoteRequestLog.STATUS_SUCCESS,
        latency_ms=normalized_quote.response_time_ms,
        error_message="",
    )

    QuoteResult.objects.create(
        deal=deal,
        provider=provider,
        request_log=request_log,
        premium=normalized_quote.premium,
        vat=normalized_quote.vat,
        total=normalized_quote.total,
        currency=normalized_quote.currency,
        plan_name=normalized_quote.plan_name,
        response_time_ms=normalized_quote.response_time_ms,
        raw_response=normalized_quote.raw_response,
    )
    return normalized_quote.as_dict()


def _persist_failure(
    *,
    deal: Deal,
    provider: InsuranceProvider,
    payload: dict[str, Any],
    provider_code: str,
    exc: Exception,
) -> dict[str, Any]:
    QuoteRequestLog.objects.create(
        deal=deal,
        provider=provider,
        request_payload=payload,
        response_payload={},
        status=QuoteRequestLog.STATUS_FAILED,
        error_message=str(exc),
    )
    return {"provider": provider_code, "error": str(exc)}


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
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception(
            "Unexpected quote fetch error for deal %s with provider %s",
            deal.id,
            provider.code,
        )
        return None, {"provider": provider, "error": exc}


def get_best_quotes(deal_id: int) -> dict[str, Any]:
    deal = (
        Deal.objects.select_related("lead", "lead__responsible")
        .get(id=deal_id)
    )
    providers = list(get_active_provider_configs())
    payload = build_deal_quote_payload(deal)

    if not providers:
        return {
            "deal_id": deal.id,
            "quotes": [],
            "failures": [],
            "requested_provider_count": 0,
            "successful_provider_count": 0,
        }

    quotes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    max_workers = min(max(len(providers), 1), 8)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
                        deal=deal,
                        provider=quote["provider"],
                        payload=payload,
                        normalized_quote=quote["quote"],
                    )
                )
            if failure:
                failures.append(
                    _persist_failure(
                        deal=deal,
                        provider=failure["provider"],
                        payload=payload,
                        provider_code=failure["provider"].code,
                        exc=failure["error"],
                    )
                )

    quotes.sort(key=lambda item: (Decimal(str(item["total"])), item["provider"]))

    return {
        "deal_id": deal.id,
        "quotes": quotes,
        "failures": failures,
        "requested_provider_count": len(providers),
        "successful_provider_count": len(quotes),
    }
