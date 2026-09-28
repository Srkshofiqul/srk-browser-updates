"""
srkBrowser - VIP Client Activation Dialog
Ultra-Luxury Obsidian Dark UI with Real-Time Telegram Cloud Approval
Author: SRK Shofiqul
"""

import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QApplication, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon, QColor

from core.telegram_license_shield import (
    get_machine_hwid,
    decode_license_key,
    verify_license_data,
    save_license_file,
    send_telegram_request,
    poll_telegram_approval,
    get_saved_client_meta
)


class VIPActivationDialog(QDialog):
    status_updated = Signal(str)
    approval_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("srkBrowser VIP Activation Shield")
        self.setFixedSize(540, 560)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d13;
                border: 1px solid #1f293d;
                border-radius: 12px;
            }
        """)

        self.hwid = get_machine_hwid()
        self.is_polling = False

        self.status_updated.connect(self._on_status_updated)
        self.approval_finished.connect(self._on_approval_finished)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        # 1. Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #121724, stop:1 #0c101a);
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 10px 14px;
            }
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setSpacing(4)

        title_lbl = QLabel("👑 srkBrowser VIP Client Activation")
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 900; color: #00ffff; background: transparent; border: none;")
        h_layout.addWidget(title_lbl)

        sub_lbl = QLabel("Hardware-Locked Enterprise Shield • Developed with ❤️ by SRK Shofiqul")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        h_layout.addWidget(sub_lbl)

        layout.addWidget(header_frame)

        # 2. Hardware ID Card
        hwid_frame = QFrame()
        hwid_frame.setStyleSheet("""
            QFrame {
                background: #111522;
                border: 1px solid #23314a;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        hwid_layout = QVBoxLayout(hwid_frame)
        hwid_layout.setSpacing(6)

        hwid_tag = QLabel("YOUR UNIQUE HARDWARE ID (HWID):")
        hwid_tag.setStyleSheet("font-size: 10px; font-weight: 800; color: #38bdf8; letter-spacing: 1px; background: transparent; border: none;")
        hwid_layout.addWidget(hwid_tag)

        row_hwid = QHBoxLayout()
        self.hwid_lbl = QLabel(self.hwid)
        self.hwid_lbl.setStyleSheet("""
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 15px;
            font-weight: bold;
            color: #ffffff;
            background: transparent;
            border: none;
        """)
        row_hwid.addWidget(self.hwid_lbl)

        btn_copy = QPushButton("📋 Copy HWID")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(0, 255, 255, 0.12);
                color: #00ffff;
                border: 1px solid rgba(0, 255, 255, 0.35);
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: rgba(0, 255, 255, 0.22);
            }
        """)
        btn_copy.clicked.connect(self._copy_hwid)
        row_hwid.addWidget(btn_copy)
        hwid_layout.addLayout(row_hwid)

        layout.addWidget(hwid_frame)

        # 3. Client Name & Phone Input
        input_frame = QFrame()
        input_frame.setStyleSheet("background: transparent; border: none;")
        in_layout = QVBoxLayout(input_frame)
        in_layout.setContentsMargins(0, 4, 0, 4)
        in_layout.setSpacing(10)

        lbl_name = QLabel("Client Name / Business:")
        lbl_name.setStyleSheet("font-size: 11px; font-weight: 700; color: #cbd5e1;")
        in_layout.addWidget(lbl_name)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter your full name or company...")
        self.name_edit.setStyleSheet("""
            QLineEdit {
                background: #141926;
                border: 1px solid #283650;
                border-radius: 7px;
                color: #f8fafc;
                font-size: 13px;
                padding: 7px 12px;
            }
            QLineEdit:focus {
                border: 1px solid #00ffff;
            }
        """)
        in_layout.addWidget(self.name_edit)

        lbl_phone = QLabel("WhatsApp / Phone Number (Optional):")
        lbl_phone.setStyleSheet("font-size: 11px; font-weight: 700; color: #cbd5e1;")
        in_layout.addWidget(lbl_phone)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("e.g. 017xxxxxxxx")
        self.phone_edit.setStyleSheet("""
            QLineEdit {
                background: #141926;
                border: 1px solid #283650;
                border-radius: 7px;
                color: #f8fafc;
                font-size: 13px;
                padding: 7px 12px;
            }
            QLineEdit:focus {
                border: 1px solid #00ffff;
            }
        """)
        in_layout.addWidget(self.phone_edit)

        try:
            saved_meta = get_saved_client_meta()
            if saved_meta.get("name"):
                self.name_edit.setText(saved_meta["name"])
            if saved_meta.get("phone"):
                self.phone_edit.setText(saved_meta["phone"])
        except Exception:
            pass

        layout.addWidget(input_frame)

        # 4. Big Telegram Request Action Button
        self.btn_request = QPushButton("🚀 Request Activation via Telegram")
        self.btn_request.setCursor(Qt.PointingHandCursor)
        self.btn_request.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #00b4d8);
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 800;
                padding: 10px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
                border: 1px solid #00ffff;
            }
            QPushButton:disabled {
                background: #334155;
                color: #94a3b8;
                border: 1px solid #475569;
            }
        """)
        self.btn_request.clicked.connect(self._on_request_telegram)
        layout.addWidget(self.btn_request)

        # 5. Status text & progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1e293b;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #00ffff;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready to connect to SRK License Cloud.")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        layout.addWidget(self.status_lbl)

        # 6. Offline Key Manual Input (Collapsible/Accordion)
        self.btn_toggle_offline = QPushButton("🔑 Have an Offline License Key? Click to enter")
        self.btn_toggle_offline.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_offline.setStyleSheet("font-size: 11px; color: #38bdf8; background: transparent; border: none; text-decoration: underline;")
        self.btn_toggle_offline.clicked.connect(self._toggle_offline_ui)
        layout.addWidget(self.btn_toggle_offline)

        self.offline_frame = QFrame()
        self.offline_frame.setStyleSheet("background: transparent; border: none;")
        off_layout = QHBoxLayout(self.offline_frame)
        off_layout.setContentsMargins(0, 0, 0, 0)
        off_layout.setSpacing(8)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Paste SRK-KEY-xxxx here...")
        self.key_edit.setStyleSheet("""
            QLineEdit {
                background: #141926;
                border: 1px solid #283650;
                border-radius: 6px;
                color: #ffffff;
                font-family: monospace;
                font-size: 11px;
                padding: 6px 10px;
            }
        """)
        off_layout.addWidget(self.key_edit)

        btn_activate_key = QPushButton("Activate")
        btn_activate_key.setCursor(Qt.PointingHandCursor)
        btn_activate_key.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        btn_activate_key.clicked.connect(self._activate_offline_key)
        off_layout.addWidget(btn_activate_key)

        self.offline_frame.setVisible(False)
        layout.addWidget(self.offline_frame)

    def _copy_hwid(self):
        cb = QApplication.clipboard()
        cb.setText(self.hwid)
        self.status_lbl.setText("📋 HWID copied to clipboard!")

    def _toggle_offline_ui(self):
        self.offline_frame.setVisible(not self.offline_frame.isVisible())

    def _activate_offline_key(self):
        raw_key = self.key_edit.text().strip()
        if not raw_key:
            QMessageBox.warning(self, "Empty Key", "Please paste your license key first.")
            return

        payload = decode_license_key(raw_key)
        if not payload:
            QMessageBox.critical(self, "Invalid Key", "The entered license key format is invalid.")
            return

        valid, msg = verify_license_data(payload, self.hwid)
        if not valid:
            QMessageBox.critical(self, "License Error", f"Failed to activate:\n{msg}")
            return

        name = self.name_edit.text().strip()
        phone = self.phone_edit.text().strip()
        if name and (not payload.get("customer_name") or payload.get("customer_name") == "Valued Customer"):
            payload["customer_name"] = name
            payload["name"] = name
        if phone and not payload.get("phone"):
            payload["phone"] = phone

        save_license_file(payload)
        QMessageBox.information(self, "Activated", f"🎉 License Activated Successfully!\n{msg}")
        self.accept()

    def _on_request_telegram(self):
        name = self.name_edit.text().strip()
        phone = self.phone_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name Required", "Please enter your name or business name.")
            self.name_edit.setFocus()
            return

        self.btn_request.setEnabled(False)
        self.name_edit.setEnabled(False)
        self.phone_edit.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setText("📡 Sending request to Shofiqul Bhai's Telegram...")

        def _worker():
            ok, msg = send_telegram_request(name, phone, self.hwid)
            if not ok:
                self.approval_finished.emit(False, msg)
                return

            self.status_updated.emit("⏳ Request Sent! Waiting for Admin Approval on Telegram...")
            appr_ok, appr_msg = poll_telegram_approval(
                self.hwid,
                name,
                client_phone=phone,
                timeout_sec=300,
                status_callback=lambda text: self.status_updated.emit(text)
            )
            self.approval_finished.emit(appr_ok, appr_msg)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_status_updated(self, text: str):
        self.status_lbl.setText(text)

    def _on_approval_finished(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        if success:
            self.status_lbl.setText("🎉 ACCESS GRANTED! Unlocking srkBrowser...")
            self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #10b981;")
            QTimer.singleShot(900, self.accept)
        else:
            self.btn_request.setEnabled(True)
            self.name_edit.setEnabled(True)
            self.phone_edit.setEnabled(True)
            self.status_lbl.setText(f"❌ {message}")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #ef4444;")
            QMessageBox.warning(self, "Authorization Status", message)


def enforce_telegram_license_check(parent=None) -> bool:
    """
    Checks if system is activated. If not, shows the VIPActivationDialog.
    Returns True if valid/activated, False if closed/rejected.
    """
    from core.telegram_license_shield import is_system_activated
    is_act, status_text, _ = is_system_activated()
    if is_act:
        return True

    dlg = VIPActivationDialog(parent)
    res = dlg.exec()
    return res == QDialog.Accepted
