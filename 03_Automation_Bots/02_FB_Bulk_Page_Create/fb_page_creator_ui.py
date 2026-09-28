# -*- coding: utf-8 -*-
"""
⚡ Facebook Bulk Page Creator Studio (Ultra-Compact Clean Redesign)
Theme: Cyber Blood-Crimson & Ice-Cyan Hacker Edition
Author: srkBrowser Automation Lab
Description: Elite Cyberpunk / Hacker theme with Neon Crimson Blood-Red accents,
Electric Ice-Cyan highlights, and deep carbon-black stealth architecture.
"""

import os
import sys
import time
import re
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Set, Union

from PySide6.QtCore import Qt, QTimer, QPoint, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QCheckBox, QProgressBar, QTextEdit, QPlainTextEdit, QFrame,
    QMessageBox, QFileDialog, QSizePolicy, QButtonGroup, QRadioButton
)

# Import security, helpers and engine
from fb_page_creator_security import check_srbrowser_heartbeat, get_effective_bot_license
from fb_page_creator_helpers import (
    OPENPYXL_AVAILABLE, 
    parse_page_names_file_or_text,
    export_created_pages_report
)
from fb_page_creator_engine import PageCreatorWorkerThread, kill_all_bot_browsers
from fb_page_creator_proxy_bridge import test_proxy_connection, test_multiple_proxies


class PastePageNamesModal(QDialog):
    """
    Cyber-Styled Modal Dialog for pasting multi-line Facebook Page Names.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📝 Paste Facebook Page Names")
        self.resize(540, 390)
        self.setStyleSheet("""
            QDialog {
                background-color: #07060c;
                color: #e2e8f0;
                font-family: 'Segoe UI', system-ui, sans-serif;
                border: 1.5px solid #ff2a5f;
                border-radius: 12px;
            }
            QLabel { color: #e2e8f0; }
            QTextEdit {
                background-color: #030307;
                color: #38bdf8;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
                font-size: 11.5px;
                border: 1px solid #4a152d;
                border-radius: 6px;
                padding: 10px;
            }
            QTextEdit:focus {
                border: 1px solid #ff2a5f;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        lbl_title = QLabel("📝 Paste Facebook Page Names")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #ff3366;")

        lbl_hint = QLabel(
            "📋 Enter Page Names (1 per line):\n"
            "  • Names are assigned serially to profiles (Profile 1 ➔ Name 1, Profile 2 ➔ Name 2...)\n"
            "  • If list is empty, bot automatically generates dynamic auto-branding names."
        )
        lbl_hint.setStyleSheet("font-size: 11px; color: #94a3b8; background: #0e0a16; border: 1px solid #2d162a; border-radius: 6px; padding: 7px;")

        self.txt_content = QTextEdit()
        self.txt_content.setPlaceholderText("Tech Zone Pro\nDigital Media Studio\nCreative Studio BD\nSmart Trend Lifestyle\n...")
        self.txt_content.textChanged.connect(self._update_counter)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.lbl_count = QLabel("📋 0 names entered")
        self.lbl_count.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")

        btn_cancel = QPushButton("✖ Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #110d1c;
                color: #94a3b8;
                border: 1px solid #241d33;
                border-radius: 5px;
                padding: 6px 16px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #1e1730;
                color: #f1f5f9;
            }
        """)
        btn_clear = QPushButton("🗑️ Clear")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet("""
            QPushButton {
                background: #1c080d;
                color: #f43f5e;
                border: 1px solid #f43f5e55;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #330b14;
                color: #fda4af;
                border-color: #f43f5e;
            }
        """)
        btn_clear.clicked.connect(self._clear_content)

        btn_cancel.clicked.connect(self.reject)

        btn_load = QPushButton("💾 Load Page Names")
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:0.5 #e11d48, stop:1 #ff2a5f);
                color: #ffffff;
                border: 1px solid #ff6b8b;
                border-radius: 5px;
                padding: 6px 18px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:0.5 #f43f5e, stop:1 #ff477e);
            }
        """)
        btn_load.clicked.connect(self.accept)

        btn_box.addWidget(self.lbl_count)
        btn_box.addStretch(1)
        btn_box.addWidget(btn_clear)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_load)

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_hint)
        layout.addWidget(self.txt_content, 1)
        layout.addLayout(btn_box)

    def _clear_content(self) -> None:
        self.txt_content.clear()
        self._update_counter()

    def _update_counter(self) -> None:
        text = self.txt_content.toPlainText().strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        c = len(lines)
        self.lbl_count.setText(f"📋 {c} name{'s' if c != 1 else ''} entered")

    def get_text(self) -> str:
        return self.txt_content.toPlainText().strip()



