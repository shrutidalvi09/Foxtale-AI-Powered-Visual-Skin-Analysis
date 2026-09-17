"""Local persistence: SQLite scan history, JSON settings, optional saved
images, and a saved calibration profile.

Everything lives under the user's home directory, never in the app folder,
and (per the app's privacy defaults) captured images are NOT written to disk
unless the user opts in via Settings -> "Save captured images locally".
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from engine.calibration import CalibrationProfile
from engine.schemas import RegionObservation, SkinAnalysis

APP_DIR = Path.home() / ".foxtale_gui"
IMAGES_DIR = APP_DIR / "images"
DB_PATH = APP_DIR / "history.db"
SETTINGS_PATH = APP_DIR / "settings.json"
CALIBRATION_PATH = APP_DIR / "calibration.json"

DEFAULT_SETTINGS = {
    "save_history": True,
    "save_images": False,
    "theme": "light",
    "min_confidence": 0.0,
    "camera_index": 0,
    "camera_width": 1280,
    "camera_height": 720,
}


@dataclass
class ScanRecord:
    id: str
    timestamp: str
    analysis: SkinAnalysis
    regions: List[RegionObservation]
    image_path: Optional[str] = None


def _ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS scans (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            regions_json TEXT NOT NULL,
            image_path TEXT
        )"""
    )
    return conn


# ---------------------------------------------------------------- settings

def load_settings() -> dict:
    _ensure_dirs()
    if not SETTINGS_PATH.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_PATH.read_text())
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    _ensure_dirs()
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2))


# ------------------------------------------------------------- calibration

def load_calibration() -> Optional[CalibrationProfile]:
    if not CALIBRATION_PATH.exists():
        return None
    try:
        return CalibrationProfile.from_dict(json.loads(CALIBRATION_PATH.read_text()))
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def save_calibration(profile: CalibrationProfile) -> None:
    _ensure_dirs()
    CALIBRATION_PATH.write_text(json.dumps(profile.to_dict(), indent=2))


def clear_calibration() -> None:
    if CALIBRATION_PATH.exists():
        CALIBRATION_PATH.unlink()


# ------------------------------------------------------------------ scans

def make_transient_record(analysis: SkinAnalysis, regions: List[RegionObservation]) -> ScanRecord:
    """A ScanRecord that is shown in the UI but never written to disk --
    used when the user has "Save scan history" turned off."""
    return ScanRecord(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        analysis=analysis,
        regions=regions,
        image_path=None,
    )


def save_scan(
    analysis: SkinAnalysis,
    regions: List[RegionObservation],
    image_bgr: Optional[np.ndarray],
    save_image: bool,
) -> ScanRecord:
    _ensure_dirs()
    scan_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    image_path = None
    if save_image and image_bgr is not None:
        image_path = str(IMAGES_DIR / f"{scan_id}.jpg")
        cv2.imwrite(image_path, image_bgr)

    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO scans (id, timestamp, analysis_json, regions_json, image_path) VALUES (?, ?, ?, ?, ?)",
            (
                scan_id,
                timestamp,
                json.dumps(analysis.to_dict()),
                json.dumps([r.to_dict() for r in regions]),
                image_path,
            ),
        )
    conn.close()

    return ScanRecord(id=scan_id, timestamp=timestamp, analysis=analysis, regions=regions, image_path=image_path)


def _row_to_record(row) -> ScanRecord:
    scan_id, timestamp, analysis_json, regions_json, image_path = row
    return ScanRecord(
        id=scan_id,
        timestamp=timestamp,
        analysis=SkinAnalysis.from_dict(json.loads(analysis_json)),
        regions=[RegionObservation.from_dict(r) for r in json.loads(regions_json)],
        image_path=image_path,
    )


def list_scans() -> List[ScanRecord]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, timestamp, analysis_json, regions_json, image_path FROM scans ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [_row_to_record(r) for r in rows]


def get_scan(scan_id: str) -> Optional[ScanRecord]:
    conn = _connect()
    row = conn.execute(
        "SELECT id, timestamp, analysis_json, regions_json, image_path FROM scans WHERE id = ?",
        (scan_id,),
    ).fetchone()
    conn.close()
    return _row_to_record(row) if row else None


def delete_scan(scan_id: str) -> None:
    record = get_scan(scan_id)
    if record and record.image_path:
        Path(record.image_path).unlink(missing_ok=True)
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    conn.close()


def delete_all_scans() -> None:
    for record in list_scans():
        if record.image_path:
            Path(record.image_path).unlink(missing_ok=True)
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM scans")
    conn.close()


def export_history_json(dest_path: str) -> int:
    records = list_scans()
    payload = [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "analysis": r.analysis.to_dict(),
            "regions": [o.to_dict() for o in r.regions],
        }
        for r in records
    ]
    Path(dest_path).write_text(json.dumps(payload, indent=2))
    return len(payload)


def import_history_json(src_path: str) -> int:
    data = json.loads(Path(src_path).read_text())
    conn = _connect()
    count = 0
    with conn:
        for entry in data:
            conn.execute(
                "INSERT OR IGNORE INTO scans (id, timestamp, analysis_json, regions_json, image_path) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    entry.get("id", str(uuid.uuid4())),
                    entry["timestamp"],
                    json.dumps(entry["analysis"]),
                    json.dumps(entry["regions"]),
                    None,
                ),
            )
            count += 1
    conn.close()
    return count
