"""Integration tests for auth — token verification and error responses.

Tests against Firebase Auth Emulator.
"""


class TestAuth:
    """Test authentication flows."""

    # /spots is public; use a still-guarded route (/users/me/lists) to exercise auth.
    def test_missing_header_returns_401(self, client):
        """Missing Authorization header → 401 MISSING_TOKEN (not 422)."""
        r = client.get("/users/me/lists")
        assert r.status_code == 401
        body = r.json()
        assert body["code"] == "MISSING_TOKEN"
        assert "detail" in body

    def test_malformed_header_returns_401(self, client):
        """Malformed header (no Bearer prefix) → 401 MISSING_TOKEN."""
        r = client.get(
            "/users/me/lists",
            headers={"Authorization": "InvalidTokenHere"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "MISSING_TOKEN"

    def test_invalid_token_returns_401(self, client):
        """Invalid/expired token → 401 INVALID_TOKEN."""
        r = client.get(
            "/users/me/lists",
            headers={"Authorization": "Bearer fake-invalid-token-12345"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "INVALID_TOKEN"

    def test_valid_token_passes(self, client, auth_headers):
        """Valid emulator token → request proceeds (200 or endpoint-specific status)."""
        r = client.get(
            "/users/me/lists",
            headers=auth_headers,
        )
        assert r.status_code == 200

    def test_health_no_auth_required(self, client):
        """Health endpoint doesn't require auth."""
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "env" in body
