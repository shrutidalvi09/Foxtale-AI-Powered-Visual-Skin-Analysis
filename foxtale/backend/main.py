"""Foxtale backend -- FastAPI entrypoint.

Run locally with:
    uvicorn main:app --reload

Photos are analysed on this machine (OpenCV, no cloud calls). Scans, notes and
settings are stored in a local SQLite database under ~/.foxtale_web (override
with FOXTALE_DATA_DIR).
"""

import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import delivery, insights, report_builder, storage, whatsapp
from engine.face_detection import detect_face
from engine.image_processing import split_regions
from engine.quality import compute_quality
from engine.schemas import DISCLAIMER
from engine.skin_analysis import analyze_face
from utils.image_utils import decode_image, resize_max_dim

ASSETS = Path(__file__).resolve().parent / "assets"

app = FastAPI(
    title="Foxtale API",
    description="Visual, AI-assisted skin observation API. Not a medical diagnosis tool.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/product-images", StaticFiles(directory=ASSETS / "products"), name="product-images")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ------------------------------------------------------------------ analyze

def _jpeg_bytes(image) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes() if ok else b""


@app.post("/api/analyze")
async def analyze(background_tasks: BackgroundTasks, image: UploadFile = File(...)) -> Dict[str, Any]:
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=415, detail="Please upload a JPEG, PNG, or WebP image.")
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty image upload.")
    try:
        cv_image = decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cv_image = resize_max_dim(cv_image, max_dim=900)
    face = detect_face(cv_image)
    if not face.ok:
        return {"faceDetected": False, "error": face.error, "message": face.message, "disclaimer": DISCLAIMER}

    settings = storage.load_settings()
    # The v2 engine reads the untouched photo (it flattens lighting per region itself).
    regions = split_regions(cv_image, face.box)
    analysis, observations = analyze_face(regions, None, float(settings.get("min_confidence", 0.0)))
    if analysis.overall_score is None:
        return {
            "faceDetected": False, "error": "not_enough_skin", "disclaimer": DISCLAIMER,
            "message": "Not enough clearly visible skin was found in this photo. Face the camera, keep hair "
                       "and hands off your face, and try again.",
        }

    quality = compute_quality(cv_image, face.box)
    quality_dict = dict(quality.to_dict(), tips=quality.tips)
    analysis_dict = analysis.to_dict()
    regions_list = [o.to_dict() for o in observations]

    scans_before = storage.list_scans()
    previous = scans_before[0]["analysis"] if scans_before else None

    if settings.get("save_history", True):
        image_bytes = _jpeg_bytes(cv_image) if settings.get("save_images", False) else None
        scan = storage.save_scan(analysis_dict, regions_list, quality_dict, image_bytes)
    else:
        scan = storage.transient_scan(analysis_dict, regions_list, quality_dict)

    delivering = delivery.should_deliver(settings)
    if delivering:
        storage.set_delivery(scan["id"], "pending")
        background_tasks.add_task(delivery.deliver_new_scan, scan, cv_image, previous)
    return {"faceDetected": True, "scan": scan, "disclaimer": DISCLAIMER,
            "whatsapp": "pending" if delivering else None}


# -------------------------------------------------------------------- scans

@app.get("/api/scans")
def list_scans() -> List[Dict[str, Any]]:
    return storage.list_scans()


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str) -> Dict[str, Any]:
    scan = storage.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


@app.get("/api/scans/{scan_id}/image")
def get_scan_image(scan_id: str):
    path = storage.image_path(scan_id)
    if not path:
        raise HTTPException(status_code=404, detail="No photo was saved for this scan.")
    return FileResponse(path, media_type="image/jpeg")


class ScanPatch(BaseModel):
    note: Optional[str] = None
    starred: Optional[bool] = None
    journal: Optional[Dict[str, List[str]]] = None


@app.patch("/api/scans/{scan_id}")
def patch_scan(scan_id: str, body: ScanPatch) -> Dict[str, Any]:
    if not storage.get_scan(scan_id):
        raise HTTPException(status_code=404, detail="Scan not found.")
    return storage.update_scan(scan_id, note=body.note, starred=body.starred, journal=body.journal)  # type: ignore[return-value]


