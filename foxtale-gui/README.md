# 🦊 Foxtale Desktop

A native Windows/desktop **GUI** edition of Foxtale — the same visual skin-analysis engine
(face detection + rule-based computer-vision heuristics) as the [`foxtale`](../foxtale) web
app, rebuilt as a standalone **PySide6 (Qt)** application. No browser, no server — everything
runs in one local process.

> ⚠️ **Not a medical device.** Foxtale describes *visible features in a photo* only. It never
> diagnoses a medical condition and never infers age, ethnicity, or health status.

---

## What's different from the web app

The web app (`foxtale/`) is left untouched. This is a separate, richer client built on the
same analysis engine, adding:

- **Live scanning guidance** — real-time face-lock indicator and brightness meter drawn over
  the camera feed *before* you even capture (the web version only checks after capture).
- **Burst capture** — Capture grabs 5 frames and automatically keeps the sharpest one.
- **Per-user skin-tone calibration** (opt-in) — sample your own forehead as a baseline so
  redness/dryness scoring adapts to you instead of one fixed threshold for everyone.
- **SQLite-backed history** with a **Trends** tab (matplotlib) charting each category's
  severity across all your past scans.
- **Compare** page — pick any two past scans and see an improved/unchanged/worsened delta
  per category.
- **Report export** — one-page PDF report, or an annotated PNG with markers drawn on the photo.
- **JSON history backup/restore** (export/import).
- **Device & resolution picker**, **light/dark theme**, a **confidence threshold** slider to
  control how many region markers show up, and keyboard shortcuts (`Ctrl+N` new scan,
  `Ctrl+H` history, `Ctrl+,` settings, `Esc` home).
- Fully local: no HTTP calls at all, no CORS, no backend process to run.

---

## Project structure

```text
foxtale-gui/
├── main.py                    Entry point (python main.py)
├── requirements.txt
├── engine/                    Framework-agnostic analysis engine (ported from foxtale/backend)
│   ├── schemas.py               Plain dataclasses (no pydantic/FastAPI dependency)
│   ├── face_detection.py        OpenCV Haar-cascade detection + quality checks
│   ├── image_processing.py      Normalize / region-split / calibration patch
│   ├── skin_analysis.py         Rule-based heuristics (the "model"), calibration-aware
│   └── calibration.py           Per-user skin-tone baseline
└── gui/
    ├── theme.py                Light/dark QSS stylesheets
    ├── main_window.py           Sidebar nav + page routing + shortcuts
    ├── core/
    │   ├── camera_worker.py      QThread wrapping cv2.VideoCapture, burst capture
    │   ├── analysis_worker.py    QThread running the engine off the UI thread
    │   ├── storage.py             SQLite history + JSON settings + optional saved images
    │   ├── recommendations.py     Skincare tip generator (same rules as the web app)
    │   └── report_export.py       PDF + annotated-PNG export
    ├── widgets/                  CameraView, FaceReportView, AnalysisCard, TrendChart, Toast...
    └── pages/                    Home, Scan, Results, History, Compare, Settings, About
```

---

## Quick start

```bash
cd foxtale-gui
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

A window opens directly — no `localhost`, no separate backend process.

---

## Where data lives

Everything is stored under your home directory, never inside the app folder:

```text
~/.foxtale_gui/
├── settings.json       Save-history / save-images / theme / confidence / camera prefs
├── calibration.json    Your personal skin-tone baseline (only if you calibrated)
├── history.db          SQLite: one row per saved scan (analysis JSON + optional image path)
└── images/             Captured photos — only written if "Save captured images" is enabled
```

- **Save scan history** is on by default (summaries only); **Save captured images** is off by
  default (opt-in), matching the web app's privacy stance.
- **Delete Scan** / **Delete All History** (Settings/History pages) remove the DB rows and any
  saved image files immediately — nothing is recoverable after that.

---

## Replacing the prototype model

Same contract as the web backend: swap `engine/face_detection.py`'s `detect_face()` for
MediaPipe/RetinaFace, or `engine/skin_analysis.py`'s `analyze_face()` for a trained model, as
long as the function signatures and return types (`SkinAnalysis` / `RegionObservation`) stay the
same — nothing in `gui/` needs to change.

---

## Packaging as a standalone .exe (optional)

Once the app runs correctly with `python main.py`, you can bundle it with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Foxtale main.py
```

The output lands in `dist/Foxtale/`.
