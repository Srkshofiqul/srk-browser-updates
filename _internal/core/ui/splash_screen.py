"""
Browser Profile Manager - Modern Splash Screen
Python 3.13 / PySide6 Desktop Application
"""

import os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QGraphicsDropShadowEffect, QApplication
)


class SplashScreen(QWidget):
    """
    Modern frameless dark-themed splash screen with live progress reporting.
    """

    def __init__(self, icon_path: str = "") -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(480, 290)

        # Center on screen
        screen_geo = QApplication.primaryScreen().geometry()
        x = (screen_geo.width() - self.width()) // 2
        y = (screen_geo.height() - self.height()) // 2
        self.move(x, y)

        self._init_ui(icon_path)

    def _init_ui(self, icon_path: str) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Card container with shadow
        card = QWidget(self)
        card.setObjectName("SplashCard")
        card.setStyleSheet("""
            QWidget#SplashCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #181825, stop:1 #11111b);
                border: 1.5px solid rgba(139, 92, 246, 0.4);
                border-radius: 18px;
            }
        """)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 26, 28, 24)
        card_layout.setSpacing(14)

        # Top Header (Icon + Title + Version Badge)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(54, 54)
        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(
                54, 54, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            icon_lbl.setPixmap(pix)
        else:
            icon_lbl.setText("🌐")
            icon_lbl.setStyleSheet("font-size: 36px;")
        header_layout.addWidget(icon_lbl)

        # Titles
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        
        app_title = QLabel("srkBrowser")
        app_title.setStyleSheet("""
            font-size: 22px;
            font-weight: 900;
            color: #ffffff;
            letter-spacing: 0.5px;
        """)
        title_row.addWidget(app_title)

        ver_badge = QLabel(" v2.1.0 ")
        ver_badge.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #3b82f6);
            color: #ffffff;
            font-size: 11px;
            font-weight: 800;
            border-radius: 6px;
            padding: 2px 6px;
        """)
        title_row.addWidget(ver_badge)
        title_row.addStretch()

        tagline = QLabel("Isolated Multi-Profile & Automation Engine")
        tagline.setStyleSheet("font-size: 12px; color: #a6adc8; font-weight: 500;")

        title_vbox.addLayout(title_row)
        title_vbox.addWidget(tagline)
        header_layout.addLayout(title_vbox)

        card_layout.addLayout(header_layout)
        card_layout.addSpacing(10)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #313244;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:0.5 #3b82f6, stop:1 #06b6d4);
                border-radius: 4px;
            }
        """)
        card_layout.addWidget(self.progress_bar)

        # Status text & percentage row
        status_row = QHBoxLayout()
        self.status_lbl = QLabel("Starting srkBrowser...")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #cdd6f4; font-weight: 500;")
        
        self.percent_lbl = QLabel("10%")
        self.percent_lbl.setStyleSheet("font-size: 12px; color: #89b4fa; font-weight: 700;")

        status_row.addWidget(self.status_lbl)
        status_row.addStretch()
        status_row.addWidget(self.percent_lbl)
        card_layout.addLayout(status_row)

        # Footer credit
        footer_lbl = QLabel("Developed with ❤️ by SRK Shofiqul")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_lbl.setStyleSheet("font-size: 10.5px; color: #6c7086; margin-top: 4px;")
        card_layout.addWidget(footer_lbl)

        main_layout.addWidget(card)

    def set_progress(self, value: int, message: str = "") -> None:
        """Update progress bar and status message immediately."""
        self.progress_bar.setValue(value)
        self.percent_lbl.setText(f"{value}%")
        if message:
            self.status_lbl.setText(message)
        QApplication.processEvents()

    def finish_and_show(self, main_window: QWidget) -> None:
        """Finish splash smoothly and show main window."""
        self.set_progress(100, "Ready!")
        QApplication.processEvents()
        QTimer.singleShot(150, lambda: self._do_finish(main_window))

    def _do_finish(self, main_window: QWidget) -> None:
        main_window.show()
        self.close()
