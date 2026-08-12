"""
Setup Firebase Authentication for scamshield-ai-2026:
- Initialize Identity Platform (if needed)
- Enable email/password + Google sign-in
- Sync google-services.json + .env FIREBASE_WEB_API_KEY

Run: python scripts/setup_firebase_auth.py
"""
import base64
import json
from pathlib import Path
from urllib.parse import quote

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parent.parent
SA_PATH = ROOT / "scamshield-ai-2026-firebase-adminsdk-fbsvc-a2fd1547f0 (1).json"
OUT_GS = ROOT.parent / "ScamShieldAI_FE" / "app" / "google-services.json"
ENV_PATH = ROOT / ".env"

PROJECT = "scamshield-ai-2026"
APP_ID = "1:171903181936:android:1a3b8a79be8c89989100b5"


def _auth_headers() -> dict[str, str]:
    creds = service_account.Credentials.from_service_account_file(
        str(SA_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }


def _ensure_identity_platform(headers: dict[str, str]) -> None:
    init_url = f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}:initializeAuth"
    r_init = httpx.post(init_url, headers=headers, json={}, timeout=30)
    print("initializeAuth:", r_init.status_code, r_init.text[:400])

    r = httpx.post(
        f"https://identitytoolkit.googleapis.com/v2/projects/{PROJECT}/identityPlatform:initializeIdentityPlatform",
        headers=headers,
        json={},
        timeout=30,
    )
    print("initializeIdentityPlatform:", r.status_code, r.text[:400])


def _enable_email_password(headers: dict[str, str]) -> None:
    r = httpx.patch(
        f"https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}/config"
        "?updateMask=signIn.email.enabled,signIn.email.passwordRequired",
        headers=headers,
        json={"signIn": {"email": {"enabled": True, "passwordRequired": True}}},
        timeout=30,
    )
    print("enable email/password:", r.status_code, r.text[:600])


def _ensure_google_provider(headers: dict[str, str]) -> None:
    get_url = (
        f"https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}"
        "/defaultSupportedIdpConfigs/google.com"
    )
    r_get = httpx.get(get_url, headers=headers, timeout=30)
    if r_get.status_code == 200:
        r = httpx.patch(
            f"{get_url}?updateMask=enabled",
            headers=headers,
            json={"enabled": True},
            timeout=30,
        )
        print("patch google provider:", r.status_code, r.text[:600])
        return

    r = httpx.post(
        f"https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}"
        "/defaultSupportedIdpConfigs?idpId=google.com",
        headers=headers,
        json={
            "enabled": True,
            "name": f"projects/{PROJECT}/defaultSupportedIdpConfigs/google.com",
        },
        timeout=30,
    )
    print("create google provider:", r.status_code, r.text[:600])


def _sync_android_config(headers: dict[str, str]) -> str:
    r = httpx.get(
        f"https://firebase.googleapis.com/v1beta1/projects/-/androidApps/{APP_ID}/config",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    contents = base64.b64decode(r.json()["configFileContents"]).decode()
    OUT_GS.write_text(contents, encoding="utf-8")
    data = json.loads(contents)
    api_key = data["client"][0]["api_key"][0]["current_key"]
    oauth = data["client"][0].get("oauth_client", [])
    print("google-services.json saved:", OUT_GS)
    print("oauth_client:", json.dumps(oauth, indent=2))
    return api_key


def _update_env(api_key: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    out: list[str] = []
    found_key = found_sa = False
    for line in lines:
        if line.startswith("FIREBASE_WEB_API_KEY="):
            out.append(f"FIREBASE_WEB_API_KEY={api_key}")
            found_key = True
        elif line.startswith("FIREBASE_SERVICE_ACCOUNT_JSON="):
            out.append(f"FIREBASE_SERVICE_ACCOUNT_JSON={SA_PATH.name}")
            found_sa = True
        else:
            out.append(line)
    if not found_key:
        out.append(f"FIREBASE_WEB_API_KEY={api_key}")
    if not found_sa:
        out.append(f"FIREBASE_SERVICE_ACCOUNT_JSON={SA_PATH.name}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(".env updated")


def _test_signup(api_key: str) -> None:
    r = httpx.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}",
        json={
            "email": "scamshield.test@example.com",
            "password": "password123",
            "returnSecureToken": True,
        },
        timeout=30,
    )
    print("signUp test:", r.status_code, r.text[:500])


def main() -> None:
    headers = _auth_headers()
    _ensure_identity_platform(headers)
    _enable_email_password(headers)
    _ensure_google_provider(headers)
    api_key = _sync_android_config(headers)
    _update_env(api_key)
    _test_signup(api_key)


if __name__ == "__main__":
    main()
