import requests

GRAPH_URL = "https://graph.microsoft.com/v1.0"


def get_user_profile(access_token):

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        f"{GRAPH_URL}/me",
        headers=headers
    )

    return response.json()


def get_emails(access_token):

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        f"{GRAPH_URL}/me/messages?$top=10",
        headers=headers
    )

    data = response.json()

    formatted_emails = []

    for mail in data.get("value", []):

        formatted_emails.append({
            "subject": mail.get("subject"),
            "received": mail.get("receivedDateTime"),
            "body_preview": mail.get("bodyPreview")
        })

    return formatted_emails