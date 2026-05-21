import logging
import os
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import requests
from requests import HTTPError
from django.core.cache import cache

from .exceptions import (
    ProviderAuthenticationError,
    ProviderCircuitOpenError,
    ProviderConfigurationError,
    ProviderRequestError,
)
from .schemas import NormalizedQuote

logger = logging.getLogger(__name__)

_REDACT_KEYS = {
    "authorization",
    "x-api-key",
    "api_key",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "emirates_id",
    "national_id",
    "civil_id",
    "mobile_number",
    "phone_number",
    "email",
    "emailAddress",
}


def _redact(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if not text:
        return value
    if len(text) <= 6:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def _redact_payload(obj: Any) -> Any:
    if isinstance(obj, dict):
        sanitized: dict[str, Any] = {}
        for key, value in obj.items():
            key_text = str(key)
            if key_text.strip().lower() in _REDACT_KEYS:
                sanitized[key_text] = _redact(value)
            else:
                sanitized[key_text] = _redact_payload(value)
        return sanitized
    if isinstance(obj, list):
        return [_redact_payload(item) for item in obj[:50]]
    return obj


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
            is_auth_request=True,
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
        is_auth_request: bool = False,
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
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Provider %s request %s %s (attempt %s/%s) headers=%s params=%s json=%s",
                        self.provider_code,
                        method,
                        url,
                        attempt + 1,
                        retries + 1,
                        _redact_payload(headers),
                        _redact_payload(params),
                        _redact_payload(json_payload),
                    )
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
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Provider %s response %s %s in %sms payload=%s",
                        self.provider_code,
                        method,
                        url,
                        int((time.perf_counter() - started) * 1000),
                        _redact_payload(payload),
                    )
                logger.info(
                    "Provider %s request succeeded in %sms",
                    self.provider_code,
                    int((time.perf_counter() - started) * 1000),
                )
                return payload
            except HTTPError as exc:
                # Don't retry auth / client-side validation errors.
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code in (401, 403):
                    self._record_failure()
                    body = ""
                    json_body: dict[str, Any] | None = None
                    try:
                        body = (exc.response.text or "")[:2000] if exc.response is not None else ""
                    except Exception:
                        body = ""
                    try:
                        json_body = exc.response.json() if exc.response is not None and exc.response.content else None
                    except Exception:
                        json_body = None
                    logger.warning(
                        "Provider %s request failed with HTTP %s (no retry). body=%s",
                        self.provider_code,
                        status_code,
                        body,
                    )
                    print(f"{self.provider_code} response:", body)

                    # 401 is always auth.
                    if status_code == 401:
                        raise ProviderAuthenticationError(
                            f"{self.provider_code} unauthorized (HTTP 401). {body}".strip()
                        )

                    # Some providers (e.g. QIC) return business-rule errors using HTTP 403.
                    # If we can parse an errMessage, treat it as a request error instead of auth.
                    if isinstance(json_body, dict):
                        err_message = json_body.get("errMessage") or json_body.get("message")
                        if err_message:
                            raise ProviderRequestError(str(err_message))

                    raise ProviderAuthenticationError(
                        f"{self.provider_code} forbidden (HTTP 403). {body}".strip()
                    )

                # Bug 3 fix: Handle 500 on auth endpoint with skip_on_auth_failure flag
                if (status_code == 500 and is_auth_request and 
                    self.get_extra_config().get("skip_on_auth_failure", False)):
                    self._record_failure()
                    body = ""
                    try:
                        body = (exc.response.text or "")[:2000] if exc.response is not None else ""
                    except Exception:
                        body = ""
                    logger.warning(
                        "Provider %s auth endpoint returned HTTP 500 and skip_on_auth_failure is enabled; "
                        "immediately opening circuit breaker. body=%s",
                        self.provider_code,
                        body,
                    )
                    raise ProviderCircuitOpenError(
                        f"{self.provider_code} auth endpoint returned HTTP 500; circuit breaker opened. {body}".strip()
                    )

                # For other 4xx errors, don't retry unless explicitly allowed (429/408).
                if status_code and status_code < 500 and status_code not in (408, 429):
                    self._record_failure()
                    body = ""
                    try:
                        body = (exc.response.text or "")[:2000] if exc.response is not None else ""
                    except Exception:
                        body = ""
                    logger.warning(
                        "Provider %s request failed with HTTP %s (no retry). body=%s",
                        self.provider_code,
                        status_code,
                        body,
                    )
                    print(f"{self.provider_code} response:", body)
                    raise ProviderRequestError(
                        f"{self.provider_code} request failed (HTTP {status_code}). {body}".strip()
                    )

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
            status=str(payload.get("status", "SUCCESS")).upper(),
            benefits=payload.get("benefits", {}) if isinstance(payload.get("benefits"), dict) else {},
            optional_covers=payload.get("optional_covers", {}) if isinstance(payload.get("optional_covers"), dict) else {},
            vehicle_details=payload.get("vehicle_details", {}) if isinstance(payload.get("vehicle_details"), dict) else {},
            coverage_amount=str(payload.get("coverage_amount")) if payload.get("coverage_amount") not in (None, "") else None,
            deductible=str(payload.get("deductible")) if payload.get("deductible") not in (None, "") else None,
            coverage_score=float(payload.get("coverage_score", 0) or 0),
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
