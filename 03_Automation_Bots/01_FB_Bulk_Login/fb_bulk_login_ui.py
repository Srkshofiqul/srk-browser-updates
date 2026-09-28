"""
Professional Dark-Obsidian Cyber-Ops Automation Studio UI for Facebook Bulk ID Login Bot.
Equipped with:
- Excel (.xlsx), CSV (.csv), and Plain Text (.txt) accounts file loader
- Interactive Paste Accounts Modal
- Target Profile Group selector & dynamic on-the-fly group creation
- Auto-profile generator per account with anti-detect fingerprinting
- Automated 2FA OTP solver & failure screenshot recorder
- Multi-threaded worker control with live terminal and metrics
- Built-in srkBrowser heartbeat detector and license synchronization
"""

import os
import re
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QLineEdit, QFileDialog, QInputDialog, QWidget, QSizePolicy,
    QToolTip
)

# Import bot security and helpers
from fb_bulk_login_security import check_srbrowser_heartbeat, get_effective_bot_license, verify_standalone_execution_guard, BotSingleInstanceGuard
from fb_bulk_login_helpers import parse_accounts_file_or_text, get_all_logged_in_accounts_list, export_all_logged_in_accounts_backup
from fb_bulk_login_engine import kill_all_bot_browsers, GracefulShutdownWorker, FbBulkLoginWorkerThread, get_active_browser_sessions_count


