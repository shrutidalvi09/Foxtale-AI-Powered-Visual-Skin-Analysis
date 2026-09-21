"""Light/dark stylesheets matching the real Foxtale brand: white/navy base
with the brand's own orange (#e54a00, sampled directly from the logo file)
as the primary accent, and a soft blue as a secondary/informational accent.
Every interactive control (buttons, combo boxes, checkboxes, sliders, tabs,
scrollbars, tables) gets a custom look here so nothing falls back to the raw
OS widget style.
"""

NAVY = "#0b1224"
FOX = "#e54a00"
FOX_HOVER = "#ee5a10"
ACCENT = "#3b8dff"

# Text-safe variants: the vivid brand colors above read poorly as TEXT
# against white (verified by contrast calculation). These deeper shades of
# the same hues are for text/foreground use only; FOX/ACCENT stay for
# fills, borders and other non-text UI elements where the AA bar is a
# looser 3:1.
ACCENT_TEXT = "#2a6fe0"
FOX_TEXT = "#9c3808"

LIGHT_QSS = f"""
QWidget {{
    background-color: #ffffff;
    color: {NAVY};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow {{ background-color: #ffffff; }}
QToolTip {{
    background-color: white;
    color: {NAVY};
    border: 1px solid #d9deeb;
    border-radius: 6px;
    padding: 6px 10px;
}}

#Sidebar {{
    background-color: #f7f8fb;
    border-right: 1px solid #e7e9f0;
}}
#SidebarButton {{
    text-align: left;
    padding: 11px 16px 11px 18px;
    border-radius: 10px;
    border: none;
    border-left: 4px solid transparent;
    background: transparent;
    color: #33415c;
    font-weight: 600;
    font-size: 13.5px;
}}
#SidebarButton:hover {{ background-color: #eef1f8; }}
#SidebarButton[active="true"] {{
    background-color: #fff3ea;
    color: {NAVY};
    border-left: 4px solid {FOX};
}}
#Brand {{ font-size: 17px; font-weight: 800; }}
#BrandTag {{ color: #6b7280; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}

QPushButton#Primary {{
    background-color: {FOX};
    color: {NAVY};
    border: none;
    border-radius: 18px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#Primary:hover {{ background-color: {FOX_HOVER}; }}
QPushButton#Primary:pressed {{ background-color: {FOX}; padding-top: 11px; padding-bottom: 9px; }}
QPushButton#Primary:disabled {{ background-color: #f3c3a1; color: #8a5a3a; }}

QPushButton#Secondary {{
    background-color: white;
    color: {NAVY};
    border: 1px solid #d9deeb;
    border-radius: 18px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#Secondary:hover {{ border-color: {ACCENT}; color: {ACCENT_TEXT}; background-color: #f5f9ff; }}
QPushButton#Secondary:pressed {{ background-color: #eaf1ff; }}

QFrame#Card {{
    background-color: white;
    border: 1px solid #eceff5;
    border-radius: 14px;
}}
QFrame#HeroPanel {{
    border-radius: 18px;
    background-color: #f7f9fc;
    border: 1px solid #e7e9f0;
}}
QFrame#Disclaimer {{
    background-color: #fff3ea;
    border: 1px solid #ffd9b8;
    border-radius: 14px;
}}
QFrame#Divider {{ background-color: #eceff5; max-height: 1px; min-height: 1px; border: none; }}

QLabel#Heading {{ font-size: 25px; font-weight: 800; }}
QLabel#SubHeading {{ color: #5a6478; }}
QLabel#Muted {{ color: #6b7280; font-size: 11px; }}
QLabel#Badge {{
    color: {FOX_TEXT};
    background-color: #fff0e3;
    border: 1px solid #ffd9b8;
    border-radius: 12px;
    padding: 4px 12px;
    font-weight: 800;
    font-size: 11px;
}}

QProgressBar {{
    border: none;
    border-radius: 6px;
    background-color: #eef1f8;
    height: 10px;
    text-align: center;
}}
QProgressBar::chunk {{
    border-radius: 6px;
    background-color: {FOX};
}}

QComboBox {{
    background-color: white;
    border: 1px solid #d9deeb;
    border-radius: 10px;
    padding: 6px 10px;
    min-height: 22px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: white;
    border: 1px solid #e7e9f0;
    border-radius: 8px;
    selection-background-color: #fff0e3;
    selection-color: {NAVY};
    padding: 4px;
    outline: none;
}}

QCheckBox {{ spacing: 10px; font-weight: 600; padding: 2px 0; }}
QCheckBox::indicator {{
    width: 19px; height: 19px;
    border-radius: 6px;
    border: 2px solid #d9deeb;
    background: white;
}}
QCheckBox::indicator:hover {{ border-color: {FOX}; }}
QCheckBox::indicator:checked {{
    border-color: {FOX};
    background-color: {FOX};
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: #eef1f8;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {FOX};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: white;
    border: 3px solid {FOX};
}}
QSlider::handle:horizontal:hover {{ border-color: {FOX_TEXT}; }}

QTabWidget::pane {{
    border: 1px solid #eceff5;
    border-radius: 12px;
    top: -1px;
    padding: 6px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 700;
    color: #6b7280;
}}
QTabBar::tab:selected {{
    background: #f7f8fb;
    color: {NAVY};
    border-bottom: 3px solid {FOX};
}}
QTabBar::tab:hover:!selected {{ color: {ACCENT_TEXT}; }}

QTableWidget {{
    background: white;
    border: 1px solid #eceff5;
    border-radius: 10px;
    gridline-color: #f0f2f7;
    selection-background-color: #fff0e3;
    selection-color: {NAVY};
}}
QTableWidget::item {{ padding: 6px; }}
QHeaderView::section {{
    background-color: #f7f8fb;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #eceff5;
    font-weight: 700;
    color: #5a6478;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #d9deeb;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #b8c0d6; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #d9deeb;
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

QMessageBox {{ background-color: white; }}
"""

