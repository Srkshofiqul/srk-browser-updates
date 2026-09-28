"""
Browser Profile Manager - Graceful Exit Cloud Sync Dialog
Python 3.13 / PySide6 Desktop Application
Developer: Srk Shofiqul (sritzone.com)
"""

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QFrame, QWidget
)

try:
    from core.cloud_sync import sync_tracker
except ImportError:
    try:
        from cloud_sync import sync_tracker
    except ImportError:
        sync_tracker = None


class ExitSyncDialog(QDialog):
    """
    Graceful Exit Synchronization Barrier Dialog.
    Displays live cloud sync progress (profile purges & session ZIP uploads)
    upon application exit, ensuring 100% data integrity before closing.
    """
    def __init__(self, max_timeout_sec: float = 8.0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.max_timeout_sec = max_timeout_sec
        self.start_time = time.time()
        self._is_forced_exit = False

        self.setWindowTitle("srkBrowser Cloud Sync")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(460, 210)

        self._init_ui()

        # Center on parent or screen
        if parent:
            geo = parent.geometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2
            )

        # Polling timer to monitor sync status
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(120)
        self.poll_timer.timeout.connect(self._check_sync_status)
        self.poll_timer.start()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Container card
        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 14px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        # Header Title with Icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        self.icon_lbl = QLabel("☁️", self.card)
        self.icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")

        self.title_lbl = QLabel("Synchronizing with srkBrowser Cloud...", self.card)
        self.title_lbl.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: bold;
                color: #cdd6f4;
                background: transparent;
                border: none;
            }
        """)
        header_layout.addWidget(self.icon_lbl)
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        # Status text
        self.status_lbl = QLabel("Saving login sessions and cloud changes. Please wait...", self.card)
        self.status_lbl.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #a6adc8;
                background: transparent;
                border: none;
            }
        """)
        card_layout.addWidget(self.status_lbl)

        # Progress bar
        self.progress_bar = QProgressBar(self.card)
        self.progress_bar.setRange(0, 0)  # Indeterminate pulsating bar
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #11111b;
                border: 1px solid #313244;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #89b4fa, stop:0.5 #cba6f7, stop:1 #b4befe);
                border-radius: 4px;
            }
        """)
        card_layout.addWidget(self.progress_bar)

        # Footer action buttons
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.btn_exit_now = QPushButton("Exit Immediately", self.card)
        self.btn_exit_now.setCursor(Qt.PointingHandCursor)
        self.btn_exit_now.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #45475a;
                color: #ffffff;
                border-color: #585b70;
            }
            QPushButton:pressed {
                background-color: #1e1e2e;
            }
        """)
        self.btn_exit_now.clicked.connect(self._on_force_exit)
        footer_layout.addWidget(self.btn_exit_now)

        card_layout.addLayout(footer_layout)
        main_layout.addWidget(self.card)

    def _check_sync_status(self) -> None:
        """Poll the sync tracker. Auto-close cleanly once all tasks settle."""
        elapsed = time.time() - self.start_time

        if sync_tracker:
            is_busy = sync_tracker.is_busy()
            if not is_busy:
                self.poll_timer.stop()
                self.accept()
                return

            summary = sync_tracker.get_summary_text()
            if summary and summary != "All synced":
                self.status_lbl.setText(f"☁️ {summary}... Please wait.")

        # Timeout guard: Never hang indefinitely if network is unreachable
        if elapsed >= self.max_timeout_sec:
            if sync_tracker:
                sync_tracker.save_offline_queue()
            self.poll_timer.stop()
            self.accept()

    def _on_force_exit(self) -> None:
        """User chose to exit now; persist pending tasks to offline queue."""
        self._is_forced_exit = True
        self.poll_timer.stop()
        if sync_tracker:
            sync_tracker.save_offline_queue()
        self.reject()
