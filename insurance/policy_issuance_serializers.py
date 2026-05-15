from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from deals.models import Deal
from .models import PolicyIssuance, QuoteBatch, QuoteResult


def _to_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


_HTTP_URL_START = re.compile(r"^https?://", re.I)


def _extract_payment_url_from_nested(raw: object, depth: int = 0) -> str:
    """Best-effort payment URL from nested JSON (e.g. DIC choose-scheme body)."""
    if raw is None or depth > 14:
        return ""
    if isinstance(raw, str):
        t = raw.strip()
        if _HTTP_URL_START.match(t):
            return t
        if t.startswith("{") or t.startswith("["):
            try:
                parsed = json.loads(t)
                return _extract_payment_url_from_nested(parsed, depth + 1)
            except (json.JSONDecodeError, TypeError, ValueError):
                return ""
        return ""
    if isinstance(raw, (int, float, bool)):
        return ""
    if isinstance(raw, list):
        for item in raw:
            got = _extract_payment_url_from_nested(item, depth + 1)
            if got:
                return got
        return ""
    if isinstance(raw, dict):
        priority = (
            "paymentUrl",
            "payment_url",
            "payUrl",
            "pay_url",
            "paymentLink",
            "payment_link",
            "redirectUrl",
            "redirect_url",
        )
        for k in priority:
            if k in raw:
                got = _extract_payment_url_from_nested(raw[k], depth + 1)
                if got:
                    return got
        for k, v in raw.items():
            lk = str(k).lower()
            if ("payment" in lk and "url" in lk) or "redirect" in lk:
                got = _extract_payment_url_from_nested(v, depth + 1)
                if got:
                    return got
        for v in raw.values():
            got = _extract_payment_url_from_nested(v, depth + 1)
            if got:
                return got
    return ""


def agent_debug_policy_line(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
) -> None:
    """NDJSON debug line for Cursor debug mode (no secrets)."""
    import json as _json
    import time as _time

    try:
        line = (
            _json.dumps(
                {
                    "sessionId": "fe6ad5",
                    "hypothesisId": hypothesis_id,
                    "location": location,
                    "message": message,
                    "data": data,
                    "timestamp": int(_time.time() * 1000),
                },
                default=str,
            )
            + "\n"
        )
        with open(
            "/Users/adhi/Documents/freelance/Promise-insurance/codes/.cursor/debug-fe6ad5.log",
            "a",
            encoding="utf-8",
        ) as _f:
            _f.write(line)
    except Exception:
        pass


def _resolved_payment_url_for_create(payload: dict, quote_result: QuoteResult | None = None) -> str:
    direct = (payload.get("payment_url") or "").strip()
    if direct:
        return direct[:2048]
    nested = _extract_payment_url_from_nested(payload.get("choose_scheme_response"))
    if nested:
        return nested[:2048]
    if quote_result is not None and quote_result.raw_response is not None:
        from_qr = _extract_payment_url_from_nested(quote_result.raw_response)
        if from_qr:
            return from_qr[:2048]
    return ""


class PolicyIssuanceCreateSerializer(serializers.Serializer):
    """Body from client checkout confirm (mirrors PolicyCheckoutState core fields)."""

    batch_id = serializers.IntegerField(required=True, min_value=1)
    quote_result_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    provider = serializers.CharField(required=False, allow_blank=True, max_length=50)
    provider_display_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    plan_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=10, default="AED")

    base_premium = serializers.FloatField(required=False, default=0)
    grand_total = serializers.FloatField(required=False, default=0)
    addon_line_items = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    dic_request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    dic_scheme_payload = serializers.JSONField(required=False, allow_null=True)
    choose_scheme_response = serializers.JSONField(required=False, allow_null=True)
    quotation_no = serializers.CharField(required=False, allow_blank=True, max_length=128)
    payment_url = serializers.CharField(required=False, allow_blank=True, max_length=2048)

    payment_status = serializers.CharField(required=False, allow_blank=True, max_length=20)
    issuance_status = serializers.CharField(required=False, allow_blank=True, max_length=40)

    customer_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    customer_phone = serializers.CharField(required=False, allow_blank=True, max_length=50)
    customer_email = serializers.CharField(required=False, allow_blank=True, max_length=254)

    checkout_submit_skipped = serializers.BooleanField(required=False, default=False)
    choose_scheme_error = serializers.CharField(required=False, allow_blank=True, default="")


