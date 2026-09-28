"""
Browser Profile Manager - Custom Widgets Module
Python 3.13 / PySide6 Desktop Application
"""

from typing import Dict, Any, List, Optional
from PySide6.QtCore import Qt, Signal, QPoint, QRectF, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import (
    QAbstractButton, QCheckBox, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMenu, QProgressBar, QPushButton, QSizePolicy, QStyle, QVBoxLayout, QWidget
)

from config import CATEGORIES
from utils import format_timestamp, get_display_number


class ModernToggleSwitch(QAbstractButton):
    """
    Modern iOS / Material style pill-shaped Toggle Switch Slider.
    Features:
    - Smooth animated sliding thumb
    - Antialiased crisp vector rendering
    - Emerald Green (#10b981) when checked / ON
    - Ash Slate (#282d47) with border when unchecked / OFF
    - Interactive hover & pointer cursor
    - Standard toggled(bool) signal
    """
    state_changed = Signal(bool)

    def __init__(
        self,
        checked: bool = False,
        parent: Optional[QWidget] = None,
        active_color: str = "#10b981",
        inactive_color: str = "#282d47",
        thumb_color: str = "#ffffff",
        width: int = 42,
        height: int = 22
    ) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(width, height)

        self._active_color = QColor(active_color)
        self._inactive_color = QColor(inactive_color)
        self._thumb_color = QColor(thumb_color)
        self._track_radius = height / 2.0
        self._thumb_radius = (height - 4) / 2.0

        # Position offset: 0.0 (left/unchecked) to 1.0 (right/checked)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.toggled.connect(self._handle_toggled)
        self._update_tooltip(checked)

    def _update_tooltip(self, checked: bool) -> None:
        self.setToolTip("Status: Enabled (Click to Turn OFF)" if checked else "Status: Disabled (Click to Turn ON)")

    def _handle_toggled(self, checked: bool) -> None:
        self._update_tooltip(checked)
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()
        self.state_changed.emit(checked)

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, val: float) -> None:
        self._offset = val
        self.update()

    offset = Property(float, get_offset, set_offset)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._offset = 1.0 if checked else 0.0
        self._update_tooltip(checked)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        r = self._track_radius

        # Interpolate track background color based on offset
        r_c = int(self._inactive_color.red() + (self._active_color.red() - self._inactive_color.red()) * self._offset)
        g_c = int(self._inactive_color.green() + (self._active_color.green() - self._inactive_color.green()) * self._offset)
        b_c = int(self._inactive_color.blue() + (self._active_color.blue() - self._inactive_color.blue()) * self._offset)
        bg_col = QColor(r_c, g_c, b_c)

        # Draw track pill with subtle border
        border_col = QColor("#3b4261" if self._offset < 0.5 else "#059669")
        painter.setPen(QPen(border_col, 1))
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

        # Draw sliding thumb circle
        thumb_diameter = self._thumb_radius * 2.0
        margin = 2.0
        min_x = margin
        max_x = w - thumb_diameter - margin
        thumb_x = min_x + (max_x - min_x) * self._offset
        thumb_y = margin

        painter.setPen(Qt.NoPen)
        # Subtle drop shadow for thumb
        painter.setBrush(QBrush(QColor(0, 0, 0, 45)))
        painter.drawEllipse(QRectF(thumb_x, thumb_y + 1.0, thumb_diameter, thumb_diameter))

        # Thumb circle body
        painter.setBrush(QBrush(self._thumb_color))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diameter, thumb_diameter))

        painter.end()


class CircularStorageGauge(QWidget):
    """Luxury circular neon progress gauge with antialiased gradient arc and crisp percentage readout."""

    def __init__(self, value: int = 10, max_value: int = 500, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.value = value
        self.max_value = max(1, max_value)
        self.setFixedSize(144, 144)

    def set_values(self, value: int, max_val: int) -> None:
        self.value = value
        self.max_value = max(1, max_val)
        self.update()

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient
        from PySide6.QtCore import Qt, QRectF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = QRectF(14, 14, 116, 116)

        # Background track
        pen_bg = QPen(QColor("#181b2e"), 10)
        pen_bg.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 0, 360 * 16)

        # Active vibrant gradient arc
        ratio = min(1.0, max(0.01, self.value / self.max_value))
        span = int(ratio * 360 * 16)

        grad = QLinearGradient(14, 14, 130, 130)
        grad.setColorAt(0.0, QColor("#6366f1"))
        grad.setColorAt(0.5, QColor("#a855f7"))
        grad.setColorAt(1.0, QColor("#38bdf8"))

        pen_fg = QPen(grad, 10)
        pen_fg.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_fg)
        painter.drawArc(rect, 90 * 16, -span)

        # Inner center value text
        painter.setPen(QColor("#ffffff"))
        font_val = QFont("Segoe UI", 18, QFont.Bold)
        painter.setFont(font_val)
        painter.drawText(QRectF(0, 42, 144, 30), Qt.AlignCenter, str(self.value))

        # Percentage tag
        pct = round((self.value / self.max_value) * 100, 1)
        painter.setPen(QColor("#818cf8"))
        font_sub = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font_sub)
        painter.drawText(QRectF(0, 74, 144, 20), Qt.AlignCenter, f"{pct}% USED")


