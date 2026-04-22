"""
Refresh access tokens using the refresh token from an HttpOnly cookie.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from api.cookie_auth import clear_refresh_cookie, set_refresh_cookie
from api.responses import success_response, error_response


class CookieTokenRefreshView(APIView):
    """
    POST with credentials (cookies). Reads refresh JWT from HttpOnly cookie,
    returns new access token in JSON body. Rotates refresh cookie when enabled.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        name = getattr(settings, "JWT_REFRESH_COOKIE_NAME", "refresh_token")
        refresh = request.COOKIES.get(name)
        if not refresh:
            raise AuthenticationFailed("Unauthorized")

        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            resp = error_response(
                message="Unauthorized",
                code=status.HTTP_401_UNAUTHORIZED,
                errors={"refresh": ["Invalid or expired refresh token."]},
            )
            clear_refresh_cookie(resp)
            return resp

        data = serializer.validated_data
        access = data["access"]
        # Never put refresh token in JSON — only HttpOnly cookie (when rotated).
        response = success_response(
            message="Access token refreshed successfully",
            data={"access": access},
            status_code=status.HTTP_200_OK,
        )
        if "refresh" in data:
            set_refresh_cookie(response, data["refresh"])
        return response
