# Foxtale Desktop — Details & Features

A native Windows desktop application (PySide6/Qt) that scans your face with a
webcam and produces a **visual, non-diagnostic** skin observation report —
acne-like spots, redness, texture, and dryness indicators — entirely on your
own machine. No server, no network calls, no telemetry.

This is the desktop sibling of the Foxtale web app (`../foxtale`), sharing
the same underlying analysis approach but built as a self-contained native
GUI with a deeper feature set (calibration, hands-free capture, trend
insights, system tray, full data backup, and more — detailed below).

> ⚠️ **Not a medical device.** Every result is phrased as a visible
> observation, never a diagnosis. Foxtale doesn't infer age, ethnicity, or
> health status, and every relevant screen carries the disclaimer:
> *"This analysis is based only on visible features in the captured image
> and is not a medical diagnosis. For persistent, painful, spreading, or
> concerning skin changes, consult a qualified dermatologist."*

---

## 1. Tech stack

| Layer | Technology |
|---|---|
| UI framework | PySide6 (Qt 6) |
| Camera / CV | OpenCV (`opencv-python-headless`), NumPy |
| Face detection | OpenCV Haar cascade (local, no downloads, no cloud) |
| Icons | qtawesome (Font Awesome, flat single-color glyphs — no emoji) |
| Charts | matplotlib (embedded via `FigureCanvasQTAgg`) |
| PDF reports | reportlab |
| Storage | SQLite (`sqlite3`, stdlib) + JSON (settings/calibration) |
| Runtime | Python 3.14 |

## 2. Project layout

```text
foxtale-gui/
├── main.py                    Entry point (python main.py)
├── requirements.txt
├── assets/                    Real brand logo files (logo_full.png, logo_mark.png)
├── engine/                    Framework-agnostic analysis engine
│   ├── schemas.py               Plain dataclasses (SkinAnalysis, RegionObservation, ...)
│   ├── face_detection.py        Haar-cascade detection + lighting/distance checks
│   ├── image_processing.py      Normalize / region-split / calibration patch
│   ├── skin_analysis.py         Rule-based heuristics (the "model")
│   └── calibration.py           Per-user skin-tone baseline
└── gui/
    ├── theme.py                  Light/dark stylesheets, brand color tokens
    ├── assets.py                  Logo loading, monochrome icon helpers, shadows
    ├── main_window.py             Sidebar nav, page routing, tray icon, shortcuts
    ├── core/
    │   ├── camera_worker.py        QThread wrapping cv2.VideoCapture, burst capture
    │   ├── analysis_worker.py      QThread running the engine off the UI thread
    │   ├── storage.py               SQLite history + JSON settings + backup/restore
    │   ├── insights.py              Rule-based trend narrative + streak stats
    │   ├── recommendations.py       Skincare tip generator
    │   └── report_export.py         Single-scan PDF, multi-scan PDF, annotated PNG
    ├── widgets/                    CameraView, FaceReportView, AnalysisCard, TrendChart, Toast...
    └── pages/                      Home, Scan, Results, History, Compare, Settings, About
```

## 3. How the analysis engine works

1. **Decode & preprocess** — captured frame is resized and checked for brightness.
2. **Face detection** — OpenCV Haar cascade finds the face box; rejects zero/multiple
   faces and faces that are too close or too far.
3. **Region split** — the face box is divided proportionally into **forehead,
   left cheek, right cheek, nose, chin**.
4. **Per-region heuristics** (`engine/skin_analysis.py`):
   - *Acne-like spots* — adaptive thresholding + contour filtering for small, localized dark blobs.
   - *Redness* — HSV hue/saturation thresholding for red-toned pixel ratio.
   - *Texture* — Laplacian variance (high-frequency detail) as a roughness proxy.
   - *Dryness indicators* — low saturation + patchy local brightness as a dullness/flakiness proxy.
5. Scores map to neutral levels (**Minimal / Mild / Moderate / Noticeable**) with a
   bounded confidence value — a UX signal, not a calibrated clinical probability.
6. **Optional calibration** shifts the redness/dryness baseline to your own skin
   tone instead of one fixed threshold for everyone (see §4).

---

## 4. Feature tour by page

### 🏠 Home
- Hero panel featuring the **real Foxtale logo** and brand tagline.
- "Start Face Scan" call to action.
- Feature-highlight cards (camera-based analysis, visual observations, private
  processing, trend tracking).
- **Recent Activity dashboard** for returning users — total scan count, last
  scan date, starred-scan count, and a "View Last Analysis" shortcut.
- **Scan reminder banner** — "It's been *N* days since your last scan — time
  for a check-in?" once you're overdue, per your reminder cadence in Settings.

### 🔍 Scan
- Live camera preview with **device and resolution picker**.
- Corner-bracket scanning frame with an animated sweep line.
- Real-time **face-lock indicator** (orange → green) and a **live brightness
  meter**, both computed before you even press Capture.
- **Burst capture** — grabs 5 frames and automatically keeps the sharpest one
  (Laplacian variance) for the highest-quality photo.
- **3-2-1 capture countdown** (toggle in Settings).
- **Hands-free auto-capture** — once your face holds steady in frame for
  ~1.5 seconds, it captures on its own (toggle in Settings; still respects
  the countdown if both are enabled).
- **Retake** button and full analysis-progress animation with step-by-step status text.
- **Skin-tone calibration** — "Calibrate skin tone from this photo" personalizes
  redness/dryness thresholds to you instead of one fixed baseline.
