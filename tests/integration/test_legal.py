"""Integration tests for GET /legal — public privacy/terms links."""


class TestLegalLinks:
    """The legal links endpoint is public and returns both document URLs."""

    def test_returns_both_urls_no_auth(self, client):
        """No auth header required; returns both https URLs + an updated date."""
        r = client.get("/legal")
        assert r.status_code == 200
        body = r.json()
        assert body["privacy_policy_url"].startswith("https://")
        assert body["terms_of_service_url"].startswith("https://")
        assert body["updated_at"]

    def test_reflects_configured_urls(self, client):
        """Endpoint surfaces the values from settings."""
        from app.core.config import settings

        body = client.get("/legal").json()
        assert body["privacy_policy_url"] == settings.PRIVACY_POLICY_URL
        assert body["terms_of_service_url"] == settings.TERMS_OF_SERVICE_URL
        assert body["updated_at"] == settings.LEGAL_UPDATED_AT
