import os
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, QThread, Signal, QPoint, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QScrollArea, QFrame,
    QProgressBar, QMessageBox
)

from fb_business_creator_engine import execute_bm_creation_flow


class BmCreationWorker(QThread):
    event_signal = Signal(dict)

    def __init__(self, user_data_dir: str, max_bms: int, profile_data: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.user_data_dir = user_data_dir
        self.max_bms = max_bms
        self.profile_data = profile_data or {}

    def run(self):
        execute_bm_creation_flow(
            user_data_dir=self.user_data_dir,
            max_bms=self.max_bms,
            profile_data=self.profile_data,
            progress_cb=lambda evt: self.event_signal.emit(evt)
        )


class FbBusinessCreatorModal(QDialog):
    """
    Sleek Cyber FB Business Manager Creator Modal.
    Features live background BM creation, compact streamed rows, explicit [Copy] buttons, and limit alerts.
    """
    def __init__(
        self,
        profile_data: Optional[Dict[str, Any]] = None,
        user_data_dir: str = "",
        parent: Optional[QWidget] = None,
        profile_mgr: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(parent)
        self.profile_data = profile_data or {}
        self.user_data_dir = user_data_dir
        self.profile_mgr = profile_mgr
        self._drag_pos = QPoint()
        self.created_bms: List[Dict[str, Any]] = []

        if not self.profile_data and self.profile_mgr and hasattr(self.profile_mgr, "get_all_profiles"):
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

        self.setWindowTitle(f"FB Business Creator — {self.p_num_str}")
        self.setFixedSize(620, 560)
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

        # Main Card container
        self.card = QFrame()
        self.card.setObjectName("MainCard")
        self.card.setStyleSheet("""
            #MainCard {
                background: #0d0d1a;
                border: 2px solid #6366f1;
                border-radius: 18px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(10)

        # 1. Header Bar
        h_head = QHBoxLayout()
        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        
        lbl_title = QLabel(f"Business Creator — {self.p_num_str}")
        lbl_title.setStyleSheet("""
            color: #ffffff;
            font-size: 16px;
            font-weight: 800;
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: transparent;
            border: none;
        """)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #1e1e2f;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #ef4444; color: white; border-color: #ef4444; }
        """)
        btn_close.clicked.connect(self.reject)

        h_head.addWidget(lbl_icon)
        h_head.addWidget(lbl_title)
        h_head.addStretch()
        h_head.addWidget(btn_close)
        card_layout.addLayout(h_head)

        lbl_sub = QLabel("1-Click Instant Facebook Business Manager Automation in background.")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: -6px; background: transparent; border: none;")
        card_layout.addWidget(lbl_sub)

        # 2. Control Row: SpinBox & Start Button
        ctrl_box = QFrame()
        ctrl_box.setStyleSheet("background: #14142b; border-radius: 12px; padding: 4px; border: 1px solid #232342;")
        h_ctrl = QHBoxLayout(ctrl_box)
        h_ctrl.setContentsMargins(12, 6, 12, 6)

        lbl_count = QLabel("Target BMs:")
        lbl_count.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: 700; border: none;")
        
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 10)
        self.spin_count.setValue(10)
        self.spin_count.setFixedSize(65, 30)
        self.spin_count.setStyleSheet("""
            QSpinBox {
                background: #090914;
                color: #38bdf8;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding-left: 8px;
                font-weight: 800;
                font-size: 13px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
                background: #1e293b;
                border-left: 1px solid #3b82f6;
            }
        """)

        lbl_max_hint = QLabel("(Max: 10)")
        lbl_max_hint.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600; border: none;")

        self.btn_start = QPushButton("⚡ Create Business Managers Now")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #06b6d4);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12.5px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #22d3ee);
            }
            QPushButton:disabled { background: #334155; color: #64748b; }
        """)
        self.btn_start.clicked.connect(self._start_creation)

        h_ctrl.addWidget(lbl_count)
        h_ctrl.addWidget(self.spin_count)
        h_ctrl.addWidget(lbl_max_hint)
        h_ctrl.addStretch()
        h_ctrl.addWidget(self.btn_start)
        card_layout.addWidget(ctrl_box)

        # Status Label & Progress Bar
        self.lbl_status = QLabel("Ready. Click button above to begin creating Business Managers.")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        card_layout.addWidget(self.lbl_status)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setFixedHeight(3)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setVisible(False)
        self.prog_bar.setStyleSheet("""
            QProgressBar { background: #13122c; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #06b6d4); }
        """)
        card_layout.addWidget(self.prog_bar)

        # 3. BM Links Panel (Compact layout)
        panel_box = QFrame()
        panel_box.setStyleSheet("background: #090914; border-radius: 12px; border: 1px solid #1e2038;")
        v_panel = QVBoxLayout(panel_box)
        v_panel.setContentsMargins(12, 8, 12, 8)
        v_panel.setSpacing(4)

        h_pan_top = QHBoxLayout()
        lbl_pan_title = QLabel("⚡ BM LINKS")
        lbl_pan_title.setStyleSheet("color: #a855f7; font-size: 12.5px; font-weight: 800; letter-spacing: 1px; border: none;")
        self.lbl_bm_count = QLabel("Created: 0")
        self.lbl_bm_count.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; border: none;")
        h_pan_top.addWidget(lbl_pan_title)
        h_pan_top.addStretch()
        h_pan_top.addWidget(self.lbl_bm_count)
        v_panel.addLayout(h_pan_top)

        # Scroll Area for generated links
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.links_container = QWidget()
        self.links_layout = QVBoxLayout(self.links_container)
        self.links_layout.setContentsMargins(0, 2, 0, 2)
        self.links_layout.setSpacing(4)
        self.links_layout.addStretch()

        self.scroll.setWidget(self.links_container)
        v_panel.addWidget(self.scroll)
        card_layout.addWidget(panel_box, stretch=1)

        # 4. Limit / Status Toast Banner (Bottom banner)
        self.banner_notice = QFrame()
        self.banner_notice.setVisible(False)
        self.banner_notice.setStyleSheet("background: #4c0519; border-radius: 8px; border: 1px solid #f43f5e; padding: 4px;")
        h_notice = QHBoxLayout(self.banner_notice)
        h_notice.setContentsMargins(10, 4, 10, 4)
        self.lbl_notice = QLabel("")
        self.lbl_notice.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700; border: none; background: transparent;")
        h_notice.addWidget(self.lbl_notice)
        card_layout.addWidget(self.banner_notice)

        # 5. Footer Row: Copy All Links & Close
        h_foot = QHBoxLayout()
        self.btn_copy_all = QPushButton("📋 Copy All BM Links")
        self.btn_copy_all.setEnabled(False)
        self.btn_copy_all.setCursor(Qt.PointingHandCursor)
        self.btn_copy_all.setStyleSheet("""
            QPushButton {
                background: #1e1b4b;
                color: #c7d2fe;
                border: 1px solid #4f46e5;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover { background: #312e81; color: white; }
            QPushButton:disabled { background: #13122c; color: #475569; border-color: #1e2038; }
        """)
        self.btn_copy_all.clicked.connect(self._copy_all_links)

        btn_exit = QPushButton("Exit ✕")
        btn_exit.setCursor(Qt.PointingHandCursor)
        btn_exit.setStyleSheet("""
            QPushButton {
                background: #1e1e2f;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2b2b40; color: white; }
        """)
        btn_exit.clicked.connect(self.accept)

        h_foot.addWidget(self.btn_copy_all)
        h_foot.addStretch()
        h_foot.addWidget(btn_exit)
        card_layout.addLayout(h_foot)

        root.addWidget(self.card)

    def _start_creation(self):
        if not self.user_data_dir or not os.path.exists(self.user_data_dir):
            self.lbl_status.setText("🔴 Error: Profile directory not found.")
            self.lbl_status.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700; border: none;")
            return

        self.btn_start.setEnabled(False)
        self.spin_count.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.banner_notice.setVisible(False)
        self.btn_start.setText("Creating BMs... ⏳")

        max_n = self.spin_count.value()

        self.worker = BmCreationWorker(
            user_data_dir=self.user_data_dir,
            max_bms=max_n,
            profile_data=self.profile_data
        )
        self.worker.event_signal.connect(self._handle_event)
        self.worker.start()

    def _handle_event(self, evt: dict):
        evt_type = evt.get("type")

        if evt_type == "status":
            msg = evt.get("message", "")
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600; border: none;")

        elif evt_type == "progress":
            msg = evt.get("message", "")
            self.lbl_status.setText(msg)

        elif evt_type == "bm_created":
            bm_num = evt.get("bm_num", len(self.created_bms) + 1)
            name = evt.get("name", "Unknown BM")
            b_id = evt.get("business_id", "unknown")
            url = evt.get("url", "")
            
            entry = {"bm_num": bm_num, "name": name, "business_id": b_id, "url": url}
            self.created_bms.append(entry)

            self.lbl_bm_count.setText(f"Created: {len(self.created_bms)}")
            self._add_bm_link_row(entry)
            self.btn_copy_all.setEnabled(True)

            self.lbl_status.setText(f"🟢 BM {bm_num} Created! — {name}")
            self.lbl_status.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 700; border: none;")

        elif evt_type == "failed":
            reason = evt.get("reason", "Creation failed")
            bm_num = evt.get("bm_num", 1)
            self.banner_notice.setVisible(True)
            self.lbl_notice.setText(f"⛔ BM {bm_num} Failed: {reason}")
            self.lbl_status.setText(f"⚠️ Limit Reached or Stopped at BM {bm_num}")
            self.lbl_status.setStyleSheet("color: #fb7185; font-size: 11px; font-weight: 700; border: none;")

        elif evt_type == "done":
            self.prog_bar.setVisible(False)
            self.btn_start.setEnabled(True)
            self.spin_count.setEnabled(True)
            self.btn_start.setText("⚡ Create More BMs")

            total = evt.get("total_created", len(self.created_bms))
            limit = evt.get("limit_reached", False)
            if limit:
                self.banner_notice.setVisible(True)
                reason = evt.get("reason", "Limit Reached")
                self.lbl_notice.setText(f"⛔ BM Limit Reached ({reason}) — Total Created: {total}")
                self.lbl_status.setText(f"🏁 Creation complete. Total {total} BM{'s' if total != 1 else ''} created.")
            else:
                self.lbl_status.setText(f"✅ Success! Created all {total} Business Managers.")
                self.lbl_status.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 700; border: none;")

        elif evt_type == "error":
            self.prog_bar.setVisible(False)
            self.btn_start.setEnabled(True)
            self.spin_count.setEnabled(True)
            self.btn_start.setText("⚡ Try Again")
            err_msg = evt.get("message", "Error")
            self.lbl_status.setText(f"🔴 Error: {err_msg}")
            self.lbl_status.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700; border: none;")

    def _add_bm_link_row(self, entry: dict):
        row = QFrame()
        row.setFixedHeight(30)
        row.setStyleSheet("""
            QFrame {
                background: #131326;
                border: 1px solid #1f223d;
                border-radius: 6px;
                padding: 1px 6px;
            }
            QFrame:hover {
                border-color: #06b6d4;
                background: #181933;
            }
        """)
        h = QHBoxLayout(row)
        h.setContentsMargins(6, 2, 6, 2)
        h.setSpacing(8)

        title_text = f"✅ BM {entry['bm_num']} — {entry['name']}"
        btn_open = QPushButton(title_text)
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setStyleSheet("""
            QPushButton {
                color: #38bdf8;
                font-weight: 700;
                font-size: 11.5px;
                border: none;
                background: transparent;
                text-align: left;
            }
            QPushButton:hover { color: #ffffff; text-decoration: underline; }
        """)
        url = entry.get("url")
        if url:
            btn_open.clicked.connect(lambda: webbrowser.open(url))

        # Explicit [Copy] Button
        btn_copy = QPushButton("Copy")
        btn_copy.setToolTip("Copy direct BM Link to clipboard")
        btn_copy.setFixedSize(50, 22)
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #38bdf8;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 800;
                padding: 0px;
            }
            QPushButton:hover { background: #3b82f6; color: #ffffff; }
        """)
        btn_copy.clicked.connect(lambda _, b=btn_copy, u=url: self._copy_single_link(u, b))

        h.addWidget(btn_open, stretch=1)
        h.addWidget(btn_copy)

        self.links_layout.insertWidget(self.links_layout.count() - 1, row)

    def _copy_single_link(self, url: str, btn: QPushButton):
        if url:
            QApplication.clipboard().setText(url)
            btn.setText("Copied! ✓")
            btn.setStyleSheet("""
                QPushButton {
                    background: #10b981;
                    color: #ffffff;
                    border: 1px solid #10b981;
                    border-radius: 4px;
                    font-size: 9.5px;
                    font-weight: 800;
                }
            """)
            QTimer.singleShot(1500, lambda: (
                btn.setText("Copy"),
                btn.setStyleSheet("""
                    QPushButton {
                        background: #1e293b;
                        color: #38bdf8;
                        border: 1px solid #3b82f6;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: 800;
                    }
                    QPushButton:hover { background: #3b82f6; color: #ffffff; }
                """)
            ))
            self.lbl_status.setText("📋 Copied BM link to clipboard!")
            self.lbl_status.setStyleSheet("color: #a855f7; font-size: 11px; font-weight: 700; border: none;")

    def _copy_all_links(self):
        if not self.created_bms:
            return
        lines = []
        for b in self.created_bms:
            lines.append(f"BM {b['bm_num']} - {b['name']}: {b['url']}")
        all_text = "\n".join(lines)
        QApplication.clipboard().setText(all_text)
        self.btn_copy_all.setText("Copied All! ✓")
        QTimer.singleShot(1500, lambda: self.btn_copy_all.setText("📋 Copy All BM Links"))
        self.lbl_status.setText(f"📋 Copied all {len(self.created_bms)} BM links to clipboard!")
        self.lbl_status.setStyleSheet("color: #a855f7; font-size: 11px; font-weight: 700; border: none;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


def launch_ui(profile_mgr=None, parent=None, profile_data=None, user_data_dir="", **kwargs) -> bool:
    dlg = FbBusinessCreatorModal(profile_data=profile_data, user_data_dir=user_data_dir, parent=parent, profile_mgr=profile_mgr, **kwargs)
    return dlg.exec() == QDialog.DialogCode.Accepted

def main(profile_mgr=None, parent=None, profile_data=None, user_data_dir="", **kwargs) -> bool:
    return launch_ui(profile_mgr=profile_mgr, parent=parent, profile_data=profile_data, user_data_dir=user_data_dir, **kwargs)


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    modal = FbBusinessCreatorModal(profile_data={"number": "540", "name": "Profile 540"})
    modal.show()
    sys.exit(app.exec())
