from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view

from api.responses import error_response, success_response

from .models import PolicyIssuance, QuoteBatch, QuoteResult
from .policy_issuance_serializers import (
    PolicyIssuanceCreateSerializer,
    PolicyIssuanceListSerializer,
    agent_debug_policy_line,
    create_policy_issuance_from_payload,
    _extract_payment_url_from_nested,
    _normalize_issuance_status,
    _normalize_payment_status,
)


def _safe_client_payment_url(raw: object) -> str:
    """Accept only http(s) URLs from PATCH body; max 2048 chars."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if len(s) > 2048:
        s = s[:2048]
    low = s.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        return ""
    return s


@api_view(["GET", "POST"])
def policy_issuances(request):
    if request.method == "GET":
        qs = (
            PolicyIssuance.objects.select_related("deal", "quote_batch", "quote_result")
            .order_by("-created_at")[:500]
        )
        serializer = PolicyIssuanceListSerializer(qs, many=True)
        return success_response(
            message="Policy issuances fetched successfully",
            data=serializer.data,
            status_code=status.HTTP_200_OK,
        )

    body = PolicyIssuanceCreateSerializer(data=request.data)
    if not body.is_valid():
        return error_response(
            message="Validation failed",
            code=status.HTTP_400_BAD_REQUEST,
            errors=body.errors,
        )

    validated = body.validated_data
    batch_id = validated["batch_id"]
    batch = (
        QuoteBatch.objects.select_related("deal", "lead")
        .filter(id=batch_id)
        .first()
    )
    if batch is None:
        return error_response(
            message="Quote batch not found",
            code=status.HTTP_404_NOT_FOUND,
            errors={"batch_id": [str(batch_id)]},
        )

    quote_result = None
    qrid = validated.get("quote_result_id")
    if qrid is not None:
        quote_result = QuoteResult.objects.filter(id=qrid, batch=batch).first()
        if quote_result is None:
            return error_response(
                message="Quote result not found for this batch",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"quote_result_id": [str(qrid)]},
            )

    payload = {k: v for k, v in validated.items() if k not in ("batch_id", "quote_result_id")}
    obj = create_policy_issuance_from_payload(
        payload=payload,
        batch=batch,
        quote_result=quote_result,
    )
    out = PolicyIssuanceListSerializer(obj)
    return success_response(
        message="Policy issuance recorded",
        data=out.data,
        status_code=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
def policy_issuance_detail(request, pk: int):
    """Fetch one issuance or update workflow status (e.g. issued → active)."""
    qs = PolicyIssuance.objects.select_related("deal", "quote_batch", "quote_result")
    obj = qs.filter(pk=pk).first()
    if obj is None:
        return error_response(
            message="Policy issuance not found",
            code=status.HTTP_404_NOT_FOUND,
            errors={"id": [str(pk)]},
        )

    if request.method == "GET":
        out = PolicyIssuanceListSerializer(obj)
        return success_response(
            message="Policy issuance fetched successfully",
            data=out.data,
            status_code=status.HTTP_200_OK,
        )

    raw_status = request.data.get("issuance_status")
    raw_payment = request.data.get("payment_status")

    has_status = raw_status is not None and str(raw_status).strip() != ""
    has_payment = raw_payment is not None and str(raw_payment).strip() != ""

    if not has_status and not has_payment:
        return error_response(
            message="Provide issuance_status and/or payment_status",
            code=status.HTTP_400_BAD_REQUEST,
            errors={
                "issuance_status": ["At least one of issuance_status or payment_status is required."],
            },
        )

    client_pay = _safe_client_payment_url(request.data.get("payment_url"))

    if has_payment:
        obj.payment_status = _normalize_payment_status(raw_payment)
    if has_status:
        obj.issuance_status = _normalize_issuance_status(raw_status)
    obj.save()
    # #region agent log
    url_len_after_main = len((obj.payment_url or "").strip())
    # #endregion
    if not (obj.payment_url or "").strip():
        extracted = _extract_payment_url_from_nested(obj.choose_scheme_response)
        if not extracted:
            qr = getattr(obj, "quote_result", None)
            if qr is not None and qr.raw_response is not None:
                extracted = _extract_payment_url_from_nested(qr.raw_response)
        if not extracted and client_pay:
            extracted = client_pay
        if extracted:
            obj.payment_url = extracted[:2048]
            obj.save(update_fields=["payment_url"])
    # #region agent log
    agent_debug_policy_line(
        "H1",
        "policy_issuance_views.policy_issuance_detail.patch",
        "after_save_backfill",
        {
            "pk": obj.pk,
            "urlLenAfterMainSave": url_len_after_main,
            "urlLenFinal": len((obj.payment_url or "").strip()),
            "had_status_patch": has_status,
        },
    )
    # #endregion
    out = PolicyIssuanceListSerializer(obj)
    return success_response(
        message="Policy issuance updated",
        data=out.data,
        status_code=status.HTTP_200_OK,
    )
