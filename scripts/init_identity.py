import base64
import json
from pathlib import Path

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parent.parent
SA_PATH = ROOT / "scamshield-ai-2026-firebase-adminsdk-fbsvc-a2fd1547f0 (1).json"

creds = service_account.Credentials.from_service_account_file(
    str(SA_PATH),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
creds.refresh(Request())
headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

project = "scamshield-ai-2026"

for label, method, url, body in [
    (
        "init_identity_platform",
        "post",
        f"https://identitytoolkit.googleapis.com/v2/projects/{project}/identityPlatform:initializeIdentityPlatform",
        {},
    ),
    (
        "get_config_v2",
        "get",
        f"https://identitytoolkit.googleapis.com/v2/projects/{project}/config",
        None,
    ),
    (
        "get_config_admin",
        "get",
        f"https://identitytoolkit.googleapis.com/admin/v2/projects/{project}/config",
        None,
    ),
]:
    fn = httpx.post if method == "post" else httpx.get
    kwargs = {"headers": headers, "timeout": 30}
    if body is not None:
        kwargs["json"] = body
    r = fn(url, **kwargs)
    print(f"\n=== {label} {r.status_code} ===")
    print(r.text[:1500])
