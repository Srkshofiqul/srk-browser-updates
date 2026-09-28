"""
Browser Profile Manager - Modern Asynchronous Bulk Progress Dialog & Workers
Provides non-blocking background workers and smooth real-time progress feedback for Bulk Create and Bulk Delete.
"""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QFrame, QWidget
)


class ModernProgressDialog(QDialog):
    """
    Ultra-modern glassmorphic progress modal with real-time percentage and status readouts.
    Prevents UI freezing and keeps users informed during heavy bulk operations.
    """

    def __init__(self, title: str = "Processing...", subtitle: str = "Please wait while operation completes...", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(460, 200)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #0f111e;
                border: 1px solid #232742;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header Title
        hdr_hbox = QHBoxLayout()
        self.lbl_icon = QLabel("⚡")
        self.lbl_icon.setStyleSheet("font-size: 20px;")
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #f1f5f9; font-size: 15px; font-weight: 800; font-family: 'Segoe UI', system-ui, sans-serif;")
        
        hdr_hbox.addWidget(self.lbl_icon)
        hdr_hbox.addWidget(self.lbl_title, stretch=1)
        layout.addLayout(hdr_hbox)

        # Dynamic Status Subtitle
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setStyleSheet("color: #94a3b8; font-size: 11.5px; font-weight: 600;")
        self.lbl_subtitle.setWordWrap(True)
        layout.addWidget(self.lbl_subtitle)

        # Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1a1d30;
                border: 1px solid #282d4a;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #38bdf8);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Bottom Info Row (Percentage | Counter Chip)
        bot_hbox = QHBoxLayout()
        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700;")
        
        self.lbl_counter = QLabel("0 / 0 (0%)")
        self.lbl_counter.setStyleSheet("color: #c084fc; font-size: 11px; font-weight: 800;")
        
        bot_hbox.addWidget(self.lbl_status, stretch=1)
        bot_hbox.addWidget(self.lbl_counter)
        layout.addLayout(bot_hbox)

    def set_progress(self, current: int, total: int, status_text: str = "") -> None:
        """Update progress bar percentage and counter text."""
        total = max(1, total)
        pct = int(min(100, (current / total) * 100))
        self.progress_bar.setValue(pct)
        self.lbl_counter.setText(f"{current} / {total} ({pct}%)")
        if status_text:
            self.lbl_status.setText(status_text)

    def set_title(self, title: str, subtitle: str = "") -> None:
        self.lbl_title.setText(title)
        if subtitle:
            self.lbl_subtitle.setText(subtitle)


class BulkCreateWorker(QThread):
    """Background QThread worker for creating profiles with live progress signals."""
    progress = Signal(int, int, str)    # current, total, profile_name
    finished = Signal(list, str)        # created_list, error_msg

    def __init__(self, profile_mgr: Any, params: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.params = params

    def run(self) -> None:
        try:
            def _cb(curr, tot, name):
                self.progress.emit(curr, tot, name)

            # Inject progress callback into bulk_create_profiles
            self.params["progress_callback"] = _cb
            created = self.profile_mgr.bulk_create_profiles(**self.params)
            self.finished.emit(created, "")
        except Exception as e:
            self.finished.emit([], str(e))


class BulkDeleteWorker(QThread):
    """Background QThread worker for deleting profiles with live progress signals."""
    progress = Signal(int, int, str)    # current, total, profile_id
    finished = Signal(int, str)         # deleted_count, error_msg

    def __init__(self, profile_mgr: Any, profile_ids: List[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profile_ids = profile_ids

    def run(self) -> None:
        try:
            def _cb(curr, tot, pid):
                self.progress.emit(curr, tot, pid)

            deleted_count = self.profile_mgr.bulk_delete_profiles(self.profile_ids, progress_callback=_cb)
            self.finished.emit(deleted_count, "")
        except Exception as e:
            self.finished.emit(0, str(e))