class ProxyTestWorker(QThread):
    result_ready = Signal(bool, str, str)  # ok, summary, country_or_detail

    def __init__(self, proxy_input: Union[str, List[str]], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        if isinstance(proxy_input, str):
            self.proxy_list = [
                line.strip() for line in proxy_input.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        else:
            self.proxy_list = [
                str(p).strip() for p in proxy_input
                if str(p).strip() and not str(p).strip().startswith("#")
            ]

    def run(self) -> None:
        if not self.proxy_list:
            self.result_ready.emit(False, "⚠️ No proxy string entered", "")
            return

        if len(self.proxy_list) == 1:
            ok, ip_or_err, country = test_proxy_connection(self.proxy_list[0], timeout=7.0)
            if ok:
                loc = f" ({country})" if country else ""
                self.result_ready.emit(True, f"🟢 1/1 Live: {ip_or_err}{loc}", country)
            else:
                self.result_ready.emit(False, f"🔴 Failed: {ip_or_err[:32]}", "")
        else:
            res = test_multiple_proxies(self.proxy_list, timeout=6.0)
            total = res.get("total", 0)
            success_count = res.get("success_count", 0)
            failed_count = res.get("failed_count", 0)
            results = res.get("results", [])

            if success_count == total and total > 0:
                countries = list(dict.fromkeys([r["country"] for r in results if r.get("country")]))
                c_str = f" [{', '.join(countries[:3])}]" if countries else ""
                first_ip = next((r["ip_or_err"] for r in results if r.get("ok")), "")
                self.result_ready.emit(True, f"🟢 All {total}/{total} Proxies Live{c_str} (e.g. {first_ip})", "")
            elif success_count > 0:
                first_ip = next((r["ip_or_err"] for r in results if r.get("ok")), "")
                self.result_ready.emit(True, f"🟡 {success_count}/{total} Live ({failed_count} Failed) • {first_ip}", "")
            else:
                self.result_ready.emit(False, f"🔴 All {total} Proxies Failed (Timeout / Refused)", "")


class ProxySettingsModal(QDialog):
    """
    Elite Cyber-Themed Modal Dialog for Residential Proxy Configuration & Connectivity Testing.
    Features a clean multi-line textarea displaying at least 5 lines of proxies,
    real-time count badges, round-robin auto-rotation hints, and parallel testing.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Residential Proxy Configuration")
        self.setFixedSize(480, 390)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos = QPoint()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        main_card = QFrame(self)
        main_card.setStyleSheet("""
            QFrame#MainCard {
                background-color: #0b0816;
                border: 1.5px solid #db277788;
                border-radius: 14px;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel { background: transparent; }
        """)
        main_card.setObjectName("MainCard")
        root_layout.addWidget(main_card)

        layout = QVBoxLayout(main_card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        # 1. Header with Icon Badge, Title & Close Button
        h_header = QHBoxLayout()
        h_header.setSpacing(10)

        lbl_icon = QLabel("🛡️")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setFixedSize(28, 28)
        lbl_icon.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2c123b, stop:1 #130a22);
                border: 1px solid #db277766;
                border-radius: 6px;
                font-size: 14px;
            }
        """)

        lbl_title = QLabel("Residential Proxy Configuration")
        lbl_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #fdf2f8; letter-spacing: 0.3px; border: none;")

        btn_x = QPushButton("✕")
        btn_x.setFixedSize(22, 22)
        btn_x.setCursor(Qt.PointingHandCursor)
        btn_x.setStyleSheet("""
            QPushButton {
                background: #170d22;
                color: #94a3b8;
                border: 1px solid #311c42;
                border-radius: 11px;
                font-weight: bold;
                font-size: 10.5px;
            }
            QPushButton:hover { background: #ef4444; color: #ffffff; border-color: #ef4444; }
        """)
        btn_x.clicked.connect(self.reject)

        h_header.addWidget(lbl_icon)
        h_header.addWidget(lbl_title, 1)
        h_header.addWidget(btn_x)
        layout.addLayout(h_header)

        # 2. Enable Proxy Checkbox
        self.chk_enable = QCheckBox("Enable Residential Proxy for Page Creation")
        self.chk_enable.setCursor(Qt.PointingHandCursor)
        self.chk_enable.setStyleSheet("""
            QCheckBox {
                color: #38bdf8;
                font-size: 11.5px;
                font-weight: 700;
                spacing: 8px;
            }
            QCheckBox:hover { color: #67e8f9; }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1.5px solid #0284c7;
                border-radius: 4px;
                background-color: #05050f;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border: 1.5px solid #38bdf8;
            }
        """)
        layout.addWidget(self.chk_enable)

        # 3. Proxy Input Section Label
        lbl_inp = QLabel("Proxy List (One per line, min 5 recommended):")
        lbl_inp.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 700;")
        layout.addWidget(lbl_inp)

        # 4. Multi-Line Textarea (displays 5 lines comfortably)
        self.txt_proxy = QPlainTextEdit()
        self.txt_proxy.setFixedHeight(105)

        # Subtle translucent shadow/watermark palette for placeholder text
        pal_proxy = self.txt_proxy.palette()
        pal_proxy.setColor(QPalette.ColorRole.PlaceholderText, QColor("#54607b"))
        self.txt_proxy.setPalette(pal_proxy)

        self.txt_proxy.setPlaceholderText(
            "Format Examples (One proxy per line):\n"
            "user:password@hostname:port  (e.g. DataImpulse)\n"
            "hostname:port:user:password\n"
            "gw.dataimpulse.com:10000:username:password\n"
            "user:pass@host:port"
        )
        self.txt_proxy.setStyleSheet("""
            QPlainTextEdit {
                background-color: #06040d;
                color: #f1f5f9;
                border: 1px solid #332049;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
                line-height: 1.35;
                selection-background-color: #db2777;
                selection-color: #ffffff;
            }
            QPlainTextEdit:focus {
                border: 1.5px solid #ec4899;
                background-color: #0a0614;
            }
            QScrollBar:vertical {
                background: #090614;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #2d1838;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #db2777;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        layout.addWidget(self.txt_proxy)

        # 5. Routing Mode Selection Box
        mode_box = QFrame()
        mode_box.setStyleSheet("""
            QFrame {
                background: #090614;
                border: 1px solid #231638;
                border-radius: 8px;
            }
        """)
        v_mode = QVBoxLayout(mode_box)
        v_mode.setContentsMargins(10, 8, 10, 8)
        v_mode.setSpacing(6)

        lbl_m_head = QLabel("Routing Mode:")
        lbl_m_head.setStyleSheet("color: #c084fc; font-size: 10.5px; font-weight: 800; border: none;")
        v_mode.addWidget(lbl_m_head)

        self.radio_dynamic = QRadioButton("⚡ Dynamic Mode (Recommended)")
        self.radio_dynamic.setChecked(True)
        self.radio_dynamic.setCursor(Qt.PointingHandCursor)
        self.radio_dynamic.setStyleSheet("""
            QRadioButton { color: #38bdf8; font-size: 11px; font-weight: 700; spacing: 6px; border: none; }
            QRadioButton::indicator { width: 13px; height: 13px; border-radius: 6px; border: 1.5px solid #0284c7; background: #06060e; }
            QRadioButton::indicator:checked { background: #38bdf8; border: 2px solid #0369a1; }
        """)

        self.radio_full = QRadioButton("🌐 Full Session Mode")
        self.radio_full.setCursor(Qt.PointingHandCursor)
        self.radio_full.setStyleSheet("""
            QRadioButton { color: #cbd5e1; font-size: 11px; font-weight: 700; spacing: 6px; border: none; }
            QRadioButton::indicator { width: 13px; height: 13px; border-radius: 6px; border: 1.5px solid #64748b; background: #06060e; }
            QRadioButton::indicator:checked { background: #f43f5e; border: 2px solid #be123c; }
        """)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_dynamic)
        self.mode_group.addButton(self.radio_full)

        v_mode.addWidget(self.radio_dynamic)
        v_mode.addWidget(self.radio_full)
        layout.addWidget(mode_box)

        # 6. Test Connection Row
        h_test = QHBoxLayout()
        h_test.setSpacing(10)

        self.btn_test = QPushButton("⚡ Test Proxies")
        self.btn_test.setCursor(Qt.PointingHandCursor)
        self.btn_test.setFixedSize(110, 28)
        self.btn_test.setStyleSheet("""
            QPushButton {
                background: #1f081c;
                color: #f472b6;
                border: 1px solid #db277788;
                border-radius: 6px;
                padding: 3px 10px;
                font-weight: 800;
                font-size: 10.5px;
            }
            QPushButton:hover { background: #350c2e; color: #ffffff; border-color: #ec4899; }
            QPushButton:disabled { background: #130919; color: #64748b; border-color: #291833; }
        """)
        self.btn_test.clicked.connect(self._on_test_clicked)

        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setFixedHeight(26)
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.hide()

        h_test.addWidget(self.btn_test)
        h_test.addWidget(self.lbl_test_result, 1)
        layout.addLayout(h_test)

        layout.addStretch()

        # 7. Bottom Action Buttons
        h_action = QHBoxLayout()
        h_action.setSpacing(10)

        btn_cancel = QPushButton("✖ Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #110d1c;
                color: #94a3b8;
                border: 1px solid #241d33;
                border-radius: 6px;
                padding: 4px 18px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background: #1e1730; color: #f1f5f9; border-color: #3b2d54; }
        """)
        btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("💾 Save && Apply")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(28)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #db2777, stop:1 #ec4899);
                color: #ffffff;
                border: 1px solid #f472b6;
                border-radius: 6px;
                padding: 4px 22px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ec4899, stop:1 #f472b6);
            }
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)

        h_action.addStretch()
        h_action.addWidget(btn_cancel)
        h_action.addWidget(self.btn_save)
        layout.addLayout(h_action)

        main_card.mousePressEvent = self.mousePressEvent
        main_card.mouseMoveEvent = self.mouseMoveEvent
        main_card.mouseReleaseEvent = self.mouseReleaseEvent

        self._load_current_config()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = QPoint()

    def _update_counter(self) -> None:
        pass

    def _get_config_path(self) -> Path:
        return Path(__file__).resolve().parent / "fb_page_creator_proxy_config.json"

    def _load_current_config(self) -> None:
        cfg = self._get_config_path()
        if cfg.exists():
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.chk_enable.setChecked(bool(data.get("enabled", False)))
                raw_p = str(data.get("proxy_string", "")).strip()
                if not raw_p and "proxies" in data and isinstance(data["proxies"], list):
                    raw_p = "\n".join(str(p).strip() for p in data["proxies"])
                self.txt_proxy.setPlainText(raw_p)
                self._update_counter()
                if str(data.get("mode", "dynamic")).lower() == "full":
                    self.radio_full.setChecked(True)
                else:
                    self.radio_dynamic.setChecked(True)
            except Exception:
                pass

    def _on_test_clicked(self) -> None:
        raw = self.txt_proxy.toPlainText().strip()
        lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
        if not lines:
            self.lbl_test_result.setText("⚠️ Enter proxy string(s) first")
            self.lbl_test_result.setStyleSheet("""
                background-color: #21160a; color: #f59e0b;
                font-size: 10.5px; font-weight: 700;
                border: 1px solid #d9770688; border-radius: 4px;
                padding: 2px 8px;
            """)
            self.lbl_test_result.show()
            return

        self.btn_test.setEnabled(False)
        test_msg = "⏳ Testing proxy..." if len(lines) == 1 else f"⏳ Testing {len(lines)} proxies in parallel..."
        self.lbl_test_result.setText(test_msg)
        self.lbl_test_result.setStyleSheet("""
            background-color: #0b1928; color: #38bdf8;
            font-size: 10.5px; font-weight: 700;
            border: 1px solid #0284c788; border-radius: 4px;
            padding: 2px 8px;
        """)
        self.lbl_test_result.show()

        self.test_worker = ProxyTestWorker(lines, self)
        self.test_worker.result_ready.connect(self._apply_test_res)
        self.test_worker.start()

    def _apply_test_res(self, ok: bool, ip_or_summary: str, country: str) -> None:
        self.btn_test.setEnabled(True)
        if ok:
            self.lbl_test_result.setText(ip_or_summary)
            self.lbl_test_result.setStyleSheet("""
                background-color: #061f14; color: #34d399;
                font-size: 10.5px; font-weight: 800;
                border: 1px solid #05966988; border-radius: 4px;
                padding: 2px 8px;
            """)
        else:
            self.lbl_test_result.setText(ip_or_summary)
            self.lbl_test_result.setStyleSheet("""
                background-color: #1f070a; color: #f87171;
                font-size: 10.5px; font-weight: 800;
                border: 1px solid #dc262688; border-radius: 4px;
                padding: 2px 8px;
            """)
        self.lbl_test_result.show()

    def _on_save_clicked(self) -> None:
        cfg = self._get_config_path()
        raw_text = self.txt_proxy.toPlainText().strip()
        lines = [l.strip() for l in raw_text.splitlines() if l.strip() and not l.strip().startswith("#")]
        data = {
            "enabled": self.chk_enable.isChecked(),
            "proxy_string": raw_text,
            "proxies": lines,
            "mode": "full" if self.radio_full.isChecked() else "dynamic"
        }
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
        self.accept()


class AutomationFinishedModal(QDialog):
    """
    Cyber-Themed Frameless Completion Modal for FB Page Creator.
    """
    def __init__(self, summary_text: str, report_path: str, success_count: int, failed_count: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.report_path = report_path
        self.setWindowTitle("Task Completed")
        self.setFixedSize(460, 240)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos = QPoint()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        main_card = QFrame(self)
        main_card.setStyleSheet("""
            QFrame {
                background-color: #08070e;
                border: 1.5px solid #ff2a5f;
                border-radius: 12px;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel { background: transparent; }
        """)

        layout = QVBoxLayout(main_card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Header with Icon & Close Button
        h_header = QHBoxLayout()
        h_header.setSpacing(10)
        lbl_icon = QLabel("🎉")
        lbl_icon.setStyleSheet("font-size: 24px; border: none;")

        v_head = QVBoxLayout()
        v_head.setSpacing(1)
        lbl_title = QLabel("Facebook Page Creation Finished!")
        lbl_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #ff3366; border: none;")
        lbl_sub = QLabel("Automation pipeline finished all queued profile tasks.")
        lbl_sub.setStyleSheet("font-size: 10.5px; color: #94a3b8; border: none;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)

        btn_x = QPushButton("✕")
        btn_x.setFixedSize(22, 22)
        btn_x.setCursor(Qt.PointingHandCursor)
        btn_x.setStyleSheet("""
            QPushButton {
                background: #170d18;
                color: #94a3b8;
                border: 1px solid #2d182e;
                border-radius: 11px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #ef4444; color: white; border-color: #ef4444; }
        """)
        btn_x.clicked.connect(self.accept)

        h_header.addWidget(lbl_icon)
        h_header.addLayout(v_head, 1)
        h_header.addWidget(btn_x)
        layout.addLayout(h_header)

        # Stats Deck Row
        h_stats = QHBoxLayout()
        h_stats.setSpacing(8)

        def make_stat_box(title: str, val: str, color: str, bg: str, border: str) -> QFrame:
            f = QFrame()
            f.setFixedHeight(50)
            f.setStyleSheet(f"background: {bg}; border: 1px solid {border}; border-radius: 6px;")
            v = QVBoxLayout(f)
            v.setContentsMargins(6, 4, 6, 4)
            v.setSpacing(0)
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-size: 9.5px; font-weight: 700; color: #94a3b8; border: none;")
            lbl_v = QLabel(val)
            lbl_v.setStyleSheet(f"font-size: 16px; font-weight: 900; color: {color}; border: none;")
            v.addWidget(lbl_t)
            v.addWidget(lbl_v)
            return f

        h_stats.addWidget(make_stat_box("SUCCESSFUL", str(success_count), "#4ade80", "#052617", "#166534"))
        h_stats.addWidget(make_stat_box("FAILED", str(failed_count), "#ff4d6d", "#290812", "#991b1b"))
        h_stats.addWidget(make_stat_box("TOTAL PROCESSED", str(success_count + failed_count), "#38bdf8", "#081729", "#0284c7"))
        layout.addLayout(h_stats)

        layout.addStretch()

        # Action Buttons
        h_btns = QHBoxLayout()
        h_btns.setSpacing(8)

        if report_path and os.path.exists(report_path):
            btn_open_file = QPushButton("📑 Open Excel Report")
            btn_open_file.setCursor(Qt.PointingHandCursor)
            btn_open_file.setStyleSheet("""
                QPushButton {
                    background: #0c182b;
                    color: #38bdf8;
                    border: 1px solid #0284c7;
                    border-radius: 5px;
                    padding: 5px 14px;
                    font-size: 11px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background: #142a4a;
                    color: #ffffff;
                    border: 1px solid #38bdf8;
                }
            """)
            btn_open_file.clicked.connect(self._open_report_file)
            h_btns.addWidget(btn_open_file)

        btn_ok = QPushButton("✨ Great, Done")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:0.5 #e11d48, stop:1 #ff2a5f);
                color: #ffffff;
                border: 1px solid #ff6b8b;
                border-radius: 5px;
                padding: 5px 18px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:0.5 #f43f5e, stop:1 #ff477e);
            }
        """)
        btn_ok.clicked.connect(self.accept)

        h_btns.addStretch()
        h_btns.addWidget(btn_ok)
        layout.addLayout(h_btns)

        root_layout.addWidget(main_card)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _open_report_file(self) -> None:
        if self.report_path and os.path.exists(self.report_path):
            if sys.platform == "win32":
                os.startfile(self.report_path)
            else:
                subprocess.Popen(["xdg-open", self.report_path])


class CreateNewGroupModal(QDialog):
    """
    Cyber-Styled Modal Dialog for creating a new profile group.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📁 Create New Profile Group")
        self.resize(420, 195)
        self.setStyleSheet("""
            QDialog {
                background-color: #07060c;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
                border: 1.5px solid #ff2a5f;
                border-radius: 10px;
            }
            QLabel { color: #f1f5f9; }
            QLineEdit {
                background-color: #0e0a16;
                color: #ff6b8b;
                border: 1px solid #4a152d;
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QLineEdit:focus {
                border: 1px solid #ff2a5f;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        lbl_title = QLabel("📁 Create New Profile Group")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #ff3366;")

        lbl_hint = QLabel("Enter a name for the new group (e.g. 'Page_Failed_Accounts'):")
        lbl_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Page_Failed_Accounts")
        self.txt_name.returnPressed.connect(self._on_accept)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        btn_cancel = QPushButton("✖ Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #110d1c;
                color: #94a3b8;
                border: 1px solid #241d33;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #1e1730;
                color: #f1f5f9;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        self.btn_create = QPushButton("➕ Create Group")
        self.btn_create.setCursor(Qt.PointingHandCursor)
        self.btn_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:0.5 #e11d48, stop:1 #ff2a5f);
                color: #ffffff;
                border: 1px solid #ff6b8b;
                border-radius: 5px;
                padding: 6px 18px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:0.5 #f43f5e, stop:1 #ff477e);
            }
        """)
        self.btn_create.clicked.connect(self._on_accept)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_create)

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_hint)
        layout.addWidget(self.txt_name)
        layout.addLayout(btn_box)

    def _on_accept(self) -> None:
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid group name.")
            return
        self.accept()

    def get_group_name(self) -> str:
        return self.txt_name.text().strip()


class MasterBotStudioDialog(QDialog):
    """
    Sleek, Compact Multi-Threaded Facebook Bulk Page Creator Studio.
    Layout: Ultra-clean, proportional, spacious layout matching Bot #3.
    Theme: Cyber Blood-Crimson & Ice-Cyan Hacker Edition.
    """

    def __init__(
        self,
        profile_mgr: Optional[Any] = None,
        parent: Optional[QWidget] = None,
        bot_id: str = "fb_bulk_page_create",
        bot_title: str = "⚡ Facebook Bulk Page Creator Studio",
        *args,
        **kwargs
    ) -> None:
        # Flexible argument handling: supports (profile_mgr, parent) or (profile_mgr, bot_id, bot_title, parent)
        if isinstance(parent, str):
            bot_id = parent
            parent = kwargs.get("parent")
        elif parent is not None and not isinstance(parent, QWidget):
            parent = None

        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.bot_id = str(bot_id or "fb_bulk_page_create")
        self.bot_title = str(bot_title or "⚡ Facebook Bulk Page Creator Studio")

        self.loaded_page_names: List[str] = []
        self.worker_thread: Optional[PageCreatorWorkerThread] = None
        self.is_duplicate = False
        self._drag_pos = QPoint()

        # All profiles
        self.all_profiles: List[Dict[str, Any]] = []
        if self.profile_mgr and hasattr(self.profile_mgr, "get_all_profiles"):
            self.all_profiles = self.profile_mgr.get_all_profiles()

        self._init_window()
        self._build_ui()
        self._populate_groups()
        self._update_db_counter()
        # Default to Method 2 (API) on startup
        if hasattr(self, "combo_method"):
            self.combo_method.setCurrentIndex(1)
        self._update_proxy_btn_state()

        # Live heartbeat check timer
        self._check_srbrowser_heartbeat()
        self.timer_hb = QTimer(self)
        self.timer_hb.timeout.connect(self._check_srbrowser_heartbeat)
        self.timer_hb.start(3000)

    def _init_window(self) -> None:
        self.setFixedSize(740, 480)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(f"{self.bot_title} — Professional Automation Studio")

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # Outer Main Card with Glowing Border & Void Background (Matching FB Bulk Login Studio)
        self.main_card = QFrame()
        self.main_card.setObjectName("MainCard")
        self.main_card.setStyleSheet("""
            QFrame#MainCard {
                background-color: #0b071a;
                border: 1.5px solid #232545;
                border-radius: 12px;
            }
        """)
        root_layout.addWidget(self.main_card)

        card_layout = QVBoxLayout(self.main_card)
        card_layout.setContentsMargins(12, 6, 12, 6)
        card_layout.setSpacing(3)

        # Enable dragging directly on main card
        self.main_card.mousePressEvent = self.mousePressEvent
        self.main_card.mouseMoveEvent = self.mouseMoveEvent
        self.main_card.mouseReleaseEvent = self.mouseReleaseEvent

        # -------------------------------------------------------------
        # 1. HEADER BAR (Ultra-clean Cyber Deck matching Studio)
        # -------------------------------------------------------------
        h_head = QHBoxLayout()
        h_head.setContentsMargins(0, 0, 0, 0)
        h_head.setSpacing(8)

        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 16px; border: none; background: transparent; color: #f43f5e;")

        self.lbl_title = QLabel("Facebook Bulk Page Creator Bot")
        self.lbl_title.setStyleSheet("""
            color: #c084fc;
            font-size: 15px;
            font-weight: 800;
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: transparent;
            border: none;
            letter-spacing: 0.3px;
        """)

        # Enable dragging on title and icon
        self.lbl_title.mousePressEvent = self.mousePressEvent
        self.lbl_title.mouseMoveEvent = self.mouseMoveEvent
        self.lbl_title.mouseReleaseEvent = self.mouseReleaseEvent
        lbl_icon.mousePressEvent = self.mousePressEvent
        lbl_icon.mouseMoveEvent = self.mouseMoveEvent
        lbl_icon.mouseReleaseEvent = self.mouseReleaseEvent

        # Live srkBrowser Core Active Status Badge
        self.lbl_srbrowser_status = QLabel("🟢 srkBrowser Active")
        self.lbl_srbrowser_status.setFixedHeight(24)
        self.lbl_srbrowser_status.setStyleSheet("""
            QLabel {
                background-color: #052415;
                color: #4ade80;
                font-size: 11px;
                font-weight: 800;
                border: 1px solid #05966988;
                border-radius: 5px;
                padding: 2px 10px;
            }
        """)

        self.lbl_license = None

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #94a3b8;
                border: 1px solid #2b1e4a;
                border-radius: 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #ef4444; color: white; border-color: #ef4444; }
        """)
        btn_close.clicked.connect(self._cleanup_and_close)

        h_head.addWidget(lbl_icon)
        h_head.addWidget(self.lbl_title)
        h_head.addStretch()
        h_head.addWidget(self.lbl_srbrowser_status)
        h_head.addSpacing(6)
        h_head.addWidget(btn_close)
        card_layout.addLayout(h_head)

        # -------------------------------------------------------------
        # 2. UNIFIED CONTROLS & CONFIGURATION BOX (3 Clean Balanced Rows)
        # -------------------------------------------------------------
        self.target_box = QFrame()
        self.target_box.setFixedHeight(106)
        self.target_box.setStyleSheet("background: #131428; border-radius: 8px; border: 1px solid #232545;")
        v_target = QVBoxLayout(self.target_box)
        v_target.setContentsMargins(8, 5, 8, 5)
        v_target.setSpacing(6)

        # === ROW 1: Target Profiles Selector & Live Target Badge ===
        h_tgt_row = QHBoxLayout()
        h_tgt_row.setSpacing(6)

        # Segmented buttons for Group vs Numbers
        self.btn_seg_group = QPushButton("📁 Group")
        self.btn_seg_group.setCheckable(True)
        self.btn_seg_group.setChecked(True)
        self.btn_seg_group.setFixedHeight(26)
        self.btn_seg_group.setFixedWidth(74)
        self.btn_seg_group.setCursor(Qt.PointingHandCursor)

        self.btn_seg_numbers = QPushButton("🔢 Numbers")
        self.btn_seg_numbers.setCheckable(True)
        self.btn_seg_numbers.setFixedHeight(26)
        self.btn_seg_numbers.setFixedWidth(82)
        self.btn_seg_numbers.setCursor(Qt.PointingHandCursor)

        self.btn_group_target = QButtonGroup(self)
        self.btn_group_target.addButton(self.btn_seg_group)
        self.btn_group_target.addButton(self.btn_seg_numbers)
        self.btn_group_target.setExclusive(True)

        self._style_segmented_buttons(self.btn_seg_group, self.btn_seg_numbers)
        self.btn_seg_group.toggled.connect(self._on_target_mode_changed)
        self.btn_seg_numbers.toggled.connect(self._on_target_mode_changed)

        h_tgt_row.addWidget(self.btn_seg_group)
        h_tgt_row.addWidget(self.btn_seg_numbers)

        # Group Dropdown
        self.combo_groups = QComboBox()
        self.combo_groups.setFixedHeight(26)
        self.combo_groups.setStyleSheet("""
            QComboBox {
                background: #0c0e24;
                color: #38bdf8;
                border: 1px solid #281d4a;
                border-radius: 4px;
                padding: 1px 8px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QComboBox:focus { border-color: #7c3aed; }
            QComboBox QAbstractItemView {
                background-color: #0e0e1c;
                color: #ffffff;
                selection-background-color: #7c3aed;
            }
        """)
        self.combo_groups.currentIndexChanged.connect(self._update_db_counter)
        h_tgt_row.addWidget(self.combo_groups, stretch=1)

        # Profile Numbers Input
        self.txt_profile_numbers = QLineEdit()
        self.txt_profile_numbers.setFixedHeight(26)
        self.txt_profile_numbers.setPlaceholderText("e.g. 1-10 or 226, 227, 230")
        self.txt_profile_numbers.setStyleSheet("""
            QLineEdit {
                background: #0c0e24;
                color: #38bdf8;
                border: 1px solid #281d4a;
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QLineEdit:focus { border-color: #7c3aed; }
        """)
        self.txt_profile_numbers.textChanged.connect(self._update_db_counter)
        self.txt_profile_numbers.setVisible(False)
        h_tgt_row.addWidget(self.txt_profile_numbers, stretch=1)

        # Refresh Sync Button
        self.btn_refresh_groups = QPushButton("🔄")
        self.btn_refresh_groups.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_groups.setFixedSize(26, 26)
        self.btn_refresh_groups.setToolTip("🔄 Reload Profiles & Groups from srkBrowser")
        self.btn_refresh_groups.setStyleSheet("""
            QPushButton {
                background: #0c1526;
                color: #38bdf8;
                border: 1px solid #0284c788;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #10243d;
                color: #67e8f9;
                border: 1px solid #38bdf8;
            }
        """)
        self.btn_refresh_groups.clicked.connect(self._on_refresh_sync)
        h_tgt_row.addWidget(self.btn_refresh_groups)

        # Target Count Badge (Neon Purple Glow)
        self.lbl_target_count_badge = QLabel("🎯 0 Profiles")
        self.lbl_target_count_badge.setFixedHeight(26)
        self.lbl_target_count_badge.setStyleSheet("""
            background: #1a0f2e; color: #c084fc;
            border: 1px solid #7c3aed; border-radius: 5px;
            padding: 2px 10px; font-weight: 800; font-size: 11px;
        """)
        h_tgt_row.addWidget(self.lbl_target_count_badge)
        v_target.addLayout(h_tgt_row)

        # === ROW 2: Threads, Delay, Fail Move & Automation Toggles ===
        h_param_row = QHBoxLayout()
        h_param_row.setSpacing(6)

        lbl_th = QLabel("Threads:")
        lbl_th.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 20)
        self.spin_threads.setValue(2)
        self._style_spinbox(self.spin_threads, width=42)

        lbl_st = QLabel("Delay:")
        lbl_st.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.5, 60.0)
        self.spin_delay.setDecimals(1)
        self.spin_delay.setSingleStep(0.5)
        self.spin_delay.setValue(2.0)
        self.spin_delay.setSuffix("s")
        self.spin_delay.setToolTip("Pacing delay between actions (seconds)")
        self._style_spinbox(self.spin_delay, width=52)

        # Vertical Separator
        sep_p = QFrame()
        sep_p.setFrameShape(QFrame.VLine)
        sep_p.setStyleSheet("color: #232545;")

        lbl_fail = QLabel("Fail:")
        lbl_fail.setStyleSheet("color: #f87171; font-weight: 700; font-size: 11px;")
        self.combo_fail_group = QComboBox()
        self.combo_fail_group.setFixedHeight(26)
        self.combo_fail_group.view().setMinimumWidth(180)
        self.combo_fail_group.setStyleSheet("""
            QComboBox {
                background: #0c0e24;
                color: #fca5a5;
                border: 1px solid #7f1d1d;
                border-radius: 4px;
                padding: 1px 16px 1px 5px;
                font-size: 10.5px;
                font-weight: 700;
                min-width: 48px;
                max-width: 68px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left: 1px solid #7f1d1d55;
            }
            QComboBox:focus { border-color: #ef4444; }
            QComboBox QAbstractItemView {
                background-color: #0b0918;
                color: #f1f5f9;
                border: 1px solid #ef444488;
                border-radius: 6px;
                padding: 4px;
                min-width: 180px;
                selection-background-color: #dc2626;
                selection-color: #ffffff;
            }
        """)
        self.combo_fail_group.currentIndexChanged.connect(self._on_fail_group_changed)

        self.chk_auto_switch = QCheckBox("Page Switch")
        self.chk_auto_switch.setCursor(Qt.PointingHandCursor)
        self.chk_auto_switch.setChecked(True)
        self.chk_auto_switch.setToolTip("Automatically switch profile context to newly created Page")
        self.chk_auto_switch.setStyleSheet("""
            QCheckBox {
                color: #38bdf8;
                font-size: 11px;
                font-weight: 700;
                spacing: 5px;
            }
            QCheckBox:hover { color: #67e8f9; }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border: 1px solid #0284c7;
                border-radius: 3px;
                background-color: #06060e;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
            }
        """)

        self.chk_headless = QCheckBox("Headless")
        self.chk_headless.setCursor(Qt.PointingHandCursor)
        self.chk_headless.setStyleSheet("""
            QCheckBox {
                color: #94a3b8;
                font-size: 11px;
                font-weight: 700;
                spacing: 5px;
            }
            QCheckBox:hover { color: #f1f5f9; }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border: 1px solid #334155;
                border-radius: 3px;
                background-color: #06060e;
            }
            QCheckBox::indicator:checked {
                background-color: #38bdf8;
                border: 1px solid #38bdf8;
            }
        """)

        h_param_row.addWidget(lbl_th)
        h_param_row.addWidget(self.spin_threads)
        h_param_row.addSpacing(4)
        h_param_row.addWidget(lbl_st)
        h_param_row.addWidget(self.spin_delay)
        h_param_row.addSpacing(4)
        h_param_row.addWidget(sep_p)
        h_param_row.addSpacing(2)
        h_param_row.addWidget(lbl_fail)
        h_param_row.addWidget(self.combo_fail_group)
        h_param_row.addStretch()
        h_param_row.addWidget(self.chk_auto_switch)
        h_param_row.addSpacing(6)
        h_param_row.addWidget(self.chk_headless)
        h_param_row.addSpacing(6)

        self.btn_proxy = QPushButton("🛡️ Proxy: OFF")
        self.btn_proxy.setCursor(Qt.PointingHandCursor)
        self.btn_proxy.setFixedHeight(26)
        self.btn_proxy.setToolTip("Configure Residential Proxy (DataImpulse / Custom)")
        self.btn_proxy.setStyleSheet("""
            QPushButton {
                background: #0e0e1c;
                color: #94a3b8;
                border: 1px solid #232545;
                border-radius: 4px;
                padding: 1px 8px;
                font-weight: 700;
                font-size: 10.5px;
            }
            QPushButton:hover {
                background: #1c142e;
                color: #f472b6;
                border-color: #db277788;
            }
        """)
        self.btn_proxy.clicked.connect(self._on_open_proxy_modal)
        h_param_row.addWidget(self.btn_proxy)

        v_target.addLayout(h_param_row)

        # === ROW 3: Method Selector, Mode (Random/Custom) & Dynamic Mode Controls ===
        h_mode_row = QHBoxLayout()
        h_mode_row.setSpacing(5)

        lbl_method = QLabel("Method:")
        lbl_method.setStyleSheet("color: #f43f5e; font-weight: 800; font-size: 11px;")
        h_mode_row.addWidget(lbl_method)

        self.combo_method = QComboBox()
        self.combo_method.setFixedHeight(26)
        self.combo_method.setStyleSheet("""
            QComboBox {
                background: #0e0e1c;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 1px 14px 1px 6px;
                font-size: 10.5px;
                font-weight: 800;
                min-width: 120px;
            }
            QComboBox:focus { border-color: #38bdf8; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 14px;
                border-left: none;
            }
            QComboBox QAbstractItemView {
                background-color: #070712;
                color: #ffffff;
                selection-background-color: #0284c7;
            }
        """)
        self.combo_method.addItem("⚡ Method 1 (API)")
        self.combo_method.addItem("✨ Method 2 (API)")
        self.combo_method.setToolTip(
            "⚡ Method 1 (API): High-speed direct GraphQL mutation API (Supports Random & Custom).\n"
            "✨ Method 2 (API): Automated Browser Engine with human pacing (Auto Random Identity)."
        )
        self.combo_method.currentIndexChanged.connect(self._on_method_changed)
        h_mode_row.addWidget(self.combo_method)
        h_mode_row.addSpacing(4)

        sep_m = QFrame()
        sep_m.setFrameShape(QFrame.VLine)
        sep_m.setStyleSheet("color: #232545;")
        h_mode_row.addWidget(sep_m)
        h_mode_row.addSpacing(2)

        lbl_mode = QLabel("Mode:")
        lbl_mode.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 11px;")
        h_mode_row.addWidget(lbl_mode)

        self.combo_mode = QComboBox()
        self.combo_mode.setFixedHeight(26)
        self.combo_mode.setStyleSheet("""
            QComboBox {
                background: #0e0e1c;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 1px 16px 1px 8px;
                font-size: 10.5px;
                font-weight: 800;
                min-width: 90px;
            }
            QComboBox:focus { border-color: #38bdf8; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 14px;
                border-left: none;
            }
            QComboBox QAbstractItemView {
                background-color: #070712;
                color: #ffffff;
                selection-background-color: #0284c7;
            }
            QComboBox:disabled {
                background: #090914;
                color: #64748b;
                border-color: #334155;
            }
        """)
        self.combo_mode.addItem("🎲 Random")
        self.combo_mode.addItem("✏️ Custom")
        self.combo_mode.setToolTip(
            "Creation Mode:\n"
            "🎲 Random: Automatically generate profile identities.\n"
            "✏️ Custom: Paste custom page names and choose category."
        )
        self.combo_mode.currentIndexChanged.connect(self._on_creation_mode_changed)
        h_mode_row.addWidget(self.combo_mode)
        h_mode_row.addSpacing(4)

        # Dynamic Status Badge for Random Mode
        self.lbl_random_info = QLabel("✨ Auto Names & Categories")
        self.lbl_random_info.setFixedHeight(26)
        self.lbl_random_info.setStyleSheet("""
            color: #38bdf8;
            font-size: 10.5px;
            font-weight: 600;
            background: #061526;
            border: 1px solid #0284c755;
            border-radius: 4px;
            padding: 2px 8px;
        """)
        h_mode_row.addWidget(self.lbl_random_info)

        # Custom Page Names: Paste Button
        self.btn_paste = QPushButton("📝 Paste Names")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.setFixedHeight(26)
        self.btn_paste.setStyleSheet("""
            QPushButton {
                background: #201026;
                color: #c084fc;
                border: 1px solid #7c3aed;
                border-radius: 4px;
                padding: 1px 8px;
                font-weight: 700;
                font-size: 10.5px;
            }
            QPushButton:hover { background: #32163d; color: #ffffff; }
        """)
        self.btn_paste.setToolTip("Click to paste custom page names (1 per line)")
        self.btn_paste.clicked.connect(self._on_paste_page_names_text)
        h_mode_row.addWidget(self.btn_paste)

        # Vertical Separator for Custom mode
        self.sep_custom = QFrame()
        self.sep_custom.setFrameShape(QFrame.VLine)
        sep_custom_style = "color: #232545;"
        self.sep_custom.setStyleSheet(sep_custom_style)
        h_mode_row.addWidget(self.sep_custom)

        # Category Label & Dropdown
        self.lbl_cat = QLabel("Category:")
        self.lbl_cat.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 11px;")
        h_mode_row.addWidget(self.lbl_cat)

        self.combo_category = QComboBox()
        self.combo_category.setFixedHeight(26)
        self.combo_category.setStyleSheet("""
            QComboBox {
                background: #0c0e24;
                color: #e2e8f0;
                border: 1px solid #281d4a;
                border-radius: 4px;
                padding: 1px 14px 1px 5px;
                font-size: 10.5px;
                font-weight: 700;
                min-width: 95px;
                max-width: 110px;
            }
            QComboBox:focus { border-color: #7c3aed; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 14px;
                border-left: none;
            }
            QComboBox QAbstractItemView {
                background-color: #0e0e1c;
                color: #ffffff;
                selection-background-color: #7c3aed;
            }
        """)
        CATEGORIES = [
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
        for c_name, c_id in CATEGORIES:
            self.combo_category.addItem(c_name, c_id)
        h_mode_row.addWidget(self.combo_category)

        h_mode_row.addStretch()

        # Dummy hidden widgets for compatibility
        self.btn_upload = QPushButton()
        self.btn_upload.setVisible(False)
        self.lbl_file_status = QLabel("")
        self.lbl_file_status.setVisible(False)

        v_target.addLayout(h_mode_row)
        card_layout.addWidget(self.target_box)

        # -------------------------------------------------------------
        # 3. METRICS DECK (3 Glowing Metric Cards matching Studio)
        # -------------------------------------------------------------
        h_metrics = QHBoxLayout()
        h_metrics.setSpacing(8)

        # Card 1: SUCCESSFUL
        self.card_succ = QFrame()
        self.card_succ.setFixedHeight(62)
        self.card_succ.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #061a11, stop:1 #030d08);
                border: 1.5px solid #059669;
                border-radius: 8px;
            }
        """)
        v_cs = QVBoxLayout(self.card_succ)
        v_cs.setContentsMargins(8, 4, 8, 4)
        v_cs.setSpacing(0)

        h_cs_head = QHBoxLayout()
        lbl_succ_dot = QLabel("🟢")
        lbl_succ_dot.setStyleSheet("font-size: 10px; border: none; background: transparent;")
        lbl_succ_title = QLabel("SUCCESSFUL")
        lbl_succ_title.setStyleSheet("color: #34d399; font-weight: 800; font-size: 11px; border: none; background: transparent;")
        h_cs_head.addWidget(lbl_succ_dot)
        h_cs_head.addWidget(lbl_succ_title)
        h_cs_head.addStretch()
        v_cs.addLayout(h_cs_head)

        self.lbl_val_success = QLabel("0")
        self.lbl_val_success.setStyleSheet("color: #10b981; font-weight: 900; font-size: 20px; border: none; background: transparent;")
        v_cs.addWidget(self.lbl_val_success)

        self.lbl_succ_sub = QLabel("Pages Created Successfully")
        self.lbl_succ_sub.setStyleSheet("color: #059669; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cs.addWidget(self.lbl_succ_sub)
        h_metrics.addWidget(self.card_succ, stretch=1)

        # Card 2: FAILED
        self.card_fail = QFrame()
        self.card_fail.setFixedHeight(62)
        self.card_fail.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #220b0e, stop:1 #110507);
                border: 1.5px solid #dc2626;
                border-radius: 8px;
            }
        """)
        v_cf = QVBoxLayout(self.card_fail)
        v_cf.setContentsMargins(8, 4, 8, 4)
        v_cf.setSpacing(0)

        h_cf_head = QHBoxLayout()
        lbl_fail_dot = QLabel("🔴")
        lbl_fail_dot.setStyleSheet("font-size: 10px; border: none; background: transparent;")
        lbl_fail_title = QLabel("FAILED")
        lbl_fail_title.setStyleSheet("color: #f87171; font-weight: 800; font-size: 11px; border: none; background: transparent;")
        h_cf_head.addWidget(lbl_fail_dot)
        h_cf_head.addWidget(lbl_fail_title)
        h_cf_head.addStretch()
        v_cf.addLayout(h_cf_head)

        self.lbl_val_failed = QLabel("0")
        self.lbl_val_failed.setStyleSheet("color: #ef4444; font-weight: 900; font-size: 20px; border: none; background: transparent;")
        v_cf.addWidget(self.lbl_val_failed)

        self.lbl_fail_sub = QLabel("Failed Accounts / Errors")
        self.lbl_fail_sub.setStyleSheet("color: #b91c1c; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cf.addWidget(self.lbl_fail_sub)
        h_metrics.addWidget(self.card_fail, stretch=1)

        # Card 3: REMAINING
        self.card_rem = QFrame()
        self.card_rem.setFixedHeight(62)
        self.card_rem.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #081729, stop:1 #040c16);
                border: 1.5px solid #0284c7;
                border-radius: 8px;
            }
        """)
        v_cr = QVBoxLayout(self.card_rem)
        v_cr.setContentsMargins(8, 4, 8, 4)
        v_cr.setSpacing(0)

        h_cr_head = QHBoxLayout()
        lbl_rem_dot = QLabel("⏳")
        lbl_rem_dot.setStyleSheet("font-size: 10px; border: none; background: transparent;")
        lbl_rem_title = QLabel("REMAINING")
        lbl_rem_title.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 11px; border: none; background: transparent;")
        h_cr_head.addWidget(lbl_rem_dot)
        h_cr_head.addWidget(lbl_rem_title)
        h_cr_head.addStretch()
        v_cr.addLayout(h_cr_head)

        self.lbl_val_remaining = QLabel("0")
        self.lbl_val_remaining.setStyleSheet("color: #0ea5e9; font-weight: 900; font-size: 20px; border: none; background: transparent;")
        v_cr.addWidget(self.lbl_val_remaining)

        self.lbl_rem_sub = QLabel("Queued Accounts In Target")
        self.lbl_rem_sub.setStyleSheet("color: #0284c7; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cr.addWidget(self.lbl_rem_sub)
        h_metrics.addWidget(self.card_rem, stretch=1)

        card_layout.addLayout(h_metrics)

        # -------------------------------------------------------------
        # 4. GLOWING PROGRESS BAR (Centered Clean Gradient)
        # -------------------------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Progress: 0/0 (0%)")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #090a16;
                border: 1px solid #1e2238;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
                font-size: 10.5px;
                font-weight: 800;
                font-family: 'Segoe UI', sans-serif;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #38bdf8);
                border-radius: 4px;
                margin: 1px;
            }
        """)
        card_layout.addWidget(self.progress_bar)

        # -------------------------------------------------------------
        # 5. BEAUTIFUL LIVE LOGS TERMINAL (Monospace on Dark Carbon)
        # -------------------------------------------------------------
        self.log_box = QFrame()
        self.log_box.setFixedHeight(160)
        self.log_box.setStyleSheet("background: #070812; border: 1px solid #1e2238; border-radius: 6px;")
        v_log = QVBoxLayout(self.log_box)
        v_log.setContentsMargins(8, 6, 8, 6)
        v_log.setSpacing(0)

        self.txt_terminal = QTextEdit()
        self.txt_logs = self.txt_terminal
        self.txt_terminal.setReadOnly(True)
        self.txt_terminal.document().setDocumentMargin(2)
        self.txt_terminal.setStyleSheet("""
            QTextEdit {
                background: transparent;
                color: #38bdf8;
                border: none;
                font-family: 'Consolas', 'JetBrains Mono', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.25;
                padding: 0px;
                margin: 0px;
            }
            QScrollBar:vertical {
                background: #070812; width: 5px; border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #27273a; border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #8b5cf6;
            }
        """)
        self.txt_terminal.setPlaceholderText("📟 Automation console ready. Logs will appear here in real-time...")
        v_log.addWidget(self.txt_terminal)
        card_layout.addWidget(self.log_box)

        self._append_log("💻 [SYSTEM ACTIVE] // FB BULK PAGE CREATOR STUDIO READY • WAITING FOR AUTOMATION...")

        # -------------------------------------------------------------
        # 6. ACTION CONTROLS (At the very bottom matching Studio)
        # -------------------------------------------------------------
        h_act = QHBoxLayout()
        h_act.setSpacing(8)

        self.btn_run = QPushButton("▶️ Start Bot")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setFixedHeight(30)
        self.btn_run.setFixedWidth(115)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                font-weight: 800;
                font-size: 11.5px;
                border: 1px solid #a78bfa;
                border-radius: 5px;
                padding: 2px 10px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed); }
            QPushButton:disabled { background: #1e2238; color: #64748b; border: 1px solid #232545; }
        """)
        self.btn_run.clicked.connect(self._start_automation)

        self.btn_reports = QPushButton("📁 Reports")
        self.btn_reports.setCursor(Qt.PointingHandCursor)
        self.btn_reports.setFixedHeight(30)
        self.btn_reports.setToolTip("Open folder containing CSV Reports & Screenshots")
        self.btn_reports.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #fbbf24;
                border: 1px solid #2b1e4a;
                border-radius: 5px;
                padding: 2px 12px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background: #261b45; color: #fde68a; border-color: #38bdf8; }
        """)
        self.btn_reports.clicked.connect(self._open_reports_dir)

        self.btn_stop = QPushButton("🛑 Stop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setFixedHeight(30)
        self.btn_stop.setFixedWidth(75)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #f87171;
                border: 1px solid #ef444455;
                border-radius: 5px;
                padding: 2px 10px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background: #ef4444; color: #ffffff; border-color: #ef4444; }
            QPushButton:disabled { background: #131428; color: #475569; border: 1px solid #1e2238; }
        """)
        self.btn_stop.clicked.connect(self._stop_automation)

        h_act.addWidget(self.btn_run)
        h_act.addStretch(1)
        h_act.addWidget(self.btn_reports)
        h_act.addWidget(self.btn_stop)
        card_layout.addLayout(h_act)


    # -------------------------------------------------------------
    # Styling Helpers
    # -------------------------------------------------------------
    def _style_segmented_buttons(self, btn_grp: QPushButton, btn_nums: QPushButton) -> None:
        style_active = """
            QPushButton {
                background: #3b0817;
                color: #ff6b8b;
                border: 1.5px solid #ff2a5f;
                border-radius: 4px;
                font-weight: 800;
                font-size: 11px;
                padding: 2px 6px;
            }
        """
        style_inactive = """
            QPushButton {
                background: #100f1c;
                color: #94a3b8;
                border: 1px solid #242238;
                border-radius: 4px;
                font-weight: 700;
                font-size: 11px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: #1a172c;
                color: #e2e8f0;
            }
        """
        if btn_grp.isChecked():
            btn_grp.setStyleSheet(style_active)
            btn_nums.setStyleSheet(style_inactive)
        else:
            btn_grp.setStyleSheet(style_inactive)
            btn_nums.setStyleSheet(style_active)

    def _style_spinbox(self, spin, width: int = 46) -> None:
        spin.setFixedHeight(26)
        spin.setFixedWidth(width)
        spin.setAlignment(Qt.AlignCenter)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spin.setStyleSheet("""
            QSpinBox, QDoubleSpinBox {
                background: #06060e;
                color: #ff3366;
                border: 1px solid #4a152d;
                border-radius: 4px;
                font-weight: 800;
                font-size: 11.5px;
                padding: 1px 2px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #00f2fe;
                background: #0c0b18;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 0px;
                height: 0px;
                border: none;
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow,
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
                width: 0px;
                height: 0px;
                border: none;
                image: none;
            }
        """)

    # -------------------------------------------------------------
    # Drag and Move Window Handlers
    # -------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = QPoint()

    # -------------------------------------------------------------
    # Heartbeat Check
    # -------------------------------------------------------------
    def _check_srbrowser_heartbeat(self) -> None:
        try:
            is_ok = check_srbrowser_heartbeat()
            if is_ok:
                self.lbl_srbrowser_status.setText("🟢 srkBrowser Active")
                self.lbl_srbrowser_status.setStyleSheet("""
                    background-color: #061f14; color: #34d399;
                    font-size: 11px; font-weight: 800;
                    border: 1px solid #05966988; border-radius: 5px;
                    padding: 2px 10px;
                """)
            else:
                self.lbl_srbrowser_status.setText("🟡 srkBrowser Offline")
                self.lbl_srbrowser_status.setStyleSheet("""
                    background-color: #291804; color: #f59e0b;
                    font-size: 11px; font-weight: 800;
                    border: 1px solid #b4530988; border-radius: 5px;
                    padding: 2px 10px;
                """)
        except Exception:
            pass

    # -------------------------------------------------------------
    # Target Mode Switching & Population
    # -------------------------------------------------------------
    def _on_target_mode_changed(self) -> None:
        self._style_segmented_buttons(self.btn_seg_group, self.btn_seg_numbers)
        if self.btn_seg_numbers.isChecked():
            self.combo_groups.hide()
            self.btn_refresh_groups.hide()
            self.txt_profile_numbers.show()
        else:
            self.txt_profile_numbers.hide()
            self.combo_groups.show()
            self.btn_refresh_groups.show()
        self._update_db_counter()
        self._on_creation_mode_changed()

    def _populate_groups(self) -> None:
        prev_fail_sel = self.combo_fail_group.currentData() if hasattr(self, "combo_fail_group") else None

        self.combo_groups.clear()
        self.combo_groups.addItem("🌐 All Profiles", "ALL")

        if hasattr(self, "combo_fail_group"):
            self.combo_fail_group.blockSignals(True)
            self.combo_fail_group.clear()
            self.combo_fail_group.addItem("🚫 None", "NONE")
            self.combo_fail_group.addItem("➕ Create New...", "__CREATE_NEW__")

        if self.profile_mgr and hasattr(self.profile_mgr, "get_groups"):
            try:
                groups = self.profile_mgr.get_groups()
                for g in groups:
                    if g and g.strip():
                        self.combo_groups.addItem(f"📁 {g}", g)
                        if hasattr(self, "combo_fail_group"):
                            self.combo_fail_group.addItem(f"📁 {g}", g)
            except Exception:
                pass

        if hasattr(self, "combo_fail_group"):
            if prev_fail_sel and prev_fail_sel not in ("NONE", "__CREATE_NEW__"):
                idx = self.combo_fail_group.findData(prev_fail_sel)
                if idx >= 0:
                    self.combo_fail_group.setCurrentIndex(idx)
                else:
                    self.combo_fail_group.setCurrentIndex(0)
            else:
                self.combo_fail_group.setCurrentIndex(0)
            self.combo_fail_group.blockSignals(False)

    def _on_fail_group_changed(self) -> None:
        if hasattr(self, "combo_fail_group"):
            curr_txt = self.combo_fail_group.currentText()
            self.combo_fail_group.setToolTip(f"Failed Profiles Target Group: {curr_txt}")
            if self.combo_fail_group.currentData() == "__CREATE_NEW__":
                self._on_prompt_create_fail_group()

    def _on_prompt_create_fail_group(self) -> None:
        modal = CreateNewGroupModal(parent=self)
        if modal.exec() == QDialog.Accepted:
            new_g = modal.get_group_name().strip()
            if new_g:
                created = False
                if self.profile_mgr and hasattr(self.profile_mgr, "add_group"):
                    try:
                        created = self.profile_mgr.add_group(new_g)
                    except Exception:
                        pass
                if not created:
                    try:
                        from core.profile_manager import ProfileManager
                        pm = ProfileManager()
                        created = pm.add_group(new_g)
                    except Exception:
                        pass

                self._populate_groups()

                idx = self.combo_fail_group.findData(new_g)
                if idx >= 0:
                    self.combo_fail_group.setCurrentIndex(idx)

                self._append_log(f"📁 [GROUP CREATED] New group '{new_g}' created and selected for failed profiles!")
        else:
            if hasattr(self, "combo_fail_group") and self.combo_fail_group.currentData() == "__CREATE_NEW__":
                self.combo_fail_group.setCurrentIndex(0)

    def _get_target_profiles(self) -> List[Dict[str, Any]]:
        if not self.profile_mgr:
            return []
        all_profs = []
        if hasattr(self.profile_mgr, "get_all_profiles"):
            all_profs = self.profile_mgr.get_all_profiles()
        elif hasattr(self.profile_mgr, "profiles"):
            all_profs = self.profile_mgr.profiles or []

        if self.btn_seg_numbers.isChecked():
            raw_val = self.txt_profile_numbers.text().strip()
            if not raw_val or raw_val.lower() == "all":
                return all_profs
            
            target_nums: Set[str] = set()
            parts = raw_val.replace(" ", "").split(",")
            for p in parts:
                if "-" in p:
                    sub = p.split("-")
                    if len(sub) == 2 and sub[0].isdigit() and sub[1].isdigit():
                        s, e = int(sub[0]), int(sub[1])
                        for n in range(min(s, e), max(s, e) + 1):
                            target_nums.add(str(n))
                elif p.isdigit():
                    target_nums.add(str(int(p)))
                elif p.strip():
                    m_p = re.search(r'(\d+)', p)
                    if m_p:
                        target_nums.add(str(int(m_p.group(1))))
                    else:
                        target_nums.add(p.strip().lower())

            matched = []
            for prof in all_profs:
                p_num = str(prof.get("number", "")).strip()
                p_name = str(prof.get("name", "")).strip().lower()
                p_id = str(prof.get("id", "")).strip().lower()

                m_num = re.search(r'(\d+)', p_num)
                digit_num = str(int(m_num.group(1))) if m_num else ""
                
                m_name = re.match(r'^profile\s*0*(\d+)$', p_name, re.IGNORECASE)
                digit_name = str(int(m_name.group(1))) if m_name else ""

                if (digit_num and digit_num in target_nums) or \
                   (digit_name and digit_name in target_nums) or \
                   (p_name in target_nums) or \
                   (p_id in target_nums):
                    matched.append(prof)
            return matched

        else:
            sel_data = self.combo_groups.currentData()
            if not sel_data or sel_data == "ALL":
                return all_profs
            return [p for p in all_profs if p.get("group") == sel_data]

    def _update_db_counter(self) -> None:
        target_profs = self._get_target_profiles()
        c = len(target_profs)
        self.lbl_val_remaining.setText(str(c))
        self.lbl_target_count_badge.setText(f"🎯 {c} Profile{'s' if c != 1 else ''}")

    def _on_refresh_sync(self) -> None:
        if self.profile_mgr and hasattr(self.profile_mgr, "load_profiles"):
            try:
                self.profile_mgr.load_profiles()
            except Exception:
                pass
        self._populate_groups()
        self._update_db_counter()
        self._on_creation_mode_changed()
        self._append_log("🔄 [SYNC] Database profiles & groups reloaded successfully!")

    # -------------------------------------------------------------
    # Page Names Actions
    # -------------------------------------------------------------
    def _on_upload_page_names_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Page Names File",
            "",
            "Supported Files (*.xlsx *.csv *.txt);;Excel Files (*.xlsx);;CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return

        names = parse_page_names_file_or_text(file_path=file_path)
        if names:
            self.loaded_page_names = names
            fname = Path(file_path).name
            if len(fname) > 16:
                fname = fname[:13] + "..."
            self.lbl_file_status.setText(fname)
            self._update_page_names_badge()
            self._append_log(f"📂 [LOADED] {len(names)} page name(s) from '{Path(file_path).name}'")
        else:
            QMessageBox.warning(
                self,
                "No Names Found",
                f"Could not extract valid page names from:\n{Path(file_path).name}"
            )

    def _on_paste_page_names_text(self) -> None:
        modal = PastePageNamesModal(self)
        if self.loaded_page_names:
            modal.txt_content.setPlainText("\n".join(self.loaded_page_names))
            modal._update_counter()
        if modal.exec() == QDialog.Accepted:
            raw_text = modal.get_text()
            if raw_text:
                names = parse_page_names_file_or_text(text_content=raw_text)
                if names:
                    self.loaded_page_names = names
                    self.lbl_file_status.setText("Pasted Text")
                    self._update_page_names_badge()
                    self._append_log(f"📝 [PASTED] {len(names)} page name(s) successfully loaded from text.")
                else:
                    self.loaded_page_names = []
                    self.lbl_file_status.setText("No file loaded")
                    self._update_page_names_badge()
                    self._append_log("🗑️ Loaded page names cleared.")
            else:
                self.loaded_page_names = []
                self.lbl_file_status.setText("No file loaded")
                self._update_page_names_badge()
                self._append_log("🗑️ Loaded page names cleared.")

    def _on_clear_page_names(self) -> None:
        self.loaded_page_names = []
        self.lbl_file_status.setText("No file loaded")
        self._update_page_names_badge()
        self._append_log("🗑️ Loaded page names cleared (Defaulting to dynamic auto-branding).")

    def _on_method_changed(self) -> None:
        """Handles switching between Method 1 (API) and Method 2 (API)."""
        is_method_2 = (hasattr(self, "combo_method") and self.combo_method.currentIndex() == 1)

        # Allow both Method 1 and Method 2 to use Mode (Random or Custom)
        if hasattr(self, "combo_mode"):
            self.combo_mode.setEnabled(True)

        self._on_creation_mode_changed()

        if is_method_2:
            is_custom = (hasattr(self, "combo_mode") and self.combo_mode.currentIndex() == 1)
            if is_custom:
                self._append_log("✨ [METHOD SELECTED] Method 2 (API) - Automated Core Engine (Custom Name Mode active).")
            else:
                self._append_log("✨ [METHOD SELECTED] Method 2 (API) - Automated Core Engine (Random Identity Mode active).")
        else:
            self._append_log("⚡ [METHOD SELECTED] Method 1 (API) - Direct GraphQL Mutation (Random & Custom modes available).")

    def _on_creation_mode_changed(self) -> None:
        is_method_2 = (hasattr(self, "combo_method") and self.combo_method.currentIndex() == 1)
        is_custom = (hasattr(self, "combo_mode") and self.combo_mode.currentIndex() == 1)

        if is_custom:
            if hasattr(self, "combo_mode"):
                self.combo_mode.setStyleSheet("""
                    QComboBox {
                        background: #180d1e;
                        color: #f43f5e;
                        border: 1px solid #f43f5e;
                        border-radius: 4px;
                        padding: 1px 16px 1px 8px;
                        font-size: 10.5px;
                        font-weight: 800;
                        min-width: 90px;
                    }
                    QComboBox:focus { border-color: #fb7185; }
                    QComboBox::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 14px;
                        border-left: none;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #120716;
                        color: #ffffff;
                        selection-background-color: #f43f5e;
                    }
                """)
            # Show Custom Name options
            if hasattr(self, "btn_paste"):
                self.btn_paste.show()
            if hasattr(self, "sep_custom"):
                self.sep_custom.show()

            if is_method_2:
                # In Method 2, Category is automated by the script, so keep category picker hidden
                if hasattr(self, "lbl_cat"):
                    self.lbl_cat.hide()
                if hasattr(self, "combo_category"):
                    self.combo_category.hide()
                # Show Random Category Active badge
                if hasattr(self, "lbl_random_info"):
                    self.lbl_random_info.setText("✨ Random Category Active")
                    self.lbl_random_info.setStyleSheet("""
                        color: #a855f7;
                        font-size: 10.5px;
                        font-weight: 700;
                        background: #190b28;
                        border: 1px solid #a855f766;
                        border-radius: 4px;
                        padding: 2px 8px;
                    """)
                    self.lbl_random_info.show()
            else:
                # Method 1 allows choosing category
                if hasattr(self, "lbl_random_info"):
                    self.lbl_random_info.hide()
                if hasattr(self, "lbl_cat"):
                    self.lbl_cat.show()
                if hasattr(self, "combo_category"):
                    self.combo_category.show()
        else:
            if hasattr(self, "combo_mode"):
                self.combo_mode.setStyleSheet("""
                    QComboBox {
                        background: #0e0e1c;
                        color: #38bdf8;
                        border: 1px solid #0284c7;
                        border-radius: 4px;
                        padding: 1px 16px 1px 8px;
                        font-size: 10.5px;
                        font-weight: 800;
                        min-width: 90px;
                    }
                    QComboBox:focus { border-color: #38bdf8; }
                    QComboBox::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 14px;
                        border-left: none;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #070712;
                        color: #ffffff;
                        selection-background-color: #0284c7;
                    }
                    QComboBox:disabled {
                        background: #090914;
                        color: #64748b;
                        border-color: #334155;
                    }
                """)
            # Hide Custom options
            if hasattr(self, "btn_paste"):
                self.btn_paste.hide()
            if hasattr(self, "sep_custom"):
                self.sep_custom.hide()
            if hasattr(self, "lbl_cat"):
                self.lbl_cat.hide()
            if hasattr(self, "combo_category"):
                self.combo_category.hide()

            # Show Random info badge
            if hasattr(self, "lbl_random_info"):
                if is_method_2:
                    self.lbl_random_info.setText("✨ Random Name & Category Active")
                    self.lbl_random_info.setStyleSheet("""
                        color: #a855f7;
                        font-size: 10.5px;
                        font-weight: 700;
                        background: #190b28;
                        border: 1px solid #a855f766;
                        border-radius: 4px;
                        padding: 2px 8px;
                    """)
                else:
                    self.lbl_random_info.setText("✨ Auto Names & Categories")
                    self.lbl_random_info.setStyleSheet("""
                        color: #38bdf8;
                        font-size: 10.5px;
                        font-weight: 600;
                        background: #061526;
                        border: 1px solid #0284c755;
                        border-radius: 4px;
                        padding: 2px 8px;
                    """)
                self.lbl_random_info.show()

        self._update_page_names_badge()

    def _update_page_names_badge(self) -> None:
        if hasattr(self, "btn_paste"):
            count = len(self.loaded_page_names)
            if count > 0:
                self.btn_paste.setText(f"📝 {count} Names")
                self.btn_paste.setToolTip(f"{count} custom page name(s) loaded.\nClick to view, edit, or clear.")
                self.btn_paste.setStyleSheet("""
                    QPushButton {
                        background: #2b0816;
                        color: #ff6b8b;
                        border: 1px solid #ff2a5f;
                        border-radius: 4px;
                        padding: 1px 10px;
                        font-weight: 700;
                        font-size: 10.5px;
                    }
                    QPushButton:hover { background: #3d0e22; color: #ffffff; }
                """)
            else:
                self.btn_paste.setText("📝 Paste Names")
                self.btn_paste.setToolTip("Click to paste custom page names (1 per line)")
                self.btn_paste.setStyleSheet("""
                    QPushButton {
                        background: #201026;
                        color: #c084fc;
                        border: 1px solid #7c3aed;
                        border-radius: 4px;
                        padding: 1px 10px;
                        font-weight: 700;
                        font-size: 10px;
                    }
                    QPushButton:hover { background: #32163d; color: #ffffff; }
                """)

    def _append_log(self, text: str) -> None:
        self.txt_terminal.append(text)
        sb = self.txt_terminal.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    # -------------------------------------------------------------
    # Automation Execution Logic
    # -------------------------------------------------------------
    def _start_automation(self) -> None:
        target_profs = self._get_target_profiles()
        if not target_profs:
            QMessageBox.warning(self, "No Profiles", "No profiles found in the selected target group or numbers range!")
            return

        self.target_profiles = target_profs
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_val_success.setText("0")
        self.lbl_val_failed.setText("0")
        self.lbl_val_remaining.setText(str(len(target_profs)))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Progress: 0/{len(target_profs)} (0%)")

        fail_grp = self.combo_fail_group.currentData() if hasattr(self, "combo_fail_group") else None
        if fail_grp in ("NONE", "None", "__CREATE_NEW__", "", None):
            fail_grp = None

        creation_mode = "custom" if (hasattr(self, "combo_mode") and self.combo_mode.currentIndex() == 1) else "random"
        cat_id = str(self.combo_category.currentData() or "2347428775505624") if hasattr(self, "combo_category") else "2347428775505624"
        cat_name = str(self.combo_category.currentText() or "Digital Creator") if hasattr(self, "combo_category") else "Digital Creator"

        if creation_mode == "custom" and not self.loaded_page_names:
            QMessageBox.warning(
                self,
                "No Custom Names Loaded",
                "You selected Custom Mode, but haven't entered any page names!\n\n"
                "Please click the 'Paste Names' button to enter or paste custom page names."
            )
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return

        # Read active proxy config from persistent file
        proxy_enabled = False
        proxy_string = ""
        proxy_mode = "dynamic"
        cfg_path = self._get_proxy_config_path()
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                proxy_enabled = bool(cdata.get("enabled", False))
                proxy_string = str(cdata.get("proxy_string", "")).strip()
                if not proxy_string and "proxies" in cdata and isinstance(cdata["proxies"], list):
                    proxy_string = "\n".join(str(p).strip() for p in cdata["proxies"])
                proxy_mode = str(cdata.get("mode", "dynamic")).lower()
            except Exception:
                pass

        creation_method = "method2" if (hasattr(self, "combo_method") and self.combo_method.currentIndex() == 1) else "method1"

        launcher = getattr(self.parent(), "browser_launcher", None) if self.parent() else None
        self.worker_thread = PageCreatorWorkerThread(
            profiles_list=target_profs,
            page_names_list=self.loaded_page_names if creation_mode == "custom" else [],
            creation_mode=creation_mode,
            creation_method=creation_method,
            category_id=cat_id,
            category_name=cat_name,
            pages_per_account=1,
            threads_count=self.spin_threads.value(),
            delay_sec=self.spin_delay.value(),
            headless=self.chk_headless.isChecked(),
            auto_switch_page=self.chk_auto_switch.isChecked(),
            failed_group=fail_grp,
            profile_mgr=self.profile_mgr,
            browser_launcher=launcher,
            proxy_enabled=proxy_enabled,
            proxy_string=proxy_string,
            proxy_mode=proxy_mode,
            parent=self
        )
        self.worker_thread.log_emitted.connect(self._append_log)
        self.worker_thread.progress_updated.connect(self._on_progress_updated)
        self.worker_thread.stats_updated.connect(self._on_stats_updated)
        self.worker_thread.finished_signal.connect(self._on_finished)
        self.worker_thread.start()

    def _stop_automation(self) -> None:
        was_running = False
        if self.worker_thread and self.worker_thread.isRunning():
            was_running = True
            self.worker_thread.stop()
            self.worker_thread.wait(1000)

        kill_all_bot_browsers()
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if was_running:
            self._append_log("🛑 [STOPPED] Automation aborted and all active browsers closed.")

    def _cleanup_and_close(self) -> None:
        if hasattr(self, "timer_hb") and self.timer_hb.isActive():
            self.timer_hb.stop()
        self._stop_automation()
        self.reject()

    def closeEvent(self, event) -> None:
        if hasattr(self, "timer_hb") and self.timer_hb.isActive():
            self.timer_hb.stop()
        self._stop_automation()
        event.accept()

    def reject(self) -> None:
        if hasattr(self, "timer_hb") and self.timer_hb.isActive():
            self.timer_hb.stop()
        self._stop_automation()
        super().reject()

    def _on_progress_updated(self, current: int, total: int) -> None:
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"Progress: {current}/{total} ({pct}%)")

    def _on_stats_updated(self, success: int, failed: int, remaining: int) -> None:
        self.lbl_val_success.setText(str(success))
        self.lbl_val_failed.setText(str(failed))
        self.lbl_val_remaining.setText(str(remaining))

    def _on_finished(self, success: bool, message: str, report_path: str) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._append_log(f"🏁 [COMPLETE] {message}")
        
        if self.profile_mgr and hasattr(self.profile_mgr, "load_profiles"):
            try:
                self.profile_mgr.load_profiles()
            except Exception:
                pass
        self._update_db_counter()
        self._on_creation_mode_changed()
        
        modal = AutomationFinishedModal(
            summary_text=message,
            report_path=report_path,
            success_count=int(self.lbl_val_success.text() or "0"),
            failed_count=int(self.lbl_val_failed.text() or "0"),
            parent=self
        )
        modal.exec()

    def _open_reports_dir(self) -> None:
        rep_dir = Path(__file__).resolve().parent / "reports"
        rep_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(rep_dir))
        else:
            subprocess.Popen(["xdg-open", str(rep_dir)])

    def _on_open_proxy_modal(self) -> None:
        modal = ProxySettingsModal(parent=self)
        if modal.exec() == QDialog.Accepted:
            self._update_proxy_btn_state()

    def _get_proxy_config_path(self) -> Path:
        return Path(__file__).resolve().parent / "fb_page_creator_proxy_config.json"

    def _update_proxy_btn_state(self) -> None:
        cfg_path = self._get_proxy_config_path()
        is_enabled = False
        mode_str = "dynamic"
        proxy_count = 0
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                is_enabled = bool(cdata.get("enabled", False))
                mode_str = str(cdata.get("mode", "dynamic")).lower()
                raw_p = str(cdata.get("proxy_string", "")).strip()
                p_lines = [l.strip() for l in raw_p.splitlines() if l.strip() and not l.strip().startswith("#")]
                proxy_count = len(p_lines)
            except Exception:
                pass

        if not hasattr(self, "btn_proxy"):
            return

        if is_enabled:
            count_info = f" ({proxy_count})" if proxy_count > 0 else ""
            self.btn_proxy.setText(f"🛡️ Proxy: ON{count_info}")
            self.btn_proxy.setToolTip(f"Residential Proxy is ACTIVE ({mode_str.upper()} mode, {proxy_count} IP(s) configured).\nClick to configure or disable.")
            self.btn_proxy.setStyleSheet("""
                QPushButton {
                    background: #25091f;
                    color: #f472b6;
                    border: 1.5px solid #ec4899;
                    border-radius: 4px;
                    padding: 1px 8px;
                    font-weight: 800;
                    font-size: 10.5px;
                }
                QPushButton:hover {
                    background: #380d2f;
                    color: #ffffff;
                    border-color: #f472b6;
                }
            """)
        else:
            self.btn_proxy.setText("🛡️ Proxy: OFF")
            self.btn_proxy.setToolTip("Residential Proxy is OFF.\nClick to configure and enable.")
            self.btn_proxy.setStyleSheet("""
                QPushButton {
                    background: #0e0e1c;
                    color: #94a3b8;
                    border: 1px solid #232545;
                    border-radius: 4px;
                    padding: 1px 8px;
                    font-weight: 700;
                    font-size: 10.5px;
                }
                QPushButton:hover {
                    background: #1c142e;
                    color: #f472b6;
                    border-color: #db277788;
                }
            """)


# Alias for backward compatibility
FbBulkPageCreatorBotDialog = MasterBotStudioDialog

_active_bot_dialogs: List[Any] = []

def launch_ui(profile_mgr=None, parent=None, **kwargs):
    """Entry point for srkBrowser Dynamic Bot Launcher."""
    if profile_mgr is None:
        try:
            from profile_manager import ProfileManager
            profile_mgr = ProfileManager()
        except Exception:
            class DummyPM:
                def get_all_profiles(self): return []
                def get_groups(self): return ["Default", "Social", "Personal"]
            profile_mgr = DummyPM()

    dialog = MasterBotStudioDialog(
        profile_mgr=profile_mgr,
        bot_id="fb_bulk_page_create",
        bot_title="⚡ Facebook Bulk Page Creator Studio",
        parent=parent
    )
    if getattr(dialog, 'is_duplicate', False):
        return dialog

    dialog.setWindowModality(Qt.WindowModality.NonModal)
    _active_bot_dialogs.append(dialog)
    dialog.finished.connect(lambda: _active_bot_dialogs.remove(dialog) if dialog in _active_bot_dialogs else None)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog

def main(profile_mgr=None, parent=None, **kwargs):
    app = QApplication.instance()
    is_standalone = False
    if not app:
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        is_standalone = True

    dialog = launch_ui(profile_mgr=profile_mgr, parent=parent, **kwargs)
    if is_standalone and not getattr(dialog, 'is_duplicate', False):
        sys.exit(app.exec())
    return dialog

__all__ = ["MasterBotStudioDialog", "FbBulkPageCreatorBotDialog", "launch_ui", "main"]

