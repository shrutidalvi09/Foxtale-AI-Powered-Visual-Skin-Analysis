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
3. For the **weekly check-in**, create a third template, `foxtale_weekly`, category **Utility**, with this body (4 variables):

     ```text
     Hi {{1}}, here is your Foxtale week. {{2}} {{3}} Tip: {{4}}
     ```

   The check-in is sent by a scheduler inside the backend, so it only goes out while the backend is running (if the
   server was off on your chosen day, it sends the next time it is up). Turn it on under Settings.
4. Copy `backend/.env.example` to `backend/.env`, fill in `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`
   (and the template names if you chose different ones), then restart the backend.

Template messages are required because WhatsApp only allows free-form messages inside 24 hours of the user's last
message. Templates must be approved by Meta before they work.

**Privacy:** the number is stored only in the local database. The report (scores, findings, product suggestions and a
PDF that can include the scan photo) is uploaded to WhatsApp, which is operated by Meta. The user agrees to this when
registering, and can turn automatic sending off or remove the number on the Privacy page.

---

## 2c. Custom Skin AI (vision-LLM layer)

A second, optional analysis layer sits alongside the classical CV engine: `backend/core/skin_ai_*.py`. It is **off for
every user by default** and stays off until that user turns on "AI insights" consent in Settings, however the server
is configured.

**Architecture** (`backend/core/`):

| File | Role |
|---|---|
| `skin_ai_config.py` | All thresholds, model name, weights, read from env vars (see `.env.example`). |
| `skin_ai_measurer.py` | The `SkinMeasurer` interface. `HeuristicMeasurer` wraps the *existing* classical-CV engine (`engine.skin_analysis` + `engine.features`) -- no new measurement code, just a formatter. `TrainedModelMeasurer` is a documented stub for later. |
| `skin_ai_schema.py` | The Skin Analyst's output contract as Pydantic models. `region`/`type` are closed enums, so a disease name is *structurally* impossible as a finding type, not just discouraged by the prompt. |
| `skin_ai_moderation.py` | A second, word-list guardrail over every free-text field (summary, evidence, suggestions): strips any sentence naming a condition, a prescription drug, or alarmist language. |
| `skin_ai_provider.py` | `VisionLLMProvider` adapter interface. `AnthropicProvider` is the one real implementation; `MockProvider` is the dry-run/test path (no network call); `openai`/`gemini` are typed stubs that raise a clear "not implemented" error if selected. |
| `skin_ai_referral.py` | Deterministic "would a dermatologist's opinion help?" rule -- never an LLM call, works even with AI off. |
| `skin_ai_analyst.py` | Orchestration: consent -> rate limit -> cache -> call provider (with one retry on a schema failure) -> moderate -> confidence-blend -> fallback-to-measurements-only if the model never produces a valid result -> store. Called as a background task from `POST /api/analyze`, the same pattern as WhatsApp delivery. |
| `prompts/skin_analyst.v1.md` | The versioned system prompt + output schema the model is instructed to follow. Bump the filename (`v2.md`) and `PROMPT_VERSION` together if its meaning changes; the version is stored on every AI analysis row. |

**The visible-skin score is never touched by this layer.** It is computed entirely by the existing classical-CV engine
before the Skin Analyst ever runs; the AI layer only adds a separate, clearly-labelled "AI insights" section (written
findings, a summary, routine suggestions) plus the dermatologist-referral note.

**Try it with no account:** set `AI_DRY_RUN=1` in `backend/.env` (same idea as `WHATSAPP_DRY_RUN`) -- a canned,
schema-valid result is returned with no network call and no cost.

**Go live:** set `ANTHROPIC_API_KEY` (and optionally `AI_MODEL`) in `backend/.env`, then turn on "AI insights" in
Settings. See `.env.example` for every tunable (image size sent, rate limit, cache TTL, confidence-blend weights).

**New API endpoints:** `GET/PUT /api/ai/status` (consent + disclosure text), `GET /api/ai/{scanId}` (poll the result),
`POST /api/ai/{scanId}/run` (manual re-run, e.g. after turning consent on), `POST /api/ai/{scanId}/feedback`
(thumbs up/down per finding, gated behind the separate "help improve Foxtale AI" consent).

**Storage:** three new, additive SQLite tables (`ai_analyses`, `ai_cache`, `ai_feedback`) and two new settings keys
(`ai_enabled`, `ai_improve_consent`, both default `false`). Nothing existing changes shape, so older scans and an
older database both keep working unmodified -- there is no migration step beyond pulling the new code; the tables
are created with `CREATE TABLE IF NOT EXISTS` the first time the server starts.

