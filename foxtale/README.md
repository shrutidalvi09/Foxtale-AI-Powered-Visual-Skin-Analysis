# 🦊 Foxtale

**AI-Powered Visual Skin Analysis** — a webcam-based face scanner that surfaces visible skin
characteristics (acne-like spots, redness, texture, dryness, oiliness, tone evenness) with an overall score, a full report and a matching Foxtale skincare routine using classic computer
vision, wrapped in a modern React/TypeScript UI and a FastAPI backend.

> ⚠️ **This is not a medical device.** Foxtale describes *visible features in a photo*. It
> never diagnoses a medical condition and never infers age, ethnicity, or health status.

---

## 1. Project structure

```text
foxtale/
├── frontend/                  React + TypeScript + Vite + Tailwind (sidebar app, light/dark theme)
│   └── src/
│       ├── pages/              Dashboard, Scan, Analysis, History, Compare, Privacy, About
│       ├── components/         Layout, CameraScanner, PhotoPanel, Skincare (product cards), ui (pills, score ring, modal)
│       ├── context/            AppContext (settings, theme, current scan, toasts)
│       ├── services/api.ts     REST client
│       └── types/analysis.ts   Shared API types
│
└── backend/                   FastAPI + SQLite (everything runs locally)
    ├── main.py                 REST API (analyze, scans, trash, report, PDF, insights, settings, privacy)
    ├── engine/                 OpenCV analysis engine v2: face detection, skin mask, Lab-space measurements,
    │                           0-100 score, per-region scores, scan quality
    ├── core/                   storage (SQLite), insights, report builder, skincare advisor, PDF report
    └── assets/                 foxtale_products.json (catalog) + products/ (product photos)
```

Scans, notes and settings are stored in `~/.foxtale_web` (override with `FOXTALE_DATA_DIR`).
Photos are saved only when **Save scan photos** is on in the Privacy page.

---

## 2. Quick start

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend runs at **http://localhost:8000**. Interactive API docs: http://localhost:8000/docs

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173** and talks to the backend at
`http://localhost:8000` by default (override with `frontend/.env` → `VITE_API_BASE_URL`,
see `.env.example`).

Open http://localhost:5173, click **Start Face Scan**, allow camera access, and capture a photo.

---

## 2b. WhatsApp reports (Meta WhatsApp Cloud API)

Before the first scan the app asks for a WhatsApp number and verifies it with a 6-digit code sent over WhatsApp.
After every scan the PDF report and a summary are sent to that number automatically.

**Try it without an account:** create `backend/.env` containing `WHATSAPP_DRY_RUN=1` and restart the backend.
Nothing is sent; the verification code and each report are printed in the backend console.

**Go live**