- Friendly, specific error states: no face detected / multiple faces /
  insufficient lighting / too close / too far.

### 📊 Analysis (Results)
- Header with **Previous / Next navigation** to step chronologically through
  saved scans, a **star toggle**, and the scan timestamp.
- Four summary cards — Acne-like Spots, Visible Redness, Skin Texture, Dryness
  Indicators — each with a severity pill, confidence %, and area count.
- Interactive face photo with **clickable colored markers**; clicking one
  opens a detail panel (area, observation, confidence, disclaimer reminder).
- **Region breakdown** grouped by facial region.
- **Personal Notes** field, saved per scan (e.g. "tried a new retinol serum").
- Rule-based **recommendations** tailored to whatever was detected.
- **Export**: single-scan PDF report, annotated PNG (markers drawn on the
  photo), delete scan, start a new scan.
- Notes/starring/navigation gracefully disable (with an explanatory hint) for
  scans that weren't saved to history.

### 🕘 History
- **Search** by date or note text, **filter by severity level**, and a
  **"Starred only"** toggle.
- Inline **star** column and a note-preview column in the table.
- Per-row delete, plus **Delete All History** (confirmed).
- **Export**: CSV (spreadsheet-friendly, one row per scan), JSON (full
  scan-data export with re-import support), and a **Progress Report PDF** —
  a multi-scan report covering your currently filtered scans, with an
  embedded trend-chart image, a rule-based headline, and a full table.
- **Import JSON** to merge previously exported scans back in.
- **Trends tab** — a matplotlib chart of every category's severity across all
  your scans over time.
- **Insights tab** — a rule-based, plain-language summary comparing your
  earliest scans to your most recent ones per category (improved / worsened /
  stable), plus scan count, date span, and average days between scans.

### 🔁 Compare
- Pick any two saved scans ("From" / "To") and see a category-by-category
  level comparison with a color-coded delta (▼ Improved / ▲ Worsened / —
  Unchanged).

### ⚙️ Settings
- **Privacy** — Save scan history toggle, Save captured images toggle (off
  by default), with a plain-language explanation of what's stored where.
- **Appearance** — Light / Dark theme.
- **Scanning & Reminders** — capture countdown toggle, reminder cadence
  (Never / 3 days / Weekly / 2 weeks / Monthly), "keep running in the system
  tray" toggle, hands-free auto-capture toggle.
- **Analysis** — minimum-confidence slider controlling which region markers
  are surfaced.
- **Skin-tone Calibration** — current status + "Clear Calibration".
- **Data Backup** — "Export All Data" (one zip: settings + calibration +
  history + any saved images) and "Import All Data" (restores from that zip,
  with a confirmation prompt since it's destructive to current local data).

### ℹ️ About
- Real logo, app description, and cards explaining the app's design
  principles (visual-observation-only, explainable CV, privacy-first,
  not a medical device, personal calibration, trend tracking).

---

## 5. System integration

- **System tray icon** with Show / Start Scan / Quit; double-click to
  restore; a notification when a scan finishes while minimized; an optional
  "minimize to tray instead of quitting" behavior (Settings).
- **Real branded app icon and splash screen**, generated from your actual
  logo file rather than a placeholder mark.
- Runs as a genuine native app — no browser tab, no local web server, no
  backend process to keep alive separately.

## 6. Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | Jump to Scan |
| `Ctrl+H` | Jump to History |
| `Ctrl+,` | Jump to Settings |
| `Esc` | Jump to Home |

## 7. Privacy & data

- Everything runs locally — no network requests, ever.
- Captured images are **not saved by default**; only the analysis summary is,
  unless you opt in via Settings → Privacy → "Also save captured images".
- All data lives under your home directory, never inside the app folder:

```text
~/.foxtale_gui/
├── settings.json       All toggles/preferences described above
├── calibration.json    Your personal skin-tone baseline (only if calibrated)
├── history.db          SQLite: one row per saved scan (analysis, note, starred, optional image path)
└── images/             Captured photos — only written if "Save captured images" is on
```

- **Delete Scan** / **Delete All History** remove database rows and any
  saved image files immediately and permanently.
- The History page's JSON/CSV export is *scan data only*; Settings' "Export
  All Data" is a complete backup (settings + calibration + history + images)
  for moving to a new machine or as a safety net — the two are intentionally
  separate tools.

## 8. Design & accessibility

- Every text/background color pair was checked against WCAG contrast math
  (not eyeballed) and tuned to clear **4.5:1+** in both light and dark theme,
  including severity pills, badges, and trend-delta text.
- Fully **monochrome icon system** (Font Awesome via qtawesome) — no
  multicolor emoji anywhere in the UI.
- Brand identity built around the real Foxtale logo and its orange accent
  color, sampled directly from the source logo file.

## 9. Replacing the prototype model

The engine's interface is intentionally narrow so the rule-based heuristics
can be swapped for a trained model later without touching the GUI:

- `engine/face_detection.py` → `detect_face(image) -> FaceDetectionResult`
  (swap Haar cascade for MediaPipe/RetinaFace for more robust, landmark-aware detection).
- `engine/skin_analysis.py` → `analyze_face(regions, calibration, min_confidence) -> (SkinAnalysis, List[RegionObservation])`
  (swap the heuristics for a trained classifier/segmentation model), as long
  as the return shapes stay the same and the same neutral, non-diagnostic
  language is used for `observation` strings.

## 10. Running it

```bash
cd foxtale-gui
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
