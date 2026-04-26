import logging
import os
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import requests
from django.core.cache import cache

from .exceptions import (
    ProviderAuthenticationError,
    ProviderCircuitOpenError,
    ProviderConfigurationError,
    ProviderRequestError,
)
from .schemas import NormalizedQuote

logger = logging.getLogger(__name__)


class BaseInsuranceProvider(ABC):
    circuit_failure_limit = 3
    circuit_open_seconds = 300

    def __init__(self, provider_config):
        self.provider_config = provider_config
        self.session = requests.Session()
        self.timeout = provider_config.timeout or 30

    @property
    def provider_code(self) -> str:
        return self.provider_config.code.upper()

    def _env_name(self, key: str) -> str:
        return f"INSURANCE_PROVIDER_{self.provider_code}_{key}"

    def resolve_config_value(self, field_name: str, default: Any = "") -> Any:
        value = getattr(self.provider_config, field_name, None)
        if value not in (None, "", {}):
            return value
        return os.environ.get(self._env_name(field_name.upper()), default)

    def get_base_url(self) -> str:
        base_url = self.resolve_config_value("base_url", "")
        if not base_url:
            raise ProviderConfigurationError(
                f"{self.provider_code} is missing base_url configuration."
            )
        return str(base_url).rstrip("/")

    def get_extra_config(self) -> dict[str, Any]:
        config = self.provider_config.extra_config or {}
        return config if isinstance(config, dict) else {}

    def get_auth_headers(self) -> dict[str, str]:
        api_key = self.resolve_config_value("api_key", "")
        token = self.authenticate()
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def authenticate(self) -> str | None:
        extra_config = self.get_extra_config()
        if "mock_token" in extra_config:
            return str(extra_config["mock_token"])

        auth_endpoint = extra_config.get("auth_endpoint")
        if not auth_endpoint:
            return None

        username = self.resolve_config_value("username", "")
        password = self.resolve_config_value("password", "")
        if not username or not password:
            raise ProviderAuthenticationError(
                f"{self.provider_code} requires username and password for authentication."
            )

        response = self._request(
            method="POST",
            path=auth_endpoint,
            json_payload={"username": username, "password": password},
            authenticated=False,
        )
        token = response.get("access_token") or response.get("token")
        if not token:
            raise ProviderAuthenticationError(
                f"{self.provider_code} did not return an access token."
            )
        return str(token)

    def _circuit_key(self) -> str:
        return f"insurance-provider-circuit:{self.provider_code}"

    def _check_circuit(self) -> None:
        state = cache.get(self._circuit_key())
        if state and state.get("open_until", 0) > time.time():
            raise ProviderCircuitOpenError(
                f"{self.provider_code} circuit breaker is open."
            )

    def _record_failure(self) -> None:
        key = self._circuit_key()
        state = cache.get(key, {"count": 0, "open_until": 0})
        count = int(state.get("count", 0)) + 1
        next_state = {"count": count, "open_until": 0}
        if count >= self.circuit_failure_limit:
            next_state["open_until"] = time.time() + self.circuit_open_seconds
        cache.set(key, next_state, timeout=self.circuit_open_seconds)

    def _record_success(self) -> None:
        cache.delete(self._circuit_key())

    def _request(
        self,
        *,
        method: str,
        path: str,
        json_payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        self._check_circuit()

        url = path if path.startswith("http") else f"{self.get_base_url()}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}
        if authenticated:
            headers.update(self.get_auth_headers())
        if extra_headers:
            headers.update(extra_headers)

        last_error: Exception | None = None
        retries = int(self.get_extra_config().get("retry_count", 2))
        backoff_seconds = float(self.get_extra_config().get("retry_backoff_seconds", 0.5))

        for attempt in range(retries + 1):
            started = time.perf_counter()
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=json_payload,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                self._record_success()
                payload = response.json() if response.content else {}
                if not isinstance(payload, dict):
                    raise ProviderRequestError(
                        f"{self.provider_code} returned non-object JSON payload."
                    )
                logger.info(
                    "Provider %s request succeeded in %sms",
                    self.provider_code,
                    int((time.perf_counter() - started) * 1000),
                )
                return payload
            except Exception as exc:  # requests + json parsing
                last_error = exc
                if attempt < retries:
                    time.sleep(backoff_seconds * (attempt + 1))
                    continue
                self._record_failure()
                logger.warning(
                    "Provider %s request failed after %s attempts: %s",
                    self.provider_code,
                    retries + 1,
                    exc,
                )

        raise ProviderRequestError(str(last_error or "Unknown provider request error"))

    def build_quote_from_mapping(
        self,
        payload: dict[str, Any],
        *,
        response_time_ms: int,
    ) -> NormalizedQuote:
        return NormalizedQuote(
            provider=self.provider_config.code,
            premium=Decimal(str(payload.get("premium", 0))),
            vat=Decimal(str(payload.get("vat", 0))),
            total=Decimal(str(payload.get("total", payload.get("premium", 0)))),
            currency=str(payload.get("currency", "AED")),
            plan_name=str(payload.get("plan_name", "Standard Plan")),
            response_time_ms=response_time_ms,
            raw_response=payload,
        )

    @abstractmethod
    def get_quote(self, payload: dict[str, Any]) -> NormalizedQuote:
        raise NotImplementedError

    @abstractmethod
    def issue_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def renew_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        raise NotImplementedError
