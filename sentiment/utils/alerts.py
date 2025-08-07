# sentiment/utils/alerts.py

import os
import requests

def send_alert(message, priority=0):
    user_key = os.getenv("PUSHOVER_USER_KEY")
    app_token = os.getenv("PUSHOVER_APP_TOKEN")
    if not user_key or not app_token:
        return

    payload = {
        "token": app_token,
        "user": user_key,
        "message": message,
        "priority": priority
    }

    try:
        requests.post("https://api.pushover.net/1/messages.json", data=payload)
    except Exception:
        pass
