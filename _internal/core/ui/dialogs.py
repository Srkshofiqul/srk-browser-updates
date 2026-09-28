"""
Browser Profile Manager - Dialog Windows Module
Python 3.13 / PySide6 Desktop Application
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PySide6.QtCore import Qt, Signal, QSize, QRect, QPoint, QThread, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGraphicsOpacityEffect, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QPlainTextEdit, QVBoxLayout, QWidget
)

from config import APP_NAME, APP_VERSION, CATEGORIES, COLOR_PALETTE, REPORTS_DIR, load_settings

from utils import generate_random_user_agent, get_system_browsers, read_excel_or_csv, get_display_number
# Core Profile Dialogs - Pure Decoupled Architecture
from profile_manager import filter_by_profile_numbers

def center_dialog_over_parent(dialog: QWidget, parent: Optional[QWidget] = None) -> None:
    """Center a dialog directly over its top-level parent window on screen."""
    p = parent or dialog.parent()
    if not p:
        return
    try:
        top_window = p.window() if hasattr(p, "window") and p.window() else p
        p_geo = top_window.frameGeometry() if hasattr(top_window, "frameGeometry") else top_window.geometry()
        d_size = dialog.sizeHint() if hasattr(dialog, "sizeHint") and dialog.sizeHint().isValid() else dialog.size()
        w = max(d_size.width(), dialog.width(), 480)
        h = max(d_size.height(), dialog.height(), 400)
        x = p_geo.x() + (p_geo.width() - w) // 2
        y = p_geo.y() + (p_geo.height() - h) // 2
        x = max(20, x)
        y = max(20, y)
        dialog.move(x, y)
    except Exception:
        pass

def create_license_validity_badge(bot_id: str, is_free: bool = False) -> QLabel:
    """Create a sleek QLabel displaying the remaining days or validity status for a bot's license."""
    try:
        from bot_license_manager import BotLicenseManager
        mgr = BotLicenseManager()
        text = mgr.get_license_status_label(bot_id, is_free_module=is_free)
    except Exception:
        text = "👑 VIP User (30 Days Active)" if not is_free else "🎁 License: Free Module"

    lbl = QLabel(text)
    if "enterprise" in text.lower():
        color_bg = "rgba(234, 179, 8, 0.2)"
        color_fg = "#fbbf24"
        color_border = "rgba(245, 158, 11, 0.7)"
    elif "vip" in text.lower():
        color_bg = "rgba(168, 85, 247, 0.25)"
        color_fg = "#facc15"
        color_border = "rgba(234, 179, 8, 0.6)"
    elif "free" in text.lower():
        color_bg = "rgba(166, 227, 161, 0.15)"
        color_fg = "#a6e3a1"
        color_border = "rgba(166, 227, 161, 0.35)"
    elif "lifetime" in text.lower():
        color_bg = "rgba(203, 166, 247, 0.15)"
        color_fg = "#cba6f7"
        color_border = "rgba(203, 166, 247, 0.35)"
    else:
        color_bg = "rgba(137, 180, 250, 0.15)"
        color_fg = "#89b4fa"
        color_border = "rgba(137, 180, 250, 0.35)"

    lbl.setStyleSheet(f"""
        background: {color_bg};
        color: {color_fg};
        border: 1px solid {color_border};
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 12px;
        font-weight: bold;
    """)
    return lbl

FB_PAGE_CATEGORIES = [
    "Digital Creator",
    "Personal Blog",
    "Gaming Video Creator",
    "Gamer",
    "Video Creator",
    "Entrepreneur",
    "Product/Service",
    "Shopping & Retail",
    "Health/Beauty",
    "Musician/Band",
    "Education",
    "News & Media Website",
    "Media/News Company",
    "Community",
    "E-commerce Website",
    "Public Figure",
    "App Page",
    "Clothing (Brand)",
    "Restaurant",
    "Real Estate"
]


def parse_marketing_comments(raw_input: Any) -> List[str]:
    """Simple and reliable 1-comment-per-line parser."""
    if isinstance(raw_input, list):
        raw_text = "\n".join(raw_input)
    else:
        raw_text = str(raw_input or "")
    return [line.strip() for line in raw_text.splitlines() if line.strip()]



class HowToUseDialog(QDialog):
    """Ultra-Luxury Dark Obsidian popup window displaying step-by-step How to Use Quick Guide for automation tools."""

    def __init__(self, title: str, steps: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        clean_title = title.replace("📖 ", "").replace(" Guide", "").strip()
        self.setWindowTitle(f"📖 {clean_title} — Quick Usage Guide")
        self.resize(600, 480)
        self.setMinimumSize(500, 360)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 14px;
                font-family: 'Segoe UI', system-ui, 'Nirmala UI', sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("📖")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel(f"{clean_title} — ব্যবহার করার নিয়ম")
        lbl_t.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        lbl_sub = QLabel("Step-by-step operating instructions and recommended workflow")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        layout.addWidget(hdr_frame)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: #10121e; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #232742; min-height: 20px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: #4f46e5; }
        """)

        content_w = QWidget()
        content_w.setStyleSheet("background: transparent;")
        content_vbox = QVBoxLayout(content_w)
        content_vbox.setContentsMargins(0, 0, 6, 0)
        content_vbox.setSpacing(10)

        if isinstance(steps, str):
            step_list = [s.strip() for s in steps.splitlines() if s.strip()]
        else:
            step_list = steps

        for idx, step in enumerate(step_list, 1):
            if isinstance(step, (list, tuple)):
                if len(step) >= 2:
                    step_text = f"<span style='color: #818cf8; font-weight: 800; font-size: 13.5px;'>Step {idx}: {step[0]}</span><br/><span style='color: #cbd5e1; font-size: 12.5px; line-height: 1.5;'>{step[1]}</span>"
                else:
                    step_text = f"<span style='color: #cbd5e1; font-size: 12.5px;'>{step[0]}</span>"
            else:
                step_text = f"<span style='color: #cbd5e1; font-size: 12.5px;'>{step}</span>"

            lbl = QLabel(step_text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #131626;
                    color: #f1f5f9;
                    border: 1px solid #202438;
                    border-left: 3px solid #6366f1;
                    border-radius: 8px;
                    padding: 12px 16px;
                    font-size: 13px;
                    line-height: 1.5;
                }
            """)
            content_vbox.addWidget(lbl)

        scroll_area.setWidget(content_w)
        layout.addWidget(scroll_area, stretch=1)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_close = QPushButton("Close / বুঝেছি ✓")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 24px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)



class PinPromptDialog(QDialog):
    """Luxury Obsidian Dialog for requesting PIN verification before accessing protected profile actions."""

    def __init__(self, target_pin: str, profile_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🔐 Security PIN Required")
        self.setFixedSize(400, 240)
        self.target_pin = target_pin
        self.profile_name = profile_name

        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QLineEdit {
                background-color: #10121e;
                color: #fbbf24;
                border: 1.5px solid #232742;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 16px;
                font-weight: bold;
                letter-spacing: 4px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:focus {
                border-color: #6366f1;
                background-color: #131626;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(8, 6, 8, 6)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🔐")
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel("Security PIN Verification")
        lbl_t.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        lbl_sub = QLabel(f"Profile: <span style='color: #818cf8; font-weight: 800;'>{self.profile_name}</span> is protected")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        layout.addWidget(hdr_frame)

        # Prompt instruction
        lbl_inst = QLabel("Please enter the 4-digit Security PIN to proceed:")
        lbl_inst.setStyleSheet("font-size: 11.5px; color: #94a3b8; font-weight: 600;")
        layout.addWidget(lbl_inst)

        self.txt_pin = QLineEdit()
        self.txt_pin.setEchoMode(QLineEdit.Password)
        self.txt_pin.setPlaceholderText("••••")
        self.txt_pin.setAlignment(Qt.AlignCenter)
        self.txt_pin.setMaxLength(16)
        self.txt_pin.returnPressed.connect(self._verify_pin)
        layout.addWidget(self.txt_pin)

        # Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
                border-color: #3b4268;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_unlock = QPushButton("🔓 Unlock Profile")
        btn_unlock.setCursor(Qt.PointingHandCursor)
        btn_unlock.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
            }
        """)
        btn_unlock.clicked.connect(self._verify_pin)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_unlock)

        layout.addLayout(btn_layout)

    def _verify_pin(self) -> None:
        entered = self.txt_pin.text().strip()
        if entered == self.target_pin:
            self.accept()
        else:
            QMessageBox.warning(self, "Incorrect PIN", "The entered Security PIN is incorrect. Please try again.")
            self.txt_pin.clear()
            self.txt_pin.setFocus()



class BulkCreateDialog(QDialog):
    """Dialog for creating multiple profiles simultaneously in bulk."""

    def __init__(self, available_groups: List[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚡ Bulk Create Profiles")
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #ffffff;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #10121e;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #6366f1;
                background-color: #14172a;
            }
        """)
        self.groups = available_groups

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 16, 18, 16)

        hdr_box = QHBoxLayout()
        lbl_icon_title = QLabel("⚡  <b>Bulk Create Profiles</b>")
        lbl_icon_title.setStyleSheet("font-size: 16px; color: #818cf8; background: transparent; border: none;")
        lbl_sub = QLabel("Fast generator for multiple browser instances")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 11.5px; background: transparent; border: none;")
        hdr_box.addWidget(lbl_icon_title)
        hdr_box.addSpacing(10)
        hdr_box.addWidget(lbl_sub)
        hdr_box.addStretch()
        layout.addLayout(hdr_box)

        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        form = QFormLayout(form_frame)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(12)

        self.spn_count = QSpinBox()
        self.spn_count.setRange(1, 100)
        self.spn_count.setValue(5)

        self.txt_prefix = QLineEdit()
        self.txt_prefix.setPlaceholderText("e.g. Account or Work (Leave blank for auto)")

        self.cmb_group = QComboBox()
        self.cmb_group.addItems(self.groups)

        self.cmb_category = QComboBox()
        self.cmb_category.addItems(CATEGORIES)

        self.txt_start_url = QLineEdit()
        self.txt_start_url.setPlaceholderText("e.g. https://google.com")

        self.cmb_proxy_type = QComboBox()
        self.cmb_proxy_type.addItems(["None", "HTTP", "SOCKS5"])

        self.cmb_language = QComboBox()
        try:
            from config import SUPPORTED_PROFILE_LANGUAGES
            for l_code, l_label in SUPPORTED_PROFILE_LANGUAGES:
                self.cmb_language.addItem(f"🌐 {l_label}", l_code)
        except Exception:
            self.cmb_language.addItem("🌐 English (United States) [en-US]", "en-US")
        self.cmb_language.setCurrentIndex(0)

        form.addRow("Number of Profiles:", self.spn_count)
        form.addRow("Name Prefix:", self.txt_prefix)
        form.addRow("Group:", self.cmb_group)
        form.addRow("Category Tag:", self.cmb_category)
        form.addRow("Start Page URL:", self.txt_start_url)
        form.addRow("Browser Language:", self.cmb_language)
        form.addRow("Proxy Type:", self.cmb_proxy_type)

        layout.addWidget(form_frame)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #232742;
                color: #ffffff;
                border-color: #4b5585;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_create = QPushButton("⚡ Generate Bulk Profiles")
        btn_create.setCursor(Qt.PointingHandCursor)
        btn_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 8px 22px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                border-color: #818cf8;
            }
        """)
        btn_create.clicked.connect(self.accept)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_create)

        layout.addLayout(btn_layout)

    def get_data(self) -> Dict[str, Any]:
        return {
            "count": self.spn_count.value(),
            "name_prefix": self.txt_prefix.text().strip(),
            "group": self.cmb_group.currentText(),
            "category": self.cmb_category.currentText(),
            "start_url": self.txt_start_url.text().strip(),
            "language": self.cmb_language.currentData() or "en-US",
            "proxy_type": self.cmb_proxy_type.currentText()
        }


class QuickCreateGroupDialog(QDialog):
    """Luxury Dark Modal Dialog to quickly create a new profile group."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Group")
        self.setFixedSize(300, 115)
        self.setStyleSheet("""
            QDialog {
                background-color: #0c0f18;
                color: #f1f5f9;
                border: 1px solid #232845;
                border-radius: 10px;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11.5px;
                font-weight: 700;
            }
            QLineEdit {
                background-color: #080a13;
                color: #ffffff;
                border: 1px solid #283050;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #0e1222;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        lbl = QLabel("Enter group name:")
        self.txt_group = QLineEdit()
        self.txt_group.setPlaceholderText("Group name...")
        self.txt_group.returnPressed.connect(self.accept)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #181d33;
                color: #94a3b8;
                border: 1px solid #282d47;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #232742;
                color: #ffffff;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("Create Group")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setFixedHeight(28)
        btn_ok.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                color: #ffffff;
                border: 1px solid #60a5fa;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                border-color: #93c5fd;
            }
        """)
        btn_ok.clicked.connect(self.accept)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)

        layout.addWidget(lbl)
        layout.addWidget(self.txt_group)
        layout.addLayout(btn_box)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_dialog_over_parent(self, self.parent())

    def get_group_name(self) -> str:
        return self.txt_group.text().strip()


class QuickRenameGroupDialog(QDialog):
    """Luxury Dark Modal Dialog to rename a profile group."""

    def __init__(self, current_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename Group")
        self.setFixedSize(300, 115)
        self.setStyleSheet("""
            QDialog {
                background-color: #0c0f18;
                color: #f1f5f9;
                border: 1px solid #232845;
                border-radius: 10px;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11.5px;
                font-weight: 700;
            }
            QLineEdit {
                background-color: #080a13;
                color: #ffffff;
                border: 1px solid #283050;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border-color: #f59e0b;
                background-color: #0e1222;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        lbl = QLabel(f"Rename '{current_name}' to:")
        self.txt_group = QLineEdit(current_name)
        self.txt_group.selectAll()
        self.txt_group.returnPressed.connect(self.accept)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #181d33;
                color: #94a3b8;
                border: 1px solid #282d47;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #232742;
                color: #ffffff;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("Rename Group")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setFixedHeight(28)
        btn_ok.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
                color: #ffffff;
                border: 1px solid #fbbf24;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309);
                border-color: #fcd34d;
            }
        """)
        btn_ok.clicked.connect(self.accept)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)

        layout.addWidget(lbl)
        layout.addWidget(self.txt_group)
        layout.addLayout(btn_box)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_dialog_over_parent(self, self.parent())

    def get_group_name(self) -> str:
        return self.txt_group.text().strip()


