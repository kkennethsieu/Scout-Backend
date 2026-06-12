# iOS Upload Contract — Review & Spot Submission

This is the agreement between the Scout iOS app and the backend for submitting
reviews (and new spots). It describes **exactly** what the client must send so
that requests are accepted. The backend enforces every rule here; violating one
returns a `4xx` with a `code` field (see [Errors](#errors)).

> **The single most important rule:** photos must be uploaded as **JPEG**. iPhones
> capture **HEIC** by default, so the app **must transcode every image to JPEG
> before upload**. Raw HEIC bytes are rejected with `PHOTO_INVALID_FORMAT`.

---

## Endpoints

| Purpose                                       | Method  | Path                       |
| :-------------------------------------------- | :------ | :------------------------- |
| Add a review to an existing spot              | `POST`  | `/spots/{spot_id}/reviews` |
| Create a new spot + its first review (atomic) | `POST`  | `/spots/with-review`       |
| Update own profile (incl. avatar)             | `PATCH` | `/users/me`                |

- **Content-Type:** `multipart/form-data` (flat — no nested JSON object).
- **Auth:** `Authorization: Bearer <Firebase ID token>` on every request.
- **Success:** `201 Created`.
  - `/spots/{spot_id}/reviews` → returns a `Review`.
  - `/spots/with-review` → returns `{ "spot": Spot, "review": Review }`.
  - `PATCH /users/me` → returns the updated `User` (`200 OK`).

### Profile photo (`PATCH /users/me`)

The profile avatar follows the **same client-side preparation as review photos**
(HEIC → downscaled JPEG, ≤ 10 MB, EXIF irrelevant — the server strips it). The
only differences: it's a **single** image sent under the field name **`photo`**
(not `photos`), and it's **optional** — omit the part to leave the existing avatar
untouched. The other profile fields (`display_name`, `home_city`, `home_country`,
`email_notifications`, `push_notifications`) are plain form fields in the same
request; `email` is read-only and ignored.

---

## Photos

| Rule       | Value                             | Enforced by            |
| :--------- | :-------------------------------- | :--------------------- |
| Format     | **JPEG only** (`image/jpeg`)      | `PHOTO_INVALID_FORMAT` |
| Count      | **1–5** per submission            | `PHOTO_COUNT_INVALID`  |
| Size       | **≤ 10 MB** per file              | `PHOTO_TOO_LARGE`      |
| Field name | `photos` (repeated once per file) | —                      |

**Each photo is its own multipart part, all using the same field name `photos`.**
The server reads them as an ordered list; the first photo becomes the spot's
cover photo, so send them in the order the user arranged them.

### Required client-side preparation

Because iPhone source images are HEIC and can be 5–12 MB at full resolution, the
app must, for each selected image:

1. **Decode** the picked asset to a `UIImage` (respecting EXIF orientation —
   `UIImage` does this automatically).
2. **Downscale** the longest edge to a sane max (recommend **2048 px**). Full
   48 MP frames waste bandwidth and add nothing for spot photos.
3. **Encode to JPEG** with `jpegData(compressionQuality:)`. Start at **0.8**.
4. **Verify size** ≤ 10 MB. If still over, re-encode at a lower quality
   (step down 0.7 → 0.6 …) until it fits. With a 2048 px cap this almost never
   triggers; resulting files are typically 1–3 MB.

> Always send the JPEG produced in step 3 — never the original `PHPickerResult`
> file representation (that's HEIC).

---

## Fields

The submission is a flat set of form fields. **Only `photos` and
`overall_rating` are required.** Every other field is optional — and _omitting_ a
field is meaningful: it means "the submitter didn't answer," which is distinct
from a negative answer.

### Required

| Field            | Type          | Rule                  |
| :--------------- | :------------ | :-------------------- |
| `photos`         | file × (1–10) | see [Photos](#photos) |
| `overall_rating` | int           | `1`–`5`               |

### New-spot only (`/spots/with-review`)

| Field  | Type   | Rule         |
| :----- | :----- | :----------- |
| `name` | string | 1–200 chars  |
| `lat`  | float  | `-90`…`90`   |
| `lng`  | float  | `-180`…`180` |

The backend reverse-geocodes `lat`/`lng` into city/region/country, so the client
does **not** send those.

### Optional content fields

| Field                  | Type          | Allowed values / limit                                                 |
| :--------------------- | :------------ | :--------------------------------------------------------------------- |
| `notes`                | string        | ≤ 2000 chars                                                           |
| `gear_recommendations` | string        | ≤ 2000 chars                                                           |
| `composition_hints`    | string        | ≤ 2000 chars                                                           |
| `access_level`         | enum          | `Easy` · `Moderate` · `Difficult`                                      |
| `entrance_fee`         | number (USD)  | `≥ 0`, e.g. `12.50`. `0` = free; omit = not answered. Rounded to 2 dp. |
| `crowd_level`          | enum          | `Empty` · `Light` · `Moderate` · `Crowded`                             |
| `best_time_of_day`     | enum list     | `Sunrise` · `GoldenHour` · `BlueHour` · `Midday` · `Night`             |
| `best_season`          | enum list     | `Spring` · `Summer` · `Fall` · `Winter` · `YearRound`                  |
| `permit_required`      | tristate bool | `true` · `false` · _(omit)_                                            |
| `drone_allowed`        | tristate bool | `true` · `false` · _(omit)_                                            |
| `tripod_allowed`       | tristate bool | `true` · `false` · _(omit)_                                            |

### Encoding rules

- **Enum strings are exact, capitalized, case-sensitive.** Send `"Easy"`, never
  `"easy"`. A wrong value returns `INVALID_ENUM_VALUE`.
- **`entrance_fee` is a number, not an enum.** Send a numeric string like `"12.50"`
  (`"0"` = free). The server rounds to 2 decimals. Omit it (don't send `""`) to
  mean "didn't answer" — that's distinct from `0`.
- **Lists** (`best_time_of_day`, `best_season`): send a **separate part per
  value, repeating the field name** — exactly like `photos`. Do not send a JSON
  array or a comma-joined string.
- **Tristate booleans:** send the literal string `"true"` or `"false"`. To say
  "unknown / didn't answer," **omit the field entirely** — do not send an empty
  string. The backend stores `null`, and spot aggregates surface `null` until
  someone answers.
- **Optional fields in general:** to leave anything blank, just don't add the
  part. Don't send empty strings — for the constrained enums an empty string is
  an invalid value.

---

## Swift reference implementation

A minimal, dependency-free `URLSession` multipart builder. Adapt the model types
to your app.

```swift
import UIKit

// MARK: - Submission payload (client-side model)

struct ReviewSubmission {
    var overallRating: Int                 // required, 1...5
    var notes: String?
    var gearRecommendations: String?
    var compositionHints: String?
    var accessLevel: String?               // "Easy" | "Moderate" | "Difficult"
    var entranceFee: Double?               // USD, >= 0. 0 = free; nil = didn't answer
    var crowdLevel: String?                // "Empty" | "Light" | "Moderate" | "Crowded"
    var bestTimeOfDay: [String]            // subset of the time enum
    var bestSeason: [String]               // subset of the season enum
    var permitRequired: Bool?              // nil = didn't answer
    var droneAllowed: Bool?
    var tripodAllowed: Bool?
}

// MARK: - Image preparation (HEIC -> JPEG, downscale, fit size)

enum ImagePrep {
    static func jpegData(from image: UIImage,
                         maxEdge: CGFloat = 2048,
                         maxBytes: Int = 10 * 1024 * 1024) -> Data? {
        let scaled = downscale(image, maxEdge: maxEdge)
        var quality: CGFloat = 0.8
        var data = scaled.jpegData(compressionQuality: quality)
        while let d = data, d.count > maxBytes, quality > 0.4 {
            quality -= 0.1
            data = scaled.jpegData(compressionQuality: quality)
        }
        return data
    }

    private static func downscale(_ image: UIImage, maxEdge: CGFloat) -> UIImage {
        let longest = max(image.size.width, image.size.height)
        guard longest > maxEdge else { return image }
        let scale = maxEdge / longest
        let newSize = CGSize(width: image.size.width * scale,
                             height: image.size.height * scale)
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        return UIGraphicsImageRenderer(size: newSize, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: newSize))
        }
    }
}

// MARK: - Multipart builder

struct MultipartBuilder {
    let boundary = "Boundary-\(UUID().uuidString)"
    private var body = Data()

    mutating func addField(_ name: String, _ value: String) {
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
        body.append("\(value)\r\n")
    }

    /// Repeats `name` once per element — the wire format for enum lists and photos.
    mutating func addList(_ name: String, _ values: [String]) {
        for v in values { addField(name, v) }
    }

    /// Only emits the part when the value is non-nil. Omission = "not answered".
    mutating func addOptional(_ name: String, _ value: String?) {
        if let value { addField(name, value) }
    }

    mutating func addBool(_ name: String, _ value: Bool?) {
        if let value { addField(name, value ? "true" : "false") }
    }

    mutating func addJPEG(_ name: String, _ data: Data, filename: String) {
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: image/jpeg\r\n\r\n")
        body.append(data)
        body.append("\r\n")
    }

    func finalize() -> Data {
        var b = body
        b.append("--\(boundary)--\r\n")
        return b
    }
}

private extension Data {
    mutating func append(_ s: String) { append(s.data(using: .utf8)!) }
}

// MARK: - Request assembly

enum ReviewUploadError: Error { case noValidPhotos, tooManyPhotos }

func makeSubmitRequest(
    url: URL,
    idToken: String,
    submission: ReviewSubmission,
    newSpot: (name: String, lat: Double, lng: Double)?,  // nil for existing-spot route
    images: [UIImage]
) throws -> URLRequest {
    let jpegs = images.compactMap { ImagePrep.jpegData(from: $0) }
    guard !jpegs.isEmpty else { throw ReviewUploadError.noValidPhotos }
    guard jpegs.count <= 10 else { throw ReviewUploadError.tooManyPhotos }

    var mp = MultipartBuilder()

    // Required
    mp.addField("overall_rating", String(submission.overallRating))

    // New-spot fields (only for /spots/with-review)
    if let spot = newSpot {
        mp.addField("name", spot.name)
        mp.addField("lat", String(spot.lat))
        mp.addField("lng", String(spot.lng))
    }

    // Optional scalars
    mp.addOptional("notes", submission.notes)
    mp.addOptional("gear_recommendations", submission.gearRecommendations)
    mp.addOptional("composition_hints", submission.compositionHints)
    mp.addOptional("access_level", submission.accessLevel)
    // entrance_fee is a number: send 2-dp string, omit when not answered
    if let fee = submission.entranceFee {
        mp.addField("entrance_fee", String(format: "%.2f", fee))
    }
    mp.addOptional("crowd_level", submission.crowdLevel)

    // Lists (repeated keys)
    mp.addList("best_time_of_day", submission.bestTimeOfDay)
    mp.addList("best_season", submission.bestSeason)

    // Tristate booleans (omitted when nil)
    mp.addBool("permit_required", submission.permitRequired)
    mp.addBool("drone_allowed", submission.droneAllowed)
    mp.addBool("tripod_allowed", submission.tripodAllowed)

    // Photos (repeated `photos` key, JPEG)
    for (i, jpeg) in jpegs.enumerated() {
        mp.addJPEG("photos", jpeg, filename: "photo_\(i).jpg")
    }

    var req = URLRequest(url: url)
    req.httpMethod = "POST"
    req.setValue("Bearer \(idToken)", forHTTPHeaderField: "Authorization")
    req.setValue("multipart/form-data; boundary=\(mp.boundary)",
                 forHTTPHeaderField: "Content-Type")
    req.httpBody = mp.finalize()
    return req
}
```

### Example: the bytes on the wire

A review with one photo, a rating, two seasons, and one tristate answered looks
like this (boundaries abbreviated):

```
--B
Content-Disposition: form-data; name="overall_rating"

5
--B
Content-Disposition: form-data; name="best_season"

Summer
--B
Content-Disposition: form-data; name="best_season"

Fall
--B
Content-Disposition: form-data; name="tripod_allowed"

true
--B
Content-Disposition: form-data; name="photos"; filename="photo_0.jpg"
Content-Type: image/jpeg

<binary JPEG bytes>
--B--
```

Note `best_season` appears twice and there is **no** `permit_required` /
`drone_allowed` part because the user didn't answer them.

---

## Errors

On failure the body is `{ "detail": <message>, "code": <CODE> }`. Map these to
user-facing messaging:

| HTTP | `code`                                      | Cause                                                   | Client action                                                             |
| :--- | :------------------------------------------ | :------------------------------------------------------ | :------------------------------------------------------------------------ |
| 400  | `PHOTO_INVALID_FORMAT`                      | A photo wasn't JPEG                                     | Bug in transcode step — re-encode before retry                            |
| 400  | `PHOTO_TOO_LARGE`                           | A photo > 10 MB                                         | Re-compress at lower quality / smaller edge                               |
| 400  | `PHOTO_COUNT_INVALID`                       | 0 photos, or > 10                                       | Enforce 1–10 in the picker                                                |
| 400  | `INVALID_ENUM_VALUE`                        | A field had a value outside its vocabulary              | Fix the string (case-sensitive)                                           |
| 401  | `INVALID_TOKEN` / `MISSING_TOKEN`           | Bad/absent ID token                                     | Refresh the Firebase ID token, retry                                      |
| 404  | `SPOT_NOT_FOUND`                            | `spot_id` doesn't exist (existing-spot route)           | —                                                                         |
| 409  | `SPOT_ALREADY_EXISTS`                       | New spot within 50 m of an existing one                 | Deep-link to existing spot — body carries `spot_id`, `name`, `distance_m` |
| 422  | —                                           | Required field missing / malformed (FastAPI validation) | Fix the payload                                                           |
| 422  | `GEOCODING_NO_LOCATION`                     | Coordinate has no resolvable city/country (ocean, remote wilderness) | **Don't retry** — ask the user to pick a different/more precise location  |
| 503  | `GEOCODING_FAILED` / `UPSTREAM_UNAVAILABLE` | Backend dependency unavailable                          | Retry with backoff                                                        |

> **`SPOT_ALREADY_EXISTS` is expected, not exceptional.** When the user tries to
> create a spot that already exists nearby, switch the flow to "add a review to
> the existing spot" using the `spot_id` from the error body.

---

## Checklist before shipping the iOS submission flow

- [ ] Every image is transcoded to **JPEG** (never raw HEIC).
- [ ] Longest edge capped (~2048 px); each file verified ≤ 10 MB.
- [ ] 1–10 photos enforced in the UI before the request.
- [ ] Enum values sent as exact capitalized strings.
- [ ] Enum lists and `photos` sent as **repeated keys**, not arrays/CSV.
- [ ] Tristate booleans **omitted** (not empty/false) when unanswered.
- [ ] `Authorization: Bearer <Firebase ID token>` on every request.
- [ ] `SPOT_ALREADY_EXISTS` (409) handled as a redirect to the existing spot.