@app.delete("/api/scans/{scan_id}")
def delete_scan(scan_id: str) -> Dict[str, bool]:
    if not storage.trash_scan(scan_id):
        raise HTTPException(status_code=404, detail="Scan not found.")
    return {"ok": True}


@app.get("/api/trash")
def list_trash() -> List[Dict[str, Any]]:
    return storage.list_trash()


@app.post("/api/trash/{scan_id}/restore")
def restore(scan_id: str) -> Dict[str, bool]:
    if not storage.restore_scan(scan_id):
        raise HTTPException(status_code=404, detail="Scan not found in Recently Deleted.")
    return {"ok": True}


@app.delete("/api/trash/{scan_id}")
def delete_forever(scan_id: str) -> Dict[str, bool]:
    if not storage.delete_permanently(scan_id):
        raise HTTPException(status_code=404, detail="Scan not found.")
    return {"ok": True}


@app.delete("/api/trash")
def empty_trash() -> Dict[str, int]:
    return {"deleted": storage.empty_trash()}


# ------------------------------------------------------------------- report

class ReportRequest(BaseModel):
    analysis: Dict[str, Any]
    regions: List[Dict[str, Any]] = []
    previousAnalysis: Optional[Dict[str, Any]] = None
    owned: Optional[List[str]] = None


@app.post("/api/report")
def report(body: ReportRequest) -> Dict[str, Any]:
    """Full report content (score, categories, regions, changes, tips, skincare)
    for any scan -- saved or transient."""
    owned = body.owned if body.owned is not None else storage.load_settings().get("owned_products", [])
    try:
        return report_builder.build(body.analysis, body.regions, body.previousAnalysis, owned)
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid analysis data.") from exc


class PdfRequest(ReportRequest):
    timestamp: Optional[str] = None
    quality: Optional[Dict[str, Any]] = None
    note: str = ""
    imageDataUrl: Optional[str] = None  # photo of a scan that is not saved on the server


@app.post("/api/report/pdf")
def report_pdf(body: PdfRequest, scanId: Optional[str] = None) -> Response:
    image = None
    stored = storage.image_path(scanId) if scanId else None
    if stored:
        image = cv2.imread(str(stored))
    elif body.imageDataUrl and "," in body.imageDataUrl:
        try:
            image = decode_image(base64.b64decode(body.imageDataUrl.split(",", 1)[1]))
        except Exception:  # noqa: BLE001 - a bad photo just means a photo-less report
            image = None
    scan = {
        "analysis": body.analysis, "regions": body.regions, "quality": body.quality, "note": body.note,
        "timestamp": body.timestamp or datetime.now().isoformat(),
    }
    try:
        data = delivery.make_pdf(scan, body.previousAnalysis, image)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid analysis data.") from exc
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="foxtale-report.pdf"'})


# ---------------------------------------------------------------- dashboard

@app.get("/api/insights")
def get_insights() -> Dict[str, Any]:
    scans = storage.list_scans()
    data = insights.compute(scans)
    data["baseline"] = insights.baseline(scans)
    data["latest"] = scans[0] if scans else None
    return data


# ----------------------------------------------------------------- settings

@app.get("/api/settings")
def get_settings() -> Dict[str, Any]:
    return storage.public_settings()


@app.put("/api/settings")
def put_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    storage.save_settings(patch)  # server-controlled keys (WhatsApp number/verified) are ignored here
    return storage.public_settings()


@app.get("/api/options")
def options() -> Dict[str, Any]:
    return {"routine": storage.ROUTINE_OPTIONS, "environment": storage.ENVIRONMENT_OPTIONS}


# ------------------------------------------------------------------ privacy

@app.get("/api/privacy")
def privacy() -> Dict[str, Any]:
    return storage.stats()


