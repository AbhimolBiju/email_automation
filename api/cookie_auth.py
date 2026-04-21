"""
HttpOnly cookie helpers for JWT refresh tokens (SPA + DRF).

The refresh token is stored in an HttpOnly cookie so JavaScript cannot read it
(XSS cannot exfiltrate it). The access token is returned in JSON and kept in
memory on the client.
"""

from __future__ import annotations

from django.conf import settings


def _cookie_kwargs() -> dict:
    """Build keyword args for set_cookie / delete_cookie."""
    max_age = int(
        getattr(settings, "JWT_REFRESH_COOKIE_MAX_AGE", 60 * 60 * 24)
    )  # default 1 day
    secure = getattr(settings, "JWT_COOKIE_SECURE", not settings.DEBUG)
    samesite = getattr(settings, "JWT_COOKIE_SAMESITE", "Lax")
    path = getattr(settings, "JWT_REFRESH_COOKIE_PATH", "/")

    return {
        "max_age": max_age,
        "secure": secure,
        "httponly": True,
        "samesite": samesite,
        "path": path,
    }


def refresh_cookie_name() -> str:
    return getattr(settings, "JWT_REFRESH_COOKIE_NAME", "refresh_token")


def set_refresh_cookie(response, refresh_token: str) -> None:
    """Attach refresh JWT as HttpOnly cookie."""
    name = refresh_cookie_name()
    kwargs = _cookie_kwargs()
    response.set_cookie(name, refresh_token, **kwargs)


def clear_refresh_cookie(response) -> None:
    """Remove refresh cookie (logout). Must match path/samesite/secure."""
    name = refresh_cookie_name()
    kwargs = _cookie_kwargs()
    response.delete_cookie(name, path=kwargs["path"], samesite=kwargs["samesite"])
