"""
Shared pytest configuration for ScamShield backend tests.
"""
import os

# Auth endpoints require this key; tests mock httpx responses instead of calling Firebase.
os.environ.setdefault("FIREBASE_WEB_API_KEY", "test-firebase-web-api-key")
