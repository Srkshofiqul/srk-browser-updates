# -*- coding: utf-8 -*-
"""
User Interface (PySide6) for Facebook Reels Algorithm Trainer Bot:
- Modern Cyberpunk Dark Theme matching srkBrowser Ecosystem
- Clean, uncluttered layout: Profiles ➜ Target Seed Links ➜ Engagement Comments ➜ Execution Settings
- Autonomous Execution: Auto-Login, Suspension detection, Password->Cookie Fallback
- Smart Contextual Reel Engagement & Comments
- Parallel Browsers (1-20), Watch Delay, Headless mode
- Live execution progress bar & colorized logs console
"""

import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QCheckBox, QRadioButton, QButtonGroup, QGroupBox, QFrame, QProgressBar,
    QFileDialog, QMessageBox, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QPoint, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QColor, QCursor, QIcon

from fb_reels_algo_trainer_helpers import (
    get_base_dir,
    get_profiles_dir,
    load_lines_from_txt_file,
    parse_raw_text_lines,
    filter_by_profile_numbers,
    DEFAULT_ALGO_TRAINER_COMMENTS
)
from fb_reels_algo_trainer_engine import FbReelsAlgoTrainerEngine


class FbReelsAlgoTrainerDialog(QDialog):
    """Luxury Dark Cyberpunk Dialog for Facebook Reels Algorithm Trainer Bot."""

    def __init__(self, profile_mgr: Any = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.worker_thread: Optional[FbReelsAlgoTrainerEngine] = None

        self.setWindowTitle("⚡ Facebook Reels Algorithm Trainer Bot - srkBrowser")
        self.resize(960, 800)
        self.setMinimumSize(880, 720)

        self._drag_pos = QPoint()
        self._init_data()
        self._init_ui()
        self._load_defaults()

    def _init_data(self):
        """Loads available profiles from profile_mgr or directly from disk."""
        self.all_profiles: List[Dict[str, Any]] = []

        if self.profile_mgr is None:
            base = get_base_dir()
            for extra_p in [base / "_internal", base / "_internal" / "core", base / "core"]:
                if extra_p.exists() and str(extra_p) not in sys.path:
                    sys.path.insert(0, str(extra_p))
            try:
                from profile_manager import ProfileManager
                self.profile_mgr = ProfileManager()
            except Exception:
                try:
                    from core.profile_manager import ProfileManager
                    self.profile_mgr = ProfileManager()
                except Exception:
                    self.profile_mgr = None

        if self.profile_mgr:
            if hasattr(self.profile_mgr, "get_all_profiles") and callable(getattr(self.profile_mgr, "get_all_profiles")):
                try:
                    self.all_profiles = self.profile_mgr.get_all_profiles()
                except Exception:
                    self.all_profiles = []
            if not self.all_profiles and hasattr(self.profile_mgr, "profiles"):
                self.all_profiles = list(self.profile_mgr.profiles)

        if not self.all_profiles:
            pdir = get_profiles_dir()
            if pdir.exists():
                for sub in sorted(pdir.iterdir()):
                    if sub.is_dir() and (sub.name.startswith("Profile") or sub.name.isdigit()):
                        m = re.search(r'\d+', sub.name)
                        num_str = m.group(0) if m else "1"
                        self.all_profiles.append({
                            "id": num_str,
                            "number": int(num_str),
                            "name": sub.name,
                            "folder_name": sub.name,
                            "group": "Default"
                        })

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d17;
                color: #f1f5f9;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #1e293b;
                border-radius: 10px;
                margin-top: 14px;
                font-weight: 800;
                font-size: 12.5px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: #111827;
                border: 1px solid #1e293b;
                border-radius: 7px;
                color: #f8fafc;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #38bdf8;
            }
            QRadioButton, QCheckBox {
                color: #e2e8f0;
                font-size: 12px;
                spacing: 8px;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QScrollBar:vertical {
                background: #0f172a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ----------------------------------------------------
        # Header / Banner
        # ----------------------------------------------------
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1b4b, stop:0.5 #312e81, stop:1 #0f172a);
                border: 1px solid #4338ca;
                border-radius: 10px;
                padding: 10px 14px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 6, 8, 6)

        title_icon = QLabel("⚡")
        title_icon.setStyleSheet("font-size: 26px;")
        header_layout.addWidget(title_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("Facebook Reels Algorithm Trainer Bot")
        lbl_title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: 800;")
        lbl_sub = QLabel("⚡ Fast-Train Mode: Auto-Login ➜ Interested ➜ Follow ➜ Like ➜ Reels Discovery Feed Lock")
        lbl_sub.setStyleSheet("color: #a5b4fc; font-size: 11.5px;")
        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_sub)
        header_layout.addLayout(title_vbox, 1)

        badge = QLabel("🟢 srkBrowser Active")
        badge.setStyleSheet("""
            background: #064e3b;
            color: #6ee7b7;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid #059669;
        """)
        header_layout.addWidget(badge)
        main_layout.addWidget(header_frame)

        # ----------------------------------------------------
        # Scrollable Configuration Area
        # ----------------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(12)

        # 1. Profile Selection Group
        grp_profiles = QGroupBox("1. Target Profiles Selection")
        grp_profiles.setStyleSheet("QGroupBox { border-color: #3b82f6; } QGroupBox::title { color: #60a5fa; }")
        p_layout = QVBoxLayout(grp_profiles)
        p_layout.setSpacing(10)

        r_hbox = QHBoxLayout()
        self.radio_all = QRadioButton("All Available Profiles")
        self.radio_group = QRadioButton("By Profile Group")
        self.radio_range = QRadioButton("Custom Profile Range (e.g. 1-10, 15, 20)")
        self.radio_range.setChecked(True)

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.radio_all)
        self.btn_group.addButton(self.radio_group)
        self.btn_group.addButton(self.radio_range)

        r_hbox.addWidget(self.radio_all)
        r_hbox.addWidget(self.radio_group)
        r_hbox.addWidget(self.radio_range)
        r_hbox.addStretch()
        p_layout.addLayout(r_hbox)

        p_ctrl_hbox = QHBoxLayout()
        p_ctrl_hbox.setSpacing(10)

        self.lbl_group = QLabel("Group:")
        self.combo_groups = QComboBox()
        self.combo_groups.setMinimumWidth(160)
        self._populate_groups()

        self.lbl_range = QLabel("Range:")
        self.txt_range = QLineEdit()
        self.txt_range.setPlaceholderText("e.g. 1-5, 8, 12-20 or all")
        self.txt_range.setText("1-5")

        self.lbl_profile_count = QLabel(f"Profiles Found: {len(self.all_profiles)}")
        self.lbl_profile_count.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")

        p_ctrl_hbox.addWidget(self.lbl_group)
        p_ctrl_hbox.addWidget(self.combo_groups)
        p_ctrl_hbox.addWidget(self.lbl_range)
        p_ctrl_hbox.addWidget(self.txt_range, 1)
        p_ctrl_hbox.addWidget(self.lbl_profile_count)
        p_layout.addLayout(p_ctrl_hbox)

        self.radio_all.toggled.connect(self._on_profile_mode_changed)
        self.radio_group.toggled.connect(self._on_profile_mode_changed)
        self.radio_range.toggled.connect(self._on_profile_mode_changed)
        self._on_profile_mode_changed()

        scroll_layout.addWidget(grp_profiles)

        # 2. Side-by-side: Seed Links & Comments Management
        links_comm_hbox = QHBoxLayout()
        links_comm_hbox.setSpacing(12)

        # Seed Links Box
        grp_links = QGroupBox("2. Target Seed Reel Links")
        grp_links.setStyleSheet("QGroupBox { border-color: #06b6d4; } QGroupBox::title { color: #22d3ee; }")
        links_lay = QVBoxLayout(grp_links)
        links_lay.setSpacing(6)

        links_hdr = QHBoxLayout()
        links_desc = QLabel("Reel Links to Train (1 per line):")
        links_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        btn_import_links = QPushButton("📁 Import Links TXT")
        btn_import_links.setCursor(Qt.PointingHandCursor)
        btn_import_links.setStyleSheet("background: #164e63; color: #a5f3fc; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
        btn_import_links.clicked.connect(self._import_links_txt)
        links_hdr.addWidget(links_desc)
        links_hdr.addStretch()
        links_hdr.addWidget(btn_import_links)
        links_lay.addLayout(links_hdr)

        self.txt_seed_links = QTextEdit()
        self.txt_seed_links.setMinimumHeight(160)
        self.txt_seed_links.setPlaceholderText("https://www.facebook.com/reel/123456789\nhttps://www.facebook.com/reel/987654321")
        links_lay.addWidget(self.txt_seed_links)
        links_comm_hbox.addWidget(grp_links, 1)

        # 3. Clean Engagement Comments Box
        grp_comm = QGroupBox("3. 💬 Engagement Comments")
        grp_comm.setStyleSheet("QGroupBox { border-color: #d97706; } QGroupBox::title { color: #fbbf24; }")
        comm_lay = QVBoxLayout(grp_comm)
        comm_lay.setSpacing(6)

        comm_hdr = QHBoxLayout()
        comm_desc = QLabel("Comments to Post (1 per line):")
        comm_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        
        btn_reset_comm = QPushButton("🔄 Default")
        btn_reset_comm.setCursor(Qt.PointingHandCursor)
        btn_reset_comm.setStyleSheet("background: #451a03; color: #fde68a; font-size: 11px; padding: 3px 8px; border-radius: 5px; font-weight: 700;")
        btn_reset_comm.clicked.connect(self._reset_default_comments)

        btn_import_comm = QPushButton("📁 Import TXT")
        btn_import_comm.setCursor(Qt.PointingHandCursor)
        btn_import_comm.setStyleSheet("background: #78350f; color: #fef3c7; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
        btn_import_comm.clicked.connect(self._import_comments_txt)

        comm_hdr.addWidget(comm_desc)
        comm_hdr.addStretch()
        comm_hdr.addWidget(btn_reset_comm)
        comm_hdr.addWidget(btn_import_comm)
        comm_lay.addLayout(comm_hdr)

        self.txt_comments = QTextEdit()
        self.txt_comments.setMinimumHeight(160)
        self.txt_comments.setPlaceholderText("Awesome video! Loved the presentation! ❤️🔥\nThis is super insightful and helpful, thanks for sharing! 💡👏\nGreat content as always, keep up the fantastic work! 🚀💯")
        comm_lay.addWidget(self.txt_comments)
        links_comm_hbox.addWidget(grp_comm, 1)

        scroll_layout.addLayout(links_comm_hbox)

        # 4. Execution & Delay Settings
        grp_settings = QGroupBox("4. Execution & Delay Settings")
        grp_settings.setStyleSheet("QGroupBox { border-color: #7c3aed; } QGroupBox::title { color: #c084fc; }")
        s_layout = QGridLayout(grp_settings)
        s_layout.setContentsMargins(14, 12, 14, 12)
        s_layout.setHorizontalSpacing(16)
        s_layout.setVerticalSpacing(10)

        s_layout.addWidget(QLabel("Watch Time / Delay (s):"), 0, 0)
        self.spin_watch_delay = QSpinBox()
        self.spin_watch_delay.setRange(1, 60)
        self.spin_watch_delay.setValue(3)
        self.spin_watch_delay.setToolTip("Fast-train watch delay per video (3-4s ensures high algorithm signal registration).")
        s_layout.addWidget(self.spin_watch_delay, 0, 1)

        s_layout.addWidget(QLabel("Parallel Concurrent Browsers:"), 0, 2)
        self.spin_parallel = QSpinBox()
        self.spin_parallel.setRange(1, 20)
        self.spin_parallel.setValue(3)
        self.spin_parallel.setToolTip("Number of browser profiles to run concurrently in parallel.")
        s_layout.addWidget(self.spin_parallel, 0, 3)

        self.chk_headless = QCheckBox("Run Headless (Background Mode)")
        self.chk_headless.setChecked(False)
        self.chk_headless.setToolTip("Run browsers without opening visible windows.")
        s_layout.addWidget(self.chk_headless, 1, 0, 1, 2)

        lbl_seq = QLabel("⚡ Fast-Train Mode: ~1-2 min per profile | Auto-Login ➜ Interested ➜ Follow ➜ Like ➜ Feed Lock")
        lbl_seq.setStyleSheet("color: #a78bfa; font-size: 11px; font-style: italic;")
        s_layout.addWidget(lbl_seq, 1, 2, 1, 2)

        scroll_layout.addWidget(grp_settings)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # ----------------------------------------------------
        # Action Bar & Progress
        # ----------------------------------------------------
        action_layout = QHBoxLayout()
        self.btn_start = QPushButton("🚀 Start Algorithm Trainer Bot")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                color: #ffffff;
                font-size: 13.5px;
                font-weight: 800;
                padding: 10px 24px;
                border-radius: 8px;
                border: 1px solid #6366f1;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #0891b2);
            }
            QPushButton:disabled {
                background: #334155;
                color: #64748b;
                border: none;
            }
        """)
        self.btn_start.clicked.connect(self._start_bot)

        self.btn_stop = QPushButton("🛑 Stop Bot")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background: #991b1b;
                color: #ffffff;
                font-size: 13px;
                font-weight: 800;
                padding: 10px 20px;
                border-radius: 8px;
                border: 1px solid #ef4444;
            }
            QPushButton:hover { background: #b91c1c; }
            QPushButton:disabled { background: #292524; color: #57534e; border: none; }
        """)
        self.btn_stop.clicked.connect(self._stop_bot)

        action_layout.addWidget(self.btn_start, 3)
        action_layout.addWidget(self.btn_stop, 1)
        main_layout.addLayout(action_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #111827;
                border: 1px solid #1e293b;
                border-radius: 6px;
                height: 18px;
                text-align: center;
                color: #f8fafc;
                font-size: 10.5px;
                font-weight: 700;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Real-time Activity Log Console
        grp_log = QGroupBox("Live Activity Log")
        grp_log.setStyleSheet("QGroupBox { border-color: #334155; } QGroupBox::title { color: #94a3b8; }")
        log_lay = QVBoxLayout(grp_log)
        log_lay.setContentsMargins(10, 10, 10, 10)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(130)
        self.txt_log.setStyleSheet("""
            QTextEdit {
                background-color: #030712;
                color: #e2e8f0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11.5px;
                border: 1px solid #1f2937;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        log_lay.addWidget(self.txt_log)
        main_layout.addWidget(grp_log)

    def _populate_groups(self):
        """Populates the group dropdown from ProfileManager or discovered profiles."""
        groups = set()
        if self.profile_mgr and hasattr(self.profile_mgr, "get_groups"):
            try:
                for g in self.profile_mgr.get_groups():
                    if g:
                        groups.add(str(g))
            except Exception:
                pass

        for p in self.all_profiles:
            grp = p.get("group")
            if grp:
                groups.add(str(grp))

        if not groups:
            groups = {"Default", "Social", "Personal"}

        self.combo_groups.clear()
        for g in sorted(groups):
            self.combo_groups.addItem(g)

    def _on_profile_mode_changed(self):
        is_range = self.radio_range.isChecked()
        is_group = self.radio_group.isChecked()

        self.lbl_range.setVisible(is_range)
        self.txt_range.setVisible(is_range)
        self.lbl_group.setVisible(is_group)
        self.combo_groups.setVisible(is_group)

    def _load_defaults(self):
        """Pre-populates default seed links and comments."""
        base_dir = Path(__file__).resolve().parent
        
        links_file = base_dir / "default_seed_links.txt"
        if links_file.exists():
            lines = load_lines_from_txt_file(str(links_file))
            if lines:
                self.txt_seed_links.setText("\n".join(lines))

        comm_file = base_dir / "default_comments.txt"
        if comm_file.exists():
            lines = load_lines_from_txt_file(str(comm_file))
            if lines:
                self.txt_comments.setText("\n".join(lines))
        else:
            self._reset_default_comments()

    def _reset_default_comments(self):
        self.txt_comments.setText("\n".join(DEFAULT_ALGO_TRAINER_COMMENTS))

    def _import_links_txt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Seed Reel Links File", "", "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return
        lines = load_lines_from_txt_file(file_path)
        if lines:
            existing = self.txt_seed_links.toPlainText().strip()
            new_text = existing + ("\n" if existing else "") + "\n".join(lines)
            self.txt_seed_links.setText(new_text)
            self._append_log(f"📥 Imported {len(lines)} seed link(s) from {Path(file_path).name}")
        else:
            QMessageBox.warning(self, "Import Links", "No valid links found in the selected file.")

    def _import_comments_txt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Comments File", "", "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return
        lines = load_lines_from_txt_file(file_path)
        if lines:
            existing = self.txt_comments.toPlainText().strip()
            new_text = existing + ("\n" if existing else "") + "\n".join(lines)
            self.txt_comments.setText(new_text)
            self._append_log(f"📥 Imported {len(lines)} comment(s) from {Path(file_path).name}")
        else:
            QMessageBox.warning(self, "Import Comments", "No valid comments found in the selected file.")

    def _append_log(self, text: str):
        self.txt_log.append(text)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _resolve_selected_profiles(self) -> List[Dict[str, Any]]:
        """Resolves target profiles list based on user's active selection mode."""
        if self.radio_all.isChecked():
            return list(self.all_profiles)

        if self.radio_group.isChecked():
            selected_grp = self.combo_groups.currentText().strip()
            return [p for p in self.all_profiles if str(p.get("group", "")).strip() == selected_grp]

        if self.radio_range.isChecked():
            range_str = self.txt_range.text().strip()
            return filter_by_profile_numbers(self.all_profiles, range_str)

        return list(self.all_profiles)

    def _start_bot(self):
        """Validates inputs and starts the multi-threaded automation engine."""
        selected_profiles = self._resolve_selected_profiles()
        if not selected_profiles:
            QMessageBox.warning(
                self,
                "No Profiles Selected",
                "Please select at least one Facebook Profile to train the algorithm."
            )
            return

        raw_links = self.txt_seed_links.toPlainText()
        seed_links = parse_raw_text_lines(raw_links)
        if not seed_links:
            QMessageBox.warning(
                self,
                "No Seed Links",
                "Please enter or import at least one Facebook Reel link in Section 2."
            )
            return

        raw_comments = self.txt_comments.toPlainText()
        comments_list = parse_raw_text_lines(raw_comments)
        if not comments_list:
            comments_list = DEFAULT_ALGO_TRAINER_COMMENTS

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.txt_log.clear()

        self._append_log(f"🚀 Initializing Facebook Reels Algorithm Trainer Engine...")
        self._append_log(f"📋 Profiles to process: {len(selected_profiles)}")
        self._append_log(f"🎯 Target Seed Reel Links: {len(seed_links)}")
        self._append_log(f"💬 Engagement Comments loaded: {len(comments_list)}")
        self._append_log(f"⚡ Parallel Concurrent Browsers: {self.spin_parallel.value()}")
        self._append_log(f"⏳ Watch Time / Action Delay: {self.spin_watch_delay.value()}s")
        self._append_log("----------------------------------------------------------------------")

        self.worker_thread = FbReelsAlgoTrainerEngine(
            profile_mgr=self.profile_mgr,
            profiles_list=selected_profiles,
            seed_links=seed_links,
            comments_list=comments_list,
            watch_delay=self.spin_watch_delay.value(),
            max_concurrent_browsers=self.spin_parallel.value(),
            headless=self.chk_headless.isChecked(),
            enable_interested=True,
            enable_follow=True,
            enable_like=True,
            enable_comments=True,
            enable_ai_comments=True,
            ai_comment_tone="Natural Fan & Appreciation",
            ai_custom_instruction="",
            parent=self
        )
        self.worker_thread.log_emitted.connect(self._append_log)
        self.worker_thread.progress_updated.connect(self._on_progress_updated)
        self.worker_thread.finished_signal.connect(self._on_bot_finished)
        self.worker_thread.start()

    def _on_progress_updated(self, cur: int, total: int):
        if total > 0:
            pct = int((cur / total) * 100)
            self.progress_bar.setValue(pct)

    def _stop_bot(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.btn_stop.setEnabled(False)
            self._append_log("🛑 Stopping bot... Waiting for workers to terminate safely.")

    def _on_bot_finished(self, success: bool, msg: str):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100 if success else 0)
        self._append_log(f"\n🏁 [{ 'SUCCESS' if success else 'STOPPED' }] {msg}")
        QMessageBox.information(self, "Reels Algorithm Trainer Bot", msg)

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Bot Running",
                "The Algorithm Trainer Bot is currently running. Stop and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker_thread.stop()
                event.accept()
            else:
                event.ignore()
                return
        event.accept()


def launch_ui(profile_mgr: Any = None, parent: Optional[QWidget] = None) -> FbReelsAlgoTrainerDialog:
    dlg = FbReelsAlgoTrainerDialog(profile_mgr=profile_mgr, parent=parent)
    dlg.show()
    return dlg


def main(profile_mgr: Any = None, parent: Optional[QWidget] = None):
    app = QApplication.instance()
    is_standalone = False
    if not app:
        app = QApplication(sys.argv)
        is_standalone = True

    dlg = FbReelsAlgoTrainerDialog(profile_mgr=profile_mgr, parent=parent)
    dlg.show()
    if is_standalone:
        sys.exit(app.exec())
    return dlg


if __name__ == "__main__":
    main()
