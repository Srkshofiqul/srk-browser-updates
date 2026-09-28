"""
Browser Profile Manager - Modern Frameless Alert Dialog
Python 3.13 / PySide6 Desktop Application
"""

import os
from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QGraphicsDropShadowEffect, QApplication, QFrame
)


class ModernAlertModal(QDialog):
    """
    Ultra-modern, glassmorphism dark-themed frameless dialog for alerts and warnings.
    """

    def __init__(
        self,
        title: str = "srkBrowser Already Running",
        message: str = "srkBrowser is already running in another window!",
        detail: str = "Please check your Windows taskbar or system tray to access the existing window.",
        alert_type: str = "warning", # warning, info, error, success
        icon_path: str = "",
        parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(460, 240)
        self._drag_pos = QPoint()

        # Center on screen
        screen_geo = QApplication.primaryScreen().geometry()
        x = (screen_geo.width() - self.width()) // 2
        y = (screen_geo.height() - self.height()) // 2
        self.move(x, y)

        self._init_ui(title, message, detail, alert_type, icon_path)

    def _init_ui(
        self, 
        title: str, 
        message: str, 
        detail: str, 
        alert_type: str, 
        icon_path: str
    ) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Border color & icon based on alert_type
        if alert_type == "warning":
            border_color = "rgba(245, 158, 11, 0.55)"
            icon_badge_bg = "rgba(245, 158, 11, 0.15)"
            icon_badge_border = "rgba(245, 158, 11, 0.4)"
            icon_symbol = "⚠️"
            accent_btn_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706)"
            accent_btn_hover = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fbbf24, stop:1 #f59e0b)"
        elif alert_type == "error":
            border_color = "rgba(239, 68, 68, 0.55)"
            icon_badge_bg = "rgba(239, 68, 68, 0.15)"
            icon_badge_border = "rgba(239, 68, 68, 0.4)"
            icon_symbol = "❌"
            accent_btn_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #dc2626)"
            accent_btn_hover = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f87171, stop:1 #ef4444)"
        else:
            border_color = "rgba(139, 92, 246, 0.55)"
            icon_badge_bg = "rgba(139, 92, 246, 0.15)"
            icon_badge_border = "rgba(139, 92, 246, 0.4)"
            icon_symbol = "ℹ️"
            accent_btn_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6)"
            accent_btn_hover = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a78bfa, stop:1 #60a5fa)"

        # Card container
        card = QWidget(self)
        card.setObjectName("AlertCard")
        card.setStyleSheet(f"""
            QWidget#AlertCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e1e2e, stop:1 #11111b);
                border: 1.5px solid {border_color};
                border-radius: 16px;
            }}
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 18)
        card_layout.setSpacing(12)

        # Top Bar (App Logo/Title + Close Button)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        if icon_path and os.path.exists(icon_path):
            app_icon_lbl = QLabel()
            app_icon_lbl.setFixedSize(20, 20)
            pix = QPixmap(icon_path).scaled(
                20, 20, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            app_icon_lbl.setPixmap(pix)
            top_bar.addWidget(app_icon_lbl)

        win_title = QLabel(title)
        win_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #a6adc8;")
        top_bar.addWidget(win_title)
        top_bar.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.25);
                color: #f87171;
            }
        """)
        btn_close.clicked.connect(self.reject)
        top_bar.addWidget(btn_close)
        card_layout.addLayout(top_bar)

        # Content Row (Icon Badge + Messages)
        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        content_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Glowing Icon Badge
        badge = QLabel(icon_symbol)
        badge.setFixedSize(50, 50)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            background-color: {icon_badge_bg};
            border: 1.5px solid {icon_badge_border};
            border-radius: 25px;
            font-size: 24px;
        """)
        content_row.addWidget(badge)

        # Text VBox
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(6)

        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("font-size: 14.5px; font-weight: 800; color: #ffffff;")
        text_vbox.addWidget(msg_lbl)

        if detail:
            detail_lbl = QLabel(detail)
            detail_lbl.setWordWrap(True)
            detail_lbl.setStyleSheet("font-size: 12px; color: #bac2de; line-height: 1.4;")
            text_vbox.addWidget(detail_lbl)

        content_row.addLayout(text_vbox)
        card_layout.addLayout(content_row)

        card_layout.addSpacing(4)

        # Bottom Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        ok_btn = QPushButton("OK, Got It")
        ok_btn.setFixedSize(115, 36)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {accent_btn_gradient};
                color: #ffffff;
                font-weight: 800;
                font-size: 12.5px;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {accent_btn_hover};
            }}
            QPushButton:pressed {{
                background-color: #b45309;
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        card_layout.addLayout(btn_row)

        main_layout.addWidget(card)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


def show_already_running_alert(icon_path: str = "") -> None:
    """Helper to display the modern instance lock dialog."""
    dlg = ModernAlertModal(
        title="srkBrowser Instance Lock",
        message="srkBrowser is already running!",
        detail="Another window of srkBrowser is currently open on your system.\n\nPlease check your Windows taskbar or system tray.",
        alert_type="warning",
        icon_path=icon_path
    )
    dlg.exec()