class StatCard(QFrame):
    """Ultra-modern Executive KPI Stat Card with glowing gradient glassmorphic styling."""

    def __init__(self, title: str, value: str = "0", color: str = "#89b4fa", icon: str = "📊", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #171a2d, stop:1 #111322);
                border: 1px solid #232742;
                border-radius: 12px;
            }}
            QFrame#StatCard:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d2138, stop:1 #151829);
                border: 1px solid {color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        top_hbox = QHBoxLayout()
        top_hbox.setSpacing(8)
        self.label = QLabel(title.upper())
        self.label.setStyleSheet("color: #8c93b0; font-size: 11px; font-weight: 800; letter-spacing: 0.8px;")
        
        self.icon_badge = QLabel(icon)
        self.icon_badge.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 7px;
            padding: 3px 7px;
            font-size: 12px;
        """)
        
        top_hbox.addWidget(self.label)
        top_hbox.addStretch()
        top_hbox.addWidget(self.icon_badge)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 25px; font-weight: 900; font-family: 'Segoe UI', system-ui, sans-serif;")

        layout.addLayout(top_hbox)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        """Update displayed stat value."""
        self.value_label.setText(value)


class ProfileCard(QFrame):
    """
    Sleek, ultra-compact Card widget representing a single browser profile with multi-select checkbox,
    Group badge, Category badge, custom accent color border, PIN badge, and action buttons.
    """

    selection_changed = Signal(str, bool) # profile_id, is_checked
    open_requested = Signal(str)         # profile_id
    relogin_requested = Signal(str)      # profile_id
    quick_page_create_requested = Signal(str) # profile_id
    quick_lang_convert_requested = Signal(str) # profile_id
    generic_script_requested = Signal(str, str) # profile_id, script_id
    note_requested = Signal(str)         # profile_id
    quick_note_changed = Signal(str, str) # profile_id, new_note_text
    edit_requested = Signal(str)         # profile_id
    edit_info_requested = Signal(str)    # profile_id
    fb_info_requested = edit_info_requested  # Backward compatibility alias
    duplicate_requested = Signal(str)    # profile_id
    clean_cache_requested = Signal(str)  # profile_id
    backup_requested = Signal(str)       # profile_id
    delete_requested = Signal(str)       # profile_id

    def __init__(
        self,
        profile_data: Dict[str, Any],
        is_running: bool = False,
        show_relogin_info: bool = False,
        show_info: Optional[bool] = None,
        show_relogin: Optional[bool] = None,
        show_page_create: bool = False,
        show_lang_convert: bool = False,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.profile_id = profile_data["id"]

        if show_info is None:
            show_info = show_relogin_info
        if show_relogin is None:
            show_relogin = show_relogin_info

        self._init_ui(profile_data, is_running, show_info=show_info, show_relogin=show_relogin, show_page_create=show_page_create, show_lang_convert=show_lang_convert)

    def mousePressEvent(self, event) -> None:
        """Clicking anywhere on empty card space toggles profile checkbox selection."""
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if child and isinstance(child, (QPushButton, QLineEdit)):
                super().mousePressEvent(event)
                return
            self.chk_select.setChecked(not self.chk_select.isChecked())
        super().mousePressEvent(event)

    def _update_card_style(self, checked: bool) -> None:
        """Update profile card background subtly on selection without size change."""
        if checked:
            self.setStyleSheet("""
                QFrame#ProfileCard {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1e38, stop:1 #14172a);
                    border: 1px solid #6366f1;
                    border-radius: 9px;
                }
                QFrame#ProfileCard:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #202444, stop:1 #181b32);
                    border: 1px solid #818cf8;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#ProfileCard {
                    background-color: #131626;
                    border: 1px solid #202438;
                    border-radius: 9px;
                }
                QFrame#ProfileCard:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #181c32, stop:1 #14172a);
                    border: 1px solid rgba(99, 102, 241, 0.45);
                }
            """)

    def _init_ui(
        self,
        p: Dict[str, Any],
        is_running: bool,
        show_relogin_info: bool = False,
        show_info: Optional[bool] = None,
        show_relogin: Optional[bool] = None,
        show_page_create: bool = False,
        show_lang_convert: bool = False
    ) -> None:
        if show_info is None:
            show_info = show_relogin_info
        if show_relogin is None:
            show_relogin = show_relogin_info
        # Card Container Object
        self.setObjectName("ProfileCard")
        self.setCursor(Qt.PointingHandCursor)
        self._update_card_style(False)

        # Single Row Compact Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignVCenter)

        # Left Info Group: Checkbox | Number Badge | Name | Group Badge | PIN / Proxy Badges
        self.chk_select = QCheckBox(self)
        self.chk_select.setStyleSheet("""
            QCheckBox {
                background: transparent;
                border: none;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1px solid #3b4261;
                border-radius: 4px;
                background-color: #161829;
            }
            QCheckBox::indicator:hover {
                border-color: #818cf8;
            }
            QCheckBox::indicator:checked {
                background-color: #6366f1;
                border-color: #818cf8;
            }
        """)

        def _on_check_toggled(checked: bool):
            self._update_card_style(checked)
            self.selection_changed.emit(self.profile_id, checked)

        self.chk_select.toggled.connect(_on_check_toggled)

        disp_num = get_display_number(p.get("number", "1"))
        number_badge = QLabel(disp_num, self)
        number_badge.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(99, 102, 241, 0.18), stop:1 rgba(56, 189, 248, 0.18));
            color: #818cf8;
            font-weight: 800;
            padding: 3px 10px;
            border: 1px solid rgba(99, 102, 241, 0.35);
            border-radius: 7px;
            font-size: 11.5px;
        """)

        self.btn_note = QPushButton("ℹ️\nINFO", self)
        self.btn_note.setCursor(Qt.PointingHandCursor)
        self.btn_note.setFixedSize(38, 30)
        self.btn_note.setToolTip(f"ℹ️ View Credentials, Notes & Live Cookies [{disp_num}]")
        self.btn_note.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 212, 191, 0.12);
                color: #2dd4bf;
                border: 1px solid rgba(45, 212, 191, 0.35);
                border-radius: 6px;
                font-size: 7.5px;
                font-weight: 800;
                padding: 1px 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(45, 212, 191, 0.28);
                color: #ffffff;
                border-color: #2dd4bf;
            }
        """)
        self.btn_note.clicked.connect(lambda: self.note_requested.emit(self.profile_id))
        self.btn_note.setVisible(show_info)

        group_name = p.get("group", "Default")
        group_badge = QLabel(f"📁 {group_name}", self)
        group_badge.setStyleSheet("""
            background-color: rgba(251, 191, 36, 0.12);
            color: #fbbf24;
            border: 1px solid rgba(251, 191, 36, 0.3);
            padding: 3px 10px;
            border-radius: 7px;
            font-size: 11px;
            font-weight: 700;
        """)

        layout.addWidget(self.chk_select)
        layout.addWidget(number_badge)
        layout.addWidget(group_badge)

        if p.get("pin"):
            pin_badge = QLabel("🔒 PIN", self)
            pin_badge.setStyleSheet("background-color: rgba(249, 226, 175, 0.18); color: #f9e2af; border: 1px solid rgba(249, 226, 175, 0.35); padding: 2px 8px; border-radius: 6px; font-size: 10.5px; font-weight: bold;")
            layout.addWidget(pin_badge)

        proxy_type = p.get("proxy_type", "None")
        if proxy_type != "None":
            proxy_badge = QLabel(f"🛡️ {proxy_type}", self)
            proxy_badge.setStyleSheet("background-color: rgba(56, 189, 248, 0.14); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); padding: 2px 8px; border-radius: 6px; font-size: 10.5px; font-weight: bold;")
            layout.addWidget(proxy_badge)

        # Middle Quick Note Compact Badge (Sleek chip style)
        self._profile_data = p
        self.btn_quick_note = QPushButton(self)
        self.btn_quick_note.setCursor(Qt.PointingHandCursor)
        self.btn_quick_note.setMaximumWidth(150)
        self._update_note_badge_style(p.get("quick_note", ""))
        self.btn_quick_note.clicked.connect(self._on_edit_note_clicked)

        layout.addWidget(self.btn_quick_note)

        # Stretch to push right action buttons to the right
        layout.addStretch()

        # Right Actions: Open | Info | FB-Relogin | [Script Buttons] | 3-Dots Menu (⋮)
        self.btn_open = QPushButton("🛑 Close" if is_running else "🚀 Open", self)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(lambda: self.open_requested.emit(self.profile_id))

        self.btn_relogin = QPushButton("🔑\nFBRL", self)
        self.btn_relogin.setCursor(Qt.PointingHandCursor)
        self.btn_relogin.setFixedSize(38, 30)
        self.btn_relogin.setToolTip("🔑 1-Click FB Auto Re-Login (FBRL)")
        self.btn_relogin.setStyleSheet("""
            QPushButton {
                background-color: rgba(168, 85, 247, 0.12);
                color: #c084fc;
                border: 1px solid rgba(168, 85, 247, 0.35);
                border-radius: 6px;
                font-size: 7.5px;
                font-weight: 800;
                padding: 1px 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(168, 85, 247, 0.28);
                color: #ffffff;
                border-color: #c084fc;
            }
        """)
        self.btn_relogin.clicked.connect(lambda: self.relogin_requested.emit(self.profile_id))
        self.btn_relogin.setVisible(show_relogin)

        # 📄 1-Click FB Page Creator Studio Action Button
        self.btn_page_create = QPushButton("📄\nPAGE", self)
        self.btn_page_create.setCursor(Qt.PointingHandCursor)
        self.btn_page_create.setFixedSize(38, 30)
        self.btn_page_create.setToolTip("📄 1-Click Fast Facebook Page Creator Studio")
        self.btn_page_create.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.12);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.38);
                border-radius: 6px;
                font-size: 7.5px;
                font-weight: 800;
                padding: 1px 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.28);
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        self.btn_page_create.clicked.connect(lambda: self.quick_page_create_requested.emit(self.profile_id))
        self.btn_page_create.setVisible(show_page_create)

        # 🌐 1-Click FB Language Converter Action Button
        self.btn_lang_convert = QPushButton("🌐\nLANG", self)
        self.btn_lang_convert.setCursor(Qt.PointingHandCursor)
        self.btn_lang_convert.setFixedSize(38, 30)
        self.btn_lang_convert.setToolTip("🌐 1-Click Fast Facebook Language Converter")
        self.btn_lang_convert.setStyleSheet("""
            QPushButton {
                background-color: rgba(99, 102, 241, 0.12);
                color: #818cf8;
                border: 1px solid rgba(99, 102, 241, 0.38);
                border-radius: 6px;
                font-size: 7.5px;
                font-weight: 800;
                padding: 1px 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(99, 102, 241, 0.28);
                color: #ffffff;
                border-color: #818cf8;
            }
        """)
        self.btn_lang_convert.clicked.connect(lambda: self.quick_lang_convert_requested.emit(self.profile_id))
        self.btn_lang_convert.setVisible(show_lang_convert)

        # Sleek 3-Dots Menu Button for Clone, Edit, Delete, Cache, Backup
        self.btn_more = QPushButton("⋮", self)
        self.btn_more.setCursor(Qt.PointingHandCursor)
        self.btn_more.setFixedSize(28, 28)
        self.btn_more.setToolTip("More Profile Actions (Clone, Edit, Delete, Cache, Backup)")
        self.btn_more.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 7px;
                padding: 0px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #242942;
                border-color: #818cf8;
                color: #ffffff;
            }
            QPushButton::menu-indicator { image: none; width: 0px; }
        """)

        def _show_more_menu():
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #151829;
                    color: #cdd6f4;
                    border: 1px solid #282d47;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::item {
                    padding: 6px 20px 6px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QMenu::item:selected {
                    background-color: #232742;
                    color: #818cf8;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #282d47;
                    margin: 4px 0;
                }
            """)
            act_clone = menu.addAction("📋  Clone Profile")
            act_edit = menu.addAction("✏️  Edit Settings")
            act_info = menu.addAction("📝  Edit Info")
            act_note = menu.addAction("📌  Edit Quick Note")
            menu.addSeparator()
            act_clean = menu.addAction("🧹  Clean Profile Cache")
            act_backup = menu.addAction("📦  Backup Profile (ZIP)")
            menu.addSeparator()
            act_del = menu.addAction("🗑️  Delete Profile")

            action = menu.exec_(self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height())))
            if action == act_clone:
                self.duplicate_requested.emit(self.profile_id)
            elif action == act_edit:
                self.edit_requested.emit(self.profile_id)
            elif action == act_info:
                self.edit_info_requested.emit(self.profile_id)
            elif action == act_note:
                self.note_requested.emit(self.profile_id)
            elif action == act_clean:
                self.clean_cache_requested.emit(self.profile_id)
            elif action == act_backup:
                self.backup_requested.emit(self.profile_id)
            elif action == act_del:
                self.delete_requested.emit(self.profile_id)

        self.btn_more.clicked.connect(_show_more_menu)

        layout.addWidget(self.btn_note)
        layout.addWidget(self.btn_relogin)
        layout.addWidget(self.btn_page_create)
        layout.addWidget(self.btn_lang_convert)

        # Dynamically Render Any Other Assigned Custom Scripts (Future-Proof Plug-and-Play)
        assigned_scripts = p.get("assigned_scripts") or []
        if isinstance(assigned_scripts, str):
            assigned_scripts = [assigned_scripts]

        for sid in assigned_scripts:
            if not sid:
                continue
            s_lower = str(sid).lower()
            if any(k in s_lower for k in ("page", "lang", "info", "relogin")):
                continue  # Handled by dedicated quick buttons above
            
            if "business" in s_lower or "bm" in s_lower:
                icon, tag, scolor, sbg = "⚡", "FBBM", "#38bdf8", "rgba(56, 189, 248, 0.12)"
            elif "video" in s_lower or "vup" in s_lower:
                icon, tag, scolor, sbg = "🎬", "FBVUP", "#ec4899", "rgba(236, 72, 153, 0.12)"
            elif "cookie" in s_lower:
                icon, tag, scolor, sbg = "🍪", "COOK", "#f59e0b", "rgba(245, 158, 11, 0.12)"
            elif "share" in s_lower:
                icon, tag, scolor, sbg = "📢", "SHARE", "#f43f5e", "rgba(244, 63, 94, 0.12)"
            elif "post" in s_lower or "feed" in s_lower:
                icon, tag, scolor, sbg = "📝", "POST", "#10b981", "rgba(16, 185, 129, 0.12)"
            elif "bot" in s_lower or "auto" in s_lower:
                icon, tag, scolor, sbg = "🤖", "BOT", "#a855f7", "rgba(168, 85, 247, 0.12)"
            elif "pass" in s_lower or "login" in s_lower:
                icon, tag, scolor, sbg = "🔑", "PASS", "#c084fc", "rgba(168, 85, 247, 0.12)"
            elif "react" in s_lower or "like" in s_lower:
                icon, tag, scolor, sbg = "👍", "REACT", "#3b82f6", "rgba(59, 130, 246, 0.12)"
            elif "group" in s_lower:
                icon, tag, scolor, sbg = "👥", "GROUP", "#eab308", "rgba(234, 179, 8, 0.12)"
            else:
                clean_sid = sid.replace("fb_", "").replace("yt_", "").replace("auto_", "").replace("_", " ").strip()
                tag = (clean_sid.split()[0] if clean_sid else "RUN")[:5].upper()
                icon, scolor, sbg = "⚡", "#fbbf24", "rgba(251, 191, 36, 0.12)"

            btn_custom = QPushButton(f"{icon}\n{tag}", self)
            btn_custom.setCursor(Qt.PointingHandCursor)
            btn_custom.setFixedSize(38, 30)
            btn_custom.setToolTip(f"⚡ 1-Click Launch [{sid.replace('_', ' ').title()}]")
            btn_custom.setStyleSheet(f"""
                QPushButton {{
                    background-color: {sbg};
                    color: {scolor};
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 6px;
                    font-size: 7.5px;
                    font-weight: 800;
                    padding: 1px 0px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: rgba(255, 255, 255, 0.18);
                    color: #ffffff;
                    border-color: {scolor};
                }}
            """)
            btn_custom.clicked.connect(lambda _, s_id=sid: self.generic_script_requested.emit(self.profile_id, s_id))
            layout.addWidget(btn_custom)

        layout.addWidget(self.btn_open)
        layout.addWidget(self.btn_more)

        self.update_running_state(is_running)

    def update_opening_state(self, is_opening: bool) -> None:
        """Temporarily disable button and show glowing '⏳ Opening...' state while in launch queue."""
        if is_opening:
            self.btn_open.setEnabled(False)
            self.btn_open.setText("⏳ Opening...")
            self.btn_open.setStyleSheet("""
                QPushButton {
                    background-color: rgba(56, 189, 248, 0.2);
                    color: #38bdf8;
                    border: 1px solid rgba(56, 189, 248, 0.5);
                    border-radius: 7px;
                    padding: 5px 14px;
                    font-weight: 800;
                    font-size: 11.5px;
                }
            """)
        else:
            self.btn_open.setEnabled(True)
            self.update_running_state(self.is_running)

    def update_syncing_state(self, is_syncing: bool) -> None:
        """Temporarily disable button and show amber '⏳ Syncing...' state while cookies and process wrap up."""
        if is_syncing:
            self.btn_open.setEnabled(False)
            self.btn_open.setText("⏳ Syncing...")
            self.btn_open.setStyleSheet("""
                QPushButton {
                    background-color: rgba(69, 71, 90, 0.7);
                    color: #fab387;
                    border: 1px solid rgba(250, 179, 135, 0.4);
                    border-radius: 7px;
                    padding: 5px 14px;
                    font-weight: 800;
                    font-size: 11.5px;
                }
            """)
        else:
            self.btn_open.setEnabled(True)
            self.update_running_state(self.is_running)

    def update_running_state(self, is_running: bool) -> None:
        self.is_running = is_running
        if is_running:
            self.btn_open.setText("🛑 Close")
            self.btn_open.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
                    color: #ffffff;
                    border: 1px solid #ef4444;
                    border-radius: 7px;
                    padding: 5px 16px;
                    font-weight: 800;
                    font-size: 11.5px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #991b1b);
                    border-color: #f87171;
                }
            """)
        else:
            self.btn_open.setText("🚀 Open")
            self.btn_open.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                    color: #ffffff;
                    border: 1px solid #6366f1;
                    border-radius: 7px;
                    padding: 5px 16px;
                    font-weight: 800;
                    font-size: 11.5px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                    border-color: #818cf8;
                }
            """)

    def _update_note_badge_style(self, note_text: str) -> None:
        note_text = note_text.strip() if note_text else ""
        if note_text:
            disp_text = note_text if len(note_text) <= 12 else f"{note_text[:10]}..."
            self.btn_quick_note.setText(f"📌 {disp_text}")
            self.btn_quick_note.setToolTip(f"Note: {note_text}\n(Click to edit note)")
            self.btn_quick_note.setStyleSheet("""
                QPushButton {
                    background-color: rgba(45, 212, 191, 0.14);
                    color: #2dd4bf;
                    border: 1px solid rgba(45, 212, 191, 0.35);
                    border-radius: 7px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 700;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: rgba(45, 212, 191, 0.25);
                    border-color: #2dd4bf;
                }
            """)
        else:
            self.btn_quick_note.setText("📌 Add Note")
            self.btn_quick_note.setToolTip("Click to add a quick note or tag to this profile")
            self.btn_quick_note.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.03);
                    color: #64748b;
                    border: 1px dashed rgba(255, 255, 255, 0.14);
                    border-radius: 7px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: rgba(99, 102, 241, 0.12);
                    color: #818cf8;
                    border: 1px solid #818cf8;
                }
            """)

    def _on_edit_note_clicked(self) -> None:
        curr_note = self._profile_data.get("quick_note", "")
        disp_num = get_display_number(self._profile_data.get("number", "1"))
        text, ok = QInputDialog.getText(
            self,
            "Edit Quick Note",
            f"Enter quick note / tag for Profile [{disp_num}]:",
            QLineEdit.Normal,
            curr_note
        )
        if ok:
            new_text = text.strip()
            self._profile_data["quick_note"] = new_text
            self._update_note_badge_style(new_text)
            self.quick_note_changed.emit(self.profile_id, new_text)

    def set_running_status(self, is_running: bool) -> None:
        """Update glowing border styling and Open Profile button state."""
        self._is_running = is_running
        if is_running:
            self.setStyleSheet("""
                QFrame#ProfileCard {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f291e, stop:1 #0c1a14);
                    border: 1.5px solid #10b981;
                    border-radius: 9px;
                }
            """)
            if hasattr(self, "btn_open"):
                self.btn_open.setText("🛑 Close")
                self.btn_open.setToolTip("Click to terminate and close this browser profile window")
                self.btn_open.setEnabled(True)
                self.btn_open.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
                        color: #ffffff;
                        border: 1px solid #ef4444;
                        border-radius: 7px;
                        padding: 5px 16px;
                        font-weight: 800;
                        font-size: 11.5px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #991b1b);
                        border-color: #f87171;
                    }
                """)
            if hasattr(self, "btn_relogin"):
                self.btn_relogin.setText("🔑")
                self.btn_relogin.setEnabled(True)
                self.btn_relogin.setFixedSize(30, 28)
                self.btn_relogin.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(168, 85, 247, 0.12);
                        color: #c084fc;
                        border: 1px solid rgba(168, 85, 247, 0.35);
                        border-radius: 7px;
                        font-size: 13px;
                        font-weight: 800;
                        padding: 0px;
                    }
                    QPushButton:hover {
                        background-color: rgba(168, 85, 247, 0.28);
                        color: #ffffff;
                        border-color: #c084fc;
                    }
                """)
        else:
            self.setStyleSheet("""
                QFrame#ProfileCard {
                    background-color: #131626;
                    border: 1px solid #202438;
                    border-radius: 9px;
                }
                QFrame#ProfileCard:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #181c32, stop:1 #14172a);
                    border: 1px solid rgba(99, 102, 241, 0.45);
                }
            """)
            if hasattr(self, "btn_open"):
                self.btn_open.setText("🚀 Open")
                self.btn_open.setEnabled(True)
                self.btn_open.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                        color: #ffffff;
                        border: 1px solid #6366f1;
                        border-radius: 7px;
                        padding: 5px 16px;
                        font-weight: 800;
                        font-size: 11.5px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                        border-color: #818cf8;
                    }
                """)
            if hasattr(self, "btn_relogin"):
                self.btn_relogin.setText("🔑")
                self.btn_relogin.setEnabled(True)
                self.btn_relogin.setFixedSize(30, 28)
                self.btn_relogin.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(168, 85, 247, 0.12);
                        color: #c084fc;
                        border: 1px solid rgba(168, 85, 247, 0.35);
                        border-radius: 7px;
                        font-size: 13px;
                        font-weight: 800;
                        padding: 0px;
                    }
                    QPushButton:hover {
                        background-color: rgba(168, 85, 247, 0.28);
                        color: #ffffff;
                        border-color: #c084fc;
                    }
                """)


