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
| **GET** | `/legal` | — | Public links to the hosted privacy policy + terms of service |
| **GET** | `/users/me` | ✓ | Fetch or initialize current user doc (read-through) |
| **PATCH** | `/users/me` | ✓ | Update own profile (multipart): `display_name`, `home_city`, `home_country`, notification prefs, optional profile `photo`. Partial update; `email` is read-only |
| **GET** | `/spots` | ✓ | Find nearby spots within radius (lat/lng/radius_km) |
| **GET** | `/spots/{id}` | ✓ | Retrieve a single spot's details and computed aggregates |
| **GET** | `/spots/{id}/reviews` | ✓ | Fetch paginated review feed for a spot |
| **POST** | `/spots/{id}/reviews` | ✓ | Submit a new review for an existing spot (multipart JPEG, 1–10 photos) |
| **POST** | `/spots/with-review` | ✓ | Submit a brand new spot and its first review atomically (409 if a spot already exists within 50 m) |
| **GET** | `/reviews/{id}` | ✓ | Retrieve detailed info for a single review |
| **DELETE** | `/reviews/{id}` | ✓ | Delete the caller's own review; reverses spot aggregates (deletes the spot if it was its last review). 403 if not the author |
| **GET** | `/users/me/reviews` | ✓ | Fetch the current user's submitted reviews paginated |
| **GET** | `/users/me/lists` | ✓ | The caller's saved lists (Favorites first, auto-created) plus a `memberships` map — `{ lists, memberships }` in one snapshot |
| **POST** | `/users/me/lists` | ✓ | Create a new list (JSON `{ name, description? }`) |
| **PATCH** | `/users/me/lists/{id}` | ✓ | Edit `name` / `description`. 400 `FAVORITES_PROTECTED` for Favorites |
| **DELETE** | `/users/me/lists/{id}` | ✓ | Delete a list. 400 `FAVORITES_PROTECTED` for Favorites |
| **GET** | `/users/me/lists/{id}/spots` | ✓ | Paginated spots in a list, newest first (missing spots skipped) |
| **PATCH** | `/users/me/spots/{spot_id}/lists` | ✓ | Set the exact set of lists a spot belongs to (JSON `{ list_ids }`); diffed server-side in one transaction. The only membership write path; returns the refreshed `{ lists, memberships }` overview |

---

## Error Codes
`SPOT_NOT_FOUND`, `REVIEW_NOT_FOUND`, `USER_NOT_FOUND`, `LIST_NOT_FOUND`, `SPOT_ALREADY_EXISTS`, `REVIEW_ALREADY_EXISTS`, `FAVORITES_PROTECTED`, `LIST_LIMIT_REACHED`, `FORBIDDEN`, `PHOTO_INVALID_FORMAT`, `PHOTO_TOO_LARGE`, `PHOTO_COUNT_INVALID`, `INVALID_ENUM_VALUE`, `INVALID_CURSOR`, `GEOCODING_FAILED`, `INVALID_TOKEN`, `MISSING_TOKEN`, `RATE_LIMITED`, `INTERNAL_ERROR`, `UPSTREAM_UNAVAILABLE`.

`SPOT_ALREADY_EXISTS` (409) carries extra fields beyond `{detail, code}`: `spot_id`, `name`, `distance_m` — so the client can deep-link to the existing spot.

`REVIEW_ALREADY_EXISTS` (409) is returned by `POST /spots/{id}/reviews` when the current user has already reviewed that spot (one review per user per spot). It carries `spot_id` and `review_id` so the client can deep-link to the existing review.

`FORBIDDEN` (403) is returned by `DELETE /reviews/{id}` when the caller is not the review's author.

A fetched review (`GET /reviews/{id}`, feeds, and the `with-review` response) carries its spot's location denormalized at create time — `spot_name`, `public_lat`, `public_lng`, `city`, `admin_area` — so the client can render/map a review without a second spot lookup. These are always present on every review.

`GET /users/me` returns a `review_count` field — the user's number of reviews, maintained atomically as reviews are created and deleted (no per-request count query needed). It also returns `home_city` / `home_country` (where the user is from), `null` until set via `PATCH /users/me`, and `email_notifications` / `push_notifications` (notification preferences, both default `true`).

