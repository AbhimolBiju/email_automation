import time
from typing import Any

from .base import BaseInsuranceProvider


class QICProvider(BaseInsuranceProvider):
    def get_quote(self, payload: dict[str, Any]):
        started = time.perf_counter()
        mock_payload = self.get_extra_config().get("mock_quote_response")
        if isinstance(mock_payload, dict):
            return self.build_quote_from_mapping(
                mock_payload,
                response_time_ms=int((time.perf_counter() - started) * 1000),
            )

        endpoint = self.get_extra_config().get("quote_endpoint", "/v1/quotes")
        response = self._request(method="POST", path=endpoint, json_payload=payload)
        return self.build_quote_from_mapping(
            {
                "premium": response.get("premium") or response.get("premium_value"),
                "vat": response.get("vat") or response.get("vat_value", 0),
                "total": response.get("total") or response.get("total_premium"),
                "currency": response.get("currency", "AED"),
                "plan_name": response.get("plan_name", "QIC Plan"),
                **response,
            },
            response_time_ms=int((time.perf_counter() - started) * 1000),
        )

    def issue_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = self.get_extra_config().get("issue_policy_endpoint", "/v1/policies/issue")
        return self._request(method="POST", path=endpoint, json_payload=payload)

    def renew_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = self.get_extra_config().get("renew_policy_endpoint", "/v1/policies/renew")
        return self._request(method="POST", path=endpoint, json_payload=payload)

    def health_check(self) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_health_check")
        if isinstance(mock_payload, dict):
            return mock_payload
        endpoint = self.get_extra_config().get("health_endpoint", "/health")
        return self._request(method="GET", path=endpoint, authenticated=False)
