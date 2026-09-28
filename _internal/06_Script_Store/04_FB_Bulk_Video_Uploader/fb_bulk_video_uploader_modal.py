"""
🎬 Facebook Bulk Video / Reel Uploader Modal (Sleek Compact Redesign)
Version: 2.5.0
Author: srkBrowser Automation Lab
Description: Ultra-cute, compact modal with dual-box multi-title & multi-description,
auto-delete for stuck uploads, and live CDP batch injection.
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QSpinBox, QCheckBox,
    QFrame, QProgressBar, QFileDialog, QMessageBox
)

# Ensure current script folder is in sys.path so sibling imports always work
curr_dir = str(Path(__file__).resolve().parent)
if curr_dir not in sys.path:
    sys.path.insert(0, curr_dir)

from fb_bulk_video_uploader_engine import scan_video_folder, execute_bulk_video_upload


class BulkVideoUploadWorker(QThread):
    event_signal = Signal(dict)

    def __init__(
        self,
        user_data_dir: str,
        video_files: List[str],
        title_template: str,
        description_text: str,
        max_count: int,
        profile_data: Optional[Dict[str, Any]] = None,
        timeout_minutes: int = 10,
        auto_delete_stuck: bool = True,
        auto_publish: bool = True
    ):
        super().__init__()
        self.user_data_dir = user_data_dir
        self.video_files = video_files
        self.title_template = title_template
        self.description_text = description_text
        self.max_count = max_count
        self.profile_data = profile_data or {}
        self.timeout_minutes = timeout_minutes
        self.auto_delete_stuck = auto_delete_stuck
        self.auto_publish = auto_publish

    def run(self):
        execute_bulk_video_upload(
            user_data_dir=self.user_data_dir,
            video_files=self.video_files,
            title_template=self.title_template,
            description_text=self.description_text,
            max_count=self.max_count,
            profile_data=self.profile_data,
            progress_cb=lambda evt: self.event_signal.emit(evt),
            timeout_minutes=self.timeout_minutes,
            auto_delete_stuck=self.auto_delete_stuck,
            auto_publish=self.auto_publish
        )


class FbBulkVideoUploaderModal(QDialog):
    """
    Cute, sleek, and compact modal for bulk video uploading to Facebook Reels.
    Features:
    - Single-click folder browse with cute animated video counter badge
    - Square dual-box for Multi-Titles (one per line) & Multi-Descriptions (separated by '---')
    - Configurable timeout and stuck video auto-delete
    - Auto-publish toggle
    """

    def __init__(self, parent=None, profile_data=None, user_data_dir=None):
        super().__init__(parent)
        self.profile_data = profile_data or {}
        self.user_data_dir = user_data_dir
        self.profile_mgr = getattr(parent, "profile_mgr", None)
        self.detected_videos = []
        self.worker = None

        if not self.profile_data and self.profile_mgr:
            try:
                profs = self.profile_mgr.get_all_profiles()
                if profs:
                    self.profile_data = profs[0]
            except Exception:
                pass

        if not self.user_data_dir and self.profile_data:
            self._resolve_user_data_dir(self.profile_data)

        p_num = str(self.profile_data.get("number") or self.profile_data.get("name") or "Profile").strip()
        self.p_num_str = p_num

        self._drag_pos = QPoint()

        self.setWindowTitle(f"Bulk Reel Uploader — {self.p_num_str}")
        self.setFixedSize(680, 500)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()

    def _resolve_user_data_dir(self, p_data: dict):
        if self.profile_mgr:
            pid = p_data.get("id") or p_data.get("number")
            if hasattr(self.profile_mgr, "get_profile_folder"):
                self.user_data_dir = str(self.profile_mgr.get_profile_folder(pid).resolve())
            elif hasattr(self.profile_mgr, "get_profile_dir"):
                self.user_data_dir = str(self.profile_mgr.get_profile_dir(pid).resolve())
        if not self.user_data_dir:
            num = p_data.get("number") or p_data.get("name") or "1"
            self.user_data_dir = str(Path.home() / "AppData" / "Local" / "srkBrowser" / "profiles" / str(num))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        self.card = QFrame()
        self.card.setObjectName("MainCard")
        self.card.setStyleSheet("""
            #MainCard {
                background: #0c0d18;
                border: 2px solid #8b5cf6;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(11)

        # 1. Header Bar
        h_head = QHBoxLayout()
        lbl_icon = QLabel("🎬")
        lbl_icon.setStyleSheet("font-size: 19px; border: none; background: transparent;")
        
        lbl_title = QLabel(f"Facebook Bulk Reel Uploader — {self.p_num_str}")
        lbl_title.setStyleSheet("""
            color: #ffffff;
            font-size: 15px;
            font-weight: 800;
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: transparent;
            border: none;
        """)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #1a1a2e;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 13px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #ef4444; color: white; border-color: #ef4444; }
        """)
        btn_close.clicked.connect(self.reject)

        h_head.addWidget(lbl_icon)
        h_head.addWidget(lbl_title)
        h_head.addStretch()
        h_head.addWidget(btn_close)
        card_layout.addLayout(h_head)

        # 2. Folder Selection Row with Cute Video Count Badge
        fld_box = QFrame()
        fld_box.setStyleSheet("background: #131428; border-radius: 9px; border: 1px solid #232545; padding: 3px;")
        h_fld = QHBoxLayout(fld_box)
        h_fld.setContentsMargins(8, 3, 8, 3)
        h_fld.setSpacing(8)

        lbl_fld_icon = QLabel("📁")
        lbl_fld_icon.setStyleSheet("font-size: 14px; border: none;")
        
        self.txt_folder = QLineEdit()
        self.txt_folder.setPlaceholderText("Select video folder (.mp4, .mov)...")
        self.txt_folder.setReadOnly(True)
        self.txt_folder.setStyleSheet("""
            QLineEdit {
                background: #080913;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
        """)

        self.lbl_badge_count = QLabel("0 Videos")
        self.lbl_badge_count.setStyleSheet("""
            background: #1e1b4b; color: #a78bfa;
            border: 1px solid #6366f1; border-radius: 8px;
            padding: 3px 10px; font-weight: 800; font-size: 11px;
        """)

        btn_browse = QPushButton("📂 Browse")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 5px 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        btn_browse.clicked.connect(self._browse_folder)

        h_fld.addWidget(lbl_fld_icon)
        h_fld.addWidget(self.txt_folder, stretch=1)
        h_fld.addWidget(self.lbl_badge_count)
        h_fld.addWidget(btn_browse)
        card_layout.addWidget(fld_box)

        # 3. Parameters & Automation Row (Compact Inline)
        ctrl_box = QFrame()
        ctrl_box.setStyleSheet("background: #131428; border-radius: 9px; border: 1px solid #232545;")
        h_ctrl = QHBoxLayout(ctrl_box)
        h_ctrl.setContentsMargins(14, 6, 14, 6)
        h_ctrl.setSpacing(14)

        lbl_cnt = QLabel("Target Videos:")
        lbl_cnt.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 700; border: none;")
        
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 50)
        self.spin_count.setValue(10)
        self.spin_count.setFixedSize(65, 26)
        self.spin_count.setStyleSheet("""
            QSpinBox {
                background: #080913;
                color: #c084fc;
                border: 1px solid #8b5cf6;
                border-radius: 5px;
                padding-left: 6px;
                font-weight: 800;
                font-size: 11px;
            }
        """)

        lbl_timeout = QLabel("Timeout:")
        lbl_timeout.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 700; border: none;")

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 60)
        self.spin_timeout.setValue(10)
        self.spin_timeout.setSuffix(" m")
        self.spin_timeout.setFixedSize(65, 26)
        self.spin_timeout.setStyleSheet("""
            QSpinBox {
                background: #080913;
                color: #fbbf24;
                border: 1px solid #f59e0b;
                border-radius: 5px;
                padding-left: 6px;
                font-weight: 800;
                font-size: 11px;
            }
        """)

        self.chk_auto_delete = QCheckBox("Auto-Delete Stuck")
        self.chk_auto_delete.setChecked(True)
        self.chk_auto_delete.setStyleSheet("QCheckBox { color: #f43f5e; font-size: 11px; font-weight: 700; border: none; }")

        self.chk_auto_publish = QCheckBox("Auto-Publish")
        self.chk_auto_publish.setChecked(True)
        self.chk_auto_publish.setStyleSheet("QCheckBox { color: #10b981; font-size: 11px; font-weight: 700; border: none; }")

        h_ctrl.addWidget(lbl_cnt)
        h_ctrl.addWidget(self.spin_count)
        h_ctrl.addSpacing(10)
        h_ctrl.addWidget(lbl_timeout)
        h_ctrl.addWidget(self.spin_timeout)
        h_ctrl.addSpacing(16)
        h_ctrl.addWidget(self.chk_auto_delete)
        h_ctrl.addSpacing(10)
        h_ctrl.addWidget(self.chk_auto_publish)
        h_ctrl.addStretch()
        card_layout.addWidget(ctrl_box)

        # 4. Cute Dual Square Boxes (Side-by-Side: Titles & Descriptions)
        h_boxes = QHBoxLayout()
        h_boxes.setSpacing(10)

        # Left Square Box: Multi-Titles
        box_titles = QFrame()
        box_titles.setStyleSheet("background: #111224; border-radius: 10px; border: 1px solid #232545; padding: 6px;")
        v_title = QVBoxLayout(box_titles)
        v_title.setContentsMargins(6, 4, 6, 4)
        v_title.setSpacing(4)

        lbl_t_header = QLabel("🏷️ Video Titles (One Per Line):")
        lbl_t_header.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700; border: none;")
        
        self.txt_title = QTextEdit()
        self.txt_title.setPlaceholderText("Enter titles (one per line):\nEpisode 1 - Viral Reel\nEpisode 2 - Tech Insights\n(Auto-rotates if fewer than videos;\nleave empty to use clean file name)")
        self.txt_title.setFixedHeight(140)
        self.txt_title.setStyleSheet("""
            QTextEdit {
                background: #080913;
                color: #ffffff;
                border: 1px solid #1e2238;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 10.5px;
                line-height: 1.3;
            }
        """)
        v_title.addWidget(lbl_t_header)
        v_title.addWidget(self.txt_title)
        h_boxes.addWidget(box_titles, stretch=1)

        # Right Square Box: Multi-Descriptions
        box_descs = QFrame()
        box_descs.setStyleSheet("background: #111224; border-radius: 10px; border: 1px solid #232545; padding: 6px;")
        v_desc = QVBoxLayout(box_descs)
        v_desc.setContentsMargins(6, 4, 6, 4)
        v_desc.setSpacing(4)

        lbl_d_header = QLabel("✍️ Descriptions (Separate with '---'):")
        lbl_d_header.setStyleSheet("color: #c084fc; font-size: 11px; font-weight: 700; border: none;")

        self.txt_desc = QTextEdit()
        self.txt_desc.setPlaceholderText("Enter captions & hashtags.\nTo set different captions, separate with '---':\nCaption 1 #viral #trending\n---\nCaption 2 #tech #reels")
        self.txt_desc.setFixedHeight(140)
        self.txt_desc.setStyleSheet("""
            QTextEdit {
                background: #080913;
                color: #ffffff;
                border: 1px solid #1e2238;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 10.5px;
                line-height: 1.3;
            }
        """)
        v_desc.addWidget(lbl_d_header)
        v_desc.addWidget(self.txt_desc)
        h_boxes.addWidget(box_descs, stretch=1)

        card_layout.addLayout(h_boxes)

        # 5. Status & Progress Bar
        self.lbl_status = QLabel("Ready. Select video folder to begin.")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 10.5px; font-weight: 600; border: none;")
        card_layout.addWidget(self.lbl_status)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setFixedHeight(3)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setVisible(False)
        self.prog_bar.setStyleSheet("""
            QProgressBar { background: #13122c; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #38bdf8); }
        """)
        card_layout.addWidget(self.prog_bar)

        # 6. Action Footer
        h_foot = QHBoxLayout()
        self.btn_start = QPushButton("🚀 Start Bulk Video Upload")
        self.btn_start.setEnabled(False)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a78bfa, stop:1 #60a5fa);
            }
            QPushButton:disabled { background: #1f2238; color: #475569; }
        """)
        self.btn_start.clicked.connect(self._start_upload)

        btn_exit = QPushButton("Exit ✕")
        btn_exit.setCursor(Qt.PointingHandCursor)
        btn_exit.setStyleSheet("""
            QPushButton {
                background: #1a1a2e;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover { background: #262640; color: white; border-color: #475569; }
        """)
        btn_exit.clicked.connect(self.accept)

        h_foot.addWidget(self.btn_start, stretch=1)
        h_foot.addWidget(btn_exit)
        card_layout.addLayout(h_foot)

        root.addWidget(self.card)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing Videos")
        if folder:
            self.txt_folder.setText(folder)
            self.detected_videos = scan_video_folder(folder)
            total = len(self.detected_videos)

            if total > 0:
                self.lbl_badge_count.setText(f"🎬 {total} Videos")
                self.lbl_badge_count.setStyleSheet("""
                    background: #064e3b; color: #34d399;
                    border: 1px solid #059669; border-radius: 8px;
                    padding: 3px 10px; font-weight: 800; font-size: 11px;
                """)
                self.spin_count.setMaximum(total)
                self.spin_count.setValue(min(total, 10))
                self.btn_start.setEnabled(True)
                self.lbl_status.setText(f"✅ Found {total} video(s). Ready to upload.")
                self.lbl_status.setStyleSheet("color: #4ade80; font-size: 10.5px; font-weight: 700; border: none;")
            else:
                self.lbl_badge_count.setText("0 Videos")
                self.lbl_badge_count.setStyleSheet("""
                    background: #4c0519; color: #fb7185;
                    border: 1px solid #e11d48; border-radius: 8px;
                    padding: 3px 10px; font-weight: 800; font-size: 11px;
                """)
                self.btn_start.setEnabled(False)
                self.lbl_status.setText("⚠️ No supported video files (.mp4, .mov, etc.) found in selected folder.")
                self.lbl_status.setStyleSheet("color: #fb7185; font-size: 10.5px; font-weight: 700; border: none;")

    def _start_upload(self):
        if not self.detected_videos:
            return

        self.btn_start.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.btn_start.setText("Uploading Videos... ⏳")

        max_n = self.spin_count.value()
        t_template = self.txt_title.toPlainText().strip()
        desc = self.txt_desc.toPlainText().strip()

        timeout_min = self.spin_timeout.value()
        auto_del = self.chk_auto_delete.isChecked()
        auto_pub = self.chk_auto_publish.isChecked()

        self.worker = BulkVideoUploadWorker(
            user_data_dir=self.user_data_dir,
            video_files=self.detected_videos,
            title_template=t_template,
            description_text=desc,
            max_count=max_n,
            profile_data=self.profile_data,
            timeout_minutes=timeout_min,
            auto_delete_stuck=auto_del,
            auto_publish=auto_pub
        )
        self.worker.event_signal.connect(self._handle_event)
        self.worker.start()

    def _handle_event(self, evt: dict):
        evt_type = evt.get("type")
        msg = evt.get("message", "")

        if evt_type in ("status", "video_success"):
            if msg:
                self.lbl_status.setText(msg)
                self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 10.5px; font-weight: 600; border: none;")

        elif evt_type == "done":
            self.prog_bar.setVisible(False)
            self.btn_start.setText("Uploaded & Published! 🎉")
            self.btn_start.setEnabled(True)
            self.lbl_status.setText(msg or "🎉 Bulk upload & publishing complete!")
            self.lbl_status.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 800; border: none;")
            QMessageBox.information(self, "Upload Complete", msg or "All videos uploaded & configured successfully!")

        elif evt_type == "error":
            self.prog_bar.setVisible(False)
            self.btn_start.setText("Upload Failed ✕")
            self.btn_start.setEnabled(True)
            self.lbl_status.setText(msg or "Error during bulk upload.")
            self.lbl_status.setStyleSheet("color: #ef4444; font-size: 10.5px; font-weight: 700; border: none;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos") and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
        event.accept()


_active_dialogs = []


def launch_ui(profile_mgr=None, parent=None, profile_data=None, user_data_dir="", **kwargs) -> bool:
    """Entry point invoked by srkBrowser MainWindow to launch the non-modal, non-blocking dialog."""
    dlg = FbBulkVideoUploaderModal(parent=parent, profile_data=profile_data, user_data_dir=user_data_dir)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    _active_dialogs.append(dlg)
    dlg.finished.connect(lambda: _active_dialogs.remove(dlg) if dlg in _active_dialogs else None)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return True


def open_modal(parent=None, profile_data=None, user_data_dir=None, **kwargs):
    return launch_ui(parent=parent, profile_data=profile_data, user_data_dir=user_data_dir, **kwargs)


def main(profile_mgr=None, parent=None, profile_data=None, user_data_dir="", **kwargs):
    return launch_ui(profile_mgr=profile_mgr, parent=parent, profile_data=profile_data, user_data_dir=user_data_dir, **kwargs)


__all__ = ["FbBulkVideoUploaderModal", "launch_ui", "main", "open_modal"]


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    launch_ui(profile_data={"number": "540", "name": "Profile 540"})
    sys.exit(0)


