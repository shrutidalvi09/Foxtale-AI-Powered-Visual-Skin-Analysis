"""Trained acne-severity model (CNN, ONNX) -- an additive, learned signal next to the classical engine.

The model is trained by `foxtale/training/train.py` on ACNE04 (4-level Hayashi severity grade plus
lesion count, academic-use-only licence -- see training/README.md) and exported to
`assets/models/acne_severity.onnx`. It runs through OpenCV's DNN module, so the backend needs no
PyTorch. ImageNet normalisation is baked into the exported graph: the input is a 1x3xNxN RGB
float tensor in 0-255.

`crop_for_model` is imported by the training script too, so train-time and app-time crops match.
If the model file is missing, `predict_acne` returns None and the app behaves exactly as before.
"""

import json
import os
import threading
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

MODEL_INPUT = 320
CROP_PAD = 1.3  # crop side = CROP_PAD x the (square) face box side
SEVERITY = ["mild", "moderate", "severe", "very_severe"]

_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "models")
MODEL_PATH = os.environ.get("ACNE_MODEL_PATH", os.path.join(_MODEL_DIR, "acne_severity.onnx"))
META_PATH = os.path.splitext(MODEL_PATH)[0] + ".json"

_net = None
_meta: Dict[str, Any] = {}
_lock = threading.Lock()
_loaded = False


def crop_for_model(image: np.ndarray, box: Optional[Tuple[int, int, int, int]], size: int = MODEL_INPUT) -> np.ndarray:
    """Square crop around the face box (or the whole photo if no box), zero-padded where it runs
    off the image, resized to size x size. BGR in, BGR out."""
    ih, iw = image.shape[:2]
    if box is not None:
        x, y, w, h = box
        side = int(round(CROP_PAD * max(w, h)))
        cx, cy = x + w / 2, y + h / 2
    else:
        side = max(iw, ih)
        cx, cy = iw / 2, ih / 2
    x0, y0 = int(round(cx - side / 2)), int(round(cy - side / 2))
    pad = [max(0, -y0), max(0, y0 + side - ih), max(0, -x0), max(0, x0 + side - iw)]
    crop = image[max(0, y0):min(ih, y0 + side), max(0, x0):min(iw, x0 + side)]
    if any(pad):
        crop = cv2.copyMakeBorder(crop, *pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)


def _load() -> None:
    global _net, _meta, _loaded
    _loaded = True
    if not os.path.exists(MODEL_PATH):
        return
    try:
        _net = cv2.dnn.readNetFromONNX(MODEL_PATH)
    except cv2.error:
        _net = None
        return
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            _meta = json.load(f)


def model_info() -> Optional[Dict[str, Any]]:
    with _lock:
        if not _loaded:
            _load()
    return dict(_meta, loaded=True) if _net is not None else None


def predict_acne(image: np.ndarray, box: Optional[Tuple[int, int, int, int]]) -> Optional[Dict[str, Any]]:
    """Severity probabilities, the most likely grade, a 0-1 severity score and an estimated lesion
    count for the face in `image` (BGR). None if no model is installed."""
    with _lock:
        if not _loaded:
            _load()
        if _net is None:
            return None
        size = int(_meta.get("input_size", MODEL_INPUT))
        crop = crop_for_model(image, box, size)
        blob = cv2.dnn.blobFromImage(crop, 1.0, (size, size), swapRB=True)
        _net.setInput(blob)
        logits, log_count = _net.forward(["severity_logits", "log_lesions"])
    z = logits[0] - logits[0].max()
    probs = np.exp(z) / np.exp(z).sum()
    level = int(probs.argmax())
    expected = float((probs * np.arange(len(SEVERITY))).sum())
    return {
        "severity": SEVERITY[level],
        "level": level,
        "confidence": round(float(probs[level]), 3),
        "probabilities": {name: round(float(p), 3) for name, p in zip(SEVERITY, probs)},
        "severity_score": round(expected / (len(SEVERITY) - 1), 3),  # 0 = mild .. 1 = very severe
        "lesion_estimate": int(round(max(0.0, float(np.expm1(log_count.reshape(-1)[0]))))),
        "model": _meta.get("name", "acne_severity"),
        "model_version": _meta.get("version"),
    }
