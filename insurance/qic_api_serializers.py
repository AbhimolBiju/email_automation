from __future__ import annotations

from typing import Any

from rest_framework import serializers


class QICLoosePayloadSerializer(serializers.Serializer):
    """
    Accept arbitrary JSON object payload and pass it through unchanged.
    """

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise serializers.ValidationError({"detail": ["Expected a JSON object."]})
        return data


class QICDownloadQuoteDocumentSerializer(serializers.Serializer):
    quote_no = serializers.CharField(required=True, allow_blank=False)
    doc_type = serializers.CharField(required=False, allow_blank=False, default="Quotation")


class QICVinRequestSerializer(serializers.Serializer):
    vin = serializers.CharField(required=True, allow_blank=False)


class VehicleLookupRequestSerializer(serializers.Serializer):
    Vin = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)

    def validate_Vin(self, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("VIN is required.")
        return normalized