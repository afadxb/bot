# utils/pushover.py

import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("PUSHOVER_API_TOKEN")
USER  = os.getenv("PUSHOVER_USER_KEY")
API_URL = "https://api.pushover.net/1/messages.json"

def notify(title: str, message: str):
    """
    Send a Pushover notification via direct HTTP.
    """
    payload = {
        "token":   TOKEN,
        "user":    USER,
        "title":   title,
        "message": message,
    }
    resp = requests.post(API_URL, data=payload, timeout=10)
    resp.raise_for_status()