class GroupManagerDialog(QDialog):
    """Luxury Modal Dialog for managing, creating, renaming, and deleting profile groups."""

    def __init__(self, profile_mgr: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Profile Groups Manager")
        self.setFixedSize(500, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d18;
                color: #ffffff;
            }
        """)
        self.profile_mgr = profile_mgr
        self._init_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_dialog_over_parent(self, self.parent())

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        # Header Bar
        hdr_box = QHBoxLayout()
        hdr_box.setContentsMargins(2, 0, 2, 0)
        lbl_icon_title = QLabel("📁  <b>Profile Groups Manager</b>")
        lbl_icon_title.setStyleSheet("font-size: 15.5px; color: #ffffff; background: transparent; border: none; font-weight: 800;")
        
        self.lbl_count_badge = QLabel("✨ Groups")
        self.lbl_count_badge.setStyleSheet("background: rgba(99, 102, 241, 0.12); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 6px; padding: 2px 8px; font-size: 10.5px; font-weight: 700;")
        
        hdr_box.addWidget(lbl_icon_title)
        hdr_box.addSpacing(6)
        hdr_box.addWidget(self.lbl_count_badge)
        hdr_box.addStretch()
        layout.addLayout(hdr_box)

        # Group List Container
        self.lst_groups = QListWidget()
        self.lst_groups.setStyleSheet("""
            QListWidget {
                background-color: #0e111f;
                color: #cdd6f4;
                border: 1px solid #1f2540;
                border-radius: 12px;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item {
                background-color: #101324;
                border: 1px solid #202642;
                border-radius: 10px;
                margin-bottom: 5px;
                padding: 0px;
                outline: none;
            }
            QListWidget::item:hover {
                background-color: #161b34;
                border: 1px solid #3b4573;
            }
            QListWidget::item:selected {
                background-color: #181e3c;
                border: 1.5px solid #6366f1;
                outline: none;
            }
            QScrollBar:vertical {
                background: #090a14;
                width: 6px;
                border-radius: 3px;
                margin: 4px 2px 4px 0px;
            }
            QScrollBar::handle:vertical {
                background: #282d47;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6366f1;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
        """)
        self.lst_groups.itemDoubleClicked.connect(self._rename_group)

        # Action Buttons Row
        btn_hbox = QHBoxLayout()
        btn_hbox.setSpacing(10)

        btn_add = QPushButton("➕ Add Group")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setFixedHeight(34)
        btn_add.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 0 18px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
            }
        """)
        btn_add.clicked.connect(self._add_group)

        btn_rename = QPushButton("✏️ Rename")
        btn_rename.setCursor(Qt.PointingHandCursor)
        btn_rename.setFixedHeight(34)
        btn_rename.setStyleSheet("""
            QPushButton {
                background-color: #141829;
                color: #fbbf24;
                border: 1px solid rgba(251, 191, 36, 0.35);
                border-radius: 8px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #20243d;
                border-color: #fbbf24;
            }
        """)
        btn_rename.clicked.connect(self._rename_group)

        btn_delete = QPushButton("🗑️ Delete")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.setFixedHeight(34)
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.12);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 8px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.22);
                border-color: #ef4444;
            }
        """)
        btn_delete.clicked.connect(self._delete_group)

        btn_hbox.addWidget(btn_add)
        btn_hbox.addWidget(btn_rename)
        btn_hbox.addWidget(btn_delete)
        btn_hbox.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #141829;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 0 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #20253d;
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.accept)

        btn_hbox.addWidget(btn_close)

        layout.addLayout(hdr_box)
        layout.addWidget(self.lst_groups, stretch=1)
        layout.addLayout(btn_hbox)

        self.refresh_groups_list()

    def refresh_groups_list(self) -> None:
        self.lst_groups.clear()
        groups_list = self.profile_mgr.get_groups() if self.profile_mgr else ["Default"]
        self.lbl_count_badge.setText(f"📁 {len(groups_list)} Groups")

        counts = {g: 0 for g in groups_list}
        if self.profile_mgr:
            for p in self.profile_mgr.profiles:
                g_name = p.get("group", "Default")
                counts[g_name] = counts.get(g_name, 0) + 1

        for g in groups_list:
            c = counts.get(g, 0)
            unit_str = "profile" if c == 1 else "profiles"

            item = QListWidgetItem(self.lst_groups)
            item.setSizeHint(QSize(0, 48))
            item.setData(Qt.UserRole, g)

            widget = QWidget()
            widget.setStyleSheet("background: transparent;")
            w_layout = QHBoxLayout(widget)
            w_layout.setContentsMargins(12, 6, 14, 6)
            w_layout.setSpacing(12)

            lbl_icon = QLabel("📁")
            lbl_icon.setStyleSheet("font-size: 13.5px; background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.25); border-radius: 8px; padding: 3px 8px;")

            lbl_name = QLabel(g)
            lbl_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc; background: transparent; border: none;")

            lbl_count = QLabel(f"✨ {c} {unit_str}" if c > 0 else "0 profiles")
            if c > 0:
                lbl_count.setStyleSheet("font-size: 11px; font-weight: 800; color: #818cf8; background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 12px; padding: 3px 12px;")
            else:
                lbl_count.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; background: rgba(100, 116, 139, 0.12); border: 1px solid rgba(100, 116, 139, 0.25); border-radius: 12px; padding: 3px 10px;")

            w_layout.addWidget(lbl_icon)
            w_layout.addWidget(lbl_name, stretch=1)
            w_layout.addWidget(lbl_count)

            self.lst_groups.setItemWidget(item, widget)

    def _add_group(self) -> None:
        dlg = QuickCreateGroupDialog(self)
        if dlg.exec() == QDialog.Accepted:
            g_name = dlg.get_group_name()
            if g_name:
                if self.profile_mgr and self.profile_mgr.add_group(g_name):
                    self.refresh_groups_list()
                else:
                    QMessageBox.warning(self, "Group Error", "Group already exists or invalid name.")

    def _rename_group(self) -> None:
        selected = self.lst_groups.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Required", "Please select a group to rename.")
            return

        old_g = selected.data(Qt.UserRole)
        if old_g == "Default":
            QMessageBox.warning(self, "Action Restricted", "The 'Default' group cannot be renamed.")
            return

        dlg = QuickRenameGroupDialog(old_g, self)
        if dlg.exec() == QDialog.Accepted:
            new_name = dlg.get_group_name()
            if new_name and new_name != old_g:
                if self.profile_mgr and self.profile_mgr.rename_group(old_g, new_name):
                    self.refresh_groups_list()
                else:
                    QMessageBox.warning(self, "Rename Error", "Could not rename group.")

    def _delete_group(self) -> None:
        selected = self.lst_groups.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Required", "Please select a group to delete.")
            return

        g_name = selected.data(Qt.UserRole)
        if g_name == "Default":
            QMessageBox.warning(self, "Action Restricted", "The 'Default' group cannot be deleted.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete Group",
            f"Are you sure you want to delete group '{g_name}'?\n"
            "All profiles belonging to this group will be reassigned to 'Default'.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            if self.profile_mgr and self.profile_mgr.delete_group(g_name):
                self.refresh_groups_list()

class FlowLayout(QLayout):
    """Standard Qt FlowLayout that arranges widgets horizontally and wraps to new lines."""
    def __init__(self, parent: Optional[QWidget] = None, margin: int = 0, spacing: int = 8) -> None:
        super().__init__(parent)
        if margin is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self.item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.item_list.append(item)

    def count(self) -> int:
        return len(self.item_list)

    def itemAt(self, index: int):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self._spacing

        for item in self.item_list:
            wid = item.widget()
            space_x = spacing
            space_y = spacing
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()


class ProfileFormTabs(QTabWidget):
    """Luxury ixBrowser-Style 4-Tab Drawer Form for configuring Platform Accounts, Proxies, Fingerprints, and Preferences."""

    def __init__(
        self,
        initial_data: Optional[Dict[str, Any]] = None,
        profile_mgr: Optional[Any] = None,
        is_edit: bool = False,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.data = initial_data.copy() if initial_data else {}
        self.profile_mgr = profile_mgr
        self.is_edit = is_edit
        self.selected_color = self.data.get("color", "#6366f1")

        # Set subtle, soft placeholder color palette so placeholders don't overwhelm the eye
        pal = self.palette()
        pal.setColor(QPalette.PlaceholderText, QColor("#525d73"))
        self.setPalette(pal)

        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1c2242;
                border-radius: 14px;
                background-color: #0b0e1b;
                padding: 10px 6px;
            }
            QTabBar::tab {
                background-color: #11152a;
                color: #94a3b8;
                border: 1px solid #1f274d;
                border-radius: 10px;
                padding: 8px 14px;
                margin-right: 6px;
                margin-bottom: 6px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QTabBar::tab:hover {
                background-color: #19203e;
                color: #ffffff;
                border-color: #3b82f6;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
                color: #ffffff;
                border: 1px solid #60a5fa;
                font-weight: 800;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background-color: #080a14;
                color: #f8fafc;
                border: 1px solid #1e2646;
                border-radius: 8px;
                padding: 6px 11px;
                font-size: 12px;
                font-weight: 500;
                placeholder-text-color: #525d73;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
                border: 1.5px solid #3b82f6;
                background-color: #0c1024;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QScrollBar:vertical {
                background: #0b0e1b;
                width: 6px;
                border-radius: 3px;
                margin: 4px 2px 4px 0px;
            }
            QScrollBar::handle:vertical {
                background: #232a4e;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3b82f6;
            }
        """)

        self._init_tabs()

    def _init_tabs(self) -> None:
        card_style = """
            QFrame {
                background-color: #101426;
                border: 1px solid #1e2646;
                border-radius: 12px;
            }
            QLabel {
                color: #94a3b8;
                background: transparent;
                border: none;
                font-size: 11.5px;
                font-weight: 700;
            }
        """

        # ==========================================
        # Tab 1: 📋 Account & Credentials
        # ==========================================
        tab_platform = QWidget()
        layout_platform = QVBoxLayout(tab_platform)
        layout_platform.setSpacing(8)
        layout_platform.setContentsMargins(6, 4, 6, 4)

        scroll_p1 = QScrollArea()
        scroll_p1.setWidgetResizable(True)
        scroll_p1.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_p1_content = QWidget()
        scroll_p1_content.setStyleSheet("background: transparent;")
        vbox_p1 = QVBoxLayout(scroll_p1_content)
        vbox_p1.setSpacing(8)
        vbox_p1.setContentsMargins(2, 2, 2, 2)

        # --- Card 1.1: Profile Identity & Grouping ---
        card_id = QFrame()
        card_id.setStyleSheet(card_style)
        card_id_vbox = QVBoxLayout(card_id)
        card_id_vbox.setContentsMargins(12, 10, 12, 10)
        card_id_vbox.setSpacing(8)

        lbl_hdr_id = QLabel("🏷️  <b>Profile Identity & Folder</b>")
        lbl_hdr_id.setStyleSheet("font-size: 12.5px; color: #38bdf8; font-weight: 800; border: none;")
        card_id_vbox.addWidget(lbl_hdr_id)

        form_id = QFormLayout()
        form_id.setSpacing(8)
        form_id.setLabelAlignment(Qt.AlignLeft)

        # Profile Name + Random Name Generator
        name_hbox = QHBoxLayout()
        name_hbox.setSpacing(8)
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Profile name (e.g. FB-01)")
        self.txt_name.setText(self.data.get("name", self.data.get("number", "")))
        btn_rnd_name = QPushButton("🎲 Random")
        btn_rnd_name.setCursor(Qt.PointingHandCursor)
        btn_rnd_name.setStyleSheet("background: #181f38; color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 8px; padding: 6px 12px; font-weight: bold; font-size: 11px;")
        def _gen_name():
            import random
            nicknames = ["Alpha", "Beta", "Gamma", "Nexus", "Vanguard", "Matrix", "Falcon", "Titan", "Specter", "Quantum", "Apex", "Nova"]
            self.txt_name.setText(f"{random.choice(nicknames)}-{random.randint(100, 999)}")
        btn_rnd_name.clicked.connect(_gen_name)
        name_hbox.addWidget(self.txt_name, stretch=1)
        name_hbox.addWidget(btn_rnd_name)

        # Select Group + Create Group
        group_hbox = QHBoxLayout()
        group_hbox.setSpacing(8)
        self.cmb_group = QComboBox()
        self._refresh_group_combo()
        btn_create_group = QPushButton("➕ Create Group")
        btn_create_group.setCursor(Qt.PointingHandCursor)
        btn_create_group.setStyleSheet("""
            QPushButton {
                background-color: #181f38;
                color: #fbbf24;
                border: 1px solid rgba(251, 191, 36, 0.45);
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #252e52;
                color: #fde68a;
                border-color: #fbbf24;
            }
        """)
        btn_create_group.clicked.connect(self._create_new_group)
        group_hbox.addWidget(self.cmb_group, stretch=1)
        group_hbox.addWidget(btn_create_group)

        # Start Page URL (Moved to Tab 1)
        self.txt_start_url = QLineEdit()
        self.txt_start_url.setPlaceholderText("https://... (optional)")
        self.txt_start_url.setText(str(self.data.get("start_url", "")))

        form_id.addRow("Profile Name:", name_hbox)
        form_id.addRow("Target Group:", group_hbox)
        form_id.addRow("Start Page URL:", self.txt_start_url)
        card_id_vbox.addLayout(form_id)
        vbox_p1.addWidget(card_id)

        # --- Card 1.2: Platform Security & Credentials ---
        card_sec = QFrame()
        card_sec.setStyleSheet(card_style)
        card_sec_vbox = QVBoxLayout(card_sec)
        card_sec_vbox.setContentsMargins(12, 10, 12, 10)
        card_sec_vbox.setSpacing(8)

        lbl_hdr_sec = QLabel("🔐  <b>Platform Login & Security Credentials</b>")
        lbl_hdr_sec.setStyleSheet("font-size: 12.5px; color: #818cf8; font-weight: 800; border: none;")
        card_sec_vbox.addWidget(lbl_hdr_sec)

        form_sec = QFormLayout()
        form_sec.setSpacing(8)
        form_sec.setLabelAlignment(Qt.AlignLeft)

        # Username / UID
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Username, Email or UID")
        self.txt_username.setText(str(self.data.get("uid") or self.data.get("fb_uid") or ""))

        # Password + Toggle Visibility
        pass_hbox = QHBoxLayout()
        pass_hbox.setSpacing(8)
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("Account password")
        self.txt_password.setText(str(self.data.get("password") or self.data.get("fb_pass") or ""))
        btn_toggle_pass = QPushButton("👁️")
        btn_toggle_pass.setCursor(Qt.PointingHandCursor)
        btn_toggle_pass.setFixedWidth(36)
        btn_toggle_pass.setStyleSheet("background: #181f38; color: #94a3b8; border: 1px solid #283359; border-radius: 8px; padding: 5px; font-size: 12px;")
        def _toggle_pass():
            if self.txt_password.echoMode() == QLineEdit.Password:
                self.txt_password.setEchoMode(QLineEdit.Normal)
            else:
                self.txt_password.setEchoMode(QLineEdit.Password)
        btn_toggle_pass.clicked.connect(_toggle_pass)
        pass_hbox.addWidget(self.txt_password, stretch=1)
        pass_hbox.addWidget(btn_toggle_pass)

        # 2FA Key
        self.txt_2fa = QLineEdit()
        self.txt_2fa.setPlaceholderText("2FA TOTP secret key (optional)")
        self.txt_2fa.setText(str(self.data.get("secret_2fa") or self.data.get("fb_2fa") or ""))

        # Security PIN
        self.txt_pin = QLineEdit()
        self.txt_pin.setPlaceholderText("4-digit PIN (optional)")
        self.txt_pin.setText(str(self.data.get("pin", "")))

        form_sec.addRow("UID / Username:", self.txt_username)
        form_sec.addRow("Login Password:", pass_hbox)
        form_sec.addRow("2FA Key (TOTP):", self.txt_2fa)
        form_sec.addRow("Security PIN:", self.txt_pin)
        card_sec_vbox.addLayout(form_sec)
        vbox_p1.addWidget(card_sec)

        # --- Card 1.3: Session Data & Recovery Notes ---
        card_notes = QFrame()
        card_notes.setStyleSheet(card_style)
        card_notes_vbox = QVBoxLayout(card_notes)
        card_notes_vbox.setContentsMargins(12, 10, 12, 10)
        card_notes_vbox.setSpacing(8)

        lbl_hdr_notes = QLabel("🍪  <b>Live Session Cookie & Custom Notes</b>")
        lbl_hdr_notes.setStyleSheet("font-size: 12.5px; color: #34d399; font-weight: 800; border: none;")
        card_notes_vbox.addWidget(lbl_hdr_notes)

        form_notes = QFormLayout()
        form_notes.setSpacing(8)
        form_notes.setLabelAlignment(Qt.AlignLeft)

        # Cookie Box - Compact Sleek Height
        self.txt_cookie = QTextEdit()
        self.txt_cookie.setPlaceholderText("JSON or Netscape cookies...")
        self.txt_cookie.setFixedHeight(38)
        self.txt_cookie.setText(str(self.data.get("cookie", "")))

        # Notes Box - Compact Sleek Height
        self.txt_notes_long = QTextEdit()
        self.txt_notes_long.setPlaceholderText("Custom notes, recovery info...")
        self.txt_notes_long.setFixedHeight(38)
        raw_notes = str(self.data.get("custom_notes") or self.data.get("notes") or "")
        self.txt_notes_long.setText(raw_notes)

        form_notes.addRow("Live Cookie:", self.txt_cookie)
        form_notes.addRow("Custom Notes:", self.txt_notes_long)
        card_notes_vbox.addLayout(form_notes)
        vbox_p1.addWidget(card_notes)

        scroll_p1.setWidget(scroll_p1_content)
        layout_platform.addWidget(scroll_p1)

        # ==========================================
        # Tab 2: 🛡️ Proxy Configuration
        # ==========================================
        tab_proxy = QWidget()
        layout_proxy_v = QVBoxLayout(tab_proxy)
        layout_proxy_v.setSpacing(8)
        layout_proxy_v.setContentsMargins(6, 6, 6, 6)

        scroll_p2 = QScrollArea()
        scroll_p2.setWidgetResizable(True)
        scroll_p2.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_p2_content = QWidget()
        scroll_p2_content.setStyleSheet("background: transparent;")
        vbox_p2 = QVBoxLayout(scroll_p2_content)
        vbox_p2.setSpacing(8)
        vbox_p2.setContentsMargins(2, 2, 2, 2)

        # --- Unified Compact Proxy Server & Authentication Card ---
        card_px = QFrame()
        card_px.setStyleSheet(card_style)
        card_px_vbox = QVBoxLayout(card_px)
        card_px_vbox.setContentsMargins(14, 12, 14, 12)
        card_px_vbox.setSpacing(10)

        lbl_hdr_px = QLabel("🛡️  <b>Proxy Server & Authentication Configuration</b>")
        lbl_hdr_px.setStyleSheet("font-size: 12.5px; color: #60a5fa; font-weight: 800; border: none;")
        card_px_vbox.addWidget(lbl_hdr_px)

        form_px = QFormLayout()
        form_px.setSpacing(9)
        form_px.setLabelAlignment(Qt.AlignLeft)

        self.cmb_proxy_type = QComboBox()
        self.cmb_proxy_type.addItems(["None", "HTTP", "HTTPS", "SOCKS5"])
        cur_px_t = str(self.data.get("proxy_type", "None")).upper()
        if cur_px_t in ["NONE", "DIRECT"]:
            self.cmb_proxy_type.setCurrentText("None")
        elif cur_px_t in ["HTTP", "HTTPS", "SOCKS5"]:
            self.cmb_proxy_type.setCurrentText(cur_px_t)
        else:
            self.cmb_proxy_type.setCurrentText("None")

        host_port_hbox = QHBoxLayout()
        host_port_hbox.setSpacing(8)
        self.txt_proxy_host = QLineEdit()
        self.txt_proxy_host.setPlaceholderText("IP or Hostname")
        self.txt_proxy_host.setText(str(self.data.get("proxy_host", "")))
        self.txt_proxy_port = QLineEdit()
        self.txt_proxy_port.setPlaceholderText("Port")
        self.txt_proxy_port.setFixedWidth(100)
        self.txt_proxy_port.setText(str(self.data.get("proxy_port", "")))
        host_port_hbox.addWidget(self.txt_proxy_host, stretch=1)
        host_port_hbox.addWidget(self.txt_proxy_port)

        auth_hbox = QHBoxLayout()
        auth_hbox.setSpacing(8)
        self.txt_proxy_user = QLineEdit()
        self.txt_proxy_user.setPlaceholderText("Proxy username (optional)")
        self.txt_proxy_user.setText(str(self.data.get("proxy_user", "")))

        self.txt_proxy_pass = QLineEdit()
        self.txt_proxy_pass.setEchoMode(QLineEdit.Password)
        self.txt_proxy_pass.setPlaceholderText("Proxy password (optional)")
        self.txt_proxy_pass.setText(str(self.data.get("proxy_pass", "")))
        auth_hbox.addWidget(self.txt_proxy_user, stretch=1)
        auth_hbox.addWidget(self.txt_proxy_pass, stretch=1)

        form_px.addRow("Proxy Protocol:", self.cmb_proxy_type)
        form_px.addRow("Server Host & Port:", host_port_hbox)
        form_px.addRow("Proxy Credentials:", auth_hbox)
        card_px_vbox.addLayout(form_px)

        test_px_box = QHBoxLayout()
        test_px_box.setSpacing(10)
        btn_test_px = QPushButton("⚡ Test Proxy Connection")
        btn_test_px.setCursor(Qt.PointingHandCursor)
        btn_test_px.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                border: 1px solid #34d399;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
            }
        """)
        self.lbl_proxy_status = QLabel("Proxy status: Not tested")
        self.lbl_proxy_status.setStyleSheet("color: #94a3b8; font-size: 11.5px; font-weight: 600; background: #080a14; border: 1px solid #1c2445; border-radius: 7px; padding: 6px 12px;")
        btn_test_px.clicked.connect(self._test_proxy_connection)
        test_px_box.addWidget(btn_test_px)
        test_px_box.addWidget(self.lbl_proxy_status, stretch=1)
        card_px_vbox.addSpacing(2)
        card_px_vbox.addLayout(test_px_box)

        vbox_p2.addWidget(card_px)
        vbox_p2.addStretch(1)

        scroll_p2.setWidget(scroll_p2_content)
        layout_proxy_v.addWidget(scroll_p2)

        # ==========================================
        # Tab 3: 🌐 Anti-Detect Fingerprint
        # ==========================================
        tab_fp = QWidget()
        layout_fp_v = QVBoxLayout(tab_fp)
        layout_fp_v.setSpacing(8)
        layout_fp_v.setContentsMargins(6, 6, 6, 6)

        scroll_p3 = QScrollArea()
        scroll_p3.setWidgetResizable(True)
        scroll_p3.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_p3_content = QWidget()
        scroll_p3_content.setStyleSheet("background: transparent;")
        vbox_p3 = QVBoxLayout(scroll_p3_content)
        vbox_p3.setSpacing(8)
        vbox_p3.setContentsMargins(2, 2, 2, 2)

        # --- Unified Compact Fingerprint & Hardware Engine Card ---
        card_fp = QFrame()
        card_fp.setStyleSheet(card_style)
        card_fp_vbox = QVBoxLayout(card_fp)
        card_fp_vbox.setContentsMargins(14, 12, 14, 12)
        card_fp_vbox.setSpacing(10)

        lbl_hdr_fp = QLabel("🌐  <b>Anti-Detect Fingerprint & Hardware Engine</b>")
        lbl_hdr_fp.setStyleSheet("font-size: 12.5px; color: #38bdf8; font-weight: 800; border: none;")
        card_fp_vbox.addWidget(lbl_hdr_fp)

        form_fp = QFormLayout()
        form_fp.setSpacing(9)
        form_fp.setLabelAlignment(Qt.AlignLeft)

        ua_hbox = QHBoxLayout()
        ua_hbox.setSpacing(8)
        self.txt_user_agent = QLineEdit()
        initial_ua = self.data.get("user_agent", "").strip()
        if not initial_ua:
            initial_ua = generate_random_user_agent()
        self.txt_user_agent.setText(initial_ua)
        btn_gen_ua = QPushButton("🔄 Auto-Gen UA")
        btn_gen_ua.setCursor(Qt.PointingHandCursor)
        btn_gen_ua.setStyleSheet("background: #181f38; color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.4); border-radius: 8px; padding: 6px 12px; font-weight: 700; font-size: 11px;")
        btn_gen_ua.clicked.connect(lambda: self.txt_user_agent.setText(generate_random_user_agent()))
        ua_hbox.addWidget(self.txt_user_agent, stretch=1)
        ua_hbox.addWidget(btn_gen_ua)

        self.cmb_language = QComboBox()
        lang_options = [
            ("English (United States) - en-US", "en-US"),
            ("Bengali (Bangladesh) - bn-BD", "bn-BD"),
            ("Hindi (India) - hi-IN", "hi-IN"),
            ("Spanish (Spain) - es-ES", "es-ES"),
            ("French (France) - fr-FR", "fr-FR"),
            ("German (Germany) - de-DE", "de-DE"),
            ("Portuguese (Brazil) - pt-BR", "pt-BR"),
            ("Arabic (Saudi Arabia) - ar-SA", "ar-SA"),
            ("Japanese (Japan) - ja-JP", "ja-JP"),
            ("Korean (South Korea) - ko-KR", "ko-KR"),
            ("Russian (Russia) - ru-RU", "ru-RU"),
            ("Turkish (Turkey) - tr-TR", "tr-TR"),
            ("Vietnamese (Vietnam) - vi-VN", "vi-VN"),
            ("Indonesian (Indonesia) - id-ID", "id-ID"),
            ("Thai (Thailand) - th-TH", "th-TH"),
            ("Chinese (Simplified) - zh-CN", "zh-CN")
        ]
        for name, code in lang_options:
            self.cmb_language.addItem(name, code)
        cur_lang = self.data.get("language", "en-US")
        idx_lang = self.cmb_language.findData(cur_lang)
        if idx_lang >= 0:
            self.cmb_language.setCurrentIndex(idx_lang)

        fp_hbox = QHBoxLayout()
        fp_hbox.setSpacing(12)
        self.spn_cpu_cores = QSpinBox()
        self.spn_cpu_cores.setRange(2, 32)
        self.spn_cpu_cores.setValue(int(self.data.get("cpu_cores", 8)))
        self.spn_cpu_cores.setSuffix(" Cores")

        self.spn_ram_gb = QSpinBox()
        self.spn_ram_gb.setRange(2, 64)
        self.spn_ram_gb.setValue(int(self.data.get("ram_gb", 16)))
        self.spn_ram_gb.setSuffix(" GB RAM")

        fp_hbox.addWidget(QLabel("CPU Cores:"))
        fp_hbox.addWidget(self.spn_cpu_cores)
        fp_hbox.addSpacing(10)
        fp_hbox.addWidget(QLabel("RAM Memory:"))
        fp_hbox.addWidget(self.spn_ram_gb)
        fp_hbox.addStretch(1)

        form_fp.addRow("Custom User-Agent:", ua_hbox)
        form_fp.addRow("Browser Language:", self.cmb_language)
        form_fp.addRow("Hardware Cores & RAM:", fp_hbox)
        card_fp_vbox.addLayout(form_fp)

        # Bottom Action / Spoof Status Bar
        bot_bar = QHBoxLayout()
        bot_bar.setSpacing(10)
        btn_random_fp = QPushButton("🎲 Randomize All Fingerprints")
        btn_random_fp.setCursor(Qt.PointingHandCursor)
        btn_random_fp.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #6366f1);
                color: #ffffff;
                border: 1px solid #a78bfa;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #4f46e5);
            }
        """)
        btn_random_fp.clicked.connect(self._randomize_fingerprint)

        lbl_spoof_status = QLabel("🛡️ Canvas, WebGL, Audio & Hardware noise spoofed")
        lbl_spoof_status.setStyleSheet("color: #a78bfa; font-size: 11.5px; font-weight: 600; background: #080a14; border: 1px solid #1c2445; border-radius: 7px; padding: 6px 12px;")

        bot_bar.addWidget(btn_random_fp)
        bot_bar.addWidget(lbl_spoof_status, stretch=1)
        card_fp_vbox.addSpacing(2)
        card_fp_vbox.addLayout(bot_bar)

        vbox_p3.addWidget(card_fp)
        vbox_p3.addStretch(1)

        scroll_p3.setWidget(scroll_p3_content)
        layout_fp_v.addWidget(scroll_p3)

        # ==========================================
        # Tab 4: 🧩 Chrome Extensions
        # ==========================================
        tab_ext = QWidget()
        layout_ext_v = QVBoxLayout(tab_ext)
        layout_ext_v.setSpacing(10)
        layout_ext_v.setContentsMargins(6, 6, 6, 6)

        scroll_ext = QScrollArea()
        scroll_ext.setWidgetResizable(True)
        scroll_ext.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_ext_content = QWidget()
        scroll_ext_content.setStyleSheet("background: transparent;")
        vbox_ext = QVBoxLayout(scroll_ext_content)
        vbox_ext.setSpacing(14)
        vbox_ext.setContentsMargins(2, 2, 2, 2)

        # --- Card 4: Chrome Extensions to Auto-Install (Flow Layout) ---
        card_ext = QFrame()
        card_ext.setStyleSheet(card_style)
        card_ext.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        card_ext_vbox = QVBoxLayout(card_ext)
        card_ext_vbox.setContentsMargins(14, 12, 14, 12)
        card_ext_vbox.setSpacing(12)

        ext_hdr = QHBoxLayout()
        lbl_ext_title = QLabel("🧩  <b>Chrome Extensions to Auto-Install:</b>")
        lbl_ext_title.setStyleSheet("font-weight: 800; color: #34d399; font-size: 12.5px; border: none;")
        btn_ext_all = QPushButton("Select All")
        btn_ext_all.setCursor(Qt.PointingHandCursor)
        btn_ext_all.setStyleSheet("background: #181f38; color: #34d399; border: 1px solid rgba(52, 211, 153, 0.4); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        btn_ext_none = QPushButton("Deselect All")
        btn_ext_none.setCursor(Qt.PointingHandCursor)
        btn_ext_none.setStyleSheet("background: #181f38; color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        ext_hdr.addWidget(lbl_ext_title)
        ext_hdr.addStretch()
        ext_hdr.addWidget(btn_ext_all)
        ext_hdr.addWidget(btn_ext_none)
        card_ext_vbox.addLayout(ext_hdr)

        self.ext_checkboxes = []
        cur_exts = self.data.get("extensions") or []
        if isinstance(cur_exts, str):
            cur_exts = [cur_exts]

        all_global_exts = []
        try:
            from extension_manager import ExtensionManager
            em = ExtensionManager()
            all_global_exts = [e for e in em.get_all_extensions() if e.get("is_active", True)]
        except Exception:
            all_global_exts = []

        if all_global_exts:
            ext_flow_container = QWidget()
            ext_flow_container.setStyleSheet("background: transparent; border: none;")
            ext_flow = FlowLayout(ext_flow_container, margin=0, spacing=10)

            for ext in all_global_exts:
                ename = ext.get("name", "Extension")
                epath = ext.get("path", "")
                btn_chip = QPushButton(f"🧩  {ename}")
                btn_chip.setToolTip(ename)
                btn_chip.setCheckable(True)
                btn_chip.setChecked(epath in cur_exts or any(ename.lower() in str(x).lower() for x in cur_exts))
                btn_chip.setCursor(Qt.PointingHandCursor)
                btn_chip.setStyleSheet("""
                    QPushButton {
                        color: #94a3b8;
                        font-size: 12px;
                        font-weight: 700;
                        padding: 7px 16px;
                        background-color: #080a14;
                        border: 1.5px solid #1f274d;
                        border-radius: 16px;
                        text-align: center;
                    }
                    QPushButton:hover {
                        border-color: #34d399;
                        background-color: #131d30;
                        color: #ffffff;
                    }
                    QPushButton:checked {
                        color: #34d399;
                        border-color: #10b981;
                        background-color: rgba(16, 185, 129, 0.18);
                        font-weight: 800;
                    }
                """)
                self.ext_checkboxes.append((epath, btn_chip))
                ext_flow.addWidget(btn_chip)

            card_ext_vbox.addWidget(ext_flow_container)
        else:
            lbl_no_ext = QLabel("No active extensions enabled. Enable extensions via Extension Manager.")
            lbl_no_ext.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 4px;")
            card_ext_vbox.addWidget(lbl_no_ext)

        btn_ext_all.clicked.connect(lambda: [chk.setChecked(True) for _, chk in self.ext_checkboxes])
        btn_ext_none.clicked.connect(lambda: [chk.setChecked(False) for _, chk in self.ext_checkboxes])
        vbox_ext.addWidget(card_ext)
        vbox_ext.addStretch(1)

        scroll_ext.setWidget(scroll_ext_content)
        layout_ext_v.addWidget(scroll_ext)

        # ==========================================
        # Tab 5: 📜 Automation & Action Scripts
        # ==========================================
        tab_sc = QWidget()
        layout_sc_v = QVBoxLayout(tab_sc)
        layout_sc_v.setSpacing(10)
        layout_sc_v.setContentsMargins(6, 6, 6, 6)

        scroll_sc = QScrollArea()
        scroll_sc.setWidgetResizable(True)
        scroll_sc.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_sc_content = QWidget()
        scroll_sc_content.setStyleSheet("background: transparent;")
        vbox_sc = QVBoxLayout(scroll_sc_content)
        vbox_sc.setSpacing(14)
        vbox_sc.setContentsMargins(2, 2, 2, 2)

        # --- Card 5: Quick Action Shortcuts & Buttons on Card (Flow Layout) ---
        card_sc = QFrame()
        card_sc.setStyleSheet(card_style)
        card_sc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        card_sc_vbox = QVBoxLayout(card_sc)
        card_sc_vbox.setContentsMargins(14, 12, 14, 12)
        card_sc_vbox.setSpacing(12)

        sc_hdr = QHBoxLayout()
        lbl_sc_title = QLabel("📜  <b>Quick Action Shortcuts & Buttons on Card:</b>")
        lbl_sc_title.setStyleSheet("font-weight: 800; color: #818cf8; font-size: 12.5px; border: none;")
        btn_sc_all = QPushButton("Select All")
        btn_sc_all.setCursor(Qt.PointingHandCursor)
        btn_sc_all.setStyleSheet("background: #181f38; color: #818cf8; border: 1px solid rgba(129, 140, 248, 0.4); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        btn_sc_none = QPushButton("Deselect All")
        btn_sc_none.setCursor(Qt.PointingHandCursor)
        btn_sc_none.setStyleSheet("background: #181f38; color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        sc_hdr.addWidget(lbl_sc_title)
        sc_hdr.addStretch()
        sc_hdr.addWidget(btn_sc_all)
        sc_hdr.addWidget(btn_sc_none)
        card_sc_vbox.addLayout(sc_hdr)

        self.script_checkboxes = []
        cur_scripts = self.data.get("assigned_scripts")
        if cur_scripts is None:
            cur_scripts = []
            if bool(self.data.get("fb_uid")) or bool(self.data.get("uid")) or bool(self.data.get("notes")):
                cur_scripts.append("fb_account_info")
            if (bool(self.data.get("fb_uid")) or bool(self.data.get("uid"))) and (bool(self.data.get("fb_pass")) or bool(self.data.get("password"))):
                cur_scripts.append("fb_relogin")
        elif isinstance(cur_scripts, str):
            cur_scripts = [cur_scripts]

        available_scripts = [
            {"id": "fb_account_info", "name": "FB Info", "icon": "ℹ️", "color": "#38bdf8", "bg": "rgba(56, 189, 248, 0.18)", "desc": "View credentials, notes & live cookies on card"},
            {"id": "fb_relogin", "name": "FB-Relogin", "icon": "🔑", "color": "#fbbf24", "bg": "rgba(251, 191, 36, 0.18)", "desc": "1-Click automated background account re-login"},
            {"id": "fb_quick_page_create", "name": "Page Create", "icon": "📄", "color": "#c084fc", "bg": "rgba(192, 132, 252, 0.18)", "desc": "1-Click instant Facebook page creator studio"},
            {"id": "fb_language_converter", "name": "FB-Language", "icon": "🌐", "color": "#34d399", "bg": "rgba(52, 211, 153, 0.18)", "desc": "1-Click fast Facebook language converter"},
            {"id": "fb_business_creator", "name": "FBBM", "icon": "⚡", "color": "#38bdf8", "bg": "rgba(56, 189, 248, 0.18)", "desc": "1-Click instant Facebook Business Manager creator"},
            {"id": "fb_bulk_video_uploader", "name": "FBVUP", "icon": "🎬", "color": "#ec4899", "bg": "rgba(236, 72, 153, 0.18)", "desc": "1-Click automated Facebook bulk video uploader"}
        ]

        try:
            from bot_license_manager import BotLicenseManager
            blm_inst = BotLicenseManager()
            available_scripts = [sc for sc in available_scripts if not blm_inst.is_item_deactivated("script", sc["id"])]
        except Exception:
            pass

        if available_scripts:
            sc_flow_container = QWidget()
            sc_flow_container.setStyleSheet("background: transparent; border: none;")
            sc_flow = FlowLayout(sc_flow_container, margin=0, spacing=10)

            for sc_item in available_scripts:
                sid = sc_item["id"]
                sname = sc_item["name"]
                sicon = sc_item.get("icon", "⚡")
                scolor = sc_item.get("color", "#818cf8")
                sbg = sc_item.get("bg", "rgba(129, 140, 248, 0.18)")
                sdesc = sc_item["desc"]

                btn_chip = QPushButton(f"{sicon}  {sname}")
                btn_chip.setToolTip(sdesc)
                btn_chip.setCheckable(True)
                btn_chip.setChecked(sid in cur_scripts or any(sid in str(x) for x in cur_scripts))
                btn_chip.setCursor(Qt.PointingHandCursor)
                btn_chip.setStyleSheet(f"""
                    QPushButton {{
                        color: #94a3b8;
                        font-size: 12px;
                        font-weight: 700;
                        padding: 7px 16px;
                        background-color: #080a14;
                        border: 1.5px solid #1f274d;
                        border-radius: 16px;
                        text-align: center;
                    }}
                    QPushButton:hover {{
                        border-color: {scolor};
                        background-color: #141b32;
                        color: #ffffff;
                    }}
                    QPushButton:checked {{
                        color: {scolor};
                        border-color: {scolor};
                        background-color: {sbg};
                        font-weight: 800;
                    }}
                """)
                self.script_checkboxes.append((sid, btn_chip))
                sc_flow.addWidget(btn_chip)

            card_sc_vbox.addWidget(sc_flow_container)
        else:
            lbl_no_sc = QLabel("No active scripts enabled. Enable scripts via Scripts Manager.")
            lbl_no_sc.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 4px;")
            card_sc_vbox.addWidget(lbl_no_sc)

        btn_sc_all.clicked.connect(lambda: [chk.setChecked(True) for _, chk in self.script_checkboxes])
        btn_sc_none.clicked.connect(lambda: [chk.setChecked(False) for _, chk in self.script_checkboxes])
        vbox_sc.addWidget(card_sc)
        vbox_sc.addStretch(1)

        scroll_sc.setWidget(scroll_sc_content)
        layout_sc_v.addWidget(scroll_sc)

        # ==========================================
        # Tab 6: 🔖 Bookmarks
        # ==========================================
        tab_bm = QWidget()
        layout_bm_v = QVBoxLayout(tab_bm)
        layout_bm_v.setSpacing(10)
        layout_bm_v.setContentsMargins(6, 6, 6, 6)

        scroll_bm = QScrollArea()
        scroll_bm.setWidgetResizable(True)
        scroll_bm.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_bm_content = QWidget()
        scroll_bm_content.setStyleSheet("background: transparent;")
        vbox_bm = QVBoxLayout(scroll_bm_content)
        vbox_bm.setSpacing(14)
        vbox_bm.setContentsMargins(2, 2, 2, 2)

        # --- Card 6: Bookmarks to Auto-Import (Flow Layout) ---
        card_bm = QFrame()
        card_bm.setStyleSheet(card_style)
        card_bm.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.card_bm_vbox = QVBoxLayout(card_bm)
        self.card_bm_vbox.setContentsMargins(14, 12, 14, 12)
        self.card_bm_vbox.setSpacing(12)

        bm_hdr = QHBoxLayout()
        lbl_bm_title = QLabel("🔖  <b>Bookmarks to Auto-Import / Attach:</b>")
        lbl_bm_title.setStyleSheet("font-weight: 800; color: #f59e0b; font-size: 12.5px; border: none;")
        
        btn_add_bm = QPushButton("➕ Add Bookmark")
        btn_add_bm.setCursor(Qt.PointingHandCursor)
        btn_add_bm.setStyleSheet("background: #181f38; color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.4); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        btn_add_bm.clicked.connect(self.on_add_new_bookmark)

        btn_bm_all = QPushButton("Select All")
        btn_bm_all.setCursor(Qt.PointingHandCursor)
        btn_bm_all.setStyleSheet("background: #181f38; color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        btn_bm_all.clicked.connect(lambda: [chk.setChecked(True) for _, chk in self.bookmark_checkboxes])

        btn_bm_none = QPushButton("Deselect All")
        btn_bm_none.setCursor(Qt.PointingHandCursor)
        btn_bm_none.setStyleSheet("background: #181f38; color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        btn_bm_none.clicked.connect(lambda: [chk.setChecked(False) for _, chk in self.bookmark_checkboxes])

        bm_hdr.addWidget(lbl_bm_title)
        bm_hdr.addStretch()
        bm_hdr.addWidget(btn_add_bm)
        bm_hdr.addWidget(btn_bm_all)
        bm_hdr.addWidget(btn_bm_none)
        self.card_bm_vbox.addLayout(bm_hdr)

        self.bookmark_checkboxes = []
        self.bm_flow_container = QWidget()
        self.bm_flow_container.setStyleSheet("background: transparent; border: none;")
        self.card_bm_vbox.addWidget(self.bm_flow_container)
        self._reload_profile_bookmarks()

        vbox_bm.addWidget(card_bm)
        vbox_bm.addStretch(1)

        scroll_bm.setWidget(scroll_bm_content)
        layout_bm_v.addWidget(scroll_bm)

        # Add 6 ixBrowser Tabs
        self.addTab(tab_platform, "👤 Account")
        self.addTab(tab_proxy, "🛡️ Proxy")
        self.addTab(tab_fp, "🌐 Fingerprint")
        self.addTab(tab_ext, "🧩 Extensions")
        self.addTab(tab_sc, "📜 Scripts")
        self.addTab(tab_bm, "🔖 Bookmarks")

    def _test_proxy_connection(self) -> None:
        ptype = self.cmb_proxy_type.currentText().strip()
        if ptype.lower() == "none":
            self.lbl_proxy_status.setText("ℹ️ Direct connection (No proxy)")
            self.lbl_proxy_status.setStyleSheet("color: #94a3b8; font-weight: bold;")
            return
        host = self.txt_proxy_host.text().strip()
        port = self.txt_proxy_port.text().strip()
        user = self.txt_proxy_user.text().strip()
        pwd = self.txt_proxy_pass.text().strip()
        if not host or not port:
            self.lbl_proxy_status.setText("⚠️ Please enter proxy Host and Port")
            self.lbl_proxy_status.setStyleSheet("color: #fbbf24; font-weight: bold;")
            return

        self.lbl_proxy_status.setText("⏳ Testing connection...")
        self.lbl_proxy_status.setStyleSheet("color: #818cf8; font-weight: bold;")

        import threading
        def _run():
            try:
                import urllib.request, time, json
                proxy_str = f"{ptype.lower()}://"
                if user and pwd:
                    proxy_str += f"{user}:{pwd}@"
                proxy_str += f"{host}:{port}"
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy_str, 'https': proxy_str}))
                t0 = time.time()
                req = urllib.request.Request("http://ip-api.com/json", headers={"User-Agent": "srkBrowser/1.0"})
                resp = opener.open(req, timeout=7)
                lat = int((time.time() - t0) * 1000)
                data = json.loads(resp.read().decode())
                ip = data.get("query", host)
                country = data.get("country", "")
                self.lbl_proxy_status.setText(f"🟢 Connected! IP: {ip} ({country}) Ping: {lat}ms")
                self.lbl_proxy_status.setStyleSheet("color: #10b981; font-weight: bold;")
            except Exception as e:
                self.lbl_proxy_status.setText(f"🔴 Connection Failed: {str(e)[:35]}")
                self.lbl_proxy_status.setStyleSheet("color: #ef4444; font-weight: bold;")
        threading.Thread(target=_run, daemon=True).start()

    def _refresh_group_combo(self) -> None:
        current = self.cmb_group.currentText() if hasattr(self, "cmb_group") else self.data.get("group", "Default")
        self.cmb_group.clear()

        groups = self.profile_mgr.get_groups() if self.profile_mgr else ["Default"]
        self.cmb_group.addItems(groups)

        if current and current in groups:
            self.cmb_group.setCurrentText(current)
        elif current:
            self.cmb_group.addItem(current)
            self.cmb_group.setCurrentText(current)

    def _create_new_group(self) -> None:
        top_w = self.window() if hasattr(self, "window") and self.window() else self
        dlg = QuickCreateGroupDialog(top_w)
        if dlg.exec() == QDialog.Accepted:
            g_name = dlg.get_group_name()
            if g_name and self.profile_mgr:
                self.profile_mgr.add_group(g_name)
                self._refresh_group_combo()
                self.cmb_group.setCurrentText(g_name)

    def _open_group_manager(self) -> None:
        if self.profile_mgr:
            top_w = self.window() if hasattr(self, "window") and self.window() else self
            dlg = GroupManagerDialog(self.profile_mgr, top_w)
            dlg.exec()
            self._refresh_group_combo()

    def _randomize_fingerprint(self) -> None:
        from utils import generate_random_profile_fingerprint
        fp = generate_random_profile_fingerprint()
        self.txt_user_agent.setText(fp["user_agent"])
        self.spn_cpu_cores.setValue(fp["cpu_cores"])
        self.spn_ram_gb.setValue(fp["ram_gb"])

    def on_add_new_bookmark(self) -> None:
        try:
            from bookmark_manager import BookmarkManager
            bm_mgr = BookmarkManager()
        except Exception:
            bm_mgr = None
        if not bm_mgr:
            return

        groups = ["Default"]
        if self.profile_mgr:
            try:
                groups = self.profile_mgr.get_groups()
            except Exception:
                pass
        dlg = AddEditBookmarkDialog("", "", "all", [], groups, self, hide_target_scope=True)
        if dlg.exec() == QDialog.Accepted:
            name, url, mode, sel_grps = dlg.get_data()
            if name and url:
                bm_mgr.add_bookmark(name, url, target_mode=mode, target_groups=sel_grps)
                self._reload_profile_bookmarks(auto_check_new=name)

    def _reload_profile_bookmarks(self, auto_check_new: Optional[str] = None) -> None:
        # Collect currently checked bookmark URLs before clearing
        checked_urls = set()
        for bm_dict, chk in getattr(self, "bookmark_checkboxes", []):
            if chk.isChecked():
                checked_urls.add(bm_dict.get("url", "").lower().rstrip("/"))
        if not checked_urls:
            cur_bms = self.data.get("bookmarks") or []
            for b in cur_bms:
                if isinstance(b, dict):
                    checked_urls.add(b.get("url", "").lower().rstrip("/"))
                elif isinstance(b, str):
                    checked_urls.add(b.lower().rstrip("/"))

        if self.bm_flow_container.layout():
            bm_lay = self.bm_flow_container.layout()
            while bm_lay.count():
                item = bm_lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            bm_lay = FlowLayout(self.bm_flow_container, margin=0, spacing=10)

        self.bookmark_checkboxes = []
        all_global_bms = []
        try:
            from bookmark_manager import BookmarkManager
            bm_mgr = BookmarkManager()
            all_global_bms = bm_mgr.get_all_bookmarks()
        except Exception:
            all_global_bms = []

        if all_global_bms:
            for bm in all_global_bms:
                b_name = bm.get("name", "Bookmark")
                b_url = bm.get("url", "")
                norm_u = b_url.lower().rstrip("/")
                btn_chip = QPushButton(f"🔖  {b_name}")
                btn_chip.setToolTip(f"{b_name}\n{b_url}")
                btn_chip.setCheckable(True)
                is_chk = (norm_u in checked_urls)
                if auto_check_new and b_name.lower() == auto_check_new.lower():
                    is_chk = True
                btn_chip.setChecked(is_chk)
                btn_chip.setCursor(Qt.PointingHandCursor)
                btn_chip.setStyleSheet("""
                    QPushButton {
                        color: #94a3b8;
                        font-size: 12px;
                        font-weight: 700;
                        padding: 7px 16px;
                        background-color: #080a14;
                        border: 1.5px solid #1f274d;
                        border-radius: 16px;
                        text-align: center;
                    }
                    QPushButton:hover {
                        border-color: #f59e0b;
                        background-color: #1a1710;
                        color: #ffffff;
                    }
                    QPushButton:checked {
                        color: #f59e0b;
                        border-color: #d97706;
                        background-color: rgba(245, 158, 11, 0.18);
                        font-weight: 800;
                    }
                """)
                self.bookmark_checkboxes.append((bm, btn_chip))
                bm_lay.addWidget(btn_chip)
        else:
            lbl_no_bm = QLabel("No bookmarks currently saved. Click '+ Add Bookmark' to create one.")
            lbl_no_bm.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 4px;")
            bm_lay.addWidget(lbl_no_bm)

    def get_data(self) -> Dict[str, Any]:
        # Collect checked extensions
        selected_exts = []
        if hasattr(self, "ext_checkboxes"):
            for e_path, chk in self.ext_checkboxes:
                if chk.isChecked():
                    selected_exts.append(e_path)

        # Collect checked scripts
        selected_scripts = []
        if hasattr(self, "script_checkboxes"):
            for s_id, chk in self.script_checkboxes:
                if chk.isChecked():
                    selected_scripts.append(s_id)

        # Collect checked bookmarks
        selected_bms = []
        if hasattr(self, "bookmark_checkboxes"):
            for bm_dict, chk in self.bookmark_checkboxes:
                if chk.isChecked():
                    selected_bms.append(bm_dict)

        uid_val = self.txt_username.text().strip()
        pass_val = self.txt_password.text().strip()
        two_fa_val = self.txt_2fa.text().strip()
        custom_notes = self.txt_notes_long.toPlainText().strip()

        clean_notes_parts = []
        if uid_val:
            clean_notes_parts.append(f"FB UID: {uid_val}")
        if pass_val:
            clean_notes_parts.append(f"Pass: {pass_val}")
        if two_fa_val and two_fa_val.lower() not in ("none", "n/a", "null"):
            clean_notes_parts.append(f"2FA: {two_fa_val}")
        if custom_notes:
            clean_notes_parts.append(custom_notes)

        return {
            "name": self.txt_name.text().strip(),
            "group": self.cmb_group.currentText().strip(),
            "platform": self.data.get("platform", "Facebook"),
            "notes": "\n".join(clean_notes_parts).strip(),
            "custom_notes": custom_notes,
            "pin": self.txt_pin.text().strip(),
            "uid": uid_val,
            "fb_uid": uid_val,
            "password": pass_val,
            "fb_pass": pass_val,
            "secret_2fa": two_fa_val,
            "fb_2fa": two_fa_val,
            "cookie": self.txt_cookie.toPlainText().strip(),
            "proxy_type": self.cmb_proxy_type.currentText(),
            "proxy_host": self.txt_proxy_host.text().strip(),
            "proxy_port": self.txt_proxy_port.text().strip(),
            "proxy_user": self.txt_proxy_user.text().strip(),
            "proxy_pass": self.txt_proxy_pass.text().strip(),
            "start_url": self.txt_start_url.text().strip(),
            "language": self.cmb_language.currentData() or "en-US",
            "user_agent": self.txt_user_agent.text().strip(),
            "cpu_cores": self.spn_cpu_cores.value(),
            "ram_gb": self.spn_ram_gb.value(),
            "screen_resolution": self.data.get("screen_resolution", "1920x1080"),
            "extensions": selected_exts,
            "assigned_scripts": selected_scripts,
            "bookmarks": selected_bms,
            "color": self.selected_color
        }


class CreateProfileDialog(QDialog):
    """Luxury ixBrowser-Style Right-Docked Drawer Dialog for creating new profiles."""

    def __init__(self, default_number: str, profile_mgr: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New Browser Profile")
        self.default_number = default_number
        self.profile_mgr = profile_mgr

        # Right Docking Dimensions
        self.setMinimumSize(740, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0e17;
                color: #f1f5f9;
                border-left: 2px solid #232742;
            }
        """)

        if parent:
            p_geo = parent.geometry()
            drawer_w = min(800, max(740, int(p_geo.width() * 0.58)))
            drawer_h = max(680, p_geo.height())
            self.setGeometry(p_geo.right() - drawer_w, p_geo.top(), drawer_w, drawer_h)
        else:
            self.resize(780, 820)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 14, 18, 14)

        # 1. Top Breadcrumbs Header + Close [✕]
        hdr_box = QHBoxLayout()
        hdr_box.setSpacing(8)

        lbl_bread = QLabel(f"Dashboard  /  Browser Profile  /  <span style='color: #60a5fa; font-weight: 800;'>Create Profile ({self.default_number})</span>")
        lbl_bread.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        
        btn_close = QPushButton("✕")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #181d33;
                color: #94a3b8;
                border: 1px solid #232845;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
                border-color: #dc2626;
            }
        """)
        btn_close.clicked.connect(self.reject)

        hdr_box.addWidget(lbl_bread)
        hdr_box.addStretch()
        hdr_box.addWidget(btn_close)
        layout.addLayout(hdr_box)

        # 2. Main 4-Tab Form
        self.form_tabs = ProfileFormTabs(
            initial_data={"name": self.default_number, "number": self.default_number, "group": "Default"},
            profile_mgr=self.profile_mgr,
            parent=self
        )
        layout.addWidget(self.form_tabs)

        # 3. Fixed Bottom Action Bar (ixBrowser Style)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(4, 4, 4, 2)
        btn_layout.setSpacing(12)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #141729;
                color: #94a3b8;
                border: 1px solid #232845;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1e233d;
                color: #ffffff;
                border-color: #3b82f6;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_reset = QPushButton("🔄 Reset")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #141729;
                color: #cbd5e1;
                border: 1px solid #232845;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1e233d;
                color: #ffffff;
            }
        """)
        def _on_reset():
            self.form_tabs.txt_name.setText(self.default_number)
            self.form_tabs.txt_username.clear()
            self.form_tabs.txt_password.clear()
            self.form_tabs.txt_2fa.clear()
            self.form_tabs.txt_cookie.clear()
            self.form_tabs.txt_notes_long.clear()
        btn_reset.clicked.connect(_on_reset)

        btn_next = QPushButton("Next Step ➡️")
        btn_next.setCursor(Qt.PointingHandCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1a2038;
                color: #60a5fa;
                border: 1px solid rgba(96, 165, 250, 0.4);
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #242c4c;
                color: #93c5fd;
            }
        """)
        def _on_next():
            curr = self.form_tabs.currentIndex()
            if curr < self.form_tabs.count() - 1:
                self.form_tabs.setCurrentIndex(curr + 1)
        btn_next.clicked.connect(_on_next)

        btn_create = QPushButton("🚀 Create Profile Now")
        btn_create.setCursor(Qt.PointingHandCursor)
        btn_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                color: #ffffff;
                border: 1px solid #60a5fa;
                border-radius: 8px;
                padding: 9px 28px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                border-color: #93c5fd;
            }
        """)
        btn_create.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_next)
        btn_layout.addWidget(btn_create)
        layout.addLayout(btn_layout)

    def get_data(self) -> Dict[str, Any]:
        return self.form_tabs.get_data()


class EditProfileDialog(QDialog):
    """Luxury ixBrowser-Style Right-Docked Drawer Dialog for editing existing profile configurations."""

    def __init__(self, profile_data: Dict[str, Any], profile_mgr: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Profile - {profile_data.get('number', 'Profile')}")
        self.profile_data = profile_data
        self.profile_mgr = profile_mgr

        # Right Docking Dimensions
        self.setMinimumSize(740, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0e17;
                color: #f1f5f9;
                border-left: 2px solid #232742;
            }
        """)

        if parent:
            p_geo = parent.geometry()
            drawer_w = min(800, max(740, int(p_geo.width() * 0.58)))
            drawer_h = max(680, p_geo.height())
            self.setGeometry(p_geo.right() - drawer_w, p_geo.top(), drawer_w, drawer_h)
        else:
            self.resize(780, 820)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 14, 18, 14)

        p_num = self.profile_data.get('number', '')

        # 1. Top Breadcrumbs Header + Close [✕]
        hdr_box = QHBoxLayout()
        hdr_box.setSpacing(8)

        lbl_bread = QLabel(f"Dashboard  /  Browser Profile  /  <span style='color: #60a5fa; font-weight: 800;'>Edit Settings (Profile #{p_num})</span>")
        lbl_bread.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        
        btn_close = QPushButton("✕")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #181d33;
                color: #94a3b8;
                border: 1px solid #232845;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
                border-color: #dc2626;
            }
        """)
        btn_close.clicked.connect(self.reject)

        hdr_box.addWidget(lbl_bread)
        hdr_box.addStretch()
        hdr_box.addWidget(btn_close)
        layout.addLayout(hdr_box)

        # 2. Main 4-Tab Form
        self.form_tabs = ProfileFormTabs(
            initial_data=self.profile_data,
            profile_mgr=self.profile_mgr,
            is_edit=True,
            parent=self
        )
        layout.addWidget(self.form_tabs)

        # 3. Fixed Bottom Action Bar (ixBrowser Style)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(4, 4, 4, 2)
        btn_layout.setSpacing(12)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #141729;
                color: #94a3b8;
                border: 1px solid #232845;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1e233d;
                color: #ffffff;
                border-color: #3b82f6;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_next = QPushButton("Next Step ➡️")
        btn_next.setCursor(Qt.PointingHandCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1a2038;
                color: #60a5fa;
                border: 1px solid rgba(96, 165, 250, 0.4);
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #242c4c;
                color: #93c5fd;
            }
        """)
        def _on_next():
            curr = self.form_tabs.currentIndex()
            if curr < self.form_tabs.count() - 1:
                self.form_tabs.setCurrentIndex(curr + 1)
        btn_next.clicked.connect(_on_next)

        btn_save = QPushButton("💾 Save Changes")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                color: #ffffff;
                border: 1px solid #60a5fa;
                border-radius: 8px;
                padding: 9px 28px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                border-color: #93c5fd;
            }
        """)
        btn_save.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_next)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def get_data(self) -> Dict[str, Any]:
        return self.form_tabs.get_data()


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, current_settings: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(540)
        self.settings_data = current_settings.copy()

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        browser_layout = QHBoxLayout()
        self.txt_browser_path = QLineEdit()
        self.txt_browser_path.setText(self.settings_data.get("browser_path", ""))
        self.txt_browser_path.setPlaceholderText("Path to chrome.exe, msedge.exe, brave.exe...")

        btn_browse = QPushButton("Browse...")
        btn_browse.setObjectName("SecondaryButton")
        btn_browse.clicked.connect(self._browse_browser_path)

        btn_autodetect = QPushButton("Auto-Detect")
        btn_autodetect.setObjectName("SecondaryButton")
        btn_autodetect.clicked.connect(self._autodetect_browser)

        browser_layout.addWidget(self.txt_browser_path)
        browser_layout.addWidget(btn_browse)
        browser_layout.addWidget(btn_autodetect)

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["Dark", "Light (Default Dark recommended)"])

        size_layout = QHBoxLayout()
        self.spn_width = QSpinBox()
        self.spn_width.setRange(800, 3840)
        self.spn_width.setValue(self.settings_data.get("default_window_width", 1240))

        self.spn_height = QSpinBox()
        self.spn_height.setRange(600, 2160)
        self.spn_height.setValue(self.settings_data.get("default_window_height", 820))

        size_layout.addWidget(QLabel("Width:"))
        size_layout.addWidget(self.spn_width)
        size_layout.addWidget(QLabel("Height:"))
        size_layout.addWidget(self.spn_height)

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["English"])

        self.cmb_browser_window_size = QComboBox()
        sizes = ["1280x800 (Default)", "1366x768", "1920x1080", "1600x900", "1440x900", "1024x768"]
        self.cmb_browser_window_size.addItems(sizes)
        current_b_size = self.settings_data.get("browser_window_size", "1280x800")
        for i, s in enumerate(sizes):
            if s.startswith(current_b_size):
                self.cmb_browser_window_size.setCurrentIndex(i)
                break

        form_layout.addRow("Browser Executable:", browser_layout)
        form_layout.addRow("Browser Window Size:", self.cmb_browser_window_size)
        form_layout.addRow("UI Theme:", self.cmb_theme)
        form_layout.addRow("App Window Size:", size_layout)
        form_layout.addRow("Language:", self.cmb_lang)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self.accept)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)

        layout.addLayout(form_layout)
        layout.addLayout(btn_layout)

    def _browse_browser_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Browser Executable",
            "C:\\Program Files",
            "Executables (*.exe);;All Files (*.*)"
        )
        if path:
            self.txt_browser_path.setText(path)

    def _autodetect_browser(self) -> None:
        detected = get_system_browsers()
        if detected:
            first_name, first_path = next(iter(detected.items()))
            self.txt_browser_path.setText(first_path)
            QMessageBox.information(
                self,
                "Browser Detected",
                f"Auto-detected {first_name}:\n{first_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "No Browser Detected",
                "Could not automatically detect installed Chrome, Edge, or Brave executables. Please browse manually."
            )

    def get_settings(self) -> Dict[str, Any]:
        self.settings_data["browser_path"] = self.txt_browser_path.text().strip()
        self.settings_data["browser_window_size"] = self.cmb_browser_window_size.currentText().split(" ")[0]
        self.settings_data["theme"] = "Dark"
        self.settings_data["default_window_width"] = self.spn_width.value()
        self.settings_data["default_window_height"] = self.spn_height.value()
        self.settings_data["language"] = self.cmb_lang.currentText()
        return self.settings_data


class AboutDialog(QDialog):
    """Information modal dialog about the application."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(440)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title_label = QLabel(f"{APP_NAME} v{APP_VERSION}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa;")

        dev_label = QLabel(
            "<b>Developed with ❤️ by SRK Shofiqul</b><br/>"
            "🌐 Website: <a href='https://srbrowser.com' style='color:#89b4fa;'>srbrowser.com</a><br/>"
            "✈️ Telegram: <a href='https://t.me/srkplatforms' style='color:#a6e3a1;'>@srkplatforms</a>"
        )
        dev_label.setOpenExternalLinks(True)
        dev_label.setStyleSheet("color: #cdd6f4; font-size: 13px; background: #1e1e2e; padding: 10px; border-radius: 8px;")

        desc_label = QLabel(
            "Browser Profile Manager is a modern desktop automation suite for managing isolated "
            "browser profiles, automated Facebook publishing, profile warmup, reels commenting, and story uploading."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #a6adc8; font-size: 12px; line-height: 1.4;")

        btn_close = QPushButton("Close")
        btn_close.setObjectName("SecondaryButton")
        btn_close.clicked.connect(self.accept)

        layout.addWidget(title_label)
        layout.addWidget(dev_label)
        layout.addWidget(desc_label)
        layout.addWidget(btn_close)



class LicenseActivationDialog(QDialog):
    """
    Ultra-Luxury Dark Obsidian Activation Dialog prompted to software buyers requiring valid HWID License Key.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from license_manager import get_hardware_id
        self.hwid = get_hardware_id()
        self.activated = False

        self.setWindowTitle(f"🔒 Software License Activation - {APP_NAME}")
        self.setFixedWidth(520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QLineEdit {
                background-color: #10121e;
                color: #f1f5f9;
                border: 1.5px solid #232742;
                border-radius: 8px;
                padding: 9px 12px;
                font-size: 13px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:focus {
                border-color: #6366f1;
                background-color: #131626;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🔒")
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel(f"{APP_NAME} — License Activation")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        lbl_sub = QLabel(f"Version: <span style='color: #818cf8; font-weight: 800;'>v{APP_VERSION}</span> • Genuine License Verification")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        layout.addWidget(hdr_frame)

        # Client Details section
        lbl_info_title = QLabel("Client Registration Details (আপনার তথ্য দিন):")
        lbl_info_title.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 11.5px;")

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("👤 আপনার পুরো নাম লিখুন (e.g. Md. Shofiqul)")

        self.txt_phone = QLineEdit()
        self.txt_phone.setPlaceholderText("📱 মোবাইল / টেলিগ্রাম নাম্বার (e.g. 017xxxxxxxx)")

        try:
            from core.telegram_license_shield import get_saved_client_meta
            meta = get_saved_client_meta()
            if meta.get("name"):
                self.txt_name.setText(meta["name"])
            if meta.get("phone"):
                self.txt_phone.setText(meta["phone"])
        except Exception:
            pass

        # Hardware ID display section
        lbl_hwid_title = QLabel("Your Machine Hardware ID (HWID):")
        lbl_hwid_title.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 11.5px;")

        self.txt_hwid = QLineEdit(self.hwid)
        self.txt_hwid.setReadOnly(True)
        self.txt_hwid.setStyleSheet("font-family: 'Consolas', monospace; font-size: 12.5px; color: #fbbf24; background-color: #10121e; font-weight: bold; border: 1px solid #202438;")

        btn_copy = QPushButton("📋 Copy HWID")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #818cf8;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
                border-color: #6366f1;
            }
        """)
        btn_copy.clicked.connect(self._copy_hwid)

        btn_copy_req = QPushButton("📨 Copy Request for Telegram")
        btn_copy_req.setCursor(Qt.PointingHandCursor)
        btn_copy_req.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f766e, stop:1 #0d9488);
                color: #ffffff;
                border: 1px solid #14b8a6;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #14b8a6, stop:1 #0f766e);
            }
        """)
        btn_copy_req.clicked.connect(self._copy_request)

        h_hwid = QHBoxLayout()
        h_hwid.setSpacing(8)
        h_hwid.addWidget(self.txt_hwid, stretch=1)
        h_hwid.addWidget(btn_copy)
        h_hwid.addWidget(btn_copy_req)

        # License Key Input
        lbl_key_title = QLabel("Enter License Activation Key:")
        lbl_key_title.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 11.5px;")

        self.txt_key = QLineEdit()
        self.txt_key.setPlaceholderText("SRK-XXXX-XXXX-XXXX-XXXX")
        self.txt_key.setStyleSheet("font-family: 'Consolas', monospace; color: #34d399; font-weight: bold;")
        self.txt_key.returnPressed.connect(self._activate_clicked)

        # Action Buttons
        btn_act = QPushButton("⚡ Activate Software License")
        btn_act.setCursor(Qt.PointingHandCursor)
        btn_act.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                font-weight: 800;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
            }
        """)
        btn_act.clicked.connect(self._activate_clicked)

        btn_exit = QPushButton("Exit")
        btn_exit.setCursor(Qt.PointingHandCursor)
        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
            }
        """)
        btn_exit.clicked.connect(self.reject)

        h_btns = QHBoxLayout()
        h_btns.setSpacing(10)
        h_btns.addWidget(btn_exit)
        h_btns.addWidget(btn_act, stretch=1)

        # Developer Contact Card
        lbl_dev = QLabel(
            "<b>Official Engineering & License Support:</b> SRK Shofiqul<br/>"
            "✈️ Telegram: <a href='https://t.me/srkplatforms' style='color:#34d399;'>@srkplatforms</a>"
        )
        lbl_dev.setOpenExternalLinks(True)
        lbl_dev.setStyleSheet("font-size: 11px; color: #94a3b8; background: #131626; border: 1px solid #202438; padding: 10px 14px; border-radius: 8px; line-height: 1.4;")

        layout.addWidget(lbl_info_title)
        layout.addWidget(self.txt_name)
        layout.addWidget(self.txt_phone)
        layout.addWidget(lbl_hwid_title)
        layout.addLayout(h_hwid)
        layout.addWidget(lbl_key_title)
        layout.addWidget(self.txt_key)
        layout.addLayout(h_btns)
        layout.addWidget(lbl_dev)

    def _copy_hwid(self) -> None:
        QApplication.clipboard().setText(self.hwid)
        QMessageBox.information(self, "Copied", "📋 Machine Hardware ID (HWID) copied to clipboard!\n\nSend this HWID to SRK Shofiqul to generate your key.")

    def _copy_request(self) -> None:
        name = self.txt_name.text().strip() or "Client"
        phone = self.txt_phone.text().strip() or "N/A"
        req_text = (
            "====================================\n"
            "🔒 srkBrowser License Activation Request\n"
            "====================================\n"
            f"👤 Name: {name}\n"
            f"📱 Phone / Telegram: {phone}\n"
            f"💻 Machine ID (HWID): {self.hwid}\n"
            f"🚀 Software: srkBrowser v{APP_VERSION}\n"
            "====================================\n"
            "Please generate my activation key."
        )
        QApplication.clipboard().setText(req_text)
        QMessageBox.information(self, "Request Copied", "✅ লাইসেন্স রিকোয়েস্ট কপি করা হয়েছে!\n\nএটি টেলিগ্রামে পাঠিয়ে দিন এবং লাইসেন্স কী সংগ্রহ করুন।")

    def _activate_clicked(self) -> None:
        from license_manager import verify_license_key, save_activated_license
        key = self.txt_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Activation Error", "Please enter a valid License Key.")
            return

        is_ok, msg, exp_t, meta = verify_license_key(self.hwid, key)
        if is_ok:
            c_name = self.txt_name.text().strip() or meta.get("n", "") or "VIP Member"
            c_phone = self.txt_phone.text().strip() or meta.get("p", "")
            save_activated_license(key, c_name, c_phone)
            self.activated = True
            QMessageBox.information(self, "Activation Successful", f"🎉 Software activated successfully!\n\nName: {c_name}\nStatus: {msg}")
            self.accept()
        else:
            QMessageBox.critical(self, "Activation Failed", f"Invalid or expired License Key:\n\n{msg}")


class AppUpdateDialog(QDialog):
    """
    Ultra-Luxury Dark Obsidian modal dialog interface for In-App Software Update System.
    Checks for online updates, displays changelog, downloads update ZIP, and applies update.
    """

    def __init__(
        self,
        latest_version: str,
        download_url: str,
        changelog: str,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.latest_version = latest_version
        self.download_url = download_url
        self.changelog = changelog
        self.downloader_thread: Optional[Any] = None

        self.setWindowTitle("🚀 Software Update Available")
        self.setFixedWidth(540)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QProgressBar {
                border: 1px solid #232742;
                border-radius: 6px;
                text-align: center;
                background-color: #10121e;
                color: #f1f5f9;
                font-weight: bold;
                font-size: 11px;
                height: 22px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                border-radius: 5px;
            }
            QTextEdit {
                background-color: #10121e;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.4;
            }
            QScrollBar:vertical {
                border: none;
                background: #10121e;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #232742;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4f46e5;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel("New Software Update Available!")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        lbl_sub = QLabel(f"Current: v{APP_VERSION} ➔ <span style='color: #34d399; font-weight: 800;'>New: v{self.latest_version}</span>")
        lbl_sub.setStyleSheet("font-size: 11.5px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        ver_pill = QLabel(f"v{self.latest_version}")
        ver_pill.setStyleSheet("background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 4px 10px; font-size: 11.5px; font-weight: 800;")
        hdr_layout.addWidget(ver_pill)

        layout.addWidget(hdr_frame)

        lbl_changelog = QLabel("📋 What's New in this Version (Changelog):")
        lbl_changelog.setStyleSheet("font-weight: 700; color: #fbbf24; font-size: 12px;")

        self.txt_changelog = QTextEdit()
        self.txt_changelog.setReadOnly(True)
        self.txt_changelog.setPlainText(self.changelog)
        self.txt_changelog.setFixedHeight(120)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11.5px;")

        self.btn_update = QPushButton("🚀 Download & Apply Update Now")
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 22px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
            }
        """)
        self.btn_update.clicked.connect(self._start_download)

        btn_cancel = QPushButton("Remind Me Later")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 9px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        h_btns = QHBoxLayout()
        h_btns.setSpacing(10)
        h_btns.addWidget(btn_cancel)
        h_btns.addWidget(self.btn_update, stretch=1)

        layout.addWidget(lbl_changelog)
        layout.addWidget(self.txt_changelog)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_status)
        layout.addLayout(h_btns)

    def _start_download(self) -> None:
        if not self.download_url:
            QMessageBox.warning(self, "No Download URL", "Download URL is not provided in update package.")
            return

        self.btn_update.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("⏳ Downloading update package from server...")

        from updater import UpdateDownloaderThread
        self.downloader_thread = UpdateDownloaderThread(self.download_url, self)
        self.downloader_thread.progress_updated.connect(self._on_download_progress)
        self.downloader_thread.download_finished.connect(self._on_download_finished)
        self.downloader_thread.start()

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int((downloaded / total) * 100)
            mb_d = downloaded / (1024 * 1024)
            mb_t = total / (1024 * 1024)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"⬇️ Downloaded {mb_d:.1f} MB of {mb_t:.1f} MB ({pct}%)")
        else:
            self.progress_bar.setRange(0, 0)
            self.lbl_status.setText("⬇️ Downloading update package...")

    def _on_download_finished(self, success: bool, temp_zip_path: str, err_msg: str) -> None:
        self.progress_bar.setRange(0, 100)
        if not success:
            self.btn_update.setEnabled(True)
            self.lbl_status.setText(f"❌ Download error: {err_msg}")
            QMessageBox.critical(self, "Download Error", f"Failed to download update package:\n\n{err_msg}")
            return

        self.lbl_status.setText("📦 Extracting and applying update files...")
        from updater import apply_zip_update
        ok_apply, apply_msg = apply_zip_update(temp_zip_path)

        if ok_apply:
            from updater import restart_application
            reply = QMessageBox.question(
                self,
                "Update Applied - Restart Software",
                f"🎉 Software update v{self.latest_version} has been extracted successfully!\n\n"
                "Would you like to restart the application now to apply all new features?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            self.accept()
            if reply == QMessageBox.Yes:
                restart_application()
        else:
            self.btn_update.setEnabled(True)
            self.lbl_status.setText(f"❌ Extraction error: {apply_msg}")
            QMessageBox.critical(self, "Update Extraction Error", f"Failed to extract update package:\n\n{apply_msg}")


def extract_profile_cookies_from_disk(p: Dict[str, Any]) -> str:
    """Safely extracts full cookies from profile dictionary or raw tokens without throwing exceptions."""
    try:
        if not isinstance(p, dict):
            return ""
        for k in ["cookie", "cookie_data", "cookie_str", "cookies", "fb_cookie"]:
            v = p.get(k)
            if v and isinstance(v, str) and len(v.strip()) > 10 and "..." not in v:
                return v.strip()
            elif v and isinstance(v, list):
                cookie_str = "; ".join(f"{c.get('name', '')}={c.get('value', '')}" for c in v if isinstance(c, dict) and c.get("name"))
                if cookie_str:
                    return cookie_str
        for fld in ["raw_line", "notes", "custom_notes"]:
            raw_text = str(p.get(fld, ""))
            if "datr=" in raw_text or "c_user=" in raw_text or "sb=" in raw_text:
                for part in raw_text.split("|"):
                    if "datr=" in part or "c_user=" in part or "sb=" in part:
                        return part.strip()
    except Exception:
        pass
    return ""


class FBAccountInfoPopupDialog(QDialog):
    """
    Ultra-Luxury Modern Cyber-Glass dialog for viewing Facebook account credentials,
    2FA Secret with live TOTP generation, and Full Session Cookies with 1-click single copy.
    """

    def __init__(self, profile_data: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_data = dict(profile_data) if profile_data else {}
        self._parent_win = parent
        self._pass_visible = False
        self._totp_timer: Optional[QTimer] = None

        p_num = self.profile_data.get("number", "Profile")
        disp_num = get_display_number(str(p_num))
        clean_num = str(disp_num).replace("#", "").strip()
        p_name = self.profile_data.get("name") or f"Profile #{clean_num}"
        self.setWindowTitle(f"ℹ️ FB Account Info & Credentials - #{clean_num}")
        self.setMinimumWidth(480)
        self.resize(520, 385)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d18;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
                background: transparent;
                border: none;
            }
            QLineEdit {
                background-color: #121528;
                color: #f1f5f9;
                border: 1px solid #232847;
                border-radius: 6px;
                padding: 5px 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11.5px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:focus {
                border-color: #818cf8;
                background-color: #161a32;
            }
            QPlainTextEdit {
                background-color: #101222;
                color: #34d399;
                border: 1px solid #20243d;
                border-radius: 6px;
                padding: 6px 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10.5px;
                selection-background-color: #4f46e5;
            }
        """)

        center_dialog_over_parent(self, parent)
        self._parse_credentials()
        self._init_ui()

        # Start live TOTP timer if 2FA secret is present
        if self._secret_2fa and len(self._secret_2fa) >= 6:
            self._update_totp_code()
            self._totp_timer = QTimer(self)
            self._totp_timer.setInterval(1000)
            self._totp_timer.timeout.connect(self._update_totp_code)
            self._totp_timer.start()

    def closeEvent(self, event) -> None:
        if self._totp_timer:
            self._totp_timer.stop()
        super().closeEvent(event)

    def _parse_credentials(self) -> None:
        p = self.profile_data
        raw_notes = str(p.get("notes") or "").strip()
        raw_line = str(p.get("raw_line") or "").strip()

        # 1. Cookies
        cookie = p.get("cookie") or p.get("cookie_data") or p.get("cookie_str") or p.get("cookies") or p.get("fb_cookie") or ""
        if not cookie or len(str(cookie)) < 25 or "..." in str(cookie):
            disk_c = extract_profile_cookies_from_disk(p)
            if disk_c and len(disk_c) > len(str(cookie)):
                cookie = disk_c
        self._cookie_str = str(cookie).strip()

        # 2. UID / Email
        self._uid = str(p.get("fb_uid") or p.get("uid") or "").strip()
        
        # 3. Password
        self._password = str(p.get("fb_pass") or p.get("password") or "").strip()

        # 4. 2FA Secret
        secret_2fa = str(p.get("fb_2fa") or p.get("secret_2fa") or p.get("2fa_secret") or p.get("secret_key") or p.get("secret") or "").strip()
        if "|" in secret_2fa or any(k in secret_2fa.lower() for k in ["pass:", "uid:", "cookie:"]) or secret_2fa.lower() in ("none", "n/a", "null", "false"):
            secret_2fa = ""
        self._secret_2fa = secret_2fa

        # Scan raw notes/tokens if missing
        scan_text = f"{raw_notes}\n{raw_line}"
        if scan_text.strip():
            tokens = scan_text.replace("|", "\n").split("\n")
            for tk in tokens:
                tk_s = tk.strip()
                tk_lower = tk_s.lower()
                if not self._uid and (tk_lower.startswith("uid:") or tk_lower.startswith("fb uid:")):
                    self._uid = tk_s.split(":", 1)[1].strip()
                elif not self._password and (tk_lower.startswith("pass:") or tk_lower.startswith("password:")):
                    self._password = tk_s.split(":", 1)[1].strip()
                elif not self._secret_2fa and (tk_lower.startswith("2fa:") or tk_lower.startswith("2fa secret:") or tk_lower.startswith("secret_2fa:")):
                    val = tk_s.split(":", 1)[1].strip()
                    if val and len(val) >= 6 and val.lower() not in ("none", "n/a", "null") and "|" not in val:
                        self._secret_2fa = val

        # Fallback UID from cookie c_user
        if not self._uid:
            import re
            m = re.search(r"c_user=(\d+)", self._cookie_str or scan_text)
            if m:
                self._uid = m.group(1)

        # Extra notes
        extra_lines = []
        for line in raw_notes.split("\n"):
            sl = line.strip()
            if not sl:
                continue
            sl_low = sl.lower()
            if any(sl_low.startswith(k) for k in ["uid:", "fb uid:", "password:", "pass:", "2fa:", "2fa secret:", "secret_2fa:", "cookie:"]):
                continue
            if "datr=" in sl or "c_user=" in sl or "sb=" in sl:
                continue
            extra_lines.append(sl)
        self._extra_notes = "\n".join(extra_lines).strip()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)

        # ── Credentials Body Card (Ultra-Compact) ──
        body_frame = QFrame()
        body_frame.setStyleSheet("""
            QFrame#BodyFrame {
                background-color: #0f1220;
                border: 1px solid #1e233d;
                border-radius: 9px;
            }
        """)
        body_frame.setObjectName("BodyFrame")
        body_layout = QVBoxLayout(body_frame)
        body_layout.setContentsMargins(12, 10, 12, 10)
        body_layout.setSpacing(8)

        # Helper to create styled copy button
        def _make_copy_btn(text: str, tooltip: str, bg_grad: str, hover_grad: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(28)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg_grad};
                    color: #ffffff;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 5px;
                    padding: 0 10px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: {hover_grad};
                    border-color: rgba(255, 255, 255, 0.25);
                }}
            """)
            return btn

        # 1. 🆔 Facebook UID / Email Row
        row_uid = QHBoxLayout()
        row_uid.setSpacing(8)
        lbl_uid = QLabel("🆔  UID / Email:")
        lbl_uid.setFixedWidth(95)
        lbl_uid.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #818cf8;")
        self.txt_uid = QLineEdit(self._uid)
        self.txt_uid.setFixedHeight(28)
        self.txt_uid.setReadOnly(True)
        self.txt_uid.setPlaceholderText("No Facebook UID/Email found")

        self.btn_copy_uid = _make_copy_btn(
            "📋 Copy", "Copy Facebook UID / Email",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca)",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5)"
        )
        self.btn_copy_uid.clicked.connect(lambda: self._copy_feedback(self.btn_copy_uid, self._uid or self.txt_uid.text(), "📋 Copy"))

        row_uid.addWidget(lbl_uid)
        row_uid.addWidget(self.txt_uid, stretch=1)
        row_uid.addWidget(self.btn_copy_uid)
        body_layout.addLayout(row_uid)

        # 2. 🔑 Password Row
        row_pass = QHBoxLayout()
        row_pass.setSpacing(8)
        lbl_pass = QLabel("🔑  Password:")
        lbl_pass.setFixedWidth(95)
        lbl_pass.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #fbbf24;")
        self.txt_pass = QLineEdit(self._password)
        self.txt_pass.setFixedHeight(28)
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setReadOnly(True)
        self.txt_pass.setPlaceholderText("No Password found")

        self.btn_toggle_pass = QPushButton("👁")
        self.btn_toggle_pass.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_pass.setToolTip("Show / Hide Password")
        self.btn_toggle_pass.setFixedSize(28, 28)
        self.btn_toggle_pass.setStyleSheet("""
            QPushButton {
                background-color: #191c2f;
                color: #fbbf24;
                border: 1px solid #292e4e;
                border-radius: 5px;
                font-family: 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #242944;
                border-color: #fbbf24;
            }
        """)
        self.btn_toggle_pass.clicked.connect(self._toggle_pass_visibility)

        self.btn_copy_pass = _make_copy_btn(
            "📋 Copy", "Copy Facebook Password",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309)",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706)"
        )
        self.btn_copy_pass.clicked.connect(lambda: self._copy_feedback(self.btn_copy_pass, self._password or self.txt_pass.text(), "📋 Copy"))

        row_pass.addWidget(lbl_pass)
        row_pass.addWidget(self.txt_pass, stretch=1)
        row_pass.addWidget(self.btn_toggle_pass)
        row_pass.addWidget(self.btn_copy_pass)
        body_layout.addLayout(row_pass)

        # 3. 🔐 2FA Secret Key & Live OTP Row
        row_2fa = QHBoxLayout()
        row_2fa.setSpacing(8)
        lbl_2fa = QLabel("🔐  2FA Secret:")
        lbl_2fa.setFixedWidth(95)
        lbl_2fa.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #34d399;")
        self.txt_2fa = QLineEdit(self._secret_2fa)
        self.txt_2fa.setFixedHeight(28)
        self.txt_2fa.setReadOnly(True)
        self.txt_2fa.setPlaceholderText("No 2FA Secret found")

        self.btn_copy_2fa = _make_copy_btn(
            "📋 Copy Key", "Copy 2FA Secret Key",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857)",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669)"
        )
        self.btn_copy_2fa.clicked.connect(lambda: self._copy_feedback(self.btn_copy_2fa, self._secret_2fa or self.txt_2fa.text(), "📋 Copy Key"))

        row_2fa.addWidget(lbl_2fa)
        row_2fa.addWidget(self.txt_2fa, stretch=1)
        row_2fa.addWidget(self.btn_copy_2fa)
        body_layout.addLayout(row_2fa)

        # Sub-row: ⚡ Live 6-digit TOTP Generator (if 2FA secret exists)
        if self._secret_2fa and len(self._secret_2fa) >= 6:
            row_totp = QHBoxLayout()
            row_totp.setContentsMargins(103, 0, 0, 0)
            row_totp.setSpacing(8)

            self.lbl_totp_val = QLabel("⚡ Live OTP: Generating...")
            self.lbl_totp_val.setFixedHeight(26)
            self.lbl_totp_val.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.12);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 5px;
                padding: 2px 8px;
                font-family: 'Consolas', monospace;
                font-weight: 800;
                font-size: 11.5px;
            """)

            self.btn_copy_otp = _make_copy_btn(
                "⚡ Copy OTP", "Copy current 6-digit live 2FA code",
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d9488, stop:1 #0f766e)",
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #14b8a6, stop:1 #0d9488)"
            )
            self.btn_copy_otp.setFixedHeight(26)
            self.btn_copy_otp.clicked.connect(self._copy_current_otp)

            row_totp.addWidget(self.lbl_totp_val, stretch=1)
            row_totp.addWidget(self.btn_copy_otp)
            body_layout.addLayout(row_totp)

        # 4. 🍪 Facebook Session Cookies Box
        vbox_cookie = QVBoxLayout()
        vbox_cookie.setSpacing(4)
        hdr_cookie = QHBoxLayout()
        lbl_cookie = QLabel("🍪  Facebook Session Cookies:")
        lbl_cookie.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #c084fc;")
        hdr_cookie.addWidget(lbl_cookie)
        hdr_cookie.addStretch()

        self.btn_copy_cookie = _make_copy_btn(
            "🍪 Copy Full Cookie", "Copy entire Facebook cookie string",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9)",
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #7c3aed)"
        )
        self.btn_copy_cookie.setFixedHeight(24)
        self.btn_copy_cookie.clicked.connect(lambda: self._copy_feedback(self.btn_copy_cookie, self._cookie_str, "🍪 Copy Full Cookie"))
        hdr_cookie.addWidget(self.btn_copy_cookie)
        vbox_cookie.addLayout(hdr_cookie)

        self.txt_cookies = QPlainTextEdit()
        self.txt_cookies.setReadOnly(True)
        self.txt_cookies.setFixedHeight(54)
        self.txt_cookies.setPlainText(self._cookie_str if self._cookie_str else "No active cookies detected for this profile.")
        vbox_cookie.addWidget(self.txt_cookies)
        body_layout.addLayout(vbox_cookie)

        # 5. 📝 Extra Notes (if any)
        if self._extra_notes:
            vbox_notes = QVBoxLayout()
            vbox_notes.setSpacing(3)
            lbl_extra = QLabel("📝  Additional Profile Notes:")
            lbl_extra.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8;")
            vbox_notes.addWidget(lbl_extra)

            self.txt_extra = QPlainTextEdit()
            self.txt_extra.setReadOnly(True)
            self.txt_extra.setFixedHeight(38)
            self.txt_extra.setPlainText(self._extra_notes)
            vbox_notes.addWidget(self.txt_extra)
            body_layout.addLayout(vbox_notes)

        layout.addWidget(body_frame)

        # ── Bottom Actions Row ──
        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(8)

        # 📋 Copy All (Formatted or Pipe-Delimited)
        btn_copy_all = QPushButton("📋 Copy All (Pipe: UID|Pass|2FA|Cookie)")
        btn_copy_all.setCursor(Qt.PointingHandCursor)
        btn_copy_all.setFixedHeight(30)
        btn_copy_all.setStyleSheet("""
            QPushButton {
                background-color: #191d33;
                color: #cdd6f4;
                border: 1px solid #2a3154;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #232845;
                color: #ffffff;
                border-color: #818cf8;
            }
        """)
        btn_copy_all.clicked.connect(lambda: self._copy_all_formatted(btn_copy_all))
        bot_layout.addWidget(btn_copy_all)

        # ✏️ Edit Info Button
        btn_edit = QPushButton("✏️ Edit Info")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setFixedHeight(30)
        btn_edit.setStyleSheet("""
            QPushButton {
                background-color: #16192d;
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.15);
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)
        btn_edit.clicked.connect(self._on_edit_info_clicked)
        bot_layout.addWidget(btn_edit)

        bot_layout.addStretch()

        # Close Button
        btn_close = QPushButton("✖ Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(30)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #16192a;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #21253e;
                color: #ffffff;
                border-color: #3e4670;
            }
        """)
        btn_close.clicked.connect(self.accept)
        bot_layout.addWidget(btn_close)

        layout.addLayout(bot_layout)

    def _toggle_pass_visibility(self) -> None:
        self._pass_visible = not self._pass_visible
        if self._pass_visible:
            self.txt_pass.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_pass.setText("🙈")
        else:
            self.txt_pass.setEchoMode(QLineEdit.Password)
            self.btn_toggle_pass.setText("👁")

    def _update_totp_code(self) -> None:
        """Calculate and display real-time TOTP 6-digit code with remaining seconds."""
        if not hasattr(self, "lbl_totp_val"):
            return
        code, remaining = self._calc_totp(self._secret_2fa)
        if code:
            self._current_otp_code = code
            self.lbl_totp_val.setText(f"⚡ Live OTP:  {code[:3]} {code[3:]}   ({remaining:02d}s)")
        else:
            self._current_otp_code = ""
            self.lbl_totp_val.setText("⚡ Live OTP:  Invalid Secret")

    @staticmethod
    def _calc_totp(secret: str) -> tuple[str, int]:
        """Pure Python RFC 6238 TOTP computation with 0 dependencies."""
        try:
            import time, base64, hmac, hashlib, struct
            clean_s = str(secret or "").replace(" ", "").upper().strip()
            if not clean_s or len(clean_s) < 6:
                return "", 0
            key = base64.b32decode(clean_s, casefold=True)
            now = time.time()
            intervals_no = int(now // 30)
            remaining = int(30 - (now % 30))
            msg = struct.pack(">Q", intervals_no)
            h = hmac.new(key, msg, hashlib.sha1).digest()
            o = h[19] & 15
            code = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
            return f"{code:06d}", remaining
        except Exception:
            return "", 0

    def _copy_current_otp(self) -> None:
        otp = getattr(self, "_current_otp_code", "")
        if not otp:
            otp, _ = self._calc_totp(self._secret_2fa)
        if otp:
            self._copy_feedback(self.btn_copy_otp, otp, "⚡ Copy OTP")

    def _copy_feedback(self, btn: QPushButton, text: str, default_label: str) -> None:
        """Copies text to clipboard and animates button with glowing '✓ Copied!' feedback."""
        if not text:
            return
        QApplication.clipboard().setText(str(text).strip())
        btn.setText("✓ Copied!")
        old_style = btn.styleSheet()
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                color: #ffffff;
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11.5px;
                font-weight: 800;
            }
        """)
        QTimer.singleShot(1400, lambda: self._restore_btn(btn, default_label, old_style))

    def _restore_btn(self, btn: QPushButton, label: str, style: str) -> None:
        try:
            btn.setText(label)
            btn.setStyleSheet(style)
        except Exception:
            pass

    def _copy_all_formatted(self, btn: QPushButton) -> None:
        """Copies pipe-delimited credentials: UID|PASS|2FA|COOKIE."""
        u = self._uid or ""
        p = self._password or ""
        twofa = self._secret_2fa or ""
        c = self._cookie_str or ""
        payload = f"{u}|{p}|{twofa}|{c}"
        self._copy_feedback(btn, payload, "📋 Copy All (Pipe: UID|Pass|2FA|Cookie)")

    def _on_edit_info_clicked(self) -> None:
        """Opens EditProfileInfoDialog directly from this popup."""
        dlg = EditProfileInfoDialog(self.profile_data, parent=self)
        if dlg.exec() == EditProfileInfoDialog.Accepted:
            new_data = dlg.get_data()
            self.profile_data.update(new_data)
            # Re-parse and update UI elements
            self._parse_credentials()
            self.txt_uid.setText(self._uid)
            self.txt_pass.setText(self._password)
            self.txt_2fa.setText(self._secret_2fa)
            self.txt_cookies.setPlainText(self._cookie_str if self._cookie_str else "No active cookies detected for this profile.")
            if hasattr(self, "txt_extra"):
                self.txt_extra.setPlainText(self._extra_notes)
            if self._secret_2fa:
                self._update_totp_code()
            if self._parent_win and hasattr(self._parent_win, "refresh_all_views"):
                self._parent_win.refresh_all_views()

    # Backward compatibility methods
    def get_notes(self) -> str:
        u = self._uid or ""
        p = self._password or ""
        twofa = self._secret_2fa or ""
        c = self._cookie_str or ""
        return f"UID: {u}\nPassword: {p}\n2FA Secret: {twofa}\nCookie:\n{c}".strip()

    def _copy_cookie(self) -> None:
        if self._cookie_str:
            QApplication.clipboard().setText(self._cookie_str)

    def _copy_all(self) -> None:
        self._copy_all_formatted(QPushButton())


