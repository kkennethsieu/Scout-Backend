"""Unit-test overrides.

Unit tests are pure (no Firestore / Storage), so we override the root conftest's
autouse `clean_state` teardown — its emulator sweep retries with a long backoff
when the emulators aren't running, making the pure unit suite crawl. We still
drop the in-process spot cache so cross-test state doesn't leak.
"""

import pytest


@pytest.fixture(autouse=True)
def clean_state():
    yield
    try:
        from app.services import spot_cache

        spot_cache.invalidate()
    except Exception:
        pass