DARK_QSS = f"""
QWidget {{
    background-color: #0f1526;
    color: #e7ecf7;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow {{ background-color: #0f1526; }}
QToolTip {{
    background-color: #1a2340;
    color: white;
    border: 1px solid #2a3a63;
    border-radius: 6px;
    padding: 6px 10px;
}}

#Sidebar {{
    background-color: #0b1020;
    border-right: 1px solid #1d2740;
}}
#SidebarButton {{
    text-align: left;
    padding: 11px 16px 11px 18px;
    border-radius: 10px;
    border: none;
    border-left: 4px solid transparent;
    background: transparent;
    color: #b7c1da;
    font-weight: 600;
    font-size: 13.5px;
}}
#SidebarButton:hover {{ background-color: #17203a; }}
#SidebarButton[active="true"] {{
    background-color: #1a2340;
    color: white;
    border-left: 4px solid {FOX};
}}
#Brand {{ font-size: 17px; font-weight: 800; color: white; }}
#BrandTag {{ color: #7a86a8; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}

QPushButton#Primary {{
    background-color: {FOX};
    color: white;
    border: none;
    border-radius: 18px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#Primary:hover {{ background-color: {FOX_HOVER}; }}
QPushButton#Primary:pressed {{ background-color: {FOX}; padding-top: 11px; padding-bottom: 9px; }}
QPushButton#Primary:disabled {{ background-color: #5a4433; }}

QPushButton#Secondary {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 18px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#Secondary:hover {{ border-color: {ACCENT}; color: {ACCENT}; background-color: #16203c; }}
QPushButton#Secondary:pressed {{ background-color: #0f1730; }}

QFrame#Card {{
    background-color: #131b30;
    border: 1px solid #21294a;
    border-radius: 14px;
}}
QFrame#HeroPanel {{
    border-radius: 18px;
    background-color: #131b30;
    border: 1px solid #21294a;
}}
QFrame#Disclaimer {{
    background-color: #2a1d10;
    border: 1px solid #55381a;
    border-radius: 14px;
}}
QFrame#Divider {{ background-color: #21294a; max-height: 1px; min-height: 1px; border: none; }}

QLabel#Heading {{ font-size: 25px; font-weight: 800; color: white; }}
QLabel#SubHeading {{ color: #9aa6c3; }}
QLabel#Muted {{ color: #7a86a8; font-size: 11px; }}
QLabel#Badge {{
    color: {FOX_HOVER};
    background-color: #2a1d10;
    border: 1px solid #55381a;
    border-radius: 12px;
    padding: 4px 12px;
    font-weight: 800;
    font-size: 11px;
}}

QProgressBar {{
    border: none;
    border-radius: 6px;
    background-color: #1a2340;
    height: 10px;
    text-align: center;
}}
QProgressBar::chunk {{
    border-radius: 6px;
    background-color: {FOX};
}}

QComboBox {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 10px;
    padding: 6px 10px;
    min-height: 22px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 8px;
    selection-background-color: #1c2b52;
    selection-color: white;
    padding: 4px;
    outline: none;
}}

QCheckBox {{ spacing: 10px; font-weight: 600; padding: 2px 0; }}
QCheckBox::indicator {{
    width: 19px; height: 19px;
    border-radius: 6px;
    border: 2px solid #263457;
    background: #131b30;
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    border-color: {FOX};
    background-color: {FOX};
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: #1a2340;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {FOX};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #0f1526;
    border: 3px solid {FOX};
}}
QSlider::handle:horizontal:hover {{ border-color: white; }}

QTabWidget::pane {{
    border: 1px solid #21294a;
    border-radius: 12px;
    top: -1px;
    padding: 6px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 700;
    color: #7a86a8;
}}
QTabBar::tab:selected {{
    background: #131b30;
    color: white;
    border-bottom: 3px solid {FOX};
}}
QTabBar::tab:hover:!selected {{ color: {ACCENT}; }}

QTableWidget {{
    background: #131b30;
    border: 1px solid #21294a;
    border-radius: 10px;
    gridline-color: #1d2740;
    color: #e7ecf7;
    selection-background-color: #1c2b52;
    selection-color: white;
}}
QTableWidget::item {{ padding: 6px; }}
QHeaderView::section {{
    background-color: #0b1020;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #21294a;
    font-weight: 700;
    color: #b7c1da;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #263457;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #34456f; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #263457;
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

QMessageBox {{ background-color: #0f1526; }}
"""