class ShutdownProgressDialog(QDialog):
    """
    Live Animated Graceful Shutdown Modal:
    Smoothly closes each active browser instance in a background thread with visual feedback,
    preventing any GUI freezes or 'Not Responding' lag.
    """
    def __init__(self, profiles: List[Dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profiles = profiles
        self.setFixedSize(440, 190)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("cardFrame")
        card.setStyleSheet("""
            QFrame#cardFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #110d24, stop:1 #060410);
                border: 2px solid #a855f7;
                border-radius: 12px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(10)

        title = QLabel("🛑 Terminating Browser Sessions...")
        title.setStyleSheet("font-size: 14px; font-weight: 900; color: #f43f5e; letter-spacing: 0.5px;")
        c_layout.addWidget(title)

        self.lbl_status = QLabel("Initiating clean shutdown...")
        self.lbl_status.setStyleSheet("font-size: 11.5px; color: #cbd5e1; font-weight: 600;")
        c_layout.addWidget(self.lbl_status)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, max(1, len(profiles)))
        self.pbar.setValue(0)
        self.pbar.setFixedHeight(12)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet("""
            QProgressBar {
                background-color: #050614;
                border: 1px solid #2b1e4a;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #a855f7);
                border-radius: 5px;
            }
        """)
        c_layout.addWidget(self.pbar)

        lbl_tip = QLabel("✨ Safe Shutdown: Closing CDP ports and saving profile states...")
        lbl_tip.setStyleSheet("font-size: 10px; color: #94a3b8; font-style: italic;")
        c_layout.addWidget(lbl_tip)

        layout.addWidget(card)

        self.worker = GracefulShutdownWorker(self.profiles, self)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        QTimer.singleShot(50, self.worker.start)

    def _on_progress(self, current: int, total: int, text: str) -> None:
        self.pbar.setMaximum(max(1, total))
        self.pbar.setValue(current)
        self.lbl_status.setText(text)

    def _on_finished(self, count: int) -> None:
        kill_all_bot_browsers()
        self.accept()


class PasteAccountsModal(QDialog):
    """
    Cyber-Styled Modal Dialog for pasting multi-line Facebook account credentials.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📝 Paste Facebook Accounts")
        self.resize(600, 440)
        self.setStyleSheet("""
            QDialog {
                background-color: #060712;
                color: #e2e8f0;
                font-family: 'Segoe UI', 'Consolas', monospace, sans-serif;
            }
            QLabel { color: #e2e8f0; }
            QTextEdit {
                background-color: #03040c;
                color: #38bdf8;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
                font-size: 12px;
                border: 1px solid #7c3aed66;
                border-radius: 8px;
                padding: 12px;
            }
            QTextEdit:focus {
                border: 1px solid #c084fc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("📝 Paste Facebook Accounts")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 900; color: #c084fc;")

        lbl_hint = QLabel(
            "📋 Supported Formats (1 account per line):\n"
            "  • UID|Password|2FA_Secret|Cookies\n"
            "  • UID|Password|Cookies\n"
            "  • UID|Password|2FA_Secret\n"
            "  • UID:Password:2FA_Secret\n"
            "  • Email|Password\n"
            "  • Excel columns: [UID, Password, Cookies] or [UID, Password, 2FA, Cookies]"
        )
        lbl_hint.setStyleSheet("font-size: 11px; color: #94a3b8; background: #080a18; border: 1px solid #2b1e4a; border-radius: 6px; padding: 8px;")

        self.txt_content = QTextEdit()
        self.txt_content.setPlaceholderText("100012345678|MySecretPass123|JBSWY3DPEHPK3PXP|c_user=100012345678; xs=...\n100098765432|Pass98765|ABCDEF234567")
        self.txt_content.textChanged.connect(self._update_counter)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.lbl_count = QLabel("📋 0 lines entered")
        self.lbl_count.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11.5px;")

        btn_cancel = QPushButton("✖ Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #1e1338;
                color: #94a3b8;
                border: 1px solid #7c3aed44;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2b1a4f;
                color: #f1f5f9;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_load = QPushButton("💾 Load Accounts")
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #3b82f6);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 22px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #60a5fa);
            }
        """)
        btn_load.clicked.connect(self.accept)

        btn_box.addWidget(self.lbl_count)
        btn_box.addStretch(1)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_load)

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_hint)
        layout.addWidget(self.txt_content, stretch=1)
        layout.addLayout(btn_box)

    def _update_counter(self) -> None:
        lines = [l for l in self.txt_content.toPlainText().splitlines() if l.strip()]
        self.lbl_count.setText(f"📋 {len(lines)} line{'s' if len(lines) != 1 else ''} entered")

    def get_text(self) -> str:
        return self.txt_content.toPlainText().strip()


class CyberNoticeModal(QDialog):
    """
    Modern Cyber-styled alert modal with colored themes and auto-dismiss timer.
    """
    THEMES = {
        "red": {
            "border": "#f43f5e",
            "title": "#fda4af",
            "bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a080c, stop:1 #080305)",
            "btn_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #be123c)",
            "btn_hover": "#f43f5e"
        },
        "amber": {
            "border": "#f59e0b",
            "title": "#fde68a",
            "bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1408, stop:1 #080603)",
            "btn_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309)",
            "btn_hover": "#f59e0b"
        },
        "purple": {
            "border": "#a855f7",
            "title": "#e9d5ff",
            "bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #140d24, stop:1 #060410)",
            "btn_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #7c3aed)",
            "btn_hover": "#a855f7"
        }
    }

    def __init__(
        self,
        title: str,
        message: str,
        subtext: str = "",
        theme_color: str = "purple",
        auto_close_ms: int = 0,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(480, 210)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        cfg = self.THEMES.get(theme_color, self.THEMES["purple"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("cardFrame")
        card.setStyleSheet(f"""
            QFrame#cardFrame {{
                background: {cfg["bg"]};
                border: 2px solid {cfg["border"]};
                border-radius: 12px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(22, 20, 22, 20)
        c_layout.setSpacing(10)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 14.5px; font-weight: 900; color: {cfg['title']};")
        c_layout.addWidget(lbl_t)

        lbl_m = QLabel(message)
        lbl_m.setWordWrap(True)
        lbl_m.setStyleSheet("font-size: 12px; color: #f1f5f9; font-weight: 600; line-height: 1.4;")
        c_layout.addWidget(lbl_m)

        if subtext:
            lbl_s = QLabel(subtext)
            lbl_s.setWordWrap(True)
            lbl_s.setStyleSheet("font-size: 10.5px; color: #94a3b8; font-style: italic;")
            c_layout.addWidget(lbl_s)

        c_layout.addStretch(1)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_ok = QPushButton("OK")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background: {cfg["btn_bg"]};
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 7px 22px;
                font-weight: 800;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {cfg["btn_hover"]};
            }}
        """)
        btn_ok.clicked.connect(self.accept)
        btn_box.addWidget(btn_ok)
        c_layout.addLayout(btn_box)

        layout.addWidget(card)

        if auto_close_ms > 0:
            QTimer.singleShot(auto_close_ms, self.accept)


class MasterBotStudioDialog(QDialog):
    """
    Official Facebook Bulk ID Login Studio Dialog for srkBrowser.
    Features:
    - Multi-format accounts loading (Excel .xlsx, CSV .csv, TXT .txt, and Paste modal)
    - Dynamic Group selector & auto-isolated profile generation
    - Multi-threaded Playwright execution with 2FA TOTP automation
    - Diagnostic screenshot recording & timestamped CSV reports
    - Live srkBrowser heartbeat detection & VIP license synchronization
    """
    def __init__(
        self,
        profile_mgr: Any = None,
        parent: Optional[QWidget] = None,
        bot_id: str = "fb_bulk_login",
        bot_title: str = "Facebook Bulk ID Login Studio",
        worker_thread_class: Optional[Any] = None,
        *args,
        **kwargs
    ) -> None:
        # Handle flexible argument orders (profile_mgr, parent) or (profile_mgr, bot_id, bot_title, ...)
        if isinstance(parent, str):
            bot_id = parent
            parent = kwargs.get("parent")
        elif parent is not None and not isinstance(parent, QWidget):
            parent = None

        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.bot_id = str(bot_id or "fb_bulk_login")
        self.bot_title = str(bot_title or "Facebook Bulk ID Login Studio")
        self.worker_thread_class = worker_thread_class or FbBulkLoginWorkerThread
        self.thread: Optional[Any] = None
        self.loaded_accounts: List[Dict[str, Any]] = []

        self.setWindowTitle(f"🤖 {self.bot_title} — Professional Automation Studio")

        self._drag_pos = QPoint()
        self.setFixedSize(700, 442)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # High-contrast Cyberpunk QToolTip styling across the dialog
        QToolTip.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        t_pal = QToolTip.palette()
        t_pal.setColor(QPalette.ToolTipBase, QColor("#0d1124"))
        t_pal.setColor(QPalette.ToolTipText, QColor("#f8fafc"))
        QToolTip.setPalette(t_pal)

        self.setStyleSheet("""
            QToolTip {
                background-color: #0d1124;
                color: #f8fafc;
                border: 1.5px solid #8b5cf6;
                border-radius: 6px;
                padding: 6px 10px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11.5px;
                font-weight: 600;
            }
        """)

        # Standalone Anti-Piracy Check
        if not verify_standalone_execution_guard():
            modal = CyberNoticeModal(
                title="🔒 Security Check Failed",
                message="Unauthorized Execution Blocked:\nThis bot module must run inside the genuine srkBrowser directory.",
                theme_color="red",
                parent=self
            )
            modal.exec()
            self.reject()
            return

        self._build_ui()
        self._setup_heartbeat_timer()

        # Single-Instance Lock Guard
        self.is_duplicate = False
        self.instance_guard = BotSingleInstanceGuard(self.bot_id, self)
        if self.instance_guard.is_already_running():
            self.is_duplicate = True
            modal = CyberNoticeModal(
                title=f"🛑 {self.bot_title} Already Open",
                message=f"{self.bot_title} is already running in another window.",
                subtext="🎯 The active window has been brought to the front.",
                theme_color="red",
                auto_close_ms=3500
            )
            modal.exec()
            QTimer.singleShot(0, self.reject)
            return

        self.instance_guard.message_received.connect(self._on_ipc_message)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            self._drag_pos = pos - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            self.move(pos - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = QPoint()
        event.accept()

    def _style_spinbox(self, spin: Any) -> None:
        spin.setButtonSymbols(QSpinBox.NoButtons)
        spin.setFixedHeight(27)
        spin.setFixedWidth(52)
        spin.setAlignment(Qt.AlignCenter)
        spin.setStyleSheet("""
            QSpinBox, QDoubleSpinBox {
                background-color: #0c0e24;
                color: #38bdf8;
                border: 1px solid #281d4a;
                border-radius: 4px;
                font-weight: 800;
                font-size: 12px;
                padding: 0px 2px;
            }
            QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 0px;
                height: 0px;
                border: none;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #7c3aed;
                background-color: #140d24;
            }
        """)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # Outer Main Card with Glowing Border & Void Background
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

        # -------------------------------------------------------------
        # 1. HEADER BAR (Ultra-clean Cyber Deck)
        # -------------------------------------------------------------
        h_head = QHBoxLayout()
        h_head.setContentsMargins(0, 0, 0, 0)
        h_head.setSpacing(8)

        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 16px; border: none; background: transparent; color: #f43f5e;")

        self.lbl_title = QLabel(self.bot_title)
        self.lbl_title.setStyleSheet("""
            color: #c084fc;
            font-size: 15px;
            font-weight: 800;
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: transparent;
            border: none;
            letter-spacing: 0.3px;
        """)

        # Enable dragging directly on card, header, and title labels
        self.main_card.mousePressEvent = self.mousePressEvent
        self.main_card.mouseMoveEvent = self.mouseMoveEvent
        self.main_card.mouseReleaseEvent = self.mouseReleaseEvent
        self.lbl_title.mousePressEvent = self.mousePressEvent
        self.lbl_title.mouseMoveEvent = self.mouseMoveEvent
        self.lbl_title.mouseReleaseEvent = self.mouseReleaseEvent
        lbl_icon.mousePressEvent = self.mousePressEvent
        lbl_icon.mouseMoveEvent = self.mouseMoveEvent
        lbl_icon.mouseReleaseEvent = self.mouseReleaseEvent

        self.lbl_license = None

        # Heartbeat Indicator
        self.lbl_heartbeat = QLabel("🟢 srkBrowser Active")
        self.lbl_heartbeat.setFixedHeight(24)
        self.lbl_heartbeat.setStyleSheet("""
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
        btn_close.clicked.connect(self.reject)

        h_head.addWidget(lbl_icon)
        h_head.addWidget(self.lbl_title)
        h_head.addStretch()
        h_head.addWidget(self.lbl_heartbeat)
        h_head.addSpacing(6)
        h_head.addWidget(btn_close)
        card_layout.addLayout(h_head)

        # -------------------------------------------------------------
        # 2. ACCOUNTS & CONFIGURATION BOX (Compact & Sleek)
        # -------------------------------------------------------------
        self.target_box = QFrame()
        self.target_box.setFixedHeight(72)
        self.target_box.setStyleSheet("background: #131428; border-radius: 8px; border: 1px solid #232545;")
        v_target = QVBoxLayout(self.target_box)
        v_target.setContentsMargins(8, 4, 8, 4)
        v_target.setSpacing(10)

        # Row A: Accounts File & Paste Selectors + Count Badge
        h_acc_row = QHBoxLayout()
        h_acc_row.setSpacing(6)

        self.btn_upload = QPushButton("📁 Choose File ▾")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.setFixedHeight(27)
        self.btn_upload.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 2px 10px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
            }
        """)
        self.btn_upload.clicked.connect(self._on_upload_accounts_file)
        h_acc_row.addWidget(self.btn_upload)

        self.btn_paste = QPushButton("📝 Paste Accounts")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.setFixedHeight(27)
        self.btn_paste.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #c084fc;
                border: 1px solid #7c3aed;
                border-radius: 4px;
                padding: 2px 10px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover { background: #261b45; color: #ffffff; }
        """)
        self.btn_paste.clicked.connect(self._on_paste_accounts_text)
        h_acc_row.addWidget(self.btn_paste)

        self.btn_clear_acc = QPushButton("🗑️ Clear")
        self.btn_clear_acc.setCursor(Qt.PointingHandCursor)
        self.btn_clear_acc.setFixedHeight(27)
        self.btn_clear_acc.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #f87171;
                border: 1px solid #ef444455;
                border-radius: 4px;
                padding: 2px 10px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover { background: #330b14; color: #ffffff; border-color: #ef4444; }
        """)
        self.btn_clear_acc.clicked.connect(self._on_clear_accounts)
        h_acc_row.addWidget(self.btn_clear_acc)

        self.lbl_acc_status = QLabel("No accounts file selected")
        self.lbl_acc_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        h_acc_row.addWidget(self.lbl_acc_status, stretch=1)

        self.lbl_accounts_badge = QLabel("📋 0 Accounts Ready")
        self.lbl_accounts_badge.setFixedHeight(26)
        self.lbl_accounts_badge.setStyleSheet("""
            background: #080913; color: #94a3b8;
            border: 1px solid #334155; border-radius: 4px;
            padding: 2px 9px; font-weight: 800; font-size: 11px;
        """)
        h_acc_row.addWidget(self.lbl_accounts_badge)
        v_target.addLayout(h_acc_row)

        # Row B: Concurrency, Delay, Headless, Language & DB Button
        h_param_row = QHBoxLayout()
        h_param_row.setSpacing(6)

        lbl_grp = QLabel("Group:")
        lbl_grp.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11.5px;")
        h_param_row.addWidget(lbl_grp)

        self.cmb_group = QComboBox()
        self.cmb_group.setFixedHeight(27)
        self.cmb_group.setMinimumWidth(110)
        self.cmb_group.setStyleSheet("""
            QComboBox {
                background: #080913;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 1px 8px;
                font-weight: 700;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #10121e;
                color: #ffffff;
                selection-background-color: #8b5cf6;
            }
        """)
        self._populate_groups()
        self.cmb_group.currentIndexChanged.connect(self._on_group_changed)
        h_param_row.addWidget(self.cmb_group)

        self.btn_refresh_groups = QPushButton("🔄")
        self.btn_refresh_groups.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_groups.setFixedSize(26, 26)
        self.btn_refresh_groups.setToolTip("🔄 Refresh Groups from srkBrowser")
        self.btn_refresh_groups.setStyleSheet("""
            QPushButton {
                background: #080913;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover { background: #1a1f3c; color: #67e8f9; border-color: #38bdf8; }
        """)
        self.btn_refresh_groups.clicked.connect(self._on_refresh_sync)
        h_param_row.addWidget(self.btn_refresh_groups)

        h_param_row.addStretch(1)

        lbl_th = QLabel("Threads:")
        lbl_th.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11.5px;")
        h_param_row.addWidget(lbl_th)

        self.spn_threads = QSpinBox()
        self.spn_threads.setRange(1, 20)
        self.spn_threads.setValue(1)
        self._style_spinbox(self.spn_threads)
        h_param_row.addWidget(self.spn_threads)

        h_param_row.addStretch(1)

        lbl_del = QLabel("Delay:")
        lbl_del.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11.5px;")
        h_param_row.addWidget(lbl_del)

        self.spn_delay = QDoubleSpinBox()
        self.spn_delay.setRange(0.5, 30.0)
        self.spn_delay.setSingleStep(0.5)
        self.spn_delay.setValue(2.0)
        self.spn_delay.setSuffix("s")
        self._style_spinbox(self.spn_delay)
        h_param_row.addWidget(self.spn_delay)

        h_param_row.addStretch(1)

        self.chk_auto_lang = QCheckBox("English (en_US)")
        self.chk_auto_lang.setChecked(True)
        self.chk_auto_lang.setCursor(Qt.PointingHandCursor)
        self.chk_auto_lang.setStyleSheet("""
            QCheckBox {
                font-size: 11.5px;
                font-weight: 700;
                color: #a78bfa;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background-color: #080913;
                border: 1px solid #6366f1;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #8b5cf6;
                border-color: #a78bfa;
            }
        """)
        h_param_row.addWidget(self.chk_auto_lang)

        h_param_row.addStretch(1)

        self.chk_headless = QCheckBox("Headless")
        self.chk_headless.setChecked(False)
        self.chk_headless.setCursor(Qt.PointingHandCursor)
        self.chk_headless.setStyleSheet("""
            QCheckBox {
                font-size: 11.5px;
                font-weight: 700;
                color: #94a3b8;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background-color: #080913;
                border: 1px solid #334155;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #38bdf8;
                border-color: #38bdf8;
            }
        """)
        h_param_row.addWidget(self.chk_headless)

        v_target.addLayout(h_param_row)
        card_layout.addWidget(self.target_box)

        # -------------------------------------------------------------
        # 3. METRICS DECK (3 Big Glowing Cards)
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

        self.lbl_metric_succ_sub = QLabel("Live Logged-In Accounts")
        self.lbl_metric_succ_sub.setStyleSheet("color: #059669; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cs.addWidget(self.lbl_metric_succ_sub)
        self.lbl_stat_success = self.lbl_val_success
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

        self.lbl_metric_fail_sub = QLabel("Checkpoints / Bad Credentials")
        self.lbl_metric_fail_sub.setStyleSheet("color: #b91c1c; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cf.addWidget(self.lbl_metric_fail_sub)
        self.lbl_stat_failed = self.lbl_val_failed
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

        self.lbl_metric_rem_sub = QLabel("Queued For Automation")
        self.lbl_metric_rem_sub.setStyleSheet("color: #0284c7; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cr.addWidget(self.lbl_metric_rem_sub)
        self.lbl_stat_remaining = self.lbl_val_remaining
        h_metrics.addWidget(self.card_rem, stretch=1)

        card_layout.addLayout(h_metrics)

        # -------------------------------------------------------------
        # 4. PROGRESS BAR (Centered Clean Gradient)
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
        # 5. LIVE LOGS TERMINAL (9-Line Expanded Terminal Frame)
        # -------------------------------------------------------------
        self.log_box = QFrame()
        self.log_box.setFixedHeight(160)
        self.log_box.setStyleSheet("background: #070812; border: 1px solid #1e2238; border-radius: 6px;")
        v_log = QVBoxLayout(self.log_box)
        v_log.setContentsMargins(8, 6, 8, 6)
        v_log.setSpacing(0)

        self.txt_logs = QTextEdit()
        self.terminal = self.txt_logs
        self.txt_logs.setReadOnly(True)
        self.txt_logs.document().setDocumentMargin(2)
        self.txt_logs.setStyleSheet("""
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
        """)
        self.txt_logs.setPlaceholderText("📟 Automation console ready. Logs will appear here in real-time...")
        v_log.addWidget(self.txt_logs)
        card_layout.addWidget(self.log_box)

        # -------------------------------------------------------------
        # 6. ACTION CONTROLS (At the very bottom)
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
        self.btn_reports.clicked.connect(self._open_reports_folder)

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
        self.btn_stop.clicked.connect(lambda: self._stop_automation(is_manual_stop=True))

        # Database Master Backup button (positioned directly to the left of Reports)
        self.btn_db_backup = QPushButton("📦 Database: 0 FB IDs 📥")
        self.btn_db_backup.setCursor(Qt.PointingHandCursor)
        self.btn_db_backup.setFixedHeight(27)
        self.btn_db_backup.setToolTip(
            '<div style="background-color: #0d1124; color: #f8fafc; border: 1.5px solid #059669; '
            'border-radius: 6px; padding: 7px 11px; font-family: \'Segoe UI\', sans-serif; font-size: 11px;">'
            '<b style="color: #34d399; font-size: 11.5px;">📥 Facebook Accounts Master Backup</b><br/>'
            '<span style="color: #cbd5e1; font-size: 10.5px;">Click to download complete backup of all logged-in accounts (Excel / CSV / TXT).</span>'
            '</div>'
        )
        self.btn_db_backup.setStyleSheet("""
            QPushButton {
                background: #09131d;
                color: #38bdf8;
                border: 1px solid #05966999;
                border-radius: 4px;
                padding: 1px 10px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #062b1b;
                color: #6ee7b7;
                border-color: #10b981;
            }
        """)
        self.btn_db_backup.clicked.connect(self._on_download_all_accounts)
        self.btn_db_badge = self.btn_db_backup
        self.lbl_db_count = self.btn_db_backup

        h_act.addWidget(self.btn_run)
        h_act.addStretch()
        h_act.addWidget(self.btn_db_backup)
        h_act.addWidget(self.btn_reports)
        h_act.addWidget(self.btn_stop)

        card_layout.addLayout(h_act)

        # Initial database FB account count refresh
        self._update_db_accounts_count()

    def _update_db_accounts_count(self) -> None:
        """Updates the database backup button with total FB accounts saved in srkBrowser database."""
        try:
            accounts = get_all_logged_in_accounts_list(self.profile_mgr)
            count = len(accounts)
            target = getattr(self, 'btn_db_backup', None) or getattr(self, 'btn_db_badge', None) or getattr(self, 'lbl_db_count', None)
            if target:
                target.setText(f"📦 Database: {count} FB ID{'s' if count != 1 else ''} 📥")
                target.setToolTip(
                    f'<div style="background-color: #0d1124; color: #f8fafc; border: 1.5px solid #059669; '
                    f'border-radius: 6px; padding: 7px 11px; font-family: \'Segoe UI\', sans-serif; font-size: 11px;">'
                    f'<b style="color: #34d399; font-size: 11.5px;">📥 Facebook Accounts Master Backup</b><br/>'
                    f'<span style="color: #cbd5e1; font-size: 10.5px;">Click to download master backup of all '
                    f'<b style="color: #f8fafc;">{count}</b> logged-in Facebook account{"s" if count != 1 else ""} (Excel / CSV / TXT).</span>'
                    f'</div>'
                )
        except Exception:
            pass

    def _on_download_all_accounts(self) -> None:
        """Exports complete master backup of all Facebook accounts and live sessions."""
        accounts = get_all_logged_in_accounts_list(self.profile_mgr)
        if not accounts:
            modal = CyberNoticeModal(
                title="ℹ️ No Accounts in Database",
                message="No Facebook accounts or live sessions were found in the database yet.\nUse this studio to log in and save accounts first.",
                theme_color="amber",
                parent=self
            )
            modal.exec()
            return

        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_file = str(Path.home() / "Desktop" / f"FB_All_Logged_In_Accounts_Backup_{now_str}.xlsx")

        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            "📥 Save Complete Facebook Accounts Master Backup",
            default_file,
            "Excel Workbook (*.xlsx);;Text File (*.txt);;CSV File (*.csv)"
        )
        if not filepath:
            return

        format_type = "xlsx"
        if "(*.txt)" in selected_filter or filepath.lower().endswith(".txt"):
            format_type = "txt"
        elif "(*.csv)" in selected_filter or filepath.lower().endswith(".csv"):
            format_type = "csv"

        ok, count, res_path = export_all_logged_in_accounts_backup(
            profile_mgr=self.profile_mgr,
            target_filepath=Path(filepath),
            format_type=format_type
        )

        if ok:
            modal = CyberNoticeModal(
                title="🎉 Export Complete",
                message=f"Successfully exported {count} Facebook account{'s' if count != 1 else ''} to master backup:\n{Path(res_path).name}",
                subtext="📁 File saved and ready to use.",
                theme_color="purple",
                parent=self
            )
            modal.exec()
            try:
                subprocess.Popen(["explorer", "/select,", str(Path(res_path).resolve())])
            except Exception:
                pass
        else:
            modal = CyberNoticeModal(
                title="⚠️ Export Failed",
                message=f"Could not export accounts backup:\n{res_path}",
                theme_color="red",
                parent=self
            )
            modal.exec()

    def _on_refresh_sync(self) -> None:
        """Reloads profiles, groups, and database account counts directly from disk."""
        try:
            curr_selection = self.cmb_group.currentText()
            if self.profile_mgr and hasattr(self.profile_mgr, 'load_profiles'):
                self.profile_mgr.load_profiles()
            self._populate_groups()

            # Restore previous selection if it still exists
            idx = self.cmb_group.findText(curr_selection)
            if idx >= 0:
                self.cmb_group.setCurrentIndex(idx)

            self._update_db_accounts_count()
            self._append_log("🔄 [SYNC] Synchronized latest groups and profile database from disk.")
        except Exception as e:
            self._append_log(f"⚠️ [SYNC ERROR] Failed to reload database: {e}")

    def _populate_groups(self) -> None:
        self.cmb_group.clear()
        groups = []
        if self.profile_mgr and hasattr(self.profile_mgr, 'get_groups'):
            try:
                g_list = self.profile_mgr.get_groups()
                if g_list:
                    groups = [g for g in g_list if g and g != "All Groups"]
            except Exception:
                pass
        elif self.profile_mgr and hasattr(self.profile_mgr, 'groups'):
            try:
                groups = [g for g in self.profile_mgr.groups if g and g != "All Groups"]
            except Exception:
                pass

        if not groups:
            groups = ["Default"]

        for g in groups:
            self.cmb_group.addItem(g)

        self.cmb_group.addItem("➕ Create New Group...")

    def _on_group_changed(self) -> None:
        if self.cmb_group.currentText() == "➕ Create New Group...":
            new_name, ok = QInputDialog.getText(
                self,
                "Create Profile Group",
                "Enter new Profile Group name:"
            )
            if ok and new_name.strip():
                clean_g = new_name.strip()
                if self.profile_mgr and hasattr(self.profile_mgr, "add_group"):
                    try:
                        self.profile_mgr.add_group(clean_g)
                    except Exception:
                        pass
                self._populate_groups()
                idx = self.cmb_group.findText(clean_g)
                if idx >= 0:
                    self.cmb_group.setCurrentIndex(idx)
            else:
                self.cmb_group.setCurrentIndex(0)

    def _on_upload_accounts_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Facebook Accounts File",
            "",
            "Supported Files (*.xlsx *.csv *.txt);;Excel Files (*.xlsx);;CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return

        accs = parse_accounts_file_or_text(file_path=file_path)
        if accs:
            self.loaded_accounts = accs
            self._update_accounts_badge()
            if hasattr(self, 'lbl_acc_status'):
                self.lbl_acc_status.setText(f"{Path(file_path).name}")
            self._append_log(f"📂 [LOADED] {len(accs)} account(s) from '{Path(file_path).name}'")
        else:
            modal = CyberNoticeModal(
                title="⚠️ No Accounts Found",
                message=f"Could not extract any valid Facebook accounts from:\n{Path(file_path).name}",
                subtext="Please check that the file contains UID and Password columns or pipe-separated lines.",
                theme_color="amber",
                parent=self
            )
            modal.exec()

    def _on_paste_accounts_text(self) -> None:
        modal = PasteAccountsModal(self)
        if modal.exec() == QDialog.Accepted:
            raw_text = modal.get_text()
            if raw_text:
                accs = parse_accounts_file_or_text(text_content=raw_text)
                if accs:
                    self.loaded_accounts = accs
                    self._update_accounts_badge()
                    if hasattr(self, 'lbl_acc_status'):
                        self.lbl_acc_status.setText("Pasted accounts")
                    self._append_log(f"📝 [PASTED] {len(accs)} account(s) successfully loaded from text.")
                else:
                    modal_err = CyberNoticeModal(
                        title="⚠️ No Valid Accounts",
                        message="Could not parse valid credentials from pasted text.",
                        subtext="Ensure each line has at least UID and Password (e.g. UID|Password).",
                        theme_color="amber",
                        parent=self
                    )
                    modal_err.exec()

    def _on_clear_accounts(self) -> None:
        self.loaded_accounts = []
        self._update_accounts_badge()
        if hasattr(self, 'lbl_acc_status'):
            self.lbl_acc_status.setText("No accounts file selected")
        self._append_log("🗑️ Loaded accounts cleared.")

    def _update_accounts_badge(self) -> None:
        count = len(self.loaded_accounts)
        if count > 0:
            self.lbl_accounts_badge.setText(f"📋 {count} Account{'s' if count != 1 else ''} Ready")
            self.lbl_accounts_badge.setStyleSheet("""
                background: #140d24; color: #c084fc;
                border: 1px solid #7c3aed66; border-radius: 4px;
                padding: 2px 9px; font-weight: 800; font-size: 11px;
            """)
        else:
            self.lbl_accounts_badge.setText("📋 0 Accounts Ready")
            self.lbl_accounts_badge.setStyleSheet("""
                background: #080913; color: #94a3b8;
                border: 1px solid #334155; border-radius: 4px;
                padding: 2px 9px; font-weight: 800; font-size: 11px;
            """)
        if hasattr(self, 'lbl_val_remaining') and self.lbl_val_remaining:
            self.lbl_val_remaining.setText(str(count))

    def _setup_heartbeat_timer(self) -> None:
        self._check_heartbeat()
        self.timer_hb = QTimer(self)
        self.timer_hb.timeout.connect(self._check_heartbeat)
        self.timer_hb.start(1500)

    def _check_heartbeat(self) -> None:
        is_up, msg = check_srbrowser_heartbeat()
        if is_up:
            if hasattr(self, 'lbl_heartbeat'):
                self.lbl_heartbeat.setText("🟢 srkBrowser Active")
                self.lbl_heartbeat.setStyleSheet("""
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
            lic_info = get_effective_bot_license(self.bot_id)
            user_name = lic_info.get("user_name", "User")
            plan_tier = lic_info.get("plan_tier", "Enterprise Access")
            style_type = lic_info.get("style_type", "free")

            if hasattr(self, 'lbl_license') and self.lbl_license is not None:
                icon = "⭐" if "Enterprise" in plan_tier else ("👑" if "VIP" in plan_tier or "Pro" in plan_tier else "💎")
                plan_color = "#fbbf24" if "Pro" in plan_tier or "Enterprise" in plan_tier else "#c084fc"
                badge_html = f'{icon} <span style="color: {plan_color}; font-weight: 800;">{plan_tier}</span>'
                self.lbl_license.setStyleSheet("""
                    QLabel {
                        background-color: #140d24;
                        color: #c084fc;
                        border: 1px solid #7c3aed66;
                        border-radius: 5px;
                        padding: 2px 10px;
                        font-size: 11px;
                        font-weight: 800;
                    }
                """)
                self.lbl_license.setText(badge_html)
        else:
            if hasattr(self, 'lbl_heartbeat'):
                self.lbl_heartbeat.setText("🔴 srkBrowser Offline")
                self.lbl_heartbeat.setStyleSheet("""
                    QLabel {
                        background-color: #24050a;
                        color: #f87171;
                        font-size: 11px;
                        font-weight: 800;
                        border: 1px solid #ef444488;
                        border-radius: 5px;
                        padding: 2px 10px;
                    }
                """)
            if hasattr(self, 'lbl_license') and self.lbl_license is not None:
                self.lbl_license.setText('🔒 <span style="color: #ff3366; font-weight: 800;">OFFLINE</span>')
                self.lbl_license.setStyleSheet("""
                    QLabel {
                        background-color: #0d0608;
                        border: 1px solid #ff336666;
                        border-radius: 5px;
                        padding: 2px 10px;
                        font-size: 11px;
                    }
                """)

    def _append_log(self, text: str) -> None:
        self.txt_logs.append(text)
        sb = self.txt_logs.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _start_automation(self) -> None:
        is_up, _ = check_srbrowser_heartbeat()
        if not is_up:
            modal = CyberNoticeModal(
                title="⚠️ srkBrowser Offline",
                message="srkBrowser is not currently running.",
                subtext="Please launch srkBrowser first so the bot can connect and create profiles.",
                theme_color="amber",
                parent=self
            )
            modal.exec()
            return

        if not self.loaded_accounts:
            modal = CyberNoticeModal(
                title="📋 No Accounts Loaded",
                message="Please upload an Excel/CSV file or paste Facebook accounts before starting.",
                subtext="Click '📂 Choose Excel / CSV / TXT File' or '📝 Paste Accounts' above.",
                theme_color="amber",
                parent=self
            )
            modal.exec()
            return

        target_grp = self.cmb_group.currentText()
        if target_grp == "➕ Create New Group..." or not target_grp:
            target_grp = "Default"

        thread_count = self.spn_threads.value()
        stagger_val = self.spn_delay.value() if hasattr(self, 'spn_delay') else 2.0
        headless = self.chk_headless.isChecked()
        auto_lang = self.chk_auto_lang.isChecked() if hasattr(self, 'chk_auto_lang') else False

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Running (0%)...")
        self._on_stats_updated(0, 0, len(self.loaded_accounts))
        self._append_log(f"⚡ [EXECUTE] Starting Facebook Bulk Login for {len(self.loaded_accounts)} account(s) in Group '{target_grp}' ({thread_count} worker thread(s)) | Auto-Lang: {'Enabled' if auto_lang else 'Disabled'}...")

        # Instantiate dedicated FB bulk login worker thread
        self.thread = self.worker_thread_class(
            accounts_to_run=self.loaded_accounts,
            target_group=target_grp,
            profile_mgr=self.profile_mgr,
            max_concurrent_browsers=thread_count,
            headless=headless,
            bot_title=self.bot_title,
            stagger_delay_sec=stagger_val,
            auto_convert_en=auto_lang,
            parent=self
        )
        self.thread.log_emitted.connect(self._append_log)
        self.thread.progress_updated.connect(self._on_progress)
        self.thread.stats_updated.connect(self._on_stats_updated)
        self.thread.finished_signal.connect(self._on_finished)
        self.thread.start()

    def _on_stats_updated(self, success: int, failed: int, remaining: int) -> None:
        if hasattr(self, 'lbl_val_success') and self.lbl_val_success:
            self.lbl_val_success.setText(str(success))
        if hasattr(self, 'lbl_val_failed') and self.lbl_val_failed:
            self.lbl_val_failed.setText(str(failed))
        if hasattr(self, 'lbl_val_remaining') and self.lbl_val_remaining:
            self.lbl_val_remaining.setText(str(remaining))

    def _open_reports_folder(self) -> None:
        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(reports_dir.resolve()))
        except Exception:
            try:
                subprocess.Popen(["explorer", str(reports_dir.resolve())])
            except Exception:
                pass

    def _on_progress(self, current: int, total: int) -> None:
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"Progress: {current}/{total} ({pct}%)")

    def _on_finished(self, success: bool, msg: str, stats: dict) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        total = stats.get("total", 0)
        completed = stats.get("completed", 0)
        success_count = stats.get("success", 0)
        self._update_db_accounts_count()
        if success:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat(f"Completed ({completed}/{total})")
            self._append_log(f"🎉 [SUCCESS] {msg} | Total: {total} | Completed: {completed} | Succeeded: {success_count}")
        else:
            self._append_log(f"⚠️ [NOTICE] {msg} | Total: {total} | Completed: {completed} | Succeeded: {success_count}")

    def _stop_automation(self, is_manual_stop: bool = False) -> None:
        was_running = False
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            was_running = True
            self.thread.stop()
            self.thread.wait(2000)

        active_count = get_active_browser_sessions_count()

        if hasattr(self, 'btn_run') and self.btn_run:
            self.btn_run.setEnabled(True)
        if hasattr(self, 'btn_stop') and self.btn_stop:
            self.btn_stop.setEnabled(False)

        if was_running or active_count > 0 or is_manual_stop:
            self._append_log("🛑 [STOPPING] Terminating worker threads & closing active browser sessions...")
            created = getattr(self.thread, 'created_profiles', []) if hasattr(self, 'thread') and self.thread else []
            dlg = ShutdownProgressDialog(created, self)
            dlg.exec()
            self._append_log("✨ [STOPPED] All browser windows & automation tasks closed.")
        else:
            kill_all_bot_browsers()

    def _on_ipc_message(self, message: str) -> None:
        if message == "ACTIVATE_WINDOW":
            self.bring_to_front()

    def bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self._append_log("⚠️ Duplicate launch attempt prevented: Active studio window brought to focus.")

    def closeEvent(self, event) -> None:
        self._stop_automation(is_manual_stop=False)
        if hasattr(self, 'instance_guard') and self.instance_guard:
            self.instance_guard.close()
        event.accept()

    def reject(self) -> None:
        self._stop_automation(is_manual_stop=False)
        if hasattr(self, 'instance_guard') and self.instance_guard:
            self.instance_guard.close()
        super().reject()


# Backward compatibility and srkBrowser Bot Studio alias
FbBulkLoginBotDialog = MasterBotStudioDialog

_active_bot_dialogs: List[Any] = []


def launch_ui(profile_mgr: Any = None, parent: Optional[QWidget] = None, **kwargs) -> MasterBotStudioDialog:
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
        parent=parent,
        bot_id="fb_bulk_login",
        bot_title="⚡ Facebook Bulk ID Login Studio"
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


def main(profile_mgr: Any = None, parent: Optional[QWidget] = None, **kwargs):
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


__all__ = ["MasterBotStudioDialog", "FbBulkLoginBotDialog", "launch_ui", "main"]

