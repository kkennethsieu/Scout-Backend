# Scout Backend

Backend services for **Scout** — a high-fidelity photo spot discovery mobile application.

## Tech Stack & Architecture
- **Core**: FastAPI (Python 3.12)
- **Database / Storage**: Firebase Firestore & Cloud Storage (Admin SDK)
- **Services**: Google Geocoding API (for reverse-geocoding spots)
- **Authentication**: Firebase ID Tokens (`Bearer <token>`) verified via Admin SDK

---

## Directory Structure

```
scout-backend/
├── pyproject.toml              # Dependencies and project tools configuration
├── README.md                   # Setup and usage guide
├── Makefile                    # Developer shortcuts
├── Dockerfile                  # Cloud Run deployment package
├── firestore.rules             # Deny-all Firestore client rules
├── firestore.indexes.json      # Firestore query indexes
├── storage.rules               # Deny-all Cloud Storage rules
├── app/
│   ├── main.py                 # Core app & lifespan configuration
│   ├── core/                   # Shared config, firebase init, auth, errors
│   ├── schemas/                # Request/response validation schemas
│   ├── services/               # DB, storage, geocoding & aggregate calculation logic
│   └── api/v1/                 # Versioned router definitions
└── tests/
    ├── conftest.py             # Emulator configurations & test fixtures
    ├── helpers/                # Emulator ID token minter
    ├── unit/                   # Math, aggregations, schemas and validation tests
    └── integration/            # Full client HTTP flow mock tests
```

---

## Getting Started

### Local Development

1. **Install Firebase Tools**:
   ```bash
   npm install -g firebase-tools
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Start the Firebase Emulator Suite** (Terminal 1):
   ```bash
   make emulators
   ```

4. **Start the FastAPI Backend** (Terminal 2):
   ```bash
   # Set up local environment variables in .env first
   make dev
   ```

5. **Expose locally to iOS via ngrok** (Terminal 3):
   ```bash
   ngrok http 8000
   ```

---

## Test Suite

To run all unit and integration tests under the isolated Firebase Emulator Suite:
```bash
make test
```

For linting and styling checks:
```bash
make lint
```

---

## API Contract

| Method | Path | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| **GET** | `/health` | — | Liveness check (Cloud Run) |
| **GET** | `/users/me` | ✓ | Fetch or initialize current user doc (read-through) |
| **GET** | `/spots` | ✓ | Find nearby spots within radius (lat/lng/radius_km) |
| **GET** | `/spots/{id}` | ✓ | Retrieve a single spot's details and computed aggregates |
| **GET** | `/spots/{id}/reviews` | ✓ | Fetch paginated review feed for a spot |
| **POST** | `/spots/{id}/reviews` | ✓ | Submit a new review for an existing spot (multipart JPEG) |
| **POST** | `/spots/with-review` | ✓ | Submit a brand new spot and its first review atomically |
| **GET** | `/reviews/{id}` | ✓ | Retrieve detailed info for a single review |
| **GET** | `/users/me/reviews` | ✓ | Fetch the current user's submitted reviews paginated |

---

## Error Codes
`SPOT_NOT_FOUND`, `REVIEW_NOT_FOUND`, `USER_NOT_FOUND`, `PHOTO_INVALID_FORMAT`, `PHOTO_TOO_LARGE`, `PHOTO_COUNT_INVALID`, `INVALID_ENUM_VALUE`, `INVALID_CURSOR`, `GEOCODING_FAILED`, `INVALID_TOKEN`, `MISSING_TOKEN`, `RATE_LIMITED`, `INTERNAL_ERROR`, `UPSTREAM_UNAVAILABLE`.
