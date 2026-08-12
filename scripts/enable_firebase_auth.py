import base64
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
        "https://www.googleapis.com/auth/identitytoolkit",
    ],
)
creds.refresh(Request())
headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

project = "scamshield-ai-2026"
# Enable Google and Email/Password sign-in
for label, url, body in [
    (
        "auth_config",
        f"https://identitytoolkit.googleapis.com/admin/v2/projects/{project}/config?updateMask=signIn.allowPasswordUser,signIn.email.enabled,signIn.email.passwordRequired",
        {
            "signIn": {
                "allowPasswordUser": True,
                "email": {"enabled": True, "passwordRequired": True},
            }
        },
    ),
    (
        "google_provider",
        f"https://identitytoolkit.googleapis.com/admin/v2/projects/{project}/defaultSupportedIdpConfigs/google.com?updateMask=enabled",
        {"enabled": True, "name": f"projects/{project}/defaultSupportedIdpConfigs/google.com"},
    ),
]:
    method = httpx.patch if "defaultSupportedIdpConfigs" in url else httpx.patch
    r = method(url, headers=headers, json=body, timeout=30)
    print(f"\n=== {label} {r.status_code} ===")
    print(r.text[:2500])

# Re-fetch android config for oauth clients
app_id = "1:171903181936:android:1a3b8a79be8c89989100b5"
r = httpx.get(
    f"https://firebase.googleapis.com/v1beta1/projects/-/androidApps/{app_id}/config",
    headers={"Authorization": f"Bearer {creds.token}"},
    timeout=30,
)
print("\n=== android_config after enable ===")
if r.status_code == 200:
    contents = base64.b64decode(r.json()["configFileContents"]).decode()
    print(contents)
else:
    print(r.status_code, r.text[:1500])