**Privacy:** only a cropped, resized copy of the face (roughly 512px, JPEG re-encoded -- which also drops any EXIF/GPS
data) is sent, together with the numbers already measured on-device. Nothing is logged in plain application logs
except metadata (scan id, status, provider, finding count) -- never the image bytes or the model's raw response text.
Deleting a scan does not currently cascade-delete its `ai_analyses`/`ai_cache` rows (see Assumptions below); "Delete
all data" on the Privacy page does clear all three AI tables.

**Cost (rough order of magnitude, check current pricing before relying on this):** one call is one ~512px image plus
a few hundred input tokens of measurement JSON and prompt, with up to ~1400 output tokens. For a comparable current
Claude vision model this is very roughly **$0.01-0.03 per scan**, lower whenever the cache serves a repeat of the same
photo. The in-memory rate limit (`AI_RATE_LIMIT_PER_MIN`, default 6/minute) exists to bound a single process's spend,
not to estimate monthly cost for many users.

**Training/evaluating a custom measurer:** see `core/skin_ai_measurer.py:TrainedModelMeasurer` for the interface to
implement, and run `backend/scripts/eval_skin_ai.py --images-dir <folder> --labels <labels.json>` against a folder of
hand-labelled photos to get precision/recall/F1 on finding types, the schema-failure rate, and run-to-run consistency
(the same photo scored `--repeats` times). `--dry-run` runs the harness itself with the mock provider, at no cost.

**Tests:** `backend/tests/test_skin_ai.py` (`cd backend && .venv/Scripts/python.exe -m pytest tests/ -v`) covers
schema validation, moderation redaction, the measurement-to-finding mapping, confidence blending, the fallback path,
caching, rate limiting, and an end-to-end `/api/analyze` -> `/api/ai/{scanId}` flow against a mocked provider -- no
real network call is made by any test.

**Assumptions / left as TODO:**
- Only Anthropic is a working provider; OpenAI and Gemini adapters are stubs with the same interface (no key existed
  to test them against).
- No child-safety age-gate: the app states no existing age policy, and the prompt explicitly forbids the model from
  estimating age (inferring age from a photo is itself a privacy-sensitive guess) -- a dedicated minors policy would
  need a separate, deliberately-designed mechanism (e.g. self-attestation at signup), not visual inference.
- "Extreme filter" and "non-skin image" handling: a missing/multiple-face photo is already rejected by the existing
  face detector; filters/heavy editing are only flagged by the model's own `image_notes.filtered_or_edited_suspected`
  self-report (lowering confidence), not independently detected.
- The AI's structured findings are not yet wired into a dedicated "what changed" diff view -- the existing
  measurement-based Compare page already covers that ground; diffing two scans' AI findings is a natural follow-up.
- `GET/POST /api/export` and `/api/import` do not include AI data; exporting/restoring a backup currently leaves AI
  history behind (it will simply be regenerated on the next manual re-run).
- No automated frontend test framework exists in this project (`frontend/` has no Vitest/Jest setup); the AI-insights
  UI and consent flow were instead verified with the same headless-Chrome script approach used elsewhere in this
  project's history. Adding Vitest + Testing Library is a reasonable next step if UI regressions become a concern.

---

## 2d. Fox (voice-first assistant)

A voice-first assistant, "Fox", sits alongside the app: push-to-talk (plus an optional best-effort wake phrase,
"Hey Fox"), app control by voice, hands-free spoken coaching during a scan, and spoken results. Her persona is a
warm, encouraging older sister rather than a formal assistant -- see `prompts/voice_assistant.v1.md` for the full
tone/style rules the LLM fallback follows, and `core/guide_intents.py` for the same warm phrasing on the fixed,
offline command list. She speaks with a female voice by default (see "Female voice" below). Internally the code
keeps its original module name, `guide_*` / `core.guide_service` / `/api/voice/*` -- "Fox" is purely the
spoken/display name the user actually hears and sees; this was a pure content/copy change with no architecture
impact. She is **off for every user by default** and stays off until "Fox" is turned on in Settings. There was no
pre-existing voice assistant or any audio/speech code in this repo before this feature -- it is new, built to
mirror the Custom Skin AI module's conventions above (adapter interfaces, closed-enum schema, consent gating,
dry-run mode).

**Architecture** (`backend/core/`):