class SearchBarWidget(QWidget):
    """Clean control toolbar widget focused on Search, Group filter, and Sort options."""

    search_changed = Signal(str)
    group_changed = Signal(str)
    sort_changed = Signal(str)

    def __init__(self, groups: Optional[List[str]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.initial_groups = groups or ["Default"]
        self._group_counts: Dict[str, int] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Search Line Edit (Compact & Clean)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 #ID...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #131626;
                color: #f8fafc;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 11.5px;
                font-weight: 700;
                width: 90px;
                max-width: 105px;
            }
            QLineEdit:focus {
                border: 1px solid #6366f1;
                background-color: #181c30;
            }
        """)
        self.search_input.textChanged.connect(self.search_changed.emit)

        # Sort Combo Box (Hidden stub for compatibility)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Newest", "Oldest", "Alphabetical"])
        self.sort_combo.setVisible(False)

        # Dummy count label for compatibility
        self.lbl_group_count = QLabel("")
        self.lbl_group_count.setVisible(False)

        # Group Selector Combo Box (Compact)
        self.group_combo = QComboBox()
        self.group_combo.setStyleSheet("""
            QComboBox {
                background-color: #131626;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 4px 6px 4px 8px;
                font-weight: 700;
                font-size: 11.5px;
                min-width: 115px;
                max-width: 135px;
            }
            QComboBox:hover {
                border-color: #6366f1;
                background-color: #181c30;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #151829;
                color: #cdd6f4;
                selection-background-color: #232742;
                selection-color: #818cf8;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 26px;
                padding: 3px 8px;
                border-radius: 5px;
                font-weight: 600;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(99, 102, 241, 0.18);
                color: #818cf8;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #232742;
                color: #818cf8;
                font-weight: 700;
            }
        """)

        self.set_groups(self.initial_groups)
        self.group_combo.currentIndexChanged.connect(self._on_group_combo_changed)

        layout.addWidget(self.group_combo)
        layout.addWidget(self.search_input)

    def _on_group_combo_changed(self) -> None:
        sel_group = self.get_selected_group()
        self.group_changed.emit(sel_group)

    def get_selected_group(self) -> str:
        """Return the raw group name of the currently selected group item."""
        data = self.group_combo.currentData()
        if data is not None:
            return str(data)
        txt = self.group_combo.currentText()
        clean = txt.replace("🌐", "").replace("📁", "").replace("📂", "").strip()
        if " (" in clean:
            return clean.split(" (")[0].strip()
        return clean or "All Groups"

    def set_groups(self, groups: List[str], group_counts: Optional[Dict[str, int]] = None) -> None:
        """Update available group selector list with profile counts while preserving selection."""
        current_group = self.get_selected_group()
        if group_counts is not None:
            self._group_counts = group_counts

        self.group_combo.blockSignals(True)
        self.group_combo.clear()

        all_groups = ["All Groups"]
        for g in groups:
            if g not in all_groups:
                all_groups.append(g)

        target_idx = 0
        for idx, g in enumerate(all_groups):
            cnt = self._group_counts.get(g, 0)
            if g == "All Groups":
                display_text = f"🌐  All Groups ({cnt})"
            elif g == "Default":
                display_text = f"📁  Default ({cnt})"
            else:
                display_text = f"📂  {g} ({cnt})"

            self.group_combo.addItem(display_text, userData=g)
            if g == current_group:
                target_idx = idx

        self.group_combo.setCurrentIndex(target_idx)
        self.group_combo.blockSignals(False)

        sel_group = self.get_selected_group()
        cnt = self._group_counts.get(sel_group, 0)
        self.lbl_group_count.setText(f"📊 {cnt} Profile(s)")


class CloudSyncProgressBanner(QWidget):
    """
    Ultra-Luxury Floating Notification Card that provides live visual feedback during cloud sync.
    Features glassmorphic gradients, glowing status badges, slim neon progress bar, and elegant margins.
    """
    dismissed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CloudSyncBannerContainer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(18, 8, 18, 2)
        outer_layout.setSpacing(0)

        # Inner Glassmorphic Card
        self.card = QFrame()
        self.card.setObjectName("CloudSyncCard")
        self.card.setStyleSheet("""
            QFrame#CloudSyncCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(17, 24, 39, 0.96), stop:0.5 rgba(26, 27, 58, 0.96), stop:1 rgba(15, 23, 42, 0.96));
                border: 1px solid rgba(99, 102, 241, 0.45);
                border-radius: 12px;
            }
        """)

        # Soft drop shadow
        try:
            from PySide6.QtWidgets import QGraphicsDropShadowEffect
            from PySide6.QtGui import QColor
            shadow = QGraphicsDropShadowEffect(self.card)
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 0, 0, 160))
            shadow.setOffset(0, 4)
            self.card.setGraphicsEffect(shadow)
        except Exception:
            pass

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 9, 16, 9)
        card_layout.setSpacing(6)

        # 1. Top Header Row
        header_hbox = QHBoxLayout()
        header_hbox.setContentsMargins(0, 0, 0, 0)
        header_hbox.setSpacing(8)

        self.lbl_icon = QLabel("☁️")
        self.lbl_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        header_hbox.addWidget(self.lbl_icon)

        self.lbl_title = QLabel("Restoring Cloud Profiles & Sessions...")
        self.lbl_title.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #38bdf8; background: transparent; border: none;")
        header_hbox.addWidget(self.lbl_title)

        self.lbl_sec_badge = QLabel("AES-256")
        self.lbl_sec_badge.setStyleSheet("""
            background: rgba(16, 185, 129, 0.12);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 10px;
            font-weight: 800;
        """)
        header_hbox.addWidget(self.lbl_sec_badge)

        header_hbox.addStretch()

        self.lbl_percent = QLabel("0%")
        self.lbl_percent.setStyleSheet("""
            background: rgba(99, 102, 241, 0.18);
            color: #a5b4fc;
            border: 1px solid rgba(99, 102, 241, 0.35);
            border-radius: 5px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 800;
            font-family: 'Segoe UI', monospace;
        """)
        header_hbox.addWidget(self.lbl_percent)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Dismiss Notification")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #94a3b8;
                border: none;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.4);
                color: #ffffff;
            }
        """)
        self.btn_close.clicked.connect(self.hide_banner)
        header_hbox.addWidget(self.btn_close)

        card_layout.addLayout(header_hbox)

        # 2. Neon Slim Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(0, 0, 0, 0.5);
                border: none;
                border-radius: 2.5px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:0.5 #818cf8, stop:1 #c084fc);
                border-radius: 2.5px;
            }
        """)
        card_layout.addWidget(self.progress_bar)

        # 3. Status Detail Row
        self.lbl_detail = QLabel("Connecting to cloud server...")
        self.lbl_detail.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600; font-family: 'Segoe UI', sans-serif; background: transparent; border: none;")
        card_layout.addWidget(self.lbl_detail)

        outer_layout.addWidget(self.card)
        self.setVisible(False)

    def show_progress(self, current: int, total: int, detail: str) -> None:
        self.setVisible(True)
        self.progress_bar.setValue(current)
        self.lbl_percent.setText(f"{current}%")
        self.lbl_detail.setText(detail)
        self.lbl_title.setText("Restoring Cloud Profiles & Sessions...")
        self.lbl_title.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #38bdf8; background: transparent; border: none;")
        self.lbl_sec_badge.setVisible(True)

    def show_success(self, message: str) -> None:
        self.setVisible(True)
        self.progress_bar.setValue(100)
        self.lbl_percent.setText("100%")
        self.lbl_title.setText("✅ Cloud Sync Complete!")
        self.lbl_title.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #4ade80; background: transparent; border: none;")
        self.lbl_sec_badge.setVisible(False)
        self.lbl_detail.setText(message)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3500, self.hide_banner)

    def show_error(self, error_msg: str) -> None:
        self.setVisible(True)
        self.lbl_title.setText("⚠️ Cloud Sync Notice")
        self.lbl_title.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #f87171; background: transparent; border: none;")
        self.lbl_sec_badge.setVisible(False)
        self.lbl_detail.setText(error_msg)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(4500, self.hide_banner)

    def hide_banner(self) -> None:
        self.setVisible(False)
        self.dismissed.emit()


