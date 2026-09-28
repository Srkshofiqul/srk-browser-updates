"""
srkBrowser - Smart Offline Dialog & Runtime Network Protection Overlay
Python 3.13 / PySide6 Desktop Application
Developer: Srk Shofiqul (srbrowser.com)
"""

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect, QApplication, QFrame
)

from core.network_guard import is_internet_available


class OfflineStartupDialog(QDialog):
    """
    Modern glassmorphism dialog displayed when srkBrowser is launched without an internet connection.
    Prevents unauthenticated or corrupted states and guides the user to reconnect or exit.
    """

    def __init__(self, icon_path: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.icon_path = icon_path
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(480, 270)
        self._drag_pos = QPoint()

        # Center on primary screen
        screen_geo = QApplication.primaryScreen().geometry()
        x = (screen_geo.width() - self.width()) // 2
        y = (screen_geo.height() - self.height()) // 2
        self.move(x, y)

        self._init_ui()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Luxury Container Card
        card = QWidget(self)
        card.setObjectName("OfflineCard")
        card.setStyleSheet("""
            QWidget#OfflineCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a162b, stop:1 #0f0d1a);
                border: 1.5px solid rgba(239, 68, 68, 0.55);
                border-radius: 16px;
            }
        """)

        # Glow Drop Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(239, 68, 68, 80))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 18, 22, 20)
        card_layout.setSpacing(14)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        if self.icon_path and os.path.exists(self.icon_path):
            app_icon_lbl = QLabel()
            app_icon_lbl.setFixedSize(20, 20)
            pix = QPixmap(self.icon_path).scaled(
                20, 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            app_icon_lbl.setPixmap(pix)
            top_bar.addWidget(app_icon_lbl)

        win_title = QLabel("srkBrowser • Network Verification")
        win_title.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #a6adc8;")
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

        # Content Row (Glowing Icon + Text)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon_frame = QFrame()
        icon_frame.setFixedSize(48, 48)
        icon_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 24px;
            }
        """)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel("📡")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        icon_layout.addWidget(icon_lbl)
        content_layout.addWidget(icon_frame)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_lbl = QLabel("No Internet Connection Detected")
        title_lbl.setStyleSheet("font-size: 14.5px; font-weight: 800; color: #ffffff;")
        text_layout.addWidget(title_lbl)

        msg_lbl = QLabel(
            "srkBrowser requires an active internet connection to authenticate your license, "
            "manage browser profiles, and synchronize automation bots safely."
        )
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("font-size: 11.5px; color: #cbd5e1; line-height: 1.4;")
        text_layout.addWidget(msg_lbl)

        self.status_lbl = QLabel("⚠️ Please connect your PC to Wi-Fi or Ethernet and try again.")
        self.status_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #fbbf24; margin-top: 2px;")
        text_layout.addWidget(self.status_lbl)

        content_layout.addLayout(text_layout, stretch=1)
        card_layout.addLayout(content_layout)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.btn_exit = QPushButton("🚪 Exit Application")
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #24273a;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #313244;
                color: #ffffff;
                border-color: #585b70;
            }
        """)
        self.btn_exit.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_exit)

        self.btn_retry = QPushButton("🔄 Retry Connection")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                border: 1px solid #818cf8;
                border-radius: 8px;
                padding: 7px 22px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
                border-color: #a5b4fc;
            }
        """)
        self.btn_retry.clicked.connect(self._on_retry_clicked)
        btn_row.addWidget(self.btn_retry)

        card_layout.addLayout(btn_row)
        main_layout.addWidget(card)

    def _on_retry_clicked(self) -> None:
        """Tests internet connection immediately and accepts dialog if online."""
        self.btn_retry.setEnabled(False)
        self.btn_retry.setText("⏳ Checking...")
        self.status_lbl.setText("🔄 Verifying internet connectivity...")
        self.status_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #818cf8;")
        QApplication.processEvents()

        # Short singleShot to allow UI to render spinner before checking socket
        QTimer.singleShot(150, self._perform_recheck)

    def _perform_recheck(self) -> None:
        online = is_internet_available(timeout_sec=1.5, force_refresh=True)
        if online:
            self.status_lbl.setText("🟢 Connection restored! Launching srkBrowser...")
            self.status_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #4ade80;")
            QTimer.singleShot(400, self.accept)
        else:
            self.btn_retry.setEnabled(True)
            self.btn_retry.setText("🔄 Retry Connection")
            self.status_lbl.setText("❌ Still offline. Please check your network adapter or Wi-Fi.")
            self.status_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #f87171;")


def show_offline_startup_dialog(icon_path: str = "", parent: Optional[QWidget] = None) -> bool:
    """Helper function to present the startup offline barrier. Returns True if reconnected."""
    dlg = OfflineStartupDialog(icon_path=icon_path, parent=parent)
    res = dlg.exec()
    return res == QDialog.DialogCode.Accepted


class NetworkOfflineOverlay(QWidget):
    """
    In-Window Floating Protection Overlay that covers the MainWindow when internet connectivity drops.
    Disables interaction with profiles, bots, and tools until connection is restored.
    Automatically dismisses when internet reconnects.
    """

    retry_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("NetworkOfflineOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.setStyleSheet("background: rgba(10, 14, 26, 0.90);")
        self.setVisible(False)

        # Ensure overlay stays positioned above all main window widgets
        self._init_ui()
        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        """Keep overlay geometry synchronized with parent window resizing."""
        if watched == self.parent() and event.type() == event.Type.Resize:
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        return super().eventFilter(watched, event)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(20, 20, 20, 20)

        # Centered Floating Alert Card
        card = QFrame(self)
        card.setObjectName("OverlayCard")
        card.setFixedSize(500, 270)
        card.setStyleSheet("""
            QFrame#OverlayCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a162b, stop:1 #0e0d17);
                border: 1.5px solid rgba(239, 68, 68, 0.6);
                border-radius: 16px;
            }
        """)

        # Drop Shadow
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(36)
        shadow.setColor(QColor(239, 68, 68, 90))
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(26, 22, 26, 22)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Header with pulsating badge
        hdr_hbox = QHBoxLayout()
        hdr_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_hbox.setSpacing(10)

        icon_box = QFrame()
        icon_box.setFixedSize(46, 46)
        icon_box.setStyleSheet("""
            background-color: rgba(239, 68, 68, 0.16);
            border: 1px solid rgba(239, 68, 68, 0.45);
            border-radius: 23px;
        """)
        ib_lay = QVBoxLayout(icon_box)
        ib_lay.setContentsMargins(0, 0, 0, 0)
        ib_lbl = QLabel("📡")
        ib_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ib_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        ib_lay.addWidget(ib_lbl)
        hdr_hbox.addWidget(icon_box)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        t_lbl = QLabel("Internet Connection Lost")
        t_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff; background: transparent; border: none;")
        sub_t = QLabel("srkBrowser Network Safety Guard Active")
        sub_t.setStyleSheet("font-size: 11px; font-weight: 600; color: #f87171; background: transparent; border: none;")
        title_vbox.addWidget(t_lbl)
        title_vbox.addWidget(sub_t)
        hdr_hbox.addLayout(title_vbox)

        card_layout.addLayout(hdr_hbox)

        # Message description
        desc_lbl = QLabel(
            "Your PC lost connection to the network. All browser profile management, "
            "automation bots, and cloud sync features are paused to protect your data."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet("font-size: 12px; color: #cbd5e1; line-height: 1.4; background: transparent; border: none;")
        card_layout.addWidget(desc_lbl)

        # Status text
        self.lbl_status = QLabel("⏳ Waiting for network connection to restore automatically...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #fbbf24; background: transparent; border: none;")
        card_layout.addWidget(self.lbl_status)

        # Buttons Row
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)
        btn_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_exit = QPushButton("🚪 Exit Software")
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #24273a;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 7px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #313244;
                color: #ffffff;
                border-color: #585b70;
            }
        """)
        self.btn_exit.clicked.connect(self._on_exit_clicked)
        btn_box.addWidget(self.btn_exit)

        self.btn_retry = QPushButton("🔄 Check Again")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                border: 1px solid #818cf8;
                border-radius: 8px;
                padding: 7px 22px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
                border-color: #a5b4fc;
            }
        """)
        self.btn_retry.clicked.connect(self._on_check_again_clicked)
        btn_box.addWidget(self.btn_retry)

        card_layout.addLayout(btn_box)
        layout.addWidget(card)

    def show_overlay(self) -> None:
        """Display the modal overlay over the parent window."""
        if self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.lbl_status.setText("⏳ Waiting for network connection to restore automatically...")
        self.lbl_status.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #fbbf24; background: transparent; border: none;")
        self.btn_retry.setEnabled(True)
        self.btn_retry.setText("🔄 Check Again")
        self.setVisible(True)
        self.raise_()

    def hide_overlay(self) -> None:
        """Dismiss the overlay."""
        self.setVisible(False)

    def _on_check_again_clicked(self) -> None:
        self.btn_retry.setEnabled(False)
        self.btn_retry.setText("⏳ Checking...")
        self.lbl_status.setText("🔄 Testing connection...")
        self.lbl_status.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #818cf8; background: transparent; border: none;")
        QApplication.processEvents()

        QTimer.singleShot(150, self._verify_connection)

    def _verify_connection(self) -> None:
        online = is_internet_available(timeout_sec=1.5, force_refresh=True)
        if online:
            self.lbl_status.setText("🟢 Connection restored! Resuming srkBrowser...")
            self.lbl_status.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #4ade80; background: transparent; border: none;")
            QTimer.singleShot(350, self.hide_overlay)
            self.retry_requested.emit()
        else:
            self.btn_retry.setEnabled(True)
            self.btn_retry.setText("🔄 Check Again")
            self.lbl_status.setText("❌ Still offline. Please verify your internet connection.")
            self.lbl_status.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #f87171; background: transparent; border: none;")

    def _on_exit_clicked(self) -> None:
        self.exit_requested.emit()
        if self.parent() and hasattr(self.parent(), "close"):
            self.parent().close()
        else:
            QApplication.quit()
