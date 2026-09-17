"""Foxtale backend -- FastAPI entrypoint.

Run locally with:
    uvicorn main:app --reload
"""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from models.schemas import DISCLAIMER, AnalyzeResponse
from services.face_detection import detect_face
from services.image_processing import normalize, split_regions
from services.skin_analysis import analyze_face
from utils.image_utils import decode_image, resize_max_dim

app = FastAPI(
    title="Foxtale API",
    description="Visual, AI-assisted skin observation API. Not a medical diagnosis tool.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(image: UploadFile = File(...)) -> AnalyzeResponse:
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

    face_result = detect_face(cv_image)
    if not face_result.ok:
        return AnalyzeResponse(
            faceDetected=False,
            error=face_result.error,
            message=face_result.message,
            disclaimer=DISCLAIMER,
        )

    # Normalize lighting/contrast across the whole frame, then split into face
    # regions directly against the full image so region marker coordinates map
    # correctly onto the captured photo shown in the frontend.
    normalized_image = normalize(cv_image)
    regions = split_regions(normalized_image, face_result.box)

    analysis, observations = analyze_face(regions)

    return AnalyzeResponse(
        faceDetected=True,
        analysis=analysis,
        regions=observations,
        disclaimer=DISCLAIMER,
    )
