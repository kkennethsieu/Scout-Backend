"""Integration tests for saved lists — /users/me/lists and spot membership.

Seeds spots directly in the Firestore emulator, then drives the HTTP API.
"""

from datetime import datetime, timezone


def _seed_spot(spot_id, name, lat=34.05, lng=-118.24, photo_url=None):
    """Seed a spot in the emulator. Optional photo_url populates the cover thumbnail."""
    from app.core.firebase import db
    from app.services.aggregates import empty_aggregates

    data = {
        "name": name,
        "public_lat": lat,
        "public_lng": lng,
        "city": "Los Angeles",
        "admin_area": "California",
        "country": "United States",
        "created_at": datetime.now(timezone.utc),
        **empty_aggregates(),
    }
    if photo_url:
        data["recent_review_photos"] = [
            {"review_id": "r1", "photo_url": photo_url, "created_at": datetime.now(timezone.utc)}
        ]
    db.collection("spots").document(spot_id).set(data)


def _seed_review(spot_id, review_id, user_id, rating=4):
    """Seed a review owned by `user_id` so DELETE /reviews/{id} can be driven."""
    from app.core.firebase import db

    db.collection("reviews").document(review_id).set(
        {
            "spot_id": spot_id,
            "spot_name": "Spot",
            "public_lat": 34.05,
            "public_lng": -118.24,
            "city": "Los Angeles",
            "admin_area": "California",
            "user_id": user_id,
            "photo_urls": ["https://example.com/photo.jpg"],
            "overall_rating": rating,
            "created_at": datetime.now(timezone.utc),
        }
    )


class TestListOverview:
    def test_favorites_auto_created_and_first(self, client, auth_headers):
        r = client.get("/users/me/lists", headers=auth_headers)
        assert r.status_code == 200
        lists = r.json()["lists"]
        assert len(lists) == 1
        assert lists[0]["id"] == "favorites"
        assert lists[0]["name"] == "Favorites"
        assert lists[0]["spot_count"] == 0
        assert lists[0]["cover_photo_url"] is None
        assert lists[0]["is_system"] is True

    def test_custom_list_not_system(self, client, auth_headers):
        client.post("/users/me/lists", json={"name": "Trip"}, headers=auth_headers)
        lists = client.get("/users/me/lists", headers=auth_headers).json()["lists"]
        by_name = {item["name"]: item for item in lists}
        assert by_name["Favorites"]["is_system"] is True
        assert by_name["Trip"]["is_system"] is False

    def test_favorites_always_first(self, client, auth_headers):
        client.post("/users/me/lists", json={"name": "Aaa Early"}, headers=auth_headers)
        r = client.get("/users/me/lists", headers=auth_headers)
        lists = r.json()["lists"]
        assert lists[0]["id"] == "favorites"
        assert {item["name"] for item in lists} == {"Favorites", "Aaa Early"}

    def test_memberships_map(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        a = client.post("/users/me/lists", json={"name": "A"}, headers=auth_headers).json()["id"]
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        body = client.get("/users/me/lists", headers=auth_headers).json()
        memberships = body["memberships"]
        # Every list in the overview has a membership key (empty lists → []).
        assert set(memberships) == {item["id"] for item in body["lists"]}
        assert memberships["favorites"] == ["s1"]
        assert memberships[a] == []


class TestListCrud:
    def test_create_list(self, client, auth_headers):
        r = client.post("/users/me/lists", json={"name": "Roadtrip"}, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Roadtrip"
        assert body["spot_count"] == 0
        assert body["id"] != "favorites"
        assert body["description"] is None  # optional, defaults to null

    def test_create_with_description(self, client, auth_headers):
        r = client.post(
            "/users/me/lists",
            json={"name": "Roadtrip", "description": "West coast sunsets"},
            headers=auth_headers,
        )
        assert r.status_code == 201
        assert r.json()["description"] == "West coast sunsets"

    def test_update_description_and_clear(self, client, auth_headers):
        lid = client.post("/users/me/lists", json={"name": "Trip"}, headers=auth_headers).json()[
            "id"
        ]
        # Set it.
        r = client.patch(
            f"/users/me/lists/{lid}", json={"description": "desc"}, headers=auth_headers
        )
        assert r.json()["description"] == "desc"
        # Renaming alone leaves the description untouched (not sent).
        r = client.patch(f"/users/me/lists/{lid}", json={"name": "Trip2"}, headers=auth_headers)
        assert r.json()["name"] == "Trip2"
        assert r.json()["description"] == "desc"
        # Blank description clears it.
        r = client.patch(f"/users/me/lists/{lid}", json={"description": ""}, headers=auth_headers)
        assert r.json()["description"] is None

    def test_create_rejects_blank_name(self, client, auth_headers):
        r = client.post("/users/me/lists", json={"name": ""}, headers=auth_headers)
        assert r.status_code == 400

    def test_rename_list(self, client, auth_headers):
        lid = client.post("/users/me/lists", json={"name": "Old"}, headers=auth_headers).json()[
            "id"
        ]
        r = client.patch(f"/users/me/lists/{lid}", json={"name": "New"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "New"

    def test_delete_list(self, client, auth_headers):
        lid = client.post("/users/me/lists", json={"name": "Temp"}, headers=auth_headers).json()[
            "id"
        ]
        assert client.delete(f"/users/me/lists/{lid}", headers=auth_headers).status_code == 204
        names = {
            item["id"]
            for item in client.get("/users/me/lists", headers=auth_headers).json()["lists"]
        }
        assert lid not in names

    def test_rename_missing_list_404(self, client, auth_headers):
        r = client.patch("/users/me/lists/nope", json={"name": "X"}, headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["code"] == "LIST_NOT_FOUND"

    def test_favorites_rename_protected(self, client, auth_headers):
        r = client.patch("/users/me/lists/favorites", json={"name": "Nope"}, headers=auth_headers)
        assert r.status_code == 400
        assert r.json()["code"] == "FAVORITES_PROTECTED"

    def test_favorites_delete_protected(self, client, auth_headers):
        r = client.delete("/users/me/lists/favorites", headers=auth_headers)
        assert r.status_code == 400
        assert r.json()["code"] == "FAVORITES_PROTECTED"


class TestMembership:
    def test_add_and_count(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        r = client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        assert r.status_code == 200
        fav = client.get("/users/me/lists", headers=auth_headers).json()["lists"][0]
        assert fav["spot_count"] == 1

    def test_add_is_idempotent(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        # Setting the same membership twice can't drift the count.
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        fav = client.get("/users/me/lists", headers=auth_headers).json()["lists"][0]
        assert fav["spot_count"] == 1  # no drift

    def test_remove_is_idempotent(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        # Empty set removes it; doing it again is a no-op, count stays 0.
        client.patch("/users/me/spots/s1/lists", json={"list_ids": []}, headers=auth_headers)
        client.patch("/users/me/spots/s1/lists", json={"list_ids": []}, headers=auth_headers)
        fav = client.get("/users/me/lists", headers=auth_headers).json()["lists"][0]
        assert fav["spot_count"] == 0

    def test_add_nonexistent_spot_404(self, client, auth_headers):
        r = client.patch(
            "/users/me/spots/ghost/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        assert r.status_code == 404
        assert r.json()["code"] == "SPOT_NOT_FOUND"

    def test_add_to_missing_list_404(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        r = client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["nope"]}, headers=auth_headers
        )
        assert r.status_code == 404
        assert r.json()["code"] == "LIST_NOT_FOUND"

    def test_cover_derived_from_newest_spot(self, client, auth_headers):
        _seed_spot("s1", "Spot 1", photo_url="https://example.com/a.jpg")
        _seed_spot("s2", "Spot 2", photo_url="https://example.com/b.jpg")
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        client.patch(
            "/users/me/spots/s2/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        fav = client.get("/users/me/lists", headers=auth_headers).json()["lists"][0]
        # Newest spot (s2) drives the cover.
        assert fav["cover_photo_url"] == "https://example.com/b.jpg"


class TestListSpots:
    def test_newest_first_and_skips_missing(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        _seed_spot("s2", "Spot 2")
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        client.patch(
            "/users/me/spots/s2/lists", json={"list_ids": ["favorites"]}, headers=auth_headers
        )
        # Delete s1's underlying spot doc → it should be skipped on resolution.
        from app.core.firebase import db

        db.collection("spots").document("s1").delete()

        r = client.get("/users/me/lists/favorites/spots", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert [s["id"] for s in items] == ["s2"]  # newest first, missing skipped

    def test_pagination(self, client, auth_headers):
        for i in range(5):
            _seed_spot(f"s{i}", f"Spot {i}")
            client.patch(
                f"/users/me/spots/s{i}/lists",
                json={"list_ids": ["favorites"]},
                headers=auth_headers,
            )

        seen, cursor, pages = [], None, 0
        while True:
            params = {"limit": 2}
            if cursor:
                params["cursor"] = cursor
            r = client.get("/users/me/lists/favorites/spots", params=params, headers=auth_headers)
            assert r.status_code == 200
            body = r.json()
            seen.extend(s["id"] for s in body["items"])
            cursor = body["next_cursor"]
            pages += 1
            if cursor is None or pages > 10:
                break
        assert pages == 3
        assert seen == ["s4", "s3", "s2", "s1", "s0"]  # newest first, no gaps

    def test_list_spots_missing_list_404(self, client, auth_headers):
        r = client.get("/users/me/lists/nope/spots", headers=auth_headers)
        assert r.status_code == 404


class TestSetMembership:
    def test_set_membership_diffs(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        a = client.post("/users/me/lists", json={"name": "A"}, headers=auth_headers).json()["id"]
        b = client.post("/users/me/lists", json={"name": "B"}, headers=auth_headers).json()["id"]

        # Put s1 into favorites + A.
        r = client.patch(
            "/users/me/spots/s1/lists",
            json={"list_ids": ["favorites", a]},
            headers=auth_headers,
        )
        assert r.status_code == 200
        counts = {item["id"]: item["spot_count"] for item in r.json()["lists"]}
        assert counts["favorites"] == 1
        assert counts[a] == 1
        assert counts[b] == 0
        # The membership map reflects the same write.
        memberships = r.json()["memberships"]
        assert memberships["favorites"] == ["s1"]
        assert memberships[a] == ["s1"]
        assert memberships[b] == []

        # Now move membership to just B — favorites and A get removed, B added.
        r = client.patch("/users/me/spots/s1/lists", json={"list_ids": [b]}, headers=auth_headers)
        counts = {item["id"]: item["spot_count"] for item in r.json()["lists"]}
        assert counts["favorites"] == 0
        assert counts[a] == 0
        assert counts[b] == 1

    def test_set_membership_unknown_list_404(self, client, auth_headers):
        _seed_spot("s1", "Spot 1")
        r = client.patch(
            "/users/me/spots/s1/lists",
            json={"list_ids": ["does-not-exist"]},
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["code"] == "LIST_NOT_FOUND"


class TestSpotDeletionCleanup:
    """Deleting a spot's last review scrubs it from saved lists (no dangling refs)."""

    def test_deleting_last_review_removes_spot_from_lists(self, client, auth_with_uid):
        headers, uid = auth_with_uid["headers"], auth_with_uid["uid"]
        _seed_spot("s1", "Spot 1")
        _seed_review("s1", "rev1", uid)
        client.patch("/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=headers)

        # Sanity: list shows the spot before deletion.
        assert client.get("/users/me/lists", headers=headers).json()["lists"][0]["spot_count"] == 1

        # Delete the spot's only review → the spot is deleted → lists are scrubbed.
        assert client.delete("/reviews/rev1", headers=headers).status_code == 204

        fav = client.get("/users/me/lists", headers=headers).json()["lists"][0]
        assert fav["spot_count"] == 0  # count is truthful, no dangling ref
        spots = client.get("/users/me/lists/favorites/spots", headers=headers).json()
        assert spots["items"] == []

    def test_cleanup_spans_users(self, client, auth_headers_for):
        a = auth_headers_for(email="a@example.com")
        b = auth_headers_for(email="b@example.com")
        _seed_spot("s1", "Spot 1")
        _seed_review("s1", "rev1", a["uid"])  # owned by A
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=a["headers"]
        )
        client.patch(
            "/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=b["headers"]
        )

        assert client.delete("/reviews/rev1", headers=a["headers"]).status_code == 204

        # Both users' lists are scrubbed, not just the deleter's.
        assert (
            client.get("/users/me/lists", headers=a["headers"]).json()["lists"][0]["spot_count"]
            == 0
        )
        assert (
            client.get("/users/me/lists", headers=b["headers"]).json()["lists"][0]["spot_count"]
            == 0
        )

    def test_non_last_review_leaves_spot_and_membership(
        self, client, auth_with_uid, auth_headers_for
    ):
        headers, uid = auth_with_uid["headers"], auth_with_uid["uid"]
        other = auth_headers_for(email="other@example.com")
        _seed_spot("s1", "Spot 1")
        _seed_review("s1", "rev1", uid)  # caller's review
        _seed_review("s1", "rev2", other["uid"])  # a second review keeps the spot alive
        client.patch("/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=headers)

        # Deleting one of two reviews leaves the spot — membership is untouched.
        assert client.delete("/reviews/rev1", headers=headers).status_code == 204

        fav = client.get("/users/me/lists", headers=headers).json()["lists"][0]
        assert fav["spot_count"] == 1
        spots = client.get("/users/me/lists/favorites/spots", headers=headers).json()
        assert [s["id"] for s in spots["items"]] == ["s1"]

    def test_read_self_heals_preexisting_dangling_ref(self, client, auth_headers):
        """A spot deleted before the proactive fix is pruned on the next list read."""
        _seed_spot("s1", "Spot 1")
        _seed_spot("s2", "Spot 2")
        for sid in ("s1", "s2"):
            client.patch(
                f"/users/me/spots/{sid}/lists",
                json={"list_ids": ["favorites"]},
                headers=auth_headers,
            )
        # Simulate pre-fix corruption: delete the spot doc directly, leaving a dead ref.
        from app.core.firebase import db

        db.collection("spots").document("s1").delete()

        # Reading the list spots prunes the dead ref (self-heal).
        client.get("/users/me/lists/favorites/spots", headers=auth_headers)

        # The next overview now reports the corrected count.
        fav = client.get("/users/me/lists", headers=auth_headers).json()["lists"][0]
        assert fav["spot_count"] == 1


class TestListAuth:
    def test_requires_auth(self, client):
        assert client.get("/users/me/lists").status_code == 401
