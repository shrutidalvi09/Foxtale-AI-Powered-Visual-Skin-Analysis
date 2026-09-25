"""Foxtale backend -- FastAPI entrypoint.

Run locally with:
    uvicorn main:app --reload

Photos are analysed on this machine (OpenCV, no cloud calls). Scans, notes and
settings are stored in a local SQLite database under ~/.foxtale_web (override
with FOXTALE_DATA_DIR).
"""

import asyncio
import json
import base64
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import conflicts, delivery, diary, digest, effects, ingredients, insights, report_builder, storage, weather, whatsapp
from engine.face_detection import detect_face
from engine.image_processing import split_regions
from engine.quality import compute_quality
from engine.schemas import DISCLAIMER
from engine.skin_analysis import analyze_face, quick_spots
from utils.image_utils import decode_image, resize_max_dim

ASSETS = Path(__file__).resolve().parent / "assets"

async def _digest_loop() -> None:
    """Checks every 30 minutes whether the weekly WhatsApp check-in is due. Runs while the server is up."""
    while True:
        try:
            await run_in_threadpool(digest.maybe_send)
        except Exception:  # noqa: BLE001 - never let the scheduler die
            pass
        await asyncio.sleep(1800)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # products already marked "I use this" before usage tracking existed start counting from today
    storage.usage_sync(storage.load_settings().get("owned_products", []))
    task = asyncio.create_task(_digest_loop())
    yield
    task.cancel()


