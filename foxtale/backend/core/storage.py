"""SQLite persistence for scans, settings and the 30-day trash.

Everything lives under one data directory (default ~/.foxtale_web, override
with the FOXTALE_DATA_DIR environment variable): history.db plus an images/
folder. Scans are plain dicts so they can go straight to the JSON API.
"""

import io
import json
import os
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

TRASH_RETENTION_DAYS = 30

DEFAULT_SETTINGS: Dict[str, Any] = {
    "save_history": True,
    "save_images": False,
    "theme": "light",
    "reminder_days": 7,
    "min_confidence": 0.0,
    "owned_products": [],
    "onboarding_complete": False,
    # WhatsApp report delivery. The number, its verified flag and "skipped" are only ever set by the server
    # after an OTP check (see SERVER_CONTROLLED); the browser can change only whatsapp_auto.
    "whatsapp_number": "",
    "whatsapp_verified": False,
    "whatsapp_auto": True,
    "whatsapp_skipped": False,
}

SERVER_CONTROLLED = {"whatsapp_number", "whatsapp_verified", "whatsapp_skipped"}

ROUTINE_OPTIONS = ["Cleanser", "Moisturiser", "Sunscreen", "Treatment", "Exfoliator", "Other"]
ENVIRONMENT_OPTIONS = ["Travel", "Outdoor exposure", "High humidity", "Low humidity"]


def data_dir() -> Path:
    path = Path(os.environ.get("FOXTALE_DATA_DIR") or (Path.home() / ".foxtale_web"))
    (path / "images").mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir() / "history.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scans ("
        "id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, analysis_json TEXT NOT NULL, regions_json TEXT NOT NULL, "
        "quality_json TEXT, image_path TEXT, note TEXT DEFAULT '', starred INTEGER DEFAULT 0, "
        "journal_json TEXT, deleted_at TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS deliveries (scan_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
        "error TEXT, updated_at TEXT NOT NULL)"
    )
    return conn


# ------------------------------------------------------------------ settings

def load_settings() -> Dict[str, Any]:
    conn = _connect()
    rows = conn.execute("SELECT key, value_json FROM settings").fetchall()
    conn.close()
    merged = dict(DEFAULT_SETTINGS)
    for key, value in rows:
        if key in DEFAULT_SETTINGS:
            try:
                merged[key] = json.loads(value)
            except ValueError:
                pass
    return merged


def public_settings() -> Dict[str, Any]:
    """Settings for the browser: the phone number itself is never sent, only whether one is registered."""
    s = load_settings()
    number = s.pop("whatsapp_number", "")
    s["whatsapp_registered"] = bool(number and s.get("whatsapp_verified"))
    return s


def save_settings(patch: Dict[str, Any], internal: bool = False) -> Dict[str, Any]:
    clean = {k: v for k, v in patch.items()
             if k in DEFAULT_SETTINGS and (internal or k not in SERVER_CONTROLLED)}
    conn = _connect()
    with conn:
        for key, value in clean.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value_json) VALUES (?, ?)", (key, json.dumps(value)))
    conn.close()
    return load_settings()


# --------------------------------------------------------------------- scans

_COLUMNS = "id, timestamp, analysis_json, regions_json, quality_json, image_path, note, starred, journal_json, deleted_at"


def _row_to_scan(row) -> Dict[str, Any]:
    scan_id, timestamp, analysis_json, regions_json, quality_json, image_path, note, starred, journal_json, deleted_at = row
    return {
        "id": scan_id,
        "timestamp": timestamp,
        "analysis": json.loads(analysis_json),
        "regions": json.loads(regions_json),
        "quality": json.loads(quality_json) if quality_json else None,
        "hasImage": bool(image_path and Path(image_path).exists()),
        "note": note or "",
        "starred": bool(starred),
        "journal": json.loads(journal_json) if journal_json else {"routine": [], "environment": []},
        "deletedAt": deleted_at,
        "persisted": True,
    }