| File | Role |
|---|---|
| `guide_config.py` | Thresholds, model name, rate limit, session TTL -- read from env vars (see `.env.example`). |
| `guide_schema.py` | Fox's reply contract (`speech`, `action`, `needs_confirmation`, ...). `ActionType` is a closed enum of every app action she may propose -- she cannot invent a new one, and `wipe_data` is structurally forced into `needs_confirmation=True` even if the model "forgets" to set it. |
| `guide_intents.py` | Local, fast, offline phrase matcher (English/Hindi/Marathi) for the fixed command list (start a scan, open my diary, what does my score mean, ...). Matched instantly, no LLM call. |
| `guide_provider.py` | `TextLLMProvider` adapter (same pattern as `skin_ai_provider.py`), text-only -- never sent an image. `AnthropicProvider` is real; `MockProvider` is the dry-run/test path. |
| `guide_llm.py` | Calls the provider only when the local matcher has no confident match, with one retry on a schema failure. |
| `guide_service.py` | Orchestration: consent -> local match -> (LLM fallback, rate-limited) -> confirmation gating -> optional transcript logging. In-memory, per-browser-tab session memory (short history, for "repeat that"). |
| `prompts/voice_assistant.v1.md` | The versioned persona/system prompt: short spoken sentences, no markdown/lists/emoji/URLs, numbers in natural speech, always a next step, never diagnose, reply in the user's spoken language. |

**Frontend** (`frontend/src/`):

| File | Role |
|---|---|
| `lib/speech.ts` | Swappable `SpeechRecognizer`/`Speaker` interfaces. `WebSpeechRecognizer`/`WebSpeaker` wrap the browser's Web Speech API (the only shipped implementation); `MockRecognizer`/`MockSpeaker` back the unit tests and the `?voiceMock=1` headless-browser test hook (`window.__voiceTestHooks__`), since a headless browser has no real microphone. |
| `lib/intentMatcher.ts` | Client-only matcher for the seven **playback-control** commands (repeat/louder/quieter/stop/mute/unmute/skip guide) -- these never leave the device, so they're instant even if the backend is slow. Everything else goes to the backend's `guide_intents.py`, which is the single source of truth for app-content commands. |
| `lib/voiceMachine.ts` | The pure turn-taking state machine (`idle -> listening -> thinking -> speaking/confirming -> idle`), barge-in, and a best-effort yes/no parser for confirmations -- framework-free, so it's directly unit-tested. |
| `context/VoiceContext.tsx` | Wires the state machine to the recognizer/speaker/backend: executes app actions (navigation, explain-score grounding using the real latest score, the wipe-data confirm/cancel flow), owns mute/session state. |
| `components/VoiceAssistant.tsx` | The floating, opt-in mic button + captions panel (accessible, `aria-live`) -- only rendered once voice is turned on in Settings. |
| `components/CameraScanner.tsx` | Hands-free spoken coaching layered on the *existing* live-quality checks (lighting/distance/centered/sharpness) and auto-capture logic -- no new CV, just short spoken hints with a cooldown, plus "hold still, capturing" / "got it!" around a capture. |
| `pages/Analysis.tsx` | A "Read aloud" button that speaks the real score and summary. |

**Try it with no account:** set `GUIDE_DRY_RUN=1` in `backend/.env` -- the fixed command list still works fully (it
never calls an LLM); open-ended questions get a canned, schema-valid reply instead of a network call.

**Go live:** reuses `ANTHROPIC_API_KEY` from the Custom Skin AI section above. See `.env.example` for tuning
(`GUIDE_RATE_LIMIT_PER_MIN`, `GUIDE_SESSION_TTL_MIN`, ...).

**New API endpoints:** `GET/PUT /api/voice/status` (consent, language, speed, volume, captions, transcript consent),
`POST /api/voice/ask` (one turn: transcript in, reply out; `confirm: true/false` answers a pending irreversible
action), `POST /api/voice/session/{id}/clear`, `GET/DELETE /api/voice/transcripts`.

**Storage:** one new, additive SQLite table (`guide_transcripts`, opt-in only) and seven new settings keys
(`voice_enabled`, `wake_word_enabled`, `voice_language`, `voice_speed`, `voice_volume`, `captions_enabled`,
`voice_transcripts_consent`, all default off/neutral). `CREATE TABLE IF NOT EXISTS`, no migration step; "Delete all
data" on the Privacy page clears the transcripts table too.

**Privacy:** speech-to-text runs in the browser (the Web Speech API); only the resulting **text** is sent to this
server, never raw audio, and audio is never stored anywhere. Text is sent on to the LLM only when the local command
list doesn't recognise it. The face photo is never sent to the voice assistant. Transcripts (text only) are kept only
if "Save voice transcripts" is turned on, and can be viewed/deleted via the endpoints above.