# Backward-compatible alias for existing code
ProfileNoteDialog = FBAccountInfoPopupDialog


class EditProfileInfoDialog(QDialog):
    """
    Ultra-Luxury Cyber-Glass dialog for managing Profile Information, Facebook / Multi-Platform Account Credentials,
    Custom Notes (Gmail, Instagram, etc.), and Card Action Buttons.
    """
    def __init__(self, profile_data: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_data = profile_data.copy() if profile_data else {}
        num = self.profile_data.get("number", "Profile")
        name = self.profile_data.get("name", num)
        self.setWindowTitle(f"📝 Edit Info - {name} ({num})")
        self.resize(620, 660)
        self.setMinimumWidth(580)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d17;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
        """)

        center_dialog_over_parent(self, parent)
        self._init_ui()

    def _init_ui(self) -> None:
        num = self.profile_data.get("number", "Profile")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # 1. Header Frame with Glowing Squircle Icon & Profile Badge
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1d33, stop:1 #101322);
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 12px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(12, 10, 12, 10)
        hdr_layout.setSpacing(12)

        lbl_icon = QLabel("📝")
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setFixedSize(42, 42)
        lbl_icon.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #4338ca);
                border-radius: 10px;
                font-size: 20px;
                color: #ffffff;
                border: none;
            }
        """)
        hdr_layout.addWidget(lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("Profile Credentials & Notes")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff; background: transparent; border: none;")
        lbl_sub = QLabel("Manage Facebook, multi-platform accounts, custom notes & buttons")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        lbl_badge = QLabel(f"🏷️ #{num}")
        lbl_badge.setStyleSheet("""
            QLabel {
                background: rgba(99, 102, 241, 0.18);
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.45);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 800;
                font-size: 12.5px;
            }
        """)
        hdr_layout.addWidget(lbl_badge)
        layout.addWidget(hdr_frame)

        input_css = """
            QLineEdit, QTextEdit {
                background-color: #090b14;
                color: #ffffff;
                border: 1px solid #232845;
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 12.5px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #6366f1;
                background-color: #0e1120;
            }
            QLineEdit:hover, QTextEdit:hover {
                border-color: #383e6b;
            }
        """

        # 2. Section 1: Facebook Account Credentials Card
        fb_card = QFrame()
        fb_card.setObjectName("FbCard")
        fb_card.setStyleSheet("""
            QFrame#FbCard {
                background-color: #121526;
                border: 1px solid #20243d;
                border-radius: 12px;
            }
        """)
        fb_card_layout = QVBoxLayout(fb_card)
        fb_card_layout.setContentsMargins(14, 12, 14, 14)
        fb_card_layout.setSpacing(10)

        fb_hdr = QHBoxLayout()
        fb_hdr_lbl = QLabel("📘  Facebook Account Credentials")
        fb_hdr_lbl.setStyleSheet("color: #818cf8; font-size: 13px; font-weight: 800; background: transparent; border: none;")
        fb_hdr.addWidget(fb_hdr_lbl)
        fb_hdr.addStretch()
        fb_card_layout.addLayout(fb_hdr)

        fb_form = QFormLayout()
        fb_form.setSpacing(10)
        fb_form.setLabelAlignment(Qt.AlignLeft)

        self.txt_uid = QLineEdit()
        self.txt_uid.setStyleSheet(input_css)
        self.txt_uid.setPlaceholderText("e.g. 61582431000153 or user@email.com")
        self.txt_uid.setText(str(self.profile_data.get("fb_uid") or self.profile_data.get("uid") or ""))

        self.txt_pass = QLineEdit()
        self.txt_pass.setStyleSheet(input_css)
        self.txt_pass.setPlaceholderText("Facebook account password...")
        self.txt_pass.setText(str(self.profile_data.get("fb_pass") or self.profile_data.get("password") or ""))

        self.txt_2fa = QLineEdit()
        self.txt_2fa.setStyleSheet(input_css)
        self.txt_2fa.setPlaceholderText("e.g. JBSWY3DPEHPK3PXP (Leave blank if none)")
        self.txt_2fa.setText(str(self.profile_data.get("fb_2fa") or self.profile_data.get("secret_2fa") or ""))

        lbl_uid = QLabel("🆔 UID / Email:")
        lbl_uid.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        lbl_pass = QLabel("🔑 Password:")
        lbl_pass.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        lbl_2fa = QLabel("🔐 2FA Secret:")
        lbl_2fa.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: 700; background: transparent; border: none;")

        fb_form.addRow(lbl_uid, self.txt_uid)
        fb_form.addRow(lbl_pass, self.txt_pass)
        fb_form.addRow(lbl_2fa, self.txt_2fa)
        fb_card_layout.addLayout(fb_form)
        layout.addWidget(fb_card)

        # 3. Section 2: Multi-Platform & Custom Notes Card
        notes_card = QFrame()
        notes_card.setObjectName("NotesCard")
        notes_card.setStyleSheet("""
            QFrame#NotesCard {
                background-color: #121526;
                border: 1px solid #20243d;
                border-radius: 12px;
            }
        """)
        notes_layout = QVBoxLayout(notes_card)
        notes_layout.setContentsMargins(14, 12, 14, 14)
        notes_layout.setSpacing(8)

        notes_hdr = QHBoxLayout()
        notes_hdr_lbl = QLabel("📝  Other Accounts & Notes (Instagram, Gmail, etc.)")
        notes_hdr_lbl.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: 800; background: transparent; border: none;")
        notes_hdr.addWidget(notes_hdr_lbl)
        notes_hdr.addStretch()
        notes_layout.addLayout(notes_hdr)

        self.txt_custom_notes = QTextEdit()
        self.txt_custom_notes.setStyleSheet(input_css)
        self.txt_custom_notes.setPlaceholderText("Write additional account logins or custom notes here...")
        self.txt_custom_notes.setFixedHeight(95)

        # Pre-fill custom notes (filtering out UID/Pass/2FA/Cookies lines)
        raw_notes = self.profile_data.get("custom_notes", "") or self.profile_data.get("notes", "")
        custom_lines = []
        if raw_notes:
            for l in raw_notes.split("\n"):
                s = l.strip()
                s_lower = s.lower()
                if not s:
                    continue
                if any(s_lower.startswith(k) for k in ["uid:", "fb uid:", "password:", "pass:", "2fa:", "2fa secret:", "secret_2fa:", "cookie:", "method:"]):
                    continue
                if "|" in s and any(k in s_lower for k in ["fb uid", "uid:", "pass:"]):
                    continue
                if "datr=" in s or "c_user=" in s or "sb=" in s:
                    continue
                custom_lines.append(s)
        self.txt_custom_notes.setText("\n".join(custom_lines))
        notes_layout.addWidget(self.txt_custom_notes)
        layout.addWidget(notes_card)

        layout.addStretch()

        # 4. Bottom Footer Bar
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(4, 4, 4, 0)
        footer_layout.setSpacing(10)

        lbl_sec = QLabel("🔒 Encrypted & Cloud Synced")
        lbl_sec.setStyleSheet("color: #64748b; font-size: 11.5px; font-weight: 600; background: transparent; border: none;")
        footer_layout.addWidget(lbl_sec)
        footer_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #161828;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 9px 22px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1e2238;
                color: #ffffff;
                border-color: #4b5585;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾 Save Info")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 9px 28px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                border-color: #818cf8;
            }
        """)
        btn_save.clicked.connect(self.accept)

        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_save)
        layout.addLayout(footer_layout)

    def get_data(self) -> Dict[str, Any]:
        uid_val = self.txt_uid.text().strip()
        pass_val = self.txt_pass.text().strip()
        two_fa_val = self.txt_2fa.text().strip()
        custom_notes = self.txt_custom_notes.toPlainText().strip()

        # Preserve existing assigned scripts without overwriting
        existing_assigned = self.profile_data.get("assigned_scripts", [])

        clean_notes_parts = []
        if uid_val:
            clean_notes_parts.append(f"FB UID: {uid_val}")
        if pass_val:
            clean_notes_parts.append(f"Pass: {pass_val}")
        if two_fa_val and two_fa_val.lower() not in ("none", "n/a", "null"):
            clean_notes_parts.append(f"2FA: {two_fa_val}")
        if custom_notes:
            clean_notes_parts.append(custom_notes)

        update_data = {
            "fb_uid": uid_val,
            "uid": uid_val,
            "fb_pass": pass_val,
            "password": pass_val,
            "fb_2fa": two_fa_val,
            "secret_2fa": two_fa_val,
            "custom_notes": custom_notes,
            "notes": "\n".join(clean_notes_parts).strip(),
            "assigned_scripts": existing_assigned
        }

        return update_data


FBInfoDialog = EditProfileInfoDialog


class BulkEditDialog(QDialog):
    """
    Ultra-Luxury Dark Obsidian dialog allowing users to bulk edit Start Page URL, Proxy, Group, Extensions, and Bookmarks
    for multiple selected browser profiles simultaneously.
    """
    def __init__(self, selected_count: int, available_groups: List[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"✏️ Bulk Edit {selected_count} Profile(s)")
        self.setMinimumWidth(600)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QLineEdit, QComboBox {
                background-color: #10121e;
                color: #f1f5f9;
                border: 1.5px solid #232742;
                border-radius: 7px;
                padding: 7px 12px;
                font-size: 12px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #6366f1;
                background-color: #131626;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #10121e;
                color: #f1f5f9;
                border: 1px solid #232742;
                selection-background-color: #4f46e5;
                selection-color: #ffffff;
                outline: none;
                padding: 4px;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        try:
            from extension_manager import ExtensionManager
            self.ext_mgr = ExtensionManager()
        except Exception:
            self.ext_mgr = None

        try:
            from bookmark_manager import BookmarkManager
            self.bm_mgr = BookmarkManager()
        except Exception:
            self.bm_mgr = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("✏️")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel("Bulk Batch Edit Profiles")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        lbl_sub = QLabel("Select attributes below to apply across all chosen browser profiles")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        cnt_badge = QLabel(f"👥 {selected_count} Selected")
        cnt_badge.setStyleSheet("background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 6px; padding: 4px 10px; font-size: 11.5px; font-weight: 800;")
        hdr_layout.addWidget(cnt_badge)

        layout.addWidget(hdr_frame)

        # Helper card builder for ultra-modern accordion style cards
        def _create_option_card(title: str):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #131626;
                    border: 1px solid #202438;
                    border-radius: 9px;
                }
            """)
            card_vbox = QVBoxLayout(card)
            card_vbox.setContentsMargins(12, 9, 12, 9)
            card_vbox.setSpacing(6)

            hdr_widget = QWidget()
            hdr_widget.setCursor(Qt.PointingHandCursor)
            hdr_hbox = QHBoxLayout(hdr_widget)
            hdr_hbox.setContentsMargins(0, 2, 0, 2)
            hdr_hbox.setSpacing(8)

            chk = QCheckBox(title)
            chk.setCursor(Qt.PointingHandCursor)
            chk.setStyleSheet("""
                QCheckBox {
                    font-size: 12.5px;
                    font-weight: 800;
                    color: #f1f5f9;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 17px;
                    height: 17px;
                    border-radius: 4px;
                    border: 1px solid #232742;
                    background-color: #10121e;
                }
                QCheckBox::indicator:checked {
                    background-color: #4f46e5;
                    border-color: #6366f1;
                }
            """)

            lbl_badge = QLabel("OFF")
            lbl_badge.setCursor(Qt.PointingHandCursor)
            lbl_badge.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; background: #10121e; padding: 2px 8px; border-radius: 4px; border: 1px solid #202438;")

            hdr_hbox.addWidget(chk)
            hdr_hbox.addStretch()
            hdr_hbox.addWidget(lbl_badge)

            # Make entire header area clickable to toggle checkbox
            def _hdr_click(event):
                chk.setChecked(not chk.isChecked())

            hdr_widget.mousePressEvent = _hdr_click

            card_vbox.addWidget(hdr_widget)

            container = QWidget()
            container.setVisible(False)
            card_vbox.addWidget(container)

            def _on_toggle(checked: bool):
                container.setVisible(checked)
                if checked:
                    lbl_badge.setText("ACTIVE")
                    lbl_badge.setStyleSheet("color: #34d399; font-size: 10px; font-weight: 800; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 4px;")
                    card.setStyleSheet("""
                        QFrame {
                            background-color: #151829;
                            border: 1.5px solid #6366f1;
                            border-radius: 9px;
                        }
                    """)
                else:
                    lbl_badge.setText("OFF")
                    lbl_badge.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; background: #10121e; padding: 2px 8px; border-radius: 4px; border: 1px solid #202438;")
                    card.setStyleSheet("""
                        QFrame {
                            background-color: #131626;
                            border: 1px solid #202438;
                            border-radius: 9px;
                        }
                    """)

            chk.toggled.connect(_on_toggle)
            return card, chk, container, _on_toggle

        # 1. Start Page URL Card
        card_url, self.chk_url, self.container_url, _ = _create_option_card("🌐  Start Page URL")
        c_url_layout = QVBoxLayout(self.container_url)
        c_url_layout.setContentsMargins(0, 6, 0, 0)
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("e.g. https://www.facebook.com")
        self.input_url.setText("https://www.facebook.com")
        c_url_layout.addWidget(self.input_url)
        self.chk_url.toggled.connect(self.input_url.setEnabled)
        layout.addWidget(card_url)

        # 2. Proxy Settings Card
        card_proxy, self.chk_proxy, self.container_proxy, toggle_proxy_card = _create_option_card("🛡️  Proxy Settings")
        proxy_layout = QGridLayout(self.container_proxy)
        proxy_layout.setContentsMargins(0, 6, 0, 0)
        proxy_layout.setHorizontalSpacing(10)
        proxy_layout.setVerticalSpacing(8)
        
        self.cmb_proxy_type = QComboBox()
        self.cmb_proxy_type.addItems(["None", "HTTP", "SOCKS5"])
        
        self.input_proxy_host = QLineEdit()
        self.input_proxy_host.setPlaceholderText("Proxy Host (e.g. 192.168.1.1)")
        
        self.input_proxy_port = QLineEdit()
        self.input_proxy_port.setPlaceholderText("Port")

        self.input_proxy_user = QLineEdit()
        self.input_proxy_user.setPlaceholderText("Username (Optional)")

        self.input_proxy_pass = QLineEdit()
        self.input_proxy_pass.setPlaceholderText("Password (Optional)")

        lbl_t = QLabel("Type:")
        lbl_t.setStyleSheet("font-weight: bold; color: #818cf8;")
        lbl_hp = QLabel("Host/Port:")
        lbl_hp.setStyleSheet("font-weight: bold; color: #818cf8;")
        lbl_up = QLabel("User/Pass:")
        lbl_up.setStyleSheet("font-weight: bold; color: #818cf8;")

        proxy_layout.addWidget(lbl_t, 0, 0)
        proxy_layout.addWidget(self.cmb_proxy_type, 0, 1, 1, 2)
        proxy_layout.addWidget(lbl_hp, 1, 0)
        proxy_layout.addWidget(self.input_proxy_host, 1, 1)
        proxy_layout.addWidget(self.input_proxy_port, 1, 2)
        proxy_layout.addWidget(lbl_up, 2, 0)
        proxy_layout.addWidget(self.input_proxy_user, 2, 1)
        proxy_layout.addWidget(self.input_proxy_pass, 2, 2)

        def _toggle_proxy(checked: bool):
            toggle_proxy_card(checked)
            self.cmb_proxy_type.setEnabled(checked)
            is_active = checked and self.cmb_proxy_type.currentText() != "None"
            self.input_proxy_host.setEnabled(is_active)
            self.input_proxy_port.setEnabled(is_active)
            self.input_proxy_user.setEnabled(is_active)
            self.input_proxy_pass.setEnabled(is_active)

        self.chk_proxy.toggled.connect(_toggle_proxy)
        self.cmb_proxy_type.currentTextChanged.connect(lambda t: _toggle_proxy(self.chk_proxy.isChecked()))
        layout.addWidget(card_proxy)

        # 3. Group Assignment Card
        card_grp, self.chk_grp, self.container_grp, _ = _create_option_card("📁  Group Assignment")
        c_grp_layout = QVBoxLayout(self.container_grp)
        c_grp_layout.setContentsMargins(0, 6, 0, 0)
        self.cmb_grp = QComboBox()
        self.cmb_grp.addItems(available_groups or ["Default"])
        c_grp_layout.addWidget(self.cmb_grp)
        self.chk_grp.toggled.connect(self.cmb_grp.setEnabled)
        layout.addWidget(card_grp)

        # 4. Extensions to Auto-Install Card
        card_ext, self.chk_ext, self.container_ext, _ = _create_option_card("🧩  Auto-Install Extensions")
        c_ext_layout = QVBoxLayout(self.container_ext)
        c_ext_layout.setContentsMargins(0, 6, 0, 0)
        self.ext_checkboxes = []

        if self.ext_mgr:
            all_exts = [e for e in self.ext_mgr.get_all_extensions() if e.get("is_active", True)]
            if all_exts:
                ext_scroll = QScrollArea()
                ext_scroll.setFixedHeight(120)
                ext_scroll.setWidgetResizable(True)
                ext_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                ext_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                ext_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

                ext_content = QWidget()
                ext_content.setStyleSheet("background: transparent; border: none;")
                ext_flow = FlowLayout(ext_content, margin=0, spacing=10)

                for ext in all_exts:
                    ename = ext.get("name", "Extension")
                    epath = ext.get("path", "")
                    btn_chip = QPushButton(f"🧩  {ename}")
                    btn_chip.setToolTip(ename)
                    btn_chip.setCheckable(True)
                    btn_chip.setChecked(False)
                    btn_chip.setCursor(Qt.PointingHandCursor)
                    btn_chip.setStyleSheet("""
                        QPushButton {
                            color: #94a3b8;
                            font-size: 12px;
                            font-weight: 700;
                            padding: 7px 16px;
                            background-color: #080a14;
                            border: 1.5px solid #1f274d;
                            border-radius: 16px;
                            text-align: center;
                        }
                        QPushButton:hover {
                            border-color: #34d399;
                            background-color: #131d30;
                            color: #ffffff;
                        }
                        QPushButton:checked {
                            color: #34d399;
                            border-color: #10b981;
                            background-color: rgba(16, 185, 129, 0.18);
                            font-weight: 800;
                        }
                    """)
                    self.ext_checkboxes.append((epath, btn_chip))
                    ext_flow.addWidget(btn_chip)

                ext_scroll.setWidget(ext_content)
                c_ext_layout.addWidget(ext_scroll)
            else:
                lbl_no_ext = QLabel("No active extensions enabled.")
                lbl_no_ext.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 4px;")
                c_ext_layout.addWidget(lbl_no_ext)

        layout.addWidget(card_ext)

        # 5. Bookmarks Bar Auto-Sync Card
        card_bm, self.chk_bm, self.container_bm, _ = _create_option_card("🔖  Bookmarks Bar Auto-Sync")
        c_bm_layout = QVBoxLayout(self.container_bm)
        c_bm_layout.setContentsMargins(0, 6, 0, 0)
        self.bm_checkboxes = []

        if self.bm_mgr:
            all_bms = self.bm_mgr.get_all_bookmarks()
            if all_bms:
                bm_scroll = QScrollArea()
                bm_scroll.setFixedHeight(120)
                bm_scroll.setWidgetResizable(True)
                bm_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                bm_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                bm_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

                bm_content = QWidget()
                bm_content.setStyleSheet("background: transparent; border: none;")
                bm_flow = FlowLayout(bm_content, margin=0, spacing=10)

                for bm in all_bms:
                    bname = bm.get("name", "Bookmark")
                    burl = bm.get("url", "")
                    btn_chip = QPushButton(f"🔖  {bname}")
                    btn_chip.setToolTip(f"{bname}\n{burl}")
                    btn_chip.setCheckable(True)
                    btn_chip.setChecked(False)
                    btn_chip.setCursor(Qt.PointingHandCursor)
                    btn_chip.setStyleSheet("""
                        QPushButton {
                            color: #94a3b8;
                            font-size: 12px;
                            font-weight: 700;
                            padding: 7px 16px;
                            background-color: #080a14;
                            border: 1.5px solid #1f274d;
                            border-radius: 16px;
                            text-align: center;
                        }
                        QPushButton:hover {
                            border-color: #f59e0b;
                            background-color: #1a1710;
                            color: #ffffff;
                        }
                        QPushButton:checked {
                            color: #f59e0b;
                            border-color: #d97706;
                            background-color: rgba(245, 158, 11, 0.18);
                            font-weight: 800;
                        }
                    """)
                    self.bm_checkboxes.append((bm, btn_chip))
                    bm_flow.addWidget(btn_chip)

                bm_scroll.setWidget(bm_content)
                c_bm_layout.addWidget(bm_scroll)
            else:
                lbl_no_bm = QLabel("No bookmarks configured.")
                lbl_no_bm.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 4px;")
                c_bm_layout.addWidget(lbl_no_bm)

        layout.addWidget(card_bm)

        # 6. Quick Action Scripts Card
        card_script, self.chk_script, self.container_script, _ = _create_option_card("📜  Quick Action Scripts")
        c_sc_layout = QVBoxLayout(self.container_script)
        c_sc_layout.setContentsMargins(0, 6, 0, 0)
        self.script_checkboxes = []
        available_scripts = [
            {"id": "fb_account_info", "short_name": "FB Info", "icon": "ℹ️", "full_name": "ℹ️ Facebook Account Info & Live Credentials Viewer"},
            {"id": "fb_relogin", "short_name": "FB-Relogin", "icon": "🔑", "full_name": "🔑 Facebook Auto Account Re-Login & Cookie Refresh Helper"},
            {"id": "fb_quick_page_create", "short_name": "Page Create", "icon": "📄", "full_name": "⚡ Facebook 1-Click Instant Page Creator"},
            {"id": "fb_language_converter", "short_name": "FB-Language", "icon": "🌐", "full_name": "🌐 Facebook 1-Click Language Converter"},
            {"id": "fb_business_creator", "short_name": "FBBM", "icon": "⚡", "full_name": "⚡ Facebook 1-Click Business Manager Creator"},
            {"id": "fb_bulk_video_uploader", "short_name": "FBVUP", "icon": "🎬", "full_name": "🎬 Facebook Bulk Video Uploader"}
        ]

        try:
            from bot_license_manager import BotLicenseManager
            blm_i = BotLicenseManager()
            available_scripts = [sc for sc in available_scripts if not blm_i.is_item_deactivated("script", sc["id"])]
        except Exception:
            pass

        if available_scripts:
            sc_scroll = QScrollArea()
            sc_scroll.setFixedHeight(120)
            sc_scroll.setWidgetResizable(True)
            sc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sc_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            sc_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

            sc_content = QWidget()
            sc_content.setStyleSheet("background: transparent; border: none;")
            sc_flow = FlowLayout(sc_content, margin=0, spacing=10)

            for sc_item in available_scripts:
                sid = sc_item["id"]
                sname = sc_item["short_name"]
                sicon = sc_item.get("icon", "⚡")
                fname = sc_item.get("full_name", sname)
                btn_chip = QPushButton(f"{sicon}  {sname}")
                btn_chip.setToolTip(fname)
                btn_chip.setCheckable(True)
                btn_chip.setChecked(False)
                btn_chip.setCursor(Qt.PointingHandCursor)
                btn_chip.setStyleSheet("""
                    QPushButton {
                        color: #94a3b8;
                        font-size: 12px;
                        font-weight: 700;
                        padding: 7px 16px;
                        background-color: #080a14;
                        border: 1.5px solid #1f274d;
                        border-radius: 16px;
                        text-align: center;
                    }
                    QPushButton:hover {
                        border-color: #818cf8;
                        background-color: #141b32;
                        color: #ffffff;
                    }
                    QPushButton:checked {
                        color: #818cf8;
                        border-color: #6366f1;
                        background-color: rgba(129, 140, 248, 0.18);
                        font-weight: 800;
                    }
                """)
                self.script_checkboxes.append((sid, btn_chip))
                sc_flow.addWidget(btn_chip)

            sc_scroll.setWidget(sc_content)
            c_sc_layout.addWidget(sc_scroll)
        else:
            lbl_no_sc = QLabel("No active scripts enabled.")
            lbl_no_sc.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 4px;")
            c_sc_layout.addWidget(lbl_no_sc)

        layout.addWidget(card_script)

        # Buttons
        btn_hbox = QHBoxLayout()
        btn_hbox.setSpacing(10)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 9px 20px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
                border-color: #3b4268;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_apply = QPushButton("⚡ Apply Bulk Changes")
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 24px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
            }
        """)
        btn_apply.clicked.connect(self.accept)

        btn_hbox.addStretch()
        btn_hbox.addWidget(btn_cancel)
        btn_hbox.addWidget(btn_apply)
        layout.addLayout(btn_hbox)

    def get_updates(self) -> Dict[str, Any]:
        updates = {}
        if self.chk_url.isChecked():
            updates["start_url"] = self.input_url.text().strip()
        if self.chk_proxy.isChecked():
            updates["proxy_type"] = self.cmb_proxy_type.currentText()
            updates["proxy_host"] = self.input_proxy_host.text().strip()
            updates["proxy_port"] = self.input_proxy_port.text().strip()
            updates["proxy_user"] = getattr(self, "input_proxy_user", None).text().strip() if hasattr(self, "input_proxy_user") else ""
            updates["proxy_pass"] = getattr(self, "input_proxy_pass", None).text().strip() if hasattr(self, "input_proxy_pass") else ""
        if self.chk_grp.isChecked():
            updates["group"] = self.cmb_grp.currentText().strip() or "Default"
        if hasattr(self, "chk_ext") and self.chk_ext.isChecked():
            updates["extensions"] = [epath for epath, chk in self.ext_checkboxes if chk.isChecked()]
        if hasattr(self, "chk_bm") and self.chk_bm.isChecked():
            updates["_sync_bookmarks"] = [bm for bm, chk in self.bm_checkboxes if chk.isChecked()]
        if hasattr(self, "chk_script") and self.chk_script.isChecked():
            updates["assigned_scripts"] = [sid for sid, chk in self.script_checkboxes if chk.isChecked()]
        return updates


class ExtensionTargetDialog(QDialog):
    """Ultra-Luxury Dark Obsidian dialog presented when configuring target scope for an extension or script."""

    def __init__(
        self,
        ext_name: str,
        available_groups: List[str] = None,
        current_mode: str = "manual",
        current_groups: List[str] = None,
        item_type: str = "extension",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.ext_name = ext_name
        self.item_type = str(item_type or "extension").lower().strip()
        self.available_groups = available_groups or ["Default"]
        self.current_mode = current_mode or "manual"
        self.current_groups = current_groups or []
        self.group_checkboxes: List[Tuple[str, QCheckBox]] = []

        type_title = "Script" if self.item_type == "script" else "Extension"
        self.setWindowTitle(f"🎯 {type_title} Target Scope - {ext_name}")
        self.setFixedWidth(540)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 18, 20, 18)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🎯")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel(f"{type_title} Target Scope")
        lbl_t.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        lbl_sub_text = "Select which profiles will display this quick action button" if self.item_type == "script" else "Select which profiles will auto-load this extension"
        lbl_sub = QLabel(lbl_sub_text)
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox, stretch=1)

        disp_ext_name = ext_name if len(ext_name) <= 24 else (ext_name[:21] + "...")
        ext_badge = QLabel(disp_ext_name)
        ext_badge.setToolTip(ext_name)
        ext_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #fbbf24; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 6px; padding: 3px 8px;")
        hdr_layout.addWidget(ext_badge)

        layout.addWidget(hdr_frame)

        # Radio options group
        self.btn_group = QButtonGroup(self)

        # Option Card 1: All Profiles
        card_all = QFrame()
        card_all.setCursor(Qt.PointingHandCursor)
        card_all.setStyleSheet("""
            QFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 9px;
                padding: 2px;
            }
            QFrame:hover { border-color: #10b981; background-color: #15192c; }
        """)
        c1_v = QVBoxLayout(card_all)
        c1_v.setContentsMargins(12, 8, 12, 8)
        c1_v.setSpacing(2)

        self.rad_all = QRadioButton("🌐 All Profiles")
        self.rad_all.setStyleSheet("font-size: 13px; font-weight: 800; color: #34d399; border: none; background: transparent;")
        self.btn_group.addButton(self.rad_all)

        lbl_all_sub_text = "Auto-attach script button to all existing & future browser profiles" if self.item_type == "script" else "Auto-load on all existing & future browser profiles"
        lbl_all_sub = QLabel(lbl_all_sub_text)
        lbl_all_sub.setStyleSheet("font-size: 11px; color: #94a3b8; border: none; background: transparent; margin-left: 22px;")

        c1_v.addWidget(self.rad_all)
        c1_v.addWidget(lbl_all_sub)
        layout.addWidget(card_all)

        # Option Card 2: New Profiles Only
        card_new = QFrame()
        card_new.setCursor(Qt.PointingHandCursor)
        card_new.setStyleSheet("""
            QFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 9px;
                padding: 2px;
            }
            QFrame:hover { border-color: #6366f1; background-color: #15192c; }
        """)
        c2_v = QVBoxLayout(card_new)
        c2_v.setContentsMargins(12, 8, 12, 8)
        c2_v.setSpacing(2)

        self.rad_new_only = QRadioButton("✨ New Profiles Only")
        self.rad_new_only.setStyleSheet("font-size: 13px; font-weight: 800; color: #818cf8; border: none; background: transparent;")
        self.btn_group.addButton(self.rad_new_only)

        lbl_new_sub_text = "Auto-attach script button only when creating new browser profiles" if self.item_type == "script" else "Auto-attach only when creating new browser profiles"
        lbl_new_sub = QLabel(lbl_new_sub_text)
        lbl_new_sub.setStyleSheet("font-size: 11px; color: #94a3b8; border: none; background: transparent; margin-left: 22px;")

        c2_v.addWidget(self.rad_new_only)
        c2_v.addWidget(lbl_new_sub)
        layout.addWidget(card_new)

        # Option Card 3: Specific Groups Only
        card_grp = QFrame()
        card_grp.setCursor(Qt.PointingHandCursor)
        card_grp.setStyleSheet("""
            QFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 9px;
                padding: 2px;
            }
            QFrame:hover { border-color: #f59e0b; background-color: #15192c; }
        """)
        c3_v = QVBoxLayout(card_grp)
        c3_v.setContentsMargins(12, 8, 12, 8)
        c3_v.setSpacing(2)

        self.rad_groups = QRadioButton("👥 Specific Profile Groups Only")
        self.rad_groups.setStyleSheet("font-size: 13px; font-weight: 800; color: #fbbf24; border: none; background: transparent;")
        self.btn_group.addButton(self.rad_groups)

        lbl_grp_sub_text = "Limit script button to selected profile groups" if self.item_type == "script" else "Limit extension loading to selected profile groups"
        lbl_grp_sub = QLabel(lbl_grp_sub_text)
        lbl_grp_sub.setStyleSheet("font-size: 11px; color: #94a3b8; border: none; background: transparent; margin-left: 22px;")

        c3_v.addWidget(self.rad_groups)
        c3_v.addWidget(lbl_grp_sub)
        layout.addWidget(card_grp)

        card_all.mousePressEvent = lambda e: self.rad_all.setChecked(True)
        card_new.mousePressEvent = lambda e: self.rad_new_only.setChecked(True)
        card_grp.mousePressEvent = lambda e: self.rad_groups.setChecked(True)

        # Group Selector Panel Container
        self.grp_panel = QFrame()
        self.grp_panel.setStyleSheet("""
            QFrame {
                background-color: #10121e;
                border: 1px solid #202438;
                border-radius: 8px;
            }
        """)
        panel_layout = QVBoxLayout(self.grp_panel)
        panel_layout.setContentsMargins(10, 8, 10, 8)
        panel_layout.setSpacing(6)

        action_bar = QHBoxLayout()
        lbl_select = QLabel("Select Target Groups:")
        lbl_select.setStyleSheet("font-size: 11.5px; font-weight: bold; color: #fbbf24; border: none; background: transparent;")

        btn_select_all = QPushButton("Select All")
        btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_select_all.setStyleSheet("background: #131626; color: #818cf8; border: 1px solid #232742; border-radius: 4px; padding: 3px 8px; font-size: 10.5px; font-weight: bold;")
        btn_select_all.clicked.connect(lambda: self._set_all_groups_checked(True))

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.setCursor(Qt.PointingHandCursor)
        btn_deselect_all.setStyleSheet("background: #131626; color: #f87171; border: 1px solid #232742; border-radius: 4px; padding: 3px 8px; font-size: 10.5px; font-weight: bold;")
        btn_deselect_all.clicked.connect(lambda: self._set_all_groups_checked(False))

        action_bar.addWidget(lbl_select)
        action_bar.addStretch()
        action_bar.addWidget(btn_select_all)
        action_bar.addWidget(btn_deselect_all)
        panel_layout.addLayout(action_bar)

        self.group_chips: List[Tuple[str, QPushButton]] = []

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(80)
        scroll_area.setMaximumHeight(150)
        scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #10121e; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #232742; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: #4f46e5; }
        """)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        
        flow_layout = FlowLayout(scroll_content, margin=2, spacing=8)

        chip_style_unchecked = """
            QPushButton {
                background-color: #131626;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 7px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background-color: #181c32;
                border-color: #3b4268;
                color: #ffffff;
            }
        """
        chip_style_checked = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(245, 158, 11, 0.24), stop:1 rgba(217, 119, 6, 0.18));
                color: #fbbf24;
                border: 1px solid #f59e0b;
                border-radius: 7px;
                padding: 6px 14px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: rgba(245, 158, 11, 0.32);
                border-color: #fbbf24;
                color: #ffffff;
            }
        """

        for g in self.available_groups:
            chip_btn = QPushButton(f"📁  {g}")
            chip_btn.setCheckable(True)
            chip_btn.setCursor(Qt.PointingHandCursor)
            is_init_checked = g in self.current_groups
            chip_btn.setChecked(is_init_checked)
            chip_btn.setStyleSheet(chip_style_checked if is_init_checked else chip_style_unchecked)

            def _make_chip_toggle(btn):
                def _on_toggle(checked):
                    btn.setStyleSheet(chip_style_checked if checked else chip_style_unchecked)
                return _on_toggle

            chip_btn.toggled.connect(_make_chip_toggle(chip_btn))
            self.group_chips.append((g, chip_btn))
            flow_layout.addWidget(chip_btn)

        scroll_area.setWidget(scroll_content)
        panel_layout.addWidget(scroll_area)

        # Set initial selected radio: NONE checked if mode is manual / default
        mode_low = str(self.current_mode).lower().strip()
        if mode_low == "all":
            self.rad_all.setChecked(True)
            self.grp_panel.setVisible(False)
        elif mode_low == "new_only":
            self.rad_new_only.setChecked(True)
            self.grp_panel.setVisible(False)
        elif mode_low == "groups":
            self.rad_groups.setChecked(True)
            self.grp_panel.setVisible(True)
        else:
            # Default: None checked
            self.rad_all.setAutoExclusive(False)
            self.rad_new_only.setAutoExclusive(False)
            self.rad_groups.setAutoExclusive(False)
            self.rad_all.setChecked(False)
            self.rad_new_only.setChecked(False)
            self.rad_groups.setChecked(False)
            self.rad_all.setAutoExclusive(True)
            self.rad_new_only.setAutoExclusive(True)
            self.rad_groups.setAutoExclusive(True)
            self.grp_panel.setVisible(False)

        layout.addWidget(self.grp_panel)

        def _on_grp_toggled(checked: bool) -> None:
            self.grp_panel.setVisible(checked)
            self.adjustSize()

        self.rad_groups.toggled.connect(_on_grp_toggled)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
                border-color: #3b4268;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾 Apply & Save Scope")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
            }
        """)
        btn_save.clicked.connect(self.accept)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _set_all_groups_checked(self, checked: bool) -> None:
        for _, btn in self.group_chips:
            btn.setChecked(checked)

    def get_selection(self) -> Tuple[str, List[str]]:
        if self.rad_all.isChecked():
            return "all", []
        elif self.rad_new_only.isChecked():
            return "new_only", []
        elif self.rad_groups.isChecked():
            selected_groups = [g for g, btn in self.group_chips if btn.isChecked()]
            return "groups", selected_groups
        else:
            return "manual", []


