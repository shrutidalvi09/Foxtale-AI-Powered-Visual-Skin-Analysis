"""Light/dark stylesheets matching the real Foxtale brand: white/navy base
with the brand's own orange (#e54a00, sampled directly from the logo file)
as the primary accent, and a soft blue as a secondary/informational accent.
Every interactive control (buttons, combo boxes, checkboxes, sliders, tabs,
scrollbars, tables) gets a custom look here so nothing falls back to the raw
OS widget style.
"""

from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
CHEVRON_LIGHT = (_ASSETS_DIR / "chevron_down_light.png").as_posix()
CHEVRON_DARK = (_ASSETS_DIR / "chevron_down_dark.png").as_posix()

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

# Filled orange buttons carry white text: a slightly deeper shade of the brand
# orange clears 4.5:1 against white (the exact brand #e54a00 is only 3.95:1).
FOX_BUTTON = "#d43f00"
FOX_BUTTON_HOVER = "#bf3800"
ORANGE_TEXT = "#c2410c"

LIGHT_QSS = f"""
QWidget {{
    background-color: #ffffff;
    color: {NAVY};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow {{ background-color: #ffffff; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
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
    padding: 11px 16px;
    margin: 0 10px;
    border-radius: 12px;
    border: none;
    background: transparent;
    color: #33415c;
    font-weight: 600;
    font-size: 13.5px;
}}
#SidebarButton:hover {{ background-color: #eef1f8; }}
#SidebarButton[active="true"] {{
    background-color: #fff3ea;
    color: {ORANGE_TEXT};
}}
QFrame#ProfileCard {{
    background-color: #fff3ea;
    border: 1px solid #ffe1c2;
    border-radius: 14px;
    margin: 0 10px;
}}
#Brand {{ font-size: 17px; font-weight: 800; }}
#BrandTag {{ color: #6b7280; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}

QPushButton#Primary, QPushButton#Cta {{
    background-color: {FOX_BUTTON};
    color: white;
    border: none;
    border-radius: 20px;
    padding: 10px 22px;
    min-height: 20px;
    font-weight: 700;
}}
QPushButton#Cta {{
    border-radius: 24px;
    padding: 12px 28px;
    min-height: 24px;
    font-size: 14px;
    font-weight: 800;
}}
QPushButton#Primary:hover, QPushButton#Cta:hover {{ background-color: {FOX_BUTTON_HOVER}; }}
QPushButton#Primary:pressed, QPushButton#Cta:pressed {{ background-color: {FOX_BUTTON}; padding-top: 13px; padding-bottom: 11px; }}
QPushButton#Primary:disabled, QPushButton#Cta:disabled {{ background-color: #f3c3a1; color: white; }}
QPushButton#SoftButton {{
    background-color: #fff1e7;
    color: {ORANGE_TEXT};
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 800;
}}
QPushButton#SoftButton:hover {{ background-color: #ffe4d1; }}
QPushButton#DangerButton {{
    background-color: white;
    color: #be123c;
    border: 1px solid #f5c2c7;
    border-radius: 20px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#DangerButton:hover {{ background-color: #fff1f2; border-color: #f0a3ad; }}
QPushButton#IconButton {{ background: transparent; border: none; border-radius: 10px; padding: 8px; }}
QPushButton#IconButton:hover {{ background-color: #f3f4f8; }}
QPushButton#SortHeader {{
    background: transparent;
    border: none;
    text-align: left;
    padding: 6px 4px;
    font-weight: 700;
    color: #5a6478;
}}
QPushButton#SortHeader:hover {{ color: {ORANGE_TEXT}; }}
QPushButton#PageButton {{
    background-color: white;
    color: {NAVY};
    border: 1px solid #e2e5ee;
    border-radius: 10px;
    font-weight: 700;
}}
QPushButton#PageButton:hover:enabled {{ border-color: #ffc9a3; }}
QPushButton#PageButton:checked {{ border: 1.5px solid {FOX}; color: {ORANGE_TEXT}; background-color: #fff8f3; }}
QPushButton#PageButton:disabled {{ background-color: #f7f8fb; border-color: #eef0f5; }}
QTabWidget#PageTabs::pane {{ border: none; padding: 0; top: 2px; }}
QTabWidget#PageTabs QTabBar::tab {{
    background: transparent;
    color: #6b7280;
    padding: 12px 20px;
    margin-right: 6px;
    border-radius: 0;
    border-bottom: 3px solid transparent;
    font-weight: 700;
}}
QTabWidget#PageTabs QTabBar::tab:selected {{ background: transparent; color: {ORANGE_TEXT}; border-bottom: 3px solid {FOX}; }}
QTabWidget#PageTabs QTabBar::tab:hover:!selected {{ color: {NAVY}; }}
QPushButton#ToggleChip {{
    background-color: white;
    color: {ORANGE_TEXT};
    border: 1px solid #eceff5;
    border-radius: 21px;
    padding: 10px 20px;
    min-height: 22px;
    font-weight: 800;
}}
QPushButton#ToggleChip:hover {{ border-color: #ffc9a3; }}
QPushButton#ToggleChip:checked {{ background-color: #fff1e7; border-color: {FOX}; }}
QPushButton#RoutineChip {{
    background-color: white;
    color: {NAVY};
    border: 1px solid #e7e9f0;
    border-radius: 20px;
    padding: 9px 16px;
    min-height: 22px;
    font-weight: 600;
}}
QPushButton#RoutineChip:hover {{ border-color: #ffc9a3; }}
QPushButton#RoutineChip:checked {{ background-color: #fff1e7; border-color: {FOX}; color: {ORANGE_TEXT}; font-weight: 800; }}
QPushButton#RoutineChip:disabled {{ background-color: #f7f8fb; color: #9aa3b8; border-color: #eef0f5; }}
QPushButton#PillChip {{
    background-color: white;
    color: {NAVY};
    border: 1px solid #e7e9f0;
    border-radius: 16px;
    padding: 3px 14px;
    min-height: 26px;
    max-height: 26px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#PillChip:hover {{ border-color: #ffc9a3; }}
QPushButton#PillChip:checked {{ background-color: #fff1e7; border-color: {FOX}; color: {ORANGE_TEXT}; font-weight: 800; }}
QPushButton#Secondary:disabled {{ color: #a3abbd; background-color: #f7f8fb; border-color: #eceff5; }}
QLineEdit {{
    background-color: white;
    border: 1px solid #e2e5ee;
    border-radius: 14px;
    padding: 10px 14px;
    min-height: 22px;
    selection-background-color: #ffd9b8;
}}
QLineEdit:focus {{ border-color: {FOX}; }}
QLineEdit:disabled {{ background-color: #f7f8fb; color: #9aa3b8; }}
QFrame#TipPill {{
    background-color: #fff1e7;
    border: 1px solid #ffe1c2;
    border-radius: 20px;
}}
QFrame#TrustChips {{
    background-color: white;
    border: 1px solid #f3e4d8;
    border-radius: 14px;
}}

QPushButton#Secondary {{
    background-color: white;
    color: {NAVY};
    border: 1px solid #d9deeb;
    border-radius: 20px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#Secondary:hover {{ border-color: {ACCENT}; color: {ACCENT_TEXT}; background-color: #f5f9ff; }}
QPushButton#Secondary:pressed {{ background-color: #eaf1ff; }}

QFrame#Card {{
    background-color: white;
    border: 1px solid #eceff5;
    border-radius: 16px;
}}
QFrame#HeroPanel {{
    border-radius: 20px;
    background-color: #f7f9fc;
    border: 1px solid #e7e9f0;
}}
QFrame#HeroGradient {{
    border-radius: 22px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff6ef, stop:1 #ffe6d4);
    border: 1px solid #ffe1c2;
}}
QPushButton#LinkButton {{
    background: transparent;
    border: none;
    color: {ORANGE_TEXT};
    font-weight: 700;
    font-size: 11.5px;
    padding: 2px 0;
    text-align: left;
}}
QPushButton#LinkButton:hover {{ color: {FOX_BUTTON_HOVER}; }}
QFrame#Disclaimer {{
    background-color: #fff3ea;
    border: 1px solid #ffd9b8;
    border-radius: 16px;
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
QLabel#CardTitle {{ font-size: 14px; font-weight: 800; }}
QLabel#ErrorBanner {{
    background-color: #fdecec;
    color: #b3261e;
    border: 1px solid #f5c2c0;
    border-radius: 12px;
    padding: 10px;
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
QProgressBar#JourneyBar {{ background-color: #fde4d3; border-radius: 4px; }}
QProgressBar#JourneyBar::chunk {{ border-radius: 4px; background-color: {FOX}; }}

QComboBox {{
    background-color: white;
    border: 1px solid #d9deeb;
    border-radius: 12px;
    padding: 6px 10px;
    min-height: 22px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 32px; }}
QComboBox::down-arrow {{ image: url({CHEVRON_LIGHT}); width: 12px; height: 12px; }}
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

QRadioButton {{ spacing: 10px; font-weight: 600; padding: 2px 0; }}
QRadioButton::indicator {{
    width: 19px; height: 19px;
    border-radius: 12px;
    border: 2px solid #d9deeb;
    background: white;
}}
QRadioButton::indicator:hover {{ border-color: {FOX}; }}
QRadioButton::indicator:checked {{
    border: 2px solid {FOX};
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
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
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
    border-radius: 12px;
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

QListWidget {{
    background: white;
    border: 1px solid #eceff5;
    border-radius: 12px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:selected {{ background-color: #fff3ea; color: {NAVY}; }}

QMessageBox {{ background-color: white; }}
QDialog {{ background-color: white; }}

QMenuBar {{
    background-color: #ffffff;
    border-bottom: 1px solid #eceff5;
    padding: 2px 4px;
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 6px;
    background: transparent;
    color: {NAVY};
}}
QMenuBar::item:selected {{ background-color: #fff3ea; color: {FOX_TEXT}; }}
QMenu {{
    background-color: white;
    border: 1px solid #e7e9f0;
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px 7px 14px;
    border-radius: 6px;
    color: {NAVY};
}}
QMenu::item:selected {{ background-color: #fff3ea; color: {FOX_TEXT}; }}
QMenu::separator {{ height: 1px; background: #eceff5; margin: 6px 8px; }}
"""

