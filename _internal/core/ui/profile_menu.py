"""
Browser Profile Manager - Profile Dropdown Popup Menu (ixBrowser style)
Python 3.13 / PySide6 Desktop Application
"""

from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QFont, QCursor
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect, QMessageBox
)


class ProfileDropdownMenu(QWidget):
    """Modern Profile Dropdown Popup Card appearing beneath the top-right profile button."""

    def __init__(self, main_window: QWidget) -> None:
        super().__init__(main_window, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.main_window = main_window
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(270)

        # Root Layout
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(6, 6, 6, 6)

        # Card Container
        self.card = QFrame(self)
        self.card.setObjectName("ProfileDropdownCard")
        self.card.setStyleSheet("""
            QFrame#ProfileDropdownCard {
                background-color: #0f121e;
                border: 1.5px solid rgba(137, 180, 250, 0.35);
                border-radius: 14px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        # Drop Shadow
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(14, 14, 14, 14)
        self.card_layout.setSpacing(10)

        # ----------------------------------------------------
        # 1. TOP USER INFO HEADER
        # ----------------------------------------------------
        self.user_header = QHBoxLayout()
        self.user_header.setSpacing(12)

        self.lbl_avatar = QLabel("👑")
        self.lbl_avatar.setAlignment(Qt.AlignCenter)
        self.lbl_avatar.setFixedSize(42, 42)
        self.lbl_avatar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e1b4b, stop:1 #4338ca);
            color: #fbbf24;
            font-size: 20px;
            font-weight: bold;
            border-radius: 21px;
            border: 1.5px solid rgba(251, 191, 36, 0.5);
        """)

        u_text_vbox = QVBoxLayout()
        u_text_vbox.setSpacing(2)

        self.lbl_name = QLabel("Paid Member")
        self.lbl_name.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #ffffff;")

        self.lbl_email = QLabel("📱 Contact Telegram")
        self.lbl_email.setStyleSheet("font-size: 11px; color: #a6adc8;")

        self.lbl_badge = QLabel("👑 Paid Member (Unlimited)")
        self.lbl_badge.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(16, 185, 129, 0.25), stop:1 rgba(6, 182, 212, 0.25));
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.5);
            border-radius: 5px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: 800;
        """)

        self.lbl_validity = QLabel("⚡ Lifetime Unlimited Access")
        self.lbl_validity.setStyleSheet("""
            color: #38bdf8;
            font-size: 10px;
            font-weight: 700;
            padding-top: 1px;
        """)

        u_text_vbox.addWidget(self.lbl_name)
        u_text_vbox.addWidget(self.lbl_email)
        u_text_vbox.addWidget(self.lbl_badge)
        u_text_vbox.addWidget(self.lbl_validity)

        self.user_header.addWidget(self.lbl_avatar)
        self.user_header.addLayout(u_text_vbox)
        self.user_header.addStretch()
        self.card_layout.addLayout(self.user_header)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #26293d; background-color: #26293d; max-height: 1px;")
        self.card_layout.addWidget(div)

        # ----------------------------------------------------
        # 2. MENU ACTION ITEMS (Settings, Support & License Activation)
        # ----------------------------------------------------
        self.btn_license = self._create_menu_btn("🔑  Activate / Renew License", self._on_license_clicked, highlight=True)
        self.btn_settings = self._create_menu_btn("⚙️  Software Settings", self._on_settings_clicked)
        self.btn_support = self._create_menu_btn("💬  Contact Us & Telegram", self._on_support_clicked)

        self.card_layout.addWidget(self.btn_license)
        self.card_layout.addWidget(self.btn_settings)
        self.card_layout.addWidget(self.btn_support)

        # Hidden placeholder references to avoid AttributeErrors if called elsewhere
        self.btn_personal = QWidget(self)
        self.btn_personal.hide()
        self.btn_upgrade = QWidget(self)
        self.btn_upgrade.hide()
        self.btn_redeem = QWidget(self)
        self.btn_redeem.hide()
        self.btn_logout = QWidget(self)
        self.btn_logout.hide()

        root_lay.addWidget(self.card)

    def _create_menu_btn(self, text: str, callback, highlight: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        if highlight:
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(137, 180, 250, 0.1);
                    color: #89b4fa;
                    border: 1px solid rgba(137, 180, 250, 0.25);
                    border-radius: 8px;
                    padding: 8px 12px;
                    font-weight: 700;
                    font-size: 12.5px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                    color: #ffffff;
                    border-color: #c084fc;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #cdd6f4;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 12px;
                    font-weight: 600;
                    font-size: 12.5px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #1a1e30;
                    color: #ffffff;
                }
            """)
        btn.clicked.connect(callback)
        return btn

    def refresh_user_details(self) -> None:
        """Refresh displayed user details dynamically from active license."""
        try:
            from license_manager import get_active_license_info
            info = get_active_license_info()

            self.lbl_avatar.setText("👑")
            self.lbl_name.setText(info["name"] or "VIP Member")

            phone = str(info.get("phone", "")).strip()
            if phone:
                self.lbl_email.setText(f"📱 {phone}")
            elif info["is_active"]:
                self.lbl_email.setText(f"💻 {info['hwid']}")
            else:
                self.lbl_email.setText("❌ No Active License")

            self.lbl_badge.setText(info["plan_badge"])
            if info["is_active"]:
                if "trial" in info["plan_badge"].lower():
                    self.lbl_badge.setStyleSheet("""
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(59, 130, 246, 0.25), stop:1 rgba(14, 165, 233, 0.25));
                        color: #38bdf8;
                        border: 1px solid rgba(56, 189, 248, 0.5);
                        border-radius: 5px;
                        padding: 2px 8px;
                        font-size: 10px;
                        font-weight: 800;
                    """)
                else:
                    self.lbl_badge.setStyleSheet("""
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(16, 185, 129, 0.25), stop:1 rgba(6, 182, 212, 0.25));
                        color: #34d399;
                        border: 1px solid rgba(16, 185, 129, 0.5);
                        border-radius: 5px;
                        padding: 2px 8px;
                        font-size: 10px;
                        font-weight: 800;
                    """)
            else:
                self.lbl_badge.setStyleSheet("""
                    background: rgba(239, 68, 68, 0.25);
                    color: #f87171;
                    border: 1px solid rgba(239, 68, 68, 0.5);
                    border-radius: 5px;
                    padding: 2px 8px;
                    font-size: 10px;
                    font-weight: 800;
                """)

            self.lbl_validity.setText(info["validity_text"])
            self.lbl_validity.setVisible(True)

        except Exception as e:
            self.lbl_name.setText("Paid Member")
            self.lbl_email.setText("📱 Contact Telegram")
            self.lbl_badge.setText("👑 VIP Member")
            self.lbl_validity.setText("⚡ Active Access")

        if hasattr(self, "btn_settings"):
            self.btn_settings.setVisible(True)
        if hasattr(self, "btn_support"):
            self.btn_support.setVisible(True)

    def hideEvent(self, event) -> None:
        import time
        self._last_close_time = time.time()
        super().hideEvent(event)

    def is_recently_closed(self) -> bool:
        import time
        return (time.time() - getattr(self, "_last_close_time", 0.0)) < 0.35

    def show_beneath(self, target_widget: QWidget) -> None:
        """Position and show popup beneath the given widget."""
        self.refresh_user_details()
        self.adjustSize()
        g_pos = target_widget.mapToGlobal(QPoint(0, target_widget.height() + 6))
        # Align right edge of menu with right edge of target widget
        target_right = g_pos.x() + target_widget.width()
        menu_x = target_right - self.width()
        self.move(menu_x, g_pos.y())
        self.show()

    def _on_personal_clicked(self) -> None:
        self.close()
        auth_mgr = getattr(self.main_window, "auth_mgr", None)
        user_info = auth_mgr.get_current_user() if auth_mgr else {}
        if user_info.get("is_logged_in"):
            if hasattr(self.main_window, "open_personal_center"):
                self.main_window.open_personal_center()
            elif hasattr(self.main_window, "switch_view"):
                self.main_window.switch_view(8)
        else:
            from core.ui.dialogs import UserLoginDialog
            from PySide6.QtWidgets import QDialog
            dlg = UserLoginDialog(auth_mgr=auth_mgr, parent=self.main_window)
            if dlg.exec_() == QDialog.Accepted:
                if hasattr(self.main_window, "open_personal_center"):
                    self.main_window.open_personal_center()
                elif hasattr(self.main_window, "switch_view"):
                    self.main_window.switch_view(8)

    def _on_upgrade_clicked(self) -> None:
        self.close()
        if hasattr(self.main_window, "_on_dash_upgrade_clicked"):
            self.main_window._on_dash_upgrade_clicked()

    def _on_redeem_clicked(self) -> None:
        self.close()
        if hasattr(self.main_window, "_on_dash_redeem_clicked"):
            self.main_window._on_dash_redeem_clicked()

    def _on_license_clicked(self) -> None:
        self.close()
        try:
            from core.ui.dialogs import LicenseActivationDialog
            from PySide6.QtWidgets import QDialog
            dlg = LicenseActivationDialog(parent=self.main_window)
            if dlg.exec_() == QDialog.Accepted:
                self.refresh_user_details()
                if hasattr(self.main_window, "_refresh_account_button_status"):
                    self.main_window._refresh_account_button_status()
        except Exception as e:
            pass

    def _on_settings_clicked(self) -> None:
        self.close()
        if hasattr(self.main_window, "switch_view"):
            self.main_window.switch_view(6)

    def _on_support_clicked(self) -> None:
        self.close()
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://t.me/srplatforms"))

    def _on_logout_clicked(self) -> None:
        self.close()
        auth_mgr = getattr(self.main_window, "auth_mgr", None)
        user_info = auth_mgr.get_current_user() if auth_mgr else {}
        if not user_info.get("is_logged_in"):
            # Open Login Dialog if not logged in
            dlg = UserLoginDialog(auth_mgr=auth_mgr, allow_cancel=True, parent=self.main_window)
            dlg.exec()
            self.main_window._refresh_dashboard(force_server=True)
            return

        # Confirm Logout
        email_curr = user_info.get("email", "")
        reply = QMessageBox.question(
            self.main_window,
            "Confirm Sign Out",
            f"Logged in as:\n👤 {email_curr}\n\nDo you want to Sign Out of your account?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Sync metadata to cloud
            try:
                active_token = self.main_window.get_effective_cloud_token()
                all_profs = self.main_window.profile_mgr.get_all_profiles() if hasattr(self.main_window, "profile_mgr") else []
                if active_token and all_profs:
                    from cloud_sync import upload_profiles_cloud_backup
                    upload_profiles_cloud_backup(all_profs, license_token=active_token)
            except Exception:
                pass

            if auth_mgr:
                auth_mgr.clear_session()
            if hasattr(self.main_window, "bot_license_mgr") and self.main_window.bot_license_mgr:
                self.main_window.bot_license_mgr.purge_all_cached_licenses()
            
            self.main_window._refresh_dashboard(force_server=True)
            self.main_window.refresh_all_views()
            if hasattr(self.main_window, "btn_account_status"):
                self.main_window.btn_account_status.setText("🔓 Sign In Account")

            # Block UI and enforce mandatory sign in
            self.main_window.check_and_enforce_login(mandatory=True)