class TargetScopeProgressDialog(QDialog):
    """
    Modern Dark Obsidian progress popup displayed while applying target scope across profiles.
    Shows real-time progress bar, percentage, and profile processing status without UI freeze.
    """

    def __init__(
        self,
        item_name: str,
        total_profiles: int,
        item_type: str = "script",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.item_name = item_name
        self.total_profiles = max(1, total_profiles)
        self.item_type = str(item_type or "script").lower().strip()

        type_str = "Script" if self.item_type == "script" else "Extension"
        self.setWindowTitle(f"🎯 Applying {type_str} Target Scope")
        self.setFixedSize(500, 210)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QProgressBar {
                border: 1px solid #232742;
                border-radius: 7px;
                text-align: center;
                background-color: #10121e;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                height: 24px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                border-radius: 6px;
            }
        """)

        # Auto-center over parent
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        self.icon_lbl = QLabel("⏳")
        self.icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(self.icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.lbl_title = QLabel(f"Applying {type_str} Target Scope...")
        self.lbl_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        disp_name = item_name if len(item_name) <= 32 else (item_name[:29] + "...")
        self.lbl_sub = QLabel(f"Target: <span style='color: #818cf8; font-weight: 700;'>{disp_name}</span>")
        self.lbl_sub.setStyleSheet("font-size: 11.5px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(self.lbl_title)
        title_vbox.addWidget(self.lbl_sub)
        hdr_layout.addLayout(title_vbox, stretch=1)

        layout.addWidget(hdr_frame)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_profiles)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / %m Profiles (%p%)")
        layout.addWidget(self.progress_bar)

        # Status row
        status_hbox = QHBoxLayout()
        self.lbl_status = QLabel(f"Preparing to configure {self.total_profiles} profiles...")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11.5px;")
        status_hbox.addWidget(self.lbl_status, stretch=1)
        layout.addLayout(status_hbox)

    def set_progress(self, current: int, total: int, profile_name: str = "") -> None:
        """Update progress bar value and live status message."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        p_info = f" ({profile_name})" if profile_name else ""
        self.lbl_status.setText(f"Applying to profile {current} of {total}{p_info}...")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def set_completed(self, success_msg: str = "") -> None:
        """Update state to completed with green checkmark styling."""
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.icon_lbl.setText("✅")
        self.lbl_title.setText("Target Scope Configured Successfully!")
        self.lbl_status.setText(success_msg or f"✅ Finished configuring {self.total_profiles} profiles.")
        self.lbl_status.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()


class BulkEditProgressDialog(QDialog):
    """
    Modern Dark Obsidian progress popup displayed while applying bulk edits across profiles.
    Shows real-time progress bar, percentage, and profile processing status without UI freeze.
    """

    def __init__(
        self,
        total_profiles: int,
        details_text: str = "Applying bulk profile changes...",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.total_profiles = max(1, total_profiles)

        self.setWindowTitle("✏️ Applying Bulk Changes")
        self.setFixedSize(500, 215)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QProgressBar {
                border: 1px solid #232742;
                border-radius: 7px;
                text-align: center;
                background-color: #10121e;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                height: 24px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                border-radius: 6px;
            }
        """)

        # Auto-center over parent
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        self.icon_lbl = QLabel("⏳")
        self.icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(self.icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.lbl_title = QLabel("Applying Bulk Profile Updates...")
        self.lbl_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        self.lbl_sub = QLabel(f"Scope: <span style='color: #a78bfa; font-weight: 700;'>{details_text}</span>")
        self.lbl_sub.setStyleSheet("font-size: 11.5px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(self.lbl_title)
        title_vbox.addWidget(self.lbl_sub)
        hdr_layout.addLayout(title_vbox, stretch=1)

        layout.addWidget(hdr_frame)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_profiles)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / %m Profiles (%p%)")
        layout.addWidget(self.progress_bar)

        # Status row
        status_hbox = QHBoxLayout()
        self.lbl_status = QLabel(f"Starting update for {self.total_profiles} selected profiles...")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11.5px;")
        status_hbox.addWidget(self.lbl_status, stretch=1)
        layout.addLayout(status_hbox)

    def set_progress(self, current: int, total: int, profile_name: str = "") -> None:
        """Update progress bar value and live status message."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        p_info = f" ({profile_name})" if profile_name else ""
        self.lbl_status.setText(f"Updating profile {current} of {total}{p_info}...")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def set_completed(self, success_msg: str = "") -> None:
        """Update state to completed with green checkmark styling."""
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.icon_lbl.setText("✅")
        self.lbl_title.setText("Bulk Updates Applied Successfully!")
        self.lbl_status.setText(success_msg or f"✅ Finished updating {self.total_profiles} profiles.")
        self.lbl_status.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()


class ExtensionInstallProgressDialog(QDialog):
    """
    Modern Dark Obsidian progress popup displayed while downloading and installing
    an extension from Chrome Web Store or local package archive.
    """

    def __init__(
        self,
        title: str = "📥 Downloading Extension...",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("🧩 Chrome Extension Downloader")
        self.setFixedSize(500, 215)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QProgressBar {
                border: 1px solid #232742;
                border-radius: 7px;
                text-align: center;
                background-color: #10121e;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                height: 24px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                border-radius: 6px;
            }
        """)

        # Auto-center over parent
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        self.icon_lbl = QLabel("🧩")
        self.icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(self.icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        self.lbl_sub = QLabel("Connecting to Chrome Web Store CDN...")
        self.lbl_sub.setStyleSheet("font-size: 11.5px; color: #34d399; font-weight: 600; background: transparent; border: none;")
        title_vbox.addWidget(self.lbl_title)
        title_vbox.addWidget(self.lbl_sub)
        hdr_layout.addLayout(title_vbox, stretch=1)

        layout.addWidget(hdr_frame)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)

        # Status row
        status_hbox = QHBoxLayout()
        self.lbl_status = QLabel("Initializing download...")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11.5px;")
        status_hbox.addWidget(self.lbl_status, stretch=1)
        layout.addLayout(status_hbox)

    def set_progress(self, percent: int, status_text: str = "", sub_title: str = "") -> None:
        """Update progress bar percentage and live status."""
        self.progress_bar.setValue(min(100, max(0, percent)))
        if status_text:
            self.lbl_status.setText(status_text)
        if sub_title:
            self.lbl_sub.setText(sub_title)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def set_completed(self, success_msg: str = "", ext_name: str = "") -> None:
        """Update state to completed with green checkmark styling."""
        self.progress_bar.setValue(100)
        self.icon_lbl.setText("✅")
        self.lbl_title.setText("Extension Installed Successfully!")
        if ext_name:
            disp = ext_name if len(ext_name) <= 30 else (ext_name[:27] + "...")
            self.lbl_sub.setText(f"Installed: <span style='color: #34d399; font-weight: 800;'>{disp}</span>")
        self.lbl_status.setText(success_msg or "✅ Finished downloading and registering extension.")
        self.lbl_status.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def set_failed(self, error_msg: str) -> None:
        """Update state to failed with warning styling."""
        self.icon_lbl.setText("❌")
        self.lbl_title.setText("Installation Failed")
        self.lbl_status.setText(error_msg)
        self.lbl_status.setStyleSheet("color: #f87171; font-weight: 700; font-size: 12px;")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()


class ExtensionDownloadThread(QThread):
    """Background worker to download CRX from Chrome Web Store CDN and register extension."""
    progress_changed = Signal(int, str, str)  # percent, status_text, sub_title
    finished_signal = Signal(bool, str, dict)  # success, message, record

    def __init__(self, crx_url: str, temp_crx_path: Path, parent=None):
        super().__init__(parent)
        self.crx_url = crx_url
        self.temp_crx_path = temp_crx_path

    def run(self):
        try:
            import urllib.request
            self.progress_changed.emit(5, "Connecting to Chrome Web Store...", "Connecting to CDN...")

            req = urllib.request.Request(
                self.crx_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )

            with urllib.request.urlopen(req, timeout=35) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024

                with open(self.temp_crx_path, "wb") as out_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 80) + 5
                            mb_down = downloaded / (1024 * 1024)
                            mb_tot = total_size / (1024 * 1024)
                            self.progress_changed.emit(
                                pct,
                                f"Downloading package: {mb_down:.1f} MB / {mb_tot:.1f} MB...",
                                f"Downloading ({pct}%)"
                            )
                        else:
                            mb_down = downloaded / (1024 * 1024)
                            self.progress_changed.emit(
                                50,
                                f"Downloading package: {mb_down:.1f} MB...",
                                "Downloading..."
                            )

            self.progress_changed.emit(90, "Unpacking & verifying manifest.json...", "Unpacking...")

            from extension_manager import ExtensionManager
            ext_mgr = ExtensionManager()
            ok, msg, record = ext_mgr.add_extension(str(self.temp_crx_path))
            try:
                self.temp_crx_path.unlink(missing_ok=True)
            except Exception:
                pass

            if ok and record:
                self.progress_changed.emit(100, f"✅ Successfully added '{record['name']}'!", "Completed")
                self.finished_signal.emit(True, msg, record)
            else:
                self.finished_signal.emit(False, msg or "Unpacking failed.", {})

        except Exception as e:
            try:
                self.temp_crx_path.unlink(missing_ok=True)
            except Exception:
                pass
            self.finished_signal.emit(False, f"Download error: {str(e)}", {})


class ExtensionsManagerDialog(QDialog):
    """Full Extensions Management Dialog to upload, toggle active states, and configure targets."""

    def __init__(self, profile_mgr=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        from extension_manager import ExtensionManager
        self.ext_mgr = ExtensionManager()

        self.setWindowTitle("🧩 Global Extension Manager")
        self.resize(840, 560)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        # Header bar
        header = QHBoxLayout()
        title = QLabel("🧩 Chrome Extensions Manager")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #89b4fa;")
        header.addWidget(title)

        btn_upload = QPushButton("➕ Upload Extension (.zip / .crx / Folder)")
        btn_upload.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #11111b;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #94e2d5; }
        """)
        btn_upload.clicked.connect(self.on_upload_extension)
        header.addWidget(btn_upload)
        layout.addLayout(header)

        sub = QLabel("Upload Chrome extensions or paste Web Store URLs, then configure which browser profiles automatically receive them.")
        sub.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(sub)

        # Chrome Web Store Direct URL Downloader Box
        url_box = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("🌐 Paste Chrome Web Store Extension URL (e.g. https://chromewebstore.google.com/detail/...)")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #181825;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 8px 14px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #89b4fa; }
        """)
        btn_dl_url = QPushButton("📥 Auto-Download")
        btn_dl_url.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #b4befe; }
        """)
        btn_dl_url.clicked.connect(self.on_download_webstore_url)
        url_box.addWidget(self.url_input)
        url_box.addWidget(btn_dl_url)
        layout.addLayout(url_box)

        # Extensions Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Status", "Extension Name", "Version", "Target Scope", "Actions"])
        self.table.setColumnWidth(0, 130)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 120)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 10px;
                gridline-color: #313244;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #11111b;
                color: #89b4fa;
                font-weight: bold;
                font-size: 13px;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #313244;
            }
        """)
        layout.addWidget(self.table)

        self.refresh_table()

        # Close button
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background-color: #313244; color: #cdd6f4; border-radius: 8px; padding: 10px 28px; font-weight: bold; font-size: 13px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def refresh_table(self) -> None:
        exts = self.ext_mgr.get_all_extensions()
        self.table.setRowCount(len(exts))

        for row, ext in enumerate(exts):
            self.table.setRowHeight(row, 56)
            ext_id = ext.get("id")
            is_active = ext.get("is_active", True)
            name = ext.get("name", "Extension")
            ver = ext.get("version", "1.0")
            target_mode = ext.get("target_mode", "all")

            # Active Status Toggle Button
            btn_status = QPushButton("✔ ACTIVE" if is_active else "✖ DISABLED")
            if is_active:
                btn_status.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px; padding: 6px 12px; font-size: 12px;")
            else:
                btn_status.setStyleSheet("background-color: #45475a; color: #cdd6f4; font-weight: bold; border-radius: 6px; padding: 6px 12px; font-size: 12px;")
            btn_status.clicked.connect(lambda _, eid=ext_id, ename=name, cur_state=is_active: self.on_toggle_active(eid, ename, not cur_state))

            cell_widget = QWidget()
            h = QHBoxLayout(cell_widget)
            h.addWidget(btn_status)
            h.setAlignment(Qt.AlignCenter)
            h.setContentsMargins(6, 4, 6, 4)
            self.table.setCellWidget(row, 0, cell_widget)

            # Name Item
            item_name = QTableWidgetItem(name)
            item_name.setForeground(QColor("#ffffff" if is_active else "#6c7086"))
            self.table.setItem(row, 1, item_name)

            # Version Item
            item_ver = QTableWidgetItem(f"v{ver}")
            item_ver.setForeground(QColor("#89b4fa"))
            item_ver.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_ver)

            # Target Scope Badge Button
            if target_mode == "all":
                target_text = "🌐 All Profiles"
            elif target_mode == "new_only":
                target_text = "✨ New Profiles Only"
            else:
                target_text = "👥 Groups Only"

            btn_target = QPushButton(target_text)
            btn_target.setStyleSheet("""
                QPushButton {
                    background-color: #1e1e2e;
                    color: #89b4fa;
                    border: 1px solid #89b4fa;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #313244; }
            """)
            btn_target.clicked.connect(lambda _, eid=ext_id, ename=name: self.on_edit_target(eid, ename))
            self.table.setCellWidget(row, 3, btn_target)

            # Delete Action Button
            btn_del = QPushButton("🗑️ Delete")
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: #f38ba8;
                    color: #11111b;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #f5e0dc; }
            """)
            btn_del.clicked.connect(lambda _, eid=ext_id, ename=name: self.on_delete_extension(eid, ename))
            self.table.setCellWidget(row, 4, btn_del)

    def _get_profile_groups(self) -> List[str]:
        if not self.profile_mgr:
            return ["Default"]
        if hasattr(self.profile_mgr, "get_all_groups"):
            return self.profile_mgr.get_all_groups()
        elif hasattr(self.profile_mgr, "get_groups"):
            return self.profile_mgr.get_groups()
        elif hasattr(self.profile_mgr, "groups"):
            return list(self.profile_mgr.groups)
        return ["Default"]

    def on_upload_extension(self) -> None:
        file_dialog = QFileDialog(self, "Select Extension (.zip / .crx or Folder)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Chrome Extensions (*.zip *.crx)")
        
        path_str = ""
        if file_dialog.exec():
            selected = file_dialog.selectedFiles()
            if selected:
                path_str = selected[0]

        if not path_str:
            folder = QFileDialog.getExistingDirectory(self, "Select Unpacked Extension Directory")
            if folder:
                path_str = folder

        if not path_str:
            return

        ok, msg, record = self.ext_mgr.add_extension(path_str)
        if ok and record:
            QMessageBox.information(self, "Success", msg)
            self.refresh_table()
        else:
            QMessageBox.warning(self, "Error", msg)

    def on_download_webstore_url(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please paste a valid Chrome Web Store extension URL.")
            return

        # Extract extension ID from Web Store URL (e.g. .../detail/name/ID)
        ext_id = ""
        parts = url.rstrip("/").split("/")
        if parts:
            candidate = parts[-1].split("?")[0]
            if len(candidate) == 32 and candidate.isalpha():
                ext_id = candidate

        if not ext_id:
            QMessageBox.warning(self, "Invalid URL", "Could not extract a valid 32-character Chrome Extension ID from the link.")
            return

        crx_url = f"https://clients2.google.com/service/update2/crx?response=redirect&os=win&arch=x64&os_arch=x86_64&nacl_arch=x86-64&prod=chromecrx&prodchannel=&prodversion=114.0.5735.199&acceptformat=crx2,crx3&x=id%3D{ext_id}%26uc"

        try:
            import urllib.request
            from config import EXTENSIONS_DIR

            temp_crx = EXTENSIONS_DIR / f"temp_{ext_id}.crx"
            QApplication.setOverrideCursor(Qt.WaitCursor)
            urllib.request.urlretrieve(crx_url, str(temp_crx))
            QApplication.restoreOverrideCursor()

            ok, msg, record = self.ext_mgr.add_extension(str(temp_crx))
            try:
                temp_crx.unlink(missing_ok=True)
            except Exception:
                pass

            if ok and record:
                QMessageBox.information(self, "Success", f"Successfully downloaded and added '{record['name']}' to extension list!")
                self.url_input.clear()
                self.refresh_table()
            else:
                QMessageBox.warning(self, "Error", f"Downloaded CRX could not be installed: {msg}")
        except Exception as err:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Error", f"Failed to download extension from Web Store: {str(err)}")

    def on_toggle_active(self, ext_id: str, ext_name: str, is_active: bool) -> None:
        self.ext_mgr.update_extension(ext_id, {"is_active": is_active})
        self.refresh_table()

    def on_edit_target(self, ext_id: str, ext_name: str) -> None:
        ext_rec = next((e for e in self.ext_mgr.get_all_extensions() if e.get("id") == ext_id), {})
        if not ext_rec.get("is_active", True):
            QMessageBox.information(
                self,
                "Extension Disabled",
                f"⚠️ '{ext_name}' is currently Disabled.\n\nPlease Enable the extension first before configuring its Target Scope."
            )
            return

        groups = self._get_profile_groups()
        cur_mode = ext_rec.get("target_mode", "manual")
        cur_grps = ext_rec.get("target_groups", [])
        dlg = ExtensionTargetDialog(ext_name, groups, current_mode=cur_mode, current_groups=cur_grps, parent=self)
        if dlg.exec() == QDialog.Accepted:
            mode, target_grps = dlg.get_selection()
            self.ext_mgr.apply_extension_to_profiles(ext_id, mode, target_grps, self.profile_mgr)
            self.refresh_table()

    def on_delete_extension(self, ext_id: str, ext_name: str) -> None:
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete extension '{ext_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.ext_mgr.delete_extension(ext_id)
            self.refresh_table()


class AddEditBookmarkDialog(QDialog):
    """Dialog to create or edit a custom bookmark entry, target groups, or bookmarklet script."""

    def __init__(
        self,
        name: str = "",
        url: str = "",
        target_mode: str = "all",
        target_groups: List[str] = None,
        available_groups: List[str] = None,
        parent: Optional[QWidget] = None,
        hide_target_scope: bool = False
    ) -> None:
        super().__init__(parent)
        self.available_groups = available_groups or ["Default"]
        self.group_checkboxes: List[Tuple[str, QCheckBox]] = []
        self.hide_target_scope = hide_target_scope

        self.setWindowTitle("Add New Bookmark" if hide_target_scope else "Bookmark Details & Target Scope")
        if hide_target_scope:
            self.setFixedSize(430, 240)
        else:
            self.resize(660, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #0c0f18;
                color: #ffffff;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            QLineEdit {
                background-color: #101322;
                border: 1px solid #283050;
                border-radius: 8px;
                padding: 6px 12px;
                color: #ffffff;
                font-size: 12.5px;
            }
            QLineEdit:focus {
                border: 1.5px solid #6366f1;
                background-color: #151930;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        if not hide_target_scope:
            # 2-Column Content Layout
            content_hbox = QHBoxLayout()
            content_hbox.setSpacing(12)

            # Left Column: Bookmark Info & Scope Selection
            left_vbox = QVBoxLayout()
            left_vbox.setSpacing(10)

            # Card 1: Bookmark Details
            card_info = QFrame()
            card_info.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                    border: 1px solid #232742;
                    border-radius: 12px;
                }
            """)
            info_vbox = QVBoxLayout(card_info)
            info_vbox.setContentsMargins(14, 12, 14, 12)
            info_vbox.setSpacing(8)

            lbl_name = QLabel("Bookmark Display Name:")
            lbl_name.setStyleSheet("font-weight: 700; color: #818cf8;")
            self.txt_name = QLineEdit(name)
            self.txt_name.setPlaceholderText("e.g. 📌 Token & Cookie or 🌐 Facebook")

            lbl_url = QLabel("Bookmark URL or JavaScript:")
            lbl_url.setStyleSheet("font-weight: 700; color: #a6e3a1;")
            self.txt_url = QLineEdit(url)
            self.txt_url.setPlaceholderText("https://... or javascript:...")

            info_vbox.addWidget(lbl_name)
            info_vbox.addWidget(self.txt_name)
            info_vbox.addWidget(lbl_url)
            info_vbox.addWidget(self.txt_url)
            left_vbox.addWidget(card_info)

            # Card 2: Target Scope Selection
            card_scope = QFrame()
            card_scope.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                    border: 1px solid #232742;
                    border-radius: 12px;
                }
            """)
            scope_vbox = QVBoxLayout(card_scope)
            scope_vbox.setContentsMargins(14, 12, 14, 12)
            scope_vbox.setSpacing(8)

            lbl_scope = QLabel("Target Scope:")
            lbl_scope.setStyleSheet("font-weight: 700; color: #fbbf24;")
            scope_vbox.addWidget(lbl_scope)

            self.btn_group = QButtonGroup(self)

            self.rad_all = QRadioButton("🌐 All Profiles (All & Future)")
            self.rad_all.setStyleSheet("font-size: 11.5px; font-weight: bold; color: #a6e3a1;")
            self.btn_group.addButton(self.rad_all)
            scope_vbox.addWidget(self.rad_all)

            self.rad_new_only = QRadioButton("✨ Future New Profiles Only")
            self.rad_new_only.setStyleSheet("font-size: 11.5px; font-weight: bold; color: #818cf8;")
            self.btn_group.addButton(self.rad_new_only)
            scope_vbox.addWidget(self.rad_new_only)

            self.rad_groups = QRadioButton("👥 Specific Profile Groups")
            self.rad_groups.setStyleSheet("font-size: 11.5px; font-weight: bold; color: #fbbf24;")
            self.btn_group.addButton(self.rad_groups)
            scope_vbox.addWidget(self.rad_groups)

            self.rad_manual = QRadioButton("💾 Save to Library Only (No Auto-Sync)")
            self.rad_manual.setStyleSheet("font-size: 11.5px; font-weight: bold; color: #94a3b8;")
            self.btn_group.addButton(self.rad_manual)
            scope_vbox.addWidget(self.rad_manual)

            if target_mode == "new_only":
                self.rad_new_only.setChecked(True)
            elif target_mode == "groups":
                self.rad_groups.setChecked(True)
            elif target_mode in ("manual_only", "library_only", "none"):
                self.rad_manual.setChecked(True)
            else:
                self.rad_all.setChecked(True)

            left_vbox.addWidget(card_scope)
            content_hbox.addLayout(left_vbox, stretch=1)

            # Right Column: Group Selector Panel
            self.grp_panel = QFrame()
            self.grp_panel.setStyleSheet("""
                QFrame {
                    background-color: #131626;
                    border: 1px solid #232742;
                    border-radius: 12px;
                }
            """)
            panel_layout = QVBoxLayout(self.grp_panel)
            panel_layout.setContentsMargins(14, 12, 14, 12)
            panel_layout.setSpacing(10)

            # Select All / Deselect All Controls Header
            action_bar = QHBoxLayout()
            lbl_select = QLabel("📁 Target Profile Groups:")
            lbl_select.setStyleSheet("font-size: 12px; font-weight: bold; color: #fbbf24; border: none; background: transparent;")

            btn_select_all = QPushButton("Select All")
            btn_select_all.setCursor(Qt.PointingHandCursor)
            btn_select_all.setStyleSheet("background: #191c2e; color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
            btn_select_all.clicked.connect(lambda: self._set_all_groups_checked(True))

            btn_deselect_all = QPushButton("Deselect All")
            btn_deselect_all.setCursor(Qt.PointingHandCursor)
            btn_deselect_all.setStyleSheet("background: #191c2e; color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
            btn_deselect_all.clicked.connect(lambda: self._set_all_groups_checked(False))

            action_bar.addWidget(lbl_select)
            action_bar.addStretch()
            action_bar.addWidget(btn_select_all)
            action_bar.addWidget(btn_deselect_all)
            panel_layout.addLayout(action_bar)

            # Scroll Area for Group Checkboxes
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setStyleSheet("""
                QScrollArea { border: none; background: transparent; }
                QScrollBar:vertical { background: #10121e; width: 6px; border-radius: 3px; }
                QScrollBar::handle:vertical { background: #282d47; border-radius: 3px; }
                QScrollBar::handle:vertical:hover { background: #6366f1; }
            """)
            scroll_content = QWidget()
            scroll_content.setStyleSheet("background: transparent;")
            self.groups_vbox = QVBoxLayout(scroll_content)
            self.groups_vbox.setContentsMargins(2, 2, 2, 2)
            self.groups_vbox.setSpacing(6)

            tg_set = set(target_groups or [])
            for g in self.available_groups:
                chk = QCheckBox(f"📁  {g}")
                chk.setChecked(g in tg_set)
                chk.setStyleSheet("""
                    QCheckBox {
                        color: #cdd6f4;
                        font-size: 12px;
                        font-weight: bold;
                        padding: 6px 10px;
                        background-color: #10121e;
                        border: 1px solid #282d47;
                        border-radius: 8px;
                    }
                    QCheckBox:hover {
                        border-color: #818cf8;
                        background-color: #181c32;
                    }
                    QCheckBox:checked {
                        color: #a6e3a1;
                        border-color: #10b981;
                        background-color: #14281f;
                    }
                """)
                self.group_checkboxes.append((g, chk))
                self.groups_vbox.addWidget(chk)

            self.groups_vbox.addStretch()
            scroll_area.setWidget(scroll_content)
            panel_layout.addWidget(scroll_area, stretch=1)

            content_hbox.addWidget(self.grp_panel, stretch=1)
            layout.addLayout(content_hbox)

            # Toggle Group Panel Enabled/Opacity State based on Radio Choice
            def update_group_panel_state(*args):
                is_active = self.rad_groups.isChecked()
                self.grp_panel.setVisible(is_active)
                if is_active:
                    self.resize(660, 440)
                    self.grp_panel.setStyleSheet("""
                        QFrame {
                            background-color: #131626;
                            border: 1.5px solid #6366f1;
                            border-radius: 12px;
                        }
                    """)
                    lbl_select.setStyleSheet("font-size: 12px; font-weight: bold; color: #fbbf24; border: none; background: transparent;")
                else:
                    self.resize(450, 390)

            self.rad_all.toggled.connect(update_group_panel_state)
            self.rad_new_only.toggled.connect(update_group_panel_state)
            self.rad_groups.toggled.connect(update_group_panel_state)
            self.rad_manual.toggled.connect(update_group_panel_state)
            update_group_panel_state()

        else:
            # Clean Modern Form Layout when target scope is hidden
            lbl_name = QLabel("Bookmark Display Name:")
            lbl_name.setStyleSheet("font-weight: 700; color: #818cf8; font-size: 12px;")
            self.txt_name = QLineEdit(name)
            self.txt_name.setFixedHeight(34)
            self.txt_name.setPlaceholderText("e.g. Facebook or Google")

            lbl_url = QLabel("Bookmark URL or JavaScript:")
            lbl_url.setStyleSheet("font-weight: 700; color: #a6e3a1; font-size: 12px;")
            self.txt_url = QLineEdit(url)
            self.txt_url.setFixedHeight(34)
            self.txt_url.setPlaceholderText("https://... or javascript:...")
            self.txt_url.returnPressed.connect(self.accept)

            layout.addWidget(lbl_name)
            layout.addWidget(self.txt_name)
            layout.addSpacing(2)
            layout.addWidget(lbl_url)
            layout.addWidget(self.txt_url)

        # Action Buttons Row
        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 8, 0, 0)
        btn_box.setSpacing(10)
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(32)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #232742;
                color: #ffffff;
                border-color: #4b5585;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("✓ Save Bookmark")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(32)
        btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
            }
        """)
        btn_save.clicked.connect(self.accept)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _set_all_groups_checked(self, checked: bool) -> None:
        for _, chk in self.group_checkboxes:
            chk.setChecked(checked)

    def get_data(self) -> Tuple[str, str, str, List[str]]:
        mode = "all"
        sel_groups: List[str] = []
        if not getattr(self, "hide_target_scope", False):
            if hasattr(self, "rad_new_only") and self.rad_new_only.isChecked():
                mode = "new_only"
            elif hasattr(self, "rad_groups") and self.rad_groups.isChecked():
                mode = "groups"
            elif hasattr(self, "rad_manual") and self.rad_manual.isChecked():
                mode = "manual_only"
            if hasattr(self, "group_checkboxes"):
                sel_groups = [g for g, chk in self.group_checkboxes if chk.isChecked()]

        raw_name = self.txt_name.text().strip() or "Bookmark"
        raw_url = self.txt_url.text().strip()
        try:
            from bookmark_manager import normalize_bookmark_url
            clean_url = normalize_bookmark_url(raw_url)
        except Exception:
            clean_url = raw_url if raw_url.startswith(("http://", "https://", "javascript:")) else (f"https://{raw_url}" if raw_url else "https://google.com")
        return raw_name, clean_url, mode, sel_groups

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_dialog_over_parent(self, self.parent())


class BookmarkManagerDialog(QDialog):
    """Dialog to manage bookmarks list, target scopes, and auto-sync to Chrome profile bookmark bars."""

    def __init__(self, profile_mgr=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        from bookmark_manager import BookmarkManager
        self.bm_mgr = BookmarkManager()

        self.setWindowTitle("🔖 Chrome Auto-Bookmarks Manager")
        self.resize(780, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        header_hbox = QHBoxLayout()
        header_vbox = QVBoxLayout()
        title = QLabel("🔖  <b>Chrome Auto-Bookmarks Manager</b>")
        title.setStyleSheet("font-size: 16px; color: #818cf8; background: transparent; border: none;")
        sub = QLabel("Configure custom site links or scripts and set target profile groups for automatic Bookmark Bar display.")
        sub.setStyleSheet("color: #94a3b8; font-size: 11.5px; background: transparent; border: none;")
        header_vbox.addWidget(title)
        header_vbox.addWidget(sub)
        header_hbox.addLayout(header_vbox, stretch=1)

        btn_add = QPushButton("➕ Add Bookmark")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 7px 18px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                border-color: #818cf8;
            }
        """)
        btn_add.clicked.connect(self.on_add_bookmark)
        header_hbox.addWidget(btn_add)
        layout.addLayout(header_hbox)

        self.tbl_bm = QTableWidget()
        self.tbl_bm.setColumnCount(4)
        self.tbl_bm.setHorizontalHeaderLabels(["Name", "URL / Script", "Target Scope", "Actions"])
        self.tbl_bm.setColumnWidth(0, 160)
        self.tbl_bm.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_bm.setColumnWidth(2, 170)
        self.tbl_bm.setColumnWidth(3, 175)
        self.tbl_bm.setStyleSheet("""
            QTableWidget {
                background-color: #131626;
                color: #cdd6f4;
                border: 1px solid #232742;
                border-radius: 12px;
                gridline-color: #1e2238;
                outline: 0;
            }
            QTableWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #1e2238;
            }
            QTableWidget::item:selected {
                background-color: #1e2240;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #10121e;
                color: #818cf8;
                font-weight: 800;
                font-size: 11.5px;
                padding: 9px 10px;
                border: none;
                border-bottom: 1px solid #232742;
            }
            QScrollBar:vertical {
                background: #10121e;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #282d47;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6366f1;
            }
        """)
        layout.addWidget(self.tbl_bm)

        btn_sync_all = QPushButton("⚡ Sync Bookmarks to All Profiles Now")
        btn_sync_all.setCursor(Qt.PointingHandCursor)
        btn_sync_all.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 10px;
                font-weight: 800;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                border-color: #818cf8;
            }
        """)
        btn_sync_all.clicked.connect(self.on_sync_all_profiles)
        layout.addWidget(btn_sync_all)

        self.refresh_table()

    def _get_groups(self) -> List[str]:
        if self.profile_mgr and hasattr(self.profile_mgr, "get_groups"):
            return self.profile_mgr.get_groups()
        return ["Default"]

    def refresh_table(self) -> None:
        bms = self.bm_mgr.get_all_bookmarks()
        self.tbl_bm.setRowCount(len(bms))
        for row, b in enumerate(bms):
            self.tbl_bm.setRowHeight(row, 46)
            bm_id = b.get("id")
            name = b.get("name", "Bookmark")
            url = b.get("url", "")
            mode = b.get("target_mode", "all")
            target_groups = b.get("target_groups", [])

            item_name = QTableWidgetItem(f"📌 {name}")
            item_name.setForeground(QColor("#ffffff"))
            item_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.tbl_bm.setItem(row, 0, item_name)

            disp_url = url[:45] + "..." if len(url) > 45 else url
            item_url = QTableWidgetItem(disp_url)
            item_url.setForeground(QColor("#a6e3a1") if "javascript:" in url else QColor("#818cf8"))
            self.tbl_bm.setItem(row, 1, item_url)

            # Target Scope Badge
            if mode == "all":
                scope_text = "🌐 All Profiles"
                scope_color = "#a6e3a1"
            elif mode == "new_only":
                scope_text = "✨ New Profiles"
                scope_color = "#818cf8"
            elif mode in ("manual_only", "library_only", "none"):
                scope_text = "💾 Library Only"
                scope_color = "#94a3b8"
            else:
                scope_text = f"👥 Groups ({', '.join(target_groups)})" if target_groups else "👥 Groups Only"
                scope_color = "#fbbf24"

            item_scope = QTableWidgetItem(scope_text)
            item_scope.setForeground(QColor(scope_color))
            item_scope.setTextAlignment(Qt.AlignCenter)
            self.tbl_bm.setItem(row, 2, item_scope)

            btn_box = QWidget()
            btn_box.setStyleSheet("background: transparent;")
            h = QHBoxLayout(btn_box)
            h.setContentsMargins(4, 4, 4, 4)
            h.setSpacing(6)

            btn_edit = QPushButton("✏️ Edit")
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setStyleSheet("""
                QPushButton {
                    background-color: #191c2e;
                    color: #fbbf24;
                    border: 1px solid rgba(251, 191, 36, 0.35);
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11.5px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #232742;
                    border-color: #fbbf24;
                }
            """)
            btn_edit.clicked.connect(lambda _, bdata=b: self.on_edit_bookmark(bdata))

            btn_del = QPushButton("🗑️ Delete")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.14);
                    color: #f87171;
                    border: 1px solid rgba(239, 68, 68, 0.4);
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11.5px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: rgba(239, 68, 68, 0.25);
                    border-color: #ef4444;
                }
            """)
            btn_del.clicked.connect(lambda _, bid=bm_id, bname=name: self.on_delete_bookmark(bid, bname))

            h.addWidget(btn_edit)
            h.addWidget(btn_del)
            self.tbl_bm.setCellWidget(row, 3, btn_box)

    def on_add_bookmark(self) -> None:
        dlg = AddEditBookmarkDialog("", "", "all", [], self._get_groups(), self)
        if dlg.exec() == QDialog.Accepted:
            name, url, mode, sel_grps = dlg.get_data()
            if name and url:
                self.bm_mgr.add_bookmark(name, url, target_mode=mode, target_groups=sel_grps)
                self.refresh_table()
                if mode != "manual_only":
                    self.on_sync_all_profiles(silent=True)

    def on_edit_bookmark(self, bm_data: Dict[str, Any]) -> None:
        dlg = AddEditBookmarkDialog(
            bm_data.get("name", ""),
            bm_data.get("url", ""),
            bm_data.get("target_mode", "all"),
            bm_data.get("target_groups", []),
            self._get_groups(),
            self
        )
        if dlg.exec() == QDialog.Accepted:
            name, url, mode, sel_grps = dlg.get_data()
            if name and url:
                self.bm_mgr.update_bookmark(
                    bm_data.get("id"),
                    {"name": name, "url": url, "target_mode": mode, "target_groups": sel_grps}
                )
                self.refresh_table()
                if mode != "manual_only":
                    self.on_sync_all_profiles(silent=True)

    def on_delete_bookmark(self, bm_id: str, name: str) -> None:
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete bookmark '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.bm_mgr.delete_bookmark(bm_id)
            self.refresh_table()
            self.on_sync_all_profiles(silent=True)

    def on_sync_all_profiles(self, silent: bool = False) -> None:
        if not self.profile_mgr:
            return
        matched_profiles_count = 0
        all_profiles = self.profile_mgr.get_all_profiles()
        total_count = len(all_profiles)

        for p in all_profiles:
            p_folder = self.profile_mgr.get_profile_folder(p["id"])
            res = self.bm_mgr.sync_bookmarks_to_profile(p_folder, p)
            if res > 0:
                matched_profiles_count += 1

        if not silent:
            QMessageBox.information(
                self,
                "Bookmarks Synced",
                f"Successfully synced group-targeted bookmarks to {matched_profiles_count} matching profiles (out of {total_count} total profiles)!"
            )


