from django.urls import path

from .views import (
    outlook_login,
    outlook_callback,
    fetch_emails
)

urlpatterns = [
    path(
        "auth/outlook/login/",
        outlook_login,
        name="outlook_login"
    ),

    path(
        "auth/outlook/callback/",
        outlook_callback,
        name="outlook_callback"
    ),

    path(
        "emails/",
        fetch_emails,
        name="fetch_emails"
    ),
]