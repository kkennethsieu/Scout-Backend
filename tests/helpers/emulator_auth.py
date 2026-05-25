"""Mint Firebase Auth Emulator tokens for integration tests.

Only works against the emulator — tokens are unsigned/fake-signed.
"""

import requests

AUTH_HOST = "http://127.0.0.1:9099"
PROJECT_ID = "scout-test"


def mint_emulator_token(uid: str = "ignored", email: str | None = None, name: str = "") -> dict:
    """
    Mint an ID token via Firebase Auth Emulator REST API.

    Note: the emulator generates its own uid; we don't get to pick it.
    Returns dict with 'idToken' and 'localId' (the actual uid).
    """
    email = email or f"{uid}@example.com"
    password = "test-password-123"

    # Create user (idempotent — emulator returns 200 on duplicate signUp by email)
    requests.post(
        f"{AUTH_HOST}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        json={
            "email": email,
            "password": password,
            "displayName": name,
            "returnSecureToken": True,
        },
    )

    # Sign in to get a token
    r = requests.post(
        f"{AUTH_HOST}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key",
        json={
            "email": email,
            "password": password,
            "returnSecureToken": True,
        },
    )
    r.raise_for_status()
    data = r.json()
    return {"idToken": data["idToken"], "localId": data["localId"]}
