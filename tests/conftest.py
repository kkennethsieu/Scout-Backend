"""Shared fixtures for all tests.

Emulator environment is configured at session scope.
Each test gets clean Firestore + Storage state via autouse fixture.
"""

import os

import pytest
import requests
from fastapi.testclient import TestClient

from tests.helpers.emulator_auth import mint_emulator_token

# Set emulator environment variables at import time so they are present during test collection
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "127.0.0.1:9099"
os.environ["STORAGE_EMULATOR_HOST"] = "http://127.0.0.1:9199"
os.environ["GOOGLE_CLOUD_PROJECT"] = "scout-test"
os.environ["STORAGE_BUCKET"] = "scout-test.appspot.com"
os.environ["GEOCODING_API_KEY"] = "test-key-unused"
os.environ["ENV"] = "test"


@pytest.fixture(scope="session", autouse=True)
def emulator_env():
    """Placeholder fixture since environment is already set at module load time."""
    pass


@pytest.fixture
def mock_geocoding():
    """Default geocoding mock — returns LA data."""

    async def fake_reverse(lat, lng):
        return {
            "city": "Los Angeles",
            "admin_area": "California",
            "country": "United States",
        }

    return fake_reverse


@pytest.fixture
def client(mock_geocoding):
    """TestClient with geocoding mocked out."""
    from app.main import app
    from app.services import geocoding

    # Override the geocoding.reverse function
    original = geocoding.reverse
    geocoding.reverse = mock_geocoding

    with TestClient(app) as c:
        yield c

    geocoding.reverse = original


@pytest.fixture
def auth_headers_for():
    """
    Parameterized fixture — returns a function so tests can mint tokens
    for different users.

    Returns dict with 'headers' and 'uid'.
    """

    def _make(email="test@example.com", name="Test User"):
        result = mint_emulator_token(email=email, name=name)
        return {
            "headers": {"Authorization": f"Bearer {result['idToken']}"},
            "uid": result["localId"],
        }

    return _make


@pytest.fixture
def auth_headers(auth_headers_for):
    """Default: one test user. Returns just the headers dict."""
    result = auth_headers_for()
    return result["headers"]


@pytest.fixture
def auth_with_uid(auth_headers_for):
    """Default: one test user. Returns both headers and uid."""
    return auth_headers_for()


@pytest.fixture(autouse=True)
def clean_state():
    """Clean Firestore and Storage after each test."""
    yield

    # Clear Firestore
    try:
        requests.delete(
            "http://127.0.0.1:8080/emulator/v1/projects/scout-test/databases/(default)/documents"
        )
    except Exception:
        pass  # Emulator might not be running (unit tests)

    # Clear Storage
    try:
        from app.core.firebase import bucket

        for blob in bucket.list_blobs(prefix="reviews/"):
            blob.delete()
    except Exception:
        pass  # Emulator might not be running (unit tests)
