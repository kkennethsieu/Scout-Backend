"""Firebase Admin SDK initialization and shared clients."""

import firebase_admin
from firebase_admin import credentials, firestore, storage

from app.core.config import settings

_app = None


def init_firebase():
    """
    Initialize Firebase Admin SDK. Call once at app startup.

    Uses credential file if FIREBASE_CREDENTIALS_PATH is set (local dev),
    otherwise falls back to Application Default Credentials (Cloud Run).
    """
    global _app
    if _app is not None:
        return

    if settings.FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        _app = firebase_admin.initialize_app(cred, {"storageBucket": settings.STORAGE_BUCKET})
    else:
        _app = firebase_admin.initialize_app(options={"storageBucket": settings.STORAGE_BUCKET})


def get_db():
    """Return the Firestore client. Must call init_firebase() first."""
    return firestore.client()


def get_bucket():
    """Return the Cloud Storage bucket. Must call init_firebase() first."""
    return storage.bucket()


# Module-level accessors — initialized lazily after init_firebase() is called.
# Import these from other modules: `from app.core.firebase import db, bucket`
class _LazyDB:
    """Lazy proxy so modules can import `db` at import time."""

    _client = None

    def __getattr__(self, name):
        if _LazyDB._client is None:
            _LazyDB._client = get_db()
        return getattr(_LazyDB._client, name)


class _LazyBucket:
    """Lazy proxy so modules can import `bucket` at import time."""

    _bucket = None

    def __getattr__(self, name):
        if _LazyBucket._bucket is None:
            _LazyBucket._bucket = get_bucket()
        return getattr(_LazyBucket._bucket, name)


db = _LazyDB()
bucket = _LazyBucket()
