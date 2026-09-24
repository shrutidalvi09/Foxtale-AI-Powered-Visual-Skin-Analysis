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
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from engine.calibration import CalibrationProfile
from engine.quality import QualityResult
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
    "capture_countdown": True,
    "reminder_days": 7,  # 0 = off
    "minimize_to_tray": False,
    "auto_capture": False,
    "standardised_mode": False,
    "app_lock_enabled": False,
    "lock_on_start": True,
    "lock_after_minutes": 0,  # 0 = never auto-lock from inactivity
    "camera_profiles": [],  # [{"name", "index", "width", "height"}, ...]
    "window_geometry": None,  # {"x", "y", "w", "h", "maximized"} or None
    "onboarding_complete": False,
}

ROUTINE_OPTIONS = ["Cleanser", "Moisturiser", "Sunscreen", "Treatment", "Exfoliator", "Other"]
ENVIRONMENT_OPTIONS = ["Travel", "Outdoor exposure", "High humidity", "Low humidity"]

TRASH_RETENTION_DAYS = 30


@dataclass
class ScanRecord:
    id: str
    timestamp: str
    analysis: SkinAnalysis
    regions: List[RegionObservation]
    image_path: Optional[str] = None
    note: str = ""
    starred: bool = False
    quality: Optional[QualityResult] = None
    journal: dict = None  # {"routine": [...], "environment": [...]}
    deleted_at: Optional[str] = None  # set when soft-deleted; None means active

    def __post_init__(self):
        if self.journal is None:
            self.journal = {"routine": [], "environment": []}


def _ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing_cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _migration_0(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS scans (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            regions_json TEXT NOT NULL,
            image_path TEXT
        )"""
    )


def _migration_1(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "scans", "note", "note TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "scans", "starred", "starred INTEGER NOT NULL DEFAULT 0")


def _migration_2(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "scans", "quality_json", "quality_json TEXT")
    _add_column_if_missing(conn, "scans", "journal_json", "journal_json TEXT")


def _migration_3(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "scans", "deleted_at", "deleted_at TEXT")


def _migration_4(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS routine_logs (
            date TEXT PRIMARY KEY,
            routine_json TEXT NOT NULL
        )"""
    )


# Ordered schema steps, each safe to re-run (CREATE TABLE IF NOT EXISTS /
# column-presence checks), tracked via `PRAGMA user_version` so a fully
# migrated database skips straight past all of them on every later connect.
# New schema changes are added as `_migration_N` and appended here.
_MIGRATIONS = [_migration_0, _migration_1, _migration_2, _migration_3, _migration_4]


def _migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in range(current, len(_MIGRATIONS)):
        _MIGRATIONS[version](conn)
    if current < len(_MIGRATIONS):
        conn.execute(f"PRAGMA user_version = {len(_MIGRATIONS)}")


def _connect() -> sqlite3.Connection:
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    with conn:
        _migrate(conn)
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

def make_transient_record(
    analysis: SkinAnalysis, regions: List[RegionObservation], quality: Optional[QualityResult] = None,
) -> ScanRecord:
    """A ScanRecord that is shown in the UI but never written to disk --
    used when the user has "Save scan history" turned off."""
    return ScanRecord(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        analysis=analysis,
        regions=regions,
        image_path=None,
        quality=quality,
    )


def save_scan(
    analysis: SkinAnalysis,
    regions: List[RegionObservation],
    image_bgr: Optional[np.ndarray],
    save_image: bool,
    quality: Optional[QualityResult] = None,
) -> ScanRecord:
    _ensure_dirs()
    scan_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    image_path = None
    if save_image and image_bgr is not None:
        image_path = str(IMAGES_DIR / f"{scan_id}.jpg")
        cv2.imwrite(image_path, image_bgr)

    quality_json = json.dumps(quality.to_dict()) if quality else None

    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO scans (id, timestamp, analysis_json, regions_json, image_path, note, starred, "
            "quality_json, journal_json) VALUES (?, ?, ?, ?, ?, '', 0, ?, NULL)",
            (
                scan_id,
                timestamp,
                json.dumps(analysis.to_dict()),
                json.dumps([r.to_dict() for r in regions]),
                image_path,
                quality_json,
            ),
        )
    conn.close()

    return ScanRecord(
        id=scan_id, timestamp=timestamp, analysis=analysis, regions=regions,
        image_path=image_path, quality=quality,
    )


_SELECT_COLUMNS = (
    "id, timestamp, analysis_json, regions_json, image_path, note, starred, quality_json, "
    "journal_json, deleted_at"
)


def _row_to_record(row) -> ScanRecord:
    (scan_id, timestamp, analysis_json, regions_json, image_path, note, starred,
     quality_json, journal_json, deleted_at) = row
    return ScanRecord(
        id=scan_id,
        timestamp=timestamp,
        analysis=SkinAnalysis.from_dict(json.loads(analysis_json)),
        regions=[RegionObservation.from_dict(r) for r in json.loads(regions_json)],
        image_path=image_path,
        note=note or "",
        starred=bool(starred),
        quality=QualityResult.from_dict(json.loads(quality_json)) if quality_json else None,
        journal=json.loads(journal_json) if journal_json else {"routine": [], "environment": []},
        deleted_at=deleted_at,
    )