@app.get("/api/export")
def export_data() -> Response:
    return Response(content=storage.export_zip(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="foxtale-export.zip"'})


@app.post("/api/import")
async def import_data(file: UploadFile = File(...)) -> Dict[str, int]:
    try:
        return {"imported": storage.import_zip(await file.read())}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="That file is not a valid Foxtale export.") from exc


@app.delete("/api/data")
def wipe() -> Dict[str, bool]:
    storage.wipe_all()
    return {"ok": True}


# ----------------------------------------------------------------- whatsapp

def _wa_status() -> Dict[str, Any]:
    s = storage.load_settings()
    registered = bool(s.get("whatsapp_number") and s.get("whatsapp_verified"))
    return {
        "configured": whatsapp.is_configured(),
        "dryRun": whatsapp.dry_run(),
        "registered": registered,
        "masked": whatsapp.mask_phone(s.get("whatsapp_number", "")) if registered else "",
        "auto": bool(s.get("whatsapp_auto", True)),
        "skipped": bool(s.get("whatsapp_skipped", False)),
    }


class PhoneBody(BaseModel):
    phone: str


class CodeBody(BaseModel):
    code: str


class AutoBody(BaseModel):
    enabled: bool


def _wa_error(exc: whatsapp.WhatsAppError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


@app.get("/api/whatsapp/status")
def whatsapp_status() -> Dict[str, Any]:
    return _wa_status()


@app.post("/api/whatsapp/register")
def whatsapp_register(body: PhoneBody) -> Dict[str, Any]:
    """Step 1: send a 6-digit code to the number over WhatsApp."""
    if not whatsapp.is_configured():
        raise HTTPException(status_code=503, detail="WhatsApp is not set up on this server yet.")
    phone = whatsapp.normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=422, detail="Enter the number with its country code, for example +91 98765 43210.")
    try:
        whatsapp.start_verification(phone)
    except whatsapp.WhatsAppError as exc:
        raise _wa_error(exc) from exc
    return {"sent": True, "masked": whatsapp.mask_phone(phone), "dryRun": whatsapp.dry_run()}


@app.post("/api/whatsapp/verify")
def whatsapp_verify(body: CodeBody) -> Dict[str, Any]:
    """Step 2: check the code; on success the number becomes the delivery number."""
    try:
        phone = whatsapp.check_code(body.code)
    except whatsapp.WhatsAppError as exc:
        raise _wa_error(exc) from exc
    storage.save_settings({"whatsapp_number": phone, "whatsapp_verified": True, "whatsapp_skipped": False}, internal=True)
    return _wa_status()


@app.post("/api/whatsapp/skip")
def whatsapp_skip() -> Dict[str, Any]:
    """Only possible while the server has no WhatsApp credentials, so the app is never locked out."""
    if whatsapp.is_configured():
        raise HTTPException(status_code=409, detail="WhatsApp is set up, so registering your number is required.")
    storage.save_settings({"whatsapp_skipped": True}, internal=True)
    return _wa_status()


@app.delete("/api/whatsapp")
def whatsapp_remove() -> Dict[str, Any]:
    storage.save_settings({"whatsapp_number": "", "whatsapp_verified": False, "whatsapp_skipped": False}, internal=True)
    return _wa_status()


@app.put("/api/whatsapp/auto")
def whatsapp_auto(body: AutoBody) -> Dict[str, Any]:
    storage.save_settings({"whatsapp_auto": body.enabled})
    return _wa_status()


@app.get("/api/whatsapp/delivery/{scan_id}")
def whatsapp_delivery(scan_id: str) -> Dict[str, Any]:
    return storage.get_delivery(scan_id) or {"status": "none", "error": None, "updatedAt": None}


@app.post("/api/whatsapp/resend/{scan_id}")
def whatsapp_resend(scan_id: str, background_tasks: BackgroundTasks) -> Dict[str, bool]:
    if not _wa_status()["registered"]:
        raise HTTPException(status_code=409, detail="Register your WhatsApp number first.")
    storage.set_delivery(scan_id, "pending")
    background_tasks.add_task(delivery.resend, scan_id)
    return {"ok": True}
