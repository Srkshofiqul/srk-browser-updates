"""
Browser Profile Manager - Global Configuration & Styling Module
Python 3.13 / PySide6 Desktop Application
"""

import json
import os
import sys
import traceback

def _global_excepthook(exctype, value, tb):
    try:
        with open("crash_debug.log", "a", encoding="utf-8") as f:
            f.write("".join(traceback.format_exception(exctype, value, tb)) + "\n")
    except Exception:
        pass
    sys.__excepthook__(exctype, value, tb)
sys.excepthook = _global_excepthook

from pathlib import Path
from typing import Any, Dict, List, Optional

# Directories & Portable Customer Architecture
if getattr(sys, 'frozen', False):
    app_root = Path(sys.executable).parent.resolve()
else:
    app_root = Path(__file__).resolve().parent.parent.parent

local_data_dir = app_root / "data"
appdata_path = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "BrowserProfileManager"

# Auto-migration: if APPDATA has existing data and local_data_dir is empty/new, migrate smoothly
if not (local_data_dir / "profiles.json").exists() and (appdata_path / "profiles.json").exists():
    try:
        import shutil
        local_data_dir.mkdir(parents=True, exist_ok=True)
        for item in appdata_path.iterdir():
            target = local_data_dir / item.name
            if not target.exists():
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
    except Exception:
        pass

# Use portable local_data_dir as BASE_DIR
local_data_dir.mkdir(parents=True, exist_ok=True)
BASE_DIR = local_data_dir

meipass_dir = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent.resolve()))
ASSETS_DIR = meipass_dir / "assets" if (meipass_dir / "assets").exists() else app_root / "assets"

PROFILES_DIR = BASE_DIR / "profiles"
REPORTS_DIR = BASE_DIR / "reports"
EXTENSIONS_DIR = BASE_DIR / "extensions"
PROFILES_DB_FILE = BASE_DIR / "profiles.json"
GROUPS_FILE = BASE_DIR / "groups.json"
SETTINGS_FILE = BASE_DIR / "settings.json"
EXTENSIONS_DB_FILE = BASE_DIR / "extensions.json"
BOOKMARKS_DB_FILE = BASE_DIR / "bookmarks.json"

# Ensure directories exist
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)

from utils import safe_read_json, safe_write_json
from version import APP_VERSION

# Application Metadata
APP_NAME = "srkBrowser"
ORGANIZATION_NAME = "SRK Shofiqul"
DEVELOPER_NAME = "SRK Shofiqul"
DEVELOPER_WEBSITE = "https://srbrowser.com"
DEVELOPER_TELEGRAM = "https://t.me/srkplatforms"

# KeyAuth Cloud Licensing Credentials
KEYAUTH_NAME = "BrowserProfileManager"
KEYAUTH_OWNER_ID = "5NNrBV77cY"
KEYAUTH_SECRET = "cadb4dc8c55718a2123a6c8403de033830f41b0f686a93ab74f05f937e48d725"
KEYAUTH_VERSION = "1.0"

# Website License Verification Endpoint
WEBSITE_API_URL = "https://api.srbrowser.com/api/v1/bot/verify"
SETTINGS_FILE = BASE_DIR / "settings.json"
EXTENSIONS_DB_FILE = BASE_DIR / "extensions.json"
BOOKMARKS_DB_FILE = BASE_DIR / "bookmarks.json"

# Ensure directories exist
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Categories
CATEGORIES = [
    "General", "Work", "Personal", "Social",
    "Crypto", "Testing", "Marketing", "Learning"
]

# Color Palette Options for Profiles
COLOR_PALETTE = {
    "Blue": "#89b4fa",
    "Green": "#a6e3a1",
    "Peach": "#fab387",
    "Mauve": "#cba6f7",
    "Red": "#f38ba8",
    "Teal": "#94e2d5",
    "Yellow": "#f9e2af",
    "Sky": "#89dceb"
}