DARK_QSS = f"""
QWidget {{
    background-color: #0f1526;
    color: #e7ecf7;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow {{ background-color: #0f1526; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
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
    padding: 11px 16px;
    margin: 0 10px;
    border-radius: 12px;
    border: none;
    background: transparent;
    color: #b7c1da;
    font-weight: 600;
    font-size: 13.5px;
}}
#SidebarButton:hover {{ background-color: #17203a; }}
#SidebarButton[active="true"] {{
    background-color: #1a2340;
    color: {FOX_HOVER};
}}
QFrame#ProfileCard {{
    background-color: #1a2340;
    border: 1px solid #2a3a63;
    border-radius: 14px;
    margin: 0 10px;
}}
#Brand {{ font-size: 17px; font-weight: 800; color: white; }}
#BrandTag {{ color: #7a86a8; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}

QPushButton#Primary, QPushButton#Cta {{
    background-color: {FOX_BUTTON};
    color: white;
    border: none;
    border-radius: 20px;
    padding: 10px 22px;
    min-height: 20px;
    font-weight: 700;
}}
QPushButton#Cta {{
    border-radius: 24px;
    padding: 12px 28px;
    min-height: 24px;
    font-size: 14px;
    font-weight: 800;
}}
QPushButton#Primary:hover, QPushButton#Cta:hover {{ background-color: {FOX_BUTTON_HOVER}; }}
QPushButton#Primary:pressed, QPushButton#Cta:pressed {{ background-color: {FOX_BUTTON}; padding-top: 13px; padding-bottom: 11px; }}
QPushButton#Primary:disabled, QPushButton#Cta:disabled {{ background-color: #5a4433; color: #d9c7b8; }}
QPushButton#SoftButton {{
    background-color: #2a1d10;
    color: {FOX_HOVER};
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 800;
}}
QPushButton#SoftButton:hover {{ background-color: #35240f; }}
QPushButton#DangerButton {{
    background-color: #131b30;
    color: #fda4af;
    border: 1px solid #5b2331;
    border-radius: 20px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#DangerButton:hover {{ background-color: #2a1220; border-color: #8a3348; }}
QPushButton#IconButton {{ background: transparent; border: none; border-radius: 10px; padding: 8px; }}
QPushButton#IconButton:hover {{ background-color: #1a2340; }}
QPushButton#SortHeader {{
    background: transparent;
    border: none;
    text-align: left;
    padding: 6px 4px;
    font-weight: 700;
    color: #9aa6c3;
}}
QPushButton#SortHeader:hover {{ color: {FOX_HOVER}; }}
QPushButton#PageButton {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 10px;
    font-weight: 700;
}}
QPushButton#PageButton:hover:enabled {{ border-color: {FOX}; }}
QPushButton#PageButton:checked {{ border: 1.5px solid {FOX}; color: {FOX_HOVER}; background-color: #2a1d10; }}
QPushButton#PageButton:disabled {{ background-color: #0f1526; border-color: #1d2740; }}
QTabWidget#PageTabs::pane {{ border: none; padding: 0; top: 2px; }}
QTabWidget#PageTabs QTabBar::tab {{
    background: transparent;
    color: #7a86a8;
    padding: 12px 20px;
    margin-right: 6px;
    border-radius: 0;
    border-bottom: 3px solid transparent;
    font-weight: 700;
}}
QTabWidget#PageTabs QTabBar::tab:selected {{ background: transparent; color: {FOX_HOVER}; border-bottom: 3px solid {FOX}; }}
QTabWidget#PageTabs QTabBar::tab:hover:!selected {{ color: white; }}
QPushButton#ToggleChip {{
    background-color: #131b30;
    color: {FOX_HOVER};
    border: 1px solid #263457;
    border-radius: 21px;
    padding: 10px 20px;
    min-height: 22px;
    font-weight: 800;
}}
QPushButton#ToggleChip:hover {{ border-color: {FOX}; }}
QPushButton#ToggleChip:checked {{ background-color: #2a1d10; border-color: {FOX}; }}
QPushButton#RoutineChip {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 20px;
    padding: 9px 16px;
    min-height: 22px;
    font-weight: 600;
}}
QPushButton#RoutineChip:hover {{ border-color: {FOX}; }}
QPushButton#RoutineChip:checked {{ background-color: #2a1d10; border-color: {FOX}; color: {FOX_HOVER}; font-weight: 800; }}
QPushButton#RoutineChip:disabled {{ background-color: #0f1526; color: #56617f; border-color: #1d2740; }}
QPushButton#PillChip {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 16px;
    padding: 3px 14px;
    min-height: 26px;
    max-height: 26px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#PillChip:hover {{ border-color: {FOX}; }}
QPushButton#PillChip:checked {{ background-color: #2a1d10; border-color: {FOX}; color: {FOX_HOVER}; font-weight: 800; }}
QPushButton#Secondary:disabled {{ color: #56617f; background-color: #0f1526; border-color: #1d2740; }}
QLineEdit {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 14px;
    padding: 10px 14px;
    min-height: 22px;
    selection-background-color: #55381a;
}}
QLineEdit:focus {{ border-color: {FOX}; }}
QLineEdit:disabled {{ background-color: #0f1526; color: #56617f; }}
QFrame#TipPill {{
    background-color: #2a1d10;
    border: 1px solid #55381a;
    border-radius: 20px;
}}
QFrame#TrustChips {{
    background-color: #131b30;
    border: 1px solid #21294a;
    border-radius: 14px;
}}

QPushButton#Secondary {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 20px;
    padding: 10px 22px;
    font-weight: 700;
}}
QPushButton#Secondary:hover {{ border-color: {ACCENT}; color: {ACCENT}; background-color: #16203c; }}
QPushButton#Secondary:pressed {{ background-color: #0f1730; }}

QFrame#Card {{
    background-color: #131b30;
    border: 1px solid #21294a;
    border-radius: 16px;
}}
QFrame#HeroPanel {{
    border-radius: 20px;
    background-color: #131b30;
    border: 1px solid #21294a;
}}
QFrame#HeroGradient {{
    border-radius: 20px;
    background-color: #131b30;
    border: 1px solid #21294a;
}}
QPushButton#LinkButton {{
    background: transparent;
    border: none;
    color: {FOX_HOVER};
    font-weight: 700;
    font-size: 11.5px;
    padding: 2px 0;
    text-align: left;
}}
QPushButton#LinkButton:hover {{ color: {FOX}; }}
QFrame#Disclaimer {{
    background-color: #2a1d10;
    border: 1px solid #55381a;
    border-radius: 16px;
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
QLabel#CardTitle {{ font-size: 14px; font-weight: 800; color: white; }}
QLabel#ErrorBanner {{
    background-color: #3a1418;
    color: #fda4af;
    border: 1px solid #5c1f27;
    border-radius: 12px;
    padding: 10px;
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
QProgressBar#JourneyBar {{ background-color: #2a1d10; border-radius: 4px; }}
QProgressBar#JourneyBar::chunk {{ border-radius: 4px; background-color: {FOX}; }}

QComboBox {{
    background-color: #131b30;
    color: #e7ecf7;
    border: 1px solid #263457;
    border-radius: 12px;
    padding: 6px 10px;
    min-height: 22px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 32px; }}
QComboBox::down-arrow {{ image: url({CHEVRON_DARK}); width: 12px; height: 12px; }}
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

QRadioButton {{ spacing: 10px; font-weight: 600; padding: 2px 0; }}
QRadioButton::indicator {{
    width: 19px; height: 19px;
    border-radius: 12px;
    border: 2px solid #263457;
    background: #131b30;
}}
QRadioButton::indicator:hover {{ border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{
    border: 2px solid {FOX};
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
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
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
    border-radius: 12px;
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

QListWidget {{
    background: #131b30;
    color: #e7ecf7;
    border: 1px solid #21294a;
    border-radius: 12px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:selected {{ background-color: #1a2340; color: {FOX_HOVER}; }}

QMessageBox {{ background-color: #0f1526; }}
QDialog {{ background-color: #0f1526; }}

QMenuBar {{
    background-color: #0b1020;
    border-bottom: 1px solid #1d2740;
    padding: 2px 4px;
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 6px;
    background: transparent;
    color: #e7ecf7;
}}
QMenuBar::item:selected {{ background-color: #1a2340; color: {FOX_HOVER}; }}
QMenu {{
    background-color: #131b30;
    border: 1px solid #21294a;
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px 7px 14px;
    border-radius: 6px;
    color: #e7ecf7;
}}
QMenu::item:selected {{ background-color: #1a2340; color: {FOX_HOVER}; }}
QMenu::separator {{ height: 1px; background: #21294a; margin: 6px 8px; }}
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
    "Oiliness": "#a3a316",
    "Tone evenness": "#a855f7",
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
        "success": "#047857", "on_primary": "white",
    },
}


def icon_color(kind: str = "primary", theme: str | None = None) -> str:
    table = _ICON_COLORS["dark" if (theme or _current_theme) == "dark" else "light"]
    return table.get(kind, table["primary"])


# Muted secondary-text color as a raw hex value, for the handful of spots
# (rich-text HTML spans, matplotlib chrome) that can't use the QLabel#Muted
# QSS class directly. Matches #Muted/#SubHeading's color in each theme.
MUTED_LIGHT = "#6b7280"
MUTED_DARK = "#7a86a8"


def muted_text_color(theme: str | None = None) -> str:
    return MUTED_DARK if (theme or _current_theme) == "dark" else MUTED_LIGHT


def pill_stylesheet(level: str, theme: str | None = None) -> str:
    """Inline stylesheet for a severity 'pill' badge, built on
    level_pill_colors() so history/compare pages don't hand-roll the same
    f-string in multiple places."""
    bg, text = level_pill_colors(level, theme)
    return (
        f"background-color: {bg}; color: {text}; border-radius: 10px; "
        "padding: 3px 10px; font-weight: 700;"
    )


# Comparison-delta text colors, tuned per theme the same way LEVEL_PILL_*
# is: light mode needs deeper shades of the same hue to clear WCAG AA on
# white, dark mode's background is dark enough that the vivid hues clear it
# on their own.
DELTA_COLORS_LIGHT = {
    "improved": "#047857",
    "worsened": "#be123c",
    "unchanged": "#6b7280",
}
DELTA_COLORS_DARK = {
    "improved": "#10b981",
    "worsened": "#f43f5e",
    "unchanged": "#8993a8",
}


def delta_color(direction: str, theme: str | None = None) -> str:
    table = DELTA_COLORS_DARK if (theme or _current_theme) == "dark" else DELTA_COLORS_LIGHT
    return table.get(direction, table["unchanged"])


# Frosted-glass overlay tint + hairline border (RGBA tuples), used by the
# Toast and LockScreen widgets to tint a blurred backdrop snapshot -- a
# Qt-only approximation of acrylic/glassmorphism (QGraphicsBlurEffect over a
# grabbed pixmap), no OS-level compositing APIs.
GLASS_TINT_LIGHT = (255, 255, 255, 190)
GLASS_TINT_DARK = (19, 27, 48, 195)
GLASS_BORDER_LIGHT = (11, 18, 36, 20)
GLASS_BORDER_DARK = (255, 255, 255, 26)


def glass_tint(theme: str | None = None) -> tuple[int, int, int, int]:
    return GLASS_TINT_DARK if (theme or _current_theme) == "dark" else GLASS_TINT_LIGHT


def glass_border(theme: str | None = None) -> tuple[int, int, int, int]:
    return GLASS_BORDER_DARK if (theme or _current_theme) == "dark" else GLASS_BORDER_LIGHT
