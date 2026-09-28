# -*- coding: utf-8 -*-
"""
User Interface (PySide6) for Facebook Reels Comment Marketing Bot:
- Modern Cyberpunk Dark Theme matching srkBrowser Ecosystem
- Profile group & range selector
- Target keywords & comments management with TXT import
- Embedded CommentFormatterDialog tool
- Live execution progress & colorized logs
- Status badge: 🟢 srkBrowser Active
"""

import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Callable, Union

from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QCheckBox, QRadioButton, QButtonGroup, QGroupBox, QFrame, QProgressBar,
    QFileDialog, QMessageBox, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QPoint, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QColor, QCursor, QIcon

from fb_comment_marketing_helpers import (
    get_base_dir,
    get_profiles_dir,
    load_lines_from_txt_file,
    parse_raw_text_lines,
    filter_by_profile_numbers,
    CommentFormatterDialog
)
from fb_comment_marketing_engine import FbCommentMarketingThread


class FbCommentMarketingDialog(QDialog):
    """Luxury Dark Cyberpunk Dialog for Facebook Reels Comment Marketing Bot."""

    def __init__(self, profile_mgr: Any = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.worker_thread: Optional[FbCommentMarketingThread] = None

        self.setWindowTitle("⚡ Facebook Reels Comment Marketing Bot - srkBrowser")
        self.resize(920, 780)
        self.setMinimumSize(850, 700)

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
            # Direct scan of profiles directory
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
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 18)
        main_layout.setSpacing(12)

        # ----------------------------------------------------
        # Header Row
        # ----------------------------------------------------
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111827, stop:1 #1e1b4b);
                border: 1px solid #312e81;
                border-radius: 12px;
                padding: 10px 16px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 6, 10, 6)

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("💬 Facebook Reels Comment Marketing Bot")
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 900; color: #ffffff; border: none; background: transparent;")
        sub_lbl = QLabel("Keyword-driven targeted commenting with anti-ban humanized typing & auto-follow")
        sub_lbl.setStyleSheet("font-size: 11.5px; color: #a5b4fc; border: none; background: transparent;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)
        h_layout.addLayout(title_vbox)

        h_layout.addStretch()

        # Status badge & Developer credit
        badge_vbox = QVBoxLayout()
        badge_vbox.setAlignment(Qt.AlignRight)

        self.lbl_status_badge = QLabel("🟢 srkBrowser Active")
        self.lbl_status_badge.setStyleSheet("""
            background-color: #064e3b;
            color: #34d399;
            font-size: 11px;
            font-weight: 800;
            border: 1px solid #05966988;
            border-radius: 6px;
            padding: 4px 12px;
        """)

        dev_lbl = QLabel("Developed with ❤️ by SRK Shofiqul")
        dev_lbl.setStyleSheet("font-size: 10px; color: #38bdf8; font-weight: bold; border: none; background: transparent;")

        badge_vbox.addWidget(self.lbl_status_badge, alignment=Qt.AlignRight)
        badge_vbox.addWidget(dev_lbl, alignment=Qt.AlignRight)
        h_layout.addLayout(badge_vbox)

        main_layout.addWidget(header_frame)

        # ----------------------------------------------------
        # Scroll Area Content
        # ----------------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        # 1. Target Profiles Box
        grp_profiles = QGroupBox("1. Target Profiles Selection")
        grp_profiles.setStyleSheet("QGroupBox { border-color: #0284c7; } QGroupBox::title { color: #38bdf8; }")
        p_layout = QVBoxLayout(grp_profiles)
        p_layout.setSpacing(8)

        r_layout = QHBoxLayout()
        self.rad_all = QRadioButton(f"All Profiles ({len(self.all_profiles)} Profiles)")
        self.rad_group = QRadioButton("Target Group")
        self.rad_numbers = QRadioButton("Profile Numbers / Range")
        self.rad_all.setChecked(True)

        self.p_group = QButtonGroup(self)
        self.p_group.addButton(self.rad_all)
        self.p_group.addButton(self.rad_group)
        self.p_group.addButton(self.rad_numbers)

        r_layout.addWidget(self.rad_all)
        r_layout.addWidget(self.rad_group)
        r_layout.addWidget(self.rad_numbers)
        r_layout.addStretch()
        p_layout.addLayout(r_layout)

        # Group dropdown & Range Input
        self.sub_p_layout = QHBoxLayout()
        self.lbl_group = QLabel("Select Group:")
        self.combo_groups = QComboBox()
        # Collect groups
        groups_set = set()
        if self.profile_mgr and hasattr(self.profile_mgr, "groups"):
            for g in self.profile_mgr.groups:
                if g and str(g).strip():
                    groups_set.add(str(g).strip())
        for p in self.all_profiles:
            grp = str(p.get("group", "Default")).strip()
            if grp:
                groups_set.add(grp)
        groups = sorted(list(groups_set))
        if not groups:
            groups = ["Default"]
        self.combo_groups.addItems(groups)
        if "FB 01" in groups:
            fb_idx = self.combo_groups.findText("FB 01")
            if fb_idx >= 0:
                self.combo_groups.setCurrentIndex(fb_idx)

        self.lbl_range = QLabel("Profile Numbers (e.g. 1-10 or 1,3,5):")
        self.txt_range = QLineEdit()
        self.txt_range.setPlaceholderText("1-10 or Profile001, Profile005")

        self.sub_p_layout.addWidget(self.lbl_group)
        self.sub_p_layout.addWidget(self.combo_groups)
        self.sub_p_layout.addWidget(self.lbl_range)
        self.sub_p_layout.addWidget(self.txt_range)
        p_layout.addLayout(self.sub_p_layout)

        self.rad_all.toggled.connect(self._update_profile_inputs_visibility)
        self.rad_group.toggled.connect(self._update_profile_inputs_visibility)
        self.rad_numbers.toggled.connect(self._update_profile_inputs_visibility)
        self._update_profile_inputs_visibility()

        scroll_layout.addWidget(grp_profiles)

        # 2. Keywords & Comments Row (Side by Side)
        kw_comm_hbox = QHBoxLayout()
        kw_comm_hbox.setSpacing(12)

        # Keywords Box
        grp_kw = QGroupBox("2. Target Link Keywords Filter")
        grp_kw.setStyleSheet("QGroupBox { border-color: #059669; } QGroupBox::title { color: #34d399; }")
        kw_lay = QVBoxLayout(grp_kw)
        kw_lay.setSpacing(6)

        kw_hdr = QHBoxLayout()
        kw_desc = QLabel("Matches words/links in comments (1 per line):")
        kw_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        btn_import_kw = QPushButton("📁 Import TXT")
        btn_import_kw.setCursor(Qt.PointingHandCursor)
        btn_import_kw.setStyleSheet("background: #064e3b; color: #a7f3d0; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
        btn_import_kw.clicked.connect(self._import_keywords_txt)
        kw_hdr.addWidget(kw_desc)
        kw_hdr.addStretch()
        kw_hdr.addWidget(btn_import_kw)
        kw_lay.addLayout(kw_hdr)

        self.txt_keywords = QTextEdit()
        self.txt_keywords.setMinimumHeight(130)
        self.txt_keywords.setPlaceholderText("whatsapp.com\nwa.me\nchat.whatsapp.com\nt.me\ntelegram.me\ninbox\ndm us")
        kw_lay.addWidget(self.txt_keywords)
        kw_comm_hbox.addWidget(grp_kw)

        # Comments Box - Clean Single-Box 100% Autonomous Viral Hook Engine
        grp_comm = QGroupBox("3. 🎬 Video Marketing & Channel Links")
        grp_comm.setStyleSheet("QGroupBox { border-color: #d97706; } QGroupBox::title { color: #fbbf24; }")
        comm_lay = QVBoxLayout(grp_comm)
        comm_lay.setSpacing(6)

        comm_hdr = QHBoxLayout()
        lbl_offer = QLabel("🎯 Full Video Links (আপনার ২/৩টি ভিডিও বা চ্যানেল লিংক):")
        lbl_offer.setStyleSheet("color: #fbbf24; font-weight: bold; font-size: 11px;")
        
        btn_fmt = QPushButton("🛠️ Formatter Tool")
        btn_fmt.setCursor(Qt.PointingHandCursor)
        btn_fmt.setStyleSheet("background: #451a03; color: #fde68a; font-size: 11px; padding: 3px 8px; border-radius: 5px; font-weight: 700;")
        btn_fmt.clicked.connect(self._open_formatter_tool)

        btn_import_comm = QPushButton("📁 Import TXT")
        btn_import_comm.setCursor(Qt.PointingHandCursor)
        btn_import_comm.setStyleSheet("background: #78350f; color: #fef3c7; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
        btn_import_comm.clicked.connect(self._import_comments_txt)

        comm_hdr.addWidget(lbl_offer)
        comm_hdr.addStretch()
        comm_hdr.addWidget(btn_fmt)
        comm_hdr.addWidget(btn_import_comm)
        comm_lay.addLayout(comm_hdr)

        self.txt_user_offer = QTextEdit()
        self.txt_user_offer.setMinimumHeight(130)
        self.txt_user_offer.setPlaceholderText("এখানে আপনার ২ বা ৩টি ভিডিও/চ্যানেল লিংক দিন, যেমন:\nhttps://whatsapp.com/channel/0029Vb8mCRNBA1ex8HV4OU0E\nhttps://whatsapp.com/channel/0029Vb9DHTaDDmFTD0BFeH1s\n\n(সফটওয়্যার স্বয়ংক্রিয়ভাবে আকর্ষণীয় 'Watch Full Video 🎬🔥👇' জাতীয় ভাইরাল ইংলিশ হুক ও ইমোজি সহ কমেন্ট পোস্ট করবে!)")
        comm_lay.addWidget(self.txt_user_offer)

        lbl_ai_badge = QLabel("✨ Smart Viral Hook Engine — সম্পূর্ণ ইংলিশে আকর্ষণীয় 'Watch Full Video 🎬🔥👇' টাইটেল ও ইমোজি সহ আপনার লিংক পোস্ট করবে।")
        lbl_ai_badge.setStyleSheet("color: #34d399; font-size: 10.5px; font-weight: 600;")
        lbl_ai_badge.setWordWrap(True)
        comm_lay.addWidget(lbl_ai_badge)

        self.txt_comments = self.txt_user_offer

        kw_comm_hbox.addWidget(grp_comm)

        scroll_layout.addLayout(kw_comm_hbox)

        # 3. Delays & Execution Settings
        grp_settings = QGroupBox("4. Delays & Execution Settings")
        grp_settings.setStyleSheet("QGroupBox { border-color: #7c3aed; } QGroupBox::title { color: #c084fc; }")
        s_layout = QGridLayout(grp_settings)
        s_layout.setContentsMargins(14, 12, 14, 12)
        s_layout.setHorizontalSpacing(16)
        s_layout.setVerticalSpacing(10)

        # Row 0
        s_layout.addWidget(QLabel("Target Comments (per ID):"), 0, 0)
        self.spin_max_comments = QSpinBox()
        self.spin_max_comments.setRange(1, 500)
        self.spin_max_comments.setValue(5)
        s_layout.addWidget(self.spin_max_comments, 0, 1)

        s_layout.addWidget(QLabel("Max Reels Scan Limit:"), 0, 2)
        self.spin_max_reels = QSpinBox()
        self.spin_max_reels.setRange(1, 2000)
        self.spin_max_reels.setValue(50)
        s_layout.addWidget(self.spin_max_reels, 0, 3)

        # Row 1
        s_layout.addWidget(QLabel("Reel Scan Delay (s):"), 1, 0)
        self.spin_scan_delay = QSpinBox()
        self.spin_scan_delay.setRange(0, 60)
        self.spin_scan_delay.setValue(1)
        s_layout.addWidget(self.spin_scan_delay, 1, 1)

        s_layout.addWidget(QLabel("Post-Comment Delay (s):"), 1, 2)
        self.spin_comment_delay = QSpinBox()
        self.spin_comment_delay.setRange(0, 300)
        self.spin_comment_delay.setValue(1)
        s_layout.addWidget(self.spin_comment_delay, 1, 3)

        # Aliases for backward compatibility
        self.spin_scan_min = self.spin_scan_delay
        self.spin_scan_max = self.spin_scan_delay
        self.spin_watch_min = self.spin_comment_delay
        self.spin_watch_max = self.spin_comment_delay

        # Row 2
        s_layout.addWidget(QLabel("Parallel Concurrent Browsers:"), 2, 0)
        self.spin_parallel = QSpinBox()
        self.spin_parallel.setRange(1, 20)
        self.spin_parallel.setValue(1)
        s_layout.addWidget(self.spin_parallel, 2, 1)

        self.chk_headless = QCheckBox("Run Headless (Background Mode)")
        self.chk_headless.setChecked(False)
        s_layout.addWidget(self.chk_headless, 2, 2, 1, 2)

        scroll_layout.addWidget(grp_settings)

        # 5. Live Multi-Profile Real-Time Tracker
        grp_stats = QGroupBox("5. 📊 Live Real-Time Multi-Profile Statistics & Monitor")
        grp_stats.setStyleSheet("QGroupBox { border-color: #06b6d4; } QGroupBox::title { color: #22d3ee; }")
        stats_lay = QVBoxLayout(grp_stats)
        stats_lay.setContentsMargins(14, 12, 14, 12)
        stats_lay.setSpacing(10)

        # 4 KPI Metrics Grid
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(12)
        kpi_grid.setVerticalSpacing(8)

        def make_kpi_card(title_text: str, default_val: str, val_color: str):
            f = QFrame()
            f.setStyleSheet("""
                QFrame {
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 6px 12px;
                }
            """)
            flay = QVBoxLayout(f)
            flay.setContentsMargins(4, 4, 4, 4)
            flay.setSpacing(2)
            t_lbl = QLabel(title_text)
            t_lbl.setStyleSheet("color: #94a3b8; font-size: 10.5px; font-weight: 600; border: none; background: transparent;")
            v_lbl = QLabel(default_val)
            v_lbl.setStyleSheet(f"color: {val_color}; font-size: 14px; font-weight: 800; border: none; background: transparent;")
            flay.addWidget(t_lbl)
            flay.addWidget(v_lbl)
            return f, v_lbl

        card_p, self.lbl_stat_profile = make_kpi_card("Active Profile", "None", "#38bdf8")
        card_cur, self.lbl_stat_cur_comments = make_kpi_card("Profile Comments", "0 / 0", "#34d399")
        card_tot, self.lbl_stat_total_comments = make_kpi_card("Total Posted", "0", "#fbbf24")
        card_scanned, self.lbl_stat_reels_scanned = make_kpi_card("Reels Scanned", "0", "#a78bfa")

        kpi_grid.addWidget(card_p, 0, 0)
        kpi_grid.addWidget(card_cur, 0, 1)
        kpi_grid.addWidget(card_tot, 0, 2)
        kpi_grid.addWidget(card_scanned, 0, 3)
        stats_lay.addLayout(kpi_grid)

        # Status Summary Box
        self.txt_profile_summary = QTextEdit()
        self.txt_profile_summary.setReadOnly(True)
        self.txt_profile_summary.setFixedHeight(70)
        self.txt_profile_summary.setPlaceholderText("Real-Time Multi-Profile Status will display here as workers progress...")
        self.txt_profile_summary.setStyleSheet("""
            QTextEdit {
                background-color: #030712;
                border: 1px solid #1e293b;
                border-radius: 6px;
                color: #a5b4fc;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 6px;
            }
        """)
        stats_lay.addWidget(self.txt_profile_summary)

        scroll_layout.addWidget(grp_stats)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # ----------------------------------------------------
        # Action Bar & Progress
        # ----------------------------------------------------
        action_layout = QHBoxLayout()
        self.btn_start = QPushButton("🚀 Start Comment Marketing Bot")
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

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 7px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #818cf8);
                border-radius: 7px;
            }
        """)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Terminal Log Box
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(150)
        self.txt_log.setStyleSheet("""
            QTextEdit {
                background-color: #030712;
                border: 1px solid #1f2937;
                border-radius: 8px;
                color: #38bdf8;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        main_layout.addWidget(self.txt_log)

    def _update_profile_inputs_visibility(self):
        is_grp = self.rad_group.isChecked()
        is_num = self.rad_numbers.isChecked()
        self.lbl_group.setVisible(is_grp)
        self.combo_groups.setVisible(is_grp)
        self.lbl_range.setVisible(is_num)
        self.txt_range.setVisible(is_num)

    def _load_defaults(self):
        """Loads default keywords and comments from .txt files if available."""
        bot_dir = Path(__file__).resolve().parent

        kw_file = bot_dir / "default_keywords.txt"
        if kw_file.exists():
            kws = load_lines_from_txt_file(str(kw_file))
            if kws:
                self.txt_keywords.setPlainText("\n".join(kws))

        comm_file = bot_dir / "default_comments.txt"
        if comm_file.exists():
            comms = load_lines_from_txt_file(str(comm_file))
            if comms:
                self.txt_comments.setPlainText("\n".join(comms))

        self._append_log("⚡ Ready. Select target profiles, configure keywords, and click Start.")

    def _append_log(self, text: str):
        self.txt_log.append(text)
        sb = self.txt_log.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _import_keywords_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Target Keywords (.txt)", "", "Text Files (*.txt);;All Files (*)")
        if path:
            lines = load_lines_from_txt_file(path)
            if lines:
                self.txt_keywords.setPlainText("\n".join(lines))
                self._append_log(f"📁 Imported {len(lines)} keywords from: {Path(path).name}")
            else:
                QMessageBox.warning(self, "Empty File", "No non-empty keyword lines found.")

    def _import_comments_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Marketing Comments (.txt)", "", "Text Files (*.txt);;All Files (*)")
        if path:
            lines = load_lines_from_txt_file(path)
            if lines:
                self.txt_comments.setPlainText("\n".join(lines))
                self._append_log(f"📁 Imported {len(lines)} marketing comments from: {Path(path).name}")
            else:
                QMessageBox.warning(self, "Empty File", "No non-empty comment lines found.")

    def _open_formatter_tool(self):
        dlg = CommentFormatterDialog(self)
        if dlg.exec() == QDialog.Accepted:
            formatted = dlg.get_formatted_text()
            if formatted:
                self.txt_comments.setPlainText(formatted)
                self._append_log(f"🛠️ Applied formatted comments from Comment Formatter Tool.")

    def _get_target_profiles(self) -> List[Dict[str, Any]]:
        if self.rad_all.isChecked():
            return list(self.all_profiles)

        if self.rad_group.isChecked():
            target_grp = self.combo_groups.currentText().strip().lower()
            return [p for p in self.all_profiles if str(p.get("group", "Default")).strip().lower() == target_grp]

        if self.rad_numbers.isChecked():
            range_str = self.txt_range.text().strip()
            if not range_str:
                return []
            return filter_by_profile_numbers(self.all_profiles, range_str)

        return list(self.all_profiles)

    def _start_bot(self):
        target_profiles = self._get_target_profiles()
        if not target_profiles:
            QMessageBox.warning(self, "No Profiles", "No profiles found matching the selected criteria. Please verify your profiles.")
            return

        keywords = parse_raw_text_lines(self.txt_keywords.toPlainText())
        if not keywords:
            QMessageBox.warning(self, "No Keywords", "Please enter or import at least 1 target keyword to match.")
            return

        user_offer = self.txt_user_offer.toPlainText().strip()
        comments = parse_raw_text_lines(self.txt_comments.toPlainText())
        if not comments:
            if user_offer:
                comments = [user_offer]
            else:
                QMessageBox.warning(self, "No Comments", "Please enter your Marketing Offer/Link or at least 1 marketing comment to post.")
                return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.txt_log.clear()
        self.lbl_stat_profile.setText("Starting...")
        self.lbl_stat_cur_comments.setText(f"0 / {self.spin_max_comments.value()}")
        self.lbl_stat_total_comments.setText("0")
        self.lbl_stat_reels_scanned.setText("0")
        self.txt_profile_summary.clear()

        self.worker_thread = FbCommentMarketingThread(
            profile_mgr=self.profile_mgr,
            profiles_list=target_profiles,
            target_keywords=keywords,
            comments_list=comments,
            max_comments=self.spin_max_comments.value(),
            max_reels=self.spin_max_reels.value(),
            comment_delay=self.spin_comment_delay.value(),
            scan_delay=self.spin_scan_delay.value(),
            min_delay=self.spin_comment_delay.value(),
            max_delay=self.spin_comment_delay.value(),
            scan_min_delay=self.spin_scan_delay.value(),
            scan_max_delay=self.spin_scan_delay.value(),
            max_concurrent_browsers=self.spin_parallel.value(),
            headless=self.chk_headless.isChecked(),
            enable_ai_comments=True,
            ai_prompt_instruction="Generate an exciting, high-converting English hook with viral emojis for watching the full video via provided links.",
            user_offer_text=user_offer,
            parent=self
        )
        self.worker_thread.log_emitted.connect(self._append_log)
        self.worker_thread.progress_updated.connect(self._on_progress_updated)
        self.worker_thread.stats_updated.connect(self._on_stats_updated)
        self.worker_thread.finished_signal.connect(self._on_bot_finished)
        self.worker_thread.start()

    def _on_stats_updated(self, stats: dict):
        if not isinstance(stats, dict):
            return
        act_p = stats.get("active_profile", "")
        if act_p:
            self.lbl_stat_profile.setText(str(act_p))
        tot_posted = stats.get("total_posted", 0)
        self.lbl_stat_total_comments.setText(str(tot_posted))
        tot_scanned = stats.get("total_scanned", 0)
        self.lbl_stat_reels_scanned.setText(str(tot_scanned))

        p_status = stats.get("profile_status", {})
        if act_p and act_p in p_status:
            self.lbl_stat_cur_comments.setText(str(p_status[act_p]))

        if p_status:
            lines = [f"• {p}: {st}" for p, st in p_status.items()]
            self.txt_profile_summary.setPlainText("\n".join(lines))
            sb = self.txt_profile_summary.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

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
        QMessageBox.information(self, "Comment Marketing Bot", msg)

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Bot Running",
                "The Comment Marketing Bot is currently running. Stop and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker_thread.stop()
                self.worker_thread.wait(3000)
                event.accept()
            else:
                event.ignore()
                return
        event.accept()


def launch_ui(profile_mgr: Any = None, parent: Optional[QWidget] = None) -> FbCommentMarketingDialog:
    dlg = FbCommentMarketingDialog(profile_mgr=profile_mgr, parent=parent)
    dlg.show()
    return dlg


def main(profile_mgr: Any = None, parent: Optional[QWidget] = None):
    app = QApplication.instance()
    is_standalone = False
    if not app:
        app = QApplication(sys.argv)
        is_standalone = True

    dlg = FbCommentMarketingDialog(profile_mgr=profile_mgr, parent=parent)
    dlg.show()
    if is_standalone:
        sys.exit(app.exec())
    return dlg


if __name__ == "__main__":
    main()
