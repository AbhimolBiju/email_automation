"""
Centralized API response helpers.

All API endpoints should return one of these shapes:

Success:
{
  "success": true,
  "message": "...",
  "data": ...,
  "meta": {...}   # optional
}

Error:
{
  "success": false,
  "message": "...",
  "errors": {...} # optional
  "code": 4xx/5xx
}
"""

from __future__ import annotations

from typing import Any, Optional

from rest_framework import status as drf_status
from rest_framework.response import Response


def success_response(
    *,
    message: str,
    data: Any = None,
    meta: Optional[dict[str, Any]] = None,
    status_code: int = drf_status.HTTP_200_OK,
) -> Response:
    payload: dict[str, Any] = {"success": True, "message": message, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return Response(payload, status=status_code)


def error_response(
    *,
    message: str,
    code: int,
    errors: Optional[Any] = None,
) -> Response:
    payload: dict[str, Any] = {"success": False, "message": message, "code": code}
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=code)

