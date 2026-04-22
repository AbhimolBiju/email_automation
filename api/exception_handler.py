"""
Global DRF exception handler to standardize error responses.

This converts DRF/Django exceptions (validation, auth, not found, etc.) into:
{
  "success": false,
  "message": "...",
  "errors": {...}  # when available
  "code": 4xx/5xx
}
"""

from __future__ import annotations

from typing import Any, Optional

from rest_framework.views import exception_handler as drf_exception_handler


def _extract_errors(data: Any) -> Optional[Any]:
    # DRF can return dict of field errors, or a list, or {"detail": "..."}.
    if data is None:
        return None
    if isinstance(data, dict):
        if "detail" in data and len(data) == 1:
            return None
        return data
    if isinstance(data, list):
        return data
    return None


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    status_code = response.status_code
    data = response.data

    # Convert DRF validation errors from 400 -> 422 (Unprocessable Entity)
    # to match this project's standard.
    if status_code == 400:
        status_code = 422
        response.status_code = 422

    # Prefer DRF's "detail" as message when present.
    message = None
    if isinstance(data, dict) and "detail" in data:
        detail = data.get("detail")
        message = str(detail) if detail is not None else None

    if not message:
        if status_code == 401:
            message = "Unauthorized"
        elif status_code == 403:
            message = "Forbidden"
        elif status_code == 404:
            message = "Resource not found"
        elif status_code == 405:
            message = "Method not allowed"
        else:
            message = "Request failed"

    errors = _extract_errors(data)

    response.data = {
        "success": False,
        "message": message,
        **({"errors": errors} if errors is not None else {}),
        "code": status_code,
    }

    return response