## Profile Updates (`PATCH /users/me`)

Profile edits are sent as **multipart/form-data** (so the optional avatar can ride along):

- **Editable:** `display_name`, `home_city`, `home_country`, `email_notifications`, `push_notifications`, and an optional `photo` (single JPEG, same rules as review photos — see [docs/ios-upload-contract.md](docs/ios-upload-contract.md)).
- **`email` is read-only** — it's the Firebase Auth login identity and is never written from this endpoint.
- **Partial update:** only the fields you send change. A blank `home_city` / `home_country` clears it (`null`); a blank `display_name` is ignored (it's non-nullable). Omitted notification booleans are left unchanged.
- **Photo:** when a `photo` part is present it's validated (JPEG, ≤10 MB), EXIF-stripped, uploaded to Cloud Storage under `users/{uid}/avatar/`, and becomes `photo_url`; the previous avatar is pruned. A non-JPEG → 400 `PHOTO_INVALID_FORMAT`.

## Saved Lists

Users can save spots into lists (e.g. "Favorites", "Roadtrip"). Lists are a
per-user Firestore subcollection — `users/{uid}/lists/{listId}` — so ownership is
enforced by the path; there's no cross-user access and no owner check.

- **Favorites** lives at the fixed id `favorites`, always exists (auto-created
  on first read or first membership write — the client never creates it), and
  **cannot be renamed or deleted** (400 `FAVORITES_PROTECTED`). All other lists
  get auto-generated ids.
  Every list carries an **`is_system`** boolean (true only for Favorites) so the
  client can hide Edit/Delete affordances without hardcoding the `favorites` id.
- **Description** is an optional free-text field (≤200 chars) on any list. It's
  partial-update on `PATCH` — omit it to leave it unchanged, send blank/null to
  clear it.
- **Membership** is just a spot id appearing in a list's `spot_ids` array
  (insertion order, newest last). A spot can belong to many lists — no central
  record. `spot_count` is derived (`len(spot_ids)`); the single write path is a
  read-modify-write **transaction** so the count can't drift, and re-sending the
  same set is **idempotent**.
- **One write path:** all membership changes — add, remove, across any number of
  lists — go through `PATCH /users/me/spots/{spot_id}/lists`, which sends the full
  desired set for one spot and diffs current vs. requested server-side in a single
  transaction. The iOS "Add to list" sheet (opened from the heart) is the sole
  caller; there are no per-spot add/remove endpoints.
- **Overview** (`GET /users/me/lists`) returns `{ lists, memberships }` in one
  atomic snapshot: each list carries a derived `cover_photo_url` (the newest spot's
  cover photo) and `spot_count` (but **not** its raw `spot_ids`), while
  `memberships` maps every list id → its `spot_ids` (all lists, empty → `[]`) so
  the client can hydrate heart/checkbox state without a second call. `PATCH
  /users/me/spots/{spot_id}/lists` returns the same shape so the store re-hydrates
  atomically after each edit. Page a list's full spots via
  `GET /users/me/lists/{id}/spots` (newest first; deleted spots silently skipped).

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

## Legal pages (privacy policy & terms)

The privacy policy and terms of service are static pages in `public/`, served via
**Firebase Hosting**. The client fetches their URLs from `GET /legal` (public, no auth)
rather than hardcoding them, so they can be repointed (e.g. to a custom domain) by setting
`PRIVACY_POLICY_URL` / `TERMS_OF_SERVICE_URL` / `LEGAL_UPDATED_AT` env vars — no app release needed.

Deploy the pages:
```bash
make deploy-hosting   # firebase deploy --only hosting --project scout-497021
```
Default URLs: `https://scout-497021.web.app/privacy` and `/terms`.

> The page content in `public/privacy.html` / `public/terms.html` is a **starter template, not
> legal advice** — review it and fill the `[BRACKETED]` placeholders (operator, contact email,
> effective date, jurisdiction) before launch. The privacy policy URL also goes into App Store
> Connect metadata.