# Supported Browser Languages for Profile Fingerprints (ixBrowser / AdsPower Standard)
SUPPORTED_PROFILE_LANGUAGES = [
    ("en-US", "English (United States) [en-US]"),
    ("en-GB", "English (United Kingdom) [en-GB]"),
    ("en-CA", "English (Canada) [en-CA]"),
    ("en-AU", "English (Australia) [en-AU]"),
    ("es-ES", "Spanish (Spain) [es-ES]"),
    ("es-MX", "Spanish (Mexico) [es-MX]"),
    ("fr-FR", "French (France) [fr-FR]"),
    ("de-DE", "German (Germany) [de-DE]"),
    ("pt-BR", "Portuguese (Brazil) [pt-BR]"),
    ("pt-PT", "Portuguese (Portugal) [pt-PT]"),
    ("it-IT", "Italian (Italy) [it-IT]"),
    ("nl-NL", "Dutch (Netherlands) [nl-NL]"),
    ("pl-PL", "Polish (Poland) [pl-PL]"),
    ("tr-TR", "Turkish (Turkey) [tr-TR]"),
    ("ru-RU", "Russian (Russia) [ru-RU]"),
    ("ar-SA", "Arabic (Saudi Arabia) [ar-SA]"),
    ("hi-IN", "Hindi (India) [hi-IN]"),
    ("bn-BD", "Bengali (Bangladesh) [bn-BD]"),
    ("id-ID", "Indonesian (Indonesia) [id-ID]"),
    ("vi-VN", "Vietnamese (Vietnam) [vi-VN]"),
    ("th-TH", "Thai (Thailand) [th-TH]"),
    ("ja-JP", "Japanese (Japan) [ja-JP]"),
    ("ko-KR", "Korean (South Korea) [ko-KR]"),
    ("zh-CN", "Chinese (Simplified) [zh-CN]"),
    ("zh-TW", "Chinese (Traditional) [zh-TW]")
]
DEFAULT_PROFILE_LANGUAGE = "en-US"

# Default Pre-created Groups
DEFAULT_GROUPS = ["Default", "Work", "Personal", "Social", "Crypto", "Testing"]


def load_groups() -> List[str]:
    """Load groups list from groups.json."""
    data = safe_read_json(GROUPS_FILE)
    if isinstance(data, list) and len(data) > 0:
        return data
    safe_write_json(GROUPS_FILE, DEFAULT_GROUPS)
    return DEFAULT_GROUPS.copy()


def save_groups(groups: List[str]) -> bool:
    """Save groups list to groups.json."""
    return safe_write_json(GROUPS_FILE, groups)


def load_settings() -> Dict[str, Any]:
    """Load application settings from settings.json."""
    data = safe_read_json(SETTINGS_FILE)
    if isinstance(data, dict):
        if "browser_window_size" not in data:
            data["browser_window_size"] = "1280x800"
        if "auto_check_updates" not in data:
            data["auto_check_updates"] = False
        return data
    default_settings = {
        "browser_path": "",
        "theme": "Dark",
        "default_window_width": 1280,
        "default_window_height": 840,
        "browser_window_size": "1280x800",
        "language": "English",
        "auto_check_updates": False
    }
    safe_write_json(SETTINGS_FILE, default_settings)
    return default_settings


def save_settings(settings: Dict[str, Any]) -> bool:
    """Save settings dictionary to settings.json."""
    return safe_write_json(SETTINGS_FILE, settings)