1. In [Meta for Developers](https://developers.facebook.com/) create an app with the **WhatsApp** product. Note the
   **Phone number ID** and create a **permanent access token** (System User in Business Settings, permission
   `whatsapp_business_messaging`). While using Meta's free test number, add each recipient number under
   *API Setup -> To* first.
2. In WhatsApp Manager -> *Message templates*, create two templates (language `English`, name as below):
   - `foxtale_verify`, category **Authentication**, with the *Copy code* button (Meta's standard one-time-passcode template).
   - `foxtale_report`, category **Utility**, header type **Document** (PDF), and this body (4 variables):

     ```text
     Hi! Your Foxtale skin analysis from {{4}} is ready. Overall score: {{1}}. {{2}} Suggested routine: {{3}} The full
     PDF report is attached. This is a visual observation, not a medical diagnosis.
     ```
3. Copy `backend/.env.example` to `backend/.env`, fill in `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`
   (and the template names if you chose different ones), then restart the backend.

Template messages are required because WhatsApp only allows free-form messages inside 24 hours of the user's last
message. Templates must be approved by Meta before they work.

**Privacy:** the number is stored only in the local database. The report (scores, findings, product suggestions and a
PDF that can include the scan photo) is uploaded to WhatsApp, which is operated by Meta. The user agrees to this when
registering, and can turn automatic sending off or remove the number on the Privacy page.

---

## 3. API design

### `POST /api/analyze`

**Request:** `multipart/form-data` with a single field `image` (JPEG/PNG/WebP).

**Success response** (`faceDetected: true`):

```json
{
  "faceDetected": true,
  "analysis": {
    "acne_like_spots": { "level": "mild", "count": 4, "confidence": 0.82 },
    "redness": { "level": "minimal", "confidence": 0.76 },
    "texture": { "level": "moderate", "confidence": 0.71 },
    "dryness_indicators": { "level": "mild", "confidence": 0.68 }
  },
  "regions": [
    {
      "region": "RIGHT CHEEK",
      "category": "Redness",
      "observation": "Visible redness detected around the right cheek area",
      "confidence": 0.76,
      "x": 0.63,
      "y": 0.52
    }
  ],
  "disclaimer": "This analysis is based only on visible features in the captured image and is not a medical diagnosis. For persistent, painful, spreading, or concerning skin changes, consult a qualified dermatologist."
}
```

`region.x` / `region.y` are normalized (0–1) coordinates within the *original captured image*,
used by the frontend to place clickable markers on the photo.

**Guidance / error response** (`faceDetected: false`):

```json
{
  "faceDetected": false,
  "error": "no_face",
  "message": "No face detected. Please position your face inside the scanning area.",
  "regions": [],
  "disclaimer": "..."
}
```

`error` is one of: `no_face`, `multiple_faces`, `poor_lighting`, `too_close`, `too_far`.

### `GET /api/health`

Simple liveness check → `{ "status": "ok" }`.

---

## 4. How the analysis works (current prototype)

1. **Decode & preprocess** — the uploaded image is decoded, resized, and lighting is checked.
2. **Face detection** — OpenCV's built-in Haar cascade (`haarcascade_frontalface_default.xml`,
   ships with `opencv-python-headless`, no extra downloads) finds the face box and rejects
   zero/multiple faces or faces that are too close/far.
3. **Region split** — the face box is divided proportionally into **forehead, left cheek, right
   cheek, nose, chin** (a lightweight approximation; no landmark model is required for the MVP).
4. **Per-region heuristics** (`services/skin_analysis.py`):
   - *Acne-like spots* — adaptive thresholding + contour filtering to find small, localized dark
     blobs against local skin tone.
   - *Redness* — HSV hue/saturation thresholding for red-toned pixel ratio.
   - *Texture* — Laplacian variance (high-frequency detail) as a roughness proxy.
   - *Dryness indicators* — low saturation + patchy local brightness as a dullness/flakiness proxy.
5. Scores are mapped to neutral levels (`minimal` / `mild` / `moderate` / `noticeable`) and a
   bounded, UX-oriented confidence value — **not** a calibrated clinical probability.

This is intentionally simple, fast, fully local, and explainable — a solid MVP baseline.

---

## 5. Replacing the prototype model with a production CV model

The interface is deliberately narrow so the heuristics can be swapped for a real model without
touching the API or frontend:

- **Face detection** (`backend/services/face_detection.py`, function `detect_face(image) -> FaceDetectionResult`)
  → swap the Haar cascade for **MediaPipe Face Detection** or **RetinaFace** for more robust,
  landmark-aware detection (also unlocks precise region cropping instead of the current
  proportional-box approximation).
- **Skin analysis** (`backend/services/skin_analysis.py`, function
  `analyze_face(regions: FaceRegions) -> (SkinAnalysis, List[RegionObservation])`)
  → replace the body of this function with calls to a trained classifier/segmentation model
  (e.g., a CNN fine-tuned on dermatology-style datasets, or a hosted vision API), as long as it
  still returns a `SkinAnalysis` + `List[RegionObservation]` in the same shape. Keep the same
  neutral, non-diagnostic language when generating `observation` strings.
- Nothing in `main.py`, the Pydantic schemas, or the frontend needs to change as long as the
  function signatures and response shapes stay the same.

---

## 6. Privacy

- 🔒 **Your face image is processed only for this analysis.** The backend does not persist
  uploaded images to disk or a database — the image lives only in memory for the duration of
  the request.
- The frontend keeps the captured photo **in memory only** (React state), never in
  `localStorage`, and clears it on retake/new scan.
- Scan **history** (in `/history`) stores only the analysis *summary* (levels + confidence +
  region text) in the browser's `localStorage` — never the image — and only if the "Save scan
  history" toggle is enabled (on by default, can be turned off).
- **Delete Scan** clears the current in-memory result; **Delete All History** wipes all locally
  stored summaries. Nothing is sent to a third party.

---

## 7. Safety / disclaimer language

The app never states a diagnosis. All findings use "visible", "detected", "may be associated
with" language, and every analysis screen shows:

> **AI Disclaimer:** This analysis is based only on visible features in the captured image and
> is not a medical diagnosis. For persistent, painful, spreading, or concerning skin changes,
> consult a qualified dermatologist.

---

## 8. Development phases (status)

| Phase | Description | Status |
|---|---|---|
| 1 | React GUI: Home, Nav, Scan page, camera preview, capture | ✅ |
| 2 | Face detection + bounding box + positioning guidance | ✅ (server-side, Haar cascade) |
| 3 | Image preprocessing: resize, crop, normalize, lighting checks | ✅ |
| 4 | Rule-based skin-analysis prototype | ✅ |
| 5 | React → FastAPI integration | ✅ |
| 6 | Results dashboard | ✅ |
| 7 | Scan history + privacy controls | ✅ (localStorage, no images stored) |
| 8 | Authentication | ⛔ Not implemented — not required for MVP |

**Suggested next steps:** client-side live face guidance via MediaPipe (currently the scanning
frame is a static guide and authoritative detection happens after capture on the backend),
persistent storage/auth if multi-device history is needed, and swapping in a production CV model
per §5.