class BulkCreateProfilesDialog(QDialog):
    """
    Dialog to bulk create multiple browser profiles simultaneously
    with Group targeting, Start Page URL, Extension selection, Bookmarks sync,
    and sequential Proxy IP distribution.
    """

    def __init__(self, profile_mgr=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr

        try:
            from extension_manager import ExtensionManager
            self.ext_mgr = ExtensionManager()
        except Exception:
            self.ext_mgr = None

        try:
            from bookmark_manager import BookmarkManager
            self.bm_mgr = BookmarkManager()
        except Exception:
            self.bm_mgr = None

        self.setWindowTitle("🚀 Bulk Profile Creator")
        self.resize(740, 640)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d18;
                color: #ffffff;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            QLineEdit, QSpinBox, QComboBox, QTextEdit {
                background-color: #101222;
                color: #ffffff;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #6366f1;
                background-color: #14172e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 10, 16, 12)

        # Ultra-Compact Modern Header Bar
        hdr_box = QHBoxLayout()
        hdr_box.setContentsMargins(2, 0, 2, 0)
        lbl_icon_title = QLabel("🚀  <b>Bulk Profile Generator</b>")
        lbl_icon_title.setStyleSheet("font-size: 14px; color: #ffffff; background: transparent; border: none; font-weight: 800;")
        
        lbl_badge = QLabel("✨ Batch Creator")
        lbl_badge.setStyleSheet("background: rgba(99, 102, 241, 0.12); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 5px; padding: 1px 6px; font-size: 10px; font-weight: 700;")
        
        hdr_box.addWidget(lbl_icon_title)
        hdr_box.addSpacing(6)
        hdr_box.addWidget(lbl_badge)
        hdr_box.addStretch()
        layout.addLayout(hdr_box)

        # Ultra-Slim Form Container Card
        form_card = QFrame()
        form_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141829, stop:1 #0e101d);
                border: 1px solid #232742;
                border-radius: 8px;
            }
        """)
        form_vbox = QVBoxLayout(form_card)
        form_vbox.setContentsMargins(10, 6, 10, 6)
        form_vbox.setSpacing(6)

        # Row 1: Count, Group, Start URL in a single slim row
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)

        # Count (Clean numeric input without arrow buttons)
        lbl_count = QLabel("Profiles:")
        lbl_count.setStyleSheet("font-weight: 700; color: #ffffff; font-size: 11px;")
        self.spn_count = QSpinBox()
        self.spn_count.setButtonSymbols(QSpinBox.NoButtons)
        self.spn_count.setAlignment(Qt.AlignCenter)
        self.spn_count.setRange(1, 500)
        self.spn_count.setValue(5)
        self.spn_count.setFixedWidth(50)
        self.spn_count.setFixedHeight(28)
        self.spn_count.setStyleSheet("""
            QSpinBox {
                background: #090a14;
                color: #818cf8;
                font-weight: bold;
                border: 1px solid #282d47;
                padding: 1px 4px;
                border-radius: 5px;
                font-size: 12px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                height: 0px;
                border: none;
            }
        """)

        # Group
        lbl_group = QLabel("Group:")
        lbl_group.setStyleSheet("font-weight: 700; color: #ffffff; font-size: 11px;")
        self.cmb_group = QComboBox()
        self.cmb_group.setEditable(False)
        self.cmb_group.setFixedHeight(28)
        self.cmb_group.setMinimumWidth(130)
        self.cmb_group.setStyleSheet("""
            QComboBox {
                background: #090a14;
                color: #fbbf24;
                font-weight: bold;
                border: 1px solid #282d47;
                padding: 1px 6px;
                border-radius: 5px;
                font-size: 11px;
            }
        """)
        groups = self.profile_mgr.get_groups() if self.profile_mgr else ["Default"]
        for g in groups:
            self.cmb_group.addItem(f"📁 {g}", g)
        self.cmb_group.addItem("➕ Create Group...", "__NEW__")
        self.cmb_group.currentIndexChanged.connect(self.on_group_changed)

        # Start URL
        lbl_url = QLabel("Start URL:")
        lbl_url.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px;")
        self.txt_start_url = QLineEdit()
        self.txt_start_url.setFixedHeight(28)
        self.txt_start_url.setPlaceholderText("https://... (Optional)")
        self.txt_start_url.setStyleSheet("background: #090a14; color: #ffffff; border: 1px solid #282d47; border-radius: 5px; padding: 1px 8px; font-size: 11px;")

        row1_layout.addWidget(lbl_count)
        row1_layout.addWidget(self.spn_count)
        row1_layout.addSpacing(6)
        row1_layout.addWidget(lbl_group)
        row1_layout.addWidget(self.cmb_group)
        row1_layout.addSpacing(6)
        row1_layout.addWidget(lbl_url)
        row1_layout.addWidget(self.txt_start_url, stretch=1)

        form_vbox.addLayout(row1_layout)

        # Row 2: Slim Proxy Input
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(8)
        lbl_proxy_title = QLabel("🔌 <b>Proxies:</b>")
        lbl_proxy_title.setStyleSheet("font-size: 10.5px; color: #cbd5e1;")
        
        self.txt_proxies = QTextEdit()
        self.txt_proxies.setPlaceholderText("Paste proxy IPs (Optional - 1 per line, e.g. IP:Port or IP:Port:User:Pass)")
        self.txt_proxies.setFixedHeight(28)
        self.txt_proxies.setStyleSheet("background: #090a14; color: #a6e3a1; font-family: Consolas, monospace; font-size: 10.5px; border: 1px solid #232742; padding: 2px 6px; border-radius: 5px;")
        
        row2_layout.addWidget(lbl_proxy_title)
        row2_layout.addWidget(self.txt_proxies, stretch=1)
        form_vbox.addLayout(row2_layout)

        layout.addWidget(form_card)

        # ==========================================
        # Add-ons Modern Segmented Tab Widget (Full Height Expansion)
        # ==========================================
        self.addons_tabs = QTabWidget()
        self.addons_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #232742;
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141829, stop:1 #0f111e);
                padding: 8px;
            }
            QTabBar::tab {
                background: #111424;
                color: #94a3b8;
                border: 1px solid #232742;
                border-radius: 7px;
                padding: 5px 14px;
                margin-right: 6px;
                font-weight: 700;
                font-size: 11px;
            }
            QTabBar::tab:hover {
                background: #191e36;
                color: #ffffff;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
                color: #ffffff;
                border: 1px solid #818cf8;
            }
        """)

        # Tab 1: 🔖 Bookmarks Bar
        tab_bm = QWidget()
        tab_bm.setStyleSheet("background: transparent;")
        bm_vbox = QVBoxLayout(tab_bm)
        bm_vbox.setContentsMargins(2, 2, 2, 2)
        bm_vbox.setSpacing(6)

        bm_hdr = QHBoxLayout()
        lbl_bm_hint = QLabel("Select bookmarks to auto-sync on browser launch:")
        lbl_bm_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        btn_add_bm = QPushButton("➕ Add Bookmark")
        btn_add_bm.setCursor(Qt.PointingHandCursor)
        btn_add_bm.setStyleSheet("background: #191c2e; color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.35); border-radius: 5px; padding: 2px 8px; font-size: 10.5px; font-weight: bold;")
        btn_add_bm.clicked.connect(self.on_add_new_bookmark)

        btn_bm_all = QPushButton("Select All")
        btn_bm_all.setCursor(Qt.PointingHandCursor)
        btn_bm_all.setStyleSheet("background: #191c2e; color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: bold;")
        btn_bm_all.clicked.connect(lambda: self._set_all_bm_checked(True))
        btn_bm_none = QPushButton("Deselect All")
        btn_bm_none.setCursor(Qt.PointingHandCursor)
        btn_bm_none.setStyleSheet("background: #191c2e; color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: bold;")
        btn_bm_none.clicked.connect(lambda: self._set_all_bm_checked(False))

        bm_hdr.addWidget(lbl_bm_hint)
        bm_hdr.addStretch()
        bm_hdr.addWidget(btn_add_bm)
        bm_hdr.addWidget(btn_bm_all)
        bm_hdr.addWidget(btn_bm_none)
        bm_vbox.addLayout(bm_hdr)

        self.bm_checkboxes = []
        self.bm_scroll = QScrollArea()
        self.bm_scroll.setWidgetResizable(True)
        self.bm_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bm_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.bm_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.bm_grid_container = QWidget()
        self.bm_grid_container.setStyleSheet("background: transparent; border: none;")
        self._reload_bookmarks_grid()
        self.bm_scroll.setWidget(self.bm_grid_container)
        bm_vbox.addWidget(self.bm_scroll, stretch=1)

        self.addons_tabs.addTab(tab_bm, "🔖  Bookmarks Bar")

        # Tab 2: 🧩 Extensions
        tab_ext = QWidget()
        tab_ext.setStyleSheet("background: transparent;")
        ext_vbox = QVBoxLayout(tab_ext)
        ext_vbox.setContentsMargins(2, 2, 2, 2)
        ext_vbox.setSpacing(6)

        ext_hdr = QHBoxLayout()
        lbl_ext_hint = QLabel("Select Chrome extensions to auto-install:")
        lbl_ext_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        btn_ext_all = QPushButton("Select All")
        btn_ext_all.setCursor(Qt.PointingHandCursor)
        btn_ext_all.setStyleSheet("background: #191c2e; color: #a6e3a1; border: 1px solid rgba(166, 227, 161, 0.3); border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: bold;")
        btn_ext_all.clicked.connect(lambda: self._set_all_ext_checked(True))
        btn_ext_none = QPushButton("Deselect All")
        btn_ext_none.setCursor(Qt.PointingHandCursor)
        btn_ext_none.setStyleSheet("background: #191c2e; color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: bold;")
        btn_ext_none.clicked.connect(lambda: self._set_all_ext_checked(False))

        ext_hdr.addWidget(lbl_ext_hint)
        ext_hdr.addStretch()
        ext_hdr.addWidget(btn_ext_all)
        ext_hdr.addWidget(btn_ext_none)
        ext_vbox.addLayout(ext_hdr)

        self.ext_checkboxes = []
        all_exts = [e for e in self.ext_mgr.get_all_extensions() if e.get("is_active", True)] if self.ext_mgr else []
        if all_exts:
            ext_scroll = QScrollArea()
            ext_scroll.setWidgetResizable(True)
            ext_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            ext_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            ext_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

            ext_content = QWidget()
            ext_content.setStyleSheet("background: transparent; border: none;")
            ext_flow = FlowLayout(ext_content, margin=0, spacing=10)

            for ext in all_exts:
                ename = ext.get("name", "Extension")
                epath = ext.get("path", "")
                btn_chip = QPushButton(f"🧩  {ename}")
                btn_chip.setToolTip(ename)
                btn_chip.setCheckable(True)
                btn_chip.setChecked(False)
                btn_chip.setCursor(Qt.PointingHandCursor)
                btn_chip.setStyleSheet("""
                    QPushButton {
                        color: #94a3b8;
                        font-size: 12px;
                        font-weight: 700;
                        padding: 7px 16px;
                        background-color: #080a14;
                        border: 1.5px solid #1f274d;
                        border-radius: 16px;
                        text-align: center;
                    }
                    QPushButton:hover {
                        border-color: #34d399;
                        background-color: #131d30;
                        color: #ffffff;
                    }
                    QPushButton:checked {
                        color: #34d399;
                        border-color: #10b981;
                        background-color: rgba(16, 185, 129, 0.18);
                        font-weight: 800;
                    }
                """)
                self.ext_checkboxes.append((epath, btn_chip))
                ext_flow.addWidget(btn_chip)

            ext_scroll.setWidget(ext_content)
            ext_vbox.addWidget(ext_scroll, stretch=1)
        else:
            lbl_no_ext = QLabel("🧩 No active extensions enabled")
            lbl_no_ext.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 20px; qproperty-alignment: AlignCenter;")
            ext_vbox.addWidget(lbl_no_ext, stretch=1)

        self.addons_tabs.addTab(tab_ext, "🧩  Extensions")

        # Tab 3: ⚡ Quick Scripts
        tab_sc = QWidget()
        tab_sc.setStyleSheet("background: transparent;")
        sc_vbox = QVBoxLayout(tab_sc)
        sc_vbox.setContentsMargins(2, 2, 2, 2)
        sc_vbox.setSpacing(6)

        sc_hdr = QHBoxLayout()
        lbl_sc_hint = QLabel("Select quick action shortcut buttons on profile card:")
        lbl_sc_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        btn_sc_all = QPushButton("Select All")
        btn_sc_all.setCursor(Qt.PointingHandCursor)
        btn_sc_all.setStyleSheet("background: #191c2e; color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: bold;")
        btn_sc_all.clicked.connect(lambda: [chk.setChecked(True) for _, chk in self.script_checkboxes])
        btn_sc_none = QPushButton("Deselect All")
        btn_sc_none.setCursor(Qt.PointingHandCursor)
        btn_sc_none.setStyleSheet("background: #191c2e; color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: bold;")
        btn_sc_none.clicked.connect(lambda: [chk.setChecked(False) for _, chk in self.script_checkboxes])

        sc_hdr.addWidget(lbl_sc_hint)
        sc_hdr.addStretch()
        sc_hdr.addWidget(btn_sc_all)
        sc_hdr.addWidget(btn_sc_none)
        sc_vbox.addLayout(sc_hdr)

        self.script_checkboxes = []
        available_bulk_scripts = [
            {"id": "fb_account_info", "name": "FB Info", "icon": "ℹ️", "desc": "View credentials, notes & live cookies on card"},
            {"id": "fb_relogin", "name": "FB-Relogin", "icon": "🔑", "desc": "1-Click automated background account re-login"},
            {"id": "fb_quick_page_create", "name": "Page Create", "icon": "📄", "desc": "1-Click instant Facebook page creator studio"},
            {"id": "fb_language_converter", "name": "FB-Language", "icon": "🌐", "desc": "1-Click fast Facebook language converter"},
            {"id": "fb_business_creator", "name": "FBBM", "icon": "⚡", "desc": "1-Click instant Facebook Business Manager creator"},
            {"id": "fb_bulk_video_uploader", "name": "FBVUP", "icon": "🎬", "desc": "1-Click automated Facebook bulk video uploader"}
        ]

        try:
            from bot_license_manager import BotLicenseManager
            blm = BotLicenseManager()
            available_bulk_scripts = [sc for sc in available_bulk_scripts if not blm.is_item_deactivated("script", sc["id"])]
        except Exception:
            pass

        if available_bulk_scripts:
            sc_scroll = QScrollArea()
            sc_scroll.setWidgetResizable(True)
            sc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sc_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            sc_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

            sc_content = QWidget()
            sc_content.setStyleSheet("background: transparent; border: none;")
            sc_flow = FlowLayout(sc_content, margin=0, spacing=10)

            for sc_item in available_bulk_scripts:
                sid = sc_item["id"]
                sname = sc_item["name"]
                sicon = sc_item.get("icon", "⚡")
                sdesc = sc_item["desc"]
                btn_chip = QPushButton(f"{sicon}  {sname}")
                btn_chip.setToolTip(sdesc)
                btn_chip.setCheckable(True)
                btn_chip.setChecked(False)
                btn_chip.setCursor(Qt.PointingHandCursor)
                btn_chip.setStyleSheet("""
                    QPushButton {
                        color: #94a3b8;
                        font-size: 12px;
                        font-weight: 700;
                        padding: 7px 16px;
                        background-color: #080a14;
                        border: 1.5px solid #1f274d;
                        border-radius: 16px;
                        text-align: center;
                    }
                    QPushButton:hover {
                        border-color: #818cf8;
                        background-color: #141b32;
                        color: #ffffff;
                    }
                    QPushButton:checked {
                        color: #818cf8;
                        border-color: #6366f1;
                        background-color: rgba(129, 140, 248, 0.18);
                        font-weight: 800;
                    }
                """)
                self.script_checkboxes.append((sid, btn_chip))
                sc_flow.addWidget(btn_chip)

            sc_scroll.setWidget(sc_content)
            sc_vbox.addWidget(sc_scroll, stretch=1)
        else:
            lbl_no_sc = QLabel("⚡ No active scripts enabled")
            lbl_no_sc.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 20px; qproperty-alignment: AlignCenter;")
            sc_vbox.addWidget(lbl_no_sc, stretch=1)

        self.addons_tabs.addTab(tab_sc, "⚡  Quick Scripts")

        layout.addWidget(self.addons_tabs, stretch=1)

        # Action Buttons Footer
        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 4, 0, 0)
        btn_box.setSpacing(12)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #151828;
                color: #94a3b8;
                font-size: 12.5px;
                font-weight: 700;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #20253d;
                color: #ffffff;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_create = QPushButton("🚀 Create Profiles Now")
        btn_create.setFixedHeight(38)
        btn_create.setCursor(Qt.PointingHandCursor)
        btn_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                font-size: 13px;
                font-weight: 800;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
            }
        """)
        btn_create.clicked.connect(self.on_create_bulk)
        btn_box.addWidget(btn_create)

        layout.addLayout(btn_box)

    def on_group_changed(self, idx: int) -> None:
        val = self.cmb_group.itemData(idx)
        if val == "__NEW__":
            self.cmb_group.blockSignals(True)
            new_g, ok = QInputDialog.getText(self, "Create New Group", "Enter new profile group name:")
            if ok and new_g.strip():
                gname = new_g.strip()
                if self.profile_mgr:
                    self.profile_mgr.add_group(gname)
                new_idx = max(0, self.cmb_group.count() - 1)
                self.cmb_group.insertItem(new_idx, f"📁  {gname}", gname)
                self.cmb_group.setCurrentIndex(new_idx)
            else:
                self.cmb_group.setCurrentIndex(0)
            self.cmb_group.blockSignals(False)

    def on_add_new_bookmark(self) -> None:
        if not self.bm_mgr:
            return
        groups = self.profile_mgr.get_groups() if self.profile_mgr else ["Default"]
        dlg = AddEditBookmarkDialog("", "", "all", [], groups, self, hide_target_scope=True)
        if dlg.exec() == QDialog.Accepted:
            name, url, mode, sel_grps = dlg.get_data()
            if name and url:
                self.bm_mgr.add_bookmark(name, url, target_mode=mode, target_groups=sel_grps)
                self._reload_bookmarks_grid(auto_check_new=name)

    def _reload_bookmarks_grid(self, auto_check_new: Optional[str] = None) -> None:
        if self.bm_grid_container.layout():
            bm_lay = self.bm_grid_container.layout()
            while bm_lay.count():
                item = bm_lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            bm_lay = FlowLayout(self.bm_grid_container, margin=0, spacing=10)

        self.bm_checkboxes.clear()
        if self.bm_mgr:
            all_bms = self.bm_mgr.get_all_bookmarks()
            if all_bms:
                for bm in all_bms:
                    bname = bm.get("name", "Bookmark")
                    burl = bm.get("url", "")
                    btn_chip = QPushButton(f"🔖  {bname}")
                    btn_chip.setToolTip(f"{bname}\n{burl}")
                    btn_chip.setCheckable(True)
                    if auto_check_new and bname.lower() == auto_check_new.lower():
                        btn_chip.setChecked(True)
                    else:
                        btn_chip.setChecked(False)
                    btn_chip.setCursor(Qt.PointingHandCursor)
                    btn_chip.setStyleSheet("""
                        QPushButton {
                            color: #94a3b8;
                            font-size: 12px;
                            font-weight: 700;
                            padding: 7px 16px;
                            background-color: #080a14;
                            border: 1.5px solid #1f274d;
                            border-radius: 16px;
                            text-align: center;
                        }
                        QPushButton:hover {
                            border-color: #f59e0b;
                            background-color: #1a1710;
                            color: #ffffff;
                        }
                        QPushButton:checked {
                            color: #f59e0b;
                            border-color: #d97706;
                            background-color: rgba(245, 158, 11, 0.18);
                            font-weight: 800;
                        }
                    """)
                    self.bm_checkboxes.append((bm, btn_chip))
                    bm_lay.addWidget(btn_chip)
            else:
                lbl_no_bm = QLabel("No bookmarks currently saved.")
                lbl_no_bm.setStyleSheet("color: #64748b; font-size: 11.5px; font-style: italic; border: none; padding: 4px;")
                bm_lay.addWidget(lbl_no_bm)

    def _set_all_ext_checked(self, checked: bool) -> None:
        for _, chk in self.ext_checkboxes:
            chk.setChecked(checked)

    def _set_all_bm_checked(self, checked: bool) -> None:
        for _, chk in self.bm_checkboxes:
            chk.setChecked(checked)

    def on_create_bulk(self) -> None:
        count = self.spn_count.value()
        prefix = ""
        group_val = self.cmb_group.currentData()
        if not group_val or group_val == "__NEW__":
            group_val = self.cmb_group.currentText().replace("📁", "").replace("➕", "").replace("Create Group...", "").strip() or "Default"

        start_url = self.txt_start_url.text().strip()
        raw_proxies = self.txt_proxies.toPlainText().splitlines()

        selected_exts = [path for path, chk in self.ext_checkboxes if chk.isChecked()]
        selected_bms = [bm for bm, chk in self.bm_checkboxes if chk.isChecked()]
        selected_scripts = [sid for sid, chk in self.script_checkboxes if chk.isChecked()]

        if not self.profile_mgr:
            QMessageBox.warning(self, "Error", "Profile Manager not available.")
            return

        params = {
            "count": count,
            "name_prefix": prefix,
            "group": group_val,
            "start_url": start_url,
            "proxy_lines": raw_proxies,
            "extensions": selected_exts,
            "assigned_scripts": selected_scripts,
            "selected_bookmarks": selected_bms
        }

        if count <= 2:
            created = self.profile_mgr.bulk_create_profiles(**params)
            if self.parent() and hasattr(self.parent(), "refresh_all_views"):
                self.parent().refresh_all_views()
            QMessageBox.information(
                self,
                "Bulk Creation Success",
                f"🎉 Successfully created {len(created)} browser profiles in Group '{group_val}'!"
            )
            self.accept()
            return

        from core.ui.progress_dialog import ModernProgressDialog, BulkCreateWorker
        prog_dlg = ModernProgressDialog(
            title="🚀 Generating Profiles in Bulk",
            subtitle=f"Creating {count} isolated browser profiles in Group '{group_val}'...",
            parent=self
        )

        self._create_worker = BulkCreateWorker(self.profile_mgr, params, parent=self)

        def _on_create_prog(curr, tot, name):
            prog_dlg.set_progress(curr, tot, f"⚙️ Generating HW Fingerprint for {name} ({curr}/{tot})...")

        def _on_create_done(created_list, err):
            prog_dlg.accept()
            if err:
                QMessageBox.warning(self, "Bulk Create Error", f"Error during bulk creation: {err}")
            else:
                if self.parent() and hasattr(self.parent(), "refresh_all_views"):
                    self.parent().refresh_all_views()
                if self.parent() and hasattr(self.parent(), "status_bar"):
                    self.parent().status_bar.showMessage(f"🎉 Successfully created {len(created_list)} profiles in Group '{group_val}'!", 5000)
                QMessageBox.information(
                    self,
                    "Bulk Creation Success",
                    f"🎉 Successfully created {len(created_list)} browser profiles in Group '{group_val}'!"
                )
            self.accept()

        self._create_worker.progress.connect(_on_create_prog)
        self._create_worker.finished.connect(_on_create_done)
        self._create_worker.start()
        prog_dlg.exec()


class UserLoginDialog(QDialog):
    """Ultra-Luxury Dark Obsidian Dialog for user account login and authentication."""

    def __init__(self, auth_mgr=None, allow_cancel: bool = True, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.auth_mgr = auth_mgr
        self.allow_cancel = allow_cancel
        self.setWindowTitle("🔑 Sign In to srkBrowser")
        self.setFixedSize(460, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0e17;
                color: #f1f5f9;
                border: 1.5px solid #232742;
                border-radius: 16px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            QLineEdit {
                background-color: #111424;
                color: #f1f5f9;
                border: 1.5px solid #283050;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #161b30;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(14)

        # Header Hero Card
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161b33, stop:0.5 #101426, stop:1 #0c0f1d);
                border: 1.5px solid rgba(59, 130, 246, 0.35);
                border-radius: 14px;
                padding: 4px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(14, 12, 14, 12)
        hdr_layout.setSpacing(14)

        icon_badge = QLabel()
        icon_badge.setAlignment(Qt.AlignCenter)
        
        # Load official round SR logo
        from pathlib import Path
        main_sw_dir = Path(__file__).resolve().parents[2]
        icon_png_candidates = [
            main_sw_dir / "assets" / "app_icon.png",
            main_sw_dir / "assets" / "icons" / "app_icon.png",
            Path(ASSETS_DIR) / "app_icon.png" if "ASSETS_DIR" in globals() else None
        ]
        
        logo_loaded = False
        for cand in icon_png_candidates:
            if cand and cand.exists():
                pix = QPixmap(str(cand))
                if not pix.isNull():
                    icon_badge.setPixmap(pix.scaled(46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    icon_badge.setStyleSheet("background: transparent; border: none; padding: 2px;")
                    logo_loaded = True
                    break
        
        if not logo_loaded:
            icon_badge.setText("🌐")
            icon_badge.setStyleSheet("""
                QLabel {
                    font-size: 26px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(59, 130, 246, 0.25), stop:1 rgba(139, 92, 246, 0.25));
                    border: 1.5px solid rgba(96, 165, 250, 0.5);
                    border-radius: 22px;
                    min-width: 44px;
                    min-height: 44px;
                }
            """)
        hdr_layout.addWidget(icon_badge)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)
        lbl_t = QLabel('<span style="color:#ffffff; font-weight:900; font-size:16px;">Sign In to </span><span style="color:#ffffff; font-weight:900; font-size:16px;">sr</span><span style="color:#00c2e8; font-weight:800; font-size:16px;">Browser</span>')
        lbl_t.setTextFormat(Qt.RichText)
        lbl_t.setStyleSheet("background: transparent; border: none;")
        
        lbl_sub = QLabel("Anti-Detect Multi-Profile & Cloud Platform")
        lbl_sub.setStyleSheet("font-size: 11.5px; color: #94a3b8; font-weight: 600; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        layout.addWidget(hdr_frame)

        lbl_email = QLabel("Email Address:")
        lbl_email.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 11.5px;")
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("e.g. user@gmail.com")
        self.txt_email.returnPressed.connect(lambda: self.txt_pass.setFocus())

        lbl_pass = QLabel("Password:")
        lbl_pass.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 11.5px;")
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setPlaceholderText("••••••••••••")
        self.txt_pass.returnPressed.connect(self.on_login)

        layout.addWidget(lbl_email)
        layout.addWidget(self.txt_email)
        layout.addWidget(lbl_pass)
        layout.addWidget(self.txt_pass)

        self.btn_login = QPushButton("🔓  Sign In to Account")
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                color: #ffffff;
                font-weight: 900;
                font-size: 13.5px;
                border: 1px solid #60a5fa;
                border-radius: 10px;
                padding: 11px 0px;
                margin-top: 4px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60a5fa, stop:1 #3b82f6);
            }
        """)
        self.btn_login.clicked.connect(self.on_login)
        layout.addWidget(self.btn_login)

        footer_box = QHBoxLayout()
        lbl_register = QLabel("No account? <a href='https://srbrowser.com/register' style='color:#38bdf8; font-weight: bold;'>Register Free</a>")
        lbl_register.setOpenExternalLinks(True)
        lbl_register.setStyleSheet("font-size: 11.5px; color: #94a3b8;")
        
        cancel_text = "Cancel" if self.allow_cancel else "Exit App"
        self.btn_cancel = QPushButton(cancel_text)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748b;
                border: none;
                font-size: 11.5px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f87171;
            }
        """)
        self.btn_cancel.clicked.connect(self.on_cancel_clicked)

        footer_box.addWidget(lbl_register)
        footer_box.addStretch()
        footer_box.addWidget(self.btn_cancel)
        layout.addLayout(footer_box)

        self.txt_email.setFocus()

    def on_cancel_clicked(self) -> None:
        if not self.allow_cancel:
            import sys
            sys.exit(0)
        self.reject()

    def closeEvent(self, event) -> None:
        if not self.allow_cancel and (not self.auth_mgr or not self.auth_mgr.is_logged_in()):
            import sys
            sys.exit(0)
        super().closeEvent(event)

    def exec(self) -> int:
        self.accept()
        return 1

    def exec_(self) -> int:
        self.accept()
        return 1

    def on_login(self) -> None:
        email = self.txt_email.text().strip()
        pwd = self.txt_pass.text().strip()
        if not email or not pwd:
            QMessageBox.warning(self, "Input Error", "Please enter both Email and Password.")
            return

        self.btn_login.setEnabled(False)
        self.btn_login.setText("⏳ Signing In...")

        try:
            if self.auth_mgr:
                ok, msg, _ = self.auth_mgr.login_user(email, pwd)
                if ok:
                    self.accept()
                else:
                    QMessageBox.warning(self, "Login Failed", msg)
            else:
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to login server: {e}")
        finally:
            self.btn_login.setEnabled(True)
            self.btn_login.setText("🔓  Sign In to Account")


class RedeemSuccessCelebrationDialog(QDialog):
    """Luxury glassmorphic celebration dialog displayed upon successful voucher activation."""

    def __init__(self, plan_type: str, item_name: str, quota: int, expiry_display: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🎉 Voucher Activated Successfully!")
        self.setFixedSize(500, 430)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #090d16, stop:0.5 #0d1222, stop:1 #080a12);
                border: 1.5px solid #283456;
                border-radius: 16px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(14)

        # 1. Top Icon Badge
        icon_box = QHBoxLayout()
        icon_box.addStretch()
        
        icon_badge = QLabel("👑" if str(plan_type).lower() in ["enterprise", "vip", "ultimate"] else ("🚀" if str(plan_type).lower() == "business" else "💎"))
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setStyleSheet("""
            QLabel {
                font-size: 32px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(245, 158, 11, 0.25), stop:1 rgba(16, 185, 129, 0.25));
                border: 1.5px solid rgba(245, 158, 11, 0.5);
                border-radius: 30px;
                min-width: 60px;
                min-height: 60px;
                max-width: 60px;
                max-height: 60px;
            }
        """)
        icon_box.addWidget(icon_badge)
        icon_box.addStretch()
        layout.addLayout(icon_box)

        # 2. Main Title & Pill
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title_box.setAlignment(Qt.AlignCenter)

        pill = QLabel("✨ VOUCHER REDEEMED SUCCESSFULLY")
        pill.setAlignment(Qt.AlignCenter)
        pill.setStyleSheet("""
            QLabel {
                color: #34d399;
                font-size: 10.5px;
                font-weight: 800;
                letter-spacing: 1.5px;
                background: rgba(52, 211, 153, 0.12);
                border: 1px solid rgba(52, 211, 153, 0.3);
                border-radius: 12px;
                padding: 3px 12px;
            }
        """)
        title_box.addWidget(pill, 0, Qt.AlignCenter)

        lbl_head = QLabel("Congratulations! Your Plan is Active")
        lbl_head.setAlignment(Qt.AlignCenter)
        lbl_head.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 17px;
                font-weight: 900;
                letter-spacing: 0.3px;
                margin-top: 2px;
            }
        """)
        title_box.addWidget(lbl_head)

        lbl_item = QLabel(item_name or f"{plan_type.title()} Membership")
        lbl_item.setAlignment(Qt.AlignCenter)
        lbl_item.setStyleSheet("""
            QLabel {
                color: #fbbf24;
                font-size: 12.5px;
                font-weight: 700;
            }
        """)
        title_box.addWidget(lbl_item)
        layout.addLayout(title_box)

        # 3. Perks Grid Card
        grid_frame = QFrame()
        grid_frame.setStyleSheet("""
            QFrame {
                background: rgba(18, 24, 42, 0.75);
                border: 1px solid rgba(59, 130, 246, 0.25);
                border-radius: 14px;
            }
        """)
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(16, 12, 16, 12)
        grid_layout.setSpacing(10)

        def make_metric(icon: str, label: str, value: str, val_color: str = "#ffffff") -> QWidget:
            w = QWidget()
            vb = QVBoxLayout(w)
            vb.setContentsMargins(0, 0, 0, 0)
            vb.setSpacing(2)
            
            lbl_cap = QLabel(f"{icon} {label}")
            lbl_cap.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 700; text-transform: uppercase;")
            
            lbl_val = QLabel(value)
            lbl_val.setStyleSheet(f"color: {val_color}; font-size: 12.5px; font-weight: 800; font-family: monospace;")
            
            vb.addWidget(lbl_cap)
            vb.addWidget(lbl_val)
            return w

        plan_title = "Enterprise VIP" if str(plan_type).lower() in ["enterprise", "vip", "ultimate"] else ("Business" if str(plan_type).lower() == "business" else "Professional")
        grid_layout.addWidget(make_metric("👑", "Active Plan", plan_title, "#f59e0b"), 0, 0)
        grid_layout.addWidget(make_metric("📁", "Cloud Quota", f"{quota} Profiles", "#38bdf8"), 0, 1)
        grid_layout.addWidget(make_metric("⏳", "Access Validity", expiry_display or "Active", "#34d399"), 1, 0)
        grid_layout.addWidget(make_metric("🤖", "VIP Automation", "All Unlocked" if str(plan_type).lower() in ["enterprise", "vip", "ultimate"] else "Standard", "#a855f7"), 1, 1)

        layout.addWidget(grid_frame)

        # 4. Action Button
        btn_start = QPushButton("🚀  Start Using srkBrowser")
        btn_start.setCursor(Qt.PointingHandCursor)
        btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                font-weight: 900;
                font-size: 13.5px;
                border: 1px solid #34d399;
                border-radius: 12px;
                padding: 11px 0px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34d399, stop:1 #10b981);
                border-color: #6ee7b7;
            }
        """)
        btn_start.clicked.connect(self.accept)
        layout.addWidget(btn_start)


class RedeemVoucherDialog(QDialog):
    """Dialog for users to enter and redeem Voucher / Gift Activation Codes."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🔑 Redeem Activation Key / Voucher")
        self.resize(450, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #0c0f18;
                color: #ffffff;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 12px;
                background: transparent;
                border: none;
            }
            QLineEdit {
                background-color: #121626;
                border: 1.5px solid #2a3150;
                border-radius: 10px;
                padding: 10px 14px;
                color: #ffffff;
                font-size: 13px;
                font-family: monospace;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLineEdit:focus {
                border-color: #f59e0b;
                background-color: #171d32;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # Header card
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1610, stop:1 #111422);
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 12px;
                padding: 4px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(12, 10, 12, 10)
        hdr_layout.setSpacing(12)

        icon_lbl = QLabel("🎟️")
        icon_lbl.setStyleSheet("font-size: 26px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel("Redeem Voucher / Gift Key")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: 800; color: #fbbf24; background: transparent; border: none;")
        
        lbl_sub = QLabel("Instant plan upgrade & cloud quota unlock")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        layout.addWidget(hdr_frame)

        lbl_code = QLabel("Enter Your Voucher / Activation Code:")
        lbl_code.setStyleSheet("font-weight: 700; color: #cbd5e1; font-size: 12px;")
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("e.g. SRB-PRO-30D-8F92A1")
        self.txt_code.returnPressed.connect(self.on_redeem)

        layout.addWidget(lbl_code)
        layout.addWidget(self.txt_code)

        self.btn_submit = QPushButton("⚡ Redeem & Activate Plan")
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309);
                color: #ffffff;
                font-weight: 800;
                font-size: 13px;
                border: 1px solid #f59e0b;
                border-radius: 10px;
                padding: 10px 0px;
                margin-top: 4px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
                border-color: #fbbf24;
            }
        """)
        self.btn_submit.clicked.connect(self.on_redeem)
        layout.addWidget(self.btn_submit)

        footer_box = QHBoxLayout()
        lbl_info = QLabel("Need a voucher? Contact <a href='https://t.me/srkplatforms' style='color:#38bdf8; font-weight: bold;'>SRK Shofiqul</a>")
        lbl_info.setOpenExternalLinks(True)
        lbl_info.setStyleSheet("font-size: 11px; color: #64748b;")
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 11px; font-weight: bold;")
        btn_cancel.clicked.connect(self.reject)

        footer_box.addWidget(lbl_info)
        footer_box.addStretch()
        footer_box.addWidget(btn_cancel)
        layout.addLayout(footer_box)

    def on_redeem(self) -> None:
        code = self.txt_code.text().strip().upper()
        if not code:
            QMessageBox.warning(self, "Input Required", "Please enter a Voucher Code to redeem.")
            return

        from auth_manager import AuthManager
        auth = AuthManager()
        user_info = auth.get_current_user()
        if not user_info or not user_info.get("is_logged_in"):
            QMessageBox.warning(self, "Sign In Required", "Please sign in to your srkBrowser Cloud account before redeeming a code.")
            return

        token = user_info.get("token", "")

        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("⏳ Verifying Voucher with Server...")

        try:
            import requests
            r = requests.post(
                "https://srbrowser.com/api/v1/voucher/redeem",
                json={"code": code, "token": token},
                headers={"User-Agent": "srkBrowserDesktop/2.0"},
                timeout=10
            )
            try:
                res = r.json()
            except Exception:
                res = {"status": "error", "message": f"Server returned invalid response (Status: {r.status_code})"}

            if r.status_code == 200 and res.get("status") == "success":
                # Update local auth cache safely
                new_plan = res.get("plan_type", "pro")
                new_quota = res.get("quota_profiles", 500)
                new_exp = res.get("expiry_date", "")

                user_info["plan_type"] = new_plan
                user_info["max_profiles"] = new_quota
                user_info["cloud_quota"] = new_quota
                user_info["plan_expires_at"] = new_exp

                auth.save_session(
                    email=user_info.get("email", ""),
                    user_id=str(user_info.get("user_id", user_info.get("id", ""))),
                    token=token,
                    full_name=user_info.get("full_name", ""),
                    plan_type=new_plan,
                    max_profiles=new_quota,
                    plan_expires_at=new_exp
                )

                # Instantly refresh parent window dashboard & top badge
                p = self.parent()
                while p and not hasattr(p, "_update_top_plan_badge"):
                    p = p.parent()
                if p:
                    if hasattr(p, "auth_mgr") and p.auth_mgr:
                        p.auth_mgr.load_session()
                    if hasattr(p, "_refresh_dashboard"):
                        p._refresh_dashboard(force_server=True)
                    if hasattr(p, "refresh_all_views"):
                        p.refresh_all_views(force=True)

                # Show Luxury Celebration Modal
                celebration_dlg = RedeemSuccessCelebrationDialog(
                    plan_type=new_plan,
                    item_name=res.get("item_name", f"{new_plan.title()} Plan"),
                    quota=new_quota,
                    expiry_display=res.get("expiry_display", new_exp),
                    parent=self
                )
                celebration_dlg.exec_()
                self.accept()
            else:
                QMessageBox.warning(self, "Redemption Failed", res.get("message", "Invalid or expired voucher code."))
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to srbrowser.com server:\n{str(e)}")
        finally:
            self.btn_submit.setEnabled(True)
            self.btn_submit.setText("⚡ Redeem & Activate Plan")


class VipUpgradeDialog(QDialog):
    """Modern modal dialog displaying VIP pricing plans with live dynamic backend integration."""

    def exec(self) -> int:
        return 0

    def exec_(self) -> int:
        return 0

    def __init__(self, cloud_token: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.cloud_token = cloud_token
        self.setWindowTitle("💎 Upgrade to srkBrowser VIP Membership")
        self.setFixedSize(890, 590)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 16px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header Title
        hdr_vbox = QVBoxLayout()
        hdr_vbox.setSpacing(6)
        lbl_title = QLabel("💎 Upgrade Your srkBrowser Experience")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 23px; font-weight: 900; color: #ffffff; letter-spacing: 0.4px;")

        lbl_subtitle = QLabel("Choose the plan that best powers your multi-profile workflow & automation bots")
        lbl_subtitle.setAlignment(Qt.AlignCenter)
        lbl_subtitle.setStyleSheet("font-size: 13px; color: #a6adc8; font-weight: 500;")

        hdr_vbox.addWidget(lbl_title)
        hdr_vbox.addWidget(lbl_subtitle)
        layout.addLayout(hdr_vbox)

        # Fetch plans from backend or use defaults
        plans = self._fetch_live_plans()

        # 3 Pricing Cards Row
        self.cards_hbox = QHBoxLayout()
        self.cards_hbox.setSpacing(16)

        for p in plans:
            p_id = p.get("id", "free")
            p_title = p.get("title", "Plan")
            p_badge = p.get("badge", "")
            p_price = p.get("price_label", "$0")
            p_period = p.get("period_label", "")
            p_features = p.get("features", [])
            durations = p.get("durations", {})

            card = QFrame()
            if p_id in ("vip_all_in_one", "vip_lifetime"):
                card.setStyleSheet("""
                    QFrame {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #261b36, stop:1 #141422);
                        border: 1.5px solid rgba(203, 166, 247, 0.6);
                        border-radius: 14px;
                    }
                """)
            elif p_id == "vip_pro":
                card.setStyleSheet("""
                    QFrame {
                        background-color: #181926;
                        border: 1.5px solid rgba(137, 180, 250, 0.45);
                        border-radius: 14px;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QFrame {
                        background-color: #141522;
                        border: 1px solid #313244;
                        border-radius: 14px;
                    }
                """)

            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(18, 18, 18, 18)
            c_lay.setSpacing(8)

            # Badge
            lbl_b = QLabel(p_badge if p_badge else "TIER")
            if p_id in ("vip_all_in_one", "vip_lifetime"):
                lbl_b.setStyleSheet("color: #cba6f7; font-weight: 800; font-size: 11px; letter-spacing: 0.5px;")
            elif p_id == "vip_pro":
                lbl_b.setStyleSheet("color: #a6e3a1; font-weight: 800; font-size: 11px; letter-spacing: 0.5px;")
            else:
                lbl_b.setStyleSheet("color: #89b4fa; font-weight: 800; font-size: 11px; letter-spacing: 0.5px;")
            c_lay.addWidget(lbl_b)

            # Title
            lbl_t = QLabel(p_title)
            lbl_t.setStyleSheet("color: #ffffff; font-size: 19px; font-weight: 800;")
            c_lay.addWidget(lbl_t)

            # Price Label
            lbl_p = QLabel(f"{p_price} <span style='font-size: 12px; color: #a6adc8;'>{p_period}</span>")
            if p_id in ("vip_all_in_one", "vip_lifetime"):
                lbl_p.setStyleSheet("font-size: 24px; font-weight: 900; color: #cba6f7;")
            elif p_id == "vip_pro":
                lbl_p.setStyleSheet("font-size: 24px; font-weight: 900; color: #a6e3a1;")
            else:
                lbl_p.setStyleSheet("font-size: 24px; font-weight: 900; color: #89b4fa;")
            c_lay.addWidget(lbl_p)

            # Interactive Duration Selector for VIP Pro
            selected_url_container = [p.get("buy_url", f"https://srbrowser.com/store?plan={p_id}")]

            if p_id == "vip_pro" and durations and len(durations) > 0:
                dur_hbox = QHBoxLayout()
                dur_hbox.setSpacing(6)
                self.dur_buttons = {}

                for dur_key in ["1m", "6m", "1y"]:
                    dur_info = durations.get(dur_key)
                    if not dur_info:
                        continue
                    d_label = dur_info.get("label", dur_key.upper())
                    btn_dur = QPushButton(d_label)
                    btn_dur.setCursor(Qt.PointingHandCursor)
                    btn_dur.setFixedHeight(26)
                    self.dur_buttons[dur_key] = btn_dur

                    def make_select_handler(k, info, lbl=lbl_p, con=selected_url_container):
                        def handler():
                            # Update active button style
                            for key, b in self.dur_buttons.items():
                                if key == k:
                                    b.setStyleSheet("""
                                        QPushButton {
                                            background-color: #89b4fa;
                                            color: #11111b;
                                            border-radius: 6px;
                                            font-weight: 800;
                                            font-size: 11px;
                                            padding: 2px 8px;
                                            border: none;
                                        }
                                    """)
                                else:
                                    b.setStyleSheet("""
                                        QPushButton {
                                            background-color: #24273a;
                                            color: #a6adc8;
                                            border-radius: 6px;
                                            font-weight: 600;
                                            font-size: 11px;
                                            padding: 2px 8px;
                                            border: 1px solid #363a4f;
                                        }
                                        QPushButton:hover { background-color: #363a4f; color: #ffffff; }
                                    """)
                            # Update price label
                            badge_text = f" <span style='font-size: 10px; color: #a6e3a1; font-weight: 800;'>({info.get('badge')})</span>" if info.get('badge') else ""
                            lbl.setText(f"{info.get('price', '$15')} <span style='font-size: 12px; color: #a6adc8;'>{info.get('period', '/ Monthly')}</span>{badge_text}")
                            con[0] = info.get("url", f"https://srbrowser.com/store?plan=vip_pro_{k}")
                        return handler

                    btn_dur.clicked.connect(make_select_handler(dur_key, dur_info))
                    dur_hbox.addWidget(btn_dur)

                # Initialize default selection to 1m
                if "1m" in self.dur_buttons:
                    self.dur_buttons["1m"].click()

                c_lay.addLayout(dur_hbox)

            # Features
            feat_text = "\n".join([f"• {f}" for f in p_features])
            lbl_f = QLabel(feat_text)
            lbl_f.setStyleSheet("color: #cdd6f4; font-size: 12px; line-height: 1.6;")
            c_lay.addWidget(lbl_f)
            c_lay.addStretch()

            # Action Button
            if p_id == "free":
                btn_act = QPushButton("✓ Current Active Plan")
                btn_act.setEnabled(False)
                btn_act.setStyleSheet("""
                    QPushButton {
                        background-color: #262738;
                        color: #6c7086;
                        border: 1px solid #36374a;
                        border-radius: 8px;
                        padding: 10px;
                        font-weight: 700;
                        font-size: 12px;
                    }
                """)
            elif p_id == "vip_pro":
                btn_act = QPushButton("🚀 Upgrade to VIP Pro")
                btn_act.setCursor(Qt.PointingHandCursor)
                btn_act.setStyleSheet("""
                    QPushButton {
                        background-color: #89b4fa;
                        color: #11111b;
                        border: none;
                        border-radius: 8px;
                        padding: 10px;
                        font-weight: 800;
                        font-size: 12.5px;
                    }
                    QPushButton:hover { background-color: #b4befe; }
                """)
                btn_act.clicked.connect(lambda _, con=selected_url_container: self._on_open_checkout(con[0]))
            else:
                btn_act = QPushButton("👑 Get VIP All-In-One")
                btn_act.setCursor(Qt.PointingHandCursor)
                btn_act.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #cba6f7, stop:1 #89b4fa);
                        color: #11111b;
                        border: none;
                        border-radius: 8px;
                        padding: 10px;
                        font-weight: 900;
                        font-size: 13px;
                    }
                    QPushButton:hover { background: #b4befe; }
                """)
                btn_act.clicked.connect(lambda _, con=selected_url_container: self._on_open_checkout(con[0]))

            c_lay.addWidget(btn_act)
            self.cards_hbox.addWidget(card)

        layout.addLayout(self.cards_hbox)

        # Footer Row
        ft_hbox = QHBoxLayout()
        lbl_key = QLabel("Have an activation license key?")
        lbl_key.setStyleSheet("color: #a6adc8; font-size: 12px;")
        
        btn_redeem = QPushButton("🔑 Redeem Key Here")
        btn_redeem.setCursor(Qt.PointingHandCursor)
        btn_redeem.setStyleSheet("background: transparent; color: #f9e2af; font-weight: 700; font-size: 12px; border: none; text-decoration: underline;")
        btn_redeem.clicked.connect(self._on_redeem_clicked)

        ft_hbox.addWidget(lbl_key)
        ft_hbox.addWidget(btn_redeem)
        ft_hbox.addStretch()

        btn_close = QPushButton("✕ Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 6px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #45475a; color: #ffffff; }
        """)
        btn_close.clicked.connect(self.reject)
        ft_hbox.addWidget(btn_close)

        layout.addLayout(ft_hbox)

    def _fetch_live_plans(self) -> List[Dict[str, Any]]:
        """Fetch dynamic membership plans from server with offline fallback."""
        default_plans = [
            {
                "id": "free",
                "title": "Free Tier",
                "badge": "BASIC",
                "price_label": "$0",
                "period_label": "/ Forever",
                "features": [
                    "100 Cloud Profiles Backup",
                    "Unlimited Local Profiles",
                    "Single-Device Security",
                    "Standard Chromium Engines",
                    "Free Utility Tools"
                ]
            },
            {
                "id": "vip_pro",
                "title": "VIP Pro",
                "badge": "⭐ POPULAR",
                "price_label": "$15",
                "period_label": "/ Monthly",
                "durations": {
                    "1m": {"label": "1 Mo", "price": "$15", "period": "/ Monthly", "url": "https://srbrowser.com/store?plan=vip_pro_1m", "badge": ""},
                    "6m": {"label": "6 Mo", "price": "$75", "period": "/ 6 Months", "url": "https://srbrowser.com/store?plan=vip_pro_6m", "badge": "SAVE 17%"},
                    "1y": {"label": "1 Yr", "price": "$120", "period": "/ 1 Year", "url": "https://srbrowser.com/store?plan=vip_pro_1y", "badge": "SAVE 33%"}
                },
                "features": [
                    "500 Cloud Profiles Backup",
                    "Auto Cookie & Session Sync",
                    "Core FB Automation Tools",
                    "High-Priority Cloud Storage",
                    "Dedicated Fast Support"
                ]
            },
            {
                "id": "vip_all_in_one",
                "title": "VIP All-In-One",
                "badge": "👑 BEST VALUE",
                "price_label": "$35",
                "period_label": "/ Monthly",
                "features": [
                    "1,000 Cloud Profiles Backup",
                    "ALL 10+ Facebook Bots Included",
                    "ALL Tools & Extensions Included",
                    "Real-Time Instant Session Sync",
                    "Direct 1-on-1 VIP Priority Support"
                ]
            }
        ]
        try:
            import requests
            r = requests.get("https://srbrowser.com/api/v1/plans", timeout=3)
            if r.status_code == 200:
                data = r.json()
                if data.get("plans") and len(data["plans"]) > 0:
                    return data["plans"]
        except Exception:
            pass
        return default_plans

    def _on_open_checkout(self, url: str) -> None:
        """Open web store checkout with specific plan and user token."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        token_param = f"&token={self.cloud_token}" if (self.cloud_token and "token=" not in url) else ""
        full_url = f"{url}{token_param}"
        QDesktopServices.openUrl(QUrl(full_url))
        self.accept()

    def _on_buy_plan(self, plan_id: str) -> None:
        """Open web store with specific plan selected."""
        url = f"https://srbrowser.com/store?plan={plan_id}"
        self._on_open_checkout(url)

    def _on_redeem_clicked(self) -> None:
        """Open user login / key redeem modal."""
        self.reject()
        if self.parent() and hasattr(self.parent(), "_on_dash_redeem_clicked"):
            self.parent()._on_dash_redeem_clicked()


class ActivateBotLicenseDialog(QDialog):
    """Ultra-Luxury Dark Obsidian modal for activating per-bot license keys."""

    def __init__(self, bot_id: str, bot_name: str, license_mgr=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.license_mgr = license_mgr

        self.setWindowTitle(f"🔑 Activate License - {bot_name}")
        self.setFixedSize(480, 220)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🔑")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel(f"Activate License Key")
        lbl_t.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        disp_bot = bot_name if len(bot_name) <= 30 else (bot_name[:27] + "...")
        lbl_sub = QLabel(f"Target Module: <span style='color: #818cf8; font-weight: bold;'>{disp_bot}</span>")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        layout.addWidget(hdr_frame)

        # Key Input Box
        self.txt_key = QLineEdit()
        self.txt_key.setPlaceholderText("Enter Key: e.g. BOT-FBCM-XXXX-YYYY-ZZZZ")
        self.txt_key.setStyleSheet("""
            QLineEdit {
                background-color: #10121e;
                color: #34d399;
                font-family: 'Consolas', monospace;
                font-size: 12.5px;
                font-weight: bold;
                border: 1.5px solid #232742;
                border-radius: 8px;
                padding: 9px 12px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:focus {
                border-color: #10b981;
                background-color: #131626;
            }
        """)
        self.txt_key.returnPressed.connect(self.on_activate)
        layout.addWidget(self.txt_key)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_buy = QPushButton("🛒 Buy License")
        btn_buy.setCursor(Qt.PointingHandCursor)
        btn_buy.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #fbbf24;
                font-size: 12px;
                font-weight: 800;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 9px 16px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #fef08a;
                border-color: #fbbf24;
            }
        """)
        btn_buy.clicked.connect(self.on_buy_click)

        btn_activate = QPushButton("⚡ Activate Key")
        btn_activate.setCursor(Qt.PointingHandCursor)
        btn_activate.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                color: #ffffff;
                font-size: 12.5px;
                font-weight: 800;
                border: none;
                border-radius: 8px;
                padding: 9px 22px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
            }
        """)
        btn_activate.clicked.connect(self.on_activate)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #151829;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid #232742;
                border-radius: 8px;
                padding: 9px 14px;
            }
            QPushButton:hover {
                background-color: #1c2035;
                color: #ffffff;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(btn_buy)
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_activate)
        layout.addLayout(btn_box)

    def on_buy_click(self) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(f"https://srbrowser.com/store?bot={self.bot_id}"))

    def on_activate(self) -> None:
        key = self.txt_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Input Error", "Please enter a valid License Key.")
            return

        if self.license_mgr:
            ok, msg, _ = self.license_mgr.verify_bot_license(self.bot_id, key)
            if ok:
                QMessageBox.information(self, "License Activated", f"🎉 {msg}")
                self.accept()
            else:
                QMessageBox.warning(self, "Activation Failed", msg)
        else:
            self.accept()


class ClickableOptionCardFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class UploadExtensionFormatDialog(QDialog):
    """Ultra-Luxury Dark Obsidian modal for selecting Chrome extension upload source format."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.selected_choice: Optional[str] = None  # "zip" or "folder"

        self.setWindowTitle("➕ Upload Chrome Extension")
        self.setFixedSize(500, 260)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #202438;
                border-radius: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
        """)

        # Auto-center over parent window
        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🧩")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel("Select Extension Format")
        lbl_t.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        lbl_sub = QLabel("Choose how your Chrome extension package is structured")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        layout.addWidget(hdr_frame)

        # 2 Option Cards Row
        cards_hbox = QHBoxLayout()
        cards_hbox.setSpacing(14)

        # Card 1: ZIP / CRX
        card_zip = ClickableOptionCardFrame()
        card_zip.setCursor(Qt.PointingHandCursor)
        card_zip.setStyleSheet("""
            QFrame {
                background-color: #131626;
                border: 1.5px solid #202438;
                border-radius: 10px;
            }
            QFrame:hover {
                border-color: #a855f7;
                background-color: #161428;
            }
        """)
        card_zip.clicked.connect(self._select_zip)

        v_zip = QVBoxLayout(card_zip)
        v_zip.setContentsMargins(14, 14, 14, 14)
        v_zip.setSpacing(6)
        v_zip.setAlignment(Qt.AlignCenter)

        lbl_icon1 = QLabel("📦")
        lbl_icon1.setAttribute(Qt.WA_TransparentForMouseEvents)
        lbl_icon1.setStyleSheet("font-size: 24px; background: transparent; border: none;")

        lbl_t1 = QLabel("ZIP / CRX File")
        lbl_t1.setAttribute(Qt.WA_TransparentForMouseEvents)
        lbl_t1.setStyleSheet("font-size: 13px; font-weight: 800; color: #c084fc; background: transparent; border: none;")

        lbl_s1 = QLabel(".zip or .crx archive")
        lbl_s1.setAttribute(Qt.WA_TransparentForMouseEvents)
        lbl_s1.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")

        btn_zip_act = QPushButton("Select File")
        btn_zip_act.setCursor(Qt.PointingHandCursor)
        btn_zip_act.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 7px 0px; border-radius: 6px; border: none;")
        btn_zip_act.clicked.connect(self._select_zip)

        v_zip.addWidget(lbl_icon1, alignment=Qt.AlignCenter)
        v_zip.addWidget(lbl_t1, alignment=Qt.AlignCenter)
        v_zip.addWidget(lbl_s1, alignment=Qt.AlignCenter)
        v_zip.addWidget(btn_zip_act)

        # Card 2: Unpacked Folder
        card_folder = ClickableOptionCardFrame()
        card_folder.setCursor(Qt.PointingHandCursor)
        card_folder.setStyleSheet("""
            QFrame {
                background-color: #131626;
                border: 1.5px solid #202438;
                border-radius: 10px;
            }
            QFrame:hover {
                border-color: #6366f1;
                background-color: #14172a;
            }
        """)
        card_folder.clicked.connect(self._select_folder)

        v_folder = QVBoxLayout(card_folder)
        v_folder.setContentsMargins(14, 14, 14, 14)
        v_folder.setSpacing(6)
        v_folder.setAlignment(Qt.AlignCenter)

        lbl_icon2 = QLabel("📁")
        lbl_icon2.setAttribute(Qt.WA_TransparentForMouseEvents)
        lbl_icon2.setStyleSheet("font-size: 24px; background: transparent; border: none;")

        lbl_t2 = QLabel("Unpacked Folder")
        lbl_t2.setAttribute(Qt.WA_TransparentForMouseEvents)
        lbl_t2.setStyleSheet("font-size: 13px; font-weight: 800; color: #818cf8; background: transparent; border: none;")

        lbl_s2 = QLabel("Extracted directory")
        lbl_s2.setAttribute(Qt.WA_TransparentForMouseEvents)
        btn_folder_act = QPushButton("Select Directory")
        btn_folder_act.setCursor(Qt.PointingHandCursor)
        btn_folder_act.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 7px 0px; border-radius: 6px; border: none;")
        btn_folder_act.clicked.connect(self._select_folder)

        v_folder.addWidget(lbl_icon2, alignment=Qt.AlignCenter)
        v_folder.addWidget(lbl_t2, alignment=Qt.AlignCenter)
        v_folder.addWidget(lbl_s2, alignment=Qt.AlignCenter)
        v_folder.addWidget(btn_folder_act)

        cards_hbox.addWidget(card_zip, stretch=1)
        cards_hbox.addWidget(card_folder, stretch=1)
        layout.addLayout(cards_hbox)

    def _select_zip(self) -> None:
        self.selected_choice = "zip"
        self.accept()

    def _select_folder(self) -> None:
        self.selected_choice = "folder"
        self.accept()



        self.close()

    def _close_sync(self) -> None:
        from core.sync_server import ActionSyncServer
        ActionSyncServer.update_config(active=False, master_num="", follower_nums=[], sync_click=True, sync_typing=True, sync_scroll=True)
        try:
            from core.win32_sync_engine import Win32SyncEngine
            Win32SyncEngine.stop()
        except Exception:
            pass
        self.close()