def list_scans() -> List[ScanRecord]:
    """Active (non-trashed) scans only -- see list_trashed_scans() for
    scans currently in Recently Deleted."""
    conn = _connect()
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM scans WHERE deleted_at IS NULL ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [_row_to_record(r) for r in rows]


def list_trashed_scans() -> List[ScanRecord]:
    conn = _connect()
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM scans WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
    ).fetchall()
    conn.close()
    return [_row_to_record(r) for r in rows]


def get_scan(scan_id: str) -> Optional[ScanRecord]:
    """Looks up a scan whether active or trashed."""
    conn = _connect()
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM scans WHERE id = ?",
        (scan_id,),
    ).fetchone()
    conn.close()
    return _row_to_record(row) if row else None


def set_scan_note(scan_id: str, note: str) -> None:
    conn = _connect()
    with conn:
        conn.execute("UPDATE scans SET note = ? WHERE id = ?", (note, scan_id))
    conn.close()


def set_scan_starred(scan_id: str, starred: bool) -> None:
    conn = _connect()
    with conn:
        conn.execute("UPDATE scans SET starred = ? WHERE id = ?", (1 if starred else 0, scan_id))
    conn.close()


def set_scan_journal(scan_id: str, routine: List[str], environment: List[str]) -> None:
    conn = _connect()
    with conn:
        conn.execute(
            "UPDATE scans SET journal_json = ? WHERE id = ?",
            (json.dumps({"routine": routine, "environment": environment}), scan_id),
        )
    conn.close()


def delete_scan(scan_id: str) -> None:
    """Soft-delete: moves the scan to Recently Deleted rather than erasing
    it immediately. The row and any saved image stay on disk until it's
    restored or the retention window elapses (see purge_expired_trash)."""
    conn = _connect()
    with conn:
        conn.execute("UPDATE scans SET deleted_at = ? WHERE id = ?", (datetime.now().isoformat(), scan_id))
    conn.close()


def restore_scan(scan_id: str) -> None:
    conn = _connect()
    with conn:
        conn.execute("UPDATE scans SET deleted_at = NULL WHERE id = ?", (scan_id,))
    conn.close()


def permanently_delete_scan(scan_id: str) -> None:
    record = get_scan(scan_id)
    if record and record.image_path:
        Path(record.image_path).unlink(missing_ok=True)
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    conn.close()


def purge_expired_trash() -> int:
    """Permanently removes trashed scans older than TRASH_RETENTION_DAYS.
    Called opportunistically (e.g. on History page refresh) since this is
    a desktop app with no background process to run it on a timer."""
    cutoff = datetime.now() - timedelta(days=TRASH_RETENTION_DAYS)
    conn = _connect()
    rows = conn.execute("SELECT id, image_path, deleted_at FROM scans WHERE deleted_at IS NOT NULL").fetchall()
    expired = [(rid, image_path) for rid, image_path, deleted_at in rows if datetime.fromisoformat(deleted_at) < cutoff]
    for _, image_path in expired:
        if image_path:
            Path(image_path).unlink(missing_ok=True)
    if expired:
        with conn:
            conn.executemany("DELETE FROM scans WHERE id = ?", [(rid,) for rid, _ in expired])
    conn.close()
    return len(expired)


def delete_all_scans() -> None:
    """A genuine, permanent wipe -- bypasses Recently Deleted entirely.
    Used by explicit, already-confirmed bulk actions ("Delete All History",
    the Privacy Dashboard's "Delete All Data")."""
    conn = _connect()
    rows = conn.execute("SELECT image_path FROM scans").fetchall()
    for (image_path,) in rows:
        if image_path:
            Path(image_path).unlink(missing_ok=True)
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
            "note": r.note,
            "starred": r.starred,
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
                "INSERT OR IGNORE INTO scans (id, timestamp, analysis_json, regions_json, image_path, note, starred) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.get("id", str(uuid.uuid4())),
                    entry["timestamp"],
                    json.dumps(entry["analysis"]),
                    json.dumps(entry["regions"]),
                    None,
                    entry.get("note", ""),
                    1 if entry.get("starred") else 0,
                ),
            )
            count += 1
    conn.close()
    return count


def export_history_csv(dest_path: str) -> int:
    """A flat, spreadsheet-friendly export -- one row per scan, one column
    per category level/confidence, for users who want to chart their own
    progress in Excel/Sheets rather than the app's built-in Trends tab."""
    import csv

    records = list_scans()
    with open(dest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "starred", "note",
            "acne_level", "acne_confidence", "acne_count",
            "redness_level", "redness_confidence",
            "texture_level", "texture_confidence",
            "dryness_level", "dryness_confidence",
        ])
        for r in records:
            a = r.analysis
            writer.writerow([
                r.timestamp, r.starred, r.note,
                a.acne_like_spots.level, a.acne_like_spots.confidence, a.acne_like_spots.count or 0,
                a.redness.level, a.redness.confidence,
                a.texture.level, a.texture.confidence,
                a.dryness_indicators.level, a.dryness_indicators.confidence,
            ])
    return len(records)


