from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials

ROOT = Path(__file__).resolve().parent.parent
SA = ROOT / "scamshield-ai-2026-firebase-adminsdk-fbsvc-a2fd1547f0 (1).json"
cred = credentials.Certificate(str(SA))
firebase_admin.initialize_app(cred)

try:
    user = auth.create_user(email="admin-created@test.com", password="password123")
    print("created", user.uid)
except Exception as exc:
    print("create_user failed:", exc)
