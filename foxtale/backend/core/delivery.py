"""Builds the PDF report and delivers it to the user's verified WhatsApp number."""

import logging
import tempfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from core import report_builder, storage, whatsapp
from core.annotate import save_annotated_image
from core.face_report_pdf import build_face_report
from core.recommendations import build_recommendations
from engine.quality import QualityResult
from engine.schemas import RegionObservation, SkinAnalysis

logger = logging.getLogger("foxtale.delivery")

# Recently built reports, so "Resend" also works for scans that are not saved (their photo is gone).
_cache: "OrderedDict[str, Tuple[bytes, Tuple[str, str, str, str]]]" = OrderedDict()
_CACHE_MAX = 10


def make_pdf(scan: Dict[str, Any], previous: Optional[dict], image: Optional[np.ndarray]) -> bytes:
    analysis = SkinAnalysis.from_dict(scan["analysis"])
    prev = SkinAnalysis.from_dict(previous) if previous else None
    observations = [RegionObservation.from_dict(r) for r in scan["regions"]]
    quality = QualityResult.from_dict(scan["quality"]) if scan.get("quality") else None
    with tempfile.TemporaryDirectory() as tmp:
        annotated = None
        if image is not None:
            annotated = str(Path(tmp) / "annotated.jpg")
            save_annotated_image(image, observations, annotated)
        dest = str(Path(tmp) / "report.pdf")
        build_face_report(
            dest, analysis, observations, build_recommendations(analysis), annotated_image_path=annotated,
            timestamp=datetime.fromisoformat(scan["timestamp"]).strftime("%Y-%m-%d %H:%M"),
            quality=quality, previous=prev, note=scan.get("note", ""),
        )
        return Path(dest).read_bytes()


def message_params(scan: Dict[str, Any], previous: Optional[dict], owned: list) -> Tuple[str, str, str, str]:
    """Template variables {{1}}..{{4}}: score, summary, routine, date."""
    report = report_builder.build(scan["analysis"], scan["regions"], previous, owned)
    score = f"{report['overallScore']}/100 ({report['scoreLabel']})" if report["overallScore"] is not None else "n/a"
    picks = [s for s in report["skincare"]["suggestions"] if not s["owned"]][:4]
    routine = "; ".join(f"{s['stepLabel']}: {s['name']}" for s in picks) or "Keep up your current routine"
    date = datetime.fromisoformat(scan["timestamp"]).strftime("%d %b %Y")
    return score, report["summary"], routine, date


def _send(scan_id: str, phone: str, pdf: bytes, params: Tuple[str, str, str, str]) -> None:
    storage.set_delivery(scan_id, "sending")
    try:
        whatsapp.send_report(phone, pdf, f"foxtale-report-{params[3].replace(' ', '-')}.pdf", params)
        storage.set_delivery(scan_id, "sent")
    except whatsapp.WhatsAppError as exc:
        logger.warning("Report delivery failed for %s: %s", scan_id, exc)
        storage.set_delivery(scan_id, "failed", str(exc))
    except Exception:  # noqa: BLE001 - never let a background task crash silently
        logger.exception("Unexpected error delivering report %s", scan_id)
        storage.set_delivery(scan_id, "failed", "Something went wrong while sending the report.")


def should_deliver(settings: Dict[str, Any]) -> bool:
    return bool(settings.get("whatsapp_verified") and settings.get("whatsapp_number") and settings.get("whatsapp_auto", True))


def deliver_new_scan(scan: Dict[str, Any], image: Optional[np.ndarray], previous: Optional[dict]) -> None:
    """Runs in a background task right after analysis."""
    settings = storage.load_settings()
    if not should_deliver(settings):
        return
    try:
        pdf = make_pdf(scan, previous, image)
        params = message_params(scan, previous, settings.get("owned_products", []))
    except Exception:  # noqa: BLE001
        logger.exception("Could not build the WhatsApp report for %s", scan["id"])
        storage.set_delivery(scan["id"], "failed", "Could not build the report.")
        return
    _cache[scan["id"]] = (pdf, params)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    _send(scan["id"], settings["whatsapp_number"], pdf, params)


def resend(scan_id: str) -> bool:
    """Send the report again (a manual retry). Returns False if there is nothing to send."""
    settings = storage.load_settings()
    if not (settings.get("whatsapp_verified") and settings.get("whatsapp_number")):
        storage.set_delivery(scan_id, "failed", "Register your WhatsApp number first.")
        return False
    cached = _cache.get(scan_id)
    if cached is None:
        scan = storage.get_scan(scan_id)
        if not scan:
            storage.set_delivery(scan_id, "failed", "This report is no longer available to resend. Run a new scan.")
            return False
        scans = storage.list_scans()
        older = [s for s in scans if s["timestamp"] < scan["timestamp"]]
        previous = older[0]["analysis"] if older else None
        path = storage.image_path(scan_id)
        image = cv2.imread(str(path)) if path else None
        cached = (make_pdf(scan, previous, image), message_params(scan, previous, settings.get("owned_products", [])))
        _cache[scan_id] = cached
    _send(scan_id, settings["whatsapp_number"], *cached)
    return True
