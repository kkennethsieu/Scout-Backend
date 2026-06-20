# Scout Backend

Backend services for **Scout** — a high-fidelity photo spot discovery mobile application.

## Tech Stack & Architecture

- **Core**: FastAPI (Python 3.12), served by Uvicorn
- **Database / Storage**: Firebase Firestore & Cloud Storage (Admin SDK)
- **External services**: Google Geocoding API (reverse-geocoding new spots)
- **Authentication**: Firebase ID Tokens (`Bearer <token>`) verified via Admin SDK
- **Abuse protection**: per-user rate limiting + Firebase App Check (see [Security](#security))
- **Hosting**: Google Cloud Run (containerized), with secrets in Secret Manager
- **CI/CD**: GitHub Actions — tests on every PR, auto-deploy to Cloud Run on merge to `main`

---

## Directory Structure

.

```
scout-backend/
├── pyproject.toml              # Dependencies and project tools configuration
├── README.md                   # Setup and usage guide
├── Makefile                    # Developer shortcuts
├── Dockerfile                  # Cloud Run container image
├── .dockerignore               # Build-context exclusions (secrets, caches, tests)
├── firebase.json               # Firebase config (Firestore/Storage rules, Hosting, emulators)
├── firestore.rules             # Deny-all Firestore client rules
├── firestore.indexes.json      # Firestore composite query indexes
├── storage.rules               # Deny-all Cloud Storage client rules
├── .github/workflows/          # CI/CD — test + deploy pipeline
├── app/
│   ├── main.py                 # App, lifespan, CORS, exception handlers, router wiring
│   ├── core/                   # config, firebase init, security (auth + App Check),
│   │                           #   ratelimit, errors
│   ├── schemas/                # Request/response validation schemas
│   ├── services/               # DB, storage, geocoding & aggregate calculation logic
│   └── api/v1/                 # Versioned router definitions + shared deps
├── docs/                       # iOS upload contract and other client docs
├── public/                     # Static legal pages (privacy / terms) for Firebase Hosting
├── scripts/                    # Data seeding scripts (fake + real)
└── tests/
    ├── conftest.py             # Emulator configuration & test fixtures
    ├── helpers/                # Emulator ID token minter
    ├── unit/                   # Math, aggregations, schemas and validation tests
    └── integration/            # Full client HTTP flow tests
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

3. **Configure environment** — copy `.env.example` to `.env` and fill it in
   (see [Environment Variables](#environment-variables)).

4. **Start the Firebase Emulator Suite** (Terminal 1):

   ```bash
   make emulators
   ```

5. **Start the FastAPI Backend** (Terminal 2):

   ```bash
   make dev          # uvicorn with --reload on :8000, loads .env
   ```

6. **Expose locally to a physical iOS device** (Terminal 3):
   ```bash
   ngrok http 8000
   # or: make dev-device  (binds 0.0.0.0, loads .env.device)
   ```

---

## Environment Variables

Loaded from environment or a local `.env` file (gitignored). On Cloud Run these are
set on the service; secrets come from Secret Manager (see [Deployment](#deployment)).

| Variable                    | Required | Default    | Notes                                                                                                                              |
| :-------------------------- | :------- | :--------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| `STORAGE_BUCKET`            | ✓        | —          | Cloud Storage bucket for photos                                                                                                    |
| `GEOCODING_API_KEY`         | ✓        | —          | Google Geocoding API key. **Secret Manager in prod**, never a plaintext env var                                                    |
| `ENV`                       | —        | `dev`      | `dev` \| `prod` \| `test`                                                                                                          |
| `FIREBASE_CREDENTIALS_PATH` | —        | _(unset)_  | Local: path to a service-account JSON. **Unset on Cloud Run** → uses Application Default Credentials (the runtime service account) |
| `MAX_PHOTO_BYTES`           | —        | `10485760` | Per-photo size cap (10 MB)                                                                                                         |
| `SPOT_CACHE_TTL_SECONDS`    | —        | `45`       | TTL for the in-process spots snapshot backing nearby/search scans                                                                  |
| `CORS_ORIGINS`              | —        | `["*"]`    | Allowed origins (JSON list). iOS ignores CORS; this is for the eventual web client + Swagger UI                                    |
| `APP_CHECK_ENFORCED`        | —        | `false`    | When `false`, missing/invalid App Check tokens are logged but allowed. Flip to `true` once the iOS app ships the App Check SDK     |
| `PRIVACY_POLICY_URL`        | —        | hosted URL | Surfaced via `GET /legal`                                                                                                          |
| `TERMS_OF_SERVICE_URL`      | —        | hosted URL | Surfaced via `GET /legal`                                                                                                          |
| `LEGAL_UPDATED_AT`          | —        | ISO date   | Last revision date shown by `GET /legal`                                                                                           |

---

## Test Suite

Run all unit and integration tests under the isolated Firebase Emulator Suite:

```bash
make test
```

Linting and style checks:

```bash
make lint
```

---

## Deployment

The service runs on **Google Cloud Run** (project `scout-497021`, region `us-west2`,
service `scout-backend`).

### Container

The `Dockerfile` builds a slim Python 3.12 image, installs the package, and runs
Uvicorn bound to Cloud Run's injected `$PORT` with a single worker (Cloud Run scales
horizontally, not vertically).

### Continuous Deployment

`.github/workflows/test.yml` defines the full pipeline:

1. On every **push and PR** to `main` → the `test` job runs the suite under the
   Firebase emulators.
2. On **push to `main` only** (after tests pass) → the `deploy` job authenticates to
   GCP via **Workload Identity Federation** (keyless — no stored service-account key)
   and runs `gcloud run deploy scout-backend --source .`

So **merging to `main` is the deploy action.** During development, work on a branch
and open a PR (tests run, nothing deploys); merge only when ready to ship.

GitHub repo **variables** used by the deploy job (no secrets needed with WIF):
`GCP_WIF_PROVIDER`, `GCP_DEPLOYER_SA`.

### Secrets & IAM

- **`GEOCODING_API_KEY`** is stored in **Secret Manager** and referenced by the
  service (not a plaintext env var).
- The Cloud Run **runtime service account** needs: `roles/datastore.user` (Firestore),
  `roles/storage.objectAdmin` (photo uploads), and `roles/secretmanager.secretAccessor`
  (the API key). Photos are served via public URLs, so the bucket grants
  `allUsers:objectViewer` (public read).

### Scaling / cost

Scales to zero (`min-instances=0`), capped at `max-instances=20`, concurrency 80.
A billing budget alert is recommended — instance caps bound compute but not
Firestore/Storage/egress.

### Manual deploy (escape hatch)

```bash
make deploy-dev       # gcloud run deploy scout-backend-dev --source . (us-central1)
make deploy-hosting   # firebase deploy --only hosting (legal pages)
```

---

## Security

- **Authentication** — every `✓` endpoint requires a Firebase ID token
  (`Authorization: Bearer <token>`), verified via the Admin SDK. Missing/invalid →
  401 `MISSING_TOKEN` / `INVALID_TOKEN`.
- **Authorization** — user-scoped resources (`/users/me/...`) are enforced by path;
  review deletion checks authorship (403 `FORBIDDEN`).
- **Rate limiting** — per-user (keyed on Firebase uid) limits on write endpoints,
  returning **429 `RATE_LIMITED`** with a `Retry-After` header when exceeded:

  | Endpoint                                              | Limit    |
  | :---------------------------------------------------- | :------- |
  | `POST /spots/{id}/reviews`, `POST /spots/with-review` | 10 / min |
  | `PATCH /users/me`                                     | 20 / min |
  | `DELETE /users/me`                                    | 10 / min |
  | `POST`/`PATCH`/`DELETE /users/me/lists...`            | 30 / min |
  | `PATCH /users/me/spots/{id}/lists`                    | 60 / min |
  | `DELETE /reviews/{id}`                                | 30 / min |

  > Limits are in-process per Cloud Run instance, so the effective ceiling scales
  > with instance count. Sufficient to throttle a single abuser; swap the storage
  > backend in `app/core/ratelimit.py` for Redis when exact global limits are needed.

- **App Check** — requests to spots/reviews/users/lists routes may carry a
  Firebase App Check token (`X-Firebase-AppCheck` header), verified server-side.
  Controlled by `APP_CHECK_ENFORCED` (default `false` = log-only, so the API keeps
  working before the iOS app ships the SDK). When enforced, missing/invalid tokens →
  401 `MISSING_APP_CHECK` / `INVALID_APP_CHECK`. `/` and `/health` stay open.

---

## API Contract

| Method     | Path                              | Auth | Purpose                                                                                                                                                                                            |
| :--------- | :-------------------------------- | :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **GET**    | `/health`                         | —    | Liveness check (Cloud Run)                                                                                                                                                                         |
| **GET**    | `/legal`                          | —    | Public links to the hosted privacy policy + terms of service                                                                                                                                       |
| **GET**    | `/users/me`                       | ✓    | Fetch or initialize current user doc (read-through)                                                                                                                                                |
| **PATCH**  | `/users/me`                       | ✓    | Update own profile (multipart): `display_name`, `home_city`, `home_country`, notification prefs, optional profile `photo`. Partial update; `email` is read-only                                    |
| **DELETE** | `/users/me`                       | ✓    | Delete the caller's account: anonymizes their reviews, hard-deletes the user doc, and deletes the Firebase Auth user                                                                               |
| **GET**    | `/spots`                          | ✓    | Find nearby spots within radius (lat/lng/radius_km)                                                                                                                                                |
| **GET**    | `/spots/search`                   | ✓    | Search spots by name (global, not geo-scoped)                                                                                                                                                      |
| **GET**    | `/spots/{id}`                     | ✓    | Retrieve a single spot's details and computed aggregates                                                                                                                                           |
| **GET**    | `/spots/{id}/reviews`             | ✓    | Fetch paginated review feed for a spot. `sort`: `newest` (default) \| `highest_rated` \| `lowest_rated` \| `scout` (see [Review Sorting](#review-sorting))                                          |
| **GET**    | `/spots/{id}/reviews/search`      | ✓    | Search a spot's reviews by review text (`notes` / `gear_recommendations` / `composition_hints`), paginated (`q`, `limit`, `cursor`, `sort` — same modes as the feed)                               |
| **POST**   | `/spots/{id}/reviews`             | ✓    | Submit a new review for an existing spot (multipart JPEG, 1–5 photos)                                                                                                                              |
| **POST**   | `/spots/with-review`              | ✓    | Submit a brand new spot and its first review atomically (409 if a spot already exists within 50 m)                                                                                                 |
| **GET**    | `/reviews/{id}`                   | ✓    | Retrieve detailed info for a single review                                                                                                                                                         |
| **DELETE** | `/reviews/{id}`                   | ✓    | Delete the caller's own review; reverses spot aggregates (deletes the spot if it was its last review). 403 if not the author                                                                       |
| **GET**    | `/users/me/reviews`               | ✓    | Fetch the current user's submitted reviews paginated                                                                                                                                               |
| **GET**    | `/users/me/lists`                 | ✓    | The caller's saved lists (Favorites first, auto-created) plus a `memberships` map — `{ lists, memberships }` in one snapshot                                                                       |
| **POST**   | `/users/me/lists`                 | ✓    | Create a new list (JSON `{ name, description? }`)                                                                                                                                                  |
| **PATCH**  | `/users/me/lists/{id}`            | ✓    | Edit `name` / `description`. 400 `FAVORITES_PROTECTED` for Favorites                                                                                                                               |
| **DELETE** | `/users/me/lists/{id}`            | ✓    | Delete a list. 400 `FAVORITES_PROTECTED` for Favorites                                                                                                                                             |
| **GET**    | `/users/me/lists/{id}/spots`      | ✓    | Paginated spots in a list, newest first (missing spots skipped)                                                                                                                                    |
| **PATCH**  | `/users/me/spots/{spot_id}/lists` | ✓    | Set the exact set of lists a spot belongs to (JSON `{ list_ids }`); diffed server-side in one transaction. The only membership write path; returns the refreshed `{ lists, memberships }` overview |

---

## Error Codes

All errors return a consistent `{ detail, code }` JSON body (some carry extra fields).

`SPOT_NOT_FOUND`, `REVIEW_NOT_FOUND`, `USER_NOT_FOUND`, `LIST_NOT_FOUND`, `SPOT_ALREADY_EXISTS`, `REVIEW_ALREADY_EXISTS`, `FAVORITES_PROTECTED`, `LIST_LIMIT_REACHED`, `FORBIDDEN`, `PHOTO_INVALID_FORMAT`, `PHOTO_TOO_LARGE`, `PHOTO_COUNT_INVALID`, `INVALID_ENUM_VALUE`, `INVALID_CURSOR`, `GEOCODING_FAILED`, `GEOCODING_NO_LOCATION`, `INVALID_TOKEN`, `MISSING_TOKEN`, `MISSING_APP_CHECK`, `INVALID_APP_CHECK`, `RATE_LIMITED`, `INTERNAL_ERROR`, `UPSTREAM_UNAVAILABLE`.

`SPOT_ALREADY_EXISTS` (409) carries extra fields beyond `{detail, code}`: `spot_id`, `name`, `distance_m` — so the client can deep-link to the existing spot.

`REVIEW_ALREADY_EXISTS` (409) is returned by `POST /spots/{id}/reviews` when the current user has already reviewed that spot (one review per user per spot). It carries `spot_id` and `review_id` so the client can deep-link to the existing review.

`FORBIDDEN` (403) is returned by `DELETE /reviews/{id}` when the caller is not the review's author.

`RATE_LIMITED` (429) includes a `Retry-After` header and a `retry_after` (seconds) field.

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
- **No dangling refs.** A spot is deleted when its last review is removed
  (`DELETE /reviews/{id}`). When that happens, the spot's id is scrubbed from
  **every** user's list (a collection-group sweep), so `spot_count` stays truthful
  rather than counting a spot that no longer renders. As a safety net, reading a
  list also self-heals — any id that no longer resolves is pruned on read — so lists
  corrupted before this behavior existed converge to the correct count.

## Review Sorting

Both spot-scoped review lists — the feed (`GET /spots/{id}/reviews`) and search
(`GET /spots/{id}/reviews/search`) — accept a `sort` query param:

| `sort`          | Order                                                                          |
| :-------------- | :----------------------------------------------------------------------------- |
| `newest`        | **Default.** Most recent first (`created_at` desc).                            |
| `highest_rated` | Highest `overall_rating` first, ties broken newest-first.                      |
| `lowest_rated`  | Lowest `overall_rating` first, ties broken newest-first.                       |
| `scout`         | **Scout Sort** — a quality blend (below) surfacing the best reviews first.     |

**Scout Sort** ranks each review by a 0–1 quality score:

```
score = 0.5·(overall_rating / 5)
      + 0.3·recency_decay        # exp half-life of 30 days on review age
      + 0.2·richness             # fraction of: >1 photo, has notes, gear, composition
```

So a high-rated, recent, detailed review floats above a low-rated, old, or sparse one.
Sorting and pagination run **in memory over a single spot's reviews** (bounded per spot); the
scale path is a denormalized `scout_score` field with index-backed sorts. Pagination is unchanged
— an opaque `cursor` (an unknown cursor → 400 `INVALID_CURSOR`).

## Review Submission Contract

Reviews are sent as flat **multipart/form-data** (a Pydantic form-model binds the fields):

- **Required:** `photos` (repeated key, 1–5 JPEGs, ≤10 MB each) and `overall_rating` (1–5).
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
