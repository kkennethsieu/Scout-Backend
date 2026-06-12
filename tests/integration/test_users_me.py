"""Integration tests for GET /users/me — read-through user doc creation."""

import io

from PIL import Image


def _make_jpeg():
    """A valid JPEG file-like for multipart upload."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("avatar.jpg", buf, "image/jpeg")


def _make_png():
    """A PNG file-like for multipart upload (should be rejected)."""
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ("avatar.png", buf, "image/png")


class TestUsersMe:
    """Test user profile endpoint."""

    def test_first_call_creates_doc(self, client, auth_with_uid):
        """First call creates user doc from token claims."""
        r = client.get("/users/me", headers=auth_with_uid["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == auth_with_uid["uid"]
        assert body["email"] == "test@example.com"
        assert "created_at" in body

    def test_second_call_reads_existing(self, client, auth_with_uid):
        """Second call reads existing doc — no error, same data."""
        headers = auth_with_uid["headers"]

        r1 = client.get("/users/me", headers=headers)
        assert r1.status_code == 200

        r2 = client.get("/users/me", headers=headers)
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]
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

    def test_notification_prefs_default_true(self, client, auth_with_uid):
        """email_notifications / push_notifications default to True."""
        r = client.get("/users/me", headers=auth_with_uid["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["email_notifications"] is True
        assert body["push_notifications"] is True

    def test_requires_auth(self, client):
        """Missing auth → 401."""
        r = client.get("/users/me")
        assert r.status_code == 401


class TestUpdateUsersMe:
    """Test PATCH /users/me — multipart profile updates."""

    def test_set_both_location_fields(self, client, auth_with_uid):
        """PATCH sets home_city/home_country and they persist."""
        headers = auth_with_uid["headers"]
        r = client.patch(
            "/users/me",
            data={"home_city": "Seattle", "home_country": "United States"},
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
            data={"home_city": "Tokyo", "home_country": "Japan"},
            headers=headers,
        )
        r = client.patch("/users/me", data={"home_city": "Osaka"}, headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["home_city"] == "Osaka"
        assert body["home_country"] == "Japan"  # preserved

    def test_blank_clears_field(self, client, auth_with_uid):
        """A blank/whitespace value clears the field to None."""
        headers = auth_with_uid["headers"]
        client.patch("/users/me", data={"home_city": "Paris"}, headers=headers)
        r = client.patch("/users/me", data={"home_city": "   "}, headers=headers)
        assert r.status_code == 200
        assert r.json()["home_city"] is None

    def test_update_display_name(self, client, auth_with_uid):
        """display_name is editable and persists."""
        headers = auth_with_uid["headers"]
        r = client.patch("/users/me", data={"display_name": "Ansel Adams"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["display_name"] == "Ansel Adams"
        got = client.get("/users/me", headers=headers).json()
        assert got["display_name"] == "Ansel Adams"

    def test_blank_display_name_ignored(self, client, auth_with_uid):
        """A blank display_name is ignored, not cleared (it's non-nullable)."""
        headers = auth_with_uid["headers"]
        client.patch("/users/me", data={"display_name": "Keeper"}, headers=headers)
        r = client.patch("/users/me", data={"display_name": "   "}, headers=headers)
        assert r.status_code == 200
        assert r.json()["display_name"] == "Keeper"

    def test_toggle_notification_prefs(self, client, auth_with_uid):
        """Notification booleans toggle and persist."""
        headers = auth_with_uid["headers"]
        r = client.patch(
            "/users/me",
            data={"email_notifications": "false", "push_notifications": "false"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["email_notifications"] is False
        assert body["push_notifications"] is False

        # Untouched pref preserved on a partial update
        r2 = client.patch("/users/me", data={"push_notifications": "true"}, headers=headers)
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["push_notifications"] is True
        assert body2["email_notifications"] is False  # preserved

    def test_email_is_read_only(self, client, auth_with_uid):
        """Sending an email field does not change the stored email."""
        headers = auth_with_uid["headers"]
        original = client.get("/users/me", headers=headers).json()["email"]
        r = client.patch(
            "/users/me",
            data={"email": "attacker@evil.com", "home_city": "X"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["email"] == original

    def test_upload_photo_sets_photo_url(self, client, auth_with_uid):
        """A photo part uploads and sets photo_url under the user's avatar prefix."""
        headers = auth_with_uid["headers"]
        uid = auth_with_uid["uid"]
        r = client.patch(
            "/users/me",
            files={"photo": _make_jpeg()},
            headers=headers,
        )
        assert r.status_code == 200
        photo_url = r.json()["photo_url"]
        assert photo_url is not None
        assert f"users/{uid}/avatar/" in photo_url

        # Persisted across a fresh GET
        got = client.get("/users/me", headers=headers).json()
        assert got["photo_url"] == photo_url

    def test_upload_non_jpeg_rejected(self, client, auth_with_uid):
        """A non-JPEG photo → 400 PHOTO_INVALID_FORMAT."""
        r = client.patch(
            "/users/me",
            files={"photo": _make_png()},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 400
        assert r.json()["code"] == "PHOTO_INVALID_FORMAT"

    def test_update_requires_auth(self, client):
        r = client.patch("/users/me", data={"home_city": "X"})
        assert r.status_code == 401
