from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


class CookieTokenRefreshViewTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/auth/token/refresh/"
        self.user = get_user_model().objects.create_user(
            username="refresh-user",
            email="refresh@example.com",
            password="Secret123!",
        )

    def test_refresh_succeeds_with_cookie_even_when_authorization_header_is_invalid(self) -> None:
        refresh = str(RefreshToken.for_user(self.user))
        self.client.cookies["refresh_token"] = refresh
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-or-expired-access")

        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertTrue(response.data["data"]["access"])

    def test_refresh_succeeds_with_body_fallback_when_cookie_missing(self) -> None:
        refresh = str(RefreshToken.for_user(self.user))

        response = self.client.post(self.url, {"refresh": refresh}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertTrue(response.data["data"]["access"])
