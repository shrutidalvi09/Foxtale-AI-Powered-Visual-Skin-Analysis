"""Multi-page face skin analysis report (A4 PDF) for a single scan.

Layout: summary page (photo + overall score + category snapshot), region
breakdown, key observations, changes since the last scan, recommendations,
scan quality, and a methodology / limitations page. Built with reportlab's
canvas so it has no extra dependencies and stays fully offline.
"""

from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from engine.schemas import DISCLAIMER, RegionObservation, SkinAnalysis
from engine.skin_analysis import score_label
from gui.core import report_content as rc

ORANGE = colors.HexColor("#e54a00")
INK = colors.HexColor("#1b2233")
MUTED = colors.HexColor("#6b7385")
LINE = colors.HexColor("#e3e6ee")
SOFT = colors.HexColor("#f6f7fb")
LEVEL_COLORS = {
    "minimal": colors.HexColor("#12a06a"),
    "mild": colors.HexColor("#d99000"),
    "moderate": colors.HexColor("#e54a00"),
    "noticeable": colors.HexColor("#c81e1e"),
}
PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _score_color(score: int):
    if score >= 85:
        return LEVEL_COLORS["minimal"]
    if score >= 70:
        return colors.HexColor("#7aa500")
    if score >= 55:
        return LEVEL_COLORS["mild"]
    return LEVEL_COLORS["noticeable"]


class _Report:
    def __init__(self, dest_path: str, timestamp: Optional[str]):
        self.c = canvas.Canvas(dest_path, pagesize=A4)
        self.c.setTitle("Foxtale Face Skin Analysis Report")
        self.c.setAuthor("Foxtale Desktop")
        self.timestamp = timestamp or "N/A"
        self.page = 0
        self.y = 0.0
        self._new_page()

    # ---------------------------------------------------------- page chrome
    def _new_page(self) -> None:
        if self.page:
            self._footer()
            self.c.showPage()
        self.page += 1
        c = self.c
        c.setFillColor(ORANGE)
        c.rect(0, PAGE_H - 4 * mm, PAGE_W, 4 * mm, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 17)
        c.drawString(MARGIN, PAGE_H - 16 * mm, "foxtale")
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(MARGIN + 27 * mm, PAGE_H - 16 * mm, "Face Skin Analysis Report")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 16 * mm, self.timestamp)
        c.setStrokeColor(LINE)
        c.line(MARGIN, PAGE_H - 20 * mm, PAGE_W - MARGIN, PAGE_H - 20 * mm)
        self.y = PAGE_H - 28 * mm

    def _footer(self) -> None:
        c = self.c
        c.setStrokeColor(LINE)
        c.line(MARGIN, 15 * mm, PAGE_W - MARGIN, 15 * mm)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawString(MARGIN, 10.5 * mm, "Generated locally by Foxtale Desktop. A visual observation, not a medical diagnosis.")
        c.drawRightString(PAGE_W - MARGIN, 10.5 * mm, f"Page {self.page}")

    def ensure(self, height: float) -> None:
        if self.y - height < 20 * mm:
            self._new_page()

    # -------------------------------------------------------------- content
    def heading(self, text: str) -> None:
        self.ensure(14 * mm)
        self.c.setFillColor(INK)
        self.c.setFont("Helvetica-Bold", 12.5)
        self.c.drawString(MARGIN, self.y, text)
        self.c.setFillColor(ORANGE)
        self.c.rect(MARGIN, self.y - 2.2 * mm, 10 * mm, 0.7 * mm, stroke=0, fill=1)
        self.y -= 8 * mm

    def paragraph(self, text: str, size: float = 9.5, color=INK, x: Optional[float] = None,
                  width: Optional[float] = None, font: str = "Helvetica", leading: Optional[float] = None) -> None:
        x = MARGIN if x is None else x
        width = CONTENT_W if width is None else width
        leading = leading or size * 1.42
        lines = simpleSplit(text, font, size, width)
        for line in lines:
            self.ensure(leading + 2)
            self.c.setFillColor(color)
            self.c.setFont(font, size)
            self.c.drawString(x, self.y, line)
            self.y -= leading

    def bullet(self, text: str, size: float = 9.5) -> None:
        lines = simpleSplit(text, "Helvetica", size, CONTENT_W - 6 * mm)
        leading = size * 1.42
        for i, line in enumerate(lines):
            self.ensure(leading + 2)
            if i == 0:
                self.c.setFillColor(ORANGE)
                self.c.circle(MARGIN + 1.4 * mm, self.y + size * 0.32, 0.9 * mm, stroke=0, fill=1)
            self.c.setFillColor(INK)
            self.c.setFont("Helvetica", size)
            self.c.drawString(MARGIN + 6 * mm, self.y, line)
            self.y -= leading
        self.y -= 1.2 * mm

    def pill(self, x: float, y: float, level: str) -> None:
        w, h = 25 * mm, 5.6 * mm
        self.c.setFillColor(LEVEL_COLORS[level])
        self.c.roundRect(x, y - 1.4 * mm, w, h, h / 2, stroke=0, fill=1)
        self.c.setFillColor(colors.white)
        self.c.setFont("Helvetica-Bold", 8.5)
        self.c.drawCentredString(x + w / 2, y + 0.55 * mm, level.title())

    def score_gauge(self, cx: float, cy: float, radius: float, score: int) -> None:
        c = self.c
        c.setLineWidth(4.2 * mm)
        c.setStrokeColor(LINE)
        c.circle(cx, cy, radius, stroke=1, fill=0)
        c.setStrokeColor(_score_color(score))
        c.setLineCap(1)
        c.arc(cx - radius, cy - radius, cx + radius, cy + radius, 90, -360 * score / 100.0)
        c.setLineCap(0)
        c.setLineWidth(1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 26)
        c.drawCentredString(cx, cy - 2.5 * mm, str(score))
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawCentredString(cx, cy - 8 * mm, "out of 100")

    def photo(self, path: str, x: float, top: float, box_w: float, box_h: float) -> None:
        img = ImageReader(path)
        iw, ih = img.getSize()
        scale = min(box_w / iw, box_h / ih)
        w, h = iw * scale, ih * scale
        self.c.setFillColor(SOFT)
        self.c.roundRect(x - 1.5 * mm, top - box_h - 1.5 * mm, box_w + 3 * mm, box_h + 3 * mm, 3 * mm, stroke=0, fill=1)
        self.c.drawImage(img, x + (box_w - w) / 2, top - box_h + (box_h - h) / 2, width=w, height=h, mask="auto")

    def finish(self) -> None:
        self._footer()
        self.c.save()


