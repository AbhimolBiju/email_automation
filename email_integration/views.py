from django.shortcuts import render

# Create your views here.
from django.shortcuts import redirect
from django.http import JsonResponse

from .auth import get_auth_url
from .token_manager import get_token_from_code
from .graph_api import get_user_profile, get_emails
from .models import OutlookAccount


def outlook_login(request):

    auth_url = get_auth_url()

    return redirect(auth_url)


# def outlook_callback(request):

#     code = request.GET.get("code")

#     if not code:
#         return JsonResponse({"error": "Authorization code missing"})

#     token_data = get_token_from_code(code)

#     access_token = token_data.get("access_token")
#     refresh_token = token_data.get("refresh_token")

#     profile = get_user_profile(access_token)

#     email = profile.get("mail") or profile.get("userPrincipalName")

#     OutlookAccount.objects.create(
#         user=request.user,
#         email=email,
#         access_token=access_token,
#         refresh_token=refresh_token,
#         expires_in=token_data.get("expires_in")
#     )

#     return JsonResponse({
#         "message": "Outlook connected successfully",
#         "email": email
#     })

from django.contrib.auth.models import User


def outlook_callback(request):

    code = request.GET.get("code")

    if not code:
        return JsonResponse({
            "error": "Authorization code missing"
        })

    token_data = get_token_from_code(code)

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    profile = get_user_profile(access_token)

    email = profile.get("mail") or profile.get("userPrincipalName")

    # TEMP TEST USER
    test_user = User.objects.first()

    OutlookAccount.objects.create(
        user=test_user,
        email=email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=token_data.get("expires_in")
    )

    return JsonResponse({
        "message": "Outlook connected successfully",
        "email": email
    })

# def fetch_emails(request):

#     outlook_account = OutlookAccount.objects.filter(
#         user=request.user
#     ).first()

#     if not outlook_account:
#         return JsonResponse({
#             "error": "Outlook not connected"
#         })

#     emails = get_emails(outlook_account.access_token)

#     return JsonResponse(emails)

from django.contrib.auth.models import User


def fetch_emails(request):

    # TEMP TEST USER
    test_user = User.objects.first()

    outlook_account = OutlookAccount.objects.filter(
        user=test_user
    ).first()

    if not outlook_account:
        return JsonResponse({
            "error": "Outlook not connected"
        })

    emails = get_emails(outlook_account.access_token)

    return JsonResponse(emails, safe=False)