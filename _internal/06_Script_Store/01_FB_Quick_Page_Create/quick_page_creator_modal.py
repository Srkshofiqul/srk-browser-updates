import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QRadioButton,
    QButtonGroup, QFrame, QProgressBar, QMessageBox
)

from quick_page_creator_engine import execute_quick_page_creation, generate_random_page_name


class QuickCreationWorker(QThread):
    finished_signal = Signal(bool, str, str, str, str) # ok, msg/page_id, page_link, name, cat

    def __init__(self, user_data_dir: str, page_name: str, cat_id: str, cat_name: str, headless: bool = False, profile_data: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.user_data_dir = user_data_dir
        self.page_name = page_name
        self.cat_id = cat_id
        self.cat_name = cat_name
        self.headless = headless
        self.profile_data = profile_data or {}

    def run(self):
        ok, p_id, p_link, name, cat = execute_quick_page_creation(
            user_data_dir=self.user_data_dir,
            target_page_name=self.page_name,
            category_id=self.cat_id,
            category_name=self.cat_name,
            headless=self.headless,
            profile_data=self.profile_data
        )
        self.finished_signal.emit(ok, p_id, p_link, name, cat)


class QuickPageCreatorModal(QDialog):
    """
    Cute, Compact & Cyber-Themed 1-Click Page Creator Modal for Profile Cards.
    """
    def __init__(self, profile_data: Optional[Dict[str, Any]] = None, user_data_dir: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile_data = profile_data or {}
        self.user_data_dir = user_data_dir
        self._drag_pos = QPoint()

        prof_num = str(self.profile_data.get("number") or self.profile_data.get("name") or "Profile").strip()
        self.prof_num_text = prof_num

        self.setWindowTitle("Quick Page Creator")
        self.setFixedSize(480, 360)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        main_card = QFrame(self)
        main_card.setStyleSheet("""
            QFrame {
                background-color: #090a18;
                border: 1.5px solid #8b5cf6;
                border-radius: 14px;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel { background: transparent; }
        """)

        layout = QVBoxLayout(main_card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # Header with Drag & Close
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        lbl_icon = QLabel("📄")
        lbl_icon.setStyleSheet("font-size: 24px; border: none;")

        v_title = QVBoxLayout()
        v_title.setSpacing(1)
        lbl_title = QLabel(f"Quick Page Creator — {self.prof_num_text}")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #c084fc; border: none;")
        lbl_sub = QLabel("1-Click Instant Facebook Page Automation")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; border: none;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #94a3b8;
                border: 1px solid #7c3aed44;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
                border: 1px solid #ef4444;
            }
        """)
        btn_close.clicked.connect(self.reject)

        top_bar.addWidget(lbl_icon)
        top_bar.addLayout(v_title)
        top_bar.addStretch()
        top_bar.addWidget(btn_close)
        layout.addLayout(top_bar)

        # Mode Selection (Random vs Custom)
        mode_box = QFrame()
        mode_box.setStyleSheet("""
            QFrame {
                background-color: #04050d;
                border: 1px solid #2b1e4a;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        h_mode = QHBoxLayout(mode_box)
        h_mode.setContentsMargins(10, 4, 10, 4)
        h_mode.setSpacing(16)

        self.radio_random = QRadioButton("🎲 Random Mode")
        self.radio_random.setChecked(True)
        self.radio_random.setCursor(Qt.PointingHandCursor)
        self.radio_random.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 12px; border: none;")

        self.radio_custom = QRadioButton("✏️ Custom Mode")
        self.radio_custom.setCursor(Qt.PointingHandCursor)
        self.radio_custom.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 12px; border: none;")

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.radio_random)
        self.btn_group.addButton(self.radio_custom)
        self.btn_group.buttonClicked.connect(self._on_mode_changed)

        h_mode.addWidget(self.radio_random)
        h_mode.addWidget(self.radio_custom)
        h_mode.addStretch()
        layout.addWidget(mode_box)

        # Inputs Container
        self.inputs_card = QFrame()
        self.inputs_card.setStyleSheet("""
            QFrame {
                background-color: #04050d;
                border: 1px solid #2b1e4a;
                border-radius: 8px;
                padding: 10px;
            }
            QLineEdit, QComboBox {
                background-color: #120b24;
                border: 1px solid #7c3aed66;
                border-radius: 6px;
                color: #f1f5f9;
                font-size: 12px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #c084fc;
            }
        """)
        v_inputs = QVBoxLayout(self.inputs_card)
        v_inputs.setContentsMargins(10, 8, 10, 8)
        v_inputs.setSpacing(8)

        # Page Name Row
        h_name = QHBoxLayout()
        lbl_name = QLabel("📝 Page Name:")
        lbl_name.setStyleSheet("color: #94a3b8; font-size: 11.5px; font-weight: 700; border: none;")
        self.txt_page_name = QLineEdit()
        self.txt_page_name.setPlaceholderText("Enter custom page name...")

        self.btn_shuffle = QPushButton("🎲")
        self.btn_shuffle.setFixedSize(28, 28)
        self.btn_shuffle.setToolTip("Generate another smart name")
        self.btn_shuffle.setCursor(Qt.PointingHandCursor)
        self.btn_shuffle.setStyleSheet("""
            QPushButton {
                background: #1e1338;
                color: #38bdf8;
                border: 1px solid #7c3aed66;
                border-radius: 6px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #2b1a4f;
                color: #ffffff;
            }
        """)
        self.btn_shuffle.clicked.connect(self._shuffle_name)

        h_name.addWidget(lbl_name)
        h_name.addWidget(self.txt_page_name)
        h_name.addWidget(self.btn_shuffle)
        v_inputs.addLayout(h_name)

        # Category Row
        h_cat = QHBoxLayout()
        lbl_cat = QLabel("🏷️ Category:")
        lbl_cat.setStyleSheet("color: #94a3b8; font-size: 11.5px; font-weight: 700; border: none;")
        self.combo_category = QComboBox()
        categories = [
            ("Digital Creator", "2347428775505624"),
            ("Personal Blog", "2700"),
            ("Health/beauty", "2214"),
            ("Beauty, Cosmetic & Care", "139225689474222"),
            ("News & Media Website", "2709"),
            ("Shopping & Retail", "200600219953504"),
            ("Gaming Video Creator", "1350536325044173"),
            ("Clothing (Brand)", "2209"),
            ("Education", "2250"),
            ("Entertainment Website", "2705"),
            ("Entrepreneur", "1617"),
            ("Musician/band", "180164648685982"),
            ("Product/service", "2201"),
            ("Public Figure", "1602"),
            ("Community", "2612"),
            ("Photographer", "181475575221097")
        ]
        for cname, cid in categories:
            self.combo_category.addItem(cname, cid)

        h_cat.addWidget(lbl_cat)
        h_cat.addWidget(self.combo_category)
        v_inputs.addLayout(h_cat)

        layout.addWidget(self.inputs_card)

        # Status & Progress
        self.lbl_status = QLabel("Ready to create page.")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; border: none;")
        layout.addWidget(self.lbl_status)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setVisible(False)
        self.prog_bar.setFixedHeight(4)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #120b24;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #38bdf8);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.prog_bar)

        # Action Buttons
        h_actions = QHBoxLayout()
        h_actions.setSpacing(10)

        btn_cancel = QPushButton("✖ Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #94a3b8;
                border: 1px solid #7c3aed44;
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #2b1a4f;
                color: #ffffff;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        self.btn_create = QPushButton("⚡ Create Page Now")
        self.btn_create.setCursor(Qt.PointingHandCursor)
        self.btn_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 22px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
            }
            QPushButton:disabled {
                background: #231942;
                color: #64748b;
            }
        """)
        self.btn_create.clicked.connect(self._start_creation)

        h_actions.addWidget(btn_cancel)
        h_actions.addStretch()
        h_actions.addWidget(self.btn_create)
        layout.addLayout(h_actions)

        root_layout.addWidget(main_card)

        # Initial mode setup
        self._shuffle_name()
        self._on_mode_changed()

    def _shuffle_name(self):
        rand_name = generate_random_page_name(self.profile_data)
        self.txt_page_name.setText(rand_name)

    def _on_mode_changed(self):
        is_custom = self.radio_custom.isChecked()
        self.txt_page_name.setEnabled(is_custom)
        self.btn_shuffle.setEnabled(not is_custom)
        if not is_custom:
            self._shuffle_name()

    def _start_creation(self):
        target_name = self.txt_page_name.text().strip()
        if not target_name:
            target_name = generate_random_page_name(self.profile_data)
            self.txt_page_name.setText(target_name)

        cat_id = self.combo_category.currentData()
        cat_name = self.combo_category.currentText()

        self.btn_create.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.lbl_status.setText(f"⏳ Creating '{target_name}' in Facebook backend...")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700; border: none;")

        self.worker = QuickCreationWorker(
            user_data_dir=self.user_data_dir,
            page_name=target_name,
            cat_id=cat_id,
            cat_name=cat_name,
            headless=False,
            profile_data=self.profile_data
        )
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, ok: bool, page_id: str, page_link: str, name: str, cat: str):
        self.prog_bar.setVisible(False)
        self.btn_create.setEnabled(True)

        if ok:
            self.lbl_status.setText(f"🟢 Success! '{name}' created (ID: {page_id})")
            self.lbl_status.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 700; border: none;")
            self.btn_create.setText("✨ Create Another Page")
            if not self.radio_custom.isChecked():
                self._shuffle_name()
        else:
            self.lbl_status.setText(f"🔴 Failed: {page_id}")
            self.lbl_status.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700; border: none;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


def show_quick_page_creator(profile_data: Optional[Dict[str, Any]] = None, user_data_dir: str = "", parent: Optional[QWidget] = None) -> bool:
    """Entry point helper for launching QuickPageCreatorModal."""
    dialog = QuickPageCreatorModal(profile_data=profile_data, user_data_dir=user_data_dir, parent=parent)
    return dialog.exec() == QDialog.DialogCode.Accepted
