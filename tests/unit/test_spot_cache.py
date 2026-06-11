"""Unit tests for the in-process spots cache.

No emulator: the Firestore read (_read_all_spots) is monkeypatched with a counter
so we can assert exactly when a refresh happens.
"""

import asyncio
import time

from app.services import spot_cache


def _patch_reader(monkeypatch):
    """Replace _read_all_spots with a counter; returns a callable -> call count."""
    calls = {"n": 0}

    def fake_read():
        calls["n"] += 1
        return [{"id": f"spot-{calls['n']}", "name": "Cached"}]

    monkeypatch.setattr(spot_cache, "_read_all_spots", fake_read)
    return lambda: calls["n"]


class TestSpotCache:
    def test_hit_within_ttl(self, monkeypatch):
        """A second read within the TTL is served from cache (no re-read)."""
        count = _patch_reader(monkeypatch)
        spot_cache.invalidate()

        first = asyncio.run(spot_cache.get_all_spots())
        second = asyncio.run(spot_cache.get_all_spots())

        assert count() == 1  # only one Firestore read
        assert first is second  # same cached object

    def test_invalidate_forces_reread(self, monkeypatch):
        """invalidate() drops the snapshot so the next read refreshes."""
        count = _patch_reader(monkeypatch)
        spot_cache.invalidate()

        asyncio.run(spot_cache.get_all_spots())
        spot_cache.invalidate()
        asyncio.run(spot_cache.get_all_spots())

        assert count() == 2

    def test_expiry_rereads(self, monkeypatch):
        """An expired (but still populated) snapshot triggers a refresh."""
        count = _patch_reader(monkeypatch)
        spot_cache.invalidate()

        asyncio.run(spot_cache.get_all_spots())
        assert count() == 1

        # Simulate TTL expiry without touching _cache (distinct from invalidate).
        spot_cache._expires_at = time.monotonic() - 1
        asyncio.run(spot_cache.get_all_spots())

        assert count() == 2