def build_face_report(
    dest_path: str,
    analysis: SkinAnalysis,
    regions: List[RegionObservation],
    recommendations: List[str],
    annotated_image_path: Optional[str] = None,
    timestamp: Optional[str] = None,
    quality=None,
    previous: Optional[SkinAnalysis] = None,
    note: str = "",
) -> None:
    r = _Report(dest_path, timestamp)
    c = r.c

    # ---- summary block: photo | score + summary
    block_top = r.y
    photo_w, photo_h = 66 * mm, 82 * mm
    text_x = MARGIN
    if annotated_image_path:
        r.photo(annotated_image_path, MARGIN + 1.5 * mm, block_top, photo_w, photo_h)
        text_x = MARGIN + photo_w + 10 * mm
    text_w = PAGE_W - MARGIN - text_x

    if analysis.overall_score is not None:
        r.score_gauge(text_x + 18 * mm, block_top - 21 * mm, 15 * mm, analysis.overall_score)
        c.setFillColor(_score_color(analysis.overall_score))
        c.setFont("Helvetica-Bold", 15)
        c.drawString(text_x + 42 * mm, block_top - 16 * mm, score_label(analysis.overall_score))
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawString(text_x + 42 * mm, block_top - 22 * mm, "Overall visible skin score")
    r.y = block_top - 42 * mm
    r.paragraph(rc.overall_summary(analysis), size=9.5, x=text_x, width=text_w)
    if annotated_image_path:
        legend_y = block_top - photo_h - 8 * mm
        r.y = min(r.y, legend_y)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, legend_y + 2 * mm, "Dots on the photo mark individual spots and areas of visible observation.")
        r.y = min(r.y, legend_y - 6 * mm)
    else:
        r.y -= 4 * mm

    # ---- category snapshot
    r.heading("Skin Snapshot")
    for row in rc.category_rows(analysis):
        r.ensure(15 * mm)
        top = r.y
        c.setFillColor(SOFT)
        c.roundRect(MARGIN, top - 11.5 * mm, CONTENT_W, 12.5 * mm, 2 * mm, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(MARGIN + 3 * mm, top - 4.3 * mm, row.label)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN + 3 * mm, top - 9 * mm, r_clip(c, row.measurement, 105 * mm, 8))
        r.pill(PAGE_W - MARGIN - 28 * mm - 24 * mm, top - 5.6 * mm, row.level)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawRightString(PAGE_W - MARGIN - 3 * mm, top - 5 * mm, f"{int(row.confidence * 100)}% confidence")
        r.y -= 14 * mm
    r.y -= 6 * mm

    # ---- region breakdown
    region_rows = rc.region_rows(analysis)
    if region_rows:
        r.heading("Region Breakdown")
        r.paragraph("Each region is scored on its own visible skin (higher is clearer). Weakest region first.",
                    size=8.5, color=MUTED)
        r.y -= 1.5 * mm
        for row in region_rows:
            r.ensure(9 * mm)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(MARGIN, r.y, row.name)
            bar_x, bar_w = MARGIN + 34 * mm, 62 * mm
            c.setFillColor(LINE)
            c.roundRect(bar_x, r.y - 0.4 * mm, bar_w, 3.2 * mm, 1.6 * mm, stroke=0, fill=1)
            c.setFillColor(_score_color(row.score))
            c.roundRect(bar_x, r.y - 0.4 * mm, max(3 * mm, bar_w * row.score / 100.0), 3.2 * mm, 1.6 * mm, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(bar_x + bar_w + 4 * mm, r.y, str(row.score))
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 9)
            c.drawString(bar_x + bar_w + 15 * mm, r.y, row.concern)
            r.y -= 7.5 * mm
        r.y -= 3 * mm

    # ---- key observations
    r.heading("Key Observations")
    if not regions:
        r.paragraph("No notable visible observations in any region.")
    else:
        by_cat: dict = {}
        for obs in regions:
            by_cat.setdefault(obs.category, []).append(obs)
        for cat, items in by_cat.items():
            r.bullet(f"{cat} - {rc.category_areas(items, cat)} ({len(items)} marker{'s' if len(items) != 1 else ''})")
        r.y -= 1 * mm
        for obs in regions[:10]:
            r.paragraph(f"{obs.region.title()}: {obs.observation} ({int(obs.confidence * 100)}% confidence)",
                        size=8.5, color=MUTED)
    r.y -= 4 * mm

    # ---- change since last scan
    changes = rc.compare_with_previous(analysis, previous)
    if changes:
        r.heading("Changes Since Your Last Scan")
        for line in changes:
            r.bullet(line)
        r.y -= 3 * mm

    # ---- recommendations
    r.heading("Recommendations")
    for tip in recommendations:
        r.bullet(tip)
    r.y -= 3 * mm

    if note:
        r.heading("Your Note")
        r.paragraph(note)
        r.y -= 3 * mm

    # ---- scan quality
    if quality is not None:
        r.heading("Photo Quality")
        r.paragraph(
            f"Overall {quality.overall}/100  |  Position {quality.position_score}  |  Lighting {quality.lighting_score}  |  "
            f"Distance {quality.distance_score}  |  Sharpness {quality.sharpness_score}  |  Angle {quality.angle_score}",
            size=9,
        )
        r.paragraph("Higher-quality photos give more reliable results.", size=8.5, color=MUTED)
        r.y -= 3 * mm

    # ---- methodology
    r.heading("How This Was Measured")
    for title, body in rc.METHOD_STEPS:
        r.bullet(f"{title}: {body}", size=9)
    r.paragraph(rc.SCORE_EXPLANATION, size=8.5, color=MUTED)
    r.y -= 3 * mm
    r.paragraph(rc.LIMITATIONS, size=8.5, color=MUTED)
    r.y -= 5 * mm

    r.ensure(26 * mm)
    c.setFillColor(SOFT)
    box_h = 20 * mm
    c.roundRect(MARGIN, r.y - box_h + 4 * mm, CONTENT_W, box_h, 2.5 * mm, stroke=0, fill=1)
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(MARGIN + 4 * mm, r.y - 1 * mm, "Important")
    r.y -= 6 * mm
    r.paragraph(DISCLAIMER, size=8.5, x=MARGIN + 4 * mm, width=CONTENT_W - 8 * mm)

    r.finish()


def r_clip(c: canvas.Canvas, text: str, max_width: float, size: float) -> str:
    if c.stringWidth(text, "Helvetica", size) <= max_width:
        return text
    while text and c.stringWidth(text + "...", "Helvetica", size) > max_width:
        text = text[:-1]
    return text + "..."
