import json
from pathlib import Path

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SA_PATH = Path(__file__).resolve().parent.parent / "scamshield-ai-2026-firebase-adminsdk-fbsvc-a2fd1547f0 (1).json"

creds = service_account.Credentials.from_service_account_file(
    str(SA_PATH),
    scopes=[
        "https://www.googleapis.com/auth/firebase",
        "https://www.googleapis.com/auth/cloud-platform",
    ],
)
creds.refresh(Request())
headers = {"Authorization": f"Bearer {creds.token}"}

project = "scamshield-ai-2026"
app_id = "1:171903181936:android:1a3b8a79be8c89989100b5"
for label, url in [
    ("project", f"https://firebase.googleapis.com/v1beta1/projects/{project}"),
    ("android_config", f"https://firebase.googleapis.com/v1beta1/projects/-/androidApps/{app_id}/config"),
    ("android_sha", f"https://firebase.googleapis.com/v1beta1/projects/-/androidApps/{app_id}/sha"),
]:
    r = httpx.get(url, headers=headers, timeout=30)
    print(f"\n=== {label} {r.status_code} ===")
    print(r.text[:2500])