# Ultra-Sleek Modern Catppuccin Mocha QSS Stylesheet
DARK_STYLESHEET = """
/* Base Global Window & Dialog Styling */
QMainWindow, QDialog {
    background-color: #11111b;
    color: #cdd6f4;
    font-family: "Nirmala UI", "Segoe UI", "Vrinda", "Kalpurush", "SolaimanLipi", sans-serif;
    font-size: 13px;
}

/* Global QScrollArea Dark Engine Override */
QScrollArea {
    background-color: #11111b;
    border: none;
}

QScrollArea > QWidget {
    background-color: #11111b;
}

QScrollArea > QWidget > QWidget {
    background-color: #11111b;
}

/* Global QGroupBox Styling */
QGroupBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px;
    font-size: 13px;
    font-weight: bold;
    color: #89b4fa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: #1e1e2e;
    color: #89b4fa;
    border: 1px solid #313244;
    border-radius: 6px;
    font-weight: bold;
}

/* Global Labels & Form Labels Styling */
QLabel {
    color: #cdd6f4;
    font-size: 13px;
}

QDialog QLabel {
    color: #cdd6f4;
}

QFormLayout QLabel {
    color: #cdd6f4;
    font-weight: 600;
    font-size: 13px;
}

/* Global QTabWidget & QTabBar Styling */
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 10px;
    background-color: #181825;
}

QTabBar::tab {
    background-color: #1e1e2e;
    color: #a6adc8;
    border: 1px solid #313244;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #313244;
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #2b2b3d;
    color: #ffffff;
}

/* Luxury Modern Top Navigation Bar */
QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #0f111e);
    border-bottom: 1px solid #1f233a;
    padding: 7px 12px;
    spacing: 7px;
}

QToolBar QToolButton {
    background-color: #191c2e;
    color: #cdd6f4;
    border: 1px solid #282d47;
    border-radius: 8px;
    padding: 6px 13px;
    font-weight: 700;
    font-size: 11.5px;
}

QToolBar QToolButton:hover {
    background-color: #232742;
    color: #ffffff;
    border-color: #4b5585;
}

QToolBar QToolButton:pressed {
    background-color: #121422;
}

QToolBar::separator {
    width: 1px;
    background-color: #242944;
    margin: 6px 4px;
}

/* Luxury Sidebar Navigation Frame */
QFrame#SidebarFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f111e, stop:1 #131626);
    border-right: 1px solid #1f233a;
}

QLabel#AppTitleLabel {
    color: #89b4fa;
    font-size: 18px;
    font-weight: 800;
    padding: 10px 4px;
}

QPushButton#SidebarButton {
    background-color: transparent;
    color: #8c93b0;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 9px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#SidebarButton:hover {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.07);
    color: #ffffff;
}

QPushButton#SidebarButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(99, 102, 241, 0.24), stop:1 rgba(59, 130, 246, 0.12));
    border: 1px solid rgba(99, 102, 241, 0.45);
    border-left: 3px solid #818cf8;
    color: #ffffff;
    font-weight: 800;
}

/* Page Headers */
QLabel#HeaderTitle {
    font-size: 22px;
    font-weight: bold;
    color: #cdd6f4;
}

QLabel#HeaderSubtitle {
    font-size: 13px;
    color: #a6adc8;
}

/* Stat Cards */
QFrame#StatCard {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 12px;
}

QLabel#StatLabel {
    color: #a6adc8;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.5px;
}

QLabel#StatValue {
    font-size: 26px;
    font-weight: bold;
}

/* Inputs & Combos */
QLineEdit, QComboBox, QTextEdit {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #45475a;
}

QSpinBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 13px;
    min-height: 28px;
    selection-background-color: #45475a;
}

QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 20px;
    background-color: #313244;
    border: none;
    border-radius: 4px;
    margin: 2px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #45475a;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border-color: #89b4fa;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 8px;
    selection-background-color: #313244;
    selection-color: #89b4fa;
    padding: 4px;
}

/* List & Tree Widgets */
QListWidget, QTreeWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 6px;
    font-size: 13.5px;
    font-weight: 600;
}

QListWidget::item, QTreeWidget::item {
    color: #cdd6f4;
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 2px;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #252538;
    color: #89b4fa;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #313244;
    color: #89b4fa;
    font-weight: bold;
}

/* Standard & Action Buttons */
QPushButton {
    background-color: #89b4fa;
    color: #11111b;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
    font-size: 12.5px;
}

QPushButton:hover {
    background-color: #b4befe;
}

QPushButton#SecondaryButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
}

QPushButton#SecondaryButton:hover {
    background-color: #45475a;
    color: #ffffff;
    border-color: #89b4fa;
}

QPushButton#DangerButton {
    background-color: rgba(243, 139, 168, 0.15);
    color: #f38ba8;
    border: 1px solid rgba(243, 139, 168, 0.4);
}

QPushButton#DangerButton:hover {
    background-color: #f38ba8;
    color: #11111b;
}

/* Checkbox & RadioButton Styling */
QCheckBox, QRadioButton {
    color: #cdd6f4;
    font-size: 13px;
    font-weight: 600;
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #45475a;
    background-color: #1e1e2e;
}

QRadioButton::indicator {
    border-radius: 9px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QRadioButton:hover, QCheckBox:hover {
    color: #89b4fa;
}

/* Modern Ultra-Slim ScrollBar Styling */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 2px 1px 2px 1px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #25283d;
    min-height: 36px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #6366f1;
}

QScrollBar::handle:vertical:pressed {
    background: #818cf8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}

QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
    border: none;
    background: none;
    width: 0px;
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    border: none;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 6px;
    margin: 1px 2px 1px 2px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal {
    background: #25283d;
    min-width: 36px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #6366f1;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    border: none;
    background: none;
}

/* Status Bar */
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
    padding: 4px 12px;
}

/* Table Widget Styling */
QTableWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 10px;
    color: #ffffff;
    gridline-color: #313244;
}

QTableWidget::item {
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 12px;
    border-bottom: 1px solid #232438;
}

QTableWidget::item:hover {
    background-color: #232438;
    color: #89b4fa;
}

QHeaderView::section {
    background-color: #11111b;
    color: #89b4fa;
    padding: 12px 14px;
    border: none;
    border-bottom: 2px solid #89b4fa;
    font-size: 13px;
    font-weight: bold;
}
"""