**Full command list (local, instant, English/Hindi/Marathi):** start a scan, retake, what does my score mean, show my
last scan, open my diary, compare with last week, open my routine/shop/ingredient check/history/privacy/settings,
delete all my data (requires a spoken yes/no confirmation) -- matched server-side in `guide_intents.py` -- plus
repeat/louder/quieter/stop/mute/unmute/skip guide, matched client-side in `intentMatcher.ts`. Anything else falls
back to the LLM, which can only ever reply with text plus one action from the same closed list -- it cannot invent a
new action, and it cannot execute anything itself (the frontend always performs the actual navigation/action).

**Latency:** playback-control commands are synchronous (no network) -- effectively instant. Local app-content
commands are one loopback HTTP round trip (consistently well under 200ms against the local dev server; the <1.5s
target is not a close call). The LLM fallback path depends on the configured provider's response time; dry-run mode
returns instantly since no network call is made. No streaming TTS was implemented (replies are short, 1-3 sentences
by prompt design, so spoken-sentence streaming was judged unnecessary complexity for this app -- see TODOs).

**Tests:** `backend/tests/test_guide.py` (37 tests: intent matching incl. Hindi/Marathi and noisy transcripts, schema
validation incl. "a new action is structurally impossible" and "wipe_data forces confirmation", the confirmation
flow, "repeat" session memory, rate limiting, consent gating, an API-layer integration test) and
`frontend/src/lib/__tests__/*.test.ts` (47 tests via the newly-added Vitest: the turn-taking state machine incl.
barge-in/timeouts, the yes/no parser in three languages, the client-side intent matcher incl. a regression test for
a real bug found during manual verification -- see below). The full voice flow (enable in Settings -> push-to-talk ->
local command -> navigation; mute/unmute; explain-score grounding; the wipe-data confirm *and* cancel paths) was also
driven end-to-end against the real backend via a headless-Chrome CDP script using the `?voiceMock=1` test hook, with
zero console errors.

**A real bug found and fixed during that verification:** the frontend's `handleTranscript` checked only whether
`matchLocal()` returned a non-null result, not whether its `confidence` cleared the threshold -- so "what does my
score mean" weakly overlapped the word "what" in the "repeat" phrase list (confidence 0.14) and got silently
misrouted to "repeat" instead of reaching the backend's `explain_score` intent. Fixed by checking
`confidence >= INTENT_CONFIDENCE_THRESHOLD`, with a regression test added. A second, smaller bug (Devanagari
combining marks/matras being stripped by both the Python and JS "strip punctuation" regexes, e.g. "रुको" becoming
"रक") was also found and fixed on both sides while writing that regression test.

**Assumptions / left as TODO:**
- No native Android/iOS app exists (this is a pure web app), so there is no `AndroidManifest.xml`/`Info.plist` to
  request microphone permission in -- the browser's own mic-permission prompt (triggered by the Web Speech API) is
  the only permission surface, with a spoken + captioned fallback message on denial.
- The wake phrase ("Hey Foxtale" / Hindi / Marathi equivalents) is matched by a plain substring check on the
  continuously-listening recognizer's transcript while idle -- best-effort, foreground-tab-only, not a trained
  wake-word model, exactly as scoped in the request.
- Barge-in keeps the microphone open during "speaking" (so the user can interrupt); on hardware without echo
  cancellation (e.g. laptop speakers + built-in mic, no headphones) this can occasionally pick up Fox's own
  voice as a false trigger. Mitigating this properly needs device-level echo cancellation or push-to-talk-only mode.
- The yes/no confirmation parser (`parseYesNo`) is a small regex heuristic per language, not a trained classifier; an
  unrecognised answer is re-asked once, then cancelled for safety (never defaults to "yes").
- Hindi and Marathi phrases (both the fixed command list and Fox's persona prompt instruction to reply in the
  user's language) are good-faith, commonly-used phrasings, not professionally reviewed translations.
- Female voice is a best-effort browser-side preference (`frontend/src/lib/speech.ts:pickVoice`): the Web Speech API
  has no standard gender field, so it matches voices explicitly labelled "female" or a curated list of well-known
  female voice names (Zira, Samantha, Heera, Veena, Lekha, Swara, Aarohi, ...). On a system/browser with only one
  voice for a language (common for Hindi/Marathi outside Windows/macOS), there is no gender choice to make.
- Only Anthropic and a mock provider are implemented for the LLM fallback (same reasoning as the Skin Analyst: no
  OpenAI/Gemini key existed to test against).
- No streaming/sentence-by-sentence TTS: replies are short by prompt design, so the added complexity wasn't judged
  worthwhile for this app; would be a reasonable follow-up if longer answers are ever allowed.
- `guide_transcripts` is not included in `/api/export`/`/api/import` (same gap as the AI tables in section 2c).

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
