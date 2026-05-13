from __future__ import annotations

from typing import Any

from rest_framework import serializers


class NIALoosePayloadSerializer(serializers.Serializer):
    """
    Accept arbitrary JSON object payload and pass it through unchanged.
    """

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise serializers.ValidationError({"detail": ["Expected a JSON object."]})
        return data