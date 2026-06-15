"""Integration tests for DELETE /users/me — account deletion + cascade.

Deletion is asserted via the Admin SDK and direct Firestore reads, not via
/users/me: the old idToken still *verifies* (check_revoked=False), so hitting
/users/me afterward would just re-create a fresh user doc.
"""

import io

from PIL import Image


def _make_jpeg():
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("photo.jpg", buf, "image/jpeg")


def _spot_review_form_data(**overrides):
    data = {
        "name": "Deletion Test Spot",
        "lat": "34.0522",
        "lng": "-118.2437",
        "overall_rating": "5",
        "notes": "Keep this text after anonymization",
    }
    data.update(overrides)
    return data


class TestDeleteUser:
    def test_returns_204_and_deletes_user_doc(self, client, auth_with_uid):
        """DELETE /users/me → 204 and the Firestore user doc is gone."""
        from app.core.firebase import db

        headers = auth_with_uid["headers"]
        uid = auth_with_uid["uid"]

        # Create the user doc (read-through).
        assert client.get("/users/me", headers=headers).status_code == 200

        r = client.delete("/users/me", headers=headers)
        assert r.status_code == 204

        assert db.collection("users").document(uid).get().exists is False

    def test_auth_user_deleted(self, client, auth_with_uid):
        """The Firebase Auth user is removed server-side."""
        from firebase_admin import auth

        headers = auth_with_uid["headers"]
        uid = auth_with_uid["uid"]

        client.get("/users/me", headers=headers)
        assert client.delete("/users/me", headers=headers).status_code == 204

        try:
            auth.get_user(uid)
            raise AssertionError("Auth user should have been deleted")
        except auth.UserNotFoundError:
            pass

    def test_reviews_anonymized_and_spot_survives(self, client, auth_with_uid):
        """Reviews are detached (user_id → 'deleted_user') and content + spot persist."""
        from app.core.firebase import db

        headers = auth_with_uid["headers"]

        # Leave a review on a brand-new spot.
        r = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=headers,
        )
        assert r.status_code == 201
        body = r.json()
        spot_id = body["spot"]["id"]
        review_id = body["review"]["id"]

        assert client.delete("/users/me", headers=headers).status_code == 204

        # Review still exists, authorship detached, free text preserved.
        review = db.collection("reviews").document(review_id).get()
        assert review.exists
        review_data = review.to_dict()
        assert review_data["user_id"] == "deleted_user"
        assert review_data["notes"] == "Keep this text after anonymization"

        # Spot survives with its aggregates intact (the review still counts).
        spot = db.collection("spots").document(spot_id).get()
        assert spot.exists
        assert spot.to_dict()["review_count"] == 1

    def test_lists_deleted(self, client, auth_with_uid):
        """The user's saved-lists subcollection is removed (no Firestore cascade)."""
        from app.core.firebase import db

        headers = auth_with_uid["headers"]
        uid = auth_with_uid["uid"]

        # Materialize Favorites + a custom list with a saved spot.
        db.collection("spots").document("s1").set(
            {
                "name": "S1",
                "public_lat": 0.0,
                "public_lng": 0.0,
                "city": "X",
                "admin_area": "Y",
                "country": "Z",
            }
        )
        client.patch("/users/me/spots/s1/lists", json={"list_ids": ["favorites"]}, headers=headers)
        client.post("/users/me/lists", json={"name": "Trip"}, headers=headers)
        assert len(list(db.collection("users").document(uid).collection("lists").stream())) == 2

        assert client.delete("/users/me", headers=headers).status_code == 204

        remaining = list(db.collection("users").document(uid).collection("lists").stream())
        assert remaining == []

    def test_user_with_no_reviews(self, client, auth_with_uid):
        """A user who never reviewed can still delete → 204."""
        headers = auth_with_uid["headers"]
        client.get("/users/me", headers=headers)
        assert client.delete("/users/me", headers=headers).status_code == 204

    def test_requires_auth(self, client):
        """No token → 401."""
        assert client.delete("/users/me").status_code == 401
