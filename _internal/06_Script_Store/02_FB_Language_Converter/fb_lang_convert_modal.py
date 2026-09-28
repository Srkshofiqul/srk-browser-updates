import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QDoubleSpinBox,
    QFrame, QProgressBar, QMessageBox, QTextEdit
)

from fb_language_converter_engine import execute_language_conversion, SUPPORTED_LOCALES


class LanguageConversionWorker(QThread):
    finished_signal = Signal(bool, str) # ok, msg
    log_signal = Signal(str)

    def __init__(self, user_data_dir: str, target_locale: str, delay_sec: float, headless: bool):
        super().__init__()
        self.user_data_dir = user_data_dir
        self.target_locale = target_locale
        self.delay_sec = delay_sec
        self.headless = headless

    def run(self):
        ok, msg = execute_language_conversion(
            user_data_dir=self.user_data_dir,
            target_locale=self.target_locale,
            delay_sec=self.delay_sec,
            headless=self.headless,
            log_func=lambda m: self.log_signal.emit(str(m))
        )
        self.finished_signal.emit(ok, msg)


class FbLanguageConverterModal(QDialog):
    """
    Sleek, High-Tech Cyber 1-Click Language Converter Modal for Profile Cards.
    """
    def __init__(
        self,
        profile_data: Optional[Dict[str, Any]] = None,
        user_data_dir: str = "",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.profile_data = profile_data or {}
        self.user_data_dir = user_data_dir
        self._drag_pos = QPoint()

        prof_num = str(self.profile_data.get("number") or self.profile_data.get("name") or "Profile").strip()
        self.prof_num_text = prof_num

        self.setWindowTitle("Facebook Language Converter")
        self.setFixedSize(480, 420)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)

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
        root_layout.addWidget(main_card)

        layout = QVBoxLayout(main_card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header with Drag & Close
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        lbl_icon = QLabel("🌐")
        lbl_icon.setStyleSheet("font-size: 24px; border: none;")

        v_title = QVBoxLayout()
        v_title.setSpacing(1)
        lbl_title = QLabel(f"Language Converter — {self.prof_num_text}")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #c084fc; border: none;")
        lbl_sub = QLabel("1-Click Instant Facebook Account Locale Switcher")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; border: none;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #1e1e38;
                color: #94a3b8;
                border: 1px solid #3b3b5c;
                border-radius: 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #e11d48;
                color: #ffffff;
                border-color: #f43f5e;
            }
        """)
        btn_close.clicked.connect(self.close)

        top_bar.addWidget(lbl_icon)
        top_bar.addLayout(v_title)
        top_bar.addStretch(1)
        top_bar.addWidget(btn_close)
        layout.addLayout(top_bar)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1e1b4b; max-height: 1px; border: none; background-color: #1e1b4b;")
        layout.addWidget(sep)

        # Language Selection Section
        lbl_sel = QLabel("🎯 Target Facebook Language:")
        lbl_sel.setStyleSheet("font-weight: 700; font-size: 12px; color: #38bdf8; border: none;")
        layout.addWidget(lbl_sel)

        self.cmb_locale = QComboBox()
        self.cmb_locale.setFixedHeight(34)
        for code, label in SUPPORTED_LOCALES.items():
            self.cmb_locale.addItem(f"{label} ({code})", code)
        self.cmb_locale.setCurrentIndex(0) # Default en_US
        self.cmb_locale.setStyleSheet("""
            QComboBox {
                background-color: #0f172a;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QComboBox:hover {
                border-color: #8b5cf6;
            }
            QComboBox QAbstractItemView {
                background-color: #090a18;
                color: #38bdf8;
                selection-background-color: #1e1b4b;
                selection-color: #c084fc;
                border: 1px solid #8b5cf6;
            }
        """)
        layout.addWidget(self.cmb_locale)

        # Options Row: Anti-Bot Delay & Headless
        opt_row = QHBoxLayout()
        opt_row.setSpacing(12)

        lbl_delay = QLabel("⏱️ Anti-Bot Delay:")
        lbl_delay.setStyleSheet("color: #c084fc; font-size: 11px; font-weight: 700; border: none;")
        self.spn_delay = QDoubleSpinBox()
        self.spn_delay.setRange(0.5, 10.0)
        self.spn_delay.setValue(1.5)
        self.spn_delay.setSingleStep(0.5)
        self.spn_delay.setSuffix("s")
        self.spn_delay.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spn_delay.setFixedHeight(28)
        self.spn_delay.setFixedWidth(52)
        self.spn_delay.setAlignment(Qt.AlignCenter)
        self.spn_delay.setStyleSheet("""
            QDoubleSpinBox {
                background: #0f172a;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            }
        """)

        self.chk_headless = QCheckBox("👻 Headless Mode")
        self.chk_headless.setChecked(True)
        self.chk_headless.setStyleSheet("""
            QCheckBox {
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 700;
                border: none;
            }
        """)

        opt_row.addWidget(lbl_delay)
        opt_row.addWidget(self.spn_delay)
        opt_row.addStretch(1)
        opt_row.addWidget(self.chk_headless)
        layout.addLayout(opt_row)

        # Mini Log Box
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(80)
        self.txt_log.setStyleSheet("""
            QTextEdit {
                background-color: #030712;
                color: #4ade80;
                font-family: 'Consolas', monospace;
                font-size: 10.5px;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        self.txt_log.setText("⚡ Ready. Select target language and click 'Convert Language Now'.")
        layout.addWidget(self.txt_log)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0) # indeterminate
        self.progress_bar.hide()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e1b4b;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #38bdf8);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_convert = QPushButton("⚡ Convert Language Now")
        self.btn_convert.setFixedHeight(38)
        self.btn_convert.setCursor(Qt.PointingHandCursor)
        self.btn_convert.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                font-weight: 800;
                font-size: 12.5px;
                border: none;
                border-radius: 8px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
            }
            QPushButton:disabled {
                background: #1e1b4b;
                color: #64748b;
            }
        """)
        self.btn_convert.clicked.connect(self._on_convert_clicked)

        btn_box.addWidget(self.btn_convert)
        layout.addLayout(btn_box)

    def _append_log(self, text: str):
        self.txt_log.append(text)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def _on_convert_clicked(self):
        target_locale = self.cmb_locale.currentData()
        delay_sec = self.spn_delay.value()
        headless = self.chk_headless.isChecked()

        if not self.user_data_dir:
            self._append_log("❌ Error: Profile user data directory not specified.")
            return

        self.btn_convert.setEnabled(False)
        self.progress_bar.show()
        self.txt_log.clear()
        self._append_log(f"🚀 Starting Language Conversion to {target_locale}...")

        self.worker = LanguageConversionWorker(
            user_data_dir=self.user_data_dir,
            target_locale=target_locale,
            delay_sec=delay_sec,
            headless=headless
        )
        self.worker.log_signal.connect(self._append_log)
        self.worker.finished_signal.connect(self._on_conversion_finished)
        self.worker.start()

    def _on_conversion_finished(self, ok: bool, msg: str):
        self.btn_convert.setEnabled(True)
        self.progress_bar.hide()
        if ok:
            self._append_log(f"🎉 Success: {msg}")
        else:
            self._append_log(f"⚠️ Failed: {msg}")

    # Drag window handlers
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
