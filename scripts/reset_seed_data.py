"""Wipe seed data from the REAL project before re-seeding.

Deletes EVERY spot and review, the seed Auth users (emails starting with
'seed-'), their Firestore user docs, and all objects under the Storage
`reviews/` prefix. Real users (non 'seed-*' emails) are KEPT; their review_count
is reset to 0 since their reviews are being removed.

DANGER: destructive and irreversible. Locked to project 'scout-497021'.

Auth: gcloud Application Default Credentials by default
(`gcloud auth application-default login`), or GOOGLE_APPLICATION_CREDENTIALS.

Usage:
    # Preview only (no writes):
    python -m scripts.reset_seed_data --project scout-497021 --dry-run

    # Actually delete:
    python -m scripts.reset_seed_data --project scout-497021
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import firebase_admin
from firebase_admin import auth, credentials, firestore, storage

ALLOWED_PROJECT = "scout-497021"
DEFAULT_BUCKET = "dev-scout-photos"
SEED_EMAIL_PREFIX = "seed-"
_BATCH = 400  # Firestore batch cap is 500; stay under it.


def _delete_collection(db, name: str, dry_run: bool) -> int:
    """Delete every doc in a collection in chunked batches. Returns the count."""
    refs = [d.reference for d in db.collection(name).stream()]
    if dry_run:
        return len(refs)
    for start in range(0, len(refs), _BATCH):
        batch = db.batch()
        for ref in refs[start : start + _BATCH]:
            batch.delete(ref)
        batch.commit()
    return len(refs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help=f"Must be '{ALLOWED_PROJECT}'")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--dry-run", action="store_true", help="Report counts, delete nothing")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if args.project != ALLOWED_PROJECT:
        sys.exit(f"[reset] Refusing to run: --project must be '{ALLOWED_PROJECT}'.")

    # Force REAL Firebase (these are set in .env for local dev).
    for var in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "STORAGE_EMULATOR_HOST"):
        if os.environ.pop(var, None):
            print(f"[reset] Ignoring {var} — operating on REAL Firebase.")

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    init_opts = {"projectId": args.project, "storageBucket": args.bucket}
    if cred_path and os.path.exists(cred_path):
        firebase_admin.initialize_app(credentials.Certificate(cred_path), init_opts)
    else:
        firebase_admin.initialize_app(options=init_opts)
    db = firestore.client()
    bucket = storage.bucket()

    # ---- Survey what exists ----
    spot_n = db.collection("spots").count().get()[0][0].value
    review_n = db.collection("reviews").count().get()[0][0].value
    seed_user_refs, kept_user_refs = [], []
    seed_uids = []
    for u in db.collection("users").stream():
        email = (u.to_dict().get("email") or "")
        if email.startswith(SEED_EMAIL_PREFIX):
            seed_user_refs.append(u.reference)
            seed_uids.append(u.id)
        else:
            kept_user_refs.append(u.reference)
    review_blobs = [b for b in bucket.list_blobs(prefix="reviews/")]

    mode = "DRY RUN — nothing will be deleted" if args.dry_run else "LIVE DELETE"
    print(f"\n[reset] {mode}  (project: {args.project})")
    print(f"  spots to delete:           {spot_n}")
    print(f"  reviews to delete:         {review_n}")
    print(f"  seed users to delete:      {len(seed_user_refs)} (Auth + Firestore docs)")
    print(f"  real users to KEEP:        {len(kept_user_refs)} (review_count reset to 0)")
    print(f"  storage reviews/ objects:  {len(review_blobs)}")

    if args.dry_run:
        print("\n[reset] Dry run complete. Re-run without --dry-run to delete.")
        return

    if not args.yes:
        confirm = input("\nType 'delete' to permanently remove the above: ").strip().lower()
        if confirm != "delete":
            sys.exit("[reset] Aborted.")

    # ---- Firestore: spots + reviews ----
    n_spots = _delete_collection(db, "spots", dry_run=False)
    n_reviews = _delete_collection(db, "reviews", dry_run=False)
    print(f"[reset] Deleted {n_spots} spots, {n_reviews} reviews.")

    # ---- Seed user docs + Auth records ----
    for start in range(0, len(seed_user_refs), _BATCH):
        batch = db.batch()
        for ref in seed_user_refs[start : start + _BATCH]:
            batch.delete(ref)
        batch.commit()
    for start in range(0, len(seed_uids), 1000):  # auth.delete_users caps at 1000
        auth.delete_users(seed_uids[start : start + 1000])
    print(f"[reset] Deleted {len(seed_user_refs)} seed users (Auth + docs).")

    # ---- Reset review_count on kept users (their reviews are gone) ----
    for start in range(0, len(kept_user_refs), _BATCH):
        batch = db.batch()
        for ref in kept_user_refs[start : start + _BATCH]:
            batch.set(ref, {"review_count": 0}, merge=True)
        batch.commit()
    print(f"[reset] Reset review_count on {len(kept_user_refs)} kept users.")

    # ---- Storage: reviews/ prefix ----
    if review_blobs:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda b: b.delete(), review_blobs))
    print(f"[reset] Deleted {len(review_blobs)} storage objects under reviews/.")

    print("\n[reset] Done. You can now run scripts.seed_real_data.")


if __name__ == "__main__":
    main()