def days_since_last_scan() -> Optional[int]:
    """None if there's no history yet."""
    conn = _connect()
    row = conn.execute(
        "SELECT timestamp FROM scans WHERE deleted_at IS NULL ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    last = datetime.fromisoformat(row[0])
    return (datetime.now() - last).days


# ------------------------------------------------------- full data backup

def export_full_backup(dest_zip_path: str) -> None:
    """Everything -- settings, calibration, history, and any saved images --
    in one .zip, for moving to a new machine or as a safety-net backup.
    Distinct from the History page's JSON/CSV export, which is scan data
    only (no settings/calibration/images)."""
    import zipfile

    _ensure_dirs()
    with zipfile.ZipFile(dest_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if SETTINGS_PATH.exists():
            zf.write(SETTINGS_PATH, "settings.json")
        if CALIBRATION_PATH.exists():
            zf.write(CALIBRATION_PATH, "calibration.json")
        if DB_PATH.exists():
            zf.write(DB_PATH, "history.db")
        if IMAGES_DIR.exists():
            for img_path in IMAGES_DIR.glob("*.jpg"):
                zf.write(img_path, f"images/{img_path.name}")


def get_data_stats() -> dict:
    """Powers the Privacy Dashboard: exactly what exists locally, in plain
    numbers, so the app's "nothing leaves this device" claim is verifiable
    rather than just asserted."""
    conn = _connect()
    scan_count = conn.execute("SELECT COUNT(*) FROM scans WHERE deleted_at IS NULL").fetchone()[0]
    trashed_count = conn.execute("SELECT COUNT(*) FROM scans WHERE deleted_at IS NOT NULL").fetchone()[0]
    conn.close()

    image_files = list(IMAGES_DIR.glob("*.jpg")) if IMAGES_DIR.exists() else []
    images_size = sum(f.stat().st_size for f in image_files)
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0

    return {
        "scan_count": scan_count,
        "trashed_count": trashed_count,
        "image_count": len(image_files),
        "db_size_bytes": db_size,
        "images_size_bytes": images_size,
        "calibration_enabled": CALIBRATION_PATH.exists(),
    }


def delete_all_personal_data() -> None:
    """Scan history, saved images, calibration, and routine logs -- but
    deliberately NOT settings.json, so a user's app preferences (theme,
    reminders, etc.) survive a personal-data wipe. Used by the Privacy
    Dashboard's "Delete All Data" action."""
    delete_all_scans()
    clear_calibration()
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM routine_logs")
    conn.close()


def set_daily_routine(date_str: str, routine: List[str]) -> None:
    """`date_str` is a plain "YYYY-MM-DD" day, independent of any scan --
    this tracks what a user did that day (cleanser, sunscreen, ...) whether
    or not they also scanned."""
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO routine_logs (date, routine_json) VALUES (?, ?) "
            "ON CONFLICT(date) DO UPDATE SET routine_json = excluded.routine_json",
            (date_str, json.dumps(routine)),
        )
    conn.close()


def get_daily_routine(date_str: str) -> List[str]:
    conn = _connect()
    row = conn.execute("SELECT routine_json FROM routine_logs WHERE date = ?", (date_str,)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else []


def list_routine_logs(limit: int = 30) -> List[tuple]:
    """[(date_str, [item, ...]), ...] newest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT date, routine_json FROM routine_logs ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [(d, json.loads(j)) for d, j in rows]


def routine_streak(item: str) -> int:
    """Consecutive days (counting back from today, or from yesterday if
    today isn't logged yet) that `item` appears in the daily routine log."""
    from datetime import date, timedelta

    conn = _connect()
    rows = conn.execute("SELECT date, routine_json FROM routine_logs").fetchall()
    conn.close()
    logged = {d: set(json.loads(j)) for d, j in rows}

    day = date.today()
    if item not in logged.get(day.isoformat(), set()):
        day -= timedelta(days=1)
    streak = 0
    while item in logged.get(day.isoformat(), set()):
        streak += 1
        day -= timedelta(days=1)
    return streak


def import_full_backup(src_zip_path: str) -> None:
    """Restores a backup made by export_full_backup(), overwriting whatever
    is currently in ~/.foxtale_gui. Callers should confirm with the user
    first -- this is destructive to the current local data."""
    import zipfile

    _ensure_dirs()
    with zipfile.ZipFile(src_zip_path, "r") as zf:
        names = set(zf.namelist())
        if not ({"settings.json", "history.db"} & names):
            raise ValueError("This doesn't look like a Foxtale backup file.")

        if "settings.json" in names:
            SETTINGS_PATH.write_bytes(zf.read("settings.json"))
        if "calibration.json" in names:
            CALIBRATION_PATH.write_bytes(zf.read("calibration.json"))
        if "history.db" in names:
            DB_PATH.write_bytes(zf.read("history.db"))
        for name in names:
            if name.startswith("images/") and not name.endswith("/"):
                out_path = IMAGES_DIR / Path(name).name
                out_path.write_bytes(zf.read(name))