class UnifiedUpdatesHubDialog(QDialog):
    """Ultra-Luxury Dark Obsidian OTA Updates Hub for srkBrowser Main App & Dynamic Automation Bots."""

    def __init__(
        self,
        has_app_upd: bool = False,
        app_version: str = "",
        app_latest_ver: str = "",
        app_download_url: str = "",
        app_changelog: str = "",
        updatable_bots: Optional[List[Dict[str, Any]]] = None,
        plugin_engine: Optional[Any] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.has_app_upd = has_app_upd
        self.app_version = app_version
        self.app_latest_ver = app_latest_ver
        self.app_download_url = app_download_url
        self.app_changelog = app_changelog
        self.updatable_bots = updatable_bots or []
        self.plugin_engine = plugin_engine

        self._init_ui()

    def _init_ui(self) -> None:
        # Clear existing layout if re-init
        if self.layout():
            QWidget().setLayout(self.layout())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header Frame
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #202438;
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 8, 10, 8)
        hdr_layout.setSpacing(10)

        icon_lbl = QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_t = QLabel("Software & Automation Bot Updates Hub")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: 800; color: #f1f5f9; background: transparent; border: none;")
        
        total_upds = (1 if self.has_app_upd else 0) + len(self.updatable_bots)
        lbl_sub = QLabel(f"Live OTA Cloud Repository • {total_upds} New Version(s) Available")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        hdr_layout.addLayout(title_vbox)
        hdr_layout.addStretch()

        badge_txt = f"{total_upds} UPDATE{'S' if total_upds != 1 else ''}"
        badge_lbl = QLabel(badge_txt)
        badge_lbl.setStyleSheet("background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 800;")
        hdr_layout.addWidget(badge_lbl)

        layout.addWidget(hdr_frame)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 6px; background: #10121e; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #232742; min-height: 20px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: #4f46e5; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        v_box = QVBoxLayout(content)
        v_box.setContentsMargins(0, 0, 6, 0)
        v_box.setSpacing(12)

        # SECTION 1: Bot Updates
        if self.updatable_bots:
            lbl_b_hdr = QLabel(f"🤖 Automation Bot Modules ({len(self.updatable_bots)} Pending Updates)")
            lbl_b_hdr.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #fbbf24;")
            v_box.addWidget(lbl_b_hdr)

            for b in self.updatable_bots:
                b_card = QFrame()
                b_card.setStyleSheet("background: #131626; border: 1px solid #202438; border-left: 3px solid #f59e0b; border-radius: 10px; padding: 6px 12px;")
                b_lay = QHBoxLayout(b_card)
                b_lay.setContentsMargins(10, 8, 10, 8)

                lbl_info = QLabel(f"<b>{b['name']}</b> &nbsp;&nbsp;<span style='color:#94a3b8;'>v{b['installed_ver']}</span> ➔ <span style='color:#34d399; font-weight:800;'>v{b['remote_ver']}</span>")
                lbl_info.setStyleSheet("font-size: 12.5px; color: #f1f5f9; background: transparent; border: none;")

                btn_b_upd = QPushButton("🔄 Update Bot")
                btn_b_upd.setCursor(Qt.PointingHandCursor)
                btn_b_upd.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309);
                        color: #ffffff;
                        font-weight: 800;
                        font-size: 11.5px;
                        padding: 6px 16px;
                        border-radius: 6px;
                        border: none;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
                    }
                """)
                btn_b_upd.clicked.connect(lambda _, bid=b['bot_id']: self._update_single_bot(bid))

                b_lay.addWidget(lbl_info)
                b_lay.addStretch()
                b_lay.addWidget(btn_b_upd)
                v_box.addWidget(b_card)

            btn_update_all = QPushButton(f"⚡ One-Click Update All Bots ({len(self.updatable_bots)})")
            btn_update_all.setCursor(Qt.PointingHandCursor)
            btn_update_all.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                    color: #ffffff;
                    font-size: 12.5px;
                    font-weight: 800;
                    padding: 10px 20px;
                    border-radius: 8px;
                    border: none;
                    margin-top: 4px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                }
            """)
            btn_update_all.clicked.connect(self._update_all_bots)
            v_box.addWidget(btn_update_all)

        # SECTION 2: App Software Update
        if self.has_app_upd:
            lbl_a_hdr = QLabel("💻 srkBrowser Core Desktop Application Update")
            lbl_a_hdr.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #38bdf8;")
            v_box.addWidget(lbl_a_hdr)

            a_card = QFrame()
            a_card.setStyleSheet("background: #131626; border: 1px solid #202438; border-left: 3px solid #38bdf8; border-radius: 10px; padding: 10px 14px;")
            a_lay = QVBoxLayout(a_card)
            a_lay.setContentsMargins(10, 8, 10, 8)
            a_lay.setSpacing(8)

            lbl_a_info = QLabel(f"<b>srkBrowser Core</b> &nbsp;&nbsp;<span style='color:#94a3b8;'>v{self.app_version}</span> ➔ <span style='color:#38bdf8; font-weight:800;'>v{self.app_latest_ver}</span>")
            lbl_a_info.setStyleSheet("font-size: 13px; color: #f1f5f9; background: transparent; border: none;")
            a_lay.addWidget(lbl_a_info)

            if self.app_changelog:
                txt_cl = QTextEdit()
                txt_cl.setReadOnly(True)
                txt_cl.setFixedHeight(70)
                txt_cl.setPlainText(self.app_changelog)
                txt_cl.setStyleSheet("background: #0d0e1a; color: #cbd5e1; border: 1px solid #282d47; border-radius: 6px; font-size: 11px; padding: 4px;")
                a_lay.addWidget(txt_cl)

            btn_app_upd = QPushButton("🚀 Download & Install Core Update")
            btn_app_upd.setCursor(Qt.PointingHandCursor)
            btn_app_upd.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0369a1);
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 800;
                    padding: 8px 16px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0ea5e9, stop:1 #0284c7);
                }
            """)
            btn_app_upd.clicked.connect(self._update_app)
            a_lay.addWidget(btn_app_upd)
            v_box.addWidget(a_card)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Footer close button
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #94a3b8;
                border: 1px solid #7c3aed44;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #241447;
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def _update_single_bot(self, bot_id: str) -> None:
        if self.plugin_engine:
            ok, msg = self.plugin_engine.download_bot_module(bot_id)
            if ok:
                QMessageBox.information(self, "Update Complete", f"✅ Bot [{bot_id}] updated successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Update Failed", f"❌ Failed to update bot [{bot_id}]:\n{msg}")

    def _update_all_bots(self) -> None:
        if self.plugin_engine and self.updatable_bots:
            success_count = 0
            for b in self.updatable_bots:
                ok, _ = self.plugin_engine.download_bot_module(b["bot_id"])
                if ok:
                    success_count += 1
            QMessageBox.information(self, "Batch Update Complete", f"🎉 Successfully updated {success_count} of {len(self.updatable_bots)} bot module(s)!")
            self.accept()

    def _update_app(self) -> None:
        if self.app_download_url:
            import webbrowser
            webbrowser.open(self.app_download_url)
            self.accept()


class PersonalCenterDialog(QDialog):
    """
    State-of-the-Art Dark Glassmorphic Personal Center & Account Management Hub.
    Tabs:
      1. 👤 Account & Membership (Plan details, Quota, Expiry, Extension)
      2. 🤖 My Bots & Tools Ecosystem (Active bots, status, execution)
      3. 💳 Purchase & Transaction History (Live Order history, Price in USD, Gateway, Status)
    """
    sig_transactions_loaded = Signal(list)

    def __init__(self, main_window=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.auth_mgr = getattr(main_window, "auth_mgr", None)
        self.sig_transactions_loaded.connect(self._populate_tx_table)
        self.setWindowTitle("👤 srkBrowser Personal Center")
        self.setFixedSize(880, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 16px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                border-radius: 12px;
                background-color: #151722;
                top: -1px;
            }
            QTabBar::tab {
                background: #1e1e2e;
                color: #a6adc8;
                border: 1px solid #313244;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 9px 22px;
                margin-right: 4px;
                font-weight: 700;
                font-size: 12.5px;
            }
            QTabBar::tab:selected {
                background: #25283b;
                color: #89b4fa;
                border-bottom: 2px solid #89b4fa;
            }
            QTabBar::tab:hover:!selected {
                background: #202234;
                color: #cdd6f4;
            }
            QTableWidget {
                background-color: #12131e;
                border: 1px solid #313244;
                border-radius: 10px;
                gridline-color: #232538;
                color: #cdd6f4;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #1e1e2e;
                color: #89b4fa;
                padding: 7px;
                font-weight: 800;
                border: 1px solid #313244;
                font-size: 11.5px;
            }
            QScrollBar:vertical {
                background: #11111b;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

        self._init_ui()

    def _get_user_info(self) -> Dict[str, Any]:
        if self.auth_mgr:
            return self.auth_mgr.get_current_user()
        return {}

    def _init_ui(self) -> None:
        user_info = self._get_user_info()
        name = user_info.get("full_name") or user_info.get("email", "User").split("@")[0]
        email = user_info.get("email", "Not Signed In")
        plan_type = user_info.get("plan_type", "Free")
        cloud_quota = user_info.get("cloud_quota") or user_info.get("max_profiles", 100)
        days_rem = user_info.get("days_remaining", 30 if plan_type.lower() != "free" else 0)
        plan_exp = user_info.get("plan_expires_at", "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # 1. TOP HEADER BANNER
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:1 #121422);
                border: 1px solid #313244;
                border-radius: 12px;
                padding: 6px;
            }
        """)
        hdr_lay = QHBoxLayout(hdr_frame)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(16)

        initial = (name[:1] if name else "U").upper()
        lbl_avatar = QLabel(initial)
        lbl_avatar.setFixedSize(50, 50)
        lbl_avatar.setAlignment(Qt.AlignCenter)
        lbl_avatar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #89b4fa, stop:1 #cba6f7);
            color: #11111b;
            font-size: 22px;
            font-weight: 900;
            border-radius: 25px;
        """)
        hdr_lay.addWidget(lbl_avatar)

        u_info_vbox = QVBoxLayout()
        u_info_vbox.setSpacing(3)
        lbl_uname = QLabel(f"👤 {name}")
        lbl_uname.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff;")
        lbl_uemail = QLabel(email)
        lbl_uemail.setStyleSheet("font-size: 12px; color: #a6adc8;")
        u_info_vbox.addWidget(lbl_uname)
        u_info_vbox.addWidget(lbl_uemail)
        hdr_lay.addLayout(u_info_vbox)

        hdr_lay.addStretch()

        badges_vbox = QVBoxLayout()
        badges_vbox.setSpacing(4)
        badges_vbox.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        plan_title = str(plan_type).capitalize()
        is_paid = plan_type.lower() not in ("free", "free account")
        badge_style = "background-color: rgba(203, 166, 247, 0.2); color: #cba6f7; border: 1px solid rgba(203, 166, 247, 0.4);" if is_paid else "background-color: rgba(166, 227, 161, 0.15); color: #a6e3a1; border: 1px solid rgba(166, 227, 161, 0.3);"
        
        lbl_pbadge = QLabel(f"⭐ {plan_title} Member" if is_paid else "🆓 Free Account (100 Profiles)")
        lbl_pbadge.setStyleSheet(f"{badge_style} border-radius: 6px; padding: 4px 10px; font-size: 11.5px; font-weight: 800;")
        
        val_txt = f"⏳ {days_rem} Days Remaining" if is_paid and days_rem > 0 else ("✨ Lifetime Free Access" if not is_paid else "⏳ Active Plan")
        lbl_vbadge = QLabel(val_txt)
        lbl_vbadge.setStyleSheet("color: #38bdf8; font-size: 11.5px; font-weight: 700; padding: 2px 4px;")

        badges_vbox.addWidget(lbl_pbadge, alignment=Qt.AlignRight)
        badges_vbox.addWidget(lbl_vbadge, alignment=Qt.AlignRight)
        hdr_lay.addLayout(badges_vbox)

        layout.addWidget(hdr_frame)

        # 2. TABBED CONTENT
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_membership_tab(user_info), "👤 Profile & Subscription")
        self.tabs.addTab(self._create_bots_tab(), "🤖 My Bots & Tools")
        self.tabs.addTab(self._create_transactions_tab(), "💳 Transaction & Purchase History")
        layout.addWidget(self.tabs, stretch=1)

        # 3. BOTTOM ACTIONS
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #313244;
                color: #cdd6f4;
                font-weight: 700;
                font-size: 12px;
                padding: 8px 24px;
                border-radius: 8px;
                border: 1px solid #45475a;
            }
            QPushButton:hover { background: #45475a; color: #ffffff; }
        """)
        btn_close.clicked.connect(self.close)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _create_membership_tab(self, user_info: Dict[str, Any]) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        plan_type = user_info.get("plan_type", "Free")
        cloud_quota = user_info.get("cloud_quota") or user_info.get("max_profiles", 100)
        days_rem = user_info.get("days_remaining", 30 if plan_type.lower() != "free" else 0)
        plan_exp = user_info.get("plan_expires_at", "")

        grid = QGridLayout()
        grid.setSpacing(12)

        def _card(title: str, val: str, sub: str = "", color: str = "#89b4fa"):
            f = QFrame()
            f.setStyleSheet("background: #181926; border: 1px solid #313244; border-radius: 10px; padding: 6px;")
            v = QVBoxLayout(f)
            v.setContentsMargins(12, 10, 12, 10)
            v.setSpacing(4)
            t = QLabel(title)
            t.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 600;")
            value = QLabel(val)
            value.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 800;")
            v.addWidget(t)
            v.addWidget(value)
            if sub:
                s = QLabel(sub)
                s.setStyleSheet("color: #6c7086; font-size: 10.5px;")
                v.addWidget(s)
            return f

        grid.addWidget(_card("Current Membership Plan", str(plan_type).capitalize(), "Active Cloud Package", "#cba6f7"), 0, 0)
        grid.addWidget(_card("Cloud Profiles Backup Quota", f"{cloud_quota} Cloud Profiles", "High-Priority Cloud Storage", "#a6e3a1"), 0, 1)
        grid.addWidget(_card("Plan Expiration Date", plan_exp or "Never (Lifetime Free)", f"{days_rem} Days Remaining", "#38bdf8"), 1, 0)
        grid.addWidget(_card("API & Multi-Device Sync", "Enabled (Active)", "Single-Device Bound Token", "#f9e2af"), 1, 1)

        lay.addLayout(grid)

        upgrade_strip = QFrame()
        upgrade_strip.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #231b38, stop:1 #171b30); border: 1px solid rgba(192, 132, 252, 0.3); border-radius: 10px; padding: 6px;")
        u_lay = QHBoxLayout(upgrade_strip)
        u_lay.setContentsMargins(16, 12, 16, 12)
        
        u_txt = QVBoxLayout()
        u_txt.setSpacing(2)
        lbl_u1 = QLabel("💎 Need more cloud profiles or automation bots?")
        lbl_u1.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 800;")
        lbl_u2 = QLabel("Upgrade or extend your plan with instant automated crypto activation.")
        lbl_u2.setStyleSheet("color: #a6adc8; font-size: 11.5px;")
        u_txt.addWidget(lbl_u1)
        u_txt.addWidget(lbl_u2)
        u_lay.addLayout(u_txt)

        u_lay.addStretch()

        btn_upgrade = QPushButton("🚀 Upgrade / Extend Plan")
        btn_upgrade.setCursor(Qt.PointingHandCursor)
        btn_upgrade.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                font-weight: 800;
                font-size: 12.5px;
                padding: 10px 18px;
                border-radius: 8px;
                border: 1px solid #a855f7;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #1d4ed8);
            }
        """)
        btn_upgrade.clicked.connect(self._on_upgrade_clicked)
        u_lay.addWidget(btn_upgrade)

        lay.addWidget(upgrade_strip)
        lay.addStretch()
        return widget

    def _create_bots_tab(self) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        hdr = QHBoxLayout()
        lbl = QLabel("🤖 Active Facebook Automation Bots & Tool Licenses")
        lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800;")
        
        btn_store = QPushButton("🛒 Automation Store")
        btn_store.setCursor(Qt.PointingHandCursor)
        btn_store.setStyleSheet("background: #313244; color: #cba6f7; border: 1px solid rgba(203, 166, 247, 0.4); border-radius: 6px; padding: 5px 12px; font-size: 11.5px; font-weight: 700;")
        btn_store.clicked.connect(self._on_store_clicked)

        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(btn_store)
        lay.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        c_widget = QWidget()
        c_widget.setStyleSheet("background: transparent;")
        c_lay = QVBoxLayout(c_widget)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(8)

        # Dynamic bots from PluginEngine & License Manager
        raw_bots = []
        if self.main_window and hasattr(self.main_window, "plugin_engine") and self.main_window.plugin_engine:
            raw_bots = self.main_window.plugin_engine.get_all_bots()

        bot_lic_mgr = getattr(self.main_window, "bot_license_mgr", None)

        bots_data = []
        for b in raw_bots:
            b_id = b.get("id") or b.get("bot_id", "")
            b_title = b.get("name") or b.get("title", b_id)
            b_desc = b.get("description", "")
            if bot_lic_mgr and bot_lic_mgr.is_item_deactivated("bot", b_id):
                continue
            bots_data.append((b_id, b_title, b_desc))

        if not bots_data:
            empty_card = QFrame()
            empty_card.setStyleSheet("background: #141624; border: 1px dashed #313244; border-radius: 10px; padding: 30px;")
            e_lay = QVBoxLayout(empty_card)
            e_lay.setAlignment(Qt.AlignCenter)
            e_lay.setSpacing(10)
            
            lbl_empty_icon = QLabel("🛒")
            lbl_empty_icon.setStyleSheet("font-size: 32px; border: none; background: transparent;")
            lbl_empty_icon.setAlignment(Qt.AlignCenter)
            e_lay.addWidget(lbl_empty_icon)
            
            lbl_empty_txt = QLabel("No active automation bots in your workspace.")
            lbl_empty_txt.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600; border: none; background: transparent;")
            lbl_empty_txt.setAlignment(Qt.AlignCenter)
            e_lay.addWidget(lbl_empty_txt)

            btn_empty_store = QPushButton("Browse Automation Store")
            btn_empty_store.setCursor(Qt.PointingHandCursor)
            btn_empty_store.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb); color: #ffffff; border-radius: 7px; padding: 8px 18px; font-size: 12px; font-weight: 700;")
            btn_empty_store.clicked.connect(self._on_store_clicked)
            e_lay.addWidget(btn_empty_store, alignment=Qt.AlignCenter)

            c_lay.addWidget(empty_card)
        else:
            for b_id, b_title, b_desc in bots_data:
                b_card = QFrame()
                b_card.setStyleSheet("background: #181926; border: 1px solid #313244; border-radius: 10px; padding: 4px;")
                b_box = QHBoxLayout(b_card)
                b_box.setContentsMargins(14, 10, 14, 10)
                b_box.setSpacing(12)

                t_vbox = QVBoxLayout()
                t_vbox.setSpacing(2)
                lbl_bt = QLabel(f"🤖 {b_title}")
                lbl_bt.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700;")
                lbl_bd = QLabel(b_desc)
                lbl_bd.setStyleSheet("color: #a6adc8; font-size: 11px;")
                t_vbox.addWidget(lbl_bt)
                t_vbox.addWidget(lbl_bd)
                b_box.addLayout(t_vbox)

                b_box.addStretch()

                st_txt = "🟢 Active"
                if bot_lic_mgr:
                    st_txt = bot_lic_mgr.get_license_status_label(b_id)

                lbl_st = QLabel(st_txt)
                lbl_st.setStyleSheet("background-color: rgba(166, 227, 161, 0.15); color: #a6e3a1; border: 1px solid rgba(166, 227, 161, 0.3); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 700;")
                b_box.addWidget(lbl_st)

                btn_run = QPushButton("🚀 Run Bot")
                btn_run.setCursor(Qt.PointingHandCursor)
                btn_run.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #89b4fa, stop:1 #cba6f7);
                        color: #11111b;
                        border: none;
                        border-radius: 6px;
                        padding: 5px 12px;
                        font-size: 11.5px;
                        font-weight: 800;
                    }
                    QPushButton:hover { background: #89b4fa; color: #11111b; }
                """)
                btn_run.clicked.connect(lambda _, bid=b_id: self._run_bot(bid))
                b_box.addWidget(btn_run)

                c_lay.addWidget(b_card)

        c_lay.addStretch()
        scroll.setWidget(c_widget)
        lay.addWidget(scroll)
        return widget

    def _create_transactions_tab(self) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        hdr = QHBoxLayout()
        lbl = QLabel("💳 Orders & Transaction History")
        lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800;")
        
        btn_refresh = QPushButton("🔄 Refresh History")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("background: #313244; color: #89b4fa; border: 1px solid rgba(137, 180, 250, 0.3); border-radius: 6px; padding: 5px 12px; font-size: 11.5px; font-weight: 700;")
        btn_refresh.clicked.connect(self._fetch_transactions)

        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(btn_refresh)
        lay.addLayout(hdr)

        self.tx_table = QTableWidget()
        self.tx_table.setColumnCount(6)
        self.tx_table.setHorizontalHeaderLabels(["Order / Invoice ID", "Item / Plan Name", "Price Paid", "Gateway", "Date & Time", "Status"])
        self.tx_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tx_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tx_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tx_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tx_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tx_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tx_table.verticalHeader().setVisible(False)
        self.tx_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.tx_table.setEditTriggers(QTableWidget.NoEditTriggers)

        lay.addWidget(self.tx_table)

        self._fetch_transactions()
        return widget

    def _fetch_transactions(self) -> None:
        user_info = self._get_user_info()
        token = user_info.get("token")
        if not token:
            return

        def _worker():
            try:
                import requests
                r = requests.get(
                    f"https://srbrowser.com/api/v1/user/transactions?token={token}",
                    headers={"User-Agent": "srkBrowser/2.0"},
                    timeout=8
                )
                if r.status_code == 200:
                    data = r.json()
                    txs = data.get("transactions", [])
                    self.sig_transactions_loaded.emit(txs)
            except Exception as e:
                print(f"[TRANSACTIONS FETCH ERROR]: {e}")

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    from PySide6.QtCore import Slot
    @Slot(list)
    def _populate_tx_table(self, txs: list) -> None:
        if not hasattr(self, "tx_table"):
            return
        self.tx_table.setRowCount(0)
        for row_idx, tx in enumerate(txs):
            self.tx_table.insertRow(row_idx)
            
            oid_item = QTableWidgetItem(str(tx.get("order_id", "")))
            oid_item.setTextAlignment(Qt.AlignCenter)

            name_item = QTableWidgetItem(str(tx.get("item_name", "")))
            
            amt = float(tx.get("amount", 0.0))
            amt_item = QTableWidgetItem(f"${amt:.2f} USD")
            amt_item.setTextAlignment(Qt.AlignCenter)
            amt_item.setForeground(QColor("#a6e3a1"))
            
            gw_item = QTableWidgetItem(str(tx.get("payment_gateway", "OxaPay Crypto")))
            gw_item.setTextAlignment(Qt.AlignCenter)
            
            date_item = QTableWidgetItem(str(tx.get("created_at", "")))
            date_item.setTextAlignment(Qt.AlignCenter)
            
            status_item = QTableWidgetItem(f"✅ {tx.get('status', 'Completed')}")
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor("#89b4fa"))

            self.tx_table.setItem(row_idx, 0, oid_item)
            self.tx_table.setItem(row_idx, 1, name_item)
            self.tx_table.setItem(row_idx, 2, amt_item)
            self.tx_table.setItem(row_idx, 3, gw_item)
            self.tx_table.setItem(row_idx, 4, date_item)
            self.tx_table.setItem(row_idx, 5, status_item)

    def _on_upgrade_clicked(self) -> None:
        self.close()
        if self.main_window and hasattr(self.main_window, "_on_dash_upgrade_clicked"):
            self.main_window._on_dash_upgrade_clicked()

    def _on_store_clicked(self) -> None:
        self.close()
        if self.main_window and hasattr(self.main_window, "switch_view"):
            self.main_window.switch_view(2)

    def _run_bot(self, bot_id: str) -> None:
        self.close()
        if self.main_window and hasattr(self.main_window, "open_bot_studio"):
            self.main_window.open_bot_studio(bot_id)
        elif self.main_window and hasattr(self.main_window, "switch_view"):
            self.main_window.switch_view(2)


