"""Integration test for the full 7-step regression flow.

Tests the full lifecycle of spots and reviews.
"""

import io

from PIL import Image


def _make_jpeg(color="red"):
    """Create a valid JPEG file-like for upload."""
    img = Image.new("RGB", (100, 100), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("photo.jpg", buf, "image/jpeg")


class TestFullFlow:
    """7-step regression flow test."""

    def test_regression_flow(self, client, auth_with_uid):
        """
        Execute the exact 7-step flow:
        1. Nearby query, no spots → empty
        2. submit-with-new-spot → returns spot + review
        3. Nearby query at same coords → returns the new spot
        4. submit-existing with different enum values → returns review
        5. Fetch spot reviews → 2 reviews, newest first
        6. Fetch spot detail → review_count=2, aggregates reflect both,
           recent_review_photos has 2 entries
        7. Fetch /users/me/reviews for submitting user → both reviews returned,
           ordering correct
        """
        headers = auth_with_uid["headers"]

        # Step 1: Nearby query, no spots → empty
        r1 = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 1.0},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json() == []

        # Step 2: submit-with-new-spot → returns spot + review
        form_data = {
            "name": "Griffith Observatory",
            "lat": "34.1184",
            "lng": "-118.3004",
            "overall_rating": "5",
            "notes": "Beautiful views of the city!",
            "best_time_of_day": "GoldenHour",
            "access_level": "Easy",
            "entrance_fee": "Free",
            "crowd_level": "Crowded",
            "environment": "Urban",
            "permit_required": False,
            "drone_allowed": False,
            "tripod_allowed": False,
            "gear_recommendations": "Observatory wide lens",
            "composition_hints": "Shoot from front path",
        }
        r2 = client.post(
            "/spots/with-review",
            data=form_data,
            files=[("photos", _make_jpeg("blue"))],
            headers=headers,
        )
        assert r2.status_code == 201
        body2 = r2.json()
        assert "spot" in body2
        assert "review" in body2

        spot = body2["spot"]
        spot_id = spot["id"]
        review1 = body2["review"]
        review1_id = review1["id"]

        assert spot["name"] == "Griffith Observatory"
        assert spot["city"] == "Los Angeles"  # Geocoding mock
        assert spot["review_count"] == 1
        assert spot["avg_rating"] == 5.0
        assert spot["mode_access_level"] == "Easy"
        assert len(spot["recent_review_photos"]) == 1

        # Step 3: Nearby query at same coords → returns the new spot
        r3 = client.get(
            "/spots",
            params={"lat": 34.1184, "lng": -118.3004, "radius_km": 1.0},
            headers=headers,
        )
        assert r3.status_code == 200
        spots = r3.json()
        assert len(spots) == 1
        assert spots[0]["id"] == spot_id
        assert spots[0]["name"] == "Griffith Observatory"
        assert spots[0]["cover_photo_url"] == review1["photo_urls"][0]

        # Step 4: submit-existing with different enum values → returns review
        form_data_2 = {
            "overall_rating": "3",
            "notes": "Very busy, difficult to find parking.",
            "best_time_of_day": "Night",
            "access_level": "Difficult",  # Changed
            "entrance_fee": "Free",
            "crowd_level": "Crowded",
            "environment": "Nature",  # Changed
            "permit_required": False,
            "drone_allowed": False,
            "tripod_allowed": False,
            "gear_recommendations": "Strong tripod needed",
            "composition_hints": "Frame observatory under stars",
        }
        r4 = client.post(
            "/spots/{}/reviews".format(spot_id),
            data=form_data_2,
            files=[("photos", _make_jpeg("green"))],
            headers=headers,
        )
        assert r4.status_code == 201
        review2 = r4.json()
        review2_id = review2["id"]
        assert review2["spot_id"] == spot_id
        assert review2["overall_rating"] == 3
        assert review2["access_level"] == "Difficult"

        # Step 5: Fetch spot reviews → 2 reviews, newest first
        r5 = client.get(
            "/spots/{}/reviews".format(spot_id),
            headers=headers,
        )
        assert r5.status_code == 200
        reviews_page = r5.json()
        assert len(reviews_page["items"]) == 2
        # The second review (submitted later) should be first
        assert reviews_page["items"][0]["id"] == review2_id
        assert reviews_page["items"][1]["id"] == review1_id

        # Step 6: Fetch spot detail → review_count=2, aggregates reflect both,
        # recent_review_photos has 2 entries
        r6 = client.get(
            "/spots/{}".format(spot_id),
            headers=headers,
        )
        assert r6.status_code == 200
        spot_detail = r6.json()
        assert spot_detail["review_count"] == 2
        # (5 + 3) / 2 = 4.0
        assert spot_detail["avg_rating"] == 4.0

        # Mode tie-breaks or counts:
        # access_level counts: Easy: 1, Difficult: 1 → Difficult (alphabetical tie-break: D < E)
        assert spot_detail["mode_access_level"] == "Difficult"
        # crowd_level counts: Crowded: 2 → Crowded
        assert spot_detail["mode_crowd_level"] == "Crowded"

        # Recent photos has 2 entries (newest review photo first)
        assert len(spot_detail["recent_review_photos"]) == 2
        assert spot_detail["recent_review_photos"][0]["review_id"] == review2_id
        assert spot_detail["recent_review_photos"][1]["review_id"] == review1_id

        # Step 7: Fetch /users/me/reviews for submitting user → both reviews returned,
        # ordering correct
        r7 = client.get(
            "/users/me/reviews",
            headers=headers,
        )
        assert r7.status_code == 200
        user_reviews = r7.json()
        assert len(user_reviews["items"]) == 2
        # Newest first
        assert user_reviews["items"][0]["id"] == review2_id
        assert user_reviews["items"][1]["id"] == review1_id
