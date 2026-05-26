import os

CLIENT_ID = os.getenv("CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")

AUTHORITY_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

SCOPES = [
    "offline_access",
    "User.Read",
    "Mail.Read",
    "Mail.Send"
]


def get_auth_url():

    scope_string = "%20".join(SCOPES)

    auth_url = (
        f"{AUTHORITY_URL}"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope={scope_string}"
    )

    return auth_url