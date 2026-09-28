# -*- coding: utf-8 -*-
"""
🎬 Facebook Bulk Video / Reel Uploader Bot (Ultra-Compact Clean Redesign)
Version: 1.2.0
Author: srkBrowser Automation Lab
Description: Ultra-clean, compact, elegant bot dialog with zero dead space,
clear segmented toggle buttons, visible checkboxes, and proportional layout.
"""

import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, QPoint, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
    QSpinBox, QCheckBox, QButtonGroup, QFrame, QProgressBar,
    QFileDialog, QMessageBox, QSizePolicy, QMenu
)

from fb_bulk_uploader_bot_helpers import (
    scan_video_folder, load_lines_from_txt_file, load_descriptions_from_txt_file, parse_raw_text_lines,
    parse_description_chunks, filter_profiles_by_target,
    fetch_cloud_uploader_templates, apply_user_links_to_descriptions,
    get_cloud_video_vault_dir, fetch_cloud_videos_manifest, sync_cloud_video_vault,
    get_default_titles_file_path, get_default_descriptions_file_path
)
from fb_bulk_uploader_bot_engine import BulkVideoUploaderMasterThread


class CloudVaultSyncWorkerThread(QThread):
    """Background worker thread to sync cloud videos without blocking the GUI."""
    progress_signal = Signal(str, int, int)
    finished_signal = Signal(list)
    error_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            def cb(msg, cur, tot):
                if not self._is_cancelled:
                    self.progress_signal.emit(msg, cur, tot)

            paths = sync_cloud_video_vault(progress_callback=cb)
            if not self._is_cancelled:
                self.finished_signal.emit(paths)
        except Exception as ex:
            if not self._is_cancelled:
                self.error_signal.emit(str(ex))


class CloudVaultSyncModalDialog(QDialog):
    """
    Sleek, Cyberpunk Modal Progress Dialog for Cloud Video Vault Synchronization:
    - Runs download on a dedicated background QThread so the UI never hangs.
    - Completely locks main window interactions during sync.
    - Closes automatically when all videos are ready.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setWindowTitle("☁️ Synchronizing Cloud Video Vault")
        self.setFixedSize(520, 210)
        self.result_paths: List[Path] = []
        self.error_msg: Optional[str] = None

        self.setStyleSheet("""
            QDialog {
                background-color: #0b071a;
                color: #f8fafc;
                border: 2px solid #7c3aed;
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)

        # Header with Icon & Titles
        h_head = QHBoxLayout()
        h_head.setSpacing(14)
        lbl_icon = QLabel("☁️")
        lbl_icon.setStyleSheet("font-size: 32px;")
        h_head.addWidget(lbl_icon)

        v_text = QVBoxLayout()
        v_text.setSpacing(3)
        lbl_title = QLabel("Cloud Video Vault Synchronization")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #ffffff;")
        lbl_sub = QLabel("Smart Differential Caching: syncing new/missing viral reels into hidden vault.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #a78bfa;")
        v_text.addWidget(lbl_title)
        v_text.addWidget(lbl_sub)
        h_head.addLayout(v_text, stretch=1)
        layout.addLayout(h_head)

        # Progress Bar
        self.bar = QProgressBar()
        self.bar.setFixedHeight(12)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet("""
            QProgressBar {
                background-color: #1a103c;
                border: 1px solid #7c3aed44;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:0.5 #ec4899, stop:1 #3b82f6);
                border-radius: 5px;
            }
        """)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        # Status & Counts Row
        h_status = QHBoxLayout()
        self.lbl_status = QLabel("Connecting to central vault...")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #94a3b8; font-family: monospace;")
        self.lbl_count = QLabel("0 / 0 (0%)")
        self.lbl_count.setStyleSheet("font-size: 11px; font-weight: bold; color: #c084fc; font-family: monospace;")
        h_status.addWidget(self.lbl_status, stretch=1)
        h_status.addWidget(self.lbl_count)
        layout.addLayout(h_status)

        # Bottom Row: Hint & Cancel
        h_bot = QHBoxLayout()
        lbl_hint = QLabel("⚡ Videos are saved in internal stealth cache and reuse instantly (0s) on future runs.")
        lbl_hint.setStyleSheet("font-size: 10px; color: #64748b; font-style: italic;")
        h_bot.addWidget(lbl_hint, stretch=1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #1e153b;
                color: #f87171;
                border: 1px solid #ef444455;
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #451a24;
                color: #ffffff;
            }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel)
        h_bot.addWidget(self.btn_cancel)
        layout.addLayout(h_bot)

        # Worker Thread Setup
        self.worker = CloudVaultSyncWorkerThread(self)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)

    def start_sync(self):
        self.worker.start()

    def _on_progress(self, msg: str, cur: int, tot: int):
        self.lbl_status.setText(msg)
        if tot > 0:
            pct = int((cur / tot) * 100)
            self.bar.setValue(pct)
            self.lbl_count.setText(f"{cur} / {tot} ({pct}%)")

    def _on_finished(self, paths: List[Path]):
        self.result_paths = paths
        self.accept()

    def _on_error(self, err: str):
        self.error_msg = err
        self.reject()

    def _on_cancel(self):
        self.worker.cancel()
        self.reject()

    def closeEvent(self, event):
        self.worker.cancel()
        super().closeEvent(event)


class CloudDescriptionLinksModal(QDialog):
    """
    Cyber-styled, premium modal dialog for entering line-by-line links
    to replace {{link}} in cloud default descriptions.
    """
    def __init__(self, initial_links: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🔗 Configure Target Links")
        self.setFixedSize(460, 310)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = QPoint()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        card = QFrame()
        card.setObjectName("LinksCard")
        card.setStyleSheet("""
            QFrame#LinksCard {
                background-color: #0b0818;
                border: 1.5px solid #7c3aed;
                border-radius: 12px;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel { background: transparent; }
        """)
        root_layout.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header bar with Icon, Title, Badge & Close Button
        h_head = QHBoxLayout()
        h_head.setSpacing(8)

        lbl_icon = QLabel("🔗")
        lbl_icon.setStyleSheet("font-size: 16px; border: none; background: transparent;")

        v_titles = QVBoxLayout()
        v_titles.setSpacing(1)
        lbl_title = QLabel("Target Links for {{link}}")
        lbl_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #c084fc; letter-spacing: 0.3px; border: none;")
        lbl_sub = QLabel("Auto-injected into {{link}} per video (1 link per line)")
        lbl_sub.setStyleSheet("font-size: 10px; color: #94a3b8; border: none;")
        v_titles.addWidget(lbl_title)
        v_titles.addWidget(lbl_sub)

        self.lbl_count_badge = QLabel("0 Links")
        self.lbl_count_badge.setStyleSheet("""
            background: #1e1b4b; color: #c084fc;
            border: 1px solid #7c3aed66; border-radius: 4px;
            padding: 2px 8px; font-weight: 800; font-size: 10.5px;
        """)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #94a3b8;
                border: 1px solid #2b1e4a;
                border-radius: 11px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #ef4444; color: white; border-color: #ef4444; }
        """)
        btn_close.clicked.connect(self.reject)

        h_head.addWidget(lbl_icon)
        h_head.addLayout(v_titles, stretch=1)
        h_head.addWidget(self.lbl_count_badge)
        h_head.addWidget(btn_close)
        layout.addLayout(h_head)

        # Text input area
        self.txt_links = QPlainTextEdit()
        self.txt_links.setPlaceholderText(
            "Paste your links here (1 link per line):\n"
            "https://example.com/link1  -> Video 1\n"
            "https://example.com/link2  -> Video 2\n"
            "https://example.com/link3  -> Video 3..."
        )
        self.txt_links.setStyleSheet("""
            QPlainTextEdit {
                background: #101226;
                color: #f8fafc;
                border: 1px solid #281d4a;
                border-radius: 6px;
                padding: 6px 8px;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 11px;
                line-height: 1.35;
            }
            QPlainTextEdit:focus {
                border-color: #8b5cf6;
                background: #141733;
            }
            QScrollBar:vertical {
                background: #0b0818; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #7c3aed66; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a78bfa;
            }
        """)
        self.txt_links.textChanged.connect(self._update_counter)
        if initial_links:
            self.txt_links.setPlainText(initial_links)
        self._update_counter()
        layout.addWidget(self.txt_links, stretch=1)

        # Bottom actions: Cancel & Save
        h_act = QHBoxLayout()
        h_act.setSpacing(8)

        btn_cancel = QPushButton("✖ Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #141224;
                color: #94a3b8;
                border: 1px solid #2b1e4a;
                border-radius: 5px;
                padding: 4px 16px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background: #1f1a3a; color: #f1f5f9; }
        """)
        btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("💾 Save && Apply")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(28)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                border: 1px solid #8b5cf6;
                border-radius: 5px;
                padding: 4px 20px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
            }
        """)
        self.btn_save.clicked.connect(self.accept)

        h_act.addStretch()
        h_act.addWidget(btn_cancel)
        h_act.addWidget(self.btn_save)
        layout.addLayout(h_act)

        # Drag support
        card.mousePressEvent = self.mousePressEvent
        card.mouseMoveEvent = self.mouseMoveEvent
        card.mouseReleaseEvent = self.mouseReleaseEvent

    def _update_counter(self) -> None:
        lines = [l.strip() for l in self.txt_links.toPlainText().splitlines() if l.strip()]
        self.lbl_count_badge.setText(f"{len(lines)} Links")

    def get_links_text(self) -> str:
        return self.txt_links.toPlainText().strip()

    def get_links_list(self) -> List[str]:
        return [l.strip() for l in self.txt_links.toPlainText().splitlines() if l.strip()]

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


class FbBulkVideoUploaderBotDialog(QDialog):
    """
    Sleek, Compact, and Elegant Multi-Threaded Facebook Bulk Video / Reel Uploader Bot.
    """

    def __init__(self, profile_mgr: Any = None, parent: Optional[QWidget] = None, *args, **kwargs):
        # Flexible parent / profile_mgr detection (supports any order or keyword arguments)
        actual_parent = None
        actual_mgr = None
        for arg in (profile_mgr, parent, *args):
            if isinstance(arg, QWidget):
                actual_parent = arg
            elif arg is not None and (hasattr(arg, 'get_all_profiles') or hasattr(arg, 'profiles') or hasattr(arg, 'data_dir')):
                actual_mgr = arg
        
        if actual_mgr is None and profile_mgr is not None and not isinstance(profile_mgr, QWidget):
            actual_mgr = profile_mgr

        super().__init__(actual_parent)
        self.profile_mgr = actual_mgr
        self.reports_dir = Path(__file__).resolve().parent / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self._drag_pos = QPoint()
        self.master_thread: Optional[BulkVideoUploaderMasterThread] = None

        # Data states
        self.all_profiles: List[Dict[str, Any]] = []
        if self.profile_mgr and hasattr(self.profile_mgr, "get_all_profiles"):
            self.all_profiles = self.profile_mgr.get_all_profiles()

        self.loaded_video_files: List[Path] = []
        self.titles_from_txt: List[str] = []
        self.descs_from_txt: List[str] = []
        self.video_source: str = "none"   # "local" or "cloud"
        self.titles_source: str = "none"  # "local" or "cloud"
        self.descs_source: str = "none"   # "local" or "cloud"
        self.custom_user_links: List[str] = []
        self.current_theme = "page_creator"

        self._init_window()
        self._init_ui()
        self._refresh_target_profiles_count()
        self.apply_theme("page_creator")
        self._check_srbrowser_heartbeat()
        self.timer_hb = QTimer(self)
        self.timer_hb.timeout.connect(self._check_srbrowser_heartbeat)
        self.timer_hb.start(3000)

    def _init_window(self):
        self.setFixedSize(700, 495)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Facebook Bulk Video / Reel Uploader Bot")

    def _init_ui(self):
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
        card_layout.setSpacing(4)

        # -------------------------------------------------------------
        # 1. HEADER BAR (Ultra-clean Cyber Deck)
        # -------------------------------------------------------------
        h_head = QHBoxLayout()
        h_head.setContentsMargins(0, 0, 0, 0)
        h_head.setSpacing(8)

        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 16px; border: none; background: transparent; color: #f43f5e;")

        self.lbl_title = QLabel("Facebook Bulk Video / Reel Uploader Bot")
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

        # Live srkBrowser Core Active Status Badge (Placed on the right side next to close button)
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

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #94a3b8;
                border: 1px solid #2b1e4a;
                border-radius: 13px;
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
        # 2. TARGET PROFILES & CONCURRENCY BOX (Compact & Balanced)
        # -------------------------------------------------------------
        self.target_box = QFrame()
        self.target_box.setFixedHeight(72)
        self.target_box.setStyleSheet("background: #131428; border-radius: 8px; border: 1px solid #232545;")
        v_target = QVBoxLayout(self.target_box)
        v_target.setContentsMargins(8, 5, 8, 5)
        v_target.setSpacing(5)

        # Row A: Segmented Mode Selector [ Group | Numbers ] + Input + Page Mode + Count Badge
        h_tgt_row = QHBoxLayout()
        h_tgt_row.setSpacing(6)

        # Clear segmented buttons for Group vs Numbers
        self.btn_seg_group = QPushButton("📁 Group")
        self.btn_seg_group.setCheckable(True)
        self.btn_seg_group.setChecked(True)
        self.btn_seg_group.setFixedHeight(26)
        self.btn_seg_group.setFixedWidth(74)
        self.btn_seg_group.setCursor(Qt.PointingHandCursor)

        self.btn_seg_numbers = QPushButton("🔢 Numbers")
        self.btn_seg_numbers.setCheckable(True)
        self.btn_seg_numbers.setFixedHeight(26)
        self.btn_seg_numbers.setFixedWidth(88)
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
                background: #080913;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 1px 8px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QComboBox QAbstractItemView {
                background-color: #10121e;
                color: #ffffff;
                selection-background-color: #8b5cf6;
            }
        """)
        groups_list = ["All Profiles"]
        if self.profile_mgr and hasattr(self.profile_mgr, "get_groups"):
            groups_list.extend(self.profile_mgr.get_groups())
        self.combo_groups.addItems(groups_list)
        self.combo_groups.currentIndexChanged.connect(self._refresh_target_profiles_count)
        h_tgt_row.addWidget(self.combo_groups, stretch=1)

        # Profile Numbers Input
        self.txt_profile_numbers = QLineEdit()
        self.txt_profile_numbers.setFixedHeight(26)
        self.txt_profile_numbers.setPlaceholderText("e.g. 500-510, 520, 538-540")
        self.txt_profile_numbers.setStyleSheet("""
            QLineEdit {
                background: #080913;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QLineEdit:focus { border-color: #8b5cf6; }
        """)
        self.txt_profile_numbers.textChanged.connect(self._refresh_target_profiles_count)
        self.txt_profile_numbers.setVisible(False)
        h_tgt_row.addWidget(self.txt_profile_numbers, stretch=1)

        # Page Mode Dropdown
        lbl_page_mode = QLabel("Page Mode:")
        lbl_page_mode.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        self.combo_page_mode = QComboBox()
        self.combo_page_mode.setFixedHeight(26)
        self.combo_page_mode.addItems(["Selected Page", "Fallback on Fail", "All Pages"])
        self.combo_page_mode.setToolTip("Multi-page strategy:\n• Selected Page: Only post to active page\n• Fallback on Fail: Try next page if first fails\n• All Pages: Post to all pages on account")
        self.combo_page_mode.setFixedWidth(106)
        self.combo_page_mode.setStyleSheet("""
            QComboBox {
                background: #080913;
                color: #67e8f9;
                border: 1px solid #0891b2;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QComboBox:focus { border-color: #22d3ee; }
            QComboBox QAbstractItemView {
                background-color: #10121e;
                color: #ffffff;
                selection-background-color: #0891b2;
            }
        """)
        h_tgt_row.addWidget(lbl_page_mode)
        h_tgt_row.addWidget(self.combo_page_mode)

        self.lbl_target_count_badge = QLabel("🎯 0 Profiles")
        self.lbl_target_count_badge.setFixedHeight(26)
        self.lbl_target_count_badge.setStyleSheet("""
            background: #1e1b4b; color: #a78bfa;
            border: 1px solid #6366f1; border-radius: 5px;
            padding: 2px 8px; font-weight: 800; font-size: 11px;
        """)
        h_tgt_row.addWidget(self.lbl_target_count_badge, 0, Qt.AlignVCenter)
        v_target.addLayout(h_tgt_row)

        # Row B: Concurrency, Stagger & Checkboxes
        h_param_row = QHBoxLayout()
        h_param_row.setSpacing(4)

        lbl_th = QLabel("Threads:")
        lbl_th.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 50)
        self.spin_threads.setValue(3)
        self._style_spinbox(self.spin_threads, 24, 40)

        lbl_st = QLabel("Stagger:")
        lbl_st.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        self.spin_stagger = QSpinBox()
        self.spin_stagger.setRange(1, 60)
        self.spin_stagger.setValue(3)
        self.spin_stagger.setSuffix("s")
        self.spin_stagger.setToolTip("Stagger interval between profile launches (seconds) with randomized human jitter.")
        self._style_spinbox(self.spin_stagger, 24, 44)

        lbl_vp = QLabel("Vids/ID:")
        lbl_vp.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        self.spin_vpp = QSpinBox()
        self.spin_vpp.setRange(1, 100)
        self.spin_vpp.setValue(10)
        self._style_spinbox(self.spin_vpp, 24, 42)

        lbl_to = QLabel("Timeout:")
        lbl_to.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 60)
        self.spin_timeout.setValue(10)
        self.spin_timeout.setSuffix("m")
        self.spin_timeout.setToolTip("Maximum minutes to wait for video to upload and publish before timeout")
        self._style_spinbox(self.spin_timeout, 24, 44)

        lbl_fail_prof = QLabel("Fail:")
        lbl_fail_prof.setStyleSheet("color: #f87171; font-weight: 700; font-size: 11px;")
        self.combo_fail_group = QComboBox()
        self.combo_fail_group.setFixedHeight(24)
        self.combo_fail_group.setFixedWidth(75)
        self.combo_fail_group.setStyleSheet("""
            QComboBox {
                background: #080913;
                color: #fca5a5;
                border: 1px solid #7f1d1d;
                border-radius: 4px;
                padding: 1px 4px;
                font-size: 11px;
                font-weight: 700;
            }
            QComboBox:focus { border-color: #ef4444; }
            QComboBox QAbstractItemView {
                background-color: #10121e;
                color: #ffffff;
                selection-background-color: #dc2626;
            }
        """)
        fail_groups = ["None"]
        if self.profile_mgr and hasattr(self.profile_mgr, "get_groups"):
            for g in self.profile_mgr.get_groups():
                if g and g not in fail_groups:
                    fail_groups.append(g)
        self.combo_fail_group.addItems(fail_groups)
        self.combo_fail_group.setToolTip("Auto-move failed profiles to this group in srkBrowser")

        self.chk_headless = QCheckBox("Headless")
        self.chk_headless.setObjectName("chkHeadless")
        self.chk_headless.setCursor(Qt.PointingHandCursor)
        self.chk_headless.setFixedHeight(24)
        self.chk_headless.setFixedWidth(80)
        self.chk_headless.setStyleSheet("font-size: 11px; font-weight: 700; color: #cbd5e1; margin-left: 2px;")

        h_param_row.addWidget(lbl_th)
        h_param_row.addWidget(self.spin_threads)
        h_param_row.addSpacing(2)
        h_param_row.addWidget(lbl_st)
        h_param_row.addWidget(self.spin_stagger)
        h_param_row.addSpacing(2)
        h_param_row.addWidget(lbl_vp)
        h_param_row.addWidget(self.spin_vpp)
        h_param_row.addSpacing(2)
        h_param_row.addWidget(lbl_to)
        h_param_row.addWidget(self.spin_timeout)
        h_param_row.addSpacing(4)
        h_param_row.addWidget(lbl_fail_prof)
        h_param_row.addWidget(self.combo_fail_group)
        h_param_row.addStretch()
        h_param_row.addWidget(self.chk_headless)

        v_target.addLayout(h_param_row)
        card_layout.addWidget(self.target_box)

        # -------------------------------------------------------------
        # 3. UNIFIED 3-IN-1 FILE & FOLDER ROW (VIDEOS, TITLES, DESCRIPTIONS)
        # -------------------------------------------------------------
        self.files_box = QFrame()
        self.files_box.setFixedHeight(38)
        self.files_box.setStyleSheet("background: #111224; border-radius: 8px; border: 1px solid #232545;")
        h_files = QHBoxLayout(self.files_box)
        h_files.setContentsMargins(8, 4, 8, 4)
        h_files.setSpacing(8)

        # 1. Video Folder (Button + Badge)
        h_fld = QHBoxLayout()
        h_fld.setSpacing(5)
        self.btn_pick_videos = QPushButton("📁 Videos ▾")
        self.btn_pick_videos.setCursor(Qt.PointingHandCursor)
        self.btn_pick_videos.setFixedHeight(26)
        self.btn_pick_videos.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
            }
        """)
        self.btn_pick_videos.setToolTip("Click to select: Local PC (Folder) or Cloud Server Vault")
        self.btn_pick_videos.clicked.connect(self._on_click_videos_source)
        h_fld.addWidget(self.btn_pick_videos, stretch=1)

        self.lbl_badge_count = QLabel("0 Videos")
        self.lbl_badge_count.setFixedHeight(24)
        self.lbl_badge_count.setStyleSheet("""
            background: #140d24; color: #c084fc;
            border: 1px solid #7c3aed66; border-radius: 4px;
            padding: 1px 6px; font-weight: 800; font-size: 11px;
        """)
        h_fld.addWidget(self.lbl_badge_count)
        h_files.addLayout(h_fld, stretch=1)

        # Separator 1
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #231b42;")
        h_files.addWidget(sep1)

        # 2. Titles File (Button + Badge)
        h_tfile = QHBoxLayout()
        h_tfile.setSpacing(5)
        self.btn_pick_titles = QPushButton("📄 Titles ▾")
        self.btn_pick_titles.setCursor(Qt.PointingHandCursor)
        self.btn_pick_titles.setFixedHeight(26)
        self.btn_pick_titles.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover { background: #261b45; color: #ffffff; }
        """)
        self.btn_pick_titles.setToolTip("Click to select: Local PC (.txt) or Cloud Server Default")
        self.btn_pick_titles.clicked.connect(self._on_click_titles_source)
        h_tfile.addWidget(self.btn_pick_titles, stretch=1)

        self.lbl_titles_count_badge = QLabel("0 Lines")
        self.lbl_titles_count_badge.setFixedHeight(24)
        self.lbl_titles_count_badge.setStyleSheet("""
            background: #082f49; color: #38bdf8;
            border: 1px solid #0284c7; border-radius: 4px;
            padding: 1px 6px; font-weight: 800; font-size: 11px;
        """)
        h_tfile.addWidget(self.lbl_titles_count_badge)
        h_files.addLayout(h_tfile, stretch=1)

        # Separator 2
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #231b42;")
        h_files.addWidget(sep2)

        # 3. Descriptions File (Button + Badge)
        h_dfile = QHBoxLayout()
        h_dfile.setSpacing(5)
        self.btn_pick_descs = QPushButton("📄 Descs ▾")
        self.btn_pick_descs.setCursor(Qt.PointingHandCursor)
        self.btn_pick_descs.setFixedHeight(26)
        self.btn_pick_descs.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #c084fc;
                border: 1px solid #7c3aed;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover { background: #261b45; color: #ffffff; }
        """)
        self.btn_pick_descs.setToolTip("Click to select: Local PC (.txt) or Cloud Server Default")
        self.btn_pick_descs.clicked.connect(self._on_click_descs_source)
        h_dfile.addWidget(self.btn_pick_descs, stretch=1)

        self.lbl_descs_count_badge = QLabel("0 Lines")
        self.lbl_descs_count_badge.setFixedHeight(24)
        self.lbl_descs_count_badge.setStyleSheet("""
            background: #2e1065; color: #c084fc;
            border: 1px solid #7c3aed; border-radius: 4px;
            padding: 1px 6px; font-weight: 800; font-size: 11px;
        """)
        h_dfile.addWidget(self.lbl_descs_count_badge)
        h_files.addLayout(h_dfile, stretch=1)

        # Hidden dummy labels to maintain backward compatibility:
        self.lbl_folder_status = QLabel("No folder selected")
        self.lbl_folder_status.setVisible(False)
        self.lbl_titles_txt_status = QLabel("No file selected")
        self.lbl_titles_txt_status.setVisible(False)
        self.lbl_descs_txt_status = QLabel("No file selected")
        self.lbl_descs_txt_status.setVisible(False)

        card_layout.addWidget(self.files_box)

        # Hidden dummy objects to maintain backward compatibility:
        self.txt_custom_link = QPlainTextEdit()
        self.lbl_link_count_badge = QLabel("0 Links")
        self.custom_link_box = QFrame()
        self.custom_link_box.setVisible(False)

        # -------------------------------------------------------------
        # 4. METRICS DECK (3 Glowing Metric Cards matching Bot #2)
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

        self.lbl_metric_succ_num = QLabel("0")
        self.lbl_metric_succ_num.setStyleSheet("color: #10b981; font-weight: 900; font-size: 20px; border: none; background: transparent;")
        v_cs.addWidget(self.lbl_metric_succ_num)

        self.lbl_metric_succ_sub = QLabel("IDs / Profiles Uploaded")
        self.lbl_metric_succ_sub.setStyleSheet("color: #059669; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cs.addWidget(self.lbl_metric_succ_sub)
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

        self.lbl_metric_fail_num = QLabel("0")
        self.lbl_metric_fail_num.setStyleSheet("color: #ef4444; font-weight: 900; font-size: 20px; border: none; background: transparent;")
        v_cf.addWidget(self.lbl_metric_fail_num)

        self.lbl_metric_fail_sub = QLabel("Failed IDs / Errors")
        self.lbl_metric_fail_sub.setStyleSheet("color: #b91c1c; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cf.addWidget(self.lbl_metric_fail_sub)
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

        self.lbl_metric_rem_num = QLabel("0")
        self.lbl_metric_rem_num.setStyleSheet("color: #0ea5e9; font-weight: 900; font-size: 20px; border: none; background: transparent;")
        v_cr.addWidget(self.lbl_metric_rem_num)

        self.lbl_metric_rem_sub = QLabel("Queued IDs In Target")
        self.lbl_metric_rem_sub.setStyleSheet("color: #0284c7; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
        v_cr.addWidget(self.lbl_metric_rem_sub)
        h_metrics.addWidget(self.card_rem, stretch=1)

        card_layout.addLayout(h_metrics)

        # Cyberpunk Glowing Progress Bar with Centered Progress Text
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
        # 5. LIVE LOGS TERMINAL (Fills Remaining Space)
        # -------------------------------------------------------------
        self.log_box = QFrame()
        self.log_box.setStyleSheet("background: #070812; border: 1px solid #1e2238; border-radius: 6px;")
        v_log = QVBoxLayout(self.log_box)
        v_log.setContentsMargins(8, 6, 8, 6)
        v_log.setSpacing(0)

        self.txt_logs = QTextEdit()
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
            QScrollBar::handle:vertical:hover {
                background: #8b5cf6;
            }
        """)
        self.txt_logs.setPlaceholderText("📟 Automation console ready. Logs will appear here in real-time...")
        v_log.addWidget(self.txt_logs)
        card_layout.addWidget(self.log_box, stretch=1)

        # -------------------------------------------------------------
        # 6. ACTION CONTROLS (At the very bottom matching Bot #2)
        # -------------------------------------------------------------
        h_act = QHBoxLayout()
        h_act.setSpacing(8)

        self.btn_start = QPushButton("▶️ Start Bot")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setFixedHeight(30)
        self.btn_start.setFixedWidth(115)
        self.btn_start.setStyleSheet("""
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
        self.btn_start.clicked.connect(self._on_start_automation)

        self.btn_reports = QPushButton("📁 Reports")
        self.btn_reports.setCursor(Qt.PointingHandCursor)
        self.btn_reports.setFixedHeight(30)
        self.btn_reports.setFixedWidth(85)
        self.btn_reports.setToolTip("Open folder containing CSV Reports & Screenshots")
        self.btn_reports.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #fbbf24;
                border: 1px solid #2b1e4a;
                border-radius: 5px;
                padding: 2px 10px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background: #261b45; color: #fde68a; border-color: #38bdf8; }
        """)
        self.btn_reports.clicked.connect(self._on_open_reports_folder)

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
        self.btn_stop.clicked.connect(self._on_stop_automation)

        self.lbl_live_status = QLabel("")
        self.lbl_live_status.hide()

        # Left Corner: Start Bot | Right Side: Reports, Stop
        h_act.addWidget(self.btn_start)
        h_act.addStretch(1)
        h_act.addWidget(self.btn_reports)
        h_act.addWidget(self.btn_stop)
        card_layout.addLayout(h_act)

    # -------------------------------------------------------------
    # Page Creator Studio Cyber-Dark Theme Engine
    # -------------------------------------------------------------
    def apply_theme(self, theme: str = "page_creator"):
        self.current_theme = theme
        # Exact Color Palette from Facebook Bulk Page Creator Studio
        self.main_card.setStyleSheet("""
            #MainCard {
                background-color: #080816;
                border: 1.5px solid #2b1e4a;
                border-radius: 14px;
            }
            QLabel { color: #f1f5f9; font-size: 11.5px; }
            QCheckBox {
                color: #e2e8f0;
                font-weight: 700;
                font-size: 11.5px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1.5px solid #7c3aed;
                background: #0c0e24;
            }
            QCheckBox::indicator:hover {
                border-color: #a78bfa;
                background: #18112e;
            }
            QCheckBox::indicator:checked {
                background: #7c3aed;
                border-color: #c084fc;
            }
        """)
        if hasattr(self, "lbl_title"):
            self.lbl_title.setText("Facebook Bulk Video / Reel Uploader Bot")
            self.lbl_title.setStyleSheet("""
                color: #c084fc;
                font-size: 15px;
                font-weight: 800;
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: transparent;
                border: none;
                letter-spacing: 0.3px;
            """)
        if hasattr(self, "lbl_srbrowser_status"):
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
        if hasattr(self, "target_box"):
            self.target_box.setStyleSheet("background-color: #090a1d; border: 1px solid #231b42; border-radius: 8px;")
        if hasattr(self, "combo_groups"):
            self.combo_groups.setStyleSheet("""
                QComboBox {
                    background-color: #0c0e24;
                    color: #38bdf8;
                    border: 1px solid #281d4a;
                    border-radius: 5px;
                    padding: 3px 8px;
                    font-size: 12px;
                    font-weight: 700;
                }
                QComboBox:focus { border-color: #7c3aed; }
                QComboBox::drop-down { border: none; }
                QComboBox QAbstractItemView {
                    background-color: #0c0e24;
                    color: #f1f5f9;
                    selection-background-color: #7c3aed;
                    selection-color: white;
                }
            """)
        if hasattr(self, "txt_profile_numbers"):
            self.txt_profile_numbers.setStyleSheet("""
                QLineEdit {
                    background-color: #0c0e24;
                    color: #38bdf8;
                    border: 1px solid #281d4a;
                    border-radius: 5px;
                    padding: 3px 8px;
                    font-size: 12px;
                    font-weight: 700;
                }
                QLineEdit:focus { border-color: #7c3aed; }
            """)
        if hasattr(self, "files_box"):
            self.files_box.setStyleSheet("background-color: #090a1d; border: 1px solid #231b42; border-radius: 8px;")
        if hasattr(self, "card_succ"):
            self.card_succ.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #081a13, stop:1 #040d09);
                    border: 1.5px solid #059669;
                    border-radius: 8px;
                }
            """)
        if hasattr(self, "card_fail"):
            self.card_fail.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2b1016, stop:1 #14070a);
                    border: 1.5px solid #dc2626;
                    border-radius: 8px;
                }
            """)
        if hasattr(self, "card_rem"):
            self.card_rem.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #091a2e, stop:1 #040e1a);
                    border: 1.5px solid #0284c7;
                    border-radius: 8px;
                }
            """)
        if hasattr(self, "log_box"):
            self.log_box.setStyleSheet("background-color: #050614; border: 1px solid #1c1538; border-radius: 6px;")
        if hasattr(self, "lbl_log_title"):
            self.lbl_log_title.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 800; border: none; background: transparent;")
        if hasattr(self, "txt_logs"):
            self.txt_logs.setStyleSheet("""
                QTextEdit {
                    background: transparent;
                    color: #38bdf8;
                    border: none;
                    font-family: 'Consolas', 'JetBrains Mono', 'Courier New', monospace;
                    font-size: 11px;
                    line-height: 1.25;
                }
                QScrollBar:vertical {
                    background: #050614; width: 6px; border-radius: 3px;
                }
                QScrollBar::handle:vertical {
                    background: #1c1538; border-radius: 3px;
                }
            """)
        if hasattr(self, "progress_bar"):
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #080915;
                    border: 1px solid #1e2238;
                    border-radius: 6px;
                    text-align: center;
                    color: #ffffff;
                    font-size: 11px;
                    font-weight: 800;
                    font-family: 'Segoe UI', sans-serif;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #38bdf8);
                    border-radius: 5px;
                    margin: 1px;
                }
            """)
        if hasattr(self, "btn_start"):
            self.btn_start.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                    color: #ffffff;
                    font-weight: 800;
                    font-size: 12px;
                    border: 1px solid #8b5cf6;
                    border-radius: 5px;
                    padding: 3px 10px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
                }
                QPushButton:disabled { background: #18112e; color: #64748b; border: 1px solid #231b42; }
            """)
        if hasattr(self, "btn_reports"):
            self.btn_reports.setStyleSheet("""
                QPushButton {
                    background: #18112e;
                    color: #c084fc;
                    border: 1px solid #7c3aed66;
                    border-radius: 5px;
                    padding: 3px 10px;
                    font-weight: 800;
                    font-size: 11.5px;
                }
                QPushButton:hover { background: #2b1a4f; color: #ffffff; border-color: #a78bfa; }
            """)
        if hasattr(self, "btn_stop"):
            self.btn_stop.setStyleSheet("""
                QPushButton {
                    background: #dc2626;
                    color: #ffffff;
                    font-weight: 800;
                    font-size: 12px;
                    border: 1px solid #ef4444;
                    border-radius: 5px;
                }
                QPushButton:hover { background: #b91c1c; }
                QPushButton:disabled { background: #1e2238; color: #64748b; border-color: transparent; }
            """)
        if hasattr(self, "btn_seg_group") and hasattr(self, "btn_seg_numbers"):
            self._style_segmented_buttons(self.btn_seg_group, self.btn_seg_numbers)
        if hasattr(self, "spin_threads"):
            for sp in [self.spin_threads, self.spin_stagger, self.spin_vpp, self.spin_timeout]:
                self._style_spinbox(sp)
        if hasattr(self, "lbl_target_count_badge"):
            self.lbl_target_count_badge.setStyleSheet("""
                background-color: #140d24; color: #c084fc;
                border: 1px solid #7c3aed66; border-radius: 5px;
                padding: 2px 9px; font-weight: 800; font-size: 11.5px;
            """)
        self._check_srbrowser_heartbeat()

    def _style_segmented_buttons(self, btn1: QPushButton, btn2: QPushButton):
        qss = """
            QPushButton {
                background: #18112e;
                color: #c084fc;
                border: 1px solid #7c3aed66;
                border-radius: 5px;
                padding: 2px 10px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: #261b45;
                color: #e9d5ff;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                font-weight: 800;
                border: none;
            }
        """
        btn1.setStyleSheet(qss)
        btn2.setStyleSheet(qss)

    def _style_spinbox(self, spin: QSpinBox, h: int = 24, w: Optional[int] = None):
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spin.setFixedHeight(h)
        if w is not None:
            spin.setFixedWidth(w)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setStyleSheet("""
            QSpinBox {
                background-color: #0c0e24;
                color: #38bdf8;
                border: 1px solid #281d4a;
                border-radius: 4px;
                font-weight: 800;
                font-size: 11.5px;
                padding: 0px 2px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                height: 0px;
                border: none;
            }
            QSpinBox:focus {
                border-color: #7c3aed;
                background-color: #140d24;
            }
        """)

    def _style_textedit(self, txt: QTextEdit):
        txt.setStyleSheet("""
            QTextEdit {
                background-color: #0c0e24;
                color: #ffffff;
                border: 1px solid #281d4a;
                border-radius: 5px;
                padding: 4px 6px;
                font-size: 11px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QTextEdit:focus { border-color: #7c3aed; }
        """)

    # -------------------------------------------------------------
    # Event Handlers & Modes
    # -------------------------------------------------------------
    def _on_target_mode_changed(self):
        is_group = self.btn_seg_group.isChecked()
        self.combo_groups.setVisible(is_group)
        self.txt_profile_numbers.setVisible(not is_group)
        self._refresh_target_profiles_count()

    def _refresh_target_profiles_count(self):
        mode = "group" if self.btn_seg_group.isChecked() else "numbers"
        grp = self.combo_groups.currentText()
        nums = self.txt_profile_numbers.text()
        matched = filter_profiles_by_target(self.all_profiles, mode=mode, group_name=grp, numbers_text=nums)
        count = len(matched)
        self.lbl_target_count_badge.setText(f"🎯 {count} Profiles")
        if hasattr(self, "lbl_metric_rem_num"):
            self.lbl_metric_rem_num.setText(str(count))
        if hasattr(self, "progress_bar") and not (hasattr(self, "master_thread") and self.master_thread and self.master_thread.isRunning()):
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(f"Progress: 0/{count} (0%)")

    def _check_srbrowser_heartbeat(self):
        try:
            from fb_bulk_uploader_bot_security import check_srbrowser_heartbeat
            is_up, msg = check_srbrowser_heartbeat()
        except Exception:
            is_up = True
            msg = "Active"

        if hasattr(self, "lbl_srbrowser_status"):
            if is_up:
                self.lbl_srbrowser_status.setText("🟢 srkBrowser Active")
                self.lbl_srbrowser_status.setToolTip(f"Core Engine: {msg}")
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
            else:
                self.lbl_srbrowser_status.setText("🔴 srkBrowser Offline")
                self.lbl_srbrowser_status.setToolTip(f"Core Engine: {msg}")
                self.lbl_srbrowser_status.setStyleSheet("""
                    QLabel {
                        background-color: #2b1016;
                        color: #f87171;
                        font-size: 11px;
                        font-weight: 800;
                        border: 1px solid #dc262688;
                        border-radius: 5px;
                        padding: 2px 10px;
                    }
                """)

    def _append_log(self, level: str, msg: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        is_hacker = getattr(self, "current_theme", "hacking") == "hacking"
        if is_hacker:
            time_color = "#00e5ff"
            if level == "SUCCESS":
                color = "#00ff88"
            elif level == "ERROR":
                color = "#ff3355"
            elif level == "WARNING":
                color = "#facc15"
            else:
                color = "#86efac"
        else:
            time_color = "#64748b"
            if level == "SUCCESS":
                color = "#34d399"
            elif level == "ERROR":
                color = "#f87171"
            elif level == "WARNING":
                color = "#fbbf24"
            else:
                color = "#94a3b8"

        html = f'<span style="color:{time_color};">[{now_str}]</span> <span style="color:{color}; font-weight: 600;">{msg}</span>'
        if hasattr(self, "txt_logs"):
            self.txt_logs.append(html)
            sb = self.txt_logs.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    def _on_click_videos_source(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0d111d;
                color: #f1f5f9;
                border: 1.5px solid #7c3aed;
                border-radius: 8px;
                padding: 4px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QMenu::item {
                padding: 7px 18px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #2e1065;
                color: #c084fc;
            }
        """)
        act_local = menu.addAction("💻 Select from Local PC (Folder)")
        act_cloud = menu.addAction("☁️ Use Cloud Server Vault")
        pt = self.btn_pick_videos.mapToGlobal(QPoint(0, self.btn_pick_videos.height() + 2))
        action = menu.exec(pt)
        if action == act_local:
            self._on_browse_video_folder()
        elif action == act_cloud:
            self._on_select_cloud_videos()

    def _on_select_cloud_videos(self):
        manifest = fetch_cloud_videos_manifest()
        vault_dir = get_cloud_video_vault_dir()
        video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
        cached_count = len([p for p in vault_dir.iterdir() if p.is_file() and p.suffix.lower() in video_exts and p.stat().st_size > 1024])

        total_available = len(manifest) or cached_count
        if total_available > 0:
            self.video_source = "cloud"
            self.lbl_folder_status.setText("☁️ Cloud Video Vault")
            self.lbl_folder_status.setStyleSheet("color: #a855f7; font-size: 11px; font-weight: 700;")
            self.lbl_badge_count.setText(f"{total_available} Videos")
            self.lbl_live_status.setText(f"Cloud Vault selected: {total_available} videos ready.")
            self._append_log("SUCCESS", f"☁️ Cloud Video Vault selected ({total_available} videos available on server/vault).")
            self._append_log("INFO", "⚡ Smart Caching active: videos are stored securely in internal vault and reused with 0-delay on future runs.")
        else:
            QMessageBox.information(
                self, "Cloud Video Vault",
                "No videos found in Cloud Vault yet.\n\nYou can upload videos to the Vault from your Admin Panel:\nhttps://srbrowser.com/admin (Cloud Presets tab)"
            )

    def _on_browse_video_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Video Folder")
        if folder:
            self.video_source = "local"
            self.loaded_video_files = scan_video_folder(folder)
            count = len(self.loaded_video_files)
            folder_name = Path(folder).name or folder
            self.lbl_folder_status.setText(folder_name)
            self.lbl_folder_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
            self.lbl_folder_status.setToolTip(folder)
            self.lbl_badge_count.setText(f"{count} Videos")
            self.lbl_live_status.setText(f"Loaded {count} videos.")
            self._append_log("INFO", f"Loaded {count} videos from: {folder_name}")

    def _on_click_titles_source(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0d111d;
                color: #f1f5f9;
                border: 1.5px solid #0284c7;
                border-radius: 8px;
                padding: 4px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QMenu::item {
                padding: 7px 18px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #082f49;
                color: #38bdf8;
            }
        """)
        act_local = menu.addAction("💻 Select from Local PC (.txt)")
        act_cloud = menu.addAction("☁️ Use Cloud Server Default")
        menu.addSeparator()
        act_open_titles = menu.addAction("📝 Open / Edit Default Titles File (.txt)")
        pt = self.btn_pick_titles.mapToGlobal(QPoint(0, self.btn_pick_titles.height() + 2))
        action = menu.exec(pt)
        if action == act_local:
            self._on_browse_titles_txt()
        elif action == act_cloud:
            self._on_select_cloud_titles()
        elif action == act_open_titles:
            self._on_open_default_titles_file()

    def _on_open_default_titles_file(self):
        try:
            t_path = get_default_titles_file_path()
            if not t_path.exists():
                tpls = fetch_cloud_uploader_templates()
                titles = tpls.get("titles", [])
                t_path.parent.mkdir(parents=True, exist_ok=True)
                t_path.write_text("\n".join(titles) + "\n", encoding="utf-8")
            os.startfile(str(t_path))
            self._append_log("INFO", f"📝 Opened default titles file: {t_path.name}")
        except Exception as ex:
            QMessageBox.information(self, "Default Titles", f"File location:\n{t_path}\n\nCould not auto-open: {ex}")

    def _on_select_cloud_titles(self):
        tpls = fetch_cloud_uploader_templates()
        titles = tpls.get("titles", [])
        if titles:
            self.titles_from_txt = titles
            self.titles_source = "cloud"
            self.lbl_titles_txt_status.setText("☁️ Cloud Server Default")
            self.lbl_titles_txt_status.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700;")
            self.lbl_titles_count_badge.setText(f"{len(titles)} Lines")
            self.lbl_live_status.setText(f"Loaded {len(titles)} cloud titles.")
            self._append_log("SUCCESS", f"☁️ Loaded {len(titles)} default titles (from default_titles.txt / cloud).")
        else:
            QMessageBox.warning(self, "Cloud Titles", "No cloud titles found on server.")

    def _on_browse_titles_txt(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Select titles.txt", "", "Text Files (*.txt);;All Files (*)")
        if fpath:
            self.titles_source = "local"
            self.titles_from_txt = load_lines_from_txt_file(fpath)
            self.lbl_titles_txt_status.setText(Path(fpath).name)
            self.lbl_titles_txt_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
            self.lbl_titles_count_badge.setText(f"{len(self.titles_from_txt)} Lines")
            self.lbl_live_status.setText(f"Loaded {len(self.titles_from_txt)} titles.")
            self._append_log("INFO", f"Loaded {len(self.titles_from_txt)} titles from: {Path(fpath).name}")

    def _on_click_descs_source(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0d111d;
                color: #f1f5f9;
                border: 1.5px solid #7c3aed;
                border-radius: 8px;
                padding: 4px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QMenu::item {
                padding: 7px 18px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #2e1065;
                color: #c084fc;
            }
        """)
        act_local = menu.addAction("💻 Select from Local PC (.txt)")
        act_cloud = menu.addAction("☁️ Use Cloud Server Default")
        menu.addSeparator()
        act_open_descs = menu.addAction("📝 Open / Edit Default Descriptions File (.txt)")
        act_links = None
        if self.descs_from_txt:
            menu.addSeparator()
            act_links = menu.addAction("🔗 Configure Target Links ({{link}})")
        pt = self.btn_pick_descs.mapToGlobal(QPoint(0, self.btn_pick_descs.height() + 2))
        action = menu.exec(pt)
        if action == act_local:
            self._on_browse_descs_txt()
        elif action == act_cloud:
            self._on_select_cloud_descs()
        elif action == act_open_descs:
            self._on_open_default_descriptions_file()
        elif action == act_links:
            self._on_configure_target_links()

    def _on_open_default_descriptions_file(self):
        try:
            d_path = get_default_descriptions_file_path()
            if not d_path.exists():
                tpls = fetch_cloud_uploader_templates()
                descs = tpls.get("descriptions", [])
                d_path.parent.mkdir(parents=True, exist_ok=True)
                d_path.write_text("\n---\n".join(descs) + "\n", encoding="utf-8")
            os.startfile(str(d_path))
            self._append_log("INFO", f"📝 Opened default descriptions file: {d_path.name}")
        except Exception as ex:
            QMessageBox.information(self, "Default Descriptions", f"File location:\n{d_path}\n\nCould not auto-open: {ex}")

    def _on_configure_target_links(self):
        initial_text = "\n".join(self.custom_user_links) if self.custom_user_links else self.txt_custom_link.toPlainText().strip()
        modal = CloudDescriptionLinksModal(initial_links=initial_text, parent=self)
        if modal.exec() == QDialog.Accepted:
            self.custom_user_links = modal.get_links_list()
            self.txt_custom_link.setPlainText("\n".join(self.custom_user_links))
            link_count = len(self.custom_user_links)
            source_lbl = f"Local file: {self.lbl_descs_txt_status.text()}" if self.descs_source == "local" else "Cloud Server Default"
            if link_count > 0:
                self.lbl_descs_count_badge.setToolTip(f"{source_lbl} ({len(self.descs_from_txt)} lines) | {link_count} Link(s) Configured")
            else:
                self.lbl_descs_count_badge.setToolTip(f"{source_lbl} ({len(self.descs_from_txt)} lines)")
            self.lbl_live_status.setText(f"Configured {link_count} target links.")
            if link_count > 0:
                self._append_log("INFO", f"🔗 {link_count} custom target link(s) configured to auto-replace {{{{link}}}} in descriptions.")
            else:
                self._append_log("INFO", "⚡ 0 custom links configured.")

    def _on_select_cloud_descs(self):
        tpls = fetch_cloud_uploader_templates()
        descs = tpls.get("descriptions", [])
        if descs:
            initial_text = "\n".join(self.custom_user_links) if self.custom_user_links else self.txt_custom_link.toPlainText().strip()
            modal = CloudDescriptionLinksModal(initial_links=initial_text, parent=self)
            if modal.exec() == QDialog.Accepted:
                self.custom_user_links = modal.get_links_list()
                self.txt_custom_link.setPlainText("\n".join(self.custom_user_links))
                self.descs_from_txt = descs
                self.descs_source = "cloud"
                self.lbl_descs_txt_status.setText("☁️ Cloud Server Default")
                self.lbl_descs_txt_status.setStyleSheet("color: #c084fc; font-size: 11px; font-weight: 700;")
                self.lbl_descs_count_badge.setText(f"{len(descs)} Lines")
                link_count = len(self.custom_user_links)
                if link_count > 0:
                    self.lbl_descs_count_badge.setToolTip(f"Cloud Server Default ({len(descs)} lines) | {link_count} Link(s) Configured")
                else:
                    self.lbl_descs_count_badge.setToolTip(f"Cloud Server Default ({len(descs)} lines)")
                self.lbl_live_status.setText(f"Loaded {len(descs)} cloud descriptions ({link_count} links).")
                self._append_log("SUCCESS", f"☁️ Loaded {len(descs)} cloud default descriptions with {{{{link}}}} tags.")
                if link_count > 0:
                    self._append_log("INFO", f"🔗 {link_count} custom target link(s) configured to auto-replace {{{{link}}}} in descriptions.")
                else:
                    self._append_log("INFO", "⚡ 0 custom links entered ({{link}} tag will remain default).")
            else:
                self._append_log("INFO", "ℹ️ Cloud descriptions configuration closed.")
        else:
            QMessageBox.warning(self, "Cloud Descriptions", "No cloud descriptions found on server.")

    def _on_browse_descs_txt(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Select descriptions.txt", "", "Text Files (*.txt);;All Files (*)")
        if fpath:
            descs = load_descriptions_from_txt_file(fpath)
            if not descs:
                QMessageBox.warning(self, "Empty File", "The selected descriptions file is empty.")
                return
            self.descs_source = "local"
            self.descs_from_txt = descs
            self.lbl_descs_txt_status.setText(Path(fpath).name)
            self.lbl_descs_txt_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
            self.lbl_descs_count_badge.setText(f"{len(self.descs_from_txt)} Descs")

            # Pop up Target Links Modal so user can configure target links for {{link}}
            initial_text = "\n".join(self.custom_user_links) if self.custom_user_links else self.txt_custom_link.toPlainText().strip()
            modal = CloudDescriptionLinksModal(initial_links=initial_text, parent=self)
            if modal.exec() == QDialog.Accepted:
                self.custom_user_links = modal.get_links_list()
                self.txt_custom_link.setPlainText("\n".join(self.custom_user_links))
                link_count = len(self.custom_user_links)
                if link_count > 0:
                    self.lbl_descs_count_badge.setToolTip(f"Local file: {Path(fpath).name} ({len(self.descs_from_txt)} lines) | {link_count} Link(s) Configured")
                else:
                    self.lbl_descs_count_badge.setToolTip(f"Local file: {Path(fpath).name} ({len(self.descs_from_txt)} lines)")
                self.lbl_live_status.setText(f"Loaded {len(self.descs_from_txt)} descriptions ({link_count} links).")
                self._append_log("SUCCESS", f"💻 Loaded {len(self.descs_from_txt)} descriptions from: {Path(fpath).name}")
                if link_count > 0:
                    self._append_log("INFO", f"🔗 {link_count} custom target link(s) configured to auto-replace {{{{link}}}} in descriptions.")
                else:
                    self._append_log("INFO", "⚡ 0 custom links entered ({{link}} tag will remain default).")
            else:
                link_count = len(self.custom_user_links) if self.custom_user_links else 0
                if link_count > 0:
                    self.lbl_descs_count_badge.setToolTip(f"Local file: {Path(fpath).name} ({len(self.descs_from_txt)} lines) | {link_count} Link(s) Configured")
                else:
                    self.lbl_descs_count_badge.setToolTip(f"Local file: {Path(fpath).name} ({len(self.descs_from_txt)} lines)")
                self.lbl_live_status.setText(f"Loaded {len(self.descs_from_txt)} descriptions.")
                self._append_log("INFO", f"💻 Loaded {len(self.descs_from_txt)} descriptions from: {Path(fpath).name}")

    def _on_link_text_changed(self):
        lines = [l.strip() for l in self.txt_custom_link.toPlainText().splitlines() if l.strip()]
        if hasattr(self, "lbl_link_count_badge"):
            self.lbl_link_count_badge.setText(f"{len(lines)} Links")

    def _on_open_reports_folder(self):
        try:
            if os.name == "nt":
                os.startfile(str(self.reports_dir))
            else:
                webbrowser.open(f"file://{self.reports_dir}")
        except Exception as e:
            QMessageBox.warning(self, "Reports", f"Could not open reports:\n{e}")

    # -------------------------------------------------------------
    # Execution Flow
    # -------------------------------------------------------------
    def _on_start_automation(self):
        mode = "group" if self.btn_seg_group.isChecked() else "numbers"
        grp = self.combo_groups.currentText()
        nums = self.txt_profile_numbers.text()
        target_profiles = filter_profiles_by_target(self.all_profiles, mode=mode, group_name=grp, numbers_text=nums)

        if not target_profiles:
            QMessageBox.warning(self, "No Profiles", "Please select at least 1 profile.")
            return

        # Cloud Video Vault smart sync if cloud video source is active
        if self.video_source == "cloud":
            self._append_log("INFO", "☁️ Synchronizing Cloud Video Vault (Smart Differential Caching)...")
            modal = CloudVaultSyncModalDialog(self)
            modal.start_sync()
            if modal.exec() != QDialog.Accepted or not modal.result_paths:
                if modal.error_msg:
                    QMessageBox.critical(self, "Sync Error", f"Failed to sync cloud videos:\n{modal.error_msg}")
                self._append_log("WARNING", "⚠️ Cloud Video Vault sync was cancelled or returned 0 files.")
                return

            self.loaded_video_files = modal.result_paths
            self.lbl_badge_count.setText(f"{len(self.loaded_video_files)} Videos")
            self._append_log("SUCCESS", f"☁️ {len(self.loaded_video_files)} Cloud Video(s) verified & ready from secure vault.")

        if not self.loaded_video_files:
            QMessageBox.warning(self, "No Videos", "Please select a valid Video Folder or Cloud Video Vault.")
            return

        titles = list(self.titles_from_txt)
        descriptions = list(self.descs_from_txt)

        # Apply user custom links to descriptions (1 link per line sequentially)
        user_link_input = self.txt_custom_link.toPlainText().strip()
        user_links = [l.strip() for l in user_link_input.splitlines() if l.strip()]
        if user_links or self.descs_source == "cloud" or any("{{link}}" in str(d).lower() for d in descriptions):
            descriptions = apply_user_links_to_descriptions(descriptions, user_links)
            if user_links:
                self._append_log("INFO", f"🔗 Detected {len(user_links)} custom link(s) — auto-injected into {len(descriptions)} description(s) replacing {{{{link}}}}")

        threads = self.spin_threads.value()
        stagger = float(self.spin_stagger.value())
        vpp = self.spin_vpp.value()
        timeout_sec = self.spin_timeout.value() * 60
        headless = self.chk_headless.isChecked()
        mode_str = "publish"
        fail_grp = self.combo_fail_group.currentText().strip() if hasattr(self, "combo_fail_group") else "None"
        page_mode = self.combo_page_mode.currentText().strip() if hasattr(self, "combo_page_mode") else "Selected Page"

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Progress: 0/{len(target_profiles)} (0%)")
        self.lbl_live_status.setText("Automation running...")

        if hasattr(self, "txt_logs"):
            self.txt_logs.clear()
        self._append_log("INFO", f"🚀 Starting bulk uploader with {len(target_profiles)} profiles, concurrency={threads}, stagger={stagger}s...")
        self._append_log("INFO", f"📑 Multi-Page Strategy: '{page_mode}'")
        if fail_grp and fail_grp.lower() != "none":
            self._append_log("INFO", f"📁 Failed profiles auto-routing target group: '{fail_grp}'")

        self.master_thread = BulkVideoUploaderMasterThread(
            profiles=target_profiles,
            video_files=self.loaded_video_files,
            titles=titles,
            descriptions=descriptions,
            videos_per_profile=vpp,
            concurrency=threads,
            stagger_sec=stagger,
            is_headless=headless,
            publish_mode=mode_str,
            timeout_sec=timeout_sec,
            reports_dir=self.reports_dir,
            profile_mgr=self.profile_mgr,
            user_links=user_links,
            fail_group=fail_grp,
            page_mode=page_mode
        )

        self.master_thread.log_emitted.connect(self._append_log)
        self.master_thread.log_emitted.connect(lambda lvl, msg: self.lbl_live_status.setText(msg[:60]))
        self.master_thread.stats_updated.connect(self._on_stats_updated)
        self.master_thread.progress_changed.connect(self._on_progress_changed)
        self.master_thread.finished_all.connect(self._on_automation_finished)

        self.master_thread.start()

    def _on_stop_automation(self):
        if self.master_thread and self.master_thread.isRunning():
            self.master_thread.cancel()
            self.btn_stop.setEnabled(False)
            self.lbl_live_status.setText("Stopping...")
            self._append_log("WARNING", "🛑 Stop command sent to automation threads. All browsers closing...")

    def closeEvent(self, event) -> None:
        self._on_stop_automation()
        if self.master_thread and self.master_thread.isRunning():
            self.master_thread.cancel()
            self.master_thread.wait(2000)
        event.accept()

    def reject(self) -> None:
        self._on_stop_automation()
        if self.master_thread and self.master_thread.isRunning():
            self.master_thread.cancel()
            self.master_thread.wait(2000)
        super().reject()

    def _on_stats_updated(self, succ_ids: int, fail_ids: int, rem_ids: int, total_videos: int):
        if hasattr(self, "lbl_metric_succ_num"):
            self.lbl_metric_succ_num.setText(str(succ_ids))
        if hasattr(self, "lbl_metric_fail_num"):
            self.lbl_metric_fail_num.setText(str(fail_ids))
        if hasattr(self, "lbl_metric_rem_num"):
            self.lbl_metric_rem_num.setText(str(rem_ids))
        if hasattr(self, "lbl_metric_succ_sub"):
            self.lbl_metric_succ_sub.setText(f"IDs Uploaded ({total_videos} Vids)")

    def _on_progress_changed(self, current: int, total: int):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"Progress: {current}/{total} ({pct}%)")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Progress: 0/0 (0%)")

    def _on_automation_finished(self, report_path: str, succ_ids: int, fail_ids: int, total_ids: int, total_videos: int):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(f"Progress: {total_ids}/{total_ids} (100%)")
        self.lbl_live_status.setText(f"Finished! IDs: {succ_ids}/{total_ids} Succeeded, {fail_ids} Failed | {total_videos} Videos")

        # Show beautiful, custom styled modal dialog focused on IDs + Total Videos
        try:
            dlg = FbBulkUploaderFinishedDialog(
                succ_profiles=succ_ids,
                fail_profiles=fail_ids,
                total_profiles=total_ids,
                total_videos=total_videos,
                report_path=report_path,
                parent=self
            )
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "Finished", f"Automation completed!\n\nSuccessful IDs: {succ_ids}/{total_ids}\nFailed IDs: {fail_ids}\nTotal Videos: {total_videos}")

    # -------------------------------------------------------------
    # Drag window handlers for Main Bot Dialog
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
        event.accept()

    def _update_custom_link_box_visibility(self, visible: bool) -> None:
        pass

    def _cleanup_and_close(self) -> None:
        if hasattr(self, "timer_hb") and self.timer_hb.isActive():
            self.timer_hb.stop()
        self._on_stop_automation()
        self.reject()

    def closeEvent(self, event) -> None:
        if hasattr(self, "timer_hb") and self.timer_hb.isActive():
            self.timer_hb.stop()
        self._on_stop_automation()
        event.accept()

    def reject(self) -> None:
        if hasattr(self, "timer_hb") and self.timer_hb.isActive():
            self.timer_hb.stop()
        self._on_stop_automation()
        super().reject()


class FbBulkUploaderFinishedDialog(QDialog):
    """
    Modern, sleek completion report dialog matching the dark hacker / cyberpunk aesthetic.
    Features vibrant summary cards, clickable report path, and smooth drag support.
    """
    def __init__(self, succ_profiles: int = 0, fail_profiles: int = 0, total_profiles: int = 0, total_videos: int = 0, report_path: str = "", parent: Any = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(500, 390)
        self._drag_pos = QPoint()
        self.report_path = report_path

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("finishedCard")
        card.setStyleSheet("""
            QFrame#finishedCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f172a, stop:0.5 #0b0f19, stop:1 #131b2e);
                border: 1px solid #334155;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(14)

        # Title bar
        h_title = QHBoxLayout()
        lbl_icon = QLabel("🎉")
        lbl_icon.setStyleSheet("font-size: 24px;")

        v_title = QVBoxLayout()
        lbl_main = QLabel("Automation Completed!")
        lbl_main.setStyleSheet("color: #f8fafc; font-size: 17px; font-weight: 800; font-family: 'Segoe UI', sans-serif;")
        lbl_sub = QLabel("Facebook Bulk Video Uploader Bot finished execution")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 11.5px;")
        v_title.addWidget(lbl_main)
        v_title.addWidget(lbl_sub)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #94a3b8;
                border: none;
                border-radius: 14px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.accept)

        h_title.addWidget(lbl_icon)
        h_title.addSpacing(8)
        h_title.addLayout(v_title, stretch=1)
        h_title.addWidget(btn_close)
        card_layout.addLayout(h_title)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background: #1e293b; max-height: 1px; border: none;")
        card_layout.addWidget(div)

        # ID / Profile Stats Cards Grid (Primary ID Focus)
        h_stats = QHBoxLayout()
        h_stats.setSpacing(12)

        # Success IDs Card
        card_succ = QFrame()
        card_succ.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(16, 185, 129, 0.15), stop:1 rgba(16, 185, 129, 0.05));
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 12px;
        """)
        v_s = QVBoxLayout(card_succ)
        v_s.setContentsMargins(12, 12, 12, 12)
        lbl_s_num = QLabel(str(succ_profiles))
        lbl_s_num.setAlignment(Qt.AlignCenter)
        lbl_s_num.setStyleSheet("color: #34d399; font-size: 26px; font-weight: 900; background: transparent; border: none;")
        lbl_s_txt = QLabel("✓ SUCCESSFUL IDS")
        lbl_s_txt.setAlignment(Qt.AlignCenter)
        lbl_s_txt.setStyleSheet("color: #a7f3d0; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; background: transparent; border: none;")
        v_s.addWidget(lbl_s_num)
        v_s.addWidget(lbl_s_txt)

        # Failed IDs Card
        card_fail = QFrame()
        card_fail.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(239, 68, 68, 0.15), stop:1 rgba(239, 68, 68, 0.05));
            border: 1px solid rgba(239, 68, 68, 0.35);
            border-radius: 12px;
        """)
        v_f = QVBoxLayout(card_fail)
        v_f.setContentsMargins(12, 12, 12, 12)
        lbl_f_num = QLabel(str(fail_profiles))
        lbl_f_num.setAlignment(Qt.AlignCenter)
        lbl_f_num.setStyleSheet("color: #f87171; font-size: 26px; font-weight: 900; background: transparent; border: none;")
        lbl_f_txt = QLabel("✕ FAILED IDS")
        lbl_f_txt.setAlignment(Qt.AlignCenter)
        lbl_f_txt.setStyleSheet("color: #fecaca; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; background: transparent; border: none;")
        v_f.addWidget(lbl_f_num)
        v_f.addWidget(lbl_f_txt)

        # Total IDs Card
        card_tot = QFrame()
        card_tot.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(124, 58, 237, 0.15), stop:1 rgba(124, 58, 237, 0.05));
            border: 1px solid rgba(124, 58, 237, 0.35);
            border-radius: 12px;
        """)
        v_t = QVBoxLayout(card_tot)
        v_t.setContentsMargins(12, 12, 12, 12)
        lbl_t_num = QLabel(str(total_profiles))
        lbl_t_num.setAlignment(Qt.AlignCenter)
        lbl_t_num.setStyleSheet("color: #a78bfa; font-size: 26px; font-weight: 900; background: transparent; border: none;")
        lbl_t_txt = QLabel("★ TOTAL IDS")
        lbl_t_txt.setAlignment(Qt.AlignCenter)
        lbl_t_txt.setStyleSheet("color: #ddd6fe; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; background: transparent; border: none;")
        v_t.addWidget(lbl_t_num)
        v_t.addWidget(lbl_t_txt)

        h_stats.addWidget(card_succ)
        h_stats.addWidget(card_fail)
        h_stats.addWidget(card_tot)
        card_layout.addLayout(h_stats)

        # Video Upload Count Pill (Showing total videos uploaded across all IDs)
        lbl_vids_pill = QLabel(f"🎬  Total Videos Uploaded: {total_videos} Videos Published Successfully")
        lbl_vids_pill.setStyleSheet("""
            background: rgba(30, 41, 59, 0.6);
            color: #38bdf8;
            font-size: 11.5px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 8px;
            border: 1px solid rgba(56, 189, 248, 0.25);
        """)
        card_layout.addWidget(lbl_vids_pill)

        # Report Notice Pill
        p_name = Path(report_path).name if report_path else "Report Generated in reports/"
        lbl_rep = QLabel(f"📄  Report: {p_name}")
        lbl_rep.setStyleSheet("""
            background: #1e293b;
            color: #94a3b8;
            font-size: 11px;
            padding: 6px 12px;
            border-radius: 8px;
            border: 1px solid #334155;
        """)
        card_layout.addWidget(lbl_rep)
        card_layout.addSpacing(2)

        # Buttons Row
        h_btns = QHBoxLayout()
        h_btns.setSpacing(10)

        btn_view_report = QPushButton("📊 View Report")
        btn_view_report.setFixedHeight(38)
        btn_view_report.setCursor(Qt.PointingHandCursor)
        btn_view_report.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #334155;
                border-color: #64748b;
                color: #ffffff;
            }
        """)
        btn_view_report.clicked.connect(self._open_report)

        btn_done = QPushButton("Done")
        btn_done.setFixedHeight(38)
        btn_done.setCursor(Qt.PointingHandCursor)
        btn_done.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #4f46e5);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 12.5px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #6366f1);
            }
        """)
        btn_done.clicked.connect(self.accept)

        h_btns.addWidget(btn_view_report, stretch=1)
        h_btns.addWidget(btn_done, stretch=1)
        card_layout.addLayout(h_btns)

        outer_layout.addWidget(card)

    def _open_report(self):
        import webbrowser
        try:
            if self.report_path and os.path.exists(self.report_path):
                if os.name == "nt":
                    try:
                        os.startfile(os.path.abspath(self.report_path))
                        return
                    except Exception:
                        pass
                webbrowser.open(f"file://{os.path.abspath(self.report_path)}")
            else:
                rep_dir = Path(__file__).resolve().parent / "reports"
                if rep_dir.exists():
                    if os.name == "nt":
                        try:
                            os.startfile(os.path.abspath(str(rep_dir.resolve())))
                            return
                        except Exception:
                            pass
                    webbrowser.open(f"file://{rep_dir.resolve()}")
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
        event.accept()




# -------------------------------------------------------------
# Module Entry Points
# -------------------------------------------------------------
_active_bot_dialogs = []


def launch_ui(profile_mgr: Any = None, parent: Any = None, **kwargs) -> bool:
    """Launch non-modal bot studio dialog."""
    dlg = FbBulkVideoUploaderBotDialog(profile_mgr=profile_mgr, parent=parent)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    _active_bot_dialogs.append(dlg)
    dlg.finished.connect(lambda: _active_bot_dialogs.remove(dlg) if dlg in _active_bot_dialogs else None)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return True


def main(profile_mgr: Any = None, parent: Any = None, **kwargs):
    return launch_ui(profile_mgr=profile_mgr, parent=parent, **kwargs)


__all__ = ["FbBulkVideoUploaderBotDialog", "launch_ui", "main"]