def stylesheet_for(theme: str) -> str:
    return DARK_QSS if theme == "dark" else LIGHT_QSS


_current_theme = "light"


def set_current_theme(theme: str) -> None:
    global _current_theme
    _current_theme = "dark" if theme == "dark" else "light"


def get_current_theme() -> str:
    return _current_theme


# Base hues used for small decorative markers (region dots, chart lines,
# left-border accents) where WCAG's looser 3:1 non-text bar applies and the
# color is always paired with a text label, never the sole signal.
LEVEL_COLORS = {
    "minimal": "#10b981",
    "mild": "#f59e0b",
    "moderate": "#f97316",
    "noticeable": "#f43f5e",
}

CATEGORY_QCOLOR = {
    "Acne-like spots": "#f43f5e",
    "Redness": "#f97316",
    "Texture": "#f59e0b",
    "Dryness indicators": "#3b82f6",
}

# Severity "pill" (bg, text) pairs, tuned per theme so the text itself always
# clears WCAG AA (4.5:1). A light 13%-alpha tint of LEVEL_COLORS over a dark
# card already passes AA on its own, but the same tint over a WHITE card does
# not (as low as 1.94:1) -- so light mode gets dedicated solid pastel/deep
# pairs instead of an alpha blend of the vivid base color.
LEVEL_PILL_LIGHT = {
    "minimal": ("#d1fae5", "#047857"),
    "mild": ("#fef3c7", "#92400e"),
    "moderate": ("#ffedd5", "#c2410c"),
    "noticeable": ("#ffe4e6", "#be123c"),
}

LEVEL_PILL_DARK = {
    "minimal": ("#064e3b", "#6ee7b7"),
    "mild": ("#451a03", "#fcd34d"),
    "moderate": ("#431407", "#fdba74"),
    "noticeable": ("#4c0519", "#fda4af"),
}


def level_pill_colors(level: str, theme: str | None = None) -> tuple[str, str]:
    """Return (background, text) for a severity pill, guaranteed >=4.5:1 contrast."""
    table = LEVEL_PILL_DARK if (theme or _current_theme) == "dark" else LEVEL_PILL_LIGHT
    return table.get(level, table["mild"])


# Monochrome icon colors by semantic role. Icons are baked bitmaps (qtawesome
# renders a single flat color per icon, deliberately -- no multicolor emoji),
# so they're colored once at construction time using whichever theme is
# active then; they don't live-repaint on a later theme toggle.
_ICON_COLORS = {
    "dark": {
        "primary": FOX_HOVER, "accent": ACCENT, "warning": FOX_HOVER,
        "success": "#6ee7b7", "on_primary": "white",
    },
    "light": {
        "primary": FOX_TEXT, "accent": ACCENT_TEXT, "warning": FOX_TEXT,
        "success": "#047857", "on_primary": NAVY,
    },
}


def icon_color(kind: str = "primary", theme: str | None = None) -> str:
    table = _ICON_COLORS["dark" if (theme or _current_theme) == "dark" else "light"]
    return table.get(kind, table["primary"])
