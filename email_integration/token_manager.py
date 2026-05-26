import requests
import os

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def get_token_from_code(code):

    data = {
        "client_id": CLIENT_ID,
        "scope": "offline_access User.Read Mail.Read Mail.Send",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(TOKEN_URL, data=data)

    return response.json()