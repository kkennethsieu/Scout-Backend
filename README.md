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
| **PATCH** | `/users/me` | ✓ | Update own profile location (`home_city` / `home_country`); partial update, blank clears a field |
| **GET** | `/spots` | ✓ | Find nearby spots within radius (lat/lng/radius_km) |
| **GET** | `/spots/{id}` | ✓ | Retrieve a single spot's details and computed aggregates |
| **GET** | `/spots/{id}/reviews` | ✓ | Fetch paginated review feed for a spot |
| **POST** | `/spots/{id}/reviews` | ✓ | Submit a new review for an existing spot (multipart JPEG, 1–10 photos) |
| **POST** | `/spots/with-review` | ✓ | Submit a brand new spot and its first review atomically (409 if a spot already exists within 50 m) |
| **GET** | `/reviews/{id}` | ✓ | Retrieve detailed info for a single review |
| **DELETE** | `/reviews/{id}` | ✓ | Delete the caller's own review; reverses spot aggregates (deletes the spot if it was its last review). 403 if not the author |
| **GET** | `/users/me/reviews` | ✓ | Fetch the current user's submitted reviews paginated |

---

## Error Codes
`SPOT_NOT_FOUND`, `REVIEW_NOT_FOUND`, `USER_NOT_FOUND`, `SPOT_ALREADY_EXISTS`, `REVIEW_ALREADY_EXISTS`, `FORBIDDEN`, `PHOTO_INVALID_FORMAT`, `PHOTO_TOO_LARGE`, `PHOTO_COUNT_INVALID`, `INVALID_ENUM_VALUE`, `INVALID_CURSOR`, `GEOCODING_FAILED`, `INVALID_TOKEN`, `MISSING_TOKEN`, `RATE_LIMITED`, `INTERNAL_ERROR`, `UPSTREAM_UNAVAILABLE`.

`SPOT_ALREADY_EXISTS` (409) carries extra fields beyond `{detail, code}`: `spot_id`, `name`, `distance_m` — so the client can deep-link to the existing spot.

`REVIEW_ALREADY_EXISTS` (409) is returned by `POST /spots/{id}/reviews` when the current user has already reviewed that spot (one review per user per spot). It carries `spot_id` and `review_id` so the client can deep-link to the existing review.

`FORBIDDEN` (403) is returned by `DELETE /reviews/{id}` when the caller is not the review's author.

A fetched review (`GET /reviews/{id}`, feeds, and the `with-review` response) carries its spot's location denormalized at create time — `spot_name`, `public_lat`, `public_lng`, `city`, `admin_area` — so the client can render/map a review without a second spot lookup. These are always present on every review.

`GET /users/me` returns a `review_count` field — the user's number of reviews, maintained atomically as reviews are created and deleted (no per-request count query needed). It also returns `home_city` / `home_country` (where the user is from), `null` until set via `PATCH /users/me`.

## Review Submission Contract

Reviews are sent as flat **multipart/form-data** (a Pydantic form-model binds the fields):

- **Required:** `photos` (repeated key, 1–10 JPEGs, ≤10 MB each) and `overall_rating` (1–5).
- **Everything else is optional.** An omitted field means "the submitter didn't answer" — which is distinct from a negative answer.
- **Tristate booleans** `permit_required` / `drone_allowed` / `tripod_allowed`: `true` / `false` / omitted (unknown). Spot aggregates surface `null` for a field nobody has answered yet.
- **`entrance_fee`** is a **USD number** (e.g. `12.50`), not a vocabulary. `0` = free (confirmed); blank/omitted = not answered. Server rounds to 2 decimals. The permit concept lives solely on `permit_required`. Spots expose `avg_entrance_fee` (mean of reported fees).
- **Constrained vocabularies** (exact capitalized strings — frontend and backend must match):
  - `access_level`: `Easy`, `Moderate`, `Difficult`
  - `crowd_level`: `Empty`, `Light`, `Moderate`, `Crowded`
  - `best_time_of_day` (list): `Sunrise`, `GoldenHour`, `BlueHour`, `Midday`, `Night`
  - `best_season` (list): `Spring`, `Summer`, `Fall`, `Winter`, `YearRound`
- **Text fields** `notes`, `gear_recommendations`, `composition_hints` are capped at 2000 chars.

> **iOS clients:** see [docs/ios-upload-contract.md](docs/ios-upload-contract.md) for the full client-side contract, including the required **HEIC → JPEG** transcode, multipart encoding rules, a Swift `URLSession` reference implementation, and error handling.