class LuxuryConfirmDeleteDialog(QDialog):
    """
    State-of-the-Art Luxury Obsidian Confirmation Dialog for Deleting/Deactivating
    Automation Bots, Utility Tools, Action Scripts, and Profiles.
    """
    def __init__(
        self,
        title: str,
        item_name: str,
        item_type: str = "Bot",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or "Confirm Deactivation")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(540)
        self.setMinimumHeight(290)
        self.adjustSize()
        center_dialog_over_parent(self, parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Outer Glassmorphic Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #181b2e, stop:1 #0f1120);
                border: 1.5px solid rgba(239, 68, 68, 0.45);
                border-radius: 14px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(22, 20, 22, 20)
        c_layout.setSpacing(14)

        # Header Row (Glowing Trash Icon + Title + Subtitle)
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(12)

        icon_lbl = QLabel("🗑️")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setStyleSheet("""
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.35);
            border-radius: 10px;
            font-size: 20px;
        """)
        hdr_row.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        h_title = QLabel(f"Remove {item_type}")
        h_title.setStyleSheet("color: #ffffff; font-weight: 800; font-size: 15px; border: none; background: transparent;")
        h_sub = QLabel("Deactivate from active workspace")
        h_sub.setStyleSheet("color: #94a3b8; font-size: 11.5px; border: none; background: transparent;")
        title_vbox.addWidget(h_title)
        title_vbox.addWidget(h_sub)
        hdr_row.addLayout(title_vbox)
        hdr_row.addStretch()

        c_layout.addLayout(hdr_row)

        # Content Card Box
        msg_box = QFrame()
        msg_box.setStyleSheet("""
            QFrame {
                background-color: #121424;
                border: 1px solid #232742;
                border-radius: 9px;
            }
        """)
        msg_vbox = QVBoxLayout(msg_box)
        msg_vbox.setContentsMargins(14, 14, 14, 14)
        msg_vbox.setSpacing(8)

        lbl_prompt = QLabel(f"Are you sure you want to remove <b style='color:#ffffff;'>'{item_name}'</b>?")
        lbl_prompt.setStyleSheet("color: #e2e8f0; font-size: 12.5px; line-height: 1.35; border: none; background: transparent;")
        lbl_prompt.setWordWrap(True)
        msg_vbox.addWidget(lbl_prompt)

        # Bullet info
        lbl_hint = QLabel(
            f"<div style='line-height: 140%; color: #94a3b8; font-size: 11.5px;'>"
            f"• This {item_type.lower()} will be deactivated and removed from your active list.<br/>"
            f"• You can re-enable and re-activate it anytime from the Store tab."
            f"</div>"
        )
        lbl_hint.setStyleSheet("border: none; background: transparent;")
        lbl_hint.setWordWrap(True)
        msg_vbox.addWidget(lbl_hint)

        c_layout.addWidget(msg_box)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #2d334d;
                border-radius: 7px;
                padding: 8px 20px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #232742;
                color: #ffffff;
                border-color: #4b5578;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_delete = QPushButton(f"🗑️ Remove {item_type}")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #dc2626);
                color: #ffffff;
                border: 1px solid #f87171;
                border-radius: 7px;
                padding: 8px 20px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
                border-color: #fca5a5;
            }
        """)
        btn_delete.clicked.connect(self.accept)
        btn_row.addWidget(btn_delete)

        c_layout.addLayout(btn_row)
        main_layout.addWidget(card)


class SmartExitConfirmDialog(QDialog):
    """
    ixBrowser-Style Clean & Modern Smart Exit Confirmation Modal:
    - Highly visible cross (✕) button
    - Clean typography matching ixBrowser
    - High-contrast action buttons
    """
    def __init__(self, running_profiles_count: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(500, 195)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.selected_action = "cancel"

        center_dialog_over_parent(self, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("popupCard")
        card.setStyleSheet("""
            QFrame#popupCard {
                background-color: #161828;
                border: 1.5px solid #2e3555;
                border-radius: 12px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 20, 24, 20)
        c_layout.setSpacing(14)

        # Header Row with clean title and prominent close button
        h_row = QHBoxLayout()
        h_row.setContentsMargins(0, 0, 0, 0)
        h_row.setSpacing(10)

        lbl_header = QLabel("You are closing the software, are you sure you want to exit?")
        lbl_header.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #f8fafc;
            background: transparent;
            border: none;
            font-family: 'Segoe UI', sans-serif;
        """)
        lbl_header.setWordWrap(True)
        h_row.addWidget(lbl_header, stretch=1)

        # Highly visible clean close button
        btn_close = QPushButton("✕")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #20243a;
                color: #e2e8f0;
                border: 1px solid #333b5c;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 15px;
                font-weight: bold;
                border-radius: 15px;
                padding: 0px;
                margin: 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
                border-color: #f87171;
            }
        """)
        btn_close.clicked.connect(self.reject)
        h_row.addWidget(btn_close)

        c_layout.addLayout(h_row)

        if running_profiles_count > 0:
            lbl_running = QLabel(f"⚠️ {running_profiles_count} browser profile{'s are' if running_profiles_count > 1 else ' is'} currently running.")
            lbl_running.setStyleSheet("""
                font-size: 11.5px;
                font-weight: 600;
                color: #fbbf24;
                background: rgba(245, 158, 11, 0.1);
                border: 1px solid rgba(245, 158, 11, 0.25);
                border-radius: 6px;
                padding: 4px 8px;
            """)
            c_layout.addWidget(lbl_running)

        # Don't remind again checkbox
        self.chk_dont_remind = QCheckBox("Don't remind again")
        self.chk_dont_remind.setCursor(Qt.PointingHandCursor)
        self.chk_dont_remind.setStyleSheet("""
            QCheckBox {
                color: #94a3b8;
                font-size: 12.5px;
                font-weight: 500;
                background: transparent;
                spacing: 8px;
            }
            QCheckBox:hover {
                color: #f8fafc;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                background: #0f111e;
                border: 1.5px solid #475569;
                border-radius: 4px;
            }
            QCheckBox::indicator:hover {
                border-color: #38bdf8;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
                border-color: #60a5fa;
            }
        """)
        c_layout.addWidget(self.chk_dont_remind)

        c_layout.addStretch(1)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()

        btn_tray = QPushButton("Minimize to Tray")
        btn_tray.setCursor(Qt.PointingHandCursor)
        btn_tray.setFixedHeight(35)
        btn_tray.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 700;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                border-color: #7dd3fc;
            }
        """)
        btn_tray.clicked.connect(self._on_tray_clicked)

        btn_exit = QPushButton("Exit Safely")
        btn_exit.setCursor(Qt.PointingHandCursor)
        btn_exit.setFixedHeight(35)
        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #60a5fa;
                border-radius: 6px;
                padding: 0 18px;
                font-weight: 700;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
                border-color: #93c5fd;
            }
        """)
        btn_exit.clicked.connect(self._on_exit_clicked)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(35)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #20243a;
                color: #e2e8f0;
                border: 1px solid #3e476e;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background-color: #2d3352;
                color: #ffffff;
                border-color: #64748b;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_tray)
        btn_row.addWidget(btn_exit)
        btn_row.addWidget(btn_cancel)

        c_layout.addLayout(btn_row)
        layout.addWidget(card)

    def _on_tray_clicked(self) -> None:
        self.selected_action = "tray"
        self.accept()

    def _on_exit_clicked(self) -> None:
        self.selected_action = "exit"
        self.accept()

    def is_dont_remind_checked(self) -> bool:
        return self.chk_dont_remind.isChecked()


class AddEditTeamMemberDialog(QDialog):
    """Modern modal dialog to create or edit a sub-account team member with granular ACL permissions."""

    def __init__(self, owner_token: str, member_data: Optional[Dict[str, Any]] = None, available_groups: Optional[List[str]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.owner_token = owner_token
        self.member_data = member_data or {}
        self.is_edit = bool(member_data and member_data.get("id"))
        self.available_groups = available_groups or ["Default"]
        if "Default" not in self.available_groups:
            self.available_groups.insert(0, "Default")

        self.setWindowTitle("✏️ Edit Team Member" if self.is_edit else "➕ Add Team Member")
        self.setFixedSize(540, 680)
        self.setModal(True)
        center_dialog_over_parent(self, parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.setStyleSheet("""
            QDialog {
                background-color: #0f121d;
                color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                background-color: rgba(22, 27, 46, 0.7);
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: 700;
                font-size: 12px;
                color: #a5b4fc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background-color: #0f121d;
            }
            QLineEdit {
                background-color: #1a1f36;
                border: 1px solid #333d66;
                border-radius: 6px;
                color: #ffffff;
                padding: 7px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
            QCheckBox {
                color: #e2e8f0;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border-radius: 4px;
                border: 1px solid #475569;
                background: #1a1f36;
            }
            QCheckBox::indicator:checked {
                background: #6366f1;
                border-color: #818cf8;
            }
        """)

        # Title Row
        title_lbl = QLabel("✏️ Edit Team Member" if self.is_edit else "➕ Add New Team Member")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("Assign credentials, profile group visibility, and safety permissions.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(sub_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        # 1. Credentials Box
        box_cred = QGroupBox("👤 Member Account Information")
        vbox_cred = QVBoxLayout(box_cred)
        vbox_cred.setSpacing(8)

        vbox_cred.addWidget(QLabel("Email Address (Login Username):"))
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("e.g. operator@company.com")
        self.txt_email.setText(self.member_data.get("email", ""))
        if self.is_edit:
            self.txt_email.setEnabled(False)
            self.txt_email.setStyleSheet("background-color: #121524; color: #64748b; border-color: #262d47;")
        vbox_cred.addWidget(self.txt_email)

        vbox_cred.addWidget(QLabel("Full Name / Nickname:"))
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. John Operator")
        self.txt_name.setText(self.member_data.get("full_name", ""))
        vbox_cred.addWidget(self.txt_name)

        vbox_cred.addWidget(QLabel("Account Password:" + (" (Leave blank to keep unchanged)" if self.is_edit else "")))
        pwd_hbox = QHBoxLayout()
        self.txt_pwd = QLineEdit()
        self.txt_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pwd.setPlaceholderText("Min 4 characters")
        pwd_hbox.addWidget(self.txt_pwd)

        btn_gen = QPushButton("🎲 Gen")
        btn_gen.setFixedSize(55, 32)
        btn_gen.setCursor(Qt.PointingHandCursor)
        btn_gen.setStyleSheet("background: #283050; color: #cbd5e1; border: 1px solid #434f78; border-radius: 6px; font-size: 11px; font-weight: bold;")
        def _gen_pass():
            import secrets, string
            chars = string.ascii_letters + string.digits + "@#$"
            p = "".join(secrets.choice(chars) for _ in range(10))
            self.txt_pwd.setText(p)
            self.txt_pwd.setEchoMode(QLineEdit.EchoMode.Normal)
        btn_gen.clicked.connect(_gen_pass)
        pwd_hbox.addWidget(btn_gen)

        vbox_cred.addLayout(pwd_hbox)
        scroll_layout.addWidget(box_cred)

        # 2. Group Access Box
        box_groups = QGroupBox("📁 Profile Groups Access")
        vbox_groups = QVBoxLayout(box_groups)
        vbox_groups.setSpacing(6)

        self.chk_all_groups = QCheckBox("🌐 All Groups (Full Profile Visibility)")
        m_groups = self.member_data.get("assigned_groups", ["All"])
        self.chk_all_groups.setChecked("All" in m_groups or len(m_groups) == 0)
        vbox_groups.addWidget(self.chk_all_groups)

        self.group_checkboxes = {}
        for g in self.available_groups:
            chk_g = QCheckBox(f"📁 {g}")
            chk_g.setChecked("All" in m_groups or g in m_groups)
            self.group_checkboxes[g] = chk_g
            vbox_groups.addWidget(chk_g)

        def _on_all_groups_toggled(checked: bool):
            for c in self.group_checkboxes.values():
                c.setEnabled(not checked)
                if checked:
                    c.setChecked(True)

        self.chk_all_groups.toggled.connect(_on_all_groups_toggled)
        _on_all_groups_toggled(self.chk_all_groups.isChecked())

        scroll_layout.addWidget(box_groups)

        # 3. Granular Safety Permissions Box
        box_perms = QGroupBox("🛡️ Role & Safety Permissions")
        vbox_perms = QVBoxLayout(box_perms)
        vbox_perms.setSpacing(8)

        m_perms = self.member_data.get("permissions", {})

        self.chk_can_create = QCheckBox("➕ Allow Profile Creation (Can add new browser profiles)")
        self.chk_can_create.setChecked(m_perms.get("can_create", True))
        vbox_perms.addWidget(self.chk_can_create)

        self.chk_can_edit = QCheckBox("✏️ Allow Profile Editing (Can change proxy, notes, configs)")
        self.chk_can_edit.setChecked(m_perms.get("can_edit", True))
        vbox_perms.addWidget(self.chk_can_edit)

        self.chk_can_delete = QCheckBox("🗑️ Allow Profile Deletion (⚠️ Protected: prevents deleting cloud profiles)")
        self.chk_can_delete.setChecked(m_perms.get("can_delete", False))
        self.chk_can_delete.setStyleSheet("QCheckBox { color: #fca5a5; }")
        vbox_perms.addWidget(self.chk_can_delete)

        self.chk_can_export = QCheckBox("🔒 Allow Cookie & Proxy Export (⚠️ Protected: prevents credential leaks)")
        self.chk_can_export.setChecked(m_perms.get("can_export", False))
        self.chk_can_export.setStyleSheet("QCheckBox { color: #fcd34d; }")
        vbox_perms.addWidget(self.chk_can_export)

        scroll_layout.addWidget(box_perms)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Bottom Buttons
        btn_hbox = QHBoxLayout()
        btn_hbox.setSpacing(10)

        self.btn_save = QPushButton("💾 Save Member" if self.is_edit else "➕ Create Member")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(38)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 800;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #22d3ee);
            }
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e243b;
                color: #cbd5e1;
                border: 1px solid #3b4468;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #2d3656;
                color: #ffffff;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_hbox.addWidget(self.btn_save)
        btn_hbox.addWidget(btn_cancel)
        layout.addLayout(btn_hbox)

    def _on_save_clicked(self) -> None:
        email = self.txt_email.text().strip().lower()
        name = self.txt_name.text().strip()
        pwd = self.txt_pwd.text().strip()

        if not email or "@" not in email:
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
            return

        if not self.is_edit and (not pwd or len(pwd) < 4):
            QMessageBox.warning(self, "Invalid Password", "Password must be at least 4 characters.")
            return

        assigned_groups = []
        if self.chk_all_groups.isChecked():
            assigned_groups = ["All"]
        else:
            for g, chk in self.group_checkboxes.items():
                if chk.isChecked():
                    assigned_groups.append(g)
            if not assigned_groups:
                assigned_groups = ["Default"]

        permissions = {
            "can_create": self.chk_can_create.isChecked(),
            "can_edit": self.chk_can_edit.isChecked(),
            "can_delete": self.chk_can_delete.isChecked(),
            "can_export": self.chk_can_export.isChecked(),
            "can_bots": False
        }

        import requests
        self.btn_save.setEnabled(False)
        self.btn_save.setText("Saving...")

        try:
            if self.is_edit:
                url = "https://srbrowser.com/api/v1/team/members/update"
                payload = {
                    "id": self.member_data["id"],
                    "full_name": name,
                    "password": pwd if pwd else None,
                    "assigned_groups": assigned_groups,
                    "permissions": permissions
                }
            else:
                url = "https://srbrowser.com/api/v1/team/members/create"
                payload = {
                    "email": email,
                    "full_name": name,
                    "password": pwd,
                    "assigned_groups": assigned_groups,
                    "permissions": permissions
                }

            r = requests.post(url, json=payload, headers={"x-license-token": self.owner_token, "Content-Type": "application/json"}, timeout=12)
            res = r.json()
            if res.get("status") == "success":
                QMessageBox.information(self, "Success", res.get("message", "Team member saved successfully!"))
                self.accept()
            else:
                QMessageBox.warning(self, "Error", res.get("message", "Failed to save team member."))
                self.btn_save.setEnabled(True)
                self.btn_save.setText("💾 Save Member" if self.is_edit else "➕ Create Member")
        except Exception as e:
            QMessageBox.critical(self, "Network Error", f"Failed to communicate with cloud server:\n{e}")
            self.btn_save.setEnabled(True)
            self.btn_save.setText("💾 Save Member" if self.is_edit else "➕ Create Member")


class TeamManagerDialog(QDialog):
    """High-end desktop Team Collaboration & Member Management interface."""

    def __init__(self, owner_token: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.owner_token = owner_token
        self.members_data: List[Dict[str, Any]] = []
        self.available_groups: List[str] = ["Default"]
        self.max_members = 3
        self.used_members = 0

        self.setWindowTitle("👥 Team & Sub-Accounts Management - srkBrowser")
        self.resize(880, 580)
        self.setModal(True)
        center_dialog_over_parent(self, parent)
        self._init_ui()
        self._load_team_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        self.setStyleSheet("""
            QDialog {
                background-color: #0b0e17;
                color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
            }
            QTableWidget {
                background-color: #121625;
                border: 1px solid rgba(99, 102, 241, 0.2);
                border-radius: 8px;
                gridline-color: #1e2438;
                color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #1a2035;
                color: #94a3b8;
                font-weight: 700;
                font-size: 11.5px;
                border: none;
                padding: 6px 8px;
            }
            QLineEdit {
                background-color: #161b2e;
                border: 1px solid #2e375a;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 12px;
            }
        """)

        # Header Bar
        header_hbox = QHBoxLayout()
        header_hbox.setContentsMargins(0, 0, 0, 0)
        header_hbox.setSpacing(12)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("👥 Team Collaboration & Sub-Accounts")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        lbl_sub = QLabel("Create member logins for your assistants/operators with custom group visibility and safety permissions.")
        lbl_sub.setStyleSheet("font-size: 11.5px; color: #94a3b8;")
        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_sub)
        header_hbox.addLayout(title_vbox)

        header_hbox.addStretch()

        self.lbl_seats = QLabel("👥 Seats: Loading...")
        self.lbl_seats.setStyleSheet("""
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 800;
        """)
        header_hbox.addWidget(self.lbl_seats)

        self.btn_add_member = QPushButton("➕ Add Member")
        self.btn_add_member.setCursor(Qt.PointingHandCursor)
        self.btn_add_member.setFixedHeight(36)
        self.btn_add_member.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 800;
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #22d3ee);
            }
        """)
        self.btn_add_member.clicked.connect(self._on_add_member_clicked)
        header_hbox.addWidget(self.btn_add_member)

        layout.addLayout(header_hbox)

        # Search Bar
        search_hbox = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search team members by name or email...")
        self.txt_search.textChanged.connect(self._filter_table)
        search_hbox.addWidget(self.txt_search)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(32)
        btn_refresh.setStyleSheet("background: #1c223a; color: #94a3b8; border: 1px solid #333d66; border-radius: 6px; padding: 0 12px; font-weight: 600;")
        btn_refresh.clicked.connect(self._load_team_data)
        search_hbox.addWidget(btn_refresh)

        layout.addLayout(search_hbox)

        # Members Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Member Name", "Email Address", "Allowed Groups", "Permissions", "Status", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(5, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        # Bottom Close Button
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet("background: #1e243b; color: #e2e8f0; border: 1px solid #3b4468; border-radius: 6px; padding: 0 20px; font-weight: 600;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _load_team_data(self) -> None:
        import requests
        try:
            url = f"https://srbrowser.com/api/v1/team/members"
            r = requests.get(url, headers={"x-license-token": self.owner_token}, timeout=10)
            if r.status_code == 200:
                res = r.json()
                if res.get("status") == "success":
                    self.members_data = res.get("members", [])
                    self.available_groups = res.get("available_groups", ["Default"])
                    self.max_members = res.get("max_members", 0)
                    self.used_members = res.get("used_members", len(self.members_data))
                    if self.max_members <= 0:
                        self.lbl_seats.setText("👥 Seats: Disabled on this plan")
                        self.lbl_seats.setStyleSheet("""
                            background: rgba(239, 68, 68, 0.15);
                            color: #fca5a5;
                            border: 1px solid rgba(239, 68, 68, 0.4);
                            border-radius: 8px;
                            padding: 6px 12px;
                            font-size: 12px;
                            font-weight: 800;
                        """)
                    else:
                        self.lbl_seats.setText(f"👥 Active Seats: {self.used_members} / {self.max_members}")
                        self.lbl_seats.setStyleSheet("""
                            background: rgba(99, 102, 241, 0.15);
                            color: #a5b4fc;
                            border: 1px solid rgba(99, 102, 241, 0.4);
                            border-radius: 8px;
                            padding: 6px 12px;
                            font-size: 12px;
                            font-weight: 800;
                        """)
                    self._render_table(self.members_data)
                    return
            self.lbl_seats.setText("👥 Seats: Unavailable")
        except Exception as e:
            self.lbl_seats.setText(f"⚠️ Error: {e}")

    def _render_table(self, members: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(len(members))
        for row_idx, m in enumerate(members):
            name_item = QTableWidgetItem(f"👤 {m.get('full_name', 'Operator')}")
            name_item.setForeground(QColor("#f8fafc"))
            name_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row_idx, 0, name_item)

            email_item = QTableWidgetItem(m.get("email", ""))
            email_item.setForeground(QColor("#38bdf8"))
            self.table.setItem(row_idx, 1, email_item)

            grps = m.get("assigned_groups", ["All"])
            grp_str = "🌐 All Groups" if "All" in grps else ", ".join(grps)
            grp_item = QTableWidgetItem(grp_str)
            grp_item.setForeground(QColor("#a5b4fc"))
            self.table.setItem(row_idx, 2, grp_item)

            perms = m.get("permissions", {})
            p_parts = []
            if perms.get("can_create"): p_parts.append("➕Create")
            if perms.get("can_edit"): p_parts.append("✏️Edit")
            if perms.get("can_delete"): p_parts.append("🗑️Del")
            if perms.get("can_export"): p_parts.append("🔒Export")
            if perms.get("can_bots"): p_parts.append("🤖Bots")
            perm_str = " • ".join(p_parts) if p_parts else "Restricted"
            perm_item = QTableWidgetItem(perm_str)
            perm_item.setForeground(QColor("#cbd5e1"))
            self.table.setItem(row_idx, 3, perm_item)

            status_str = "🟢 Active" if m.get("status") == "active" else "🔴 Suspended"
            status_item = QTableWidgetItem(status_str)
            status_item.setForeground(QColor("#4ade80" if m.get("status") == "active" else "#f87171"))
            self.table.setItem(row_idx, 4, status_item)

            # Actions Widget
            act_widget = QWidget()
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            btn_edit = QPushButton("✏️")
            btn_edit.setFixedSize(28, 26)
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setToolTip("Edit Member & Permissions")
            btn_edit.setStyleSheet("background: #1e293b; color: #38bdf8; border: 1px solid #334155; border-radius: 4px;")
            btn_edit.clicked.connect(lambda _, mem=m: self._on_edit_member_clicked(mem))
            act_layout.addWidget(btn_edit)

            btn_del = QPushButton("🗑️")
            btn_del.setFixedSize(28, 26)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setToolTip("Remove Member Account")
            btn_del.setStyleSheet("background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 4px;")
            btn_del.clicked.connect(lambda _, mem=m: self._on_delete_member_clicked(mem))
            act_layout.addWidget(btn_del)

            self.table.setCellWidget(row_idx, 5, act_widget)

    def _filter_table(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._render_table(self.members_data)
            return
        filtered = [
            m for m in self.members_data
            if q in m.get("full_name", "").lower() or q in m.get("email", "").lower()
        ]
        self._render_table(filtered)

    def _on_add_member_clicked(self) -> None:
        if self.max_members <= 0:
            QMessageBox.information(
                self,
                "Plan Upgrade Required",
                "Team Collaboration is not enabled on your current plan.\n\nPlease upgrade your subscription to invite team members."
            )
            return

        if self.used_members >= self.max_members:
            QMessageBox.warning(
                self,
                "Team Seats Full",
                f"Your plan allows up to {self.max_members} team members.\n\nPlease upgrade your subscription to add more members."
            )
            return

        dlg = AddEditTeamMemberDialog(
            owner_token=self.owner_token,
            available_groups=self.available_groups,
            parent=self
        )
        if dlg.exec() == QDialog.Accepted or dlg.result() == 1:
            self._load_team_data()

    def _on_edit_member_clicked(self, member: Dict[str, Any]) -> None:
        dlg = AddEditTeamMemberDialog(
            owner_token=self.owner_token,
            member_data=member,
            available_groups=self.available_groups,
            parent=self
        )
        if dlg.exec() == QDialog.Accepted or dlg.result() == 1:
            self._load_team_data()

    def _on_delete_member_clicked(self, member: Dict[str, Any]) -> None:
        email = member.get("email", "")
        res = QMessageBox.question(
            self,
            "Remove Team Member",
            f"Are you sure you want to remove team member '{email}'?\nThey will immediately lose access to srkBrowser on their PC.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        import requests
        try:
            url = "https://srbrowser.com/api/v1/team/members/delete"
            r = requests.post(url, json={"id": member["id"]}, headers={"x-license-token": self.owner_token, "Content-Type": "application/json"}, timeout=10)
            data = r.json()
            if data.get("status") == "success":
                QMessageBox.information(self, "Member Removed", data.get("message", "Member removed successfully!"))
                self._load_team_data()
            else:
                QMessageBox.warning(self, "Error", data.get("message", "Failed to remove member."))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to communicate with server: {e}")