class PolicyIssuanceListSerializer(serializers.ModelSerializer):
    """Queue row + customer snapshot for policy issuance UI."""

    payment_url = serializers.SerializerMethodField()
    policy_id_display = serializers.SerializerMethodField()
    insurer = serializers.CharField(source="provider_display_name", read_only=True)
    premium = serializers.SerializerMethodField()
    issue_date = serializers.SerializerMethodField()
    payment_status_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    customer = serializers.CharField(source="customer_name", read_only=True)
    product_type = serializers.CharField(read_only=True)
    method = serializers.SerializerMethodField()
    quote_batch_id = serializers.IntegerField(read_only=True, allow_null=True)
    quote_result_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = PolicyIssuance
        fields = [
            "id",
            "policy_id_display",
            "customer",
            "customer_phone",
            "customer_email",
            "product_type",
            "insurer",
            "premium",
            "issue_date",
            "payment_status_label",
            "status_label",
            "plan_name",
            "quotation_no",
            "addon_line_items",
            "provider_code",
            "dic_request_id",
            "dic_scheme_payload",
            "choose_scheme_response",
            "payment_status",
            "issuance_status",
            "grand_total",
            "currency",
            "method",
            "quote_batch_id",
            "quote_result_id",
            "payment_url",
            "created_at",
            "updated_at",
        ]

    def get_policy_id_display(self, obj: PolicyIssuance) -> str:
        if obj.quotation_no:
            return obj.quotation_no
        ref = getattr(obj.quote_batch, "reference_no", None) or ""
        if ref:
            return f"{ref}-{obj.pk}"
        return f"ISS-{obj.pk:05d}"

    def get_issue_date(self, obj: PolicyIssuance) -> str:
        """created_at is DateTimeField; API exposes calendar date only."""
        if obj.created_at is None:
            return ""
        return obj.created_at.date().isoformat()

    def get_method(self, obj: PolicyIssuance) -> str:
        return "API"

    def get_premium(self, obj: PolicyIssuance) -> str:
        cur = obj.currency or "AED"
        total = obj.grand_total or Decimal("0")
        # Match frontend-style grouping (no decimals if integer-like)
        if total == total.to_integral():
            amount = f"{int(total):,}"
        else:
            amount = f"{total:,.2f}"
        return f"{cur} {amount}"

    def get_payment_status_label(self, obj: PolicyIssuance) -> str:
        mapping = {
            PolicyIssuance.PAYMENT_PENDING: "Pending",
            PolicyIssuance.PAYMENT_PAID: "Paid",
            PolicyIssuance.PAYMENT_EXPIRED: "Expired",
        }
        return mapping.get(obj.payment_status, obj.payment_status.title())

    def get_status_label(self, obj: PolicyIssuance) -> str:
        mapping = {
            PolicyIssuance.ISSUANCE_PENDING: "Pending",
            PolicyIssuance.ISSUANCE_PAYMENT_LINK_REQUESTED: "Payment link requested",
            PolicyIssuance.ISSUANCE_PAYMENT_LINK_RECEIVED: "Payment link received",
            PolicyIssuance.ISSUANCE_ISSUED: "Issued",
            PolicyIssuance.ISSUANCE_ACTIVE: "Active",
        }
        return mapping.get(obj.issuance_status, obj.issuance_status.replace("_", " ").title())

    def get_payment_url(self, obj: PolicyIssuance) -> str:
        # #region agent log
        direct = (obj.payment_url or "").strip()
        nested = "" if direct else _extract_payment_url_from_nested(obj.choose_scheme_response)
        from_quote = ""
        if not direct and not nested:
            qr = getattr(obj, "quote_result", None)
            if qr is not None and qr.raw_response is not None:
                from_quote = _extract_payment_url_from_nested(qr.raw_response)
        result = direct if direct else (nested if nested else from_quote)
        crs = obj.choose_scheme_response
        crs_t = type(crs).__name__
        crs_k = len(crs) if isinstance(crs, dict) else 0
        agent_debug_policy_line(
            "H1",
            "policy_issuance_serializers.get_payment_url",
            "computed",
            {
                "pk": obj.pk,
                "issuance_status": obj.issuance_status,
                "directLen": len(direct),
                "nestedLen": len(nested),
                "fromQuoteLen": len(from_quote),
                "crsType": crs_t,
                "crsDictLen": crs_k,
            },
        )
        # #endregion
        return result


