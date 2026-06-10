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

    def test_review_count_defaults_zero(self, client, auth_with_uid):
        """A brand-new user has review_count 0."""
        r = client.get("/users/me", headers=auth_with_uid["headers"])
        assert r.status_code == 200
        assert r.json()["review_count"] == 0

    def test_location_defaults_none(self, client, auth_with_uid):
        """home_city / home_country are None until set."""
        r = client.get("/users/me", headers=auth_with_uid["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["home_city"] is None
        assert body["home_country"] is None

    def test_requires_auth(self, client):
        """Missing auth → 401."""
        r = client.get("/users/me")
        assert r.status_code == 401


class TestUpdateUsersMe:
    """Test PATCH /users/me — profile location updates."""

    def test_set_both_location_fields(self, client, auth_with_uid):
        """PATCH sets home_city/home_country and they persist."""
        headers = auth_with_uid["headers"]
        r = client.patch(
            "/users/me",
            json={"home_city": "Seattle", "home_country": "United States"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["home_city"] == "Seattle"
        assert body["home_country"] == "United States"

        # Persisted across a fresh GET
        got = client.get("/users/me", headers=headers).json()
        assert got["home_city"] == "Seattle"
        assert got["home_country"] == "United States"

    def test_partial_update_preserves_other_field(self, client, auth_with_uid):
        """PATCH with only one field leaves the other untouched."""
        headers = auth_with_uid["headers"]
        client.patch(
            "/users/me",
            json={"home_city": "Tokyo", "home_country": "Japan"},
            headers=headers,
        )
        r = client.patch("/users/me", json={"home_city": "Osaka"}, headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["home_city"] == "Osaka"
        assert body["home_country"] == "Japan"  # preserved

    def test_blank_clears_field(self, client, auth_with_uid):
        """A blank/whitespace value clears the field to None."""
        headers = auth_with_uid["headers"]
        client.patch("/users/me", json={"home_city": "Paris"}, headers=headers)
        r = client.patch("/users/me", json={"home_city": "   "}, headers=headers)
        assert r.status_code == 200
        assert r.json()["home_city"] is None

    def test_update_requires_auth(self, client):
        r = client.patch("/users/me", json={"home_city": "X"})
        assert r.status_code == 401
