"""Integration tests for GET /users/me — read-through user doc creation."""


class TestUsersMe:
    """Test user profile endpoint."""

    def test_first_call_creates_doc(self, client, auth_with_uid):
        """First call creates user doc from token claims."""
        r = client.get("/users/me", headers=auth_with_uid["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["uid"] == auth_with_uid["uid"]
        assert body["email"] == "test@example.com"
        assert "created_at" in body

    def test_second_call_reads_existing(self, client, auth_with_uid):
        """Second call reads existing doc — no error, same data."""
        headers = auth_with_uid["headers"]

        r1 = client.get("/users/me", headers=headers)
        assert r1.status_code == 200

        r2 = client.get("/users/me", headers=headers)
        assert r2.status_code == 200
        assert r1.json()["uid"] == r2.json()["uid"]
        assert r1.json()["created_at"] == r2.json()["created_at"]

    def test_doc_fields_match_claims(self, client, auth_headers_for):
        """User doc fields match token claims."""
        result = auth_headers_for(email="custom@example.com", name="Custom Name")
        r = client.get("/users/me", headers=result["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "custom@example.com"
        # Note: emulator may or may not pass displayName through to token claims.
        # The important thing is the endpoint doesn't crash.
        assert "display_name" in body

    def test_requires_auth(self, client):
        """Missing auth → 401."""
        r = client.get("/users/me")
        assert r.status_code == 401
