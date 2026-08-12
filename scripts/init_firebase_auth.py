import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SA = ROOT / "scamshield-ai-2026-firebase-adminsdk-fbsvc-a2fd1547f0 (1).json"
PROJECT = "scamshield-ai-2026"

creds = service_account.Credentials.from_service_account_file(
    str(SA), scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
creds.refresh(Request())
headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

for url in [
    f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}:initializeAuth",
    f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/auth",
]:
    r = httpx.post(url, headers=headers, json={}, timeout=30)
    print(url, r.status_code, r.text[:800])
