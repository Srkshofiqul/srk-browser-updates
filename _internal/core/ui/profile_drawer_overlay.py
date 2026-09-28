"""
Browser Profile Manager - In-Page Profile Create & Edit Slide-Over Drawer Overlay
Python 3.13 / PySide6 Desktop Application
"""

from typing import Dict, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QApplication
)

try:
    from core.ui.dialogs import ProfileFormTabs
except Exception:
    from dialogs import ProfileFormTabs


class DrawerCloseButton(QPushButton):
    """Crystal-sharp custom close cross button with anti-aliased vector rendering."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Close (Esc)")
        self._hovered = False

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._hovered:
            bg_color = QColor("#ef4444")
            border_color = QColor("#dc2626")
            cross_color = QColor("#ffffff")
        else:
            bg_color = QColor("#1e2438")
            border_color = QColor("#334155")
            cross_color = QColor("#f1f5f9")

        painter.setBrush(bg_color)
        painter.setPen(border_color)
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 8, 8)

        pen = QPen(cross_color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        pad = 11
        w = self.width()
        h = self.height()
        painter.drawLine(pad, pad, w - pad, h - pad)
        painter.drawLine(w - pad, pad, pad, h - pad)


class ProfileDrawerOverlay(QWidget):
    """In-page Slide-Over Profile Creation and Editing Drawer (ixBrowser Style)."""

    profile_created = Signal(dict)
    profile_updated = Signal(str, dict)
    closed = Signal()

    def __init__(self, profile_mgr: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.is_edit_mode = False
        self.current_profile_id = ""
        self.current_profile_num = ""

        self.setAttribute(Qt.WA_NoSystemBackground, False)
        self.setStyleSheet("background-color: transparent;")

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Left dim backdrop area (clicking dismisses drawer)
        self.backdrop_left = QWidget()
        self.backdrop_left.setStyleSheet("background-color: rgba(5, 8, 12, 0.65);")
        self.backdrop_left.setCursor(Qt.PointingHandCursor)
        self.backdrop_left.mousePressEvent = lambda e: self.hide_drawer()
        self.main_layout.addWidget(self.backdrop_left, stretch=1)

        # Right Drawer Frame
        self.drawer_frame = QFrame()
        self.drawer_frame.setObjectName("ProfileDrawerFrame")
        self.drawer_frame.setStyleSheet("""
            QFrame#ProfileDrawerFrame {
                background-color: #0d111a;
                border-left: 1.5px solid rgba(137, 180, 250, 0.3);
                border-top: 1.5px solid rgba(137, 180, 250, 0.3);
                border-bottom: 1.5px solid rgba(137, 180, 250, 0.3);
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        self.drawer_frame.setFixedWidth(870)

        self.d_layout = QVBoxLayout(self.drawer_frame)
        self.d_layout.setContentsMargins(22, 16, 22, 16)
        self.d_layout.setSpacing(10)

        # 1. TOP HEADER: Breadcrumbs Title + Close Button
        hdr_hbox = QHBoxLayout()
        hdr_hbox.setSpacing(10)

        self.lbl_title = QLabel("Dashboard / Browser Profile / <span style='color:#60a5fa; font-weight:800;'>Create Profile</span>")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #64748b;")

        btn_close = DrawerCloseButton()
        btn_close.clicked.connect(self.hide_drawer)

        hdr_hbox.addWidget(self.lbl_title)
        hdr_hbox.addStretch()
        hdr_hbox.addWidget(btn_close)
        self.d_layout.addLayout(hdr_hbox)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #1e2438; background-color: #1e2438; max-height: 1px;")
        self.d_layout.addWidget(div)

        # 2. Main 4-Tab Container
        self.tabs_container = QWidget()
        self.tabs_container_layout = QVBoxLayout(self.tabs_container)
        self.tabs_container_layout.setContentsMargins(0, 0, 0, 0)
        self.form_tabs: Optional[ProfileFormTabs] = None
        self.d_layout.addWidget(self.tabs_container, stretch=1)

        # 3. Fixed Bottom Action Bar (ixBrowser Style)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(4, 8, 4, 4)
        btn_layout.setSpacing(12)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #12162a;
                color: #94a3b8;
                border: 1px solid #1f274d;
                border-radius: 9px;
                padding: 9px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1a203e;
                color: #ffffff;
                border-color: #3b82f6;
            }
        """)
        btn_cancel.clicked.connect(self.hide_drawer)

        self.btn_reset = QPushButton("🔄 Reset")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #12162a;
                color: #cbd5e1;
                border: 1px solid #1f274d;
                border-radius: 9px;
                padding: 9px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1a203e;
                color: #ffffff;
                border-color: #64748b;
            }
        """)
        self.btn_reset.clicked.connect(self._on_reset)

        btn_next = QPushButton("Next Step ➡️")
        btn_next.setCursor(Qt.PointingHandCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #161c36;
                color: #60a5fa;
                border: 1px solid rgba(96, 165, 250, 0.45);
                border-radius: 9px;
                padding: 9px 22px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #21294d;
                color: #93c5fd;
                border-color: #60a5fa;
            }
        """)
        btn_next.clicked.connect(self._on_next)

        self.btn_submit = QPushButton("🚀 Create Profile Now")
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
                color: #ffffff;
                border: 1px solid #60a5fa;
                border-radius: 9px;
                padding: 10px 30px;
                font-weight: 800;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #7c3aed);
                border-color: #93c5fd;
            }
        """)
        self.btn_submit.clicked.connect(self._on_submit)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(btn_next)
        btn_layout.addWidget(self.btn_submit)
        self.d_layout.addLayout(btn_layout)

        self.main_layout.addWidget(self.drawer_frame)

    def open_create_mode(self, suggested_num: str) -> None:
        """Open drawer for creating a new profile."""
        self.is_edit_mode = False
        self.current_profile_id = ""
        self.current_profile_num = suggested_num

        self.lbl_title.setText(f"Dashboard  /  Browser Profile  /  <span style='color:#60a5fa; font-weight:800;'>Create Profile ({suggested_num})</span>")
        self.btn_submit.setText("🚀 Create Profile Now")

        self._rebuild_form_tabs({"name": suggested_num, "number": suggested_num, "group": "Default"}, is_edit=False)
        self.show_drawer()

    def open_edit_mode(self, profile_data: Dict[str, Any]) -> None:
        """Open drawer for editing an existing profile."""
        self.is_edit_mode = True
        self.current_profile_id = profile_data.get("id", "")
        self.current_profile_num = profile_data.get("number", "")

        self.lbl_title.setText(f"Dashboard  /  Browser Profile  /  <span style='color:#60a5fa; font-weight:800;'>Edit Settings (Profile #{self.current_profile_num})</span>")
        self.btn_submit.setText("💾 Save Changes")

        self._rebuild_form_tabs(profile_data, is_edit=True)
        self.show_drawer()

    def _rebuild_form_tabs(self, data: Dict[str, Any], is_edit: bool) -> None:
        """Reconstruct the ProfileFormTabs with fresh data."""
        while self.tabs_container_layout.count():
            item = self.tabs_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.form_tabs = ProfileFormTabs(
            initial_data=data,
            profile_mgr=self.profile_mgr,
            is_edit=is_edit,
            parent=self.tabs_container
        )
        self.tabs_container_layout.addWidget(self.form_tabs)

    def _on_next(self) -> None:
        if self.form_tabs:
            curr = self.form_tabs.currentIndex()
            if curr < self.form_tabs.count() - 1:
                self.form_tabs.setCurrentIndex(curr + 1)

    def _on_reset(self) -> None:
        if not self.form_tabs:
            return
        if not self.is_edit_mode:
            self.form_tabs.txt_name.setText(self.current_profile_num)
            self.form_tabs.txt_username.clear()
            self.form_tabs.txt_password.clear()
            self.form_tabs.txt_2fa.clear()
            self.form_tabs.txt_cookie.clear()
            self.form_tabs.txt_notes_long.clear()
        else:
            p_data = self.profile_mgr.get_profile_by_id(self.current_profile_id)
            if p_data:
                self._rebuild_form_tabs(p_data, is_edit=True)

    def _on_submit(self) -> None:
        if not self.form_tabs:
            return

        pdata = self.form_tabs.get_data()

        if not self.is_edit_mode:
            created_profile = self.profile_mgr.create_profile(**pdata)
            self.profile_created.emit(created_profile)
        else:
            self.profile_mgr.update_profile(self.current_profile_id, pdata)
            self.profile_updated.emit(self.current_profile_id, pdata)

        self.hide_drawer()

    def show_drawer(self) -> None:
        """Show and fit drawer overlay over parent main window."""
        self.setVisible(True)
        self.raise_()
        if self.parent():
            pw = self.parent().width()
            ph = self.parent().height()
            self.setGeometry(0, 0, pw, ph)
            target_w = min(870, max(720, int(pw * 0.72)))
            self.drawer_frame.setFixedWidth(target_w)

    def hide_drawer(self) -> None:
        """Hide the drawer overlay."""
        self.setVisible(False)
        self.closed.emit()

    def resizeEvent(self, event) -> None:
        """Keep overlay sized to parent window on resize."""
        super().resizeEvent(event)
        if self.parent():
            pw = self.parent().width()
            ph = self.parent().height()
            self.setGeometry(0, 0, pw, ph)
            target_w = min(870, max(720, int(pw * 0.72)))
            self.drawer_frame.setFixedWidth(target_w)
