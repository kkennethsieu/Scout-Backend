"""Integration tests for GET /config — public iOS version-gating config."""


class TestConfig:
    """The config endpoint is public and returns the iOS version-gating values."""

    def test_returns_config_no_auth(self, client):
        """No auth header required; returns all three keys with an https update URL."""
        r = client.get("/config")
        assert r.status_code == 200
        body = r.json()
        assert body["ios_min_version"]
        assert body["ios_latest_version"]
        assert body["ios_update_url"].startswith("https://")

    def test_reflects_configured_values(self, client):
        """Endpoint surfaces the values from settings."""
        from app.core.config import settings

        body = client.get("/config").json()
        assert body["ios_min_version"] == settings.IOS_MIN_VERSION
        assert body["ios_latest_version"] == settings.IOS_LATEST_VERSION
        assert body["ios_update_url"] == settings.IOS_UPDATE_URL
