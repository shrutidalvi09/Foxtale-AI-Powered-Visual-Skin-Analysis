"""Export a scan as an annotated PNG (markers drawn on the photo), a
one-page PDF report for a single scan, or a multi-scan progress report
covering a whole date range (summary cards + regions + recommendations +
disclaimer, or a trend chart + table across scans).
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import cv2
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from engine.schemas import DISCLAIMER, RegionObservation, SkinAnalysis

if TYPE_CHECKING:
    from gui.core.storage import ScanRecord

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


def _hex_to_bgr(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)


def build_summary_card_image(dest_path: str, record: "ScanRecord") -> None:
    """A compact, shareable summary card -- levels only, no photo -- for
    users who want to share progress without exposing their face. Distinct
    from `save_annotated_image`, which draws markers on the actual photo."""
    from gui.theme import level_pill_colors

    width, height = 900, 1120
    card = np.full((height, width, 3), 255, dtype=np.uint8)
    margin = 60

    cv2.putText(card, "foxtale", (margin, 95), cv2.FONT_HERSHEY_DUPLEX, 1.6, _hex_to_bgr("#e54a00"), 3, cv2.LINE_AA)
    cv2.putText(
        card, "AI-Powered Visual Skin Analysis", (margin, 132),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (110, 100, 90), 1, cv2.LINE_AA,
    )

    when = datetime.fromisoformat(record.timestamp).strftime("%B %d, %Y")
    cv2.putText(card, when, (margin, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (70, 60, 50), 2, cv2.LINE_AA)

    rows = [
        ("Acne-like Spots", record.analysis.acne_like_spots),
        ("Visible Redness", record.analysis.redness),
        ("Skin Texture", record.analysis.texture),
        ("Dryness Indicators", record.analysis.dryness_indicators),
    ]
    y = 260
    row_h = 190
    for label, cat in rows:
        cv2.putText(card, label, (margin, y), cv2.FONT_HERSHEY_DUPLEX, 0.8, (25, 20, 18), 2, cv2.LINE_AA)

        bg_hex, text_hex = level_pill_colors(cat.level, theme="light")
        pill_w, pill_h = 260, 64
        px0, py0 = margin, y + 22
        cv2.rectangle(card, (px0, py0), (px0 + pill_w, py0 + pill_h), _hex_to_bgr(bg_hex), -1, lineType=cv2.LINE_AA)
        cv2.putText(
            card, cat.level.title(), (px0 + 24, py0 + 43),
            cv2.FONT_HERSHEY_DUPLEX, 0.8, _hex_to_bgr(text_hex), 2, cv2.LINE_AA,
        )

        conf_text = f"{int(cat.confidence * 100)}% confidence"
        cv2.putText(
            card, conf_text, (px0 + pill_w + 28, py0 + 43),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 110, 100), 1, cv2.LINE_AA,
        )
        y += row_h

    disclaimer_lines = [
        "This is a visible-feature observation, not a medical diagnosis.",
        "Generated locally with Foxtale Desktop -- your data never leaves this device.",
    ]
    dy = height - 84
    for line in disclaimer_lines:
        cv2.putText(card, line, (margin, dy), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (140, 130, 120), 1, cv2.LINE_AA)
        dy += 26

    cv2.imwrite(dest_path, card)


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


def build_progress_report(
    dest_path: str,
    records: List["ScanRecord"],
    chart_image_path: Optional[str] = None,
    headline: Optional[str] = None,
) -> None:
    """A multi-scan progress report: date range, an optional trend-chart
    image (rendered elsewhere via TrendChart.fig.savefig), a rule-based
    headline, and a compact table of every scan in the set."""
    c = canvas.Canvas(dest_path, pagesize=A4)
    page_w, page_h = A4
    margin = 18 * mm
    y = page_h - margin

    ordered = sorted(records, key=lambda r: r.timestamp)

    c.setFillColorRGB(0.04, 0.07, 0.14)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y, "Foxtale — Progress Report")
    y -= 9 * mm

    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.35, 0.4, 0.5)
    if ordered:
        start = datetime.fromisoformat(ordered[0].timestamp).strftime("%b %d, %Y")
        end = datetime.fromisoformat(ordered[-1].timestamp).strftime("%b %d, %Y")
        c.drawString(margin, y, f"{len(ordered)} scan(s) from {start} to {end}")
    y -= 8 * mm

    if headline:
        c.setFillColorRGB(0.04, 0.07, 0.14)
        c.setFont("Helvetica-Oblique", 10.5)
        y = _draw_wrapped(c, headline, margin, y, page_w - 2 * margin, font="Helvetica-Oblique", size=10.5)
        y -= 2 * mm

    if chart_image_path:
        chart_w = page_w - 2 * margin
        chart_h = chart_w * 0.45
        c.drawImage(chart_image_path, margin, y - chart_h, width=chart_w, height=chart_h, preserveAspectRatio=True)
        y -= chart_h + 8 * mm

    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0.04, 0.07, 0.14)
    headers = ["Date", "Spots", "Redness", "Texture", "Dryness"]
    col_x = [margin, margin + 45 * mm, margin + 80 * mm, margin + 115 * mm, margin + 150 * mm]
    for x, h in zip(col_x, headers):
        c.drawString(x, y, h)
    y -= 6 * mm
    c.line(margin, y + 2 * mm, page_w - margin, y + 2 * mm)

    c.setFont("Helvetica", 9)
    for r in reversed(ordered):  # newest first in the table
        if y < 30 * mm:
            c.showPage()
            y = page_h - margin
        a = r.analysis
        values = [
            datetime.fromisoformat(r.timestamp).strftime("%Y-%m-%d %H:%M"),
            a.acne_like_spots.level.title(),
            a.redness.level.title(),
            a.texture.level.title(),
            a.dryness_indicators.level.title(),
        ]
        for x, v in zip(col_x, values):
            c.drawString(x, y, v)
        y -= 6 * mm

    y -= 6 * mm
    if y < 30 * mm:
        c.showPage()
        y = page_h - margin
    c.setFillColor(colors.HexColor("#FF8A3D"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "AI Disclaimer:")
    y -= 5 * mm
    c.setFillColorRGB(0.2, 0.22, 0.3)
    c.setFont("Helvetica", 8.5)
    _draw_wrapped(c, DISCLAIMER, margin, y, page_w - 2 * margin, size=8.5)

    c.save()