def deal_product_label(deal: Deal) -> str:
    try:
        return deal.get_sub_type_display() or deal.get_insurance_type_display() or deal.insurance_type or "Motor"
    except Exception:
        return deal.insurance_type or "Motor"


def create_policy_issuance_from_payload(*, payload: dict, batch: QuoteBatch, quote_result: QuoteResult | None) -> PolicyIssuance:
    deal = batch.deal
    lead = batch.lead

    payload_name = (payload.get("customer_name") or "").strip()
    payload_phone = (payload.get("customer_phone") or "").strip()
    payload_email = (payload.get("customer_email") or "").strip()

    customer_name = payload_name
    customer_phone = payload_phone
    customer_email = payload_email
    if lead:
        if not customer_name:
            customer_name = lead.name or ""
        if not customer_phone:
            customer_phone = (lead.mobile_number or lead.phone_number or "") or ""
        if not customer_email:
            customer_email = lead.email or ""

    product_type = deal_product_label(deal)

    return PolicyIssuance.objects.create(
        deal=deal,
        quote_batch=batch,
        quote_result=quote_result,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        product_type=product_type,
        provider_code=(payload.get("provider") or "")[:50],
        provider_display_name=payload.get("provider_display_name") or "",
        plan_name=payload.get("plan_name") or "",
        currency=(payload.get("currency") or "AED")[:10],
        base_premium=_to_decimal(payload.get("base_premium")),
        grand_total=_to_decimal(payload.get("grand_total")),
        addon_line_items=payload.get("addon_line_items") if isinstance(payload.get("addon_line_items"), list) else [],
        dic_request_id=(payload.get("dic_request_id") or "")[:64],
        dic_scheme_payload=payload.get("dic_scheme_payload"),
        choose_scheme_response=payload.get("choose_scheme_response"),
        quotation_no=(payload.get("quotation_no") or "")[:128],
        payment_url=_resolved_payment_url_for_create(payload, quote_result),
        payment_status=_normalize_payment_status(payload.get("payment_status")),
        issuance_status=_normalize_issuance_status(payload.get("issuance_status")),
        checkout_submit_skipped=bool(payload.get("checkout_submit_skipped")),
        choose_scheme_error=payload.get("choose_scheme_error") or "",
    )


def _normalize_payment_status(raw: object) -> str:
    if not raw:
        return PolicyIssuance.PAYMENT_PENDING
    s = str(raw).strip().lower()
    if s == "paid":
        return PolicyIssuance.PAYMENT_PAID
    if s == "expired":
        return PolicyIssuance.PAYMENT_EXPIRED
    return PolicyIssuance.PAYMENT_PENDING


def _normalize_issuance_status(raw: object) -> str:
    if not raw:
        return PolicyIssuance.ISSUANCE_PENDING
    s = str(raw).strip().lower().replace("-", "_")
    if s == "payment_link_recieved":  # common misspelling
        s = "payment_link_received"
    allowed = {
        "pending": PolicyIssuance.ISSUANCE_PENDING,
        "payment_link_requested": PolicyIssuance.ISSUANCE_PAYMENT_LINK_REQUESTED,
        "payment_link_received": PolicyIssuance.ISSUANCE_PAYMENT_LINK_RECEIVED,
        "issued": PolicyIssuance.ISSUANCE_ISSUED,
        "active": PolicyIssuance.ISSUANCE_ACTIVE,
    }
    return allowed.get(s, PolicyIssuance.ISSUANCE_PENDING)