app = FastAPI(
    lifespan=lifespan,
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
app.mount("/combo-images", StaticFiles(directory=ASSETS / "combos"), name="combo-images")
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


def _capture_checks(frame, box) -> Dict[str, str]:
    """Is this frame good enough to capture? Each check is 'ok' or a short reason."""
    h, w = frame.shape[:2]
    x, y, bw, bh = box
    crop = frame[max(0, y):y + bh, max(0, x):x + bw]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    sharp = float(cv2.Laplacian(cv2.resize(gray, (160, 160)), cv2.CV_64F).var())
    cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
    size = bw / w
    return {
        "lighting": "too_dark" if brightness < 75 else "too_bright" if brightness > 225 else "ok",
        "distance": "too_far" if size < 0.34 else "too_close" if size > 0.78 else "ok",
        "centered": "left" if cx < 0.4 else "right" if cx > 0.6 else "up" if cy < 0.38 else "down" if cy > 0.62 else "ok",
        "sharpness": "blurry" if sharp < 25 else "ok",
    }


@app.post("/api/live")
async def live(image: UploadFile = File(...)) -> Dict[str, Any]:
    """Fast preview pass for the live camera view: is a face in frame, and where are the spots.
    Nothing is stored; the full analysis still runs on the captured photo."""
    raw = await image.read()
    try:
        frame = resize_max_dim(decode_image(raw), max_dim=480)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    face = detect_face(frame)
    if not face.ok:
        return {"face": None, "spots": [], "message": face.message, "error": face.error}
    h, w = frame.shape[:2]
    x, y, bw, bh = face.box
    spots = quick_spots(split_regions(frame, face.box))
    return {
        "face": {"x": x / w, "y": y / h, "w": bw / w, "h": bh / h},
        "spots": spots, "message": None, "error": None,
        "checks": _capture_checks(frame, face.box),
    }


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
        return report_builder.build(body.analysis, body.regions, body.previousAnalysis, owned,
                                    storage.load_settings().get("profile") or None)
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


# ------------------------------------------------------------------ profile

ALLOWED_GOALS = {"acne", "dark_spots", "anti_aging", "hydration", "oil_control", "redness", "texture", "under_eye", "brightening"}


class ProfileBody(BaseModel):
    name: str = ""
    age_range: str = ""
    gender: str = ""
    goals: List[str] = []
    sensitive_skin: bool = False
    pregnant: bool = False
    allergies: str = ""
    budget: str = "any"
    onboarded: bool = True


@app.get("/api/profile")
def get_profile() -> Dict[str, Any]:
    return storage.load_settings().get("profile") or {}


@app.put("/api/profile")
def put_profile(body: ProfileBody) -> Dict[str, Any]:
    profile = {
        "name": body.name.strip()[:60], "age_range": body.age_range[:20], "gender": body.gender[:20],
        "goals": [g for g in body.goals if g in ALLOWED_GOALS], "sensitive_skin": body.sensitive_skin,
        "pregnant": body.pregnant, "allergies": body.allergies.strip()[:200],
        "budget": body.budget if body.budget in ("any", "low", "mid") else "any", "onboarded": body.onboarded,
    }
    storage.save_settings({"profile": profile})
    return profile


# ------------------------------------------------------------------ routine tracker

class RoutineToggle(BaseModel):
    day: str
    slot: str
    productId: str
    done: bool


@app.get("/api/routine")
def routine(days: int = 21) -> Dict[str, Any]:
    from datetime import date, timedelta
    today = date.today()
    since = (today - timedelta(days=max(1, min(days, 120)) - 1)).isoformat()
    logged = storage.routine_days(since)
    history = []
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        entry = logged.get(d, {"AM": [], "PM": []})
        history.append({"day": d, "am": len(entry["AM"]), "pm": len(entry["PM"])})
    streak = 0
    for item in reversed(history):
        if item["am"] + item["pm"] > 0:
            streak += 1
        elif item["day"] == today.isoformat():
            continue  # today is not over yet
        else:
            break
    return {"today": logged.get(today.isoformat(), {"AM": [], "PM": []}), "history": history, "streak": streak,
            "todayDate": today.isoformat()}


@app.post("/api/routine")
def routine_toggle(body: RoutineToggle) -> Dict[str, bool]:
    if body.slot not in ("AM", "PM") or len(body.day) != 10:
        raise HTTPException(status_code=422, detail="Invalid routine entry.")
    storage.routine_toggle(body.day, body.slot, body.productId[:60], body.done)
    return {"ok": True}


# -------------------------------------------------- ingredient + routine checks, product results, weekly digest

class IngredientBody(BaseModel):
    text: str


@app.post("/api/ingredients/check")
def ingredients_check(body: IngredientBody) -> Dict[str, Any]:
    from core import skincare_advisor as adv
    settings = storage.load_settings()
    scans = storage.list_scans()
    owned = set(settings.get("owned_products", []))
    owned_classes: Dict[str, List[str]] = {}
    for p in adv.load_catalog():
        if p.id in owned:
            for c in conflicts.classes_of(p):
                owned_classes.setdefault(c, []).append(p.name)
    return ingredients.check(body.text[:6000], settings.get("profile") or None, scans[0]["analysis"] if scans else None, owned_classes)


@app.get("/api/effects")
def product_effects() -> List[Dict[str, Any]]:
    return effects.compute()


@app.get("/api/routine/check")
def routine_check() -> Dict[str, Any]:
    """Clash check for the products the user says they actually use."""
    from core import skincare_advisor as adv
    owned = set(storage.load_settings().get("owned_products", []))
    products = [p for p in adv.load_catalog() if p.id in owned]
    return {"products": [p.name for p in products], "issues": conflicts.check(products)}


class ProductStart(BaseModel):
    productId: str
    startedAt: str  # YYYY-MM-DD


@app.put("/api/effects/start")
def effects_start(body: ProductStart) -> Dict[str, bool]:
    """Let the user correct the date they really started a product (they may have used it for weeks)."""
    from datetime import date as _date
    try:
        _date.fromisoformat(body.startedAt)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Use a date like 2026-09-01.") from exc
    if body.productId not in storage.usage_all():
        raise HTTPException(status_code=404, detail="Mark the product as one you use first.")
    storage.usage_set_start(body.productId, body.startedAt + "T00:00:00")
    return {"ok": True}


class DigestBody(BaseModel):
    enabled: bool
    day: int = 6
    hour: int = 9


@app.get("/api/digest")
def digest_status() -> Dict[str, Any]:
    s = storage.load_settings()
    return {
        "enabled": bool(s.get("weekly_digest")), "day": int(s.get("digest_day", 6)), "hour": int(s.get("digest_hour", 9)),
        "lastSent": s.get("digest_last_sent") or None, "preview": digest.build(),
        "registered": bool(s.get("whatsapp_verified") and s.get("whatsapp_number")),
    }


@app.put("/api/digest")
def digest_update(body: DigestBody) -> Dict[str, Any]:
    storage.save_settings({"weekly_digest": body.enabled, "digest_day": max(0, min(6, body.day)), "digest_hour": max(0, min(23, body.hour))})
    return digest_status()


@app.post("/api/digest/send")
def digest_send() -> Dict[str, Any]:
    ok, message = digest.send_now()
    if not ok:
        raise HTTPException(status_code=409, detail=message)
    return {"ok": True}


# ------------------------------------------------------------------ shop catalog

@app.get("/api/catalog")
def catalog() -> Dict[str, Any]:
    """Every Foxtale product and combo in the local catalog, for the Shop page."""
    from core import skincare_advisor as adv
    products = []
    for p in adv.load_catalog():
        products.append({
            "id": p.id, "name": p.name, "step": p.step, "stepLabel": dict(adv.STEPS).get(p.step, p.step), "when": p.when,
            "ingredients": p.key_ingredients, "targets": p.targets,
            "targetLabels": [adv.CATEGORY_LABELS[t] for t in p.targets if t in adv.CATEGORY_LABELS],
            "skinTypes": p.skin_types, "active": p.active, "howItWorks": p.how_it_works, "howToUse": p.how_to_use,
            "caution": p.caution, "url": p.url, "size": p.size, "price": p.price_inr, "priceSource": p.price_source,
            "variantId": p.variant_id, "shape": p.shape, "reason": "",
            "image": f"/product-images/{p.id}.jpg" if (ASSETS / "products" / f"{p.id}.jpg").exists() else None,
            "owned": p.id in set(storage.load_settings().get("owned_products", [])),
        })
    try:
        combos = json.loads((ASSETS / "foxtale_combos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        combos = {"combos": [], "note": ""}
    return {"products": products, "combos": combos["combos"], "comboNote": combos.get("note", ""),
            "catalogDate": adv.catalog_date(), "priceNote": adv.catalog_price_note()}


# ------------------------------------------------------------------ skin weather

class LocationBody(BaseModel):
    city: str


@app.put("/api/location")
def set_location(body: LocationBody) -> Dict[str, Any]:
    try:
        loc = weather.geocode(body.city)
    except weather.WeatherError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    storage.save_settings({"location": loc})
    return loc


@app.delete("/api/location")
def clear_location() -> Dict[str, bool]:
    storage.save_settings({"location": {}})
    return {"ok": True}


@app.get("/api/weather")
def skin_weather() -> Dict[str, Any]:
    from core import skincare_advisor as adv
    from engine.schemas import SkinAnalysis
    loc = storage.load_settings().get("location") or {}
    if not loc.get("lat"):
        return {"configured": False}
    try:
        w = weather.fetch(float(loc["lat"]), float(loc["lon"]))
    except weather.WeatherError as exc:
        return {"configured": True, "error": str(exc), "city": loc.get("name")}
    scans = storage.list_scans()
    skin_type = adv.skin_profile(SkinAnalysis.from_dict(scans[0]["analysis"])).skin_type if scans else "normal"
    tip_list = weather.tips(w, skin_type)
    names = {p.id: p.name for p in adv.load_catalog()}
    for t in tip_list:
        t["productNames"] = [names[i] for i in t["products"] if i in names]
    return {
        "configured": True, "city": loc.get("name"), "skinType": skin_type, "temp": w["temp"], "humidity": w["humidity"],
        "uv": w["uv"], "uvLabel": weather.uv_label(w["uv"]) if w["uv"] is not None else None,
        "aqi": w["aqi"], "aqiLabel": weather.aqi_label(w["aqi"]) if w["aqi"] is not None else None, "tips": tip_list,
    }


# ------------------------------------------------------------------ skin diary

class DiaryBody(BaseModel):
    sleep_hours: Optional[float] = None
    water_glasses: Optional[int] = None
    stress: Optional[int] = None
    skin_feel: Optional[int] = None
    flags: List[str] = []
    note: str = ""


@app.get("/api/diary")
def diary_list(days: int = 60) -> Dict[str, Any]:
    from datetime import date as _d, timedelta as _td
    since = (_d.today() - _td(days=max(1, min(days, 400)))).isoformat()
    entries = storage.diary_all(since)
    return {"entries": [dict(day=d, **e) for d, e in entries.items()], "flags": diary.FLAGS}


@app.put("/api/diary/{day}")
def diary_save(day: str, body: DiaryBody) -> Dict[str, Any]:
    from datetime import date as _d
    try:
        d = _d.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Use a date like 2026-09-25.") from exc
    if d > _d.today():
        raise HTTPException(status_code=422, detail="You can only log today or earlier.")
    entry = diary.clean(body.model_dump())
    storage.diary_put(day, entry)
    return dict(day=day, **entry)


@app.delete("/api/diary/{day}")
def diary_remove(day: str) -> Dict[str, bool]:
    storage.diary_delete(day)
    return {"ok": True}


@app.get("/api/diary/patterns")
def diary_patterns() -> Dict[str, Any]:
    return diary.patterns(storage.diary_all(), storage.list_scans())


# ----------------------------------------------------------------- settings

@app.get("/api/settings")
def get_settings() -> Dict[str, Any]:
    return storage.public_settings()


@app.put("/api/settings")
def put_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    storage.save_settings(patch)  # server-controlled keys (WhatsApp number/verified) are ignored here
    if "owned_products" in patch and isinstance(patch["owned_products"], list):
        storage.usage_sync([str(x) for x in patch["owned_products"]])
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
