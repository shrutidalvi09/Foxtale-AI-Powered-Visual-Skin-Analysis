"""Export a scan as an annotated PNG (markers drawn on the photo) and/or a
one-page PDF report (summary cards + regions + recommendations + disclaimer).
"""

from typing import List, Optional

import cv2
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from engine.schemas import DISCLAIMER, RegionObservation, SkinAnalysis

CATEGORY_COLOR_BGR = {
    "Acne-like spots": (60, 60, 220),
    "Redness": (0, 140, 255),
    "Texture": (0, 190, 255),
    "Dryness indicators": (255, 170, 80),
}


def save_annotated_image(image_bgr: np.ndarray, regions: List[RegionObservation], dest_path: str) -> None:
    annotated = image_bgr.copy()
    h, w = annotated.shape[:2]

    for r in regions:
        center = (int(r.x * w), int(r.y * h))
        color = CATEGORY_COLOR_BGR.get(r.category, (255, 140, 94))
        cv2.circle(annotated, center, 8, color, -1, lineType=cv2.LINE_AA)
        cv2.circle(annotated, center, 8, (255, 255, 255), 2, lineType=cv2.LINE_AA)

    cv2.imwrite(dest_path, annotated)


def _draw_wrapped(c: canvas.Canvas, text: str, x: float, y: float, max_width: float, font="Helvetica", size=9) -> float:
    c.setFont(font, size)
    words = text.split()
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, font, size) > max_width and line:
            c.drawString(x, y, line)
            y -= size + 3
            line = word
        else:
            line = trial
    if line:
        c.drawString(x, y, line)
        y -= size + 3
    return y


def build_pdf_report(
    dest_path: str,
    analysis: SkinAnalysis,
    regions: List[RegionObservation],
    recommendations: List[str],
    annotated_image_path: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> None:
    c = canvas.Canvas(dest_path, pagesize=A4)
    page_w, page_h = A4
    margin = 18 * mm
    y = page_h - margin

    c.setFillColorRGB(0.04, 0.07, 0.14)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y, "Foxtale — Skin Analysis Report")
    y -= 10 * mm

    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.35, 0.4, 0.5)
    c.drawString(margin, y, f"Generated: {timestamp or 'N/A'}")
    y -= 8 * mm

    if annotated_image_path:
        img_size = 60 * mm
        c.drawImage(annotated_image_path, margin, y - img_size, width=img_size, height=img_size,
                    preserveAspectRatio=True, anchor='n')
        card_x = margin + img_size + 8 * mm
    else:
        card_x = margin

    card_y = y
    c.setFillColorRGB(0.04, 0.07, 0.14)
    c.setFont("Helvetica-Bold", 12)
    for label, cat in [
        ("Acne-like Spots", analysis.acne_like_spots),
        ("Visible Redness", analysis.redness),
        ("Skin Texture", analysis.texture),
        ("Dryness Indicators", analysis.dryness_indicators),
    ]:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(card_x, card_y, f"{label}:")
        c.setFont("Helvetica", 11)
        extra = f" ({cat.count} area(s))" if cat.count is not None else ""
        c.drawString(card_x + 55 * mm, card_y, f"{cat.level.title()}{extra} — {int(cat.confidence * 100)}% confidence")
        card_y -= 7 * mm

    y = min(y - 65 * mm, card_y - 4 * mm)

    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, y, "Region Breakdown")
    y -= 7 * mm
    c.setFont("Helvetica", 9.5)
    if not regions:
        y = _draw_wrapped(c, "No notable visible observations in any region.", margin, y, page_w - 2 * margin)
    for r in regions:
        y = _draw_wrapped(c, f"[{r.region}] {r.category}: {r.observation}", margin, y, page_w - 2 * margin)
        if y < 40 * mm:
            c.showPage()
            y = page_h - margin

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, y, "Recommendations")
    y -= 7 * mm
    c.setFont("Helvetica", 9.5)
    for tip in recommendations:
        y = _draw_wrapped(c, f"• {tip}", margin, y, page_w - 2 * margin)
        if y < 40 * mm:
            c.showPage()
            y = page_h - margin

    y -= 6 * mm
    c.setFillColor(colors.HexColor("#FF8A3D"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "AI Disclaimer:")
    y -= 5 * mm
    c.setFillColorRGB(0.2, 0.22, 0.3)
    c.setFont("Helvetica", 8.5)
    _draw_wrapped(c, DISCLAIMER, margin, y, page_w - 2 * margin, size=8.5)

    c.save()