def transient_scan(analysis: dict, regions: list, quality: Optional[dict]) -> Dict[str, Any]:
    """A scan that is shown but never written to disk ('Save scan history' is off)."""
    return {
        "id": f"transient-{uuid.uuid4()}",
        "timestamp": datetime.now().isoformat(),
        "analysis": analysis, "regions": regions, "quality": quality,
        "hasImage": False, "note": "", "starred": False,
        "journal": {"routine": [], "environment": []}, "deletedAt": None, "persisted": False,
    }


def save_scan(analysis: dict, regions: list, quality: Optional[dict], image_bytes: Optional[bytes]) -> Dict[str, Any]:
    scan_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    image_path = None
    if image_bytes:
        image_path = str(data_dir() / "images" / f"{scan_id}.jpg")
        Path(image_path).write_bytes(image_bytes)
    conn = _connect()
    with conn:
        conn.execute(
            f"INSERT INTO scans ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, '', 0, NULL, NULL)",
            (scan_id, timestamp, json.dumps(analysis), json.dumps(regions),
             json.dumps(quality) if quality else None, image_path),
        )
    conn.close()
    return get_scan(scan_id)  # type: ignore[return-value]


def get_scan(scan_id: str, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
    conn = _connect()
    row = conn.execute(f"SELECT {_COLUMNS} FROM scans WHERE id = ?", (scan_id,)).fetchone()
    conn.close()
    if not row:
        return None
    scan = _row_to_scan(row)
    if scan["deletedAt"] and not include_deleted:
        return None
    return scan


def image_path(scan_id: str) -> Optional[Path]:
    conn = _connect()
    row = conn.execute("SELECT image_path FROM scans WHERE id = ?", (scan_id,)).fetchone()
    conn.close()
    if row and row[0] and Path(row[0]).exists():
        return Path(row[0])
    return None


def list_scans() -> List[Dict[str, Any]]:
    """Active scans, newest first."""
    conn = _connect()
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM scans WHERE deleted_at IS NULL ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [_row_to_scan(r) for r in rows]


def update_scan(scan_id: str, note: Optional[str] = None, starred: Optional[bool] = None,
                journal: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    conn = _connect()
    with conn:
        if note is not None:
            conn.execute("UPDATE scans SET note = ? WHERE id = ?", (note[:2000], scan_id))
        if starred is not None:
            conn.execute("UPDATE scans SET starred = ? WHERE id = ?", (1 if starred else 0, scan_id))
        if journal is not None:
            clean = {
                "routine": [r for r in journal.get("routine", []) if r in ROUTINE_OPTIONS],
                "environment": [e for e in journal.get("environment", []) if e in ENVIRONMENT_OPTIONS],
            }
            conn.execute("UPDATE scans SET journal_json = ? WHERE id = ?", (json.dumps(clean), scan_id))
    conn.close()
    return get_scan(scan_id)


# --------------------------------------------------------------------- trash

def trash_scan(scan_id: str) -> bool:
    conn = _connect()
    with conn:
        cur = conn.execute(
            "UPDATE scans SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL", (datetime.now().isoformat(), scan_id)
        )
    conn.close()
    return cur.rowcount > 0


def restore_scan(scan_id: str) -> bool:
    conn = _connect()
    with conn:
        cur = conn.execute("UPDATE scans SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL", (scan_id,))
    conn.close()
    return cur.rowcount > 0


def purge_expired_trash() -> int:
    cutoff = (datetime.now() - timedelta(days=TRASH_RETENTION_DAYS)).isoformat()
    conn = _connect()
    ids = [r[0] for r in conn.execute("SELECT id FROM scans WHERE deleted_at IS NOT NULL AND deleted_at < ?", (cutoff,))]
    conn.close()
    for scan_id in ids:
        delete_permanently(scan_id)
    return len(ids)


def list_trash() -> List[Dict[str, Any]]:
    purge_expired_trash()
    conn = _connect()
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM scans WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        scan = _row_to_scan(r)
        deleted = datetime.fromisoformat(scan["deletedAt"])
        scan["daysLeft"] = max(0, TRASH_RETENTION_DAYS - (datetime.now() - deleted).days)
        out.append(scan)
    return out


def delete_permanently(scan_id: str) -> bool:
    path = image_path(scan_id)
    if path:
        path.unlink(missing_ok=True)
    conn = _connect()
    with conn:
        cur = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    conn.close()
    return cur.rowcount > 0


def empty_trash() -> int:
    conn = _connect()
    ids = [r[0] for r in conn.execute("SELECT id FROM scans WHERE deleted_at IS NOT NULL")]
    conn.close()
    for scan_id in ids:
        delete_permanently(scan_id)
    return len(ids)


# ------------------------------------------------------------------- privacy

def stats() -> Dict[str, Any]:
    conn = _connect()
    active = conn.execute("SELECT COUNT(*) FROM scans WHERE deleted_at IS NULL").fetchone()[0]
    trashed = conn.execute("SELECT COUNT(*) FROM scans WHERE deleted_at IS NOT NULL").fetchone()[0]
    conn.close()
    images = list((data_dir() / "images").glob("*.jpg"))
    return {
        "scanCount": active,
        "trashCount": trashed,
        "imageCount": len(images),
        "diskBytes": sum(p.stat().st_size for p in images) + (data_dir() / "history.db").stat().st_size,
        "dataDir": str(data_dir()),
    }


def wipe_all() -> None:
    d = data_dir()
    shutil.rmtree(d / "images", ignore_errors=True)
    (d / "images").mkdir(parents=True, exist_ok=True)
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM scans")
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM deliveries")
    conn.close()


def export_zip() -> bytes:
    """Everything the app stores, as one zip: scans.json, settings.json and photos."""
    buf = io.BytesIO()
    conn = _connect()
    rows = conn.execute(f"SELECT {_COLUMNS} FROM scans ORDER BY timestamp").fetchall()
    conn.close()
    scans = [_row_to_scan(r) for r in rows]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("scans.json", json.dumps(scans, indent=2))
        zf.writestr("settings.json", json.dumps(load_settings(), indent=2))
        for scan in scans:
            p = image_path(scan["id"])
            if p:
                zf.write(p, f"images/{scan['id']}.jpg")
    return buf.getvalue()


def import_zip(data: bytes) -> int:
    """Restore scans from an export made by export_zip(). Existing ids are skipped."""
    count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        scans = json.loads(zf.read("scans.json"))
        conn = _connect()
        with conn:
            for s in scans:
                if conn.execute("SELECT 1 FROM scans WHERE id = ?", (s["id"],)).fetchone():
                    continue
                path = None
                member = f"images/{s['id']}.jpg"
                if member in zf.namelist():
                    path = str(data_dir() / "images" / f"{s['id']}.jpg")
                    Path(path).write_bytes(zf.read(member))
                conn.execute(
                    f"INSERT INTO scans ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (s["id"], s["timestamp"], json.dumps(s["analysis"]), json.dumps(s["regions"]),
                     json.dumps(s["quality"]) if s.get("quality") else None, path, s.get("note", ""),
                     1 if s.get("starred") else 0, json.dumps(s.get("journal") or {"routine": [], "environment": []}),
                     s.get("deletedAt")),
                )
                count += 1
        conn.close()
    return count


# ---------------------------------------------------------------- deliveries

def set_delivery(scan_id: str, status: str, error: Optional[str] = None) -> None:
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO deliveries (scan_id, status, error, updated_at) VALUES (?, ?, ?, ?)",
            (scan_id, status, error, datetime.now().isoformat()),
        )
    conn.close()


def get_delivery(scan_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    row = conn.execute("SELECT status, error, updated_at FROM deliveries WHERE scan_id = ?", (scan_id,)).fetchone()
    conn.close()
    return {"status": row[0], "error": row[1], "updatedAt": row[2]} if row else None
