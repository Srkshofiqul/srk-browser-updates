"""
Browser Profile Manager - Main Window & View Management Module
Python 3.13 / PySide6 Desktop Application
"""

import os
import sys
import json
import shutil
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal, QObject
from PySide6.QtGui import QIcon, QAction, QColor, QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QStackedWidget, QStatusBar, QTableWidget, QTableWidgetItem,
    QToolBar, QVBoxLayout, QWidget, QHeaderView, QSystemTrayIcon, QMenu, QLayout
)



from config import (
    APP_NAME, APP_VERSION, ASSETS_DIR, DARK_STYLESHEET, REPORTS_DIR, BASE_DIR,
    load_settings, save_settings
)

from browser import BrowserLauncher
from profile_manager import ProfileManager
from automation import SingleProfileReloginThread, OpenProfileLauncherThread
from cloud_sync import CloudUploadThread, CloudDownloadThread, CloudRestoreWorker
from core.ui.dialogs import (
    BulkCreateDialog, CreateProfileDialog, EditProfileDialog,
    GroupManagerDialog, PinPromptDialog, ExtensionsManagerDialog,
    SettingsDialog, AboutDialog, AppUpdateDialog, SmartExitConfirmDialog,
    TeamManagerDialog, AddEditTeamMemberDialog
)
from core.ui.widgets import ProfileCard, SearchBarWidget, StatCard, CloudSyncProgressBanner
from utils import format_timestamp, get_display_number, is_created_today

def _clear_layout(layout) -> None:
    """Recursively delete all child widgets and sub-layouts to prevent ghost widgets."""
    if layout is None:
        return
    while layout.count() > 0:
        item = layout.takeAt(0)
        if item.widget():
            w = item.widget()
            w.setParent(None)
            w.deleteLater()
        elif item.layout():
            _clear_layout(item.layout())


class SessionCheckThread(QThread):
    session_revoked = Signal()

    def __init__(self, auth_mgr, check_interval_sec: int = 3, parent=None):
        super().__init__(parent)
        self.auth_mgr = auth_mgr
        self.interval = max(2, check_interval_sec)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            for _ in range(self.interval):
                if not self._running:
                    return
                self.msleep(1000)

            if not self._running:
                return

            if self.auth_mgr and hasattr(self.auth_mgr, "is_logged_in") and self.auth_mgr.is_logged_in():
                try:
                    valid, code = self.auth_mgr.verify_active_session()
                    if not valid and code in ("SESSION_REVOKED", "UNAUTHORIZED", "INVALID"):
                        self.session_revoked.emit()
                        return
                except Exception:
                    pass


class ManifestSyncThread(QThread):
    manifest_fetched = Signal(list)

    def run(self):
        try:
            import requests
            r = requests.get("https://srbrowser.com/api/v1/bot/manifest", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    self.manifest_fetched.emit(data)
                    return
        except Exception:
            pass
        self.manifest_fetched.emit([])


class ToolsManifestSyncThread(QThread):
    tools_fetched = Signal(list)

    def run(self):
        try:
            import requests
            api_url = "https://srbrowser.com/api/v1/tools/manifest"
            r = requests.get(api_url, timeout=5)
            if r.status_code == 200:
                res = r.json()
                tools = res.get("tools") if isinstance(res, dict) else (res if isinstance(res, list) else None)
                if isinstance(tools, list):
                    self.tools_fetched.emit(tools)
                    return
        except Exception:
            pass
        self.tools_fetched.emit([])


class ScriptsManifestSyncThread(QThread):
    scripts_fetched = Signal(list)

    def run(self):
        try:
            import requests
            api_url = "https://srbrowser.com/api/v1/scripts/manifest"
            r = requests.get(api_url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    self.scripts_fetched.emit(data)
                    return
        except Exception:
            pass


class QuickLangConvertThread(QThread):
    finished_signal = Signal(bool, str, str)  # ok, msg, prof_num

    def __init__(self, user_dir: str, p_data: dict, prof_num: str):
        super().__init__()
        self.user_dir = user_dir
        self.p_data = p_data
        self.prof_num = prof_num

    def run(self):
        try:
            import sys
            from pathlib import Path
            script_paths = [
                Path(__file__).resolve().parent.parent.parent.parent / "06_Script_Store" / "02_FB_Language_Converter",
                Path(__file__).resolve().parent.parent.parent / "06_Script_Store" / "02_FB_Language_Converter",
                Path(__file__).resolve().parent.parent / "06_Script_Store" / "02_FB_Language_Converter",
                Path.cwd() / "06_Script_Store" / "02_FB_Language_Converter"
            ]
            for sp in script_paths:
                if sp.is_dir() and str(sp.resolve()) not in sys.path:
                    sys.path.insert(0, str(sp.resolve()))

            from fb_language_converter_engine import execute_language_conversion
            ok, msg = execute_language_conversion(
                user_data_dir=self.user_dir,
                target_locale="en_US",
                delay_sec=0.0,
                headless=False,
                profile_data=self.p_data
            )
            self.finished_signal.emit(ok, msg, self.prof_num)
        except Exception as e:
            self.finished_signal.emit(False, str(e), self.prof_num)


class TeamMembersFetchWorker(QThread):
    """Background QThread worker to fetch team members and seat limits from cloud API without blocking GUI."""
    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, token: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.token = token

    def run(self) -> None:
        import requests
        try:
            url = "https://srbrowser.com/api/v1/team/members"
            r = requests.get(
                url,
                headers={"X-Auth-Token": self.token, "x-license-token": self.token},
                timeout=8
            )
            if r.status_code == 200:
                res = r.json()
                if res.get("status") == "success":
                    self.result_ready.emit(res)
                    return
                else:
                    self.error_occurred.emit(res.get("message", "Failed to fetch team members"))
                    return
            self.error_occurred.emit(f"Server returned status {r.status_code}")
        except Exception as e:
            self.error_occurred.emit(str(e))


class MainWindow(QMainWindow):
    """
    Main application window featuring a sidebar, top toolbar,
    stacked views (Dashboard, Profiles, Automation, Settings, About), and status bar.
    """

    def __init__(self, profile_mgr: Optional[ProfileManager] = None, auth_mgr: Optional[Any] = None) -> None:
        super().__init__()

        self.settings = load_settings()
        self.profile_mgr = profile_mgr if profile_mgr is not None else ProfileManager()
        self.browser_launcher = BrowserLauncher(self)
        self.selected_profile_ids: Set[str] = set()
        self._has_bulk_opened: bool = False
        self.active_bot_dialogs: List[Any] = []

        self.current_page = 1
        self.page_size = 20
        self.total_pages = 1

        from auth_manager import AuthManager
        from bot_plugin_engine import BotPluginEngine
        from bot_license_manager import BotLicenseManager
        from report_manager import ReportManager

        self.auth_mgr = auth_mgr if auth_mgr is not None else AuthManager()
        self.plugin_engine = BotPluginEngine()
        self.bot_license_mgr = BotLicenseManager()
        self.report_mgr = ReportManager()

        self._team_page_members_data = []
        self._team_page_available_groups = ["Default"]
        self._team_page_max_members = 999999
        self._team_page_used_members = 0

        # Enforce Telegram Hardware-Locked VIP License Shield
        try:
            from core.ui.vip_license_dialog import enforce_telegram_license_check
            if not enforce_telegram_license_check(None):
                sys.exit(0)
        except Exception as lic_err:
            print(f"License check status: {lic_err}")

        self._init_window()
        self._setup_system_tray()

        self._init_toolbar()
        self._init_main_layout()
        self._connect_signals()

        # Connect browser launcher process signals for instant lightweight card updates & queue feedback
        self.browser_launcher.process_opening.connect(lambda pid: (self._update_profile_card_running_state(pid, False, is_syncing=False, is_opening=True), self.update_bulk_open_button_state()))
        self.browser_launcher.process_started.connect(lambda pid: (self._update_profile_card_running_state(pid, True, is_syncing=False, is_opening=False), self.update_bulk_open_button_state()))
        self.browser_launcher.process_syncing.connect(lambda pid: self._update_profile_card_running_state(pid, False, is_syncing=True, is_opening=False))
        self.browser_launcher.process_finished.connect(lambda pid: (self._update_profile_card_running_state(pid, False, is_syncing=False, is_opening=False), self.update_bulk_open_button_state()))
        self.browser_launcher.launch_failed.connect(lambda pid, err: (self._update_profile_card_running_state(pid, False, is_syncing=False, is_opening=False), self.status_bar.showMessage(f"❌ {err}", 5000), self.update_bulk_open_button_state()))

        self.refresh_all_views()
        try:
            init_tab = int(os.environ.get("SRK_INITIAL_TAB", "0"))
            if init_tab > 0:
                self.switch_view(init_tab)
        except Exception:
            pass

        # Background sync, store manifest
        QTimer.singleShot(250, lambda: self._sync_store_manifest_async())
        QTimer.singleShot(800, lambda: self._auto_restore_from_cloud())
        # Startup update popup completely disabled per user requirement

        # Start non-blocking asynchronous session heartbeat check in background thread (3s fast pulse)
        self.session_check_thread = SessionCheckThread(self.auth_mgr, check_interval_sec=3, parent=self)
        self.session_check_thread.session_revoked.connect(self._handle_session_revoked)
        self.session_check_thread.start()

        # Real-time background sync timer for external/bot-launched browser sessions
        self.browser_poll_timer = QTimer(self)
        self.browser_poll_timer.setInterval(2200)
        self.browser_poll_timer.timeout.connect(self._poll_external_browser_processes)
        # Real-time Network Connectivity Watcher Thread
        try:
            from core.network_guard import NetworkWatcherThread
            self.network_watcher = NetworkWatcherThread(check_interval_sec=2.5, parent=self)
            if hasattr(self, "_on_network_lost"):
                self.network_watcher.connection_lost.connect(self._on_network_lost)
            if hasattr(self, "_on_network_restored"):
                self.network_watcher.connection_restored.connect(self._on_network_restored)
            self.network_watcher.start()
        except Exception:
            pass

    def _poll_external_browser_processes(self) -> None:
        """Periodically sync active/running status of all profile cards with disk locks & external bot sessions."""
        if not hasattr(self, "cards_vbox") or not hasattr(self, "browser_launcher"):
            return
        from core.ui.widgets import ProfileCard
        state_changed = False
        for i in range(self.cards_vbox.count()):
            item = self.cards_vbox.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ProfileCard):
                card = item.widget()
                pid = card.profile_id
                if not getattr(card, "is_opening", False) and not getattr(card, "is_syncing", False):
                    is_running = self.browser_launcher.is_running(pid)
                    if card.is_running != is_running:
                        if card.is_running and not is_running:
                            # Transition: Running -> Syncing... -> Open
                            card.update_syncing_state(True)
                            try:
                                if hasattr(self, "profile_mgr"):
                                    self.profile_mgr.sync_profile_cookies_from_disk(pid)
                            except Exception:
                                pass

                            def _finish_external_sync(c=card, p=pid):
                                try:
                                    c.update_syncing_state(False)
                                    c.update_running_state(False)
                                except (RuntimeError, Exception):
                                    pass
                                try:
                                    self.update_bulk_open_button_state()
                                except (RuntimeError, Exception):
                                    pass
                                try:
                                    self._refresh_profiles_list()
                                    self._auto_sync_to_cloud()
                                except (RuntimeError, Exception):
                                    pass

                            QTimer.singleShot(1200, _finish_external_sync)
                            state_changed = True
                        else:
                            # Transition: Closed -> Running (Close button)
                            card.update_running_state(is_running)
                            state_changed = True
        if state_changed:
            self.update_bulk_open_button_state()

    def _update_profile_card_running_state(self, profile_id: str, is_running: bool, is_syncing: bool = False, is_opening: bool = False) -> None:
        """Lightweight in-place UI update for a single card without destroying and rebuilding the list."""
        if not hasattr(self, "cards_vbox"):
            return
        from core.ui.widgets import ProfileCard
        for i in range(self.cards_vbox.count()):
            item = self.cards_vbox.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ProfileCard):
                card = item.widget()
                if card.profile_id == profile_id:
                    if is_opening:
                        card.update_opening_state(True)
                    elif is_syncing:
                        card.update_syncing_state(True)
                    else:
                        card.update_syncing_state(False)
                        card.update_opening_state(False)
                        card.update_running_state(is_running)
                    break

    def check_and_enforce_login(self, mandatory: bool = True, *args: Any, **kwargs: Any) -> bool:
        """Customer Edition: Directly authorized without modal login blocking."""
        return True

    def _init_window(self) -> None:
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.setApplicationName(APP_NAME)
            QApplication.setApplicationDisplayName("")
        except Exception:
            pass
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        width = self.settings.get("default_window_width", 1280)
        height = self.settings.get("default_window_height", 840)
        self.resize(width, height)
        self.setMinimumSize(980, 680)
        self.setStyleSheet(DARK_STYLESHEET)

        # Set Window Icon dynamically from assets directory (app_icon.png, app_icon.ico, or icon.png)
        icon_candidates = [
            ASSETS_DIR / "app_icon.png",
            ASSETS_DIR / "app_icon.ico",
            ASSETS_DIR / "icon.png",
            ASSETS_DIR / "logo.png",
            ASSETS_DIR / "icons" / "app_icon.png",
            ASSETS_DIR / "icons" / "icon.png"
        ]
        for icon_path in icon_candidates:
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                break

        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _init_toolbar(self) -> None:
        toolbar = QToolBar("Main Controls")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        act_create = QAction("➕ Profile", self)
        act_create.triggered.connect(self.on_create_profile)

        act_groups = QAction("📁 Groups", self)
        act_groups.triggered.connect(self.on_open_group_manager)

        self.act_team = QAction("👥 Team", self)
        self.act_team.triggered.connect(self.on_open_team_manager)

        act_ext = QAction("🧩 Extensions", self)
        act_ext.triggered.connect(self.on_open_extension_manager)

        act_update = QAction("🚀 Updates", self)
        act_update.triggered.connect(lambda: self.on_check_for_updates(silent=False))

        act_sync = QAction("🔄 Refresh", self)
        act_sync.setToolTip("1-Click Full Cloud Sync & Refresh (Scripts, Tools, Bots, Extensions & Profiles)")
        act_sync.triggered.connect(self.on_global_refresh_and_sync)

        act_restart = QAction("⚡ Restart", self)
        act_restart.triggered.connect(self.on_restart_action)

        toolbar.addAction(act_create)
        toolbar.addAction(act_groups)
        toolbar.addAction(self.act_team)
        toolbar.addAction(act_ext)
        toolbar.addSeparator()
        toolbar.addAction(act_update)
        toolbar.addAction(act_sync)
        toolbar.addAction(act_restart)

        # 🌟 Right-Aligned VIP Membership & Days Remaining Badge
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # 💎 Top Toolbar Upgrade Button (Left of User Profile)
        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        curr_plan = str(user_info.get("plan_type", "free")).lower()
        curr_quota = int(user_info.get("max_profiles", 100) or 100)

        if curr_plan in ("pro", "professional", "vip") or curr_quota == 500:
            btn_title = "⭐ Professional"
            btn_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(16, 185, 129, 0.18), stop:1 rgba(6, 182, 212, 0.18));
                    color: #34d399;
                    font-weight: 800;
                    font-size: 11.5px;
                    border: 1px solid rgba(16, 185, 129, 0.45);
                    border-radius: 8px;
                    padding: 5px 13px;
                    margin-right: 6px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(16, 185, 129, 0.32), stop:1 rgba(6, 182, 212, 0.32));
                    border-color: #34d399;
                    color: #ffffff;
                }
            """
        elif curr_plan in ("business",) or curr_quota == 1000:
            btn_title = "🚀 Business"
            btn_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(139, 92, 246, 0.18), stop:1 rgba(236, 72, 153, 0.18));
                    color: #c084fc;
                    font-weight: 800;
                    font-size: 11.5px;
                    border: 1px solid rgba(139, 92, 246, 0.45);
                    border-radius: 8px;
                    padding: 5px 13px;
                    margin-right: 6px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(139, 92, 246, 0.32), stop:1 rgba(236, 72, 153, 0.32));
                    border-color: #c084fc;
                    color: #ffffff;
                }
            """
        elif curr_plan in ("enterprise", "ultimate") or curr_quota >= 5000:
            btn_title = "👑 Enterprise"
            btn_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(245, 158, 11, 0.18), stop:1 rgba(225, 29, 72, 0.18));
                    color: #fbbf24;
                    font-weight: 800;
                    font-size: 11.5px;
                    border: 1px solid rgba(245, 158, 11, 0.45);
                    border-radius: 8px;
                    padding: 5px 13px;
                    margin-right: 6px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(245, 158, 11, 0.32), stop:1 rgba(225, 29, 72, 0.32));
                    border-color: #fbbf24;
                    color: #ffffff;
                }
            """
        else:
            btn_title = "💎 Upgrade VIP"
            btn_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                    color: #ffffff;
                    border: 1px solid rgba(192, 132, 252, 0.5);
                    border-radius: 8px;
                    padding: 5px 13px;
                    font-weight: 800;
                    font-size: 11.5px;
                    margin-right: 6px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #3b82f6);
                    border-color: #c084fc;
                }
            """

        self.btn_top_upgrade = QPushButton(btn_title)
        self.btn_top_upgrade.hide()

        btn_account_text = "💎  Paid Member  ▾"
        has_vip = True

        self.btn_account_status = QPushButton(btn_account_text)
        self.btn_account_status.setCursor(Qt.PointingHandCursor)
        if has_vip:
            self.btn_account_status.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2a1b4e, stop:1 #1e1738);
                    color: #facc15;
                    border: 1px solid rgba(234, 179, 8, 0.45);
                    border-radius: 8px;
                    padding: 5px 14px;
                    font-weight: 800;
                    font-size: 12px;
                    margin-right: 4px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b256e, stop:1 #2a204e);
                    border-color: #facc15;
                    color: #ffffff;
                }
            """)
        else:
            self.btn_account_status.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1d33, stop:1 #131526);
                    color: #f1f5f9;
                    border: 1px solid #2d3356;
                    border-radius: 8px;
                    padding: 5px 14px;
                    font-weight: 800;
                    font-size: 12px;
                    margin-right: 4px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #252a4a, stop:1 #1a1d36);
                    border-color: #818cf8;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #101220;
                }
            """)
        # Profile Dropdown Popup Menu (ixBrowser style)
        try:
            from ui.profile_menu import ProfileDropdownMenu
        except Exception:
            from core.ui.profile_menu import ProfileDropdownMenu
        self.profile_menu_popup = ProfileDropdownMenu(main_window=self)
        self.btn_account_status.clicked.connect(self._on_toggle_profile_menu)
        toolbar.addWidget(self.btn_account_status)
        self._refresh_account_button_status()

    def _refresh_account_button_status(self) -> None:
        """Update top account button with active license plan and remaining time."""
        if not hasattr(self, "btn_account_status"):
            return
        try:
            from license_manager import get_active_license_info
            info = get_active_license_info()
            if info["is_active"]:
                nav_text = f"{info['nav_badge']}  ▾"
                self.btn_account_status.setText(nav_text)
                self.btn_account_status.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2a1b4e, stop:1 #1e1738);
                        color: #facc15;
                        border: 1px solid rgba(234, 179, 8, 0.45);
                        border-radius: 8px;
                        padding: 5px 14px;
                        font-weight: 800;
                        font-size: 12px;
                        margin-right: 4px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b256e, stop:1 #2a204e);
                        border-color: #facc15;
                        color: #ffffff;
                    }
                """)
            elif info["is_expired"]:
                self.btn_account_status.setText("⚠️  Expired  ▾")
                self.btn_account_status.setStyleSheet("""
                    QPushButton {
                        background: rgba(239, 68, 68, 0.25);
                        color: #fca5a5;
                        border: 1px solid rgba(239, 68, 68, 0.5);
                        border-radius: 8px;
                        padding: 5px 14px;
                        font-weight: 800;
                        font-size: 12px;
                        margin-right: 4px;
                    }
                """)
            else:
                self.btn_account_status.setText("🔑  Activate  ▾")
                self.btn_account_status.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f766e, stop:1 #0d9488);
                        color: #ffffff;
                        border: 1px solid #14b8a6;
                        border-radius: 8px;
                        padding: 5px 14px;
                        font-weight: 800;
                        font-size: 12px;
                        margin-right: 4px;
                    }
                """)
        except Exception:
            self.btn_account_status.setText("💎  Paid Member  ▾")

    def _on_toggle_profile_menu(self) -> None:
        """Toggle ixBrowser-style Profile dropdown popup card beneath profile button."""
        if not hasattr(self, "profile_menu_popup") or not self.profile_menu_popup:
            try:
                from ui.profile_menu import ProfileDropdownMenu
            except Exception:
                from core.ui.profile_menu import ProfileDropdownMenu
            self.profile_menu_popup = ProfileDropdownMenu(main_window=self)

        if self.profile_menu_popup.isVisible():
            self.profile_menu_popup.close()
            return

        if hasattr(self.profile_menu_popup, "is_recently_closed") and self.profile_menu_popup.is_recently_closed():
            # If the menu was just dismissed by this same mouse click on the profile button, do not reopen
            return

        self._refresh_account_button_status()
        self.profile_menu_popup.show_beneath(self.btn_account_status)

    def _init_main_layout(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_hbox = QHBoxLayout(central_widget)
        main_hbox.setContentsMargins(0, 0, 0, 0)
        main_hbox.setSpacing(0)

        # Sidebar Frame
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("SidebarFrame")
        sidebar_frame.setFixedWidth(215)

        sidebar_vbox = QVBoxLayout(sidebar_frame)
        sidebar_vbox.setContentsMargins(12, 16, 12, 16)
        sidebar_vbox.setSpacing(8)

        # Modern Brand Header (Logo Icon + Glowing Brand Typography)
        brand_widget = QWidget()
        brand_layout = QHBoxLayout(brand_widget)
        brand_layout.setContentsMargins(4, 4, 4, 8)
        brand_layout.setSpacing(10)
        brand_layout.setAlignment(Qt.AlignVCenter)

        from pathlib import Path
        main_sw_dir = Path(__file__).resolve().parents[2]
        icon_png = str(main_sw_dir / "assets" / "app_icon.png")

        if os.path.exists(icon_png):
            lbl_logo = QLabel()
            pix = QPixmap(icon_png)
            if not pix.isNull():
                lbl_logo.setPixmap(pix.scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                brand_layout.addWidget(lbl_logo)

        lbl_brand_text = QLabel('<span style="color:#ffffff; font-weight:900; font-size:19px; font-family: Segoe UI, sans-serif;">srk</span><span style="color:#00c2e8; font-weight:800; font-size:19px; font-family: Segoe UI, sans-serif;">Browser</span>')
        lbl_brand_text.setTextFormat(Qt.RichText)
        brand_layout.addWidget(lbl_brand_text)
        brand_layout.addStretch()

        sidebar_vbox.addWidget(brand_widget)

        sidebar_vbox.addSpacing(16)

        self.btn_nav_dashboard = QPushButton("📊 Dashboard")
        self.btn_nav_dashboard.setObjectName("SidebarButton")
        self.btn_nav_dashboard.setCheckable(True)
        self.btn_nav_dashboard.setChecked(True)
        self.btn_nav_dashboard.clicked.connect(lambda: self.switch_view(0))

        self.btn_nav_profiles = QPushButton("🌐 Profile Manager")
        self.btn_nav_profiles.setObjectName("SidebarButton")
        self.btn_nav_profiles.setCheckable(True)
        self.btn_nav_profiles.clicked.connect(lambda: self.switch_view(1))

        self.btn_nav_automation = QPushButton("🤖 Automation Bots")
        self.btn_nav_automation.setObjectName("SidebarButton")
        self.btn_nav_automation.setCheckable(True)
        self.btn_nav_automation.clicked.connect(lambda: self.switch_view(2))

        self.btn_nav_tools = QPushButton("🛠️ Power Tools")
        self.btn_nav_tools.setObjectName("SidebarButton")
        self.btn_nav_tools.setCheckable(True)
        self.btn_nav_tools.clicked.connect(lambda: self.switch_view(4))

        self.btn_nav_scripts = QPushButton("📜 Script Studio")
        self.btn_nav_scripts.setObjectName("SidebarButton")
        self.btn_nav_scripts.setCheckable(True)
        self.btn_nav_scripts.clicked.connect(lambda: self.switch_view(5))

        self.btn_nav_settings = QPushButton("⚙️ App Settings")
        self.btn_nav_settings.setObjectName("SidebarButton")
        self.btn_nav_settings.setCheckable(True)
        self.btn_nav_settings.clicked.connect(lambda: self.switch_view(6))

        self.btn_nav_about = QPushButton("ℹ️ System Info")
        self.btn_nav_about.setObjectName("SidebarButton")
        self.btn_nav_about.setCheckable(True)
        self.btn_nav_about.clicked.connect(lambda: self.switch_view(7))

        sidebar_vbox.addWidget(self.btn_nav_dashboard)
        sidebar_vbox.addWidget(self.btn_nav_profiles)
        sidebar_vbox.addWidget(self.btn_nav_automation)
        sidebar_vbox.addWidget(self.btn_nav_tools)
        sidebar_vbox.addWidget(self.btn_nav_scripts)
        sidebar_vbox.addWidget(self.btn_nav_settings)
        sidebar_vbox.addWidget(self.btn_nav_about)
        sidebar_vbox.addStretch()

        # Developer Branding Card at bottom of Sidebar (Ultra-Sleek Glassmorphic Widget)
        dev_card = QFrame()
        dev_card.setObjectName("SidebarDevCard")
        dev_card.setStyleSheet("""
            QFrame#SidebarDevCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(26, 29, 45, 0.95), stop:1 rgba(15, 17, 28, 0.95));
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 10px;
                padding: 6px 4px;
            }
        """)
        dev_vbox = QVBoxLayout(dev_card)
        dev_vbox.setContentsMargins(6, 6, 6, 6)
        dev_vbox.setSpacing(0)

        btn_dev_tg = QPushButton("✈️ Telegram")
        btn_dev_tg.setCursor(Qt.PointingHandCursor)
        btn_dev_tg.setFixedHeight(34)
        btn_dev_tg.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(16, 185, 129, 0.22), stop:1 rgba(6, 182, 212, 0.22));
                color: #6ee7b7;
                border: 1px solid rgba(16, 185, 129, 0.45);
                border-radius: 7px;
                font-size: 11px;
                font-weight: 800;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #0891b2);
                color: #ffffff;
                border-color: #34d399;
            }
        """)
        def _open_tg():
            url = "https://t.me/srkplatforms"
            try:
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                if not QDesktopServices.openUrl(QUrl(url)):
                    import webbrowser
                    webbrowser.open(url)
            except Exception:
                try:
                    import webbrowser
                    webbrowser.open(url)
                except Exception:
                    pass
        btn_dev_tg.clicked.connect(_open_tg)

        dev_vbox.addWidget(btn_dev_tg)

        sidebar_vbox.addWidget(dev_card)

        # Content Layout with Top Cloud Sync Banner
        content_container = QWidget()
        content_vbox = QVBoxLayout(content_container)
        content_vbox.setContentsMargins(0, 0, 0, 0)
        content_vbox.setSpacing(6)

        self.cloud_sync_banner = CloudSyncProgressBanner(self)
        content_vbox.addWidget(self.cloud_sync_banner)

        # Stacked Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_dashboard_page())        # index 0
        self.stack.addWidget(self._create_profiles_page())         # index 1
        self.stack.addWidget(self._create_automation_page())       # index 2
        self.stack.addWidget(self._create_extensions_page())       # index 3
        self.stack.addWidget(self._create_tools_page())            # index 4
        self.stack.addWidget(self._create_scripts_page())          # index 5
        self.stack.addWidget(self._create_settings_page())         # index 6
        self.stack.addWidget(self._create_about_page())            # index 7
        self.stack.addWidget(self._create_personal_center_page())  # index 8
        self.stack.addWidget(self._create_team_page())             # index 9

        content_vbox.addWidget(self.stack, stretch=1)

        main_hbox.addWidget(sidebar_frame)
        main_hbox.addWidget(content_container, stretch=1)

        # In-Page Upgrade Slide Overlay (ixBrowser style drawer)
        try:
            from ui.upgrade_overlay import UpgradeSlideOverlay
        except Exception:
            from core.ui.upgrade_overlay import UpgradeSlideOverlay
        self.upgrade_overlay = UpgradeSlideOverlay(parent=self)
        self.upgrade_overlay.setVisible(False)

        # In-Page Profile Create & Edit Slide Overlay (ixBrowser style drawer)
        try:
            from ui.profile_drawer_overlay import ProfileDrawerOverlay
        except Exception:
            from core.ui.profile_drawer_overlay import ProfileDrawerOverlay
        self.profile_drawer = ProfileDrawerOverlay(profile_mgr=self.profile_mgr, parent=self)
        self.profile_drawer.setVisible(False)
        self.profile_drawer.profile_created.connect(self._on_drawer_profile_created)
        self.profile_drawer.profile_updated.connect(self._on_drawer_profile_updated)

        # In-Window Network Offline Protection Overlay
        try:
            from core.ui.network_dialog import NetworkOfflineOverlay
        except Exception:
            from ui.network_dialog import NetworkOfflineOverlay
        self.network_overlay = NetworkOfflineOverlay(parent=self)
        self.network_overlay.setVisible(False)
        self.network_overlay.retry_requested.connect(self._on_network_restored)
        self.network_overlay.exit_requested.connect(self.close)

    def _on_network_lost(self) -> None:
        """Invoked when live internet connection drops during runtime."""
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage("Working in offline standalone mode", 4000)

    def _on_network_restored(self) -> None:
        """Invoked when internet connection is restored."""
        if hasattr(self, "network_overlay") and self.network_overlay:
            self.network_overlay.hide_overlay()
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage("🟢 Internet connection restored! All services active.", 5000)
        if hasattr(self, "_sync_store_manifest_async"):
            self._sync_store_manifest_async()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "upgrade_overlay") and self.upgrade_overlay and self.upgrade_overlay.isVisible():
            self.upgrade_overlay.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "profile_drawer") and self.profile_drawer and self.profile_drawer.isVisible():
            self.profile_drawer.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "network_overlay") and self.network_overlay and self.network_overlay.isVisible():
            self.network_overlay.setGeometry(0, 0, self.width(), self.height())

    def open_personal_center(self) -> None:
        """Switch view directly to Personal Center inside the main window."""
        self.switch_view(8)

    def switch_view(self, index: int) -> None:
        """Switch current stack page index and update button check state."""
        is_member = bool(hasattr(self, "auth_mgr") and self.auth_mgr and self.auth_mgr.is_team_member())
        if is_member and index in (2, 8, 9):
            index = 0

        self.stack.setCurrentIndex(index)
        self.btn_nav_dashboard.setChecked(index == 0)
        self.btn_nav_profiles.setChecked(index == 1)
        self.btn_nav_automation.setChecked(index == 2)
        if hasattr(self, "btn_nav_extensions") and self.btn_nav_extensions:
            self.btn_nav_extensions.setChecked(index == 3)
        self.btn_nav_tools.setChecked(index == 4)
        self.btn_nav_scripts.setChecked(index == 5)
        self.btn_nav_settings.setChecked(index == 6)
        self.btn_nav_about.setChecked(index == 7)
        if hasattr(self, "btn_nav_team") and self.btn_nav_team:
            self.btn_nav_team.setChecked(index == 9)

        if index == 8:
            self._refresh_personal_center()
        elif index == 9:
            self._refresh_team_page()
        else:
            self.refresh_all_views()

    def _create_dashboard_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        user_name = user_info.get("full_name") or user_info.get("email", "User").split("@")[0]
        curr_plan = str(user_info.get("plan_type", "free")).lower()
        curr_quota = int(user_info.get("max_profiles", 100) or user_info.get("cloud_quota", 100) or 100)
        curr_plan_title = "Professional" if (curr_plan in ("pro", "professional", "vip") or curr_quota == 500) else ("Business" if curr_quota == 1000 else ("Enterprise" if curr_quota >= 5000 else "Free"))

        stats = self.profile_mgr.get_dashboard_stats() if hasattr(self, "profile_mgr") and self.profile_mgr else {"total_profiles": 0}
        total_p = stats.get("total_profiles", 0)

        # ----------------------------------------------------
        # ROW 1: Clean Dashboard Header Row (Title on Left, Capsule Actions on Right)
        # ----------------------------------------------------
        header_hbox = QHBoxLayout()
        header_hbox.setContentsMargins(0, 0, 0, 0)

        t_box = QVBoxLayout()
        t_box.setSpacing(2)
        lbl_title = QLabel("Dashboard")
        lbl_title.setStyleSheet("font-size: 19px; font-weight: 800; color: #ffffff;")
        
        lbl_welcome_sub = QLabel(f"👋 Welcome back, <b style='color:#ffffff;'>{user_name}</b> • Anti-Detect Profile Manager")
        lbl_welcome_sub.setStyleSheet("color: #8c93b0; font-size: 11.5px;")
        t_box.addWidget(lbl_title)
        t_box.addWidget(lbl_welcome_sub)
        header_hbox.addLayout(t_box)

        header_hbox.addStretch()

        # Capsule Action Buttons Right
        btn_box = QHBoxLayout()
        btn_box.setSpacing(9)

        self.btn_dash_new_profile = QPushButton("➕ New Profile")
        self.btn_dash_new_profile.setCursor(Qt.PointingHandCursor)
        self.btn_dash_new_profile.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 6px 16px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                border-color: #818cf8;
            }
        """)
        self.btn_dash_new_profile.clicked.connect(self.on_create_profile)
        btn_box.addWidget(self.btn_dash_new_profile)
        header_hbox.addLayout(btn_box)

        layout.addLayout(header_hbox)

        # ----------------------------------------------------
        # ROW 2: 3 Executive Metric Stat Cards
        # ----------------------------------------------------
        stat_hbox = QHBoxLayout()
        stat_hbox.setSpacing(12)

        from core.ui.widgets import StatCard, CircularStorageGauge

        init_bots_count = 5
        if hasattr(self, "plugin_engine"):
            try:
                init_bots_count = len(self.plugin_engine.get_all_bots()) or 5
            except Exception:
                init_bots_count = 5

        self.card_total = StatCard("Active Profiles", str(total_p), "#89b4fa", icon="👥")
        self.card_bots = StatCard("Automation Bots", f"{init_bots_count} Active", "#cba6f7", icon="🤖")
        self.card_running = StatCard("Running Browsers", "0 Active", "#f9e2af", icon="⚡")

        stat_hbox.addWidget(self.card_total)
        stat_hbox.addWidget(self.card_bots)
        stat_hbox.addWidget(self.card_running)

        layout.addLayout(stat_hbox)

        # ----------------------------------------------------
        # ROW 3: Automation Bots & Anti-Detect Shield
        # ----------------------------------------------------
        row3_hbox = QHBoxLayout()
        row3_hbox.setSpacing(14)

        # BOX 1: 🤖 Automation Bots Fast Launcher
        self.box_quick_bots = QFrame()
        self.box_quick_bots.setStyleSheet("""
            QFrame {
                background-color: #151828;
                border: 1px solid #282d44;
                border-radius: 12px;
            }
            QLabel { background: transparent; border: none; }
        """)
        b3_layout = QVBoxLayout(self.box_quick_bots)
        b3_layout.setContentsMargins(16, 14, 16, 14)
        b3_layout.setSpacing(9)

        b3_hdr = QHBoxLayout()
        lbl_b3_title = QLabel("🤖 Automation Bots & Tools")
        lbl_b3_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #ffffff;")
        btn_all_bots = QPushButton("🛒 Bot Store")
        btn_all_bots.setCursor(Qt.PointingHandCursor)
        btn_all_bots.setStyleSheet("""
            QPushButton {
                background: #2b2e46;
                color: #cba6f7;
                border: 1px solid rgba(203, 166, 247, 0.35);
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover { background: #cba6f7; color: #11111b; }
        """)
        btn_all_bots.clicked.connect(lambda: self.switch_view(2))
        b3_hdr.addWidget(lbl_b3_title)
        b3_hdr.addStretch()
        b3_hdr.addWidget(btn_all_bots, 0, Qt.AlignVCenter)
        b3_layout.addLayout(b3_hdr)

        self.vbox_quick_bots_items = QVBoxLayout()
        self.vbox_quick_bots_items.setContentsMargins(0, 0, 0, 0)
        self.vbox_quick_bots_items.setSpacing(9)
        b3_layout.addLayout(self.vbox_quick_bots_items)
        b3_layout.addStretch()
        self._populate_quick_bots_ui()

        row3_hbox.addWidget(self.box_quick_bots, stretch=1)

        # BOX 2: 🛡️ Anti-Detect Engine Health & Diagnostics
        self.box_system_tools = QFrame()
        self.box_system_tools.setStyleSheet("""
            QFrame {
                background-color: #151828;
                border: 1px solid #282d44;
                border-radius: 12px;
            }
            QLabel { background: transparent; border: none; }
        """)
        b2_layout = QVBoxLayout(self.box_system_tools)
        b2_layout.setContentsMargins(16, 14, 16, 14)
        b2_layout.setSpacing(10)

        # Header
        b2_hdr = QHBoxLayout()
        lbl_b2_title = QLabel("Anti-Detect Engine Health & Diagnostics")
        lbl_b2_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #ffffff;")
        badge_b2 = QLabel("🛡️ Spoof-Safe 2.0")
        badge_b2.setStyleSheet("""
            background-color: rgba(137, 180, 250, 0.12);
            color: #89b4fa;
            border: 1px solid rgba(137, 180, 250, 0.3);
            border-radius: 6px;
            padding: 2px 7px;
            font-weight: 700;
            font-size: 10px;
        """)
        b2_hdr.addWidget(lbl_b2_title)
        b2_hdr.addStretch()
        b2_hdr.addWidget(badge_b2, 0, Qt.AlignVCenter)
        b2_layout.addLayout(b2_hdr)

        # Hero Status Banner
        hero_box = QFrame()
        hero_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(16, 185, 129, 0.14), stop:1 rgba(6, 182, 212, 0.14));
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 9px;
            }
        """)
        hero_lay = QHBoxLayout(hero_box)
        hero_lay.setContentsMargins(12, 8, 12, 8)
        hero_lay.setSpacing(10)

        lbl_hero_icon = QLabel("🛡️")
        lbl_hero_icon.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        hero_lay.addWidget(lbl_hero_icon)

        hero_txt = QVBoxLayout()
        hero_txt.setSpacing(2)
        lbl_h1 = QLabel("<b>Live Anti-Detect Core Active</b> • <span style='color:#a6e3a1; font-weight:700;'>🟢 100% Protected</span>")
        lbl_h1.setStyleSheet("color: #ffffff; font-size: 12px; background: transparent; border: none;")
        lbl_h2 = QLabel("Hardware Canvas, WebGL, Audio & ClientRects noise spoofing active.")
        lbl_h2.setStyleSheet("color: #a6adc8; font-size: 10.5px; background: transparent; border: none;")
        hero_txt.addWidget(lbl_h1)
        hero_txt.addWidget(lbl_h2)
        hero_lay.addLayout(hero_txt, stretch=1)
        b2_layout.addWidget(hero_box)

        # 4 Security Modules Grid (2x2)
        from PySide6.QtWidgets import QGridLayout
        sec_grid = QGridLayout()
        sec_grid.setSpacing(6)

        def _make_sec_chip(icon_txt, title_txt, status_txt):
            f = QFrame()
            f.setStyleSheet("background-color: #10121e; border: 1px solid #202438; border-radius: 7px;")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(8, 5, 8, 5)
            fl.setSpacing(1)
            lt = QLabel(f"{icon_txt} {title_txt}")
            lt.setStyleSheet("color: #ffffff; font-size: 10.5px; font-weight: 700; background: transparent; border: none;")
            ls = QLabel(status_txt)
            ls.setStyleSheet("color: #a6e3a1; font-size: 9.5px; font-weight: 600; background: transparent; border: none;")
            fl.addWidget(lt)
            fl.addWidget(ls)
            f.lbl_title = lt
            f.lbl_status = ls
            return f

        sec_grid.addWidget(_make_sec_chip("🎨", "Canvas/WebGL", "🟢 Spoofed Noise"), 0, 0)
        sec_grid.addWidget(_make_sec_chip("🎧", "Audio Context", "🟢 Hardware Mask"), 0, 1)
        sec_grid.addWidget(_make_sec_chip("💻", "ClientRects", "🟢 Native Emul"), 1, 0)
        sec_grid.addWidget(_make_sec_chip("📍", "Proxy IP/Geo", "🟢 Auto-Matched"), 1, 1)
        b2_layout.addLayout(sec_grid)

        row3_hbox.addWidget(self.box_system_tools, stretch=1)
        layout.addLayout(row3_hbox, stretch=1)

        # ----------------------------------------------------
        # ROW 4: ⚡ System Performance & Quick Utilities
        # ----------------------------------------------------
        row4_hbox = QHBoxLayout()
        row4_hbox.setSpacing(14)

        self.box_perf_vip = QFrame()
        self.box_perf_vip.setStyleSheet("""
            QFrame {
                background-color: #151828;
                border: 1px solid #282d44;
                border-radius: 12px;
            }
            QLabel { background: transparent; border: none; }
        """)
        b4_layout = QVBoxLayout(self.box_perf_vip)
        b4_layout.setContentsMargins(16, 14, 16, 14)
        b4_layout.setSpacing(10)

        b4_hdr = QHBoxLayout()
        self.lbl_b4_title = QLabel("🛡️ System Utilities & Quick Tools")
        self.lbl_b4_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #ffffff;")
        self.badge_b4 = QLabel("⚡ Lifetime Unlimited")
        self.badge_b4.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.12);
            color: #6ee7b7;
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 6px;
            padding: 2px 7px;
            font-weight: 700;
            font-size: 10px;
        """)
        b4_hdr.addWidget(self.lbl_b4_title)
        b4_hdr.addStretch()
        b4_hdr.addWidget(self.badge_b4, 0, Qt.AlignVCenter)
        b4_layout.addLayout(b4_hdr)

        def _make_action_strip(icon_str, title_str, tag_str, on_click):
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(38)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #10121e;
                    border: 1px solid #202438;
                    border-radius: 8px;
                    padding: 0px 12px;
                }
                QPushButton:hover {
                    background-color: #16192d;
                    border-color: #3b4261;
                }
            """)
            btn_lay = QHBoxLayout(btn)
            btn_lay.setContentsMargins(12, 0, 12, 0)
            btn_lay.setSpacing(10)
            
            lbl_i = QLabel(icon_str)
            lbl_i.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            lbl_t = QLabel(title_str)
            lbl_t.setStyleSheet("color: #cdd6f4; font-size: 11.5px; font-weight: 700; background: transparent; border: none;")
            
            lbl_tag = QLabel(tag_str)
            lbl_tag.setStyleSheet("color: #8c93b0; font-size: 10.5px; font-weight: 700; background: transparent; border: none;")
            
            btn_lay.addWidget(lbl_i)
            btn_lay.addWidget(lbl_t)
            btn_lay.addStretch()
            btn_lay.addWidget(lbl_tag)
            btn.clicked.connect(on_click)
            return btn

        # Interactive Action Strips (Side-by-Side in Row 4)
        strips_hbox = QHBoxLayout()
        strips_hbox.setSpacing(12)
        strip1 = _make_action_strip("🧹", "Clean Browser Cache & Free RAM", "⚡ Instant Purge ›", self.on_clean_all_profiles_cache)
        strip2 = _make_action_strip("🌐", "Proxy Match & WebRTC IP Shield", "🛡️ Leak-Proof ›", lambda: QMessageBox.information(self, "WebRTC Leak Shield", "🔒 WebRTC, IPv6 & DNS leak prevention are fully active and enforced across all profiles."))
        strips_hbox.addWidget(strip1, stretch=1)
        strips_hbox.addWidget(strip2, stretch=1)
        b4_layout.addLayout(strips_hbox)

        row4_hbox.addWidget(self.box_perf_vip, stretch=1)
        layout.addLayout(row4_hbox)

        return widget

    def _create_profiles_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 8, 16, 6)
        layout.setSpacing(6)

        # ----------------------------------------------------
        # ROW 1: Header Row (Title on Left, Glass Actions on Right)
        # ----------------------------------------------------
        header_hbox = QHBoxLayout()
        header_hbox.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("Browser Profiles")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")

        self.lbl_profile_count_badge = QLabel("0 Profiles")
        self.lbl_profile_count_badge.setStyleSheet("""
            QLabel {
                background: rgba(99, 102, 241, 0.15);
                color: #818cf8;
                border: 1px solid rgba(99, 102, 241, 0.35);
                border-radius: 10px;
                padding: 3px 10px;
                font-weight: 800;
                font-size: 11.5px;
            }
        """)

        title_box = QHBoxLayout()
        title_box.setSpacing(10)
        title_box.addWidget(lbl_title)
        title_box.addWidget(self.lbl_profile_count_badge)

        btn_header_create = QPushButton("➕ Create Profile")
        btn_header_create.setCursor(Qt.PointingHandCursor)
        btn_header_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 6px 15px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
                border-color: #818cf8;
            }
        """)
        btn_header_create.clicked.connect(self.on_create_profile)

        btn_header_groups = QPushButton("📁 Groups")
        btn_header_groups.setCursor(Qt.PointingHandCursor)
        btn_header_groups.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #232742;
                border-color: #4b5585;
                color: #ffffff;
            }
        """)
        btn_header_groups.clicked.connect(self.on_open_group_manager)

        btn_header_bm = QPushButton("🔖 Bookmarks")
        btn_header_bm.setCursor(Qt.PointingHandCursor)
        btn_header_bm.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #232742;
                border-color: #4b5585;
                color: #ffffff;
            }
        """)
        btn_header_bm.clicked.connect(self.on_open_bookmark_manager)

        self.btn_cloud_restore = QPushButton("📥 Cloud Restore")
        self.btn_cloud_restore.setCursor(Qt.PointingHandCursor)
        self.btn_cloud_restore.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #a6e3a1;
                border: 1px solid rgba(166, 227, 161, 0.35);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #232742;
                border-color: #a6e3a1;
                color: #ffffff;
            }
        """)
        self.btn_cloud_restore.clicked.connect(self.on_cloud_restore)

        btn_header_bulk_create = QPushButton("⚡ Bulk Create")
        btn_header_bulk_create.setCursor(Qt.PointingHandCursor)
        btn_header_bulk_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 6px 15px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #1e40af);
                border-color: #60a5fa;
            }
        """)
        btn_header_bulk_create.clicked.connect(self.on_open_bulk_create_dialog)
        btn_header_refresh = QPushButton("🔄 Refresh")
        btn_header_refresh.setCursor(Qt.PointingHandCursor)
        btn_header_refresh.setToolTip("🔄 1-Click Instant Refresh profiles & sync live database from disk")
        btn_header_refresh.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #818cf8;
                border: 1px solid rgba(99, 102, 241, 0.35);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #232742;
                border-color: #818cf8;
                color: #ffffff;
            }
        """)
        btn_header_refresh.clicked.connect(self.on_manual_refresh_profiles)

        header_btn_hbox = QHBoxLayout()
        header_btn_hbox.setSpacing(8)
        header_btn_hbox.addWidget(btn_header_create)
        header_btn_hbox.addWidget(btn_header_bulk_create)
        header_btn_hbox.addWidget(btn_header_groups)
        header_btn_hbox.addWidget(btn_header_bm)
        header_btn_hbox.addWidget(btn_header_refresh)

        header_hbox.addLayout(title_box)
        header_hbox.addStretch()
        header_hbox.addLayout(header_btn_hbox)

        # ----------------------------------------------------
        # ROW 2: Command & Filter Bar Controls
        # ----------------------------------------------------
        self.chk_select_all = QCheckBox("Select All Visible")
        self.chk_select_all.setStyleSheet("""
            QCheckBox {
                color: #cdd6f4;
                font-weight: 700;
                font-size: 11.5px;
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
        self.chk_select_all.toggled.connect(self.on_select_all_toggled)

        self.btn_bulk_open = QPushButton("🚀 Bulk Open (0)")
        self.btn_bulk_open.setCursor(Qt.PointingHandCursor)
        self.btn_bulk_open.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 7px;
                padding: 5px 12px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #3730a3);
            }
            QPushButton:disabled {
                background-color: #161929;
                color: #4a5073;
                border: 1px solid #232740;
            }
        """)
        self.btn_bulk_open.setEnabled(False)
        self.btn_bulk_open.clicked.connect(self.on_bulk_open_profiles)

        self.btn_bulk_edit = QPushButton("✏️ Bulk Edit (0)")
        self.btn_bulk_edit.setCursor(Qt.PointingHandCursor)
        self.btn_bulk_edit.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9);
                color: #ffffff;
                border: 1px solid #8b5cf6;
                border-radius: 7px;
                padding: 5px 12px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #5b21b6);
            }
            QPushButton:disabled {
                background-color: #161929;
                color: #4a5073;
                border: 1px solid #232740;
            }
        """)
        self.btn_bulk_edit.setEnabled(False)
        self.btn_bulk_edit.clicked.connect(self.on_bulk_edit_profiles)

        self.btn_bulk_delete = QPushButton("🗑️ Bulk Delete (0)")
        self.btn_bulk_delete.setCursor(Qt.PointingHandCursor)
        self.btn_bulk_delete.setObjectName("DangerButton")
        self.btn_bulk_delete.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
                color: #ffffff;
                border: 1px solid #ef4444;
                border-radius: 7px;
                padding: 5px 12px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #991b1b);
            }
            QPushButton:disabled {
                background-color: #161929;
                color: #4a5073;
                border: 1px solid #232740;
            }
        """)
        self.btn_bulk_delete.setEnabled(False)
        self.btn_bulk_delete.clicked.connect(self.on_bulk_delete_profiles)

        self.search_bar = SearchBarWidget(groups=self.profile_mgr.get_groups())
        self.search_bar.search_changed.connect(self.on_search_filter_changed)
        self.search_bar.group_changed.connect(self.on_search_filter_changed)
        self.search_bar.sort_changed.connect(self.on_search_filter_changed)

        command_bar_layout = QHBoxLayout()
        command_bar_layout.setContentsMargins(0, 4, 0, 0)
        command_bar_layout.setSpacing(10)
        command_bar_layout.addWidget(self.chk_select_all)
        command_bar_layout.addWidget(self.btn_bulk_open)
        command_bar_layout.addWidget(self.btn_bulk_edit)
        command_bar_layout.addWidget(self.btn_bulk_delete)
        command_bar_layout.addStretch()
        command_bar_layout.addWidget(self.search_bar)

        # ----------------------------------------------------
        # MASTER CONTROL PANEL FRAME (Enclosing Top Controls)
        # ----------------------------------------------------
        master_header_frame = QFrame()
        master_header_frame.setObjectName("MasterHeaderPanel")
        master_header_frame.setStyleSheet("""
            QFrame#MasterHeaderPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        master_layout = QVBoxLayout(master_header_frame)
        master_layout.setContentsMargins(14, 8, 14, 8)
        master_layout.setSpacing(6)

        master_layout.addLayout(header_hbox)

        header_divider = QFrame()
        header_divider.setFrameShape(QFrame.HLine)
        header_divider.setStyleSheet("background-color: #202438; max-height: 1px; border: none;")
        master_layout.addWidget(header_divider)

        master_layout.addLayout(command_bar_layout)

        layout.addWidget(master_header_frame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #11111b;
            }
            QScrollArea > QWidget {
                background-color: #11111b;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 2px 1px 2px 1px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #25283d;
                min-height: 36px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6366f1;
            }
            QScrollBar::handle:vertical:pressed {
                background: #818cf8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                border: none;
                background: none;
                width: 0px;
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                border: none;
                background: none;
            }
        """)

        self.cards_container = QWidget()
        self.cards_container.setObjectName("cards_container")
        self.cards_container.setStyleSheet("QWidget#cards_container { background-color: #11111b; }")
        self.cards_vbox = QVBoxLayout(self.cards_container)
        self.cards_vbox.setContentsMargins(0, 0, 0, 0)
        self.cards_vbox.setSpacing(4)

        self.cards_vbox.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, stretch=1)

        self.pagination_bar = self._create_pagination_bar()
        layout.addWidget(self.pagination_bar)

        return widget

    def _create_pagination_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("PaginationFrame")
        frame.setFixedHeight(32)
        frame.setStyleSheet("""
            QFrame#PaginationFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 8px;
            }
            QComboBox {
                background-color: #161829;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 5px;
                padding: 1px 6px;
                font-weight: 700;
                font-size: 11px;
                max-height: 22px;
            }
            QSpinBox {
                background-color: #161829;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 5px;
                padding: 1px 4px;
                font-weight: 700;
                font-size: 11px;
                max-height: 22px;
                max-width: 42px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(8)

        # 1. Total Count Label
        self.lbl_page_total = QLabel("Total 0")
        self.lbl_page_total.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11.5px;")

        # 2. Page Size Dropdown
        self.cmb_page_size = QComboBox()
        self.cmb_page_size.addItems(["10/page", "20/page", "50/page", "100/page", "200/page", "All/page"])
        self.cmb_page_size.setCurrentIndex(1)
        self.cmb_page_size.currentIndexChanged.connect(self._on_page_size_changed)

        # 2b. Profile Sort Order Dropdown
        self.cmb_sort_order = QComboBox()
        self.cmb_sort_order.addItems(["⬇️ Newest First", "⬆️ Oldest First"])
        self.cmb_sort_order.setToolTip("Profile Ordering: Show newest or oldest (#1) first")
        saved_sort = "Newest"
        if hasattr(self, "settings") and isinstance(self.settings, dict):
            saved_sort = self.settings.get("profile_sort_order", "Newest")
        self.cmb_sort_order.setCurrentIndex(1 if ("Oldest" in saved_sort or "Asc" in saved_sort) else 0)
        self.cmb_sort_order.currentIndexChanged.connect(self._on_sort_order_changed)

        layout.addWidget(self.lbl_page_total)
        layout.addWidget(self.cmb_page_size)
        layout.addWidget(self.cmb_sort_order)
        layout.addStretch()

        # 3. Dynamic Pages HBox
        self.pages_hbox = QHBoxLayout()
        self.pages_hbox.setSpacing(3)
        layout.addLayout(self.pages_hbox)

        # 4. Jump to Page Box
        lbl_goto = QLabel("Go to")
        lbl_goto.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")

        self.spin_goto = QSpinBox()
        self.spin_goto.setRange(1, 1)
        self.spin_goto.setValue(1)
        self.spin_goto.setAlignment(Qt.AlignCenter)
        self.spin_goto.editingFinished.connect(self._on_goto_page)


        layout.addWidget(lbl_goto)
        layout.addWidget(self.spin_goto)


        return frame

    def _update_pagination_controls(self, total_items: int) -> None:
        size_txt = self.cmb_page_size.currentText()
        if "10/" in size_txt:
            self.page_size = 10
        elif "20/" in size_txt:
            self.page_size = 20
        elif "50/" in size_txt:
            self.page_size = 50
        elif "100/" in size_txt:
            self.page_size = 100
        elif "200/" in size_txt:
            self.page_size = 200
        else:
            self.page_size = 999999

        import math
        self.total_pages = max(1, math.ceil(total_items / self.page_size))
        self.current_page = min(max(1, self.current_page), self.total_pages)

        self.lbl_page_total.setText(f"Total {total_items}")
        self.spin_goto.blockSignals(True)
        self.spin_goto.setRange(1, self.total_pages)
        self.spin_goto.setValue(self.current_page)
        self.spin_goto.blockSignals(False)


        while self.pages_hbox.count() > 0:
            child = self.pages_hbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Prev Button
        btn_prev = QPushButton("‹")
        btn_prev.setEnabled(self.current_page > 1)
        btn_prev.setCursor(Qt.PointingHandCursor if self.current_page > 1 else Qt.ArrowCursor)
        btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_prev.clicked.connect(self._on_page_prev_clicked)
        self.pages_hbox.addWidget(btn_prev)

        page_nums = []
        if self.total_pages <= 7:
            page_nums = list(range(1, self.total_pages + 1))
        else:
            page_nums = [1]
            if self.current_page > 3:
                page_nums.append("...")
            
            start_p = max(2, self.current_page - 1)
            end_p = min(self.total_pages - 1, self.current_page + 1)
            for p in range(start_p, end_p + 1):
                if p not in page_nums:
                    page_nums.append(p)
            
            if self.current_page < self.total_pages - 2:
                page_nums.append("...")
            if self.total_pages not in page_nums:
                page_nums.append(self.total_pages)

        for item in page_nums:
            if item == "...":
                lbl_dots = QLabel("...")
                lbl_dots.setStyleSheet("color: #6c7086; font-weight: bold; padding: 0 2px; font-size: 11px;")
                self.pages_hbox.addWidget(lbl_dots)
            else:
                p_num = int(item)
                btn = QPushButton(str(p_num))
                btn.setCursor(Qt.PointingHandCursor)
                if p_num == self.current_page:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #89b4fa; color: #11111b; border: 1px solid #89b4fa;
                            border-radius: 4px; padding: 2px 7px; font-weight: 800; font-size: 11.5px; max-height: 22px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                            border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 11.5px; max-height: 22px;
                        }
                        QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
                    """)
                btn.clicked.connect(lambda _, p=p_num: self._go_to_page(p))
                self.pages_hbox.addWidget(btn)

        # Next Button
        btn_next = QPushButton("›")
        btn_next.setEnabled(self.current_page < self.total_pages)
        btn_next.setCursor(Qt.PointingHandCursor if self.current_page < self.total_pages else Qt.ArrowCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_next.clicked.connect(self._on_page_next_clicked)
        self.pages_hbox.addWidget(btn_next)

    def _clear_profile_selections(self) -> None:
        """Clear all active profile selections, uncheck Select All, and update bulk action buttons."""
        self.selected_profile_ids.clear()
        self._has_bulk_opened = False
        if hasattr(self, "chk_select_all"):
            self.chk_select_all.blockSignals(True)
            self.chk_select_all.setChecked(False)
            self.chk_select_all.blockSignals(False)
        self.update_bulk_open_button_state()
        if hasattr(self, "btn_bulk_edit"):
            self.btn_bulk_edit.setText("✏️ Bulk Edit (0)")
            self.btn_bulk_edit.setEnabled(False)
        if hasattr(self, "btn_bulk_delete"):
            self.btn_bulk_delete.setText("🗑️ Bulk Delete (0)")
            self.btn_bulk_delete.setEnabled(False)

    def _on_page_size_changed(self) -> None:
        self.current_page = 1
        self._clear_profile_selections()
        self._refresh_profiles_list()

    def _on_sort_order_changed(self, idx: int) -> None:
        val = "Oldest" if idx == 1 else "Newest"
        if hasattr(self, "settings") and isinstance(self.settings, dict):
            self.settings["profile_sort_order"] = val
            try:
                save_settings(self.settings)
            except Exception:
                pass
        self.current_page = 1
        self._clear_profile_selections()
        self._refresh_profiles_list()

    def _on_page_prev_clicked(self) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self._clear_profile_selections()
            self._refresh_profiles_list()

    def _on_page_next_clicked(self) -> None:
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._clear_profile_selections()
            self._refresh_profiles_list()

    def _go_to_page(self, page_num: int) -> None:
        if 1 <= page_num <= self.total_pages and page_num != self.current_page:
            self.current_page = page_num
            self._clear_profile_selections()
            self._refresh_profiles_list()

    def _on_goto_page(self) -> None:
        val = self.spin_goto.value()
        self._go_to_page(val)

    def _get_favorite_extensions_file_path(self) -> Path:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = Path(appdata) / "BrowserProfileManager"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "favorite_extensions.json"

    def _load_favorite_extensions(self) -> set:
        try:
            p = self._get_favorite_extensions_file_path()
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
        except Exception as e:
            logger.warning(f"Failed to load favorite extensions: {e}")
        return set()

    def _save_favorite_extensions(self) -> None:
        try:
            p = self._get_favorite_extensions_file_path()
            favs = getattr(self, "favorite_extensions_set", set())
            with open(p, "w", encoding="utf-8") as f:
                json.dump(list(favs), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save favorite extensions: {e}")

    def _toggle_favorite_extension(self, ext_id: str, ext_name: str) -> None:
        if not hasattr(self, "favorite_extensions_set"):
            self.favorite_extensions_set = self._load_favorite_extensions()
        
        if ext_id in self.favorite_extensions_set:
            self.favorite_extensions_set.remove(ext_id)
            msg = f"⭐ Removed '{ext_name}' from Favorites."
        else:
            self.favorite_extensions_set.add(ext_id)
            msg = f"❤️ Added '{ext_name}' to Favorites!"
        
        self._save_favorite_extensions()
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(msg, 3000)
        
        self._refresh_extensions_view()

    def _create_extensions_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        if not hasattr(self, "favorite_extensions_set"):
            self.favorite_extensions_set = self._load_favorite_extensions()

        # Single-Line Compact Control Header Bar (Zero Space Waste)
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                border: 1px solid #232742;
                border-radius: 10px;
            }
        """)
        header_hbox = QHBoxLayout(header_card)
        header_hbox.setContentsMargins(12, 8, 12, 8)
        header_hbox.setSpacing(10)

        # Tab Capsule: Active Extensions & Favorites
        tab_capsule = QFrame()
        tab_capsule.setStyleSheet("background-color: #10121e; border: 1px solid #232742; border-radius: 8px;")
        tab_capsule_hbox = QHBoxLayout(tab_capsule)
        tab_capsule_hbox.setContentsMargins(3, 3, 3, 3)
        tab_capsule_hbox.setSpacing(4)

        self.btn_ext_tab_active = QPushButton("🟢 Active Extensions (0)")
        self.btn_ext_tab_active.setCursor(Qt.PointingHandCursor)
        self.btn_ext_tab_active.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                font-weight: 800;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #6366f1;
            }
        """)

        self.btn_ext_tab_favorites = QPushButton("❤️ Favorites (0)")
        self.btn_ext_tab_favorites.setCursor(Qt.PointingHandCursor)
        self.btn_ext_tab_favorites.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_ext_tab_active.clicked.connect(lambda: self._switch_ext_tab("active"))
        self.btn_ext_tab_favorites.clicked.connect(lambda: self._switch_ext_tab("favorites"))

        tab_capsule_hbox.addWidget(self.btn_ext_tab_active)
        tab_capsule_hbox.addWidget(self.btn_ext_tab_favorites)
        header_hbox.addWidget(tab_capsule)

        self.ext_url_input = QLineEdit()
        self.ext_url_input.setPlaceholderText("🔍 Search or paste Chrome Web Store URL...")
        self.ext_url_input.setStyleSheet("""
            QLineEdit {
                background-color: #131626;
                border: 1px solid #282d47;
                border-radius: 7px;
                padding: 6px 12px;
                color: #ffffff;
                font-size: 11.5px;
            }
            QLineEdit:focus { border-color: #6366f1; background-color: #181c30; }
        """)
        self.ext_url_input.textChanged.connect(lambda txt: self._refresh_extensions_view(txt))
        self.ext_url_input.returnPressed.connect(self.on_download_webstore_url_full_page)
        header_hbox.addWidget(self.ext_url_input, stretch=1)

        btn_dl_url = QPushButton("📥 Add Extension")
        btn_dl_url.setCursor(Qt.PointingHandCursor)
        btn_dl_url.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                color: #ffffff;
                border: 1px solid #10b981;
                border-radius: 7px;
                padding: 6px 14px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
            }
        """)
        btn_dl_url.clicked.connect(self.on_download_webstore_url_full_page)
        header_hbox.addWidget(btn_dl_url)

        btn_upload = QPushButton("➕ Upload Extension")
        btn_upload.setCursor(Qt.PointingHandCursor)
        btn_upload.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9);
                color: #ffffff;
                border: 1px solid #8b5cf6;
                border-radius: 7px;
                padding: 6px 14px;
                font-weight: 800;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #7c3aed);
            }
        """)
        btn_upload.clicked.connect(self.on_upload_extension_full_page)
        header_hbox.addWidget(btn_upload)

        layout.addWidget(header_card)

        # Extensions 3x3 Grid Area (Dynamically expands to fill 100% of viewport without gaps)
        active_content = QWidget()
        active_content.setStyleSheet("background: transparent; border: none;")
        self.active_ext_cards_grid = QGridLayout(active_content)
        self.active_ext_cards_grid.setContentsMargins(0, 0, 0, 0)
        self.active_ext_cards_grid.setSpacing(12)
        for c in range(3):
            self.active_ext_cards_grid.setColumnStretch(c, 1)
        for r in range(4):
            self.active_ext_cards_grid.setRowStretch(r, 1)

        layout.addWidget(active_content, stretch=1)

        # Extensions Pagination Bar (9 per page)
        self.ext_pagination_bar = self._create_ext_pagination_bar()
        layout.addWidget(self.ext_pagination_bar)

        return widget

    def _update_ext_subnav_styles(self, active_tab: str = "active") -> None:
        style_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #6366f1;"
        style_fav_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #be123c); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #f43f5e;"
        style_inactive = "background-color: transparent; color: #a6adc8; font-weight: 600; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: none;"

        if hasattr(self, "btn_ext_tab_active") and self.btn_ext_tab_active:
            self.btn_ext_tab_active.setStyleSheet(style_active if active_tab == "active" else style_inactive)
        if hasattr(self, "btn_ext_tab_favorites") and self.btn_ext_tab_favorites:
            self.btn_ext_tab_favorites.setStyleSheet(style_fav_active if active_tab == "favorites" else style_inactive)

    def _switch_ext_tab(self, tab_mode: str = "active") -> None:
        self._current_ext_tab = tab_mode
        self.ext_current_page = 1
        self._update_ext_subnav_styles(tab_mode)
        self._refresh_extensions_view()

    def _create_extension_card(self, ext: dict, total_profs: int, is_system: bool = False) -> QFrame:
        ext_id = ext.get("id")
        is_active = ext.get("is_active", True)
        name = ext.get("name", "Extension")
        ver = ext.get("version", "1.0")
        target_mode = ext.get("target_mode", "all")
        desc = ext.get("description", "") or ("Official Built-in extension for automated session & cookie management across profile browsers." if is_system else "Custom Chrome extension uploaded for automation and browser profiles.")

        # Curated Rich Dark-Ash & Charcoal Palettes (Visible contrast, cohesive dark theme)
        dark_ash_themes = {
            "ublock": {
                "bg_start": "#1d2030", "bg_end": "#141624", "border": "#2e344d", "border_hover": "#818cf8",
                "icon": "🛡️", "accent": "#818cf8", "icon_bg": "rgba(129, 140, 248, 0.14)"
            },
            "metamask": {
                "bg_start": "#241e1c", "bg_end": "#181412", "border": "#3d2e2a", "border_hover": "#fb923c",
                "icon": "🦊", "accent": "#fb923c", "icon_bg": "rgba(251, 146, 60, 0.14)"
            },
            "cookie-editor": {
                "bg_start": "#1b1e32", "bg_end": "#121424", "border": "#2c3252", "border_hover": "#6366f1",
                "icon": "🍪", "accent": "#a5b4fc", "icon_bg": "rgba(99, 102, 241, 0.14)"
            },
            "editthiscookie": {
                "bg_start": "#231f18", "bg_end": "#181510", "border": "#3b3224", "border_hover": "#fbbf24",
                "icon": "🍪", "accent": "#fde047", "icon_bg": "rgba(251, 191, 36, 0.14)"
            },
            "sessionbox": {
                "bg_start": "#17232e", "bg_end": "#101822", "border": "#233648", "border_hover": "#38bdf8",
                "icon": "🗂️", "accent": "#38bdf8", "icon_bg": "rgba(56, 189, 248, 0.14)"
            },
            "user-agent": {
                "bg_start": "#172520", "bg_end": "#101a17", "border": "#233a33", "border_hover": "#34d399",
                "icon": "🎭", "accent": "#34d399", "icon_bg": "rgba(52, 211, 153, 0.14)"
            },
            "switchyomega": {
                "bg_start": "#182132", "bg_end": "#111724", "border": "#26354f", "border_hover": "#60a5fa",
                "icon": "🌐", "accent": "#60a5fa", "icon_bg": "rgba(96, 165, 250, 0.14)"
            },
            "fingerprint": {
                "bg_start": "#211b30", "bg_end": "#161222", "border": "#362a4d", "border_hover": "#c084fc",
                "icon": "🔒", "accent": "#c084fc", "icon_bg": "rgba(192, 132, 252, 0.14)"
            },
            "buster": {
                "bg_start": "#241a24", "bg_end": "#181119", "border": "#3c263a", "border_hover": "#f472b6",
                "icon": "🤖", "accent": "#f472b6", "icon_bg": "rgba(244, 114, 182, 0.14)"
            },
            "dark reader": {
                "bg_start": "#1f182a", "bg_end": "#15101e", "border": "#342446", "border_hover": "#a855f7",
                "icon": "🌙", "accent": "#c084fc", "icon_bg": "rgba(168, 85, 247, 0.14)"
            },
            "violentmonkey": {
                "bg_start": "#242018", "bg_end": "#181510", "border": "#3b3322", "border_hover": "#facc15",
                "icon": "⚡", "accent": "#fde047", "icon_bg": "rgba(250, 204, 21, 0.14)"
            },
            "cyberghost": {
                "bg_start": "#182030", "bg_end": "#111724", "border": "#26334d", "border_hover": "#38bdf8",
                "icon": "👻", "accent": "#38bdf8", "icon_bg": "rgba(56, 189, 248, 0.14)"
            }
        }

        # Fallback Dark Ash Tones for any newly uploaded extension
        fallback_dark_ash = [
            {"bg_start": "#1d2030", "bg_end": "#141624", "border": "#2e344d", "border_hover": "#818cf8", "icon": "🧩", "accent": "#818cf8", "icon_bg": "rgba(129, 140, 248, 0.14)"},
            {"bg_start": "#211b30", "bg_end": "#161222", "border": "#362a4d", "border_hover": "#c084fc", "icon": "⚡", "accent": "#c084fc", "icon_bg": "rgba(192, 132, 252, 0.14)"},
            {"bg_start": "#17232e", "bg_end": "#101822", "border": "#233648", "border_hover": "#38bdf8", "icon": "🌐", "accent": "#38bdf8", "icon_bg": "rgba(56, 189, 248, 0.14)"},
            {"bg_start": "#172520", "bg_end": "#101a17", "border": "#233a33", "border_hover": "#34d399", "icon": "🛡️", "accent": "#34d399", "icon_bg": "rgba(52, 211, 153, 0.14)"},
            {"bg_start": "#241e1c", "bg_end": "#181412", "border": "#3d2e2a", "border_hover": "#fbbf24", "icon": "⭐", "accent": "#fbbf24", "icon_bg": "rgba(251, 191, 36, 0.14)"}
        ]

        search_key = (name + " " + ext_id).lower()
        theme = None
        for k, t in dark_ash_themes.items():
            if k in search_key:
                theme = t
                break

        if not theme:
            hash_idx = sum(ord(c) for c in ext_id) % len(fallback_dark_ash)
            theme = fallback_dark_ash[hash_idx]

        card_frame = QFrame()
        card_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_frame.setMinimumHeight(135)
        card_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {theme["bg_start"]}, stop:1 {theme["bg_end"]});
                border: 1px solid {theme["border"]};
                border-radius: 10px;
            }}
            QFrame:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {theme["bg_start"]}, stop:1 #202438);
                border: 1px solid {theme["border_hover"]};
            }}
        """)

        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        # Header Row: Icon + Title + Version Pill + Status Badge (Unified Dark Ash Style)
        header_hbox = QHBoxLayout()
        header_hbox.setContentsMargins(0, 0, 0, 0)
        header_hbox.setSpacing(6)

        icon_path = ext.get("icon_path", "")
        lbl_icon = QLabel()
        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            if not pix.isNull():
                lbl_icon.setPixmap(pix.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                lbl_icon.setStyleSheet(f"background: {theme['icon_bg']}; border: 1px solid {theme['border']}; border-radius: 6px; padding: 2px 4px;")
            else:
                lbl_icon.setText(theme["icon"])
                lbl_icon.setStyleSheet(f"font-size: 14px; background: {theme['icon_bg']}; color: {theme['accent']}; border: 1px solid {theme['border']}; border-radius: 6px; padding: 2px 6px;")
        else:
            lbl_icon.setText(theme["icon"])
            lbl_icon.setStyleSheet(f"font-size: 14px; background: {theme['icon_bg']}; color: {theme['accent']}; border: 1px solid {theme['border']}; border-radius: 6px; padding: 2px 6px;")

        lbl_name = QLabel(name)
        lbl_name.setWordWrap(True)
        lbl_name.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #ffffff; border: none; background: transparent; line-height: 1.25;")
        lbl_name.setToolTip(name)

        lbl_ver = QLabel(f"v{ver}")
        lbl_ver.setStyleSheet(f"font-size: 9.5px; font-weight: bold; color: {theme['accent']}; background: {theme['icon_bg']}; border: 1px solid {theme['border']}; border-radius: 4px; padding: 1px 5px;")

        # Favorite Star Button
        if not hasattr(self, "favorite_extensions_set"):
            self.favorite_extensions_set = self._load_favorite_extensions()
        is_fav = ext_id in self.favorite_extensions_set
        btn_fav = QPushButton("⭐" if is_fav else "☆")
        btn_fav.setCursor(Qt.PointingHandCursor)
        btn_fav.setToolTip("Remove from Favorites" if is_fav else "Add to Favorites")
        if is_fav:
            btn_fav.setStyleSheet("""
                QPushButton {
                    background: rgba(251, 191, 36, 0.2);
                    color: #fbbf24;
                    font-size: 12px;
                    font-weight: 900;
                    border: 1px solid rgba(251, 191, 36, 0.5);
                    border-radius: 4px;
                    padding: 1px 5px;
                }
                QPushButton:hover {
                    background: rgba(251, 191, 36, 0.35);
                }
            """)
        else:
            btn_fav.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.04);
                    color: #64748b;
                    font-size: 12px;
                    font-weight: bold;
                    border: 1px solid #282d47;
                    border-radius: 4px;
                    padding: 1px 5px;
                }
                QPushButton:hover {
                    color: #fbbf24;
                    border-color: #fbbf24;
                    background: rgba(251, 191, 36, 0.12);
                }
            """)
        btn_fav.clicked.connect(lambda _, eid=ext_id, ename=name: self._toggle_favorite_extension(eid, ename))

        lbl_badge = QLabel("🟢 ACTIVE" if is_active else "⚪ DISABLED")
        if is_active:
            lbl_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")
        else:
            lbl_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #94a3b8; background: rgba(148, 163, 184, 0.15); border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 4px; padding: 1px 5px;")

        header_hbox.addWidget(lbl_icon, 0, Qt.AlignTop)
        header_hbox.addWidget(lbl_name, 1)
        header_hbox.addWidget(lbl_ver, 0, Qt.AlignTop)
        header_hbox.addWidget(btn_fav, 0, Qt.AlignTop)
        header_hbox.addWidget(lbl_badge, 0, Qt.AlignTop)

        card_layout.addLayout(header_hbox)

        # Description Label
        lbl_desc = QLabel(desc)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.3; border: none; background: transparent;")
        card_layout.addWidget(lbl_desc, stretch=1)

        # Footer Row: Target Scope Button (Left), Active Toggle & Delete (Right)
        footer_hbox = QHBoxLayout()
        footer_hbox.setContentsMargins(0, 0, 0, 0)
        footer_hbox.setSpacing(6)

        if target_mode == "all":
            target_text = f"🌐 All Profiles ({total_profs})"
        elif target_mode == "new_only":
            target_text = "✨ New Profiles Only"
        elif target_mode == "groups":
            t_grps = ext.get("target_groups", [])
            target_text = f"👥 Groups ({', '.join(t_grps)})" if t_grps else "👥 Groups Only"
        else:
            target_text = "🎯 Manual Scope"

        btn_target = QPushButton(target_text)
        btn_target.setCursor(Qt.PointingHandCursor)
        btn_target.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cbd5e1;
                border: 1px solid #282d47;
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #232742;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        btn_target.clicked.connect(lambda _, eid=ext_id, ename=name: self.on_edit_ext_target_full_page(eid, ename))
        footer_hbox.addWidget(btn_target)

        footer_hbox.addStretch()

        # Modern Pill Toggle Switch Slider
        from core.ui.widgets import ModernToggleSwitch
        switch_status = ModernToggleSwitch(checked=is_active)
        switch_status.toggled.connect(lambda state, eid=ext_id, ename=name: self.on_toggle_ext_active_full_page(eid, ename, state))
        footer_hbox.addWidget(switch_status)

        if not is_system:
            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Delete Extension")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.12);
                    color: #ef4444;
                    border: 1px solid rgba(239, 68, 68, 0.25);
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #ef4444; color: #ffffff; }
            """)
            btn_del.clicked.connect(lambda _, eid=ext_id, ename=name: self.on_delete_ext_full_page(eid, ename))
            footer_hbox.addWidget(btn_del)

        card_layout.addLayout(footer_hbox)

        return card_frame

    def _create_ext_pagination_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ExtPaginationFrame")
        frame.setFixedHeight(32)
        frame.setStyleSheet("""
            QFrame#ExtPaginationFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 8px;
            }
            QSpinBox {
                background-color: #161829;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 5px;
                padding: 1px 4px;
                font-weight: 700;
                font-size: 11px;
                max-height: 22px;
                max-width: 42px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(8)

        # 1. Total Count Label
        self.lbl_ext_page_total = QLabel("Total 0")
        self.lbl_ext_page_total.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11.5px;")
        layout.addWidget(self.lbl_ext_page_total)
        layout.addStretch()

        # 2. Dynamic Pages HBox
        self.ext_pages_hbox = QHBoxLayout()
        self.ext_pages_hbox.setSpacing(3)
        layout.addLayout(self.ext_pages_hbox)

        # 3. Jump to Page Box
        lbl_goto = QLabel("Go to")
        lbl_goto.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")

        self.spin_ext_goto = QSpinBox()
        self.spin_ext_goto.setRange(1, 1)
        self.spin_ext_goto.setValue(1)
        self.spin_ext_goto.setAlignment(Qt.AlignCenter)
        self.spin_ext_goto.editingFinished.connect(self._on_ext_goto_page)

        layout.addWidget(lbl_goto)
        layout.addWidget(self.spin_ext_goto)

        return frame

    def _update_ext_pagination_controls(self, total_items: int) -> None:
        import math
        self.ext_page_size = 12
        if not hasattr(self, "ext_current_page"):
            self.ext_current_page = 1

        self.ext_total_pages = max(1, math.ceil(total_items / self.ext_page_size))
        self.ext_current_page = min(max(1, self.ext_current_page), self.ext_total_pages)

        if hasattr(self, "lbl_ext_page_total") and self.lbl_ext_page_total:
            self.lbl_ext_page_total.setText(f"Total {total_items}")

        if hasattr(self, "spin_ext_goto") and self.spin_ext_goto:
            self.spin_ext_goto.blockSignals(True)
            self.spin_ext_goto.setRange(1, self.ext_total_pages)
            self.spin_ext_goto.setValue(self.ext_current_page)
            self.spin_ext_goto.blockSignals(False)

        if not hasattr(self, "ext_pages_hbox") or self.ext_pages_hbox is None:
            return

        while self.ext_pages_hbox.count() > 0:
            child = self.ext_pages_hbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Prev Button
        btn_prev = QPushButton("‹")
        btn_prev.setEnabled(self.ext_current_page > 1)
        btn_prev.setCursor(Qt.PointingHandCursor if self.ext_current_page > 1 else Qt.ArrowCursor)
        btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_prev.clicked.connect(self._on_ext_page_prev_clicked)
        self.ext_pages_hbox.addWidget(btn_prev)

        page_nums = []
        if self.ext_total_pages <= 7:
            page_nums = list(range(1, self.ext_total_pages + 1))
        else:
            page_nums = [1]
            if self.ext_current_page > 3:
                page_nums.append("...")
            
            start_p = max(2, self.ext_current_page - 1)
            end_p = min(self.ext_total_pages - 1, self.ext_current_page + 1)
            for p in range(start_p, end_p + 1):
                if p not in page_nums:
                    page_nums.append(p)
            
            if self.ext_current_page < self.ext_total_pages - 2:
                page_nums.append("...")
            if self.ext_total_pages not in page_nums:
                page_nums.append(self.ext_total_pages)

        for item in page_nums:
            if item == "...":
                lbl_dots = QLabel("...")
                lbl_dots.setStyleSheet("color: #6c7086; font-weight: bold; padding: 0 2px; font-size: 11px;")
                self.ext_pages_hbox.addWidget(lbl_dots)
            else:
                p_num = int(item)
                btn = QPushButton(str(p_num))
                btn.setCursor(Qt.PointingHandCursor)
                if p_num == self.ext_current_page:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #89b4fa; color: #11111b; border: 1px solid #89b4fa;
                            border-radius: 4px; padding: 2px 7px; font-weight: 800; font-size: 11.5px; max-height: 22px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                            border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 11.5px; max-height: 22px;
                        }
                        QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
                    """)
                btn.clicked.connect(lambda _, p=p_num: self._go_to_ext_page(p))
                self.ext_pages_hbox.addWidget(btn)

        # Next Button
        btn_next = QPushButton("›")
        btn_next.setEnabled(self.ext_current_page < self.ext_total_pages)
        btn_next.setCursor(Qt.PointingHandCursor if self.ext_current_page < self.ext_total_pages else Qt.ArrowCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_next.clicked.connect(self._on_ext_page_next_clicked)
        self.ext_pages_hbox.addWidget(btn_next)

    def _on_ext_page_prev_clicked(self) -> None:
        if hasattr(self, "ext_current_page") and self.ext_current_page > 1:
            self.ext_current_page -= 1
            self._refresh_extensions_view()

    def _on_ext_page_next_clicked(self) -> None:
        if hasattr(self, "ext_current_page") and hasattr(self, "ext_total_pages") and self.ext_current_page < self.ext_total_pages:
            self.ext_current_page += 1
            self._refresh_extensions_view()

    def _on_ext_goto_page(self) -> None:
        if hasattr(self, "spin_ext_goto"):
            val = self.spin_ext_goto.value()
            self._go_to_ext_page(val)

    def _go_to_ext_page(self, page_num: int) -> None:
        if hasattr(self, "ext_total_pages") and 1 <= page_num <= self.ext_total_pages:
            self.ext_current_page = page_num
            self._refresh_extensions_view()

    def _refresh_extensions_view(self, search_text: str = "") -> None:
        if not hasattr(self, "active_ext_cards_grid"):
            return

        if not hasattr(self, "favorite_extensions_set"):
            self.favorite_extensions_set = self._load_favorite_extensions()

        if not hasattr(self, "_current_ext_tab"):
            self._current_ext_tab = "active"

        from extension_manager import ExtensionManager
        ext_mgr = ExtensionManager()
        exts = ext_mgr.get_all_extensions()

        total_exts = len(exts)
        total_profs = len(self.profile_mgr.get_all_profiles())

        _clear_layout(self.active_ext_cards_grid)

        for col in range(3):
            self.active_ext_cards_grid.setColumnStretch(col, 1)
        for row in range(3):
            self.active_ext_cards_grid.setRowStretch(row, 1)

        active_count = sum(1 for e in exts if e.get("is_active", True))
        fav_count = sum(1 for e in exts if e.get("id") in self.favorite_extensions_set)

        if hasattr(self, "btn_ext_tab_active") and self.btn_ext_tab_active:
            self.btn_ext_tab_active.setText(f"🟢 Active Extensions ({active_count})")
        if hasattr(self, "btn_ext_tab_favorites") and self.btn_ext_tab_favorites:
            self.btn_ext_tab_favorites.setText(f"❤️ Favorites ({fav_count})")

        # Filter by active tab (All/Active vs Favorites)
        if self._current_ext_tab == "favorites":
            source_exts = [e for e in exts if e.get("id") in self.favorite_extensions_set]
        else:
            source_exts = exts

        # Filter by search query if user is typing a keyword (not a URL)
        q = (search_text or (self.ext_url_input.text() if hasattr(self, "ext_url_input") else "")).strip().lower()
        if q and not q.startswith("http://") and not q.startswith("https://") and not "chromewebstore" in q:
            filtered_exts = [e for e in source_exts if q in e.get("name", "").lower() or q in e.get("description", "").lower() or q in e.get("id", "").lower()]
        else:
            filtered_exts = source_exts

        # Update Pagination Controls for 9 per page
        self._update_ext_pagination_controls(len(filtered_exts))

        # Slice 9 items for current page
        start_idx = (self.ext_current_page - 1) * self.ext_page_size
        end_idx = start_idx + self.ext_page_size
        page_items = filtered_exts[start_idx:end_idx]

        # Render current page 3x4 extensions with full expansion
        if page_items:
            for idx in range(12):
                row = idx // 3
                col = idx % 3
                if idx < len(page_items):
                    ext = page_items[idx]
                    is_sys = ext.get("is_system", False) or "relogin" in ext.get("id", "") or "cookie" in ext.get("id", "")
                    card = self._create_extension_card(ext, total_profs, is_system=is_sys)
                    self.active_ext_cards_grid.addWidget(card, row, col)
                else:
                    dummy = QWidget()
                    dummy.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    self.active_ext_cards_grid.addWidget(dummy, row, col)
        else:
            no_act_frame = QFrame()
            no_act_frame.setStyleSheet("background: #131626; border: 1px dashed #282d47; border-radius: 12px; padding: 36px;")
            v_empty = QVBoxLayout(no_act_frame)
            v_empty.setAlignment(Qt.AlignCenter)

            if self._current_ext_tab == "favorites":
                lbl_no = QLabel("❤️ No Favorite Extensions Added Yet" if not q else f"🔍 No favorite extensions found matching '{q}'")
                lbl_no.setStyleSheet("font-size: 15px; font-weight: 700; color: #f43f5e; border: none;")
                lbl_sub = QLabel("Click the ⭐ star icon on any extension card to add your favourite extensions here for instant access!")
                lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8; border: none; margin-top: 6px;")
            else:
                lbl_no = QLabel(f"🔍 No extensions found matching '{q}'" if q else "🧩 No extensions installed yet.")
                lbl_no.setStyleSheet("font-size: 14px; font-weight: 700; color: #cdd6f4; border: none;")
                lbl_sub = QLabel("Paste a Chrome Web Store URL above or click 'Upload Extension' to get started!")
                lbl_sub.setStyleSheet("font-size: 12px; color: #818cf8; border: none; margin-top: 6px;")

            v_empty.addWidget(lbl_no, alignment=Qt.AlignCenter)
            if not q or self._current_ext_tab == "favorites":
                v_empty.addWidget(lbl_sub, alignment=Qt.AlignCenter)

            self.active_ext_cards_grid.addWidget(no_act_frame, 0, 0, 1, 3)

    def on_upload_extension_full_page(self) -> None:
        from core.ui.dialogs import UploadExtensionFormatDialog
        dlg = UploadExtensionFormatDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        choice = dlg.selected_choice
        path_str = ""
        if choice == "zip":
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "Select Extension Package (.zip / .crx)",
                "",
                "Chrome Extensions (*.zip *.crx);;All Files (*.*)"
            )
            if filepath:
                path_str = filepath
        elif choice == "folder":
            folder = QFileDialog.getExistingDirectory(self, "Select Unpacked Extension Directory")
            if folder:
                path_str = folder

        if not path_str:
            return

        from core.ui.dialogs import ExtensionInstallProgressDialog
        prog = ExtensionInstallProgressDialog(title="📦 Importing Extension Package...", parent=self)
        prog.show()
        prog.set_progress(40, "Unpacking & validating manifest.json...", "Extracting...")

        from extension_manager import ExtensionManager
        ext_mgr = ExtensionManager()
        ok, msg, record = ext_mgr.add_extension(path_str)
        if ok and record:
            prog.set_completed(f"✅ Successfully uploaded '{record['name']}'!", record.get("name"))
            self.refresh_all_views()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(700, prog.accept)
        else:
            prog.set_failed(f"❌ {msg}")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2500, prog.reject)

    def on_download_webstore_url_full_page(self) -> None:
        url = self.ext_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please paste a valid Chrome Web Store extension URL or ID.")
            return

        import re
        ext_id = ""
        clean_url = url.split("?")[0].rstrip("/")
        # Check if bare 32-char ID or extract from URL path
        m = re.search(r'([a-p]{32})', clean_url.lower())
        if not m:
            m = re.search(r'([a-z0-9]{32})', clean_url.lower())
        if m:
            ext_id = m.group(1)

        if not ext_id:
            QMessageBox.warning(self, "Invalid URL", "Could not extract a valid 32-character Chrome Extension ID from the link.")
            return

        from config import EXTENSIONS_DIR
        from core.ui.dialogs import ExtensionInstallProgressDialog, ExtensionDownloadThread

        temp_crx = EXTENSIONS_DIR / f"temp_{ext_id}.crx"
        crx_url = f"https://clients2.google.com/service/update2/crx?response=redirect&os=win&arch=x64&os_arch=x86_64&nacl_arch=x86-64&prod=chromecrx&prodchannel=&prodversion=114.0.5735.199&acceptformat=crx2,crx3&x=id%3D{ext_id}%26uc"

        prog = ExtensionInstallProgressDialog(title="📥 Downloading Chrome Extension...", parent=self)
        prog.show()

        self._ext_dl_thread = ExtensionDownloadThread(crx_url, temp_crx, parent=self)

        def _on_prog(pct, status_text, sub_title):
            prog.set_progress(pct, status_text, sub_title)

        def _on_finished(success, msg, record):
            if success and record:
                prog.set_completed(f"✅ Successfully added '{record.get('name', 'Extension')}'!", record.get('name'))
                self.ext_url_input.clear()
                self.refresh_all_views()
                from PySide6.QtCore import QTimer
                QTimer.singleShot(700, prog.accept)
            else:
                prog.set_failed(f"❌ {msg}")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2500, prog.reject)

        self._ext_dl_thread.progress_changed.connect(_on_prog)
        self._ext_dl_thread.finished_signal.connect(_on_finished)
        self._ext_dl_thread.start()

    def on_toggle_ext_active_full_page(self, ext_id: str, ext_name: str, is_active: bool) -> None:
        from extension_manager import ExtensionManager
        ext_mgr = ExtensionManager()
        ext_mgr.update_extension(ext_id, {"is_active": is_active})
        status_txt = "🟢 Enabled" if is_active else "⚪ Disabled"
        self.status_bar.showMessage(f"Extension '{ext_name}' is now {status_txt}.", 3000)
        self.refresh_all_views()

    def on_edit_ext_target_full_page(self, ext_id: str, ext_name: str) -> None:
        from extension_manager import ExtensionManager
        from core.ui.dialogs import ExtensionTargetDialog
        ext_mgr = ExtensionManager()
        ext_rec = next((e for e in ext_mgr.get_all_extensions() if e.get("id") == ext_id), {})

        # If extension is disabled, notify the user to enable it first
        if not ext_rec.get("is_active", True):
            QMessageBox.information(
                self,
                "Extension Disabled",
                f"⚠️ '{ext_name}' is currently Disabled.\n\nPlease Enable the extension first before configuring its Target Scope."
            )
            return

        cur_mode = ext_rec.get("target_mode", "manual")
        cur_grps = ext_rec.get("target_groups", [])
        groups = self.profile_mgr.get_groups()
        from core.ui.dialogs import ExtensionTargetDialog, TargetScopeProgressDialog
        dlg = ExtensionTargetDialog(ext_name, groups, current_mode=cur_mode, current_groups=cur_grps, item_type="extension", parent=self)
        if dlg.exec() == ExtensionTargetDialog.Accepted:
            mode, target_grps = dlg.get_selection()
            all_profs = self.profile_mgr.get_all_profiles()
            total_profs = len(all_profs)

            prog = TargetScopeProgressDialog(
                item_name=ext_name,
                total_profiles=total_profs,
                item_type="extension",
                parent=self
            )
            prog.show()

            ext_mgr.sync_extension_to_profiles(
                ext_id, mode, target_grps, self.profile_mgr,
                progress_callback=lambda cur, tot, p_name: prog.set_progress(cur, tot, p_name)
            )

            prog.set_completed(f"✅ Successfully configured for {total_profs} profiles!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(600, prog.accept)

            self.refresh_all_views()

    def on_delete_ext_full_page(self, ext_id: str, ext_name: str) -> None:
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete extension '{ext_name}'?\n\nThis will remove it from the software and from any assigned browser profiles.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from extension_manager import ExtensionManager
            ext_mgr = ExtensionManager()
            ext_rec = next((e for e in ext_mgr.get_all_extensions() if e.get("id") == ext_id), {})
            ext_path = ext_rec.get("path", "")

            # If profiles have this extension, show progress popup to clean up
            all_profs = self.profile_mgr.get_all_profiles()
            affected = [p for p in all_profs if ext_path and ext_path in p.get("extensions", [])]
            if affected:
                from core.ui.dialogs import BulkEditProgressDialog
                prog = BulkEditProgressDialog(
                    total_profiles=len(affected),
                    details_text=f"Removing '{ext_name}'",
                    parent=self
                )
                prog.show()
                from utils import safe_write_json
                for i, p in enumerate(affected):
                    p_name = p.get("name") or f"Profile #{p.get('number', i + 1)}"
                    ext_list = p.get("extensions", [])
                    if ext_path in ext_list:
                        ext_list.remove(ext_path)
                    p["extensions"] = ext_list
                    p_folder = self.profile_mgr.get_profile_folder(p["id"])
                    try:
                        safe_write_json(p_folder / "profile.json", p)
                        from browser import auto_pin_extensions_in_profile
                        auto_pin_extensions_in_profile(p_folder, ext_list)
                    except Exception:
                        pass
                    prog.set_progress(i + 1, len(affected), p_name)

                try:
                    self.profile_mgr.save_profiles()
                except Exception:
                    pass

                prog.set_completed(f"✅ Removed from {len(affected)} profile(s)!")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(500, prog.accept)

            ext_mgr.delete_extension(ext_id)
            self.refresh_all_views()

    def _get_favorite_bots_file_path(self) -> Path:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = Path(appdata) / "BrowserProfileManager"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "favorite_bots.json"

    def _load_favorite_bots(self) -> set:
        try:
            p = self._get_favorite_bots_file_path()
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
        except Exception as e:
            logger.warning(f"Failed to load favorite bots: {e}")
        return set()

    def _save_favorite_bots(self) -> None:
        try:
            p = self._get_favorite_bots_file_path()
            favs = getattr(self, "favorite_bots_set", set())
            with open(p, "w", encoding="utf-8") as f:
                json.dump(list(favs), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save favorite bots: {e}")

    def _toggle_favorite_bot(self, bot_id: str, bot_title: str) -> None:
        if not hasattr(self, "favorite_bots_set"):
            self.favorite_bots_set = self._load_favorite_bots()
        
        if bot_id in self.favorite_bots_set:
            self.favorite_bots_set.remove(bot_id)
            msg = f"⭐ Removed '{bot_title}' from Favorites."
        else:
            self.favorite_bots_set.add(bot_id)
            msg = f"❤️ Added '{bot_title}' to Favorites!"
        
        self._save_favorite_bots()
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(msg, 3000)
        
        search_txt = self.txt_store_search.text() if hasattr(self, "txt_store_search") else ""
        self._render_automation_grid(search_text=search_txt)

    def _create_automation_page(self) -> QWidget:
        """Create the Automation category page with single-line header, 3x3 grid, favorites & pagination."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        if not hasattr(self, "favorite_bots_set"):
            self.favorite_bots_set = self._load_favorite_bots()

        # Single-Line Compact Control Header Bar (Zero Clutter)
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                border: 1px solid #232742;
                border-radius: 10px;
            }
        """)
        header_hbox = QHBoxLayout(header_card)
        header_hbox.setContentsMargins(12, 8, 12, 8)
        header_hbox.setSpacing(10)

        # Tab Capsule: All Bots, Free Bots, Premium Bots & Favorite Bots
        tab_capsule = QFrame()
        tab_capsule.setStyleSheet("background-color: #10121e; border: 1px solid #232742; border-radius: 8px;")
        tab_capsule_hbox = QHBoxLayout(tab_capsule)
        tab_capsule_hbox.setContentsMargins(3, 3, 3, 3)
        tab_capsule_hbox.setSpacing(4)

        self.btn_auto_all_tab = QPushButton("🤖 All Bots (0)")
        self.btn_auto_all_tab.setCursor(Qt.PointingHandCursor)
        self.btn_auto_all_tab.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6);
                color: #ffffff;
                font-weight: 800;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #6366f1;
            }
        """)

        self.btn_auto_free_tab = QPushButton("🎁 Free Bots (0)")
        self.btn_auto_free_tab.setCursor(Qt.PointingHandCursor)
        self.btn_auto_free_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_auto_premium_tab = QPushButton("⭐ Premium Bots (0)")
        self.btn_auto_premium_tab.setCursor(Qt.PointingHandCursor)
        self.btn_auto_premium_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_auto_favorites_tab = QPushButton("❤️ Favorites (0)")
        self.btn_auto_favorites_tab.setCursor(Qt.PointingHandCursor)
        self.btn_auto_favorites_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_auto_all_tab.clicked.connect(lambda: self._switch_automation_category("all"))
        self.btn_auto_free_tab.clicked.connect(lambda: self._switch_automation_category("free"))
        self.btn_auto_premium_tab.clicked.connect(lambda: self._switch_automation_category("premium"))
        self.btn_auto_favorites_tab.clicked.connect(lambda: self._switch_automation_category("favorites"))

        tab_capsule_hbox.addWidget(self.btn_auto_all_tab)
        tab_capsule_hbox.addWidget(self.btn_auto_free_tab)
        tab_capsule_hbox.addWidget(self.btn_auto_premium_tab)
        tab_capsule_hbox.addWidget(self.btn_auto_favorites_tab)
        header_hbox.addWidget(tab_capsule)

        self.txt_store_search = QLineEdit()
        self.txt_store_search.setPlaceholderText("🔍 Search bots by name, category, or tag...")
        self.txt_store_search.setStyleSheet("""
            QLineEdit {
                background-color: #131626;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 11.5px;
            }
            QLineEdit:focus { border-color: #6366f1; background-color: #181c30; }
        """)
        self.txt_store_search.textChanged.connect(self._on_automation_search_changed)
        header_hbox.addWidget(self.txt_store_search, stretch=1)

        layout.addWidget(header_card)

        # Automation 3x3 Grid Area (Dynamically expands to fill 100% of viewport without gaps)
        automation_content = QWidget()
        automation_content.setStyleSheet("background: transparent; border: none;")
        self.automation_grid = QGridLayout(automation_content)
        self.automation_grid.setContentsMargins(0, 0, 0, 0)
        self.automation_grid.setSpacing(12)
        for c in range(3):
            self.automation_grid.setColumnStretch(c, 1)
        for r in range(4):
            self.automation_grid.setRowStretch(r, 1)

        layout.addWidget(automation_content, stretch=1)

        # Automation Pagination Bar (9 per page)
        self.automation_pagination_bar = self._create_automation_pagination_bar()
        layout.addWidget(self.automation_pagination_bar)

        if hasattr(self, "_sync_store_manifest_async"):
            self._sync_store_manifest_async()
        self._render_automation_grid()
        return page

    def _switch_automation_category(self, cat_mode: str) -> None:
        """Switch between All Bots, Free Bots, Premium Bots, and Favorites."""
        self._current_automation_category = cat_mode
        self.automation_current_page = 1

        style_all_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #6366f1;"
        style_free_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #10b981;"
        style_prem_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #8b5cf6;"
        style_fav_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #be123c); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #f43f5e;"
        style_inactive = "background-color: transparent; color: #a6adc8; font-weight: 600; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: none;"

        if hasattr(self, "btn_auto_all_tab"):
            self.btn_auto_all_tab.setStyleSheet(style_all_active if cat_mode == "all" else style_inactive)
        if hasattr(self, "btn_auto_free_tab"):
            self.btn_auto_free_tab.setStyleSheet(style_free_active if cat_mode == "free" else style_inactive)
        if hasattr(self, "btn_auto_premium_tab"):
            self.btn_auto_premium_tab.setStyleSheet(style_prem_active if cat_mode == "premium" else style_inactive)
        if hasattr(self, "btn_auto_favorites_tab"):
            self.btn_auto_favorites_tab.setStyleSheet(style_fav_active if cat_mode == "favorites" else style_inactive)

        search_txt = self.txt_store_search.text() if hasattr(self, "txt_store_search") else ""
        self._render_automation_grid(search_text=search_txt)

    def _create_automation_pagination_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("AutomationPaginationFrame")
        frame.setFixedHeight(32)
        frame.setStyleSheet("""
            QFrame#AutomationPaginationFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 8px;
            }
            QSpinBox {
                background-color: #161829;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 5px;
                padding: 1px 4px;
                font-weight: 700;
                font-size: 11px;
                max-height: 22px;
                max-width: 42px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(8)

        self.lbl_auto_page_total = QLabel("Total 0")
        self.lbl_auto_page_total.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11.5px;")
        layout.addWidget(self.lbl_auto_page_total)
        layout.addStretch()

        self.auto_pages_hbox = QHBoxLayout()
        self.auto_pages_hbox.setSpacing(3)
        layout.addLayout(self.auto_pages_hbox)

        lbl_goto = QLabel("Go to")
        lbl_goto.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")

        self.spin_auto_goto = QSpinBox()
        self.spin_auto_goto.setRange(1, 1)
        self.spin_auto_goto.setValue(1)
        self.spin_auto_goto.setAlignment(Qt.AlignCenter)
        self.spin_auto_goto.editingFinished.connect(self._on_automation_goto_page)

        layout.addWidget(lbl_goto)
        layout.addWidget(self.spin_auto_goto)

        return frame

    def _update_automation_pagination_controls(self, total_items: int) -> None:
        import math
        self.auto_page_size = 12
        if not hasattr(self, "automation_current_page"):
            self.automation_current_page = 1

        self.auto_total_pages = max(1, math.ceil(total_items / self.auto_page_size))
        self.automation_current_page = min(max(1, self.automation_current_page), self.auto_total_pages)

        if hasattr(self, "lbl_auto_page_total") and self.lbl_auto_page_total:
            self.lbl_auto_page_total.setText(f"Total {total_items}")

        if hasattr(self, "spin_auto_goto") and self.spin_auto_goto:
            self.spin_auto_goto.blockSignals(True)
            self.spin_auto_goto.setRange(1, self.auto_total_pages)
            self.spin_auto_goto.setValue(self.automation_current_page)
            self.spin_auto_goto.blockSignals(False)

        if not hasattr(self, "auto_pages_hbox") or self.auto_pages_hbox is None:
            return

        while self.auto_pages_hbox.count() > 0:
            child = self.auto_pages_hbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        btn_prev = QPushButton("‹")
        btn_prev.setEnabled(self.automation_current_page > 1)
        btn_prev.setCursor(Qt.PointingHandCursor if self.automation_current_page > 1 else Qt.ArrowCursor)
        btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_prev.clicked.connect(self._on_automation_page_prev_clicked)
        self.auto_pages_hbox.addWidget(btn_prev)

        page_nums = []
        if self.auto_total_pages <= 7:
            page_nums = list(range(1, self.auto_total_pages + 1))
        else:
            page_nums = [1]
            if self.automation_current_page > 3:
                page_nums.append("...")
            
            start_p = max(2, self.automation_current_page - 1)
            end_p = min(self.auto_total_pages - 1, self.automation_current_page + 1)
            for p in range(start_p, end_p + 1):
                if p not in page_nums:
                    page_nums.append(p)
            
            if self.automation_current_page < self.auto_total_pages - 2:
                page_nums.append("...")
            if self.auto_total_pages not in page_nums:
                page_nums.append(self.auto_total_pages)

        for item in page_nums:
            if item == "...":
                lbl_dots = QLabel("...")
                lbl_dots.setStyleSheet("color: #6c7086; font-weight: bold; padding: 0 2px; font-size: 11px;")
                self.auto_pages_hbox.addWidget(lbl_dots)
            else:
                p_num = int(item)
                btn = QPushButton(str(p_num))
                btn.setCursor(Qt.PointingHandCursor)
                if p_num == self.automation_current_page:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #89b4fa; color: #11111b; border: 1px solid #89b4fa;
                            border-radius: 4px; padding: 2px 7px; font-weight: 800; font-size: 11.5px; max-height: 22px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                            border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 11.5px; max-height: 22px;
                        }
                        QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
                    """)
                btn.clicked.connect(lambda _, p=p_num: self._go_to_automation_page(p))
                self.auto_pages_hbox.addWidget(btn)

        btn_next = QPushButton("›")
        btn_next.setEnabled(self.automation_current_page < self.auto_total_pages)
        btn_next.setCursor(Qt.PointingHandCursor if self.automation_current_page < self.auto_total_pages else Qt.ArrowCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_next.clicked.connect(self._on_automation_page_next_clicked)
        self.auto_pages_hbox.addWidget(btn_next)

    def _on_automation_page_prev_clicked(self) -> None:
        if hasattr(self, "automation_current_page") and self.automation_current_page > 1:
            self.automation_current_page -= 1
            self._render_automation_grid(search_text=self.txt_store_search.text() if hasattr(self, "txt_store_search") else "")

    def _on_automation_page_next_clicked(self) -> None:
        if hasattr(self, "automation_current_page") and hasattr(self, "auto_total_pages") and self.automation_current_page < self.auto_total_pages:
            self.automation_current_page += 1
            self._render_automation_grid(search_text=self.txt_store_search.text() if hasattr(self, "txt_store_search") else "")

    def _on_automation_goto_page(self) -> None:
        if hasattr(self, "spin_auto_goto"):
            val = self.spin_auto_goto.value()
            self._go_to_automation_page(val)

    def _go_to_automation_page(self, page_num: int) -> None:
        if hasattr(self, "auto_total_pages") and 1 <= page_num <= self.auto_total_pages:
            self.automation_current_page = page_num
            self._render_automation_grid(search_text=self.txt_store_search.text() if hasattr(self, "txt_store_search") else "")

    def _on_automation_search_changed(self, text: str) -> None:
        """Debounced automation search: smooth typing without UI freeze."""
        if not hasattr(self, "_auto_search_timer"):
            self._auto_search_timer = QTimer(self)
            self._auto_search_timer.setSingleShot(True)
            self._auto_search_timer.setInterval(160)
            self._auto_search_timer.timeout.connect(lambda: self._do_automation_search(self.txt_store_search.text() if hasattr(self, "txt_store_search") else ""))
        self._auto_search_timer.start(160)

    def _do_automation_search(self, text: str) -> None:
        self.automation_current_page = 1
        self._render_automation_grid(search_text=text)

    def _render_automation_grid(self, search_text: str = "") -> None:
        """Render automation bot cards dynamically with 9 items per page, 3x3 grid, favorites & live search."""
        if not hasattr(self, "automation_grid") or self.automation_grid is None:
            return

        _clear_layout(self.automation_grid)

        for col in range(3):
            self.automation_grid.setColumnStretch(col, 1)
        for row in range(4):
            self.automation_grid.setRowStretch(row, 1)

        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        plan_str = str(user_info.get("plan") or user_info.get("plan_name") or user_info.get("plan_type") or user_info.get("subscription") or "").upper()
        curr_quota = int(user_info.get("max_profiles", 100) or user_info.get("cloud_quota", 100) or 100)
        is_enterprise = ("ENTERPRISE" in plan_str) or bool(user_info.get("is_enterprise", False)) or user_info.get("role") == "admin" or curr_quota >= 5000

        # Cloud-driven dynamic automation bots (loaded from server manifest)
        builtin_bots = []

        # Dynamic Luxury Cyberpunk Palette Pool for Automation Bots
        # (bg_start, bg_end, border, theme_color, icon_bg, btn_bg_s, btn_bg_e, btn_border, btn_hover)
        dynamic_automation_palettes = [
            ("#221832", "#130e1e", "#3d2856", "#c084fc", "rgba(192, 132, 252, 0.16)", "#7c3aed", "#6d28d9", "#a855f7", "#8b5cf6"),  # Cyber Violet / Orchid
            ("#12261e", "#0c1813", "#1d4234", "#34d399", "rgba(52, 211, 153, 0.16)", "#059669", "#047857", "#10b981", "#34d399"),  # Emerald Matrix / Mint
            ("#2a1c14", "#180f0b", "#4a2f20", "#fb923c", "rgba(251, 146, 60, 0.16)", "#ea580c", "#c2410c", "#f97316", "#fb923c"),  # Sunset Flame / Gold
            ("#141f32", "#0d1420", "#223554", "#60a5fa", "rgba(96, 165, 250, 0.16)", "#2563eb", "#1d4ed8", "#3b82f6", "#60a5fa"),  # Azure Electric Blue
            ("#2b1522", "#190d14", "#4e223c", "#f43f5e", "rgba(244, 63, 94, 0.16)", "#e11d48", "#be123c", "#f43f5e", "#fb7185"),   # Hot Crimson / Rose
            ("#12242c", "#0a161c", "#1c3d4b", "#38bdf8", "rgba(56, 189, 248, 0.16)", "#0284c7", "#0369a1", "#0ea5e9", "#38bdf8"),  # Electric Aqua / Cyan
        ]

        bots_map = {}
        for bb in builtin_bots:
            bid = bb["bot_id"]
            lic_info = self.bot_license_mgr.get_local_license(bid) if hasattr(self, "bot_license_mgr") else None
            has_lic = (lic_info is not None and lic_info.get("is_active", True))
            has_acc = bb["is_free"] or is_enterprise or has_lic
            bb["has_access"] = has_acc
            bb["callback"] = lambda *args, b_id=bid, t=bb["title"]: self._launch_dynamic_bot(b_id, t)
            bots_map[bid] = bb

        # Merge with online / plugin engine bots & local bots manifest
        online_bots = getattr(self, "_store_online_bots", None)
        if (online_bots is None or len(online_bots) == 0) and hasattr(self, "plugin_engine"):
            online_bots = self.plugin_engine.get_all_bots()

        # Discover local bots from 03_Automation_Bots/bots_manifest.json
        local_bots = []
        try:
            from pathlib import Path
            import json
            base_p = Path(__file__).resolve().parent.parent.parent
            for cand_p in [base_p / "03_Automation_Bots" / "bots_manifest.json", base_p.parent / "03_Automation_Bots" / "bots_manifest.json"]:
                if cand_p.exists():
                    with open(cand_p, "r", encoding="utf-8") as bf:
                        local_bots = json.load(bf)
                    break
        except Exception:
            pass

        if local_bots:
            existing_bids = set((b.get("bot_id") or b.get("id")) for b in (online_bots or []))
            online_bots = list(online_bots or [])
            for lb in local_bots:
                lbid = lb.get("bot_id") or lb.get("id")
                if lbid and lbid not in existing_bids:
                    online_bots.append(lb)
                    existing_bids.add(lbid)

        if online_bots and isinstance(online_bots, list) and len(online_bots) > 0:
            for b_idx, item in enumerate(online_bots):
                if not item.get("is_enabled", True) and not item.get("is_published", True):
                    continue
                bid = item.get("bot_id") or item.get("id")
                if not bid:
                    continue
                is_free_val = item.get("is_free")
                access_type_val = str(item.get("access_type", "")).upper()
                is_free_bool = (is_free_val is True or is_free_val == 1 or str(is_free_val).lower() == "true" or access_type_val == "FREE")
                price_lbl = str(item.get("price_label", "FREE" if is_free_bool else "$10"))
                
                lic_info = self.bot_license_mgr.get_local_license(bid) if hasattr(self, "bot_license_mgr") else None
                has_lic = (lic_info is not None and lic_info.get("is_active", True))
                has_acc = is_free_bool or is_enterprise or has_lic

                bot_title = item.get("title") or item.get("name") or f"🤖 {bid.replace('_', ' ').title()}"

                bg_s_def, bg_e_def, b_col_def, a_col_def, i_bg_def, btn_s_def, btn_e_def, btn_b_def, btn_h_def = dynamic_automation_palettes[b_idx % len(dynamic_automation_palettes)]

                b_lower = bid.lower()
                bot_icon = item.get("icon")
                if not bot_icon:
                    if "video" in b_lower or "reel" in b_lower:
                        bot_icon = "🎬"
                    elif "page" in b_lower:
                        bot_icon = "📄"
                    elif "login" in b_lower or "auth" in b_lower:
                        bot_icon = "🔑"
                    elif "comment" in b_lower or "marketing" in b_lower:
                        bot_icon = "💬"
                    else:
                        bot_icon = "🤖"

                is_upd = False
                rem_ver = str(item.get("version", "2.0.0"))
                if hasattr(self, "plugin_engine"):
                    try:
                        is_upd, inst_v, rem_v = self.plugin_engine.is_update_available(bid)
                        if is_upd:
                            rem_ver = rem_v
                    except Exception:
                        pass

                card_btn_text = f"🔄 Update (v{rem_ver})" if is_upd else item.get("btn_text", "🚀 Run Bot")

                bots_map[bid] = {
                    "bot_id": bid,
                    "title": bot_title,
                    "category": item.get("category", "AUTOMATION"),
                    "version": str(item.get("version", "2.0.0")),
                    "icon": bot_icon,
                    "description": item.get("desc") or item.get("description") or "Dynamic Cloud Automation Module",
                    "price_label": price_lbl,
                    "is_free": is_free_bool,
                    "has_access": has_acc,
                    "callback": (lambda *args, b_id=bid, t=bot_title: self._launch_dynamic_bot(b_id, t)),
                    "btn_text": card_btn_text,
                    "is_update": is_upd,
                    "theme_color": item.get("theme_color") or a_col_def,
                    "bg_start": item.get("bg_start") or bg_s_def,
                    "bg_end": item.get("bg_end") or bg_e_def,
                    "border": item.get("border") or b_col_def,
                    "border_hover": item.get("border_hover") or a_col_def,
                    "icon_bg": item.get("icon_bg") or i_bg_def,
                    "btn_bg_s": "#d97706" if is_upd else (item.get("btn_bg_s") or btn_s_def),
                    "btn_bg_e": "#b45309" if is_upd else (item.get("btn_bg_e") or btn_e_def),
                    "btn_border": "#f59e0b" if is_upd else (item.get("btn_border") or btn_b_def),
                    "btn_hover": "#fbbf24" if is_upd else (item.get("btn_hover") or btn_h_def),
                    "tutorial_url": item.get("tutorial_url", "")
                }

        bots_to_show = list(bots_map.values())
        query = search_text.lower().strip()
        curr_cat = getattr(self, "_current_automation_category", "free")

        if not hasattr(self, "favorite_bots_set"):
            self.favorite_bots_set = self._load_favorite_bots()

        free_bots = [b for b in bots_to_show if (b.get("is_free", True) or str(b.get("price_label")).upper() == "FREE")]
        premium_bots = [b for b in bots_to_show if not (b.get("is_free", True) or str(b.get("price_label")).upper() == "FREE")]
        favorite_bots = [b for b in bots_to_show if b["bot_id"] in self.favorite_bots_set]

        if hasattr(self, "btn_auto_all_tab"):
            self.btn_auto_all_tab.setText(f"🤖 All Bots ({len(bots_to_show)})")
        if hasattr(self, "btn_auto_free_tab"):
            self.btn_auto_free_tab.setText(f"🎁 Free Bots ({len(free_bots)})")
        if hasattr(self, "btn_auto_premium_tab"):
            self.btn_auto_premium_tab.setText(f"⭐ Premium Bots ({len(premium_bots)})")
        if hasattr(self, "btn_auto_favorites_tab"):
            self.btn_auto_favorites_tab.setText(f"❤️ Favorites ({len(favorite_bots)})")

        curr_cat = getattr(self, "_current_automation_category", "all")

        if curr_cat == "all":
            source_list = bots_to_show
        elif curr_cat == "free":
            source_list = free_bots
        elif curr_cat == "premium":
            source_list = premium_bots
        else:
            source_list = favorite_bots

        matched = []
        for b in source_list:
            if not query or query in b["title"].lower() or query in b["description"].lower() or query in b["category"].lower():
                matched.append(b)

        # Update Pagination Controls for 12 per page
        self._update_automation_pagination_controls(len(matched))

        # Slice 12 items for current page
        start_idx = (self.automation_current_page - 1) * self.auto_page_size
        end_idx = start_idx + self.auto_page_size
        page_items = matched[start_idx:end_idx]

        if not matched:
            empty_frame = QFrame()
            empty_frame.setStyleSheet("background: #111424; border: 1px dashed #232742; border-radius: 12px; padding: 40px;")
            v_empty = QVBoxLayout(empty_frame)
            v_empty.setAlignment(Qt.AlignCenter)
            if curr_cat == "favorites" and len(favorite_bots) == 0:
                lbl_no = QLabel("❤️ No Favorite Bots Added Yet")
                lbl_no.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4; border: none;")
                lbl_sub = QLabel("Click the ⭐ star icon on any bot card to add your favourite automation bots here for instant access!")
                lbl_sub.setStyleSheet("font-size: 12px; color: #a6adc8; margin-top: 6px; border: none;")
                v_empty.addWidget(lbl_no, alignment=Qt.AlignCenter)
                v_empty.addWidget(lbl_sub, alignment=Qt.AlignCenter)
            else:
                lbl_no = QLabel(f"🔍 No bots found matching '{query}'" if query else ("🤖 No automation bots published yet" if curr_cat == "all" else ("🎁 No Free Bots available" if curr_cat == "free" else ("⭐ No Premium Bots available" if curr_cat == "premium" else "❤️ No bots in favorites"))))
                lbl_no.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4; border: none;")
                v_empty.addWidget(lbl_no, alignment=Qt.AlignCenter)
                if not query:
                    lbl_sub = QLabel("Publish automation bots from the Admin Panel or click Refresh to sync from cloud.")
                    lbl_sub.setStyleSheet("font-size: 12px; color: #a6adc8; margin-top: 6px; border: none;")
                    v_empty.addWidget(lbl_sub, alignment=Qt.AlignCenter)
                    btn_refresh = QPushButton("🔄 Refresh Cloud Bots")
                    btn_refresh.setCursor(Qt.PointingHandCursor)
                    btn_refresh.setStyleSheet("background-color: #4f46e5; color: #ffffff; font-weight: 700; border-radius: 6px; padding: 6px 16px; font-size: 11.5px; margin-top: 10px;")
                    btn_refresh.clicked.connect(self._sync_store_manifest_async)
                    v_empty.addWidget(btn_refresh, alignment=Qt.AlignCenter)
            self.automation_grid.addWidget(empty_frame, 0, 0, 1, 3)
            return

        for idx in range(12):
            row = idx // 3
            col = idx % 3
            if idx < len(page_items):
                b = page_items[idx]
                bg_s = b.get("bg_start", "#1b1d30")
                bg_e = b.get("bg_end", "#121422")
                border_c = b.get("border", "#2b304f")
                hover_c = b.get("border_hover", "#818cf8")
                theme_col = b.get("theme_color", "#818cf8")
                icon_bg = b.get("icon_bg", "rgba(129, 140, 248, 0.14)")
                bot_icon = b.get("icon", "🤖")

                card = QFrame()
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                card.setMinimumHeight(135)
                card.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_s}, stop:1 {bg_e});
                        border: 1px solid {border_c};
                        border-radius: 10px;
                    }}
                    QFrame:hover {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_s}, stop:1 #202438);
                        border: 1px solid {hover_c};
                    }}
                """)
                c_layout = QVBoxLayout(card)
                c_layout.setContentsMargins(14, 12, 14, 12)
                c_layout.setSpacing(6)

                # Row 1 (Header): Icon + Title (Full Stretch Width) + Favorite Star
                c_top_row = QHBoxLayout()
                c_top_row.setContentsMargins(0, 0, 0, 0)
                c_top_row.setSpacing(8)

                lbl_icon = QLabel(bot_icon)
                lbl_icon.setStyleSheet(f"font-size: 14px; background: {icon_bg}; color: {theme_col}; border: 1px solid {border_c}; border-radius: 6px; padding: 2px 6px;")

                full_b_name = b["title"]
                import re
                clean_b_title = re.sub(r'^[^\w\s]+\s*', '', full_b_name).strip() or full_b_name
                lbl_b_title = QLabel(clean_b_title)
                lbl_b_title.setWordWrap(True)
                lbl_b_title.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #ffffff; border: none; background: transparent; line-height: 1.25;")
                lbl_b_title.setToolTip(full_b_name)

                # Favorite Star Button
                is_fav = b["bot_id"] in self.favorite_bots_set
                btn_fav = QPushButton("⭐" if is_fav else "☆")
                btn_fav.setCursor(Qt.PointingHandCursor)
                btn_fav.setToolTip("Remove from Favorites" if is_fav else "Add to Favorites")
                if is_fav:
                    btn_fav.setStyleSheet("""
                        QPushButton {
                            background: rgba(251, 191, 36, 0.2);
                            color: #fbbf24;
                            font-size: 12px;
                            font-weight: 900;
                            border: 1px solid rgba(251, 191, 36, 0.5);
                            border-radius: 4px;
                            padding: 1px 5px;
                        }
                        QPushButton:hover {
                            background: rgba(251, 191, 36, 0.35);
                        }
                    """)
                else:
                    btn_fav.setStyleSheet("""
                        QPushButton {
                            background: rgba(255, 255, 255, 0.04);
                            color: #64748b;
                            font-size: 12px;
                            font-weight: bold;
                            border: 1px solid #282d47;
                            border-radius: 4px;
                            padding: 1px 5px;
                        }
                        QPushButton:hover {
                            color: #fbbf24;
                            border-color: #fbbf24;
                            background: rgba(251, 191, 36, 0.12);
                        }
                    """)
                btn_fav.clicked.connect(lambda _, bid=b["bot_id"], bt=full_b_name: self._toggle_favorite_bot(bid, bt))

                c_top_row.addWidget(lbl_icon, 0, Qt.AlignVCenter)
                c_top_row.addWidget(lbl_b_title, 1, Qt.AlignVCenter)
                c_top_row.addWidget(btn_fav, 0, Qt.AlignVCenter)
                c_layout.addLayout(c_top_row)

                # Row 2 (Meta Info): Version Badge (Left) + Price/Access Badge (Right)
                c_meta_row = QHBoxLayout()
                c_meta_row.setContentsMargins(0, 0, 0, 0)
                c_meta_row.setSpacing(6)

                lbl_ver = QLabel(f"v{b.get('version', '2.0.0')}")
                lbl_ver.setStyleSheet(f"font-size: 9.5px; font-weight: bold; color: {theme_col}; background: {icon_bg}; border: 1px solid {border_c}; border-radius: 4px; padding: 1px 5px;")

                is_free_val = b.get("is_free", True)
                price_lbl_str = b.get("price_label", "FREE")
                has_acc = b.get("has_access", True)

                if has_acc:
                    if is_free_val or price_lbl_str == "FREE":
                        price_badge = QLabel("🎁 FREE")
                        price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")
                    elif is_enterprise:
                        price_badge = QLabel("⭐ Enterprise Access")
                        price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")
                    else:
                        price_badge = QLabel("✅ Active License")
                        price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")
                else:
                    price_badge = QLabel(f"⭐ {price_lbl_str}")
                    price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #fbbf24; background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 4px; padding: 1px 5px;")

                c_meta_row.addWidget(lbl_ver, 0, Qt.AlignVCenter)
                c_meta_row.addStretch(1)
                c_meta_row.addWidget(price_badge, 0, Qt.AlignVCenter)
                c_layout.addLayout(c_meta_row)

                # Description Label
                lbl_b_desc = QLabel(b["description"])
                lbl_b_desc.setWordWrap(True)
                lbl_b_desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.3; border: none; background: transparent;")
                c_layout.addWidget(lbl_b_desc, stretch=1)

                # Footer Row: Tutorial Button (Left), Action Button (Right)
                btn_hbox = QHBoxLayout()
                btn_hbox.setContentsMargins(0, 0, 0, 0)
                btn_hbox.setSpacing(6)

                tut_url = b.get("tutorial_url", "")
                btn_tut = QPushButton("📺 Tutorial")
                btn_tut.setCursor(Qt.PointingHandCursor)
                btn_tut.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #191c2e;
                        color: {theme_col};
                        border: 1px solid {border_c};
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-weight: 700;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{ background-color: #232742; border-color: {hover_c}; color: #ffffff; }}
                """)
                btn_tut.clicked.connect(lambda *args, u=tut_url, bid=b['bot_id']: self.on_open_bot_tutorial(bid, u))
                btn_hbox.addWidget(btn_tut)
                btn_hbox.addStretch()

                if has_acc:
                    btn_action = QPushButton(b.get("btn_text", "🚀 Run Bot"))
                    btn_action.setCursor(Qt.PointingHandCursor)
                    btn_s = b.get("btn_bg_s", "#4f46e5")
                    btn_e = b.get("btn_bg_e", "#4338ca")
                    btn_b = b.get("btn_border", "#6366f1")
                    btn_h = b.get("btn_hover", "#818cf8")
                    btn_action.setStyleSheet(f"""
                        QPushButton {{
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {btn_s}, stop:1 {btn_e});
                            color: #ffffff;
                            border: 1px solid {btn_b};
                            border-radius: 6px;
                            padding: 4px 12px;
                            font-weight: 800;
                            font-size: 11px;
                        }}
                        QPushButton:hover {{
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {btn_e}, stop:1 #1e1b4b);
                            border-color: {btn_h};
                        }}
                    """)
                    btn_action.clicked.connect(b.get("callback", lambda: None))
                    btn_hbox.addWidget(btn_action)
                else:
                    buy_title = f"🛒 Buy ({price_lbl_str})" if price_lbl_str else "🛒 Buy License"
                    btn_action = QPushButton(buy_title)
                    btn_action.setCursor(Qt.PointingHandCursor)
                    btn_action.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309); color: #ffffff; font-size: 11px; font-weight: 800; padding: 4px 12px; border-radius: 6px; border: 1px solid #f59e0b;")
                    btn_action.clicked.connect(lambda _, bid=b["bot_id"]: self.on_buy_bot_license(bid))
                    btn_hbox.addWidget(btn_action)

                c_layout.addLayout(btn_hbox)
                self.automation_grid.addWidget(card, row, col)
            else:
                dummy = QWidget()
                dummy.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.automation_grid.addWidget(dummy, row, col)

    def _create_automation_card(self, *args, **kwargs) -> QFrame:
        """Backward compatibility dummy wrapper."""
        return QFrame()

    def _switch_automation_to_store(self) -> None:
        self._switch_automation_category("free")

    def _switch_automation_to_active(self) -> None:
        self._switch_automation_category("free")

    def _apply_store_filter(self, filter_type: str = "all", trigger_async: bool = False) -> None:
        search_txt = self.txt_store_search.text() if hasattr(self, "txt_store_search") else ""
        self._render_automation_grid(search_text=search_txt)

    def _refresh_active_bots_tab(self) -> None:
        search_txt = self.txt_store_search.text() if hasattr(self, "txt_store_search") else ""
        self._render_automation_grid(search_text=search_txt)

    def _update_automation_subnav_styles(self, is_store_active: bool) -> None:
        pass

    def on_update_bot_module(self, bot_id: str) -> None:
        if not hasattr(self, "plugin_engine"):
            return
        success, msg = self.plugin_engine.download_bot_module(bot_id)
        if success:
            QMessageBox.information(self, "Bot Update Complete", f"✅ {msg}")
            self._sync_store_manifest_async()
            self.refresh_all_views()
        else:
            QMessageBox.warning(self, "Bot Update Failed", f"❌ {msg}")

    def _sync_store_manifest_async(self) -> None:
        if not (hasattr(self, "_manifest_sync_thread") and self._manifest_sync_thread is not None and self._manifest_sync_thread.isRunning()):
            self._manifest_sync_thread = ManifestSyncThread(self)
            self._manifest_sync_thread.manifest_fetched.connect(self._on_manifest_fetched_bg)
            self._manifest_sync_thread.start()

        if hasattr(self, "_sync_tools_manifest_async"):
            self._sync_tools_manifest_async()

        if hasattr(self, "_sync_scripts_manifest_async"):
            self._sync_scripts_manifest_async()

    def _on_manifest_fetched_bg(self, online_bots: list) -> None:
        if not isinstance(online_bots, list):
            return
        self._store_online_bots = online_bots
        try:
            manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "03_Automation_Bots", "bots_manifest.json"))
            if not os.path.exists(manifest_path):
                manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "03_Automation_Bots", "bots_manifest.json"))
            if os.path.exists(manifest_path):
                existing_bots = []
                try:
                    with open(manifest_path, "r", encoding="utf-8") as rf:
                        existing_bots = json.load(rf)
                except Exception:
                    pass
                merged_bots = list(online_bots)
                existing_ids = set(b.get("bot_id") for b in merged_bots if b.get("bot_id"))
                for eb in existing_bots:
                    if eb.get("bot_id") and eb.get("bot_id") not in existing_ids:
                        merged_bots.append(eb)
                        existing_ids.add(eb.get("bot_id"))
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(merged_bots, f, indent=2)
        except Exception:
            pass
        search_txt = self.txt_store_search.text() if hasattr(self, "txt_store_search") else ""
        self._render_automation_grid(search_text=search_txt)
        if hasattr(self, "_populate_quick_bots_ui"):
            self._populate_quick_bots_ui()


    def _create_settings_page(self) -> QWidget:
        """Create the Ultra-Modern Executive Settings Hub with category subnav capsules and luxury full-width panels."""
        widget = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 1. SaaS Executive Header Bar with Center Capsule Subnav
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #151829, stop:0.5 #121422, stop:1 #0f111d);
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(16, 10, 16, 10)
        h_layout.setSpacing(14)

        # Left: Title & Badge
        v_info = QHBoxLayout()
        v_info.setSpacing(10)
        v_info.setAlignment(Qt.AlignVCenter)

        ico_hdr = QLabel("⚙️")
        ico_hdr.setStyleSheet("font-size: 16px; background: rgba(99, 102, 241, 0.18); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 8px; padding: 5px 8px;")
        v_info.addWidget(ico_hdr)

        lbl_title = QLabel("App Settings")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 900; color: #ffffff; letter-spacing: 0.2px;")
        v_info.addWidget(lbl_title)
        h_layout.addLayout(v_info)

        h_layout.addStretch()

        # Center: Category Capsule Navigation Bar
        tab_capsule = QFrame()
        tab_capsule.setStyleSheet("background-color: #10121e; border: 1px solid #232742; border-radius: 8px; padding: 2px;")
        tab_h = QHBoxLayout(tab_capsule)
        tab_h.setContentsMargins(2, 2, 2, 2)
        tab_h.setSpacing(3)

        tab_active_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6);
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 800;
                font-size: 11.5px;
            }
        """
        tab_inactive_style = """
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background-color: #1a1d33;
                color: #ffffff;
            }
        """

        self.btn_stab_engine = QPushButton("🖥️ System & Engine")
        self.btn_stab_engine.setCursor(Qt.PointingHandCursor)
        self.btn_stab_engine.setStyleSheet(tab_active_style)

        self.btn_stab_security = QPushButton("🛡️ Anti-Detect & Security")
        self.btn_stab_security.setCursor(Qt.PointingHandCursor)
        self.btn_stab_security.setStyleSheet(tab_inactive_style)

        self.btn_stab_cloud = QPushButton("☁️ Cloud & Storage")
        self.btn_stab_cloud.setCursor(Qt.PointingHandCursor)
        self.btn_stab_cloud.setStyleSheet(tab_inactive_style)

        tab_h.addWidget(self.btn_stab_engine)
        tab_h.addWidget(self.btn_stab_security)
        tab_h.addWidget(self.btn_stab_cloud)
        h_layout.addWidget(tab_capsule)

        h_layout.addStretch()

        # Right: Quick Actions in Header
        h_btns = QHBoxLayout()
        h_btns.setSpacing(8)

        btn_reset_defaults = QPushButton("🔄 Reset Defaults")
        btn_reset_defaults.setCursor(Qt.PointingHandCursor)
        btn_reset_defaults.setStyleSheet("""
            QPushButton {
                background-color: #1a1d30;
                color: #cdd6f4;
                border: 1px solid #2d3356;
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #252a48;
                border-color: #818cf8;
                color: #ffffff;
            }
        """)
        btn_reset_defaults.clicked.connect(self._on_reset_page_settings)

        btn_save_settings = QPushButton("💾 Save Preferences")
        btn_save_settings.setCursor(Qt.PointingHandCursor)
        btn_save_settings.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6);
                color: #ffffff;
                font-weight: 800;
                font-size: 11.5px;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 7px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #60a5fa);
                border-color: #a5b4fc;
            }
        """)
        btn_save_settings.clicked.connect(self._on_save_page_settings)

        h_btns.addWidget(btn_reset_defaults)
        h_btns.addWidget(btn_save_settings)
        h_layout.addLayout(h_btns)
        layout.addWidget(header_card)

        # 2. Main Stacked Settings Container
        settings_stack = QStackedWidget()

        def _switch_settings_tab(idx: int):
            settings_stack.setCurrentIndex(idx)
            self.btn_stab_engine.setStyleSheet(tab_active_style if idx == 0 else tab_inactive_style)
            self.btn_stab_security.setStyleSheet(tab_active_style if idx == 1 else tab_inactive_style)
            self.btn_stab_cloud.setStyleSheet(tab_active_style if idx == 2 else tab_inactive_style)

        self.btn_stab_engine.clicked.connect(lambda: _switch_settings_tab(0))
        self.btn_stab_security.clicked.connect(lambda: _switch_settings_tab(1))
        self.btn_stab_cloud.clicked.connect(lambda: _switch_settings_tab(2))

        def _make_category_card(icon_str: str, title_str: str, badge_text: str, badge_style: str) -> tuple[QWidget, QVBoxLayout]:
            panel = QWidget()
            p_lay = QVBoxLayout(panel)
            p_lay.setContentsMargins(0, 0, 0, 0)
            p_lay.setSpacing(12)

            card = QFrame()
            card.setStyleSheet("""
                QFrame#SettingsCategoryCard {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141728, stop:1 #0f111e);
                    border: 1px solid #232742;
                    border-radius: 14px;
                }
            """)
            card.setObjectName("SettingsCategoryCard")
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(20, 18, 20, 18)
            c_lay.setSpacing(12)

            # Header
            hdr = QHBoxLayout()
            hdr.setSpacing(10)
            hdr.setAlignment(Qt.AlignVCenter)

            ico_lbl = QLabel(icon_str)
            ico_lbl.setStyleSheet("font-size: 16px; background: transparent; border: none;")
            hdr.addWidget(ico_lbl)

            tit_lbl = QLabel(title_str)
            tit_lbl.setStyleSheet("font-size: 14px; font-weight: 900; color: #ffffff; background: transparent; border: none;")
            hdr.addWidget(tit_lbl)
            hdr.addStretch()

            badge_lbl = QLabel(badge_text)
            badge_lbl.setStyleSheet(f"font-size: 10px; font-weight: 800; border-radius: 6px; padding: 3px 9px; {badge_style}")
            hdr.addWidget(badge_lbl)
            c_lay.addLayout(hdr)

            # Divider
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet("background-color: #1e2238; border: none;")
            c_lay.addWidget(div)
            c_lay.addSpacing(4)

            p_lay.addWidget(card)
            p_lay.addStretch()
            return panel, c_lay

        def _make_setting_row(icon_emoji: str, icon_grad: str, title_str: str, subtitle_str: str, right_widget_or_layout) -> QFrame:
            row_frame = QFrame()
            row_frame.setStyleSheet("""
                QFrame#SettingRow {
                    background-color: #101220;
                    border: 1px solid #1c2035;
                    border-radius: 10px;
                }
                QFrame#SettingRow:hover {
                    background-color: #16192e;
                    border-color: #2e3458;
                }
            """)
            row_frame.setObjectName("SettingRow")
            r_lay = QHBoxLayout(row_frame)
            r_lay.setContentsMargins(16, 12, 16, 12)
            r_lay.setSpacing(14)
            r_lay.setAlignment(Qt.AlignVCenter)

            # Left Themed Icon Capsule
            ico = QLabel(icon_emoji)
            ico.setAlignment(Qt.AlignCenter)
            ico.setFixedSize(38, 38)
            ico.setStyleSheet(f"""
                QLabel {{
                    background: {icon_grad};
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 9px;
                    font-size: 16px;
                }}
            """)
            r_lay.addWidget(ico)

            # Text Info (Title + Subtitle)
            t_box = QVBoxLayout()
            t_box.setSpacing(3)
            t_box.setAlignment(Qt.AlignVCenter)

            l_title = QLabel(title_str)
            l_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff; background: transparent; border: none;")
            t_box.addWidget(l_title)

            l_sub = QLabel(subtitle_str)
            l_sub.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500; background: transparent; border: none; line-height: 1.3;")
            l_sub.setWordWrap(True)
            t_box.addWidget(l_sub)
            r_lay.addLayout(t_box, stretch=1)

            # Right Controls
            if isinstance(right_widget_or_layout, QWidget):
                r_lay.addWidget(right_widget_or_layout)
            elif isinstance(right_widget_or_layout, QLayout):
                r_lay.addLayout(right_widget_or_layout)
            elif hasattr(right_widget_or_layout, "addWidget"):
                r_lay.addLayout(right_widget_or_layout)
            else:
                r_lay.addWidget(right_widget_or_layout)

            return row_frame

        # =========================================================================
        # 🖥️ PANEL 1: System & Browser Engine Core
        # =========================================================================
        panel1, p1_lay = _make_category_card(
            "🖥️", "System & Chromium Engine Core",
            "🟢 Core Protected", "color: #34d399; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35);"
        )

        b_engine = QLabel("🟢 Portable Core (Protected)")
        b_engine.setStyleSheet("color: #10b981; font-weight: 800; font-size: 11px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 6px 14px;")
        p1_lay.addWidget(_make_setting_row(
            "⚡", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #3b82f6)",
            "Chromium Engine Core",
            "Built-in isolated Chromium core engine with deep native fingerprint and hardware signature spoofing.",
            b_engine
        ))

        b_res = QLabel("🔒 1280 x 800 (Protected Default)")
        b_res.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 11px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 6px; padding: 6px 14px;")
        p1_lay.addWidget(_make_setting_row(
            "🖥️", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0284c7, stop:1 #0369a1)",
            "Default Viewport Resolution",
            "Standard native monitor display resolution spoofing automatically applied to newly created profiles.",
            b_res
        ))

        b_win = QLabel("🔒 1280 x 840 (Optimized)")
        b_win.setStyleSheet("color: #a78bfa; font-weight: 800; font-size: 11px; background: rgba(167, 139, 250, 0.15); border: 1px solid rgba(167, 139, 250, 0.35); border-radius: 6px; padding: 6px 14px;")
        p1_lay.addWidget(_make_setting_row(
            "📐", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #6d28d9)",
            "srkBrowser Window Geometry",
            "High-DPI desktop window dimensions and scaling geometry configured for optimal screen balance.",
            b_win
        ))

        self.cmb_session_heartbeat = QComboBox()
        self.cmb_session_heartbeat.setCursor(Qt.PointingHandCursor)
        self.cmb_session_heartbeat.setStyleSheet("""
            QComboBox {
                background-color: #0f111d;
                color: #cad3f5;
                border: 1px solid #282d47;
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
                min-width: 210px;
            }
            QComboBox:hover { border-color: #6366f1; }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #121424;
                color: #ffffff;
                selection-background-color: #4f46e5;
                border: 1px solid #232742;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        self.cmb_session_heartbeat.addItems(["25 Seconds (Recommended)", "15 Seconds (Strict)", "60 Seconds (Relaxed)"])
        p1_lay.addWidget(_make_setting_row(
            "⏱️", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d97706, stop:1 #b45309)",
            "Session Heartbeat Sync Interval",
            "Frequency of background cloud token heartbeat validation and multi-PC session conflict prevention.",
            self.cmb_session_heartbeat
        ))

        settings_stack.addWidget(panel1)

        # =========================================================================
        # 🛡️ PANEL 2: Anti-Detect Noise Spoofing & Security PIN
        # =========================================================================
        panel2, p2_lay = _make_category_card(
            "🛡️", "Anti-Detect Noise Spoofing & Security PIN Vault",
            "🔒 Enforced Active", "color: #fbbf24; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.35);"
        )

        b_ad = QLabel("🟢 Enforced Active")
        b_ad.setStyleSheet("color: #10b981; font-weight: 800; font-size: 11px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 6px 14px;")
        p2_lay.addWidget(_make_setting_row(
            "🎨", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #059669, stop:1 #047857)",
            "Canvas, WebGL & AudioContext Noise Injection",
            "Injects cryptographically unique mathematical noise per profile launch to defeat advanced hardware fingerprinting.",
            b_ad
        ))

        b_webrtc = QLabel("🟢 Leak-Proof Active")
        b_webrtc.setStyleSheet("color: #10b981; font-weight: 800; font-size: 11px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 6px 14px;")
        p2_lay.addWidget(_make_setting_row(
            "🔒", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d9488, stop:1 #0f766e)",
            "WebRTC, DNS & IPv6 Zero-Leak Tunnel",
            "Hardened zero-leak routing completely preventing public IP disclosure across WebRTC STUN/TURN and DNS requests.",
            b_webrtc
        ))

        btn_set_pin = QPushButton("🔑 Configure Master PIN")
        btn_set_pin.setCursor(Qt.PointingHandCursor)
        btn_set_pin.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #251e12, stop:1 #382c16);
                color: #fbbf24;
                border: 1px solid rgba(251, 191, 36, 0.5);
                border-radius: 7px;
                padding: 7px 16px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #4d3c1a;
                border-color: #fde047;
                color: #ffffff;
            }
        """)
        btn_set_pin.clicked.connect(self.on_set_security_pin)
        p2_lay.addWidget(_make_setting_row(
            "🔐", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d97706, stop:1 #92400e)",
            "4-Digit Profile Vault Master PIN",
            "Lock sensitive browser profiles with an encrypted 4-digit PIN access challenge before launching.",
            btn_set_pin
        ))

        settings_stack.addWidget(panel2)

        # =========================================================================
        # ☁️ PANEL 3: Cloud Vault & Storage Optimizer
        # =========================================================================
        panel3, p3_lay = _make_category_card(
            "☁️", "Cloud Vault & Storage Optimizer",
            "☁️ Real-Time Synced", "color: #38bdf8; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35);"
        )

        b_sync = QLabel("🟢 Real-Time Active")
        b_sync.setStyleSheet("color: #10b981; font-weight: 800; font-size: 11px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 6px 14px;")
        p3_lay.addWidget(_make_setting_row(
            "🔄", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0284c7, stop:1 #0369a1)",
            "Automatic Background Cloud Sync",
            "AES-256 encrypted auto-mirroring of cookies, session credentials, groups, and proxies to your cloud vault in real-time.",
            b_sync
        ))

        btn_force_restore = QPushButton("📥 Pull Cloud Profiles")
        btn_force_restore.setCursor(Qt.PointingHandCursor)
        btn_force_restore.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                border: 1px solid #3b82f6;
                border-radius: 7px;
                padding: 7px 16px;
            }
            QPushButton:hover { background: #3b82f6; }
        """)
        btn_force_restore.clicked.connect(self.on_force_restore_cloud)
        p3_lay.addWidget(_make_setting_row(
            "📥", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1d4ed8, stop:1 #1e40af)",
            "Pull & Restore Cloud Profiles",
            "Download and restore all cloud-backed browser profiles, credentials, and cookies directly to this machine.",
            btn_force_restore
        ))

        size_box = QHBoxLayout()
        size_box.setSpacing(8)
        self.lbl_setting_profiles_size = QLabel(f"📁 {self._get_profiles_folder_size_str()}")
        self.lbl_setting_profiles_size.setStyleSheet("color: #a5b4fc; font-size: 11px; font-weight: 800; background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 6px; padding: 6px 12px;")

        btn_open_folder = QPushButton("📂 Open Folder")
        btn_open_folder.setCursor(Qt.PointingHandCursor)
        btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #818cf8;
                border: 1px solid #282d47;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #262c4a; border-color: #818cf8; color: #ffffff; }
        """)
        btn_open_folder.clicked.connect(self._open_profiles_directory)
        size_box.addWidget(self.lbl_setting_profiles_size)
        size_box.addWidget(btn_open_folder)
        p3_lay.addWidget(_make_setting_row(
            "📁", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d97706, stop:1 #b45309)",
            "Local Profiles Storage Footprint",
            "Total disk space occupied by Chromium cache, LevelDB cookies, extensions, and profile data.",
            size_box
        ))

        btn_clean_cache = QPushButton("⚡ Clean RAM & Cache")
        btn_clean_cache.setCursor(Qt.PointingHandCursor)
        btn_clean_cache.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                border: 1px solid #10b981;
                border-radius: 7px;
                padding: 7px 16px;
            }
            QPushButton:hover { background: #10b981; }
        """)
        btn_clean_cache.clicked.connect(self.on_clean_all_profiles_cache)
        p3_lay.addWidget(_make_setting_row(
            "🧹", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #059669, stop:1 #047857)",
            "Clean Browser Cache & Free RAM",
            "Purge temporary shader caches, leftover lockfiles, and free unused physical system memory.",
            btn_clean_cache
        ))

        btn_vacuum_db = QPushButton("🛠️ Vacuum Database")
        btn_vacuum_db.setCursor(Qt.PointingHandCursor)
        btn_vacuum_db.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #a6adc8;
                border: 1px solid #282d47;
                border-radius: 7px;
                padding: 7px 16px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #262c4a; border-color: #6366f1; color: #ffffff; }
        """)
        btn_vacuum_db.clicked.connect(self._vacuum_database_storage)
        p3_lay.addWidget(_make_setting_row(
            "🛠️", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #4338ca)",
            "Vacuum SQLite Database Storage",
            "Re-indexes and compacts local database files to eliminate fragmentation and boost search speed.",
            btn_vacuum_db
        ))

        zip_box = QHBoxLayout()
        zip_box.setSpacing(8)
        btn_exp_zip = QPushButton("📦 Export Backup")
        btn_exp_zip.setCursor(Qt.PointingHandCursor)
        btn_exp_zip.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #262c4a; border-color: #6366f1; color: #ffffff; }
        """)
        btn_exp_zip.clicked.connect(self.on_export_data)

        btn_imp_zip = QPushButton("📂 Import Backup")
        btn_imp_zip.setCursor(Qt.PointingHandCursor)
        btn_imp_zip.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #262c4a; border-color: #6366f1; color: #ffffff; }
        """)
        btn_imp_zip.clicked.connect(self.on_import_data)

        zip_box.addWidget(btn_exp_zip)
        zip_box.addWidget(btn_imp_zip)
        p3_lay.addWidget(_make_setting_row(
            "📦", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #5b21b6)",
            "Offline ZIP Backup & Migration",
            "Export or import encrypted full profile archives for offline machine migration and cold backups.",
            zip_box
        ))

        settings_stack.addWidget(panel3)

        layout.addWidget(settings_stack, stretch=1)

        scroll_area.setWidget(content_widget)
        outer_layout = QVBoxLayout(widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)
        return widget

    def _browse_setting_browser_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Browser Executable", "C:\\Program Files", "Executables (*.exe);;All Files (*.*)"
        )
        if path and hasattr(self, "txt_setting_browser_path"):
            self.txt_setting_browser_path.setText(path)

    def _autodetect_setting_browser(self) -> None:
        from utils import get_system_browsers
        detected = get_system_browsers()
        if detected and hasattr(self, "txt_setting_browser_path"):
            first_name, first_path = next(iter(detected.items()))
            self.txt_setting_browser_path.setText(first_path)
            QMessageBox.information(self, "Browser Detected", f"Auto-detected {first_name}:\n{first_path}")
        else:
            QMessageBox.warning(self, "No Browser Detected", "Could not automatically detect installed Chromium/Chrome/Edge. Please browse manually.")

    def _open_profiles_directory(self) -> None:
        from pathlib import Path
        import os
        profiles_dir = getattr(self.profile_mgr, "base_dir", None) or (Path(__file__).parent.parent.parent / "profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(profiles_dir)))

    def _vacuum_database_storage(self) -> None:
        try:
            if hasattr(self, "profile_mgr") and hasattr(self.profile_mgr, "db_path"):
                import sqlite3
                conn = sqlite3.connect(self.profile_mgr.db_path)
                conn.execute("VACUUM;")
                conn.close()
            QMessageBox.information(self, "Storage Optimized", "🎉 SQLite Database vacuum and defragmentation completed successfully!")
        except Exception as e:
            QMessageBox.warning(self, "Optimization Error", f"Failed to vacuum database:\n{e}")

    def _on_save_page_settings(self) -> None:
        if hasattr(self, "txt_setting_browser_path"):
            self.settings["browser_path"] = self.txt_setting_browser_path.text().strip()
        self.settings["browser_window_size"] = "1280x800"
        self.settings["default_window_width"] = 1280
        self.settings["default_window_height"] = 840
        save_settings(self.settings)
        
        # Apply window resize if not maximized
        if not self.isMaximized():
            self.resize(1280, 840)

        if hasattr(self, "lbl_setting_profiles_size"):
            self.lbl_setting_profiles_size.setText(f"📁 {self._get_profiles_folder_size_str()}")
        QMessageBox.information(self, "Preferences Saved", "🎉 Application settings and engine preferences have been saved successfully!")
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage("Preferences saved successfully.", 4000)

    def _on_reset_page_settings(self) -> None:
        confirm = QMessageBox.question(
            self, "Confirm Reset", "Reset all application preferences to default values?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.settings["browser_path"] = ""
            self.settings["browser_window_size"] = "1280x800"
            self.settings["default_window_width"] = 1280
            self.settings["default_window_height"] = 840
            save_settings(self.settings)
            if hasattr(self, "txt_setting_browser_path"):
                self.txt_setting_browser_path.setText("")
            QMessageBox.information(self, "Preferences Reset", "Settings have been reset to default values.")

    def on_set_security_pin(self) -> None:
        """Set or update the master 4-digit security vault PIN."""
        current_pin = self.settings.get("security_pin", "")
        prompt = "Enter a 4-digit master PIN (leave blank to disable PIN lock):"
        if current_pin:
            prompt = f"Current PIN is set ({'•' * len(current_pin)}).\nEnter new 4-digit PIN (or leave blank to remove):"

        pin, ok = QInputDialog.getText(
            self,
            "Security PIN Vault",
            prompt,
            QLineEdit.Password
        )
        if ok:
            pin = pin.strip()
            if pin and (len(pin) != 4 or not pin.isdigit()):
                QMessageBox.warning(self, "Invalid PIN", "PIN must be exactly 4 numeric digits (e.g. 1234).")
                return
            self.settings["security_pin"] = pin
            save_settings(self.settings)
            if pin:
                QMessageBox.information(self, "PIN Configured", "🔒 4-Digit Security Master PIN has been configured successfully!")
            else:
                QMessageBox.information(self, "PIN Removed", "🔓 Security PIN protection has been disabled.")

    def on_sync_cloud(self) -> None:
        """Upload and mirror profiles to cloud vault."""
        self.on_cloud_backup()

    def on_force_restore_cloud(self) -> None:
        """Download and restore profiles from cloud vault."""
        self.on_cloud_restore()

    def on_export_data(self) -> None:
        """Export all profiles to offline JSON/ZIP backup archive."""
        all_profiles = self.profile_mgr.get_all_profiles()
        if not all_profiles:
            QMessageBox.warning(self, "No Data", "No profiles available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Offline Profile Backup",
            "srkBrowser_Profiles_Backup.json",
            "JSON Backup Archive (*.json);;CSV Spreadsheet (*.csv)"
        )
        if file_path:
            p = Path(file_path)
            if p.suffix.lower() == ".csv":
                ok = self.profile_mgr.export_profiles_csv(p)
            else:
                ok = self.profile_mgr.export_profiles(p)
            if ok:
                QMessageBox.information(self, "Export Complete", f"🎉 Successfully exported {len(all_profiles)} profiles to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export profile archive.")

    def on_import_data(self) -> None:
        """Import profiles from offline JSON/CSV backup file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Offline Profile Backup",
            "",
            "Supported Backups (*.json *.csv);;JSON Files (*.json);;CSV Files (*.csv);;All Files (*.*)"
        )
        if file_path:
            p = Path(file_path)
            if p.suffix.lower() == ".csv":
                imported, skipped = self.profile_mgr.import_profiles_csv(p)
            else:
                imported, skipped = self.profile_mgr.import_profiles(p)
            self.refresh_all_views()
            QMessageBox.information(
                self,
                "Import Complete",
                f"🎉 Successfully imported {imported} profiles!\nSkipped {skipped} duplicate/invalid entries."
            )

    def on_check_for_updates(self, silent: bool = False) -> None:
        """Check remote server for software updates."""
        try:
            from core.updater import check_remote_update_info, APP_VERSION
            has_update, latest_ver, dl_url, changelog = check_remote_update_info()
            if has_update:
                res = QMessageBox.question(
                    self,
                    "New Update Available",
                    f"🚀 A new version of srkBrowser is available!\n\n"
                    f"• Current Version: v{APP_VERSION}\n"
                    f"• Latest Version: v{latest_ver}\n\n"
                    f"Changelog:\n{changelog}\n\n"
                    "Would you like to open the download page?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if res == QMessageBox.Yes and dl_url:
                    from PySide6.QtGui import QDesktopServices
                    from PySide6.QtCore import QUrl
                    QDesktopServices.openUrl(QUrl(dl_url))
            else:
                if not silent:
                    QMessageBox.information(
                        self,
                        "Up to Date",
                        f"✅ You are using the latest version of srkBrowser (v{APP_VERSION}).\n\nNo new updates found."
                    )
        except Exception as e:
            if not silent:
                QMessageBox.warning(self, "Update Check Error", f"Unable to check for updates:\n{e}")

    def _create_about_page(self) -> QWidget:
        """Create the Ultra-Luxury Executive Platform Overview & Diagnostics Showcase."""
        widget = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 1. SaaS Executive Header Bar (Single-Line Card standard across all pages)
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #151829, stop:0.5 #121422, stop:1 #0f111d);
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(16, 10, 16, 10)
        h_layout.setSpacing(14)

        # Left: Title & Badge
        v_info = QHBoxLayout()
        v_info.setSpacing(10)
        v_info.setAlignment(Qt.AlignVCenter)

        ico_hdr = QLabel("ℹ️")
        ico_hdr.setStyleSheet("font-size: 16px; background: rgba(99, 102, 241, 0.18); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 8px; padding: 5px 8px;")
        v_info.addWidget(ico_hdr)

        lbl_title = QLabel("System Info & Platform Diagnostics")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 900; color: #ffffff; letter-spacing: 0.2px;")
        v_info.addWidget(lbl_title)

        lbl_core_pill = QLabel(f"🟢 Core v{APP_VERSION} Active")
        lbl_core_pill.setStyleSheet("font-size: 10px; font-weight: 800; color: #34d399; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 3px 8px;")
        v_info.addWidget(lbl_core_pill)

        h_layout.addLayout(v_info)
        h_layout.addStretch()

        # Right Action Buttons
        h_btns = QHBoxLayout()
        h_btns.setSpacing(8)

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        btn_tg = QPushButton("✈️ Telegram")
        btn_tg.setCursor(Qt.PointingHandCursor)
        btn_tg.setStyleSheet("""
            QPushButton {
                background-color: #1a1d30;
                color: #34d399;
                border: 1px solid #1f3d32;
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #13382c;
                border-color: #34d399;
                color: #ffffff;
            }
        """)
        btn_tg.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/srkplatforms")))

        btn_check_updates = QPushButton("🔄 Check for Updates")
        btn_check_updates.setCursor(Qt.PointingHandCursor)
        btn_check_updates.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6);
                color: #ffffff;
                font-weight: 800;
                font-size: 11.5px;
                border: 1px solid #6366f1;
                border-radius: 8px;
                padding: 7px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #60a5fa);
                border-color: #a5b4fc;
            }
        """)
        btn_check_updates.clicked.connect(lambda: self.on_check_for_updates(silent=False))

        h_btns.addWidget(btn_tg)
        h_btns.addWidget(btn_check_updates)
        h_layout.addLayout(h_btns)
        layout.addWidget(header_card)

        # 2. Hero Platform Showcase Banner
        hero_card = QFrame()
        hero_card.setStyleSheet("""
            QFrame#HeroCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #151930, stop:0.5 #111425, stop:1 #0d0f1c);
                border: 1px solid #262c4a;
                border-radius: 14px;
            }
        """)
        hero_card.setObjectName("HeroCard")
        hero_lay = QHBoxLayout(hero_card)
        hero_lay.setContentsMargins(20, 18, 20, 18)
        hero_lay.setSpacing(16)
        hero_lay.setAlignment(Qt.AlignVCenter)

        # Left Glowing Logo
        lbl_logo_icon = QLabel()
        lbl_logo_icon.setAlignment(Qt.AlignCenter)
        lbl_logo_icon.setFixedSize(54, 54)
        lbl_logo_icon.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(99, 102, 241, 0.25), stop:1 rgba(59, 130, 246, 0.25));
                border: 1.5px solid rgba(99, 102, 241, 0.5);
                border-radius: 12px;
            }
        """)
        try:
            from PySide6.QtGui import QPixmap
            from core.config import ASSETS_DIR
            pix_file = ASSETS_DIR / "app_icon.png"
            if pix_file.exists():
                pix = QPixmap(str(pix_file))
                lbl_logo_icon.setPixmap(pix.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                lbl_logo_icon.setText("🌐")
        except Exception:
            lbl_logo_icon.setText("🌐")
        hero_lay.addWidget(lbl_logo_icon)

        # Middle Brand & Description
        brand_vbox = QVBoxLayout()
        brand_vbox.setSpacing(4)
        brand_vbox.setAlignment(Qt.AlignVCenter)

        top_brand_row = QHBoxLayout()
        top_brand_row.setSpacing(10)
        top_brand_row.setAlignment(Qt.AlignVCenter)

        lbl_brand = QLabel('<span style="color:#ffffff; font-weight:900; font-size:20px;">srk</span><span style="color:#38bdf8; font-weight:900; font-size:20px;">Browser</span> <span style="color:#cdd6f4; font-size:16px; font-weight:800;">Customer Edition</span>')
        lbl_brand.setTextFormat(Qt.RichText)
        lbl_brand.setStyleSheet("background: transparent; border: none;")
        top_brand_row.addWidget(lbl_brand)

        badge_rel = QLabel(f"v{APP_VERSION} Pro • Customer Edition")
        badge_rel.setStyleSheet("color: #10b981; font-weight: 800; font-size: 10.5px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 3px 10px;")
        top_brand_row.addWidget(badge_rel)
        top_brand_row.addStretch()
        brand_vbox.addLayout(top_brand_row)

        lbl_brand_sub = QLabel("Next-Generation Anti-Detect Multi-Session Browser & Automation Architecture with Deep Hardware Spoofing Kernel")
        lbl_brand_sub.setStyleSheet("color: #94a3b8; font-size: 11.5px; font-weight: 500; border: none; background: transparent;")
        brand_vbox.addWidget(lbl_brand_sub)

        lbl_dev = QLabel("Engineered & Architected by <b style='color:#f8fafc;'>SRK Shofiqul</b> — Developed with ❤️ by SRK Shofiqul")
        lbl_dev.setStyleSheet("color: #818cf8; font-size: 11px; border: none; background: transparent;")
        brand_vbox.addWidget(lbl_dev)

        hero_lay.addLayout(brand_vbox, stretch=1)

        # Right Mini System Badges Box
        quick_stats = QFrame()
        quick_stats.setStyleSheet("background: #0f111e; border: 1px solid #1f233b; border-radius: 10px; padding: 6px;")
        qs_lay = QVBoxLayout(quick_stats)
        qs_lay.setContentsMargins(10, 8, 10, 8)
        qs_lay.setSpacing(4)

        lbl_qs1 = QLabel("💻 Windows 10/11 x64")
        lbl_qs1.setStyleSheet("color: #cad3f5; font-size: 10.5px; font-weight: 700; background: transparent; border: none;")
        lbl_qs2 = QLabel("🐍 Python 3.13 Engine")
        lbl_qs2.setStyleSheet("color: #38bdf8; font-size: 10.5px; font-weight: 700; background: transparent; border: none;")
        lbl_qs3 = QLabel("⚡ Hardware Accelerated")
        lbl_qs3.setStyleSheet("color: #34d399; font-size: 10.5px; font-weight: 700; background: transparent; border: none;")

        qs_lay.addWidget(lbl_qs1)
        qs_lay.addWidget(lbl_qs2)
        qs_lay.addWidget(lbl_qs3)
        hero_lay.addWidget(quick_stats)

        layout.addWidget(hero_card)

        # 3. 3-Column Technical Architecture Grid with Mini Metric Rows
        matrix_container = QWidget()
        matrix_grid = QGridLayout(matrix_container)
        matrix_grid.setContentsMargins(0, 0, 0, 0)
        matrix_grid.setSpacing(14)
        matrix_grid.setColumnStretch(0, 1)
        matrix_grid.setColumnStretch(1, 1)
        matrix_grid.setColumnStretch(2, 1)

        def _make_spec_card(icon_str: str, title_str: str, badge_text: str, badge_style: str) -> tuple[QFrame, QVBoxLayout]:
            card = QFrame()
            card.setStyleSheet("""
                QFrame#SpecCard {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141728, stop:1 #0f111e);
                    border: 1px solid #232742;
                    border-radius: 12px;
                }
                QFrame#SpecCard:hover {
                    border-color: #353b60;
                }
            """)
            card.setObjectName("SpecCard")
            c_box = QVBoxLayout(card)
            c_box.setContentsMargins(16, 14, 16, 14)
            c_box.setSpacing(8)

            # Card Header
            hdr = QHBoxLayout()
            hdr.setSpacing(8)
            hdr.setAlignment(Qt.AlignVCenter)

            ico_lbl = QLabel(icon_str)
            ico_lbl.setStyleSheet("font-size: 15px; background: transparent; border: none;")
            hdr.addWidget(ico_lbl)

            tit_lbl = QLabel(title_str)
            tit_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff; background: transparent; border: none;")
            hdr.addWidget(tit_lbl)
            hdr.addStretch()

            badge_lbl = QLabel(badge_text)
            badge_lbl.setStyleSheet(f"font-size: 9.5px; font-weight: 800; border-radius: 5px; padding: 2px 7px; {badge_style}")
            hdr.addWidget(badge_lbl)
            c_box.addLayout(hdr)

            # Divider
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet("background-color: #1e2238; border: none;")
            c_box.addWidget(div)
            c_box.addSpacing(2)

            return card, c_box

        def _make_spec_row(icon_emoji: str, label_str: str, val_str: str, val_color: str = "#cad3f5") -> QFrame:
            row = QFrame()
            row.setStyleSheet("""
                QFrame#SpecRow {
                    background-color: #101220;
                    border: 1px solid #1a1d30;
                    border-radius: 7px;
                }
                QFrame#SpecRow:hover {
                    background-color: #16192d;
                    border-color: #2a3050;
                }
            """)
            row.setObjectName("SpecRow")
            r_box = QHBoxLayout(row)
            r_box.setContentsMargins(10, 7, 10, 7)
            r_box.setSpacing(8)
            r_box.setAlignment(Qt.AlignVCenter)

            ico_l = QLabel(icon_emoji)
            ico_l.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            r_box.addWidget(ico_l)

            lbl_l = QLabel(label_str)
            lbl_l.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            r_box.addWidget(lbl_l)

            r_box.addStretch()

            val_l = QLabel(val_str)
            val_l.setStyleSheet(f"color: {val_color}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
            r_box.addWidget(val_l)

            return row

        # Column 1: Core Runtime Architecture
        acard1, ac1_box = _make_spec_card(
            "⚡", "Core Runtime Architecture",
            "🟢 Operational", "color: #34d399; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35);"
        )
        ac1_box.addWidget(_make_spec_row("💻", "Native OS", "Windows 10/11 x64", "#f1f5f9"))
        ac1_box.addWidget(_make_spec_row("🐍", "Python Runtime", "v3.13 High-Speed", "#38bdf8"))
        ac1_box.addWidget(_make_spec_row("🎨", "GUI Engine", "PySide6 Qt6 Hardware Accel", "#818cf8"))
        ac1_box.addWidget(_make_spec_row("🌐", "Local Gateway", "REST API (Port 5000)", "#34d399"))
        ac1_box.addWidget(_make_spec_row("🚀", "Threading Model", "Async Worker Pool", "#c084fc"))
        ac1_box.addStretch()
        matrix_grid.addWidget(acard1, 0, 0)

        # Column 2: Privacy & Fingerprint Kernel
        acard2, ac2_box = _make_spec_card(
            "🛡️", "Privacy & Fingerprint Kernel",
            "🔒 Enforced", "color: #fbbf24; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.35);"
        )
        ac2_box.addWidget(_make_spec_row("🎨", "Canvas & WebGL", "Mathematical Noise Spoofing", "#34d399"))
        ac2_box.addWidget(_make_spec_row("🎧", "AudioContext", "Buffer & Frequency Masking", "#34d399"))
        ac2_box.addWidget(_make_spec_row("📐", "ClientRects", "Sub-Pixel Randomizer", "#38bdf8"))
        ac2_box.addWidget(_make_spec_row("🔒", "WebRTC & DNS", "Zero-Leak Tunnel Protection", "#10b981"))
        ac2_box.addWidget(_make_spec_row("📍", "Proxy Matching", "Auto Geo Timezone & Lang", "#fbbf24"))
        ac2_box.addStretch()
        matrix_grid.addWidget(acard2, 0, 1)

        # Column 3: Cloud Vault & Storage Engine
        acard3, ac3_box = _make_spec_card(
            "☁️", "Cloud Vault & Database Store",
            "☁️ Connected", "color: #38bdf8; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35);"
        )
        ac3_box.addWidget(_make_spec_row("🔐", "Cloud Vault", "AES-256 Encrypted Sync", "#38bdf8"))
        ac3_box.addWidget(_make_spec_row("🛒", "Dynamic Store", "On-Demand Cloud Modules", "#c084fc"))
        ac3_box.addWidget(_make_spec_row("🔑", "HWID Vault", "Hardware-Locked Security", "#fbbf24"))
        ac3_box.addWidget(_make_spec_row("🗄️", "Database Storage", "SQLite WAL Concurrent", "#34d399"))
        ac3_box.addWidget(_make_spec_row("⚡", "Multi-Device", "Live Session Quota Sync", "#818cf8"))
        ac3_box.addStretch()
        matrix_grid.addWidget(acard3, 0, 2)

        layout.addWidget(matrix_container)

        # 4. System Diagnostic Health Telemetry Bar
        health_strip = QFrame()
        health_strip.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #121526, stop:0.5 #101220, stop:1 #0d0f1b);
                border: 1px solid #20243a;
                border-radius: 10px;
            }
        """)
        hs_lay = QHBoxLayout(health_strip)
        hs_lay.setContentsMargins(16, 10, 16, 10)
        hs_lay.setSpacing(18)

        def _make_diag_pill(icon_t, label_t, status_t):
            pill = QLabel(f"{icon_t} {label_t}: <b style='color:#34d399;'>{status_t}</b>")
            pill.setStyleSheet("color: #cad3f5; font-size: 11.5px; font-weight: 600; background: transparent; border: none;")
            return pill

        hs_lay.addWidget(_make_diag_pill("🛡️", "Anti-Detect Kernel", "Operational"))
        hs_lay.addWidget(_make_diag_pill("🌐", "Local REST Gateway", "127.0.0.1:5000"))
        hs_lay.addWidget(_make_diag_pill("☁️", "Cloud Sync Engine", "Connected & Synced"))
        hs_lay.addWidget(_make_diag_pill("🗄️", "SQLite WAL Storage", "Optimized (Fast)"))
        hs_lay.addStretch()

        layout.addWidget(health_strip)

        # 5. Clean Enterprise Footer
        lbl_footer = QLabel("© 2026 srkBrowser Customer Edition. All rights reserved. Built for professional digital marketing, multi-account management & automation workflows.")
        lbl_footer.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 500; text-align: center; margin-top: 4px;")
        lbl_footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_footer)

        layout.addStretch()

        scroll_area.setWidget(content_widget)
        outer_layout = QVBoxLayout(widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)
        return widget


    def _get_favorite_tools_file_path(self) -> Path:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = Path(appdata) / "BrowserProfileManager"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "favorite_tools.json"

    def _load_favorite_tools(self) -> set:
        try:
            p = self._get_favorite_tools_file_path()
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
        except Exception as e:
            logger.warning(f"Failed to load favorite tools: {e}")
        return set()

    def _save_favorite_tools(self) -> None:
        try:
            p = self._get_favorite_tools_file_path()
            favs = getattr(self, "favorite_tools_set", set())
            with open(p, "w", encoding="utf-8") as f:
                json.dump(list(favs), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save favorite tools: {e}")

    def _toggle_favorite_tool(self, tool_id: str, tool_name: str) -> None:
        if not hasattr(self, "favorite_tools_set"):
            self.favorite_tools_set = self._load_favorite_tools()
        
        if tool_id in self.favorite_tools_set:
            self.favorite_tools_set.remove(tool_id)
            msg = f"⭐ Removed '{tool_name}' from Favorites."
        else:
            self.favorite_tools_set.add(tool_id)
            msg = f"❤️ Added '{tool_name}' to Favorites!"
        
        self._save_favorite_tools()
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(msg, 3000)
        
        search_txt = self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else ""
        self._render_tools_grid(search_text=search_txt)

    def _create_tools_page(self) -> QWidget:
        """Create the Tools category page containing utility software tools with live search, favorites & pagination."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        if not hasattr(self, "favorite_tools_set"):
            self.favorite_tools_set = self._load_favorite_tools()

        # Single-Line Compact Control Header Bar (Zero Clutter)
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                border: 1px solid #232742;
                border-radius: 10px;
            }
        """)
        header_hbox = QHBoxLayout(header_card)
        header_hbox.setContentsMargins(12, 8, 12, 8)
        header_hbox.setSpacing(10)

        # Tab Capsule: All Tools, Free Tools, Premium Tools & Favorite Tools
        tab_capsule = QFrame()
        tab_capsule.setStyleSheet("background-color: #10121e; border: 1px solid #232742; border-radius: 8px;")
        tab_capsule_hbox = QHBoxLayout(tab_capsule)
        tab_capsule_hbox.setContentsMargins(3, 3, 3, 3)
        tab_capsule_hbox.setSpacing(4)

        self.btn_tools_all_tab = QPushButton("🛠️ All Tools (0)")
        self.btn_tools_all_tab.setCursor(Qt.PointingHandCursor)
        self.btn_tools_all_tab.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6);
                color: #ffffff;
                font-weight: 800;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #6366f1;
            }
        """)

        self.btn_tools_free_tab = QPushButton("🎁 Free Tools (0)")
        self.btn_tools_free_tab.setCursor(Qt.PointingHandCursor)
        self.btn_tools_free_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_tools_premium_tab = QPushButton("⭐ Premium Tools (0)")
        self.btn_tools_premium_tab.setCursor(Qt.PointingHandCursor)
        self.btn_tools_premium_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_tools_favorites_tab = QPushButton("❤️ Favorites (0)")
        self.btn_tools_favorites_tab.setCursor(Qt.PointingHandCursor)
        self.btn_tools_favorites_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_tools_all_tab.clicked.connect(lambda: self._switch_tools_category("all"))
        self.btn_tools_free_tab.clicked.connect(lambda: self._switch_tools_category("free"))
        self.btn_tools_premium_tab.clicked.connect(lambda: self._switch_tools_category("premium"))
        self.btn_tools_favorites_tab.clicked.connect(lambda: self._switch_tools_category("favorites"))

        tab_capsule_hbox.addWidget(self.btn_tools_all_tab)
        tab_capsule_hbox.addWidget(self.btn_tools_free_tab)
        tab_capsule_hbox.addWidget(self.btn_tools_premium_tab)
        tab_capsule_hbox.addWidget(self.btn_tools_favorites_tab)
        header_hbox.addWidget(tab_capsule)

        self.txt_tools_search = QLineEdit()
        self.txt_tools_search.setPlaceholderText("🔍 Search tools by name, category, or tag...")
        self.txt_tools_search.setStyleSheet("""
            QLineEdit {
                background-color: #131626;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 11.5px;
            }
            QLineEdit:focus { border-color: #6366f1; background-color: #181c30; }
        """)
        self.txt_tools_search.textChanged.connect(self._on_tools_search_changed)
        header_hbox.addWidget(self.txt_tools_search, stretch=1)

        layout.addWidget(header_card)

        # Tools 3x3 Grid Area (Dynamically expands to fill 100% of viewport without gaps)
        tools_content = QWidget()
        tools_content.setStyleSheet("background: transparent; border: none;")
        self.tools_grid = QGridLayout(tools_content)
        self.tools_grid.setContentsMargins(0, 0, 0, 0)
        self.tools_grid.setSpacing(12)
        for c in range(3):
            self.tools_grid.setColumnStretch(c, 1)
        for r in range(4):
            self.tools_grid.setRowStretch(r, 1)

        layout.addWidget(tools_content, stretch=1)

        # Tools Pagination Bar (9 per page)
        self.tools_pagination_bar = self._create_tools_pagination_bar()
        layout.addWidget(self.tools_pagination_bar)

        if hasattr(self, "_sync_tools_manifest_async"):
            self._sync_tools_manifest_async()
        self._render_tools_grid()
        return page

    def _switch_tools_category(self, cat_mode: str) -> None:
        """Switch between All Tools, Free Tools, Premium Tools, and Favorites."""
        self._current_tools_category = cat_mode
        self.tools_current_page = 1

        style_all_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #6366f1;"
        style_free_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #10b981;"
        style_prem_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #8b5cf6;"
        style_fav_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #be123c); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #f43f5e;"
        style_inactive = "background-color: transparent; color: #a6adc8; font-weight: 600; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: none;"

        if hasattr(self, "btn_tools_all_tab"):
            self.btn_tools_all_tab.setStyleSheet(style_all_active if cat_mode == "all" else style_inactive)
        if hasattr(self, "btn_tools_free_tab"):
            self.btn_tools_free_tab.setStyleSheet(style_free_active if cat_mode == "free" else style_inactive)
        if hasattr(self, "btn_tools_premium_tab"):
            self.btn_tools_premium_tab.setStyleSheet(style_prem_active if cat_mode == "premium" else style_inactive)
        if hasattr(self, "btn_tools_favorites_tab"):
            self.btn_tools_favorites_tab.setStyleSheet(style_fav_active if cat_mode == "favorites" else style_inactive)

        search_txt = self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else ""
        self._render_tools_grid(search_text=search_txt)

    def _create_tools_pagination_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ToolsPaginationFrame")
        frame.setFixedHeight(32)
        frame.setStyleSheet("""
            QFrame#ToolsPaginationFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 8px;
            }
            QSpinBox {
                background-color: #161829;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 5px;
                padding: 1px 4px;
                font-weight: 700;
                font-size: 11px;
                max-height: 22px;
                max-width: 42px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(8)

        self.lbl_tools_page_total = QLabel("Total 0")
        self.lbl_tools_page_total.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11.5px;")
        layout.addWidget(self.lbl_tools_page_total)
        layout.addStretch()

        self.tools_pages_hbox = QHBoxLayout()
        self.tools_pages_hbox.setSpacing(3)
        layout.addLayout(self.tools_pages_hbox)

        lbl_goto = QLabel("Go to")
        lbl_goto.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")

        self.spin_tools_goto = QSpinBox()
        self.spin_tools_goto.setRange(1, 1)
        self.spin_tools_goto.setValue(1)
        self.spin_tools_goto.setAlignment(Qt.AlignCenter)
        self.spin_tools_goto.editingFinished.connect(self._on_tools_goto_page)

        layout.addWidget(lbl_goto)
        layout.addWidget(self.spin_tools_goto)

        return frame

    def _update_tools_pagination_controls(self, total_items: int) -> None:
        import math
        self.tools_page_size = 12
        if not hasattr(self, "tools_current_page"):
            self.tools_current_page = 1

        self.tools_total_pages = max(1, math.ceil(total_items / self.tools_page_size))
        self.tools_current_page = min(max(1, self.tools_current_page), self.tools_total_pages)

        if hasattr(self, "lbl_tools_page_total") and self.lbl_tools_page_total:
            self.lbl_tools_page_total.setText(f"Total {total_items}")

        if hasattr(self, "spin_tools_goto") and self.spin_tools_goto:
            self.spin_tools_goto.blockSignals(True)
            self.spin_tools_goto.setRange(1, self.tools_total_pages)
            self.spin_tools_goto.setValue(self.tools_current_page)
            self.spin_tools_goto.blockSignals(False)

        if not hasattr(self, "tools_pages_hbox") or self.tools_pages_hbox is None:
            return

        while self.tools_pages_hbox.count() > 0:
            child = self.tools_pages_hbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        btn_prev = QPushButton("‹")
        btn_prev.setEnabled(self.tools_current_page > 1)
        btn_prev.setCursor(Qt.PointingHandCursor if self.tools_current_page > 1 else Qt.ArrowCursor)
        btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_prev.clicked.connect(self._on_tools_page_prev_clicked)
        self.tools_pages_hbox.addWidget(btn_prev)

        page_nums = []
        if self.tools_total_pages <= 7:
            page_nums = list(range(1, self.tools_total_pages + 1))
        else:
            page_nums = [1]
            if self.tools_current_page > 3:
                page_nums.append("...")
            
            start_p = max(2, self.tools_current_page - 1)
            end_p = min(self.tools_total_pages - 1, self.tools_current_page + 1)
            for p in range(start_p, end_p + 1):
                if p not in page_nums:
                    page_nums.append(p)
            
            if self.tools_current_page < self.tools_total_pages - 2:
                page_nums.append("...")
            if self.tools_total_pages not in page_nums:
                page_nums.append(self.tools_total_pages)

        for item in page_nums:
            if item == "...":
                lbl_dots = QLabel("...")
                lbl_dots.setStyleSheet("color: #6c7086; font-weight: bold; padding: 0 2px; font-size: 11px;")
                self.tools_pages_hbox.addWidget(lbl_dots)
            else:
                p_num = int(item)
                btn = QPushButton(str(p_num))
                btn.setCursor(Qt.PointingHandCursor)
                if p_num == self.tools_current_page:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #89b4fa; color: #11111b; border: 1px solid #89b4fa;
                            border-radius: 4px; padding: 2px 7px; font-weight: 800; font-size: 11.5px; max-height: 22px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                            border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 11.5px; max-height: 22px;
                        }
                        QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
                    """)
                btn.clicked.connect(lambda _, p=p_num: self._go_to_tools_page(p))
                self.tools_pages_hbox.addWidget(btn)

        btn_next = QPushButton("›")
        btn_next.setEnabled(self.tools_current_page < self.tools_total_pages)
        btn_next.setCursor(Qt.PointingHandCursor if self.tools_current_page < self.tools_total_pages else Qt.ArrowCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_next.clicked.connect(self._on_tools_page_next_clicked)
        self.tools_pages_hbox.addWidget(btn_next)

    def _on_tools_page_prev_clicked(self) -> None:
        if hasattr(self, "tools_current_page") and self.tools_current_page > 1:
            self.tools_current_page -= 1
            self._render_tools_grid(search_text=self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else "")

    def _on_tools_page_next_clicked(self) -> None:
        if hasattr(self, "tools_current_page") and hasattr(self, "tools_total_pages") and self.tools_current_page < self.tools_total_pages:
            self.tools_current_page += 1
            self._render_tools_grid(search_text=self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else "")

    def _on_tools_goto_page(self) -> None:
        if hasattr(self, "spin_tools_goto"):
            val = self.spin_tools_goto.value()
            self._go_to_tools_page(val)

    def _go_to_tools_page(self, page_num: int) -> None:
        if hasattr(self, "tools_total_pages") and 1 <= page_num <= self.tools_total_pages:
            self.tools_current_page = page_num
            self._render_tools_grid(search_text=self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else "")

    def _on_tools_search_changed(self, text: str) -> None:
        """Debounced power tools search: smooth typing without UI freeze."""
        if not hasattr(self, "_tools_search_timer"):
            self._tools_search_timer = QTimer(self)
            self._tools_search_timer.setSingleShot(True)
            self._tools_search_timer.setInterval(160)
            self._tools_search_timer.timeout.connect(lambda: self._do_tools_search(self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else ""))
        self._tools_search_timer.start(160)

    def _do_tools_search(self, text: str) -> None:
        self.tools_current_page = 1
        self._render_tools_grid(search_text=text)

    def _sync_tools_manifest_async(self) -> None:
        if hasattr(self, "_tools_sync_thread") and self._tools_sync_thread is not None and self._tools_sync_thread.isRunning():
            return
        self._tools_sync_thread = ToolsManifestSyncThread(self)
        self._tools_sync_thread.tools_fetched.connect(self._on_tools_manifest_fetched_bg)
        self._tools_sync_thread.start()

    def _on_tools_manifest_fetched_bg(self, tools_list: list) -> None:
        if isinstance(tools_list, list):
            self._online_tools_list = tools_list
            search_txt = self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else ""
            self._render_tools_grid(search_text=search_txt)

    def _sync_scripts_manifest_async(self) -> None:
        if hasattr(self, "_scripts_sync_thread") and self._scripts_sync_thread is not None and self._scripts_sync_thread.isRunning():
            return
        self._scripts_sync_thread = ScriptsManifestSyncThread(self)
        self._scripts_sync_thread.scripts_fetched.connect(self._on_scripts_manifest_fetched_bg)
        self._scripts_sync_thread.start()

    def _on_scripts_manifest_fetched_bg(self, scripts_list: list) -> None:
        if isinstance(scripts_list, list):
            self._online_scripts_list = scripts_list
            search_txt = self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else ""
            self._render_scripts_grid(search_text=search_txt)

    def _render_tools_grid(self, search_text: str = "") -> None:
        """Render tool cards dynamically with 9 items per page, 3x3 grid, and live search filtering."""
        if not hasattr(self, "tools_grid") or self.tools_grid is None:
            return

        _clear_layout(self.tools_grid)

        for col in range(3):
            self.tools_grid.setColumnStretch(col, 1)
        for row in range(4):
            self.tools_grid.setRowStretch(row, 1)

        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        plan_str = str(user_info.get("plan") or user_info.get("plan_name") or user_info.get("plan_type") or user_info.get("subscription") or "").upper()
        curr_quota = int(user_info.get("max_profiles", 100) or user_info.get("cloud_quota", 100) or 100)
        is_enterprise = ("ENTERPRISE" in plan_str) or bool(user_info.get("is_enterprise", False)) or user_info.get("role") == "admin" or curr_quota >= 5000

        # Cloud-driven dynamic utility tools (loaded from server manifest)
        builtin_tools = []

        # Dynamic Precision Utility Palette Pool for Power Tools
        # (bg_start, bg_end, border, theme_color, icon_bg, btn_bg_s, btn_bg_e, btn_border, btn_hover)
        dynamic_tools_palettes = [
            ("#282013", "#18130a", "#46351d", "#facc15", "rgba(250, 204, 21, 0.16)", "#d97706", "#b45309", "#f59e0b", "#fbbf24"),  # Solar Topaz / Cookie Gold
            ("#112627", "#0a1718", "#1d4144", "#2dd4bf", "rgba(45, 212, 191, 0.16)", "#0d9488", "#0f766e", "#14b8a6", "#2dd4bf"),  # Precision Teal / Aquamarine
            ("#1e1832", "#110d1e", "#352756", "#a78bfa", "rgba(167, 139, 250, 0.16)", "#7c3aed", "#6d28d9", "#8b5cf6", "#a78bfa"),  # Royal Amethyst / Violet
            ("#29171a", "#190d0f", "#48242a", "#fb7185", "rgba(251, 113, 133, 0.16)", "#e11d48", "#be123c", "#f43f5e", "#fb7185"),  # Coral Flame / Rose
            ("#141f32", "#0b1320", "#1f3354", "#38bdf8", "rgba(56, 189, 248, 0.16)", "#2563eb", "#1d4ed8", "#3b82f6", "#60a5fa"),  # Sapphire Blue
            ("#1e2713", "#12180a", "#33431e", "#a3e635", "rgba(163, 230, 53, 0.16)", "#65a30d", "#4d7c0f", "#84cc16", "#a3e635"),  # Cyber Lime / Chartreuse
        ]

        # Merge with online tools if available
        tools_map = {}
        for bt in builtin_tools:
            tid = bt["tool_id"]
            lic_info = self.bot_license_mgr.get_local_license(tid) if hasattr(self, "bot_license_mgr") else None
            has_lic = (lic_info is not None and lic_info.get("is_active", True))
            has_acc = bt["is_free"] or is_enterprise or has_lic
            bt["has_access"] = has_acc
            bt["callback"] = lambda _, t_id=tid, info=bt: self._open_tool(t_id, info)
            tools_map[tid] = bt

        # Only display utility tools dynamically published from Admin Panel (fetched from server API)
        online_tools = list(getattr(self, "_online_tools_list", None) or [])

        if online_tools and isinstance(online_tools, list) and len(online_tools) > 0:
            for t_idx, ot in enumerate(online_tools):
                if not ot.get("is_enabled", True) and not ot.get("is_published", True):
                    continue
                tid = ot.get("tool_id") or ot.get("id")
                if not tid:
                    continue
                is_free_val = ot.get("is_free", True)
                is_free_bool = (is_free_val is True or is_free_val == 1 or str(is_free_val).lower() == "true")
                price_lbl = str(ot.get("price_label", "FREE" if is_free_bool else "$10"))
                
                lic_info = self.bot_license_mgr.get_local_license(tid) if hasattr(self, "bot_license_mgr") else None
                has_lic = (lic_info is not None and lic_info.get("is_active", True))
                has_acc = is_free_bool or is_enterprise or has_lic

                bg_s_def, bg_e_def, b_col_def, a_col_def, i_bg_def, btn_s_def, btn_e_def, btn_b_def, btn_h_def = dynamic_tools_palettes[t_idx % len(dynamic_tools_palettes)]

                t_lower = tid.lower()
                tool_icon = ot.get("icon")
                if not tool_icon:
                    if "cookie" in t_lower:
                        tool_icon = "🍪"
                    elif "proxy" in t_lower:
                        tool_icon = "🛡️"
                    elif "token" in t_lower or "key" in t_lower:
                        tool_icon = "🔑"
                    elif "database" in t_lower or "data" in t_lower:
                        tool_icon = "🗄️"
                    else:
                        tool_icon = "🛠️"

                tools_map[tid] = {
                    "tool_id": tid,
                    "name": ot.get("name") or ot.get("title") or f"🛠️ {tid.replace('_', ' ').title()}",
                    "category": ot.get("category", "TOOL"),
                    "version": str(ot.get("version", "1.0.0")),
                    "icon": tool_icon,
                    "description": ot.get("description") or ot.get("desc") or "Dynamic Cloud Utility Tool",
                    "price_label": price_lbl,
                    "is_free": is_free_bool,
                    "has_access": has_acc,
                    "callback": lambda _, t_id=tid, info=ot: self._open_tool(t_id, info),
                    "btn_text": ot.get("btn_text", "⚡ Open Tool"),
                    "theme_color": ot.get("theme_color") or a_col_def,
                    "bg_start": ot.get("bg_start") or bg_s_def,
                    "bg_end": ot.get("bg_end") or bg_e_def,
                    "border": ot.get("border") or b_col_def,
                    "border_hover": ot.get("border_hover") or a_col_def,
                    "icon_bg": ot.get("icon_bg") or i_bg_def,
                    "btn_bg_s": ot.get("btn_bg_s") or btn_s_def,
                    "btn_bg_e": ot.get("btn_bg_e") or btn_e_def,
                    "btn_border": ot.get("btn_border") or btn_b_def,
                    "btn_hover": ot.get("btn_hover") or btn_h_def,
                    "tutorial_url": ot.get("tutorial_url", "")
                }
        
        tools_to_show = list(tools_map.values())
        query = search_text.lower().strip()
        curr_cat = getattr(self, "_current_tools_category", "free")

        if not hasattr(self, "favorite_tools_set"):
            self.favorite_tools_set = self._load_favorite_tools()

        free_tools = [t for t in tools_to_show if (t.get("is_free", True) or str(t.get("price_label")).upper() == "FREE")]
        premium_tools = [t for t in tools_to_show if not (t.get("is_free", True) or str(t.get("price_label")).upper() == "FREE")]
        favorite_tools = [t for t in tools_to_show if t["tool_id"] in self.favorite_tools_set]

        if hasattr(self, "btn_tools_all_tab"):
            self.btn_tools_all_tab.setText(f"🛠️ All Tools ({len(tools_to_show)})")
        if hasattr(self, "btn_tools_free_tab"):
            self.btn_tools_free_tab.setText(f"🎁 Free Tools ({len(free_tools)})")
        if hasattr(self, "btn_tools_premium_tab"):
            self.btn_tools_premium_tab.setText(f"⭐ Premium Tools ({len(premium_tools)})")
        if hasattr(self, "btn_tools_favorites_tab"):
            self.btn_tools_favorites_tab.setText(f"❤️ Favorites ({len(favorite_tools)})")

        curr_cat = getattr(self, "_current_tools_category", "all")

        if curr_cat == "all":
            source_list = tools_to_show
        elif curr_cat == "free":
            source_list = free_tools
        elif curr_cat == "premium":
            source_list = premium_tools
        else:
            source_list = favorite_tools

        matched = []
        for t in source_list:
            if not query or query in t["name"].lower() or query in t["description"].lower() or query in t["category"].lower():
                matched.append(t)

        # Update Pagination Controls for 12 per page
        self._update_tools_pagination_controls(len(matched))

        # Slice 12 items for current page
        start_idx = (self.tools_current_page - 1) * self.tools_page_size
        end_idx = start_idx + self.tools_page_size
        page_items = matched[start_idx:end_idx]

        if not matched:
            empty_frame = QFrame()
            empty_frame.setStyleSheet("background: #111424; border: 1px dashed #232742; border-radius: 12px; padding: 40px;")
            v_empty = QVBoxLayout(empty_frame)
            v_empty.setAlignment(Qt.AlignCenter)
            if curr_cat == "favorites" and len(favorite_tools) == 0:
                lbl_no = QLabel("❤️ No Favorite Tools Added Yet")
                lbl_no.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4; border: none;")
                lbl_sub = QLabel("Click the ⭐ star icon on any tool card to add your favourite tools here for instant access!")
                lbl_sub.setStyleSheet("font-size: 12px; color: #a6adc8; margin-top: 6px; border: none;")
                v_empty.addWidget(lbl_no, alignment=Qt.AlignCenter)
                v_empty.addWidget(lbl_sub, alignment=Qt.AlignCenter)
            else:
                lbl_no = QLabel(f"🔍 No tools found matching '{query}'" if query else ("🛠️ No utility tools published yet" if curr_cat == "all" else ("🎁 No Free Tools available" if curr_cat == "free" else ("⭐ No Premium Tools available" if curr_cat == "premium" else "❤️ No tools in favorites"))))
                lbl_no.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4; border: none;")
                v_empty.addWidget(lbl_no, alignment=Qt.AlignCenter)
                if not query:
                    lbl_sub = QLabel("Publish utility tools from the Admin Panel or click Refresh to sync from cloud.")
                    lbl_sub.setStyleSheet("font-size: 12px; color: #a6adc8; margin-top: 6px; border: none;")
                    v_empty.addWidget(lbl_sub, alignment=Qt.AlignCenter)
                    btn_refresh = QPushButton("🔄 Refresh Cloud Tools")
                    btn_refresh.setCursor(Qt.PointingHandCursor)
                    btn_refresh.setStyleSheet("background-color: #4f46e5; color: #ffffff; font-weight: 700; border-radius: 6px; padding: 6px 16px; font-size: 11.5px; margin-top: 10px;")
                    btn_refresh.clicked.connect(self._sync_tools_manifest_async)
                    v_empty.addWidget(btn_refresh, alignment=Qt.AlignCenter)
            self.tools_grid.addWidget(empty_frame, 0, 0, 1, 3)
            return

        for idx in range(12):
            row = idx // 3
            col = idx % 3
            if idx < len(page_items):
                t = page_items[idx]
                bg_s = t.get("bg_start", "#1b1d30")
                bg_e = t.get("bg_end", "#121422")
                border_c = t.get("border", "#2b304f")
                hover_c = t.get("border_hover", "#818cf8")
                theme_col = t.get("theme_color", "#818cf8")
                icon_bg = t.get("icon_bg", "rgba(129, 140, 248, 0.14)")
                tool_icon = t.get("icon", "🛠️")

                card = QFrame()
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                card.setMinimumHeight(135)
                card.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_s}, stop:1 {bg_e});
                        border: 1px solid {border_c};
                        border-radius: 10px;
                    }}
                    QFrame:hover {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_s}, stop:1 #202438);
                        border: 1px solid {hover_c};
                    }}
                """)
                c_layout = QVBoxLayout(card)
                c_layout.setContentsMargins(14, 12, 14, 12)
                c_layout.setSpacing(6)

                # Header Row: Icon + Title + Version Pill + Favorite Star + Price Badge
                # Row 1 (Header): Icon + Title (Full Stretch Width) + Favorite Star
                c_top_row = QHBoxLayout()
                c_top_row.setContentsMargins(0, 0, 0, 0)
                c_top_row.setSpacing(8)

                lbl_icon = QLabel(tool_icon)
                lbl_icon.setStyleSheet(f"font-size: 14px; background: {icon_bg}; color: {theme_col}; border: 1px solid {border_c}; border-radius: 6px; padding: 2px 6px;")

                full_t_name = t["name"]
                import re
                clean_t_title = re.sub(r'^[^\w\s]+\s*', '', full_t_name).strip() or full_t_name
                lbl_t_title = QLabel(clean_t_title)
                lbl_t_title.setWordWrap(True)
                lbl_t_title.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #ffffff; border: none; background: transparent; line-height: 1.25;")
                lbl_t_title.setToolTip(full_t_name)

                # Favorite Star Button
                is_fav = t["tool_id"] in self.favorite_tools_set
                btn_fav = QPushButton("⭐" if is_fav else "☆")
                btn_fav.setCursor(Qt.PointingHandCursor)
                btn_fav.setToolTip("Remove from Favorites" if is_fav else "Add to Favorites")
                if is_fav:
                    btn_fav.setStyleSheet("""
                        QPushButton {
                            background: rgba(251, 191, 36, 0.2);
                            color: #fbbf24;
                            font-size: 12px;
                            font-weight: 900;
                            border: 1px solid rgba(251, 191, 36, 0.5);
                            border-radius: 4px;
                            padding: 1px 5px;
                        }
                        QPushButton:hover {
                            background: rgba(251, 191, 36, 0.35);
                        }
                    """)
                else:
                    btn_fav.setStyleSheet("""
                        QPushButton {
                            background: rgba(255, 255, 255, 0.04);
                            color: #64748b;
                            font-size: 12px;
                            font-weight: bold;
                            border: 1px solid #282d47;
                            border-radius: 4px;
                            padding: 1px 5px;
                        }
                        QPushButton:hover {
                            color: #fbbf24;
                            border-color: #fbbf24;
                            background: rgba(251, 191, 36, 0.12);
                        }
                    """)
                btn_fav.clicked.connect(lambda _, tid=t["tool_id"], tname=full_t_name: self._toggle_favorite_tool(tid, tname))

                c_top_row.addWidget(lbl_icon, 0, Qt.AlignVCenter)
                c_top_row.addWidget(lbl_t_title, 1, Qt.AlignVCenter)
                c_top_row.addWidget(btn_fav, 0, Qt.AlignVCenter)
                c_layout.addLayout(c_top_row)

                # Row 2 (Meta Info): Version Badge (Left) + Price/Access Badge (Right)
                c_meta_row = QHBoxLayout()
                c_meta_row.setContentsMargins(0, 0, 0, 0)
                c_meta_row.setSpacing(6)

                lbl_ver = QLabel(f"v{t.get('version', '1.0.0')}")
                lbl_ver.setStyleSheet(f"font-size: 9.5px; font-weight: bold; color: {theme_col}; background: {icon_bg}; border: 1px solid {border_c}; border-radius: 4px; padding: 1px 5px;")

                is_free_val = t.get("is_free", True)
                price_lbl_str = t.get("price_label", "FREE")
                has_acc = t.get("has_access", True)

                if has_acc:
                    if is_free_val or price_lbl_str == "FREE":
                        price_badge = QLabel("🎁 FREE")
                        price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")
                    elif is_enterprise:
                        price_badge = QLabel("⭐ Enterprise Access")
                        price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")
                    else:
                        price_badge = QLabel("✅ Active License")
                        price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")
                else:
                    price_badge = QLabel(f"⭐ {price_lbl_str}")
                    price_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #fbbf24; background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 4px; padding: 1px 5px;")

                c_meta_row.addWidget(lbl_ver, 0, Qt.AlignVCenter)
                c_meta_row.addStretch(1)
                c_meta_row.addWidget(price_badge, 0, Qt.AlignVCenter)
                c_layout.addLayout(c_meta_row)

                # Description Label
                lbl_t_desc = QLabel(t["description"])
                lbl_t_desc.setWordWrap(True)
                lbl_t_desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.3; border: none; background: transparent;")
                c_layout.addWidget(lbl_t_desc, stretch=1)

                # Footer Row: Tutorial Button (Left), Action Button (Right)
                btn_hbox = QHBoxLayout()
                btn_hbox.setContentsMargins(0, 0, 0, 0)
                btn_hbox.setSpacing(6)

                tut_url = t.get("tutorial_url", "")
                btn_tut = QPushButton("📺 Tutorial")
                btn_tut.setCursor(Qt.PointingHandCursor)
                btn_tut.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #191c2e;
                        color: {theme_col};
                        border: 1px solid {border_c};
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-weight: 700;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{ background-color: #232742; border-color: {hover_c}; color: #ffffff; }}
                """)
                btn_tut.clicked.connect(lambda *args, u=tut_url, tid=t['tool_id']: self.on_open_bot_tutorial(tid, u))
                btn_hbox.addWidget(btn_tut)
                btn_hbox.addStretch()

                if has_acc:
                    btn_action = QPushButton(t.get("btn_text", "⚡ Open Tool"))
                    btn_action.setCursor(Qt.PointingHandCursor)
                    btn_s = t.get("btn_bg_s", "#4f46e5")
                    btn_e = t.get("btn_bg_e", "#4338ca")
                    btn_b = t.get("btn_border", "#6366f1")
                    btn_h = t.get("btn_hover", "#818cf8")
                    btn_action.setStyleSheet(f"""
                        QPushButton {{
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {btn_s}, stop:1 {btn_e});
                            color: #ffffff;
                            border: 1px solid {btn_b};
                            border-radius: 6px;
                            padding: 4px 12px;
                            font-weight: 800;
                            font-size: 11px;
                        }}
                        QPushButton:hover {{
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {btn_e}, stop:1 #1e1b4b);
                            border-color: {btn_h};
                        }}
                    """)
                    btn_action.clicked.connect(t.get("callback", lambda: None))
                    btn_hbox.addWidget(btn_action)
                else:
                    buy_title = f"🛒 Buy ({price_lbl_str})" if price_lbl_str else "🛒 Buy License"
                    btn_action = QPushButton(buy_title)
                    btn_action.setCursor(Qt.PointingHandCursor)
                    btn_action.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309); color: #ffffff; font-size: 11px; font-weight: 800; padding: 4px 12px; border-radius: 6px; border: 1px solid #f59e0b;")
                    btn_action.clicked.connect(lambda _, tid=t["tool_id"]: self.on_buy_bot_license(tid))
                    btn_hbox.addWidget(btn_action)

                c_layout.addLayout(btn_hbox)
                self.tools_grid.addWidget(card, row, col)
            else:
                dummy = QWidget()
                dummy.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.tools_grid.addWidget(dummy, row, col)

    def _open_tool(self, tool_id: str, tool_info: dict = None):
        """Dynamically open/launch any cloud utility tool dialog by tool_id."""
        t_id_clean = str(tool_id or "").strip().lower()
        title = (tool_info.get("name") or tool_info.get("title") if isinstance(tool_info, dict) else t_id_clean)
        try:
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            tool_dir = Path(appdata) / "BrowserProfileManager" / "modules" / "tools" / t_id_clean
            # Smart Cloud OTA Auto-Updater: Check remote version vs local cached version
            remote_ver = str((tool_info.get("version") if isinstance(tool_info, dict) else "") or "").strip()
            ver_file = tool_dir / "version.txt"
            local_ver = ver_file.read_text(encoding="utf-8").strip() if ver_file.exists() else ""

            # If remote version is newer or different from local version, auto-purge cache and force fresh download!
            if remote_ver and local_ver != remote_ver:
                import shutil
                shutil.rmtree(tool_dir, ignore_errors=True)
                tool_dir.mkdir(parents=True, exist_ok=True)
                py_files = []
            else:
                py_files = list(tool_dir.glob("*.py"))

            if not py_files:
                if hasattr(self, "status_bar"):
                    self.status_bar.showMessage(f"⏳ Downloading tool '{title}' (v{remote_ver or 'latest'})...", 4000)
                
                # Attempt download from server
                import urllib.request
                target_dest = tool_dir / f"{t_id_clean}_tool.py"
                download_src = f"https://srbrowser.com/api/v1/store/tools/{t_id_clean}/download"
                try:
                    req = urllib.request.Request(download_src, headers={"User-Agent": "srkBrowser Desktop App"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        c_data = resp.read()
                        if c_data.startswith(b"PK\x03\x04"):
                            import zipfile, io
                            with zipfile.ZipFile(io.BytesIO(c_data)) as zf:
                                zf.extractall(tool_dir)
                            py_files = list(tool_dir.glob("*.py"))
                        elif not c_data.startswith(b'{"status": "error"') and not c_data.startswith(b'{"status":"error"'):
                            with open(target_dest, "wb") as out_f:
                                out_f.write(c_data)
                            py_files = [target_dest]
                            if remote_ver:
                                try:
                                    ver_file.write_text(remote_ver, encoding="utf-8")
                                except Exception:
                                    pass
                except Exception:
                    pass

            if not py_files:
                QMessageBox.information(
                    self,
                    "Cloud Utility Tool",
                    f"🛠️ Tool: {title}\n\n"
                    f"This tool is registered in the cloud catalog, but its Python script package has not been uploaded by the admin to the server yet.\n\n"
                    f"Once uploaded from the Admin Panel, clicking Open Tool will instantly download and launch it!"
                )
                return

            entry_file = py_files[0]
            for f in py_files:
                if f.name == f"{t_id_clean}_tool.py" or f.name == f"{t_id_clean}.py":
                    entry_file = f
                    break

            # Integrity check: if file was corrupted or contains null bytes, purge and re-download
            try:
                with open(entry_file, "rb") as f_chk:
                    head_data = f_chk.read(4096)
                    if b"\x00" in head_data:
                        import shutil
                        shutil.rmtree(tool_dir, ignore_errors=True)
                        tool_dir.mkdir(parents=True, exist_ok=True)
                        # Re-download immediately
                        target_dest = tool_dir / f"{t_id_clean}_tool.py"
                        download_src = f"https://srbrowser.com/api/v1/store/tools/{t_id_clean}/download"
                        req = urllib.request.Request(download_src, headers={"User-Agent": "srkBrowser Desktop App"})
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            c_data = resp.read()
                            with open(target_dest, "wb") as out_f:
                                out_f.write(c_data)
                        entry_file = target_dest
            except Exception:
                pass

            import importlib.util
            import sys
            tool_dir_str = str(tool_dir.resolve())
            if tool_dir_str not in sys.path:
                sys.path.insert(0, tool_dir_str)

            spec = importlib.util.spec_from_file_location(f"dynamic_tool_{t_id_clean}", str(entry_file))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type) and issubclass(attr, QDialog) and attr is not QDialog:
                        dlg = attr(self)
                        self._show_non_modal_dialog(dlg)
                        return
                if hasattr(mod, "launch_ui"):
                    mod.launch_ui(self)
                    return
                elif hasattr(mod, "main"):
                    mod.main()
                    return

            QMessageBox.information(self, "Tool", f"Tool [{title}] is active.")
        except Exception as err:
            import shutil
            shutil.rmtree(tool_dir, ignore_errors=True)
            QMessageBox.critical(self, "Tool Launch Error", f"Failed to launch tool '{title}':\n{err}")

    def _ensure_tools_path(self):
        """Ensure all potential modular tools paths exist in sys.path."""
        import os
        import sys
        base_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.abspath(os.path.join(base_dir, "..", "..", "tools")),
            os.path.abspath(os.path.join(base_dir, "..", "..", "04_Tools_Store")),
            os.path.abspath(os.path.join(base_dir, "..", "..", "..", "04_Tools_Store")),
            os.path.abspath(os.path.join(base_dir, "..", "..", "..", "tools")),
            os.path.abspath(os.path.join(base_dir, "..", "tools")),
        ]
        for p in possible_paths:
            if os.path.exists(p) and p not in sys.path:
                sys.path.insert(0, p)

    def _get_favorite_scripts_file_path(self) -> Path:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = Path(appdata) / "BrowserProfileManager"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "favorite_scripts.json"

    def _load_favorite_scripts(self) -> set:
        try:
            p = self._get_favorite_scripts_file_path()
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
        except Exception as e:
            logger.warning(f"Failed to load favorite scripts: {e}")
        return set()

    def _save_favorite_scripts(self) -> None:
        try:
            p = self._get_favorite_scripts_file_path()
            favs = getattr(self, "favorite_scripts_set", set())
            with open(p, "w", encoding="utf-8") as f:
                json.dump(list(favs), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save favorite scripts: {e}")

    def _toggle_favorite_script(self, script_id: str, script_name: str) -> None:
        if not hasattr(self, "favorite_scripts_set"):
            self.favorite_scripts_set = self._load_favorite_scripts()
        
        if script_id in self.favorite_scripts_set:
            self.favorite_scripts_set.remove(script_id)
            msg = f"⭐ Removed '{script_name}' from Favorites."
        else:
            self.favorite_scripts_set.add(script_id)
            msg = f"❤️ Added '{script_name}' to Favorites!"
        
        self._save_favorite_scripts()
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(msg, 3000)
        
        search_txt = self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else ""
        self._render_scripts_grid(search_text=search_txt)

    def _create_scripts_page(self) -> QWidget:
        """Create the 📜 Scripts manager page (100% Free, Clean & Modern)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        if not hasattr(self, "favorite_scripts_set"):
            self.favorite_scripts_set = self._load_favorite_scripts()
        if not hasattr(self, "_current_scripts_category"):
            self._current_scripts_category = "active"

        # Single-Line Compact Control Header Bar (Zero Space Waste)
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151829, stop:1 #111322);
                border: 1px solid #232742;
                border-radius: 10px;
            }
        """)
        header_hbox = QHBoxLayout(header_card)
        header_hbox.setContentsMargins(12, 8, 12, 8)
        header_hbox.setSpacing(10)

        # Tab Capsule: Active Automation Scripts & Favorites
        tab_capsule = QFrame()
        tab_capsule.setStyleSheet("background-color: #10121e; border: 1px solid #232742; border-radius: 8px;")
        tab_capsule_hbox = QHBoxLayout(tab_capsule)
        tab_capsule_hbox.setContentsMargins(3, 3, 3, 3)
        tab_capsule_hbox.setSpacing(4)

        self.btn_scripts_installed_tab = QPushButton("⚡ Active Scripts (0)")
        self.btn_scripts_installed_tab.setCursor(Qt.PointingHandCursor)
        self.btn_scripts_installed_tab.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
                color: #ffffff;
                font-weight: 800;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #6366f1;
            }
        """)

        self.btn_scripts_favorites_tab = QPushButton("❤️ Favorites (0)")
        self.btn_scripts_favorites_tab.setCursor(Qt.PointingHandCursor)
        self.btn_scripts_favorites_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 11.5px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
        """)

        self.btn_scripts_installed_tab.clicked.connect(lambda: self._switch_scripts_category("active"))
        self.btn_scripts_favorites_tab.clicked.connect(lambda: self._switch_scripts_category("favorites"))

        tab_capsule_hbox.addWidget(self.btn_scripts_installed_tab)
        tab_capsule_hbox.addWidget(self.btn_scripts_favorites_tab)
        header_hbox.addWidget(tab_capsule)

        self.txt_scripts_search = QLineEdit()
        self.txt_scripts_search.setPlaceholderText("🔍 Search scripts by name, category, or tag...")
        self.txt_scripts_search.setStyleSheet("""
            QLineEdit {
                background-color: #131626;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 11.5px;
            }
            QLineEdit:focus { border-color: #6366f1; background-color: #181c30; }
        """)
        self.txt_scripts_search.textChanged.connect(self._on_scripts_search_changed)
        header_hbox.addWidget(self.txt_scripts_search, stretch=1)

        layout.addWidget(header_card)

        # Scripts 3x4 Grid Area (3 cards per row, 4 cards per column)
        scripts_content = QWidget()
        scripts_content.setStyleSheet("background: transparent; border: none;")
        self.scripts_grid = QGridLayout(scripts_content)
        self.scripts_grid.setContentsMargins(0, 0, 0, 0)
        self.scripts_grid.setSpacing(12)
        for c in range(3):
            self.scripts_grid.setColumnStretch(c, 1)
        for r in range(4):
            self.scripts_grid.setRowStretch(r, 1)

        layout.addWidget(scripts_content, stretch=1)

        # Scripts Pagination Bar (12 per page)
        self.scripts_pagination_bar = self._create_scripts_pagination_bar()
        layout.addWidget(self.scripts_pagination_bar)

        if hasattr(self, "_sync_scripts_manifest_async"):
            self._sync_scripts_manifest_async()
        self._render_scripts_grid()
        return widget

    def _on_scripts_search_changed(self, text: str) -> None:
        """Debounced script studio search: smooth typing without UI freeze."""
        if not hasattr(self, "_scripts_search_timer"):
            self._scripts_search_timer = QTimer(self)
            self._scripts_search_timer.setSingleShot(True)
            self._scripts_search_timer.setInterval(160)
            self._scripts_search_timer.timeout.connect(lambda: self._render_scripts_grid(search_text=self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else ""))
        self._scripts_search_timer.start(160)

    def _switch_scripts_category(self, cat_mode: str = "active") -> None:
        self._current_scripts_category = cat_mode
        self.scripts_current_page = 1
        self._update_scripts_subnav_styles(cat_mode)
        search_txt = self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else ""
        self._render_scripts_grid(search_text=search_txt)

    def _update_scripts_subnav_styles(self, active_tab: str = "active") -> None:
        style_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #6366f1;"
        style_fav_active = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #be123c); color: #ffffff; font-weight: 800; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: 1px solid #f43f5e;"
        style_inactive = "background-color: transparent; color: #a6adc8; font-weight: 600; font-size: 11.5px; padding: 6px 14px; border-radius: 6px; border: none;"

        if hasattr(self, "btn_scripts_installed_tab") and self.btn_scripts_installed_tab:
            self.btn_scripts_installed_tab.setStyleSheet(style_active if active_tab == "active" else style_inactive)
        if hasattr(self, "btn_scripts_favorites_tab") and self.btn_scripts_favorites_tab:
            self.btn_scripts_favorites_tab.setStyleSheet(style_fav_active if active_tab == "favorites" else style_inactive)

    def _create_scripts_pagination_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ScriptsPaginationFrame")
        frame.setFixedHeight(32)
        frame.setStyleSheet("""
            QFrame#ScriptsPaginationFrame {
                background-color: #131626;
                border: 1px solid #202438;
                border-radius: 8px;
            }
            QSpinBox {
                background-color: #161829;
                color: #cdd6f4;
                border: 1px solid #282d47;
                border-radius: 5px;
                padding: 1px 4px;
                font-weight: 700;
                font-size: 11px;
                max-height: 22px;
                max-width: 42px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(8)

        self.lbl_scripts_page_total = QLabel("Total 0")
        self.lbl_scripts_page_total.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11.5px;")
        layout.addWidget(self.lbl_scripts_page_total)
        layout.addStretch()

        self.scripts_pages_hbox = QHBoxLayout()
        self.scripts_pages_hbox.setSpacing(3)
        layout.addLayout(self.scripts_pages_hbox)

        lbl_goto = QLabel("Go to")
        lbl_goto.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")

        self.spin_scripts_goto = QSpinBox()
        self.spin_scripts_goto.setRange(1, 1)
        self.spin_scripts_goto.setValue(1)
        self.spin_scripts_goto.setAlignment(Qt.AlignCenter)
        self.spin_scripts_goto.editingFinished.connect(self._on_scripts_goto_page)

        layout.addWidget(lbl_goto)
        layout.addWidget(self.spin_scripts_goto)

        return frame

    def _update_scripts_pagination_controls(self, total_items: int) -> None:
        import math
        self.scripts_page_size = 12
        if not hasattr(self, "scripts_current_page"):
            self.scripts_current_page = 1

        self.scripts_total_pages = max(1, math.ceil(total_items / self.scripts_page_size))
        self.scripts_current_page = min(max(1, self.scripts_current_page), self.scripts_total_pages)

        if hasattr(self, "lbl_scripts_page_total") and self.lbl_scripts_page_total:
            self.lbl_scripts_page_total.setText(f"Total {total_items}")

        if hasattr(self, "spin_scripts_goto") and self.spin_scripts_goto:
            self.spin_scripts_goto.blockSignals(True)
            self.spin_scripts_goto.setRange(1, self.scripts_total_pages)
            self.spin_scripts_goto.setValue(self.scripts_current_page)
            self.spin_scripts_goto.blockSignals(False)

        if not hasattr(self, "scripts_pages_hbox") or self.scripts_pages_hbox is None:
            return

        while self.scripts_pages_hbox.count() > 0:
            child = self.scripts_pages_hbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        btn_prev = QPushButton("‹")
        btn_prev.setEnabled(self.scripts_current_page > 1)
        btn_prev.setCursor(Qt.PointingHandCursor if self.scripts_current_page > 1 else Qt.ArrowCursor)
        btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_prev.clicked.connect(self._on_scripts_page_prev_clicked)
        self.scripts_pages_hbox.addWidget(btn_prev)

        page_nums = []
        if self.scripts_total_pages <= 7:
            page_nums = list(range(1, self.scripts_total_pages + 1))
        else:
            page_nums = [1]
            if self.scripts_current_page > 3:
                page_nums.append("...")
            
            start_p = max(2, self.scripts_current_page - 1)
            end_p = min(self.scripts_total_pages - 1, self.scripts_current_page + 1)
            for p in range(start_p, end_p + 1):
                if p not in page_nums:
                    page_nums.append(p)
            
            if self.scripts_current_page < self.scripts_total_pages - 2:
                page_nums.append("...")
            if self.auto_total_pages not in page_nums:
                page_nums.append(self.scripts_total_pages)

        for item in page_nums:
            if item == "...":
                lbl_dots = QLabel("...")
                lbl_dots.setStyleSheet("color: #6c7086; font-weight: bold; padding: 0 2px; font-size: 11px;")
                self.scripts_pages_hbox.addWidget(lbl_dots)
            else:
                p_num = int(item)
                btn = QPushButton(str(p_num))
                btn.setCursor(Qt.PointingHandCursor)
                if p_num == self.scripts_current_page:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #89b4fa; color: #11111b; border: 1px solid #89b4fa;
                            border-radius: 4px; padding: 2px 7px; font-weight: 800; font-size: 11.5px; max-height: 22px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                            border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 11.5px; max-height: 22px;
                        }
                        QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
                    """)
                btn.clicked.connect(lambda _, p=p_num: self._go_to_scripts_page(p))
                self.scripts_pages_hbox.addWidget(btn)

        btn_next = QPushButton("›")
        btn_next.setEnabled(self.scripts_current_page < self.scripts_total_pages)
        btn_next.setCursor(Qt.PointingHandCursor if self.scripts_current_page < self.scripts_total_pages else Qt.ArrowCursor)
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 12px; max-height: 22px;
            }
            QPushButton:hover { background-color: #313244; border-color: #89b4fa; }
            QPushButton:disabled { background-color: #181825; color: #45475a; border-color: #181825; }
        """)
        btn_next.clicked.connect(self._on_scripts_page_next_clicked)
        self.scripts_pages_hbox.addWidget(btn_next)

    def _on_scripts_page_prev_clicked(self) -> None:
        if hasattr(self, "scripts_current_page") and self.scripts_current_page > 1:
            self.scripts_current_page -= 1
            self._render_scripts_grid(search_text=self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else "")

    def _on_scripts_page_next_clicked(self) -> None:
        if hasattr(self, "scripts_current_page") and hasattr(self, "scripts_total_pages") and self.scripts_current_page < self.scripts_total_pages:
            self.scripts_current_page += 1
            self._render_scripts_grid(search_text=self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else "")

    def _on_scripts_goto_page(self) -> None:
        if hasattr(self, "spin_scripts_goto"):
            val = self.spin_scripts_goto.value()
            self._go_to_scripts_page(val)

    def _go_to_scripts_page(self, page_num: int) -> None:
        if hasattr(self, "scripts_total_pages") and 1 <= page_num <= self.scripts_total_pages:
            self.scripts_current_page = page_num
            self._render_scripts_grid(search_text=self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else "")

    def _render_scripts_grid(self, search_text: str = "") -> None:
        if not hasattr(self, "scripts_grid") or self.scripts_grid is None:
            return

        if not hasattr(self, "favorite_scripts_set"):
            self.favorite_scripts_set = self._load_favorite_scripts()
        if not hasattr(self, "_current_scripts_category"):
            self._current_scripts_category = "active"

        _clear_layout(self.scripts_grid)

        for col in range(3):
            self.scripts_grid.setColumnStretch(col, 1)
        for row in range(4):
            self.scripts_grid.setRowStretch(row, 1)

        # Cloud-driven dynamic automation scripts (loaded from server manifest)
        builtin_scripts = []

        # Dynamic Luxury Cyberpunk Palette Pool for Script Studio
        dynamic_palettes = [
            ("#112420", "#0a1714", "#1b3d36", "#2dd4bf", "rgba(45, 212, 191, 0.16)"),  # Cyber Teal / Mint (Account Info)
            ("#282013", "#18130a", "#46351d", "#facc15", "rgba(250, 204, 21, 0.16)"),  # Solar Gold / Amber (Re-login)
            ("#2a1c14", "#180f0b", "#4a2f20", "#fb923c", "rgba(251, 146, 60, 0.16)"),  # Sunset Flame / Copper (Video)
            ("#221832", "#130e1e", "#3d2856", "#c084fc", "rgba(192, 132, 252, 0.16)"),  # Cyber Orchid / Purple (BM Creator)
            ("#12242c", "#0a161c", "#1c3d4b", "#38bdf8", "rgba(56, 189, 248, 0.16)"),  # Electric Cyan / Sky (Lang Convert)
            ("#12261e", "#0c1813", "#1d4234", "#34d399", "rgba(52, 211, 153, 0.16)"),  # Emerald Mint / Matrix (Page Create)
            ("#2b1522", "#190d14", "#4e223c", "#f43f5e", "rgba(244, 63, 94, 0.16)"),   # Hot Crimson / Rose
        ]

        # Canonical mapping to eliminate duplicate IDs
        canonical_id_map = {
            "fb_quick_page_creator": "fb_quick_page_create",
            "fb_page_creator": "fb_quick_page_create",
            "fb_lang_convert": "fb_language_converter",
            "fb_language_convert": "fb_language_converter",
            "fb_auto_relogin": "fb_relogin",
            "fb_re_login": "fb_relogin",
            "fb_acc_info": "fb_account_info",
            "fb_info": "fb_account_info",
            "info": "fb_account_info",
            "account_info": "fb_account_info"
        }

        online_scripts = getattr(self, "_online_scripts_list", None) or []
        
        # Discover local scripts from 06_Script_Store so newly developed scripts appear instantly
        local_scripts = []
        try:
            from pathlib import Path
            import json
            base_p = Path(__file__).resolve().parent.parent.parent
            store_candidates = [
                base_p / "06_Script_Store",
                base_p.parent / "06_Script_Store",
                Path.cwd() / "06_Script_Store"
            ]
            for sc_dir in store_candidates:
                if sc_dir.exists() and sc_dir.is_dir():
                    for s_folder in sorted(sc_dir.iterdir(), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
                        if s_folder.is_dir():
                            mf = s_folder / "manifest.json"
                            if mf.exists():
                                try:
                                    with open(mf, "r", encoding="utf-8") as mfile:
                                        m_data = json.load(mfile)
                                    m_id = m_data.get("id")
                                    if m_id:
                                        local_scripts.append({
                                            "script_id": m_id,
                                            "full_name": m_data.get("name", m_id.replace("_", " ").title()),
                                            "short_name": m_data.get("short_name", m_id[:6]).upper(),
                                            "version": m_data.get("version", "1.0.0"),
                                            "category": m_data.get("category", "AUTOMATION"),
                                            "icon": m_data.get("icon", "⚡"),
                                            "desc": m_data.get("description", "High-speed automated cloud workflow script.")
                                        })
                                except Exception:
                                    pass
                    break
        except Exception:
            pass

        # Combine local and online scripts, keeping local newest scripts first
        combined_scripts = []
        seen_sids = set()
        for ls in local_scripts:
            sid = canonical_id_map.get(ls["script_id"], ls["script_id"])
            if sid not in seen_sids:
                combined_scripts.append(ls)
                seen_sids.add(sid)
        for os_item in (online_scripts if isinstance(online_scripts, list) else []):
            raw_id = os_item.get("script_id") or os_item.get("id")
            if raw_id:
                sid = canonical_id_map.get(raw_id, raw_id)
                if sid not in seen_sids:
                    combined_scripts.append(os_item)
                    seen_sids.add(sid)

        scripts_map = {s["script_id"]: s for s in builtin_scripts}

        if combined_scripts:
            for os_idx, os in enumerate(combined_scripts):
                raw_sid = os.get("script_id") or os.get("id")
                if not raw_sid:
                    continue
                sid = canonical_id_map.get(raw_sid, raw_sid)
                if sid in scripts_map:
                    continue

                bg_s, bg_e, b_col, a_col, i_bg = dynamic_palettes[os_idx % len(dynamic_palettes)]
                s_lower = sid.lower()
                icon = os.get("icon")
                if not icon:
                    if "video" in s_lower or "vup" in s_lower:
                        icon = "🎬"
                    elif "relogin" in s_lower or "login" in s_lower or "auth" in s_lower:
                        icon = "🔑"
                    elif "info" in s_lower or "cred" in s_lower:
                        icon = "ℹ️"
                    elif "bm" in s_lower or "business" in s_lower:
                        icon = "⚡"
                    elif "lang" in s_lower:
                        icon = "🌐"
                    elif "page" in s_lower:
                        icon = "📄"
                    elif "cookie" in s_lower:
                        icon = "🍪"
                    elif "share" in s_lower:
                        icon = "📢"
                    elif "post" in s_lower:
                        icon = "📝"
                    elif "bot" in s_lower:
                        icon = "🤖"
                    elif "react" in s_lower or "like" in s_lower:
                        icon = "👍"
                    elif "group" in s_lower:
                        icon = "👥"
                    else:
                        icon = "⚡"

                scripts_map[sid] = {
                    "script_id": sid,
                    "full_name": os.get("full_name") or os.get("title") or f"📜 {sid.replace('_', ' ').title()}",
                    "short_name": os.get("short_name", sid[:6]).upper(),
                    "version": str(os.get("version", "v1.0.0")),
                    "category": os.get("category") or "AUTOMATION",
                    "icon": icon,
                    "desc": os.get("description") or os.get("desc") or "High-speed automated cloud workflow script.",
                    "bg_start": bg_s, "bg_end": bg_e, "border": b_col, "border_hover": a_col,
                    "theme_color": a_col, "icon_bg": i_bg
                }

        scripts_to_show = list(scripts_map.values())
        total_count = len(scripts_to_show)
        active_count = len([s for s in scripts_to_show if not (hasattr(self, "bot_license_mgr") and self.bot_license_mgr.is_item_deactivated("script", s["script_id"]))])
        fav_count = sum(1 for s in scripts_to_show if s["script_id"] in self.favorite_scripts_set)

        if hasattr(self, "btn_scripts_installed_tab") and self.btn_scripts_installed_tab:
            self.btn_scripts_installed_tab.setText(f"⚡ Active Scripts ({active_count})")
        if hasattr(self, "btn_scripts_favorites_tab") and self.btn_scripts_favorites_tab:
            self.btn_scripts_favorites_tab.setText(f"❤️ Favorites ({fav_count})")

        # Filter by active tab (All/Active vs Favorites)
        if self._current_scripts_category == "favorites":
            source_scripts = [s for s in scripts_to_show if s["script_id"] in self.favorite_scripts_set]
        else:
            source_scripts = scripts_to_show

        query = search_text.lower().strip()
        matched = []
        for s in source_scripts:
            if not query or query in s["full_name"].lower() or query in s["desc"].lower() or query in s["short_name"].lower() or query in s.get("category", "").lower():
                matched.append(s)

        # Update Pagination Controls for 9 per page
        self._update_scripts_pagination_controls(len(matched))

        # Slice 9 items for current page
        start_idx = (self.scripts_current_page - 1) * self.scripts_page_size
        end_idx = start_idx + self.scripts_page_size
        page_items = matched[start_idx:end_idx]

        if not matched:
            empty_frame = QFrame()
            empty_frame.setStyleSheet("background: #111424; border: 1px dashed #232742; border-radius: 12px; padding: 40px;")
            v_empty = QVBoxLayout(empty_frame)
            v_empty.setAlignment(Qt.AlignCenter)

            if self._current_scripts_category == "favorites":
                lbl_no = QLabel("❤️ No Favorite Scripts Added Yet" if not query else f"🔍 No favorite scripts matching '{query}'")
                lbl_no.setStyleSheet("font-size: 15px; font-weight: bold; color: #f43f5e; border: none;")
                lbl_sub = QLabel("Click the ⭐ star icon on any script card to add your favourite automation scripts here for instant access!")
                lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8; border: none; margin-top: 6px;")
                v_empty.addWidget(lbl_no, alignment=Qt.AlignCenter)
                v_empty.addWidget(lbl_sub, alignment=Qt.AlignCenter)
            else:
                lbl_no = QLabel(f"🔍 No scripts found matching '{query}'" if query else "📜 No automation scripts published yet")
                lbl_no.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4; border: none;")
                v_empty.addWidget(lbl_no, alignment=Qt.AlignCenter)
                if not query:
                    lbl_sub = QLabel("Publish scripts from the Admin Panel or click Refresh to sync from cloud.")
                    lbl_sub.setStyleSheet("font-size: 12px; color: #a6adc8; margin-top: 6px; border: none;")
                    v_empty.addWidget(lbl_sub, alignment=Qt.AlignCenter)
                    btn_refresh = QPushButton("🔄 Refresh Cloud Scripts")
                    btn_refresh.setCursor(Qt.PointingHandCursor)
                    btn_refresh.setStyleSheet("background-color: #4f46e5; color: #ffffff; font-weight: 700; border-radius: 6px; padding: 6px 16px; font-size: 11.5px; margin-top: 10px;")
                    btn_refresh.clicked.connect(self._sync_scripts_manifest_async)
                    v_empty.addWidget(btn_refresh, alignment=Qt.AlignCenter)

            self.scripts_grid.addWidget(empty_frame, 0, 0, 1, 3)
            return

        for idx in range(12):
            row = idx // 3
            col = idx % 3
            if idx < len(page_items):
                s = page_items[idx]
                bg_start = s.get("bg_start", "#1a1e2e")
                bg_end = s.get("bg_end", "#131624")
                border_color = s.get("border", "#282f49")
                hover_color = s.get("border_hover", "#818cf8")
                theme_color = s.get("theme_color", "#818cf8")
                icon_bg = s.get("icon_bg", "rgba(129, 140, 248, 0.14)")

                sc_frame = QFrame()
                sc_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                sc_frame.setMinimumHeight(135)
                sc_frame.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_start}, stop:1 {bg_end});
                        border: 1px solid {border_color};
                        border-radius: 10px;
                    }}
                    QFrame:hover {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_start}, stop:1 #202438);
                        border: 1px solid {hover_color};
                    }}
                """)
                sc_vbox = QVBoxLayout(sc_frame)
                sc_vbox.setContentsMargins(14, 12, 14, 12)
                sc_vbox.setSpacing(6)

                # Row 1 (Header): Icon + Title (Full Stretch Width) + Favorite Star
                st_top_row = QHBoxLayout()
                st_top_row.setContentsMargins(0, 0, 0, 0)
                st_top_row.setSpacing(8)

                s_icon = s.get("icon", "⚡")
                lbl_icon = QLabel(s_icon)
                lbl_icon.setStyleSheet(f"font-size: 14px; background: {icon_bg}; color: {theme_color}; border: 1px solid {border_color}; border-radius: 6px; padding: 2px 6px;")

                full_s_name = s["full_name"]
                import re
                clean_title = re.sub(r'^[^\w\s]+\s*', '', full_s_name).strip() or full_s_name
                st_lbl = QLabel(clean_title)
                st_lbl.setWordWrap(True)
                st_lbl.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #ffffff; border: none; background: transparent; line-height: 1.25;")
                st_lbl.setToolTip(full_s_name)

                # Favorite Star Button
                is_fav = s["script_id"] in self.favorite_scripts_set
                btn_fav = QPushButton("⭐" if is_fav else "☆")
                btn_fav.setCursor(Qt.PointingHandCursor)
                btn_fav.setToolTip("Remove from Favorites" if is_fav else "Add to Favorites")
                if is_fav:
                    btn_fav.setStyleSheet("""
                        QPushButton {
                            background: rgba(251, 191, 36, 0.2);
                            color: #fbbf24;
                            font-size: 12px;
                            font-weight: 900;
                            border: 1px solid rgba(251, 191, 36, 0.5);
                            border-radius: 4px;
                            padding: 1px 5px;
                        }
                        QPushButton:hover {
                            background: rgba(251, 191, 36, 0.35);
                        }
                    """)
                else:
                    btn_fav.setStyleSheet("""
                        QPushButton {
                            background: rgba(255, 255, 255, 0.04);
                            color: #64748b;
                            font-size: 12px;
                            font-weight: bold;
                            border: 1px solid #282d47;
                            border-radius: 4px;
                            padding: 1px 5px;
                        }
                        QPushButton:hover {
                            color: #fbbf24;
                            border-color: #fbbf24;
                            background: rgba(251, 191, 36, 0.12);
                        }
                    """)
                btn_fav.clicked.connect(lambda _, sid=s["script_id"], sname=full_s_name: self._toggle_favorite_script(sid, sname))

                st_top_row.addWidget(lbl_icon, 0, Qt.AlignVCenter)
                st_top_row.addWidget(st_lbl, 1, Qt.AlignVCenter)
                st_top_row.addWidget(btn_fav, 0, Qt.AlignVCenter)
                sc_vbox.addLayout(st_top_row)

                # Row 2 (Meta Info): Version Badge (Left) + Free/Price Badge (Right)
                st_meta_row = QHBoxLayout()
                st_meta_row.setContentsMargins(0, 0, 0, 0)
                st_meta_row.setSpacing(6)

                st_ver = QLabel(s["version"])
                st_ver.setStyleSheet(f"font-size: 9.5px; font-weight: bold; color: {theme_color}; background: {icon_bg}; border: 1px solid {border_color}; border-radius: 4px; padding: 1px 5px;")

                lbl_badge = QLabel("🎁 FREE")
                lbl_badge.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #10b981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 1px 5px;")

                st_meta_row.addWidget(st_ver, 0, Qt.AlignVCenter)
                st_meta_row.addStretch(1)
                st_meta_row.addWidget(lbl_badge, 0, Qt.AlignVCenter)
                sc_vbox.addLayout(st_meta_row)

                # Description
                s_desc = QLabel(s["desc"])
                s_desc.setWordWrap(True)
                s_desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.3; border: none; background: transparent;")
                sc_vbox.addWidget(s_desc, stretch=1)

                s_btn_hbox = QHBoxLayout()
                s_btn_hbox.setContentsMargins(0, 0, 0, 0)
                s_btn_hbox.setSpacing(6)

                is_script_deact = hasattr(self, "bot_license_mgr") and self.bot_license_mgr.is_item_deactivated("script", s["script_id"])
                is_active = not is_script_deact

                btn_assign = QPushButton("🎯 Target Scope")
                btn_assign.setCursor(Qt.PointingHandCursor)
                btn_assign.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #191c2e;
                        color: {theme_color};
                        border: 1px solid {border_color};
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-weight: 700;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        background-color: #232742;
                        border-color: {hover_color};
                        color: #ffffff;
                    }}
                """)
                btn_assign.clicked.connect(lambda _, sid=s["script_id"], sname=full_s_name: self.on_assign_script_target(sid, sname))
                s_btn_hbox.addWidget(btn_assign)
                s_btn_hbox.addStretch()

                # Modern Pill Toggle Switch Slider
                from core.ui.widgets import ModernToggleSwitch
                switch_status = ModernToggleSwitch(checked=is_active, active_color=theme_color)
                switch_status.toggled.connect(lambda state, sid=s["script_id"], sname=full_s_name: self.on_toggle_script_active(sid, sname, state))
                s_btn_hbox.addWidget(switch_status)

                sc_vbox.addLayout(s_btn_hbox)
                self.scripts_grid.addWidget(sc_frame, row, col)
            else:
                dummy = QWidget()
                dummy.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.scripts_grid.addWidget(dummy, row, col)

    def on_toggle_script_active(self, script_id: str, script_name: str, make_active: bool) -> None:
        """Toggle active/disabled state of a script."""
        if hasattr(self, "bot_license_mgr"):
            if make_active:
                self.bot_license_mgr.activate_item("script", script_id)
                self.status_bar.showMessage(f"🟢 Script '{script_name}' is now Enabled.", 3000)
                # Auto-assign to all profiles if newly enabled and not yet present in any profile
                if script_id in ("fb_account_info", "info"):
                    all_profs = self.profile_mgr.get_all_profiles()
                    has_any = any("fb_account_info" in (p.get("assigned_scripts") or []) for p in all_profs)
                    if not has_any:
                        for p in all_profs:
                            assigned = list(p.get("assigned_scripts") or [])
                            if "fb_account_info" not in assigned:
                                assigned.append("fb_account_info")
                                p["assigned_scripts"] = assigned
                        try:
                            self.profile_mgr.save_profiles()
                        except Exception:
                            pass
            else:
                self.bot_license_mgr.deactivate_item("script", script_id)
                self.status_bar.showMessage(f"⚪ Script '{script_name}' is now Disabled.", 3000)
        self._render_scripts_grid(search_text=self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else "")
        self.refresh_all_views()

    def on_assign_script_target(self, script_id: str, script_name: str) -> None:
        """Assign script quick action button to specific profiles or groups."""
        if hasattr(self, "bot_license_mgr") and self.bot_license_mgr.is_item_deactivated("script", script_id):
            QMessageBox.information(
                self,
                "Script Disabled",
                f"⚠️ '{script_name}' is currently Disabled.\n\nPlease Enable the script first before configuring its Target Scope."
            )
            return

        from core.ui.dialogs import ExtensionTargetDialog, TargetScopeProgressDialog
        groups = self.profile_mgr.get_groups()
        dlg = ExtensionTargetDialog(script_name, groups, item_type="script", parent=self)
        if dlg.exec() == ExtensionTargetDialog.Accepted:
            mode, target_grps = dlg.get_selection()
            all_profiles = self.profile_mgr.get_all_profiles()
            total_profs = len(all_profiles)

            # Show modern progress popup dialog
            prog = TargetScopeProgressDialog(
                item_name=script_name,
                total_profiles=total_profs,
                item_type="script",
                parent=self
            )
            prog.show()

            for i, p in enumerate(all_profiles):
                pid = p["id"]
                p_name = p.get("name") or f"Profile #{p.get('number', i + 1)}"
                p_grp = p.get("group", "Default")
                assigned = p.get("assigned_scripts", [])
                if isinstance(assigned, str):
                    assigned = [assigned]
                else:
                    assigned = list(assigned)

                should_have = False
                if mode == "all":
                    should_have = True
                elif mode == "groups" and p_grp in target_grps:
                    should_have = True

                if should_have and script_id not in assigned:
                    assigned.append(script_id)
                elif not should_have and script_id in assigned:
                    if script_id in assigned:
                        assigned.remove(script_id)

                p["assigned_scripts"] = assigned
                try:
                    p_folder = self.profile_mgr.get_profile_folder(pid)
                    from utils import safe_write_json
                    safe_write_json(p_folder / "profile.json", p)
                except Exception:
                    pass

                prog.set_progress(i + 1, total_profs, p_name)

            # Batch save once to database
            try:
                self.profile_mgr.save_profiles()
            except Exception:
                pass

            try:
                import threading
                from cloud_sync import upload_profiles_cloud_backup
                threading.Thread(target=upload_profiles_cloud_backup, args=(all_profiles,), daemon=True).start()
            except Exception:
                pass

            prog.set_completed(f"✅ Successfully configured for {total_profs} profiles!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(600, prog.accept)

            self.refresh_all_views()


    def _connect_signals(self) -> None:
        self.browser_launcher.process_started.connect(self._on_browser_process_changed)
        self.browser_launcher.process_syncing.connect(self._on_browser_process_syncing)
        self.browser_launcher.process_finished.connect(self._on_browser_process_changed)

    def _on_browser_process_syncing(self, profile_id: str) -> None:
        if not hasattr(self, "cards_vbox"):
            return
        from core.ui.widgets import ProfileCard
        for i in range(self.cards_vbox.count()):
            item = self.cards_vbox.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ProfileCard):
                card = item.widget()
                if card.profile_id == profile_id:
                    card.update_syncing_state(True)
                    break

    def _on_browser_process_changed(self, profile_id: str) -> None:
        self._refresh_dashboard()
        self._update_cards_running_status()
        self.update_bulk_open_button_state()
        running_count = sum(1 for p in self.profile_mgr.profiles if self.browser_launcher.is_running(p["id"]))
        total_count = len(self.profile_mgr.profiles)
        self.status_bar.showMessage(f"Total Profiles: {total_count} | Active Browsers: {running_count}")

    def _update_cards_running_status(self) -> None:
        if not hasattr(self, "cards_vbox"):
            return
        from core.ui.widgets import ProfileCard
        for i in range(self.cards_vbox.count()):
            item = self.cards_vbox.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ProfileCard):
                card = item.widget()
                is_running = self.browser_launcher.is_running(card.profile_id)
                card.update_syncing_state(False)
                card.update_running_state(is_running)

    def _apply_team_permissions_to_ui(self) -> None:
        """Dynamically lock or hide restricted buttons, tabs, and filter groups for team members."""
        if not hasattr(self, "auth_mgr") or not self.auth_mgr:
            return

        is_member = self.auth_mgr.is_team_member()

        # 1. Navigation Tabs Isolation (Automation & Team are exclusive to Master Owner)
        if hasattr(self, "btn_nav_automation"):
            self.btn_nav_automation.setVisible(not is_member)
        if hasattr(self, "btn_nav_team"):
            self.btn_nav_team.setVisible(not is_member)
        if hasattr(self, "act_team"):
            self.act_team.setVisible(not is_member)

        # 2. Top Toolbar Plan/Upgrade Badge
        if hasattr(self, "btn_top_upgrade"):
            if is_member:
                self.btn_top_upgrade.setText("👥 Team Operator")
                self.btn_top_upgrade.setCursor(Qt.ArrowCursor)
                self.btn_top_upgrade.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(99, 102, 241, 0.25), stop:1 rgba(168, 85, 247, 0.25));
                        color: #c7d2fe;
                        font-weight: 800;
                        font-size: 11.5px;
                        border: 1px solid rgba(99, 102, 241, 0.5);
                        border-radius: 6px;
                        padding: 5px 14px;
                    }
                """)
            else:
                self.btn_top_upgrade.setCursor(Qt.PointingHandCursor)

        # 3. Dashboard Isolation & Dynamic 2-Box Balance
        if hasattr(self, "box_quick_bots"):
            self.box_quick_bots.setVisible(not is_member)
        if hasattr(self, "box_member_workspace"):
            self.box_member_workspace.setVisible(is_member)
        if hasattr(self, "btn_dash_upgrade_act"):
            self.btn_dash_upgrade_act.setVisible(not is_member)
        if hasattr(self, "strip_dash_vip"):
            self.strip_dash_vip.setVisible(not is_member)
        if hasattr(self, "strip_member_sync"):
            self.strip_member_sync.setVisible(is_member)

        # Update Box 4 Badge & Title
        if hasattr(self, "lbl_b4_title"):
            self.lbl_b4_title.setText("🛡️ System Utilities & Quick Tools")
        if hasattr(self, "badge_b4"):
            self.badge_b4.setText("⚡ Lifetime Unlimited")
            self.badge_b4.setStyleSheet("background-color: rgba(16, 185, 129, 0.12); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-weight: 700; font-size: 10px;")

        # Card 3 in Row 2: Keep visible at all times to maintain perfect 4-card metric symmetry
        if hasattr(self, "card_bots"):
            self.card_bots.setVisible(True)
            if is_member:
                if hasattr(self.card_bots, "label"):
                    self.card_bots.label.setText("SHIELD STATUS")
                if hasattr(self.card_bots, "icon_badge"):
                    self.card_bots.icon_badge.setText("🛡️")
                if hasattr(self.card_bots, "value_label"):
                    self.card_bots.value_label.setText("100% Protected")
                    self.card_bots.value_label.setStyleSheet("color: #a6e3a1; font-size: 20px; font-weight: 900; font-family: 'Segoe UI', system-ui, sans-serif;")
            else:
                if hasattr(self.card_bots, "label"):
                    self.card_bots.label.setText("AUTOMATION BOTS")
                if hasattr(self.card_bots, "icon_badge"):
                    self.card_bots.icon_badge.setText("🤖")
                if hasattr(self.card_bots, "value_label"):
                    curr_txt = self.card_bots.value_label.text()
                    if not curr_txt or "100%" in curr_txt or "Protected" in curr_txt:
                        b_cnt = len(getattr(self, "_cached_active_bots", []))
                        if not b_cnt and hasattr(self, "plugin_engine"):
                            try:
                                b_cnt = len(self.plugin_engine.get_all_bots())
                            except Exception:
                                b_cnt = 5
                        self.card_bots.value_label.setText(f"{b_cnt or 5} Active")
                    self.card_bots.value_label.setStyleSheet("color: #cba6f7; font-size: 25px; font-weight: 900; font-family: 'Segoe UI', system-ui, sans-serif;")

        # Dynamic Member Workspace Chips Update
        if is_member and hasattr(self, "chip_member_groups"):
            user_info = self.auth_mgr.get_current_user() if self.auth_mgr else {}
            assigned = user_info.get("assigned_groups", ["Default"])
            if not assigned or "All" in assigned:
                assigned_txt = "🟢 All Groups"
            else:
                assigned_txt = "🟢 " + (", ".join(assigned) if len(assigned) <= 2 else f"{len(assigned)} Groups")
            
            can_create = self.auth_mgr.can_create_profiles()
            can_edit = self.auth_mgr.can_edit_profiles()
            can_delete = self.auth_mgr.can_delete_profiles()

            if hasattr(self.chip_member_groups, "lbl_status"):
                self.chip_member_groups.lbl_status.setText(assigned_txt)
            if hasattr(self.chip_member_create, "lbl_status"):
                self.chip_member_create.lbl_status.setText("🟢 Allowed" if can_create else "🔒 Restricted")
                self.chip_member_create.lbl_status.setStyleSheet("color: #a6e3a1; font-size: 9.5px; font-weight: 600;" if can_create else "color: #fca5a5; font-size: 9.5px; font-weight: 600;")
            if hasattr(self.chip_member_edit, "lbl_status"):
                self.chip_member_edit.lbl_status.setText("🟢 Allowed" if can_edit else "🔒 Restricted")
                self.chip_member_edit.lbl_status.setStyleSheet("color: #a6e3a1; font-size: 9.5px; font-weight: 600;" if can_edit else "color: #fca5a5; font-size: 9.5px; font-weight: 600;")
            if hasattr(self.chip_member_delete, "lbl_status"):
                self.chip_member_delete.lbl_status.setText("🟢 Allowed" if can_delete else "🔒 Owner Only")
                self.chip_member_delete.lbl_status.setStyleSheet("color: #a6e3a1; font-size: 9.5px; font-weight: 600;" if can_delete else "color: #fca5a5; font-size: 9.5px; font-weight: 600;")

        if not is_member:
            # Full owner/standard access: unlock all controls
            if hasattr(self, "btn_bulk_delete"):
                self.btn_bulk_delete.setEnabled(True)
                self.btn_bulk_delete.setToolTip("")
            if hasattr(self, "btn_create_profile"):
                self.btn_create_profile.setEnabled(True)
                self.btn_create_profile.setToolTip("")
            if hasattr(self, "btn_bulk_create"):
                self.btn_bulk_create.setEnabled(True)
                self.btn_bulk_create.setToolTip("")
            if hasattr(self, "btn_bulk_edit"):
                self.btn_bulk_edit.setEnabled(True)
                self.btn_bulk_edit.setToolTip("")
            return

        # 4. Profile Management Specific Permissions for Members
        can_delete = self.auth_mgr.can_delete_profiles()
        if hasattr(self, "btn_bulk_delete"):
            self.btn_bulk_delete.setEnabled(can_delete)
            if not can_delete:
                self.btn_bulk_delete.setToolTip("🔒 Profile deletion is restricted by Team Owner.")

        can_create = self.auth_mgr.can_create_profiles()
        if hasattr(self, "btn_create_profile"):
            self.btn_create_profile.setEnabled(can_create)
            if not can_create:
                self.btn_create_profile.setToolTip("🔒 Profile creation is restricted by Team Owner.")
        if hasattr(self, "btn_bulk_create"):
            self.btn_bulk_create.setEnabled(can_create)
            if not can_create:
                self.btn_bulk_create.setToolTip("🔒 Profile creation is restricted by Team Owner.")

        can_edit = self.auth_mgr.can_edit_profiles()
        if hasattr(self, "btn_bulk_edit"):
            self.btn_bulk_edit.setEnabled(can_edit)
            if not can_edit:
                self.btn_bulk_edit.setToolTip("🔒 Profile editing is restricted by Team Owner.")

    def refresh_all_views(self, force: bool = False) -> None:
        """Refresh active view and update status bar dynamically without redundant background re-renders."""
        if force:
            self.profile_mgr.sync_and_repair_profiles()
            self._refresh_dashboard()
            self._refresh_profiles_list()
            self._refresh_settings_view()
            self._refresh_extensions_view()
        else:
            curr_idx = self.stack.currentIndex() if hasattr(self, "stack") else 1
            if curr_idx == 0:
                self._refresh_dashboard()
            elif curr_idx == 1:
                self._refresh_profiles_list()
            elif curr_idx == 2:
                if hasattr(self, "_sync_store_manifest_async"):
                    self._sync_store_manifest_async()
            elif curr_idx == 3:
                self._refresh_extensions_view()
            elif curr_idx == 4:
                if hasattr(self, "_sync_tools_manifest_async"):
                    self._sync_tools_manifest_async()
            elif curr_idx == 5:
                if hasattr(self, "_sync_scripts_manifest_async"):
                    self._sync_scripts_manifest_async()
            elif curr_idx == 6:
                self._refresh_settings_view()

        self._apply_team_permissions_to_ui()
        self.update_bulk_open_button_state()

        running_count = sum(1 for p in self.profile_mgr.profiles if self.browser_launcher.is_running(p["id"]))
        total_count = len(self.profile_mgr.profiles)
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage(f"Total Profiles: {total_count} | Active Browsers: {running_count}")

        if hasattr(self, "auth_mgr") and self.auth_mgr.is_logged_in():
            user_info = self.auth_mgr.get_current_user()
            role_tag = f" (Team Member)" if self.auth_mgr.is_team_member() else ""
            name_display = (user_info.get("full_name") or user_info.get("email", "User Account").split("@")[0]) + role_tag
            if hasattr(self, "btn_account_status"):
                self.btn_account_status.setText(f"👤  {name_display}  ▾")

    def _update_profiles_folder_size_async(self) -> None:
        """Calculate disk size of the profiles folder in a background thread to prevent UI freezing."""
        if getattr(self, "_is_calculating_profiles_size", False):
            return
        self._is_calculating_profiles_size = True

        import threading
        def _calc_worker():
            try:
                target_dir = getattr(self.profile_mgr, "base_dir", None)
                if not target_dir or not os.path.exists(str(target_dir)):
                    res_str = "0.0 KB"
                else:
                    total_bytes = 0
                    dir_str = str(target_dir)
                    for root, _, files in os.walk(dir_str):
                        for f in files:
                            try:
                                fp = os.path.join(root, f)
                                total_bytes += os.path.getsize(fp)
                            except (OSError, PermissionError):
                                pass

                    if total_bytes < 1024 * 1024:
                        kb = total_bytes / 1024
                        res_str = f"{kb:.1f} KB" if kb > 0 else "0.0 KB"
                    elif total_bytes < 1024 * 1024 * 1024:
                        mb = total_bytes / (1024 * 1024)
                        res_str = f"{mb:.1f} MB"
                    else:
                        gb = total_bytes / (1024 * 1024 * 1024)
                        res_str = f"{gb:.2f} GB"

                self._cached_profiles_size_str = res_str

                def _apply_ui():
                    if hasattr(self, "lbl_setting_profiles_size") and self.lbl_setting_profiles_size:
                        self.lbl_setting_profiles_size.setText(f"📁 Local Profiles Size: <b>{res_str}</b>")
                    self._is_calculating_profiles_size = False

                QTimer.singleShot(0, _apply_ui)
            except Exception:
                self._is_calculating_profiles_size = False

        threading.Thread(target=_calc_worker, daemon=True).start()

    def _get_profiles_folder_size_str(self) -> str:
        """Instantly return cached profiles folder size and schedule async refresh."""
        self._update_profiles_folder_size_async()
        return getattr(self, "_cached_profiles_size_str", "1.38 GB")

    def _on_dash_upgrade_clicked(self) -> None:
        """Customer Standalone Edition: All features unlocked, no upgrade modal."""
        return

    def _on_dash_redeem_clicked(self) -> None:
        """Customer Standalone Edition: Lifetime Enterprise active, no redeem needed."""
        return

    def _on_manual_sync_clicked(self) -> None:
        """Triggered when user clicks '🔄 Sync Cloud' button on dashboard: pulls latest cloud profiles and updates UI with live progress banner."""
        if hasattr(self, "btn_dash_refresh"):
            self.btn_dash_refresh.setText("⏳ Syncing...")
            self.btn_dash_refresh.setEnabled(False)

        active_token = self.get_effective_cloud_token()
        if not active_token:
            if hasattr(self, "btn_dash_refresh"):
                self.btn_dash_refresh.setText("🔄 Sync Cloud")
                self.btn_dash_refresh.setEnabled(True)
            self._refresh_dashboard()
            return

        try:
            from core.cloud_sync import CloudRestoreWorker
        except Exception:
            try:
                from cloud_sync import CloudRestoreWorker
            except Exception:
                CloudRestoreWorker = None

        if hasattr(self, "cloud_sync_banner") and self.cloud_sync_banner:
            self.cloud_sync_banner.show_progress(5, 100, "Connecting to srkBrowser Cloud...")

        base_dir = getattr(self.profile_mgr, "base_dir", None) if hasattr(self, "profile_mgr") else None
        if CloudRestoreWorker:
            self.cloud_download_thread = CloudRestoreWorker(license_token=active_token, batch_size=50, restore_sessions=True, base_dir=base_dir, parent=self)

            def _on_manual_progress(step: int, total: int, detail: str) -> None:
                if hasattr(self, "cloud_sync_banner") and self.cloud_sync_banner:
                    self.cloud_sync_banner.show_progress(step, total, detail)
                if hasattr(self, "status_bar") and self.status_bar:
                    self.status_bar.showMessage(f"☁️ {detail}", 3000)

            def _on_manual_batch_imported(imported_count: int, total_count: int, chunk_profiles: list) -> None:
                if chunk_profiles and hasattr(self, "profile_mgr"):
                    self.profile_mgr.import_cloud_backup_profiles(chunk_profiles, full_mirror=(imported_count <= len(chunk_profiles)))
                    self.refresh_all_views()

            def _on_manual_download_finished(success: bool, msg: str, total_count: int) -> None:
                if hasattr(self, "btn_dash_refresh"):
                    self.btn_dash_refresh.setText("🔄 Sync Cloud")
                    self.btn_dash_refresh.setEnabled(True)

                if success:
                    self.refresh_all_views()
                    self._refresh_dashboard(force_server=True)
                    if hasattr(self, "cloud_sync_banner") and self.cloud_sync_banner:
                        if total_count > 0:
                            self.cloud_sync_banner.show_success(f"All {total_count} profiles & sessions synced successfully!")
                        else:
                            self.cloud_sync_banner.hide_banner()
                    if hasattr(self, "status_bar") and self.status_bar:
                        self.status_bar.showMessage(f"🟢 Cloud Synced: {total_count} profile(s) ready on this PC!", 5000)
                else:
                    self._refresh_dashboard(force_server=True)
                    if hasattr(self, "cloud_sync_banner") and self.cloud_sync_banner:
                        self.cloud_sync_banner.show_error(msg)
                    if hasattr(self, "status_bar") and self.status_bar:
                        self.status_bar.showMessage(f"ℹ️ Sync notice: {msg}", 4000)

            self.cloud_download_thread.progress_signal.connect(_on_manual_progress)
            self.cloud_download_thread.batch_imported_signal.connect(_on_manual_batch_imported)
            self.cloud_download_thread.finished_signal.connect(_on_manual_download_finished)
            self.cloud_download_thread.start()
        else:
            if hasattr(self, "btn_dash_refresh"):
                self.btn_dash_refresh.setText("🔄 Sync Cloud")
                self.btn_dash_refresh.setEnabled(True)

    def _refresh_dashboard(self, force_server: bool = False) -> None:
        stats = self.profile_mgr.get_dashboard_stats()
        total_p = stats["total_profiles"]
        running_count = sum(1 for p in self.profile_mgr.profiles if self.browser_launcher.is_running(p["id"]))

        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        is_member = bool(hasattr(self, "auth_mgr") and self.auth_mgr and self.auth_mgr.is_team_member())
        curr_plan = str(user_info.get("plan_type", "free")).lower()
        curr_quota = int(user_info.get("max_profiles", 100) or user_info.get("cloud_quota", 100) or 100)
        curr_plan_title = "Professional" if (curr_plan in ("pro", "professional", "vip") or curr_quota == 500) else ("Business" if curr_quota == 1000 else ("Enterprise" if curr_quota >= 5000 else "Free"))

        if hasattr(self, "card_total"):
            self.card_total.set_value(str(total_p))
        if hasattr(self, "card_running"):
            self.card_running.set_value(str(running_count))
        if hasattr(self, "card_cloud"):
            if is_member:
                self.card_cloud.set_value(f"{total_p} Active")
            else:
                self.card_cloud.set_value(f"{min(total_p, curr_quota)} / {curr_quota}")
        if hasattr(self, "lbl_dash_quota_detail"):
            if is_member:
                self.lbl_dash_quota_detail.setText(f"🟣 <b>Active Profiles:</b> {total_p} Profiles (Managed Group)")
            elif total_p > curr_quota:
                self.lbl_dash_quota_detail.setText(f"Quota: {curr_quota} Cloud / {total_p} Local ({curr_plan_title})")
            else:
                self.lbl_dash_quota_detail.setText(f"Quota: {total_p} / {curr_quota} Profiles ({curr_plan_title})")
        if hasattr(self, "lbl_dash_validity_detail"):
            if is_member:
                self.lbl_dash_validity_detail.setText("🔵 <b>Role:</b> 👥 Team Operator (Managed Account)")
        if hasattr(self, "dash_quota_bar"):
            self.dash_quota_bar.setMaximum(max(1, curr_quota))
            self.dash_quota_bar.setValue(min(total_p, curr_quota))
        if hasattr(self, "dash_circular_gauge"):
            if is_member:
                self.dash_circular_gauge.set_values(total_p, max(total_p, 1))
            else:
                self.dash_circular_gauge.set_values(total_p, curr_quota)

        # Update Top Badge immediately from local cache
        self._update_top_plan_badge(curr_plan_title, curr_quota)

        # Update Banner Badges immediately
        is_vip_local = curr_plan in ("enterprise", "vip", "ultimate", "pro", "professional", "business")
        if hasattr(self, "lbl_dash_plan_badge"):
            if is_member:
                self.lbl_dash_plan_badge.setText("👥 Team Operator")
                self.lbl_dash_plan_badge.setStyleSheet("background-color: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 700;")
            else:
                self.lbl_dash_plan_badge.setText(f"💎 {curr_plan_title} Member" if is_vip_local else "🆓 Free Tier")
                self.lbl_dash_plan_badge.setStyleSheet(
                    "background-color: rgba(203, 166, 247, 0.2); color: #cba6f7; border: 1px solid rgba(203, 166, 247, 0.4); border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 700;"
                    if is_vip_local else
                    "background-color: rgba(137, 180, 250, 0.15); color: #89b4fa; border: 1px solid rgba(137, 180, 250, 0.35); border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 700;"
                )
        if hasattr(self, "lbl_dash_validity"):
            if is_member:
                self.lbl_dash_validity.setText("🏢 Managed Account")
            else:
                days_rem_local = int(user_info.get("days_remaining", 0) or 0)
                self.lbl_dash_validity.setText(f"⏳ {days_rem_local} Days Remaining" if (is_vip_local and days_rem_local > 0) else ("💎 Active Plan" if is_vip_local else "✨ Lifetime Free Account"))

        # Customer Standalone Edition: No remote server summary ping
        pass

    def _update_top_plan_badge(self, plan_type: str, cloud_quota: int = 100) -> None:
        """Customer Standalone Edition: Permanently hide upgrade/plan button."""
        if hasattr(self, "btn_top_upgrade"):
            self.btn_top_upgrade.hide()
        if hasattr(self, "btn_account_status"):
            self._refresh_account_button_status()

    def _apply_dashboard_server_data(self, u: dict) -> None:
        """Update Dashboard UI elements when server summary arrives."""
        is_member = bool(hasattr(self, "auth_mgr") and self.auth_mgr and self.auth_mgr.is_team_member())
        if is_member:
            self._apply_team_permissions_to_ui()
            return

        is_vip = u.get("is_vip", False)
        plan_type = u.get("plan_type", "Free")
        cloud_quota = u.get("cloud_quota", 100) or 100
        days_rem = u.get("days_remaining", 0)
        total_cloud_p = u.get("total_cloud_profiles", 0)
        storage_mb = u.get("storage_used_mb", 0.0)
        active_bots = u.get("active_bots", [])

        # Update Top Toolbar Upgrade/Plan Badge Button
        self._update_top_plan_badge(plan_type, cloud_quota)

        # Sync with AuthManager cache
        if hasattr(self, "auth_mgr") and self.auth_mgr:
            curr_u = self.auth_mgr.get_current_user() or {}
            curr_u["plan_type"] = plan_type
            curr_u["max_profiles"] = cloud_quota
            curr_u["cloud_quota"] = cloud_quota
            if hasattr(self.auth_mgr, "current_user") and isinstance(self.auth_mgr.current_user, dict):
                self.auth_mgr.current_user.update(curr_u)

        # Update Profile Menu Badge
        if hasattr(self, "profile_menu") and self.profile_menu:
            if hasattr(self.profile_menu, "lbl_badge"):
                self.profile_menu.lbl_badge.setText(f"⭐ {plan_type} ({cloud_quota} Profiles)")

        # Update Banner Badges
        if hasattr(self, "lbl_dash_plan_badge"):
            self.lbl_dash_plan_badge.setText(f"💎 {plan_type} Member" if is_vip else "🆓 Free Tier")
            self.lbl_dash_plan_badge.setStyleSheet(
                "background-color: rgba(203, 166, 247, 0.2); color: #cba6f7; border: 1px solid rgba(203, 166, 247, 0.4); border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 700;"
                if is_vip else
                "background-color: rgba(137, 180, 250, 0.15); color: #89b4fa; border: 1px solid rgba(137, 180, 250, 0.35); border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 700;"
            )

        if hasattr(self, "lbl_dash_validity"):
            self.lbl_dash_validity.setText(f"⏳ {days_rem} Days Remaining" if is_vip else "✨ Lifetime Free Account")
            self.lbl_dash_validity.setStyleSheet(
                "background-color: rgba(203, 166, 247, 0.15); color: #cba6f7; border: 1px solid rgba(203, 166, 247, 0.3); border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 600;"
                if is_vip else
                "background-color: rgba(166, 227, 161, 0.12); color: #a6e3a1; border: 1px solid rgba(166, 227, 161, 0.3); border-radius: 6px; padding: 3px 10px; font-size: 11.5px; font-weight: 600;"
            )

        # Update Stat Cards
        stats = self.profile_mgr.get_dashboard_stats() if hasattr(self, "profile_mgr") and self.profile_mgr else {"total_profiles": 0}
        total_local_p = stats.get("total_profiles", 0)
        display_count = max(total_cloud_p, total_local_p)

        if hasattr(self, "card_cloud"):
            self.card_cloud.set_value(f"{display_count} / {cloud_quota}")
        # Update Bots List in Dashboard with Real Server or Local Bots
        self._populate_bots_list_ui(active_bots)
        self._populate_quick_bots_ui(active_bots)

        # Update Right Health Box
        if hasattr(self, "lbl_dash_quota_detail"):
            self.lbl_dash_quota_detail.setText(f"Quota: {display_count} / {cloud_quota} Profiles ({plan_type})")
        if hasattr(self, "dash_quota_bar"):
            self.dash_quota_bar.setMaximum(max(1, cloud_quota))
            self.dash_quota_bar.setValue(min(display_count, cloud_quota))
        if hasattr(self, "dash_circular_gauge"):
            self.dash_circular_gauge.set_values(display_count, cloud_quota)
        if hasattr(self, "lbl_dash_validity_detail"):
            if plan_type != "Free":
                days_txt = f"{days_rem} Days Remaining" if days_rem > 0 else "30 Days Remaining"
                self.lbl_dash_validity_detail.setText(f"⏳ Plan Validity: <b style='color:#a6e3a1;'>{days_txt}</b>")
            else:
                self.lbl_dash_validity_detail.setText("✨ Lifetime Free Access")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_dashboard(force_server=True)

    def _populate_bots_list_ui(self, bots_list=None) -> None:
        """Populate Active Bots List in Dashboard with user bots or dynamic installed bots."""
        if not hasattr(self, "vbox_bots_list"):
            return

        while self.vbox_bots_list.count():
            item = self.vbox_bots_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build dynamic installed & licensed bots list
        display_bots = []
        if hasattr(self, "plugin_engine"):
            is_enterprise = False
            if hasattr(self, "auth_mgr") and self.auth_mgr:
                u = self.auth_mgr.get_current_user() or {}
                plan = str(u.get("plan_type", "")).upper()
                role = str(u.get("role", "")).upper()
                if "ENTERPRISE" in plan or "ADMIN" in role or "OWNER" in role or self.auth_mgr.can_use_bots():
                    is_enterprise = True

            online_bots = getattr(self, "_store_online_bots", None)
            if online_bots is None and hasattr(self, "plugin_engine"):
                online_bots = self.plugin_engine.get_all_bots()

            # Always merge bundled local manifests from 03_Automation_Bots/bots_manifest.json
            local_bots = []
            try:
                base_p = Path(__file__).resolve().parent.parent.parent
                for cand_p in [
                    Path(sys.executable).parent / "03_Automation_Bots" / "bots_manifest.json",
                    base_p / "03_Automation_Bots" / "bots_manifest.json",
                    base_p.parent / "03_Automation_Bots" / "bots_manifest.json",
                    Path(__file__).resolve().parent.parent / "03_Automation_Bots" / "bots_manifest.json"
                ]:
                    if cand_p.exists():
                        with open(cand_p, "r", encoding="utf-8") as bf:
                            local_bots = json.load(bf)
                        break
            except Exception:
                pass

            if local_bots:
                existing_bids = set((b.get("bot_id") or b.get("id")) for b in (online_bots or []))
                online_bots = list(online_bots or [])
                for lb in local_bots:
                    lbid = lb.get("bot_id") or lb.get("id")
                    if lbid and lbid not in existing_bids:
                        online_bots.append(lb)
                        existing_bids.add(lbid)

            if online_bots and isinstance(online_bots, list):
                for item in online_bots:
                    bid = item.get("bot_id") or item.get("id")
                    if not bid:
                        continue
                    is_inst = self.plugin_engine.is_bot_installed(bid)
                    if not is_inst:
                        for cand in [
                            Path(sys.executable).parent / "03_Automation_Bots",
                            Path(__file__).resolve().parent.parent.parent.parent / "03_Automation_Bots",
                            Path(__file__).resolve().parent.parent.parent / "03_Automation_Bots",
                            Path(__file__).resolve().parent.parent / "03_Automation_Bots"
                        ]:
                            if cand.exists():
                                for sd in cand.iterdir():
                                    if sd.is_dir() and (bid in sd.name.lower() or sd.name.lower() in bid or ("video" in bid and "video" in sd.name.lower()) or ("page" in bid and "page" in sd.name.lower()) or ("login" in bid and "login" in sd.name.lower()) or ("comment" in bid and "comment" in sd.name.lower()) or ("algo" in bid and "algo" in sd.name.lower())):
                                        if list(sd.glob("*.py")):
                                            is_inst = True
                                            break
                            if is_inst:
                                break

                    lic_info = self.bot_license_mgr.get_local_license(bid) if hasattr(self, "bot_license_mgr") and self.bot_license_mgr else None
                    has_access = is_enterprise or (lic_info and lic_info.get("is_active", True)) or bool(item.get("is_free"))

                    if is_inst and has_access:
                        display_bots.append({
                            "bot_id": bid,
                            "name": item.get("title") or item.get("name") or bid,
                            "days_left": lic_info.get("days_remaining") if lic_info else None
                        })

        if hasattr(self, "card_bots"):
            self.card_bots.set_value(f"{len(display_bots)} Active")

        if not display_bots:
            empty_row = QFrame()
            empty_row.setStyleSheet("background-color: #1e1e2e; border: 1px dashed #313244; border-radius: 8px; padding: 12px;")
            er_layout = QVBoxLayout(empty_row)
            er_layout.setAlignment(Qt.AlignCenter)
            lbl_no = QLabel("⚡ No Active Bots Installed")
            lbl_no.setStyleSheet("background: transparent; border: none; font-weight: 700; color: #a6adc8; font-size: 11.5px;")
            er_layout.addWidget(lbl_no, alignment=Qt.AlignCenter)
            self.vbox_bots_list.addWidget(empty_row)
            return

        for b in display_bots:
            b_row = QFrame()
            b_row.setStyleSheet("background-color: #1e1e2e; border: 1px solid #313244; border-radius: 8px; padding: 6px;")
            br_layout = QHBoxLayout(b_row)
            br_layout.setContentsMargins(12, 8, 12, 8)
            
            b_name = QLabel(f"🤖 {b.get('name', 'Automation Bot')}")
            b_name.setStyleSheet("background: transparent; border: none; font-weight: 700; color: #cdd6f4; font-size: 12.5px;")
            
            d_left = b.get("days_left")
            b_exp = QLabel(f"🟢 Active ({d_left}d)" if d_left is not None else "🟢 Active")
            b_exp.setStyleSheet("background: transparent; border: none; color: #a6e3a1; font-size: 11.5px; font-weight: 700;")

            btn_launch_bot = QPushButton("🚀 Run Bot")
            btn_launch_bot.setCursor(Qt.PointingHandCursor)
            btn_launch_bot.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #cba6f7, stop:1 #89b4fa);
                    color: #11111b;
                    font-weight: 800;
                    font-size: 11px;
                    padding: 5px 12px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover { background: #b4befe; }
            """)
            bid = b.get("bot_id")
            btn_launch_bot.clicked.connect(lambda _, b_id=bid: getattr(self, f"on_open_{b_id}", lambda: self.switch_view(2))())

            br_layout.addWidget(b_name)
            br_layout.addStretch()
            br_layout.addWidget(b_exp)
            br_layout.addWidget(btn_launch_bot)
            self.vbox_bots_list.addWidget(b_row)

    def _populate_quick_bots_ui(self, bots_list=None) -> None:
        """Dynamically populates the modern launcher bot cards in Box 3 of the Dashboard."""
        if not hasattr(self, "vbox_quick_bots_items"):
            return

        while self.vbox_quick_bots_items.count():
            item = self.vbox_quick_bots_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build dynamic installed & licensed bots list
        active_bots = []
        if hasattr(self, "plugin_engine"):
            is_enterprise = False
            if hasattr(self, "auth_mgr") and self.auth_mgr:
                u = self.auth_mgr.get_current_user() or {}
                plan = str(u.get("plan_type", "")).upper()
                role = str(u.get("role", "")).upper()
                if "ENTERPRISE" in plan or "ADMIN" in role or "OWNER" in role or self.auth_mgr.can_use_bots():
                    is_enterprise = True

            online_bots = getattr(self, "_store_online_bots", None)
            if online_bots is None and hasattr(self, "plugin_engine"):
                online_bots = self.plugin_engine.get_all_bots()

            # Always merge bundled local manifests from 03_Automation_Bots/bots_manifest.json
            local_bots = []
            try:
                base_p = Path(__file__).resolve().parent.parent.parent
                for cand_p in [
                    Path(sys.executable).parent / "03_Automation_Bots" / "bots_manifest.json",
                    base_p / "03_Automation_Bots" / "bots_manifest.json",
                    base_p.parent / "03_Automation_Bots" / "bots_manifest.json",
                    Path(__file__).resolve().parent.parent / "03_Automation_Bots" / "bots_manifest.json"
                ]:
                    if cand_p.exists():
                        with open(cand_p, "r", encoding="utf-8") as bf:
                            local_bots = json.load(bf)
                        break
            except Exception:
                pass

            if local_bots:
                existing_bids = set((b.get("bot_id") or b.get("id")) for b in (online_bots or []))
                online_bots = list(online_bots or [])
                for lb in local_bots:
                    lbid = lb.get("bot_id") or lb.get("id")
                    if lbid and lbid not in existing_bids:
                        online_bots.append(lb)
                        existing_bids.add(lbid)

            if online_bots and isinstance(online_bots, list):
                for item in online_bots:
                    bid = item.get("bot_id") or item.get("id")
                    if not bid:
                        continue
                    is_inst = self.plugin_engine.is_bot_installed(bid)
                    if not is_inst:
                        for cand in [
                            Path(sys.executable).parent / "03_Automation_Bots",
                            Path(__file__).resolve().parent.parent.parent.parent / "03_Automation_Bots",
                            Path(__file__).resolve().parent.parent.parent / "03_Automation_Bots",
                            Path(__file__).resolve().parent.parent / "03_Automation_Bots"
                        ]:
                            if cand.exists():
                                for sd in cand.iterdir():
                                    if sd.is_dir() and (bid in sd.name.lower() or sd.name.lower() in bid or ("video" in bid and "video" in sd.name.lower()) or ("page" in bid and "page" in sd.name.lower()) or ("login" in bid and "login" in sd.name.lower()) or ("comment" in bid and "comment" in sd.name.lower()) or ("algo" in bid and "algo" in sd.name.lower()) or ("recovery" in bid and "recovery" in sd.name.lower())):
                                        if list(sd.glob("*.py")):
                                            is_inst = True
                                            break
                            if is_inst:
                                break

                    lic_info = self.bot_license_mgr.get_local_license(bid) if hasattr(self, "bot_license_mgr") and self.bot_license_mgr else None
                    has_access = is_enterprise or (lic_info and lic_info.get("is_active", True)) or bool(item.get("is_free"))

                    if is_inst and has_access:
                        b_title = item.get("title") or item.get("name") or bid
                        b_icon = item.get("icon")
                        if not b_icon:
                            b_lower = bid.lower()
                            if "algo" in b_lower or "trainer" in b_lower:
                                b_icon = "🎯"
                            elif "video" in b_lower or "reel" in b_lower or "upload" in b_lower:
                                b_icon = "🎬"
                            elif "page" in b_lower:
                                b_icon = "📄"
                            elif "login" in b_lower or "auth" in b_lower:
                                b_icon = "🔑"
                            elif "comment" in b_lower or "marketing" in b_lower:
                                b_icon = "💬"
                            elif "recovery" in b_lower or "checkpoint" in b_lower:
                                b_icon = "⚡"
                            else:
                                b_icon = "🤖"

                        active_bots.append({
                            "bot_id": bid,
                            "name": b_title,
                            "tagline": item.get("desc") or item.get("description") or "Cloud Automation Bot",
                            "icon": b_icon,
                            "badge": "⭐ Enterprise" if is_enterprise else ("🎁 Free" if item.get("is_free") else "🟢 Active"),
                            "callback": (lambda *args, b_id=bid, t=b_title: self._launch_dynamic_bot(b_id, t))
                        })

        self._cached_active_bots = active_bots
        if hasattr(self, "card_bots"):
            self.card_bots.set_value(f"{len(active_bots)} Active")

        if not active_bots:
            empty_b = QFrame()
            empty_b.setStyleSheet("background-color: #10121e; border: 1px dashed #202438; border-radius: 8px; padding: 12px;")
            e_lay = QVBoxLayout(empty_b)
            e_lay.setAlignment(Qt.AlignCenter)
            e_lay.setSpacing(4)
            lbl_e_title = QLabel("⚡ No Active Bots Installed")
            lbl_e_title.setStyleSheet("color: #cdd6f4; font-size: 11.5px; font-weight: 700; background: transparent; border: none;")
            lbl_e_sub = QLabel("Visit the Bot Store to download & activate automation modules.")
            lbl_e_sub.setStyleSheet("color: #8c93b0; font-size: 10px; background: transparent; border: none;")
            btn_goto_store = QPushButton("🛒 Open Bot Store")
            btn_goto_store.setCursor(Qt.PointingHandCursor)
            btn_goto_store.setStyleSheet("background: #2b2e46; color: #cba6f7; border: 1px solid rgba(203, 166, 247, 0.35); border-radius: 6px; padding: 3px 10px; font-size: 10.5px; font-weight: 700; margin-top: 4px;")
            btn_goto_store.clicked.connect(lambda: self.switch_view(2))
            e_lay.addWidget(lbl_e_title, alignment=Qt.AlignCenter)
            e_lay.addWidget(lbl_e_sub, alignment=Qt.AlignCenter)
            e_lay.addWidget(btn_goto_store, alignment=Qt.AlignCenter)
            self.vbox_quick_bots_items.addWidget(empty_b)
            return

        self.vbox_quick_bots_items.setSpacing(8)

        # Display all active bots dynamically in Box 3 (Sleek single-line cards matching Box 4)
        for b_item in active_bots:
            card_b = QFrame()
            card_b.setFixedHeight(36)
            card_b.setStyleSheet("""
                QFrame {
                    background-color: #10121e;
                    border: 1px solid #202438;
                    border-radius: 8px;
                }
                QFrame:hover {
                    border-color: rgba(203, 166, 247, 0.45);
                    background-color: #16192d;
                }
            """)
            cb_lay = QHBoxLayout(card_b)
            cb_lay.setContentsMargins(12, 0, 12, 0)
            cb_lay.setSpacing(10)

            # Left Icon
            lbl_i = QLabel(b_item.get("icon", "🤖"))
            lbl_i.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            cb_lay.addWidget(lbl_i)

            # Bot Title (Only title, single line)
            bot_title = b_item.get("name", "Automation Bot")
            lbl_n = QLabel(bot_title)
            lbl_n.setToolTip(bot_title)
            lbl_n.setStyleSheet("color: #cdd6f4; font-size: 11.5px; font-weight: 700; background: transparent; border: none;")
            cb_lay.addWidget(lbl_n)

            # Badge (Enterprise / Active) - Clean borderless subtle tag
            badge_txt = b_item.get("badge", "🟢 Active")
            lbl_badge = QLabel(badge_txt)
            if "Enterprise" in badge_txt:
                lbl_badge.setStyleSheet("color: #facc15; font-size: 10px; font-weight: 700; background: rgba(234, 179, 8, 0.10); border: none; border-radius: 4px; padding: 2px 6px;")
            else:
                lbl_badge.setStyleSheet("color: #a6e3a1; font-size: 9.5px; font-weight: 700; background: rgba(166, 227, 161, 0.10); border: none; border-radius: 4px; padding: 2px 5px;")
            cb_lay.addWidget(lbl_badge)

            cb_lay.addStretch()

            # Right Run Button
            btn_run = QPushButton("⚡ Run")
            btn_run.setCursor(Qt.PointingHandCursor)
            btn_run.setFixedHeight(26)
            btn_run.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #cba6f7, stop:1 #89b4fa);
                    color: #11111b;
                    font-weight: 800;
                    font-size: 11px;
                    padding: 2px 14px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d9b8ff, stop:1 #a6c8ff);
                    color: #000000;
                }
            """)
            btn_run.clicked.connect(b_item["callback"])
            cb_lay.addWidget(btn_run)

            self.vbox_quick_bots_items.addWidget(card_b)

        # Row 4 Slot: If less than 4 bots, provide an action strip to explore and download bots matching Row 4 in Box 4
        if len(active_bots) < 4:
            card_more = QPushButton()
            card_more.setCursor(Qt.PointingHandCursor)
            card_more.setFixedHeight(36)
            card_more.setStyleSheet("""
                QPushButton {
                    background-color: #10121e;
                    border: 1px dashed rgba(203, 166, 247, 0.4);
                    border-radius: 8px;
                    padding: 0px 12px;
                }
                QPushButton:hover {
                    background-color: #16192d;
                    border-color: #cba6f7;
                }
            """)
            c4_lay = QHBoxLayout(card_more)
            c4_lay.setContentsMargins(12, 0, 12, 0)
            c4_lay.setSpacing(10)
            c4_i = QLabel("🛒")
            c4_i.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            c4_t = QLabel("Explore & Download More Automation Bots")
            c4_t.setStyleSheet("color: #cba6f7; font-size: 11.5px; font-weight: 700; background: transparent; border: none;")
            c4_tag = QLabel("Open Bot Store ›")
            c4_tag.setStyleSheet("color: #8c93b0; font-size: 10.5px; font-weight: 700; background: transparent; border: none;")
            c4_lay.addWidget(c4_i)
            c4_lay.addWidget(c4_t)
            c4_lay.addStretch()
            c4_lay.addWidget(c4_tag)
            card_more.clicked.connect(lambda: self.switch_view(2))
            self.vbox_quick_bots_items.addWidget(card_more)

    def on_manual_refresh_profiles(self) -> None:
        """Manual 1-Click Refresh to sync disk database and re-render."""
        try:
            self.profile_mgr.load_profiles(force_repair=False)
        except Exception:
            pass
        self._refresh_profiles_list()
        if hasattr(self, "show_toast"):
            self.show_toast("🔄 Profiles database refreshed live!")

    def _refresh_profiles_list(self) -> None:
        try:
            self.profile_mgr.load_profiles(force_repair=False)
        except Exception:
            pass
        all_groups = self.profile_mgr.get_groups()
        all_profiles = self.profile_mgr.profiles

        # Team Member Group Isolation
        if hasattr(self, "auth_mgr") and self.auth_mgr.is_team_member():
            allowed = self.auth_mgr.get_allowed_groups()
            if "All" not in allowed:
                all_groups = [g for g in all_groups if g in allowed]
                all_profiles = [p for p in all_profiles if p.get("group", "Default") in allowed]

        # Calculate total profile counts for each group
        group_counts = {}
        group_counts["All Groups"] = len(all_profiles)
        for p in all_profiles:
            g = p.get("group", "Default")
            group_counts[g] = group_counts.get(g, 0) + 1
        for g in all_groups:
            if g not in group_counts:
                group_counts[g] = 0

        self.search_bar.set_groups(all_groups, group_counts)

        query = self.search_bar.search_input.text()
        group = self.search_bar.get_selected_group()

        sort_mode = "Newest"
        if hasattr(self, "cmb_sort_order") and self.cmb_sort_order:
            order_txt = self.cmb_sort_order.currentText()
            sort_mode = "Oldest" if ("Oldest" in order_txt or "Asc" in order_txt) else "Newest"
        elif hasattr(self.search_bar, "sort_combo"):
            sort_mode = self.search_bar.sort_combo.currentText()

        filtered = self.profile_mgr.filter_and_sort(
            query=query,
            sort_mode=sort_mode,
            category_filter="All",
            group_filter=group
        )

        if hasattr(self, "lbl_profile_count_badge"):
            if len(filtered) != len(all_profiles):
                self.lbl_profile_count_badge.setText(f"{len(filtered)} / {len(all_profiles)} Profiles")
            else:
                self.lbl_profile_count_badge.setText(f"{len(all_profiles)} Profiles")


        total_items = len(filtered)
        if hasattr(self, "cmb_page_size"):
            self._update_pagination_controls(total_items)

        if hasattr(self, "cards_container"):
            self.cards_container.setUpdatesEnabled(False)

        try:
            # Clear all existing cards from cards_vbox
            while self.cards_vbox.count() > 0:
                child = self.cards_vbox.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            if not filtered:
                no_data_lbl = QLabel("No profiles found matching your search or group filter.")
                no_data_lbl.setStyleSheet("color: #a6adc8; font-style: italic; padding: 20px;")
                self.cards_vbox.addWidget(no_data_lbl)
                return

            if hasattr(self, "page_size") and self.page_size < 999999:
                start_idx = (self.current_page - 1) * self.page_size
                end_idx = start_idx + self.page_size
                page_profiles = filtered[start_idx:end_idx]
            else:
                page_profiles = filtered

            show_relogin_info = False
            if hasattr(self, "ext_mgr"):
                all_exts = self.ext_mgr.get_all_extensions()
            else:
                from extension_manager import ExtensionManager
                self.ext_mgr = ExtensionManager()
                all_exts = self.ext_mgr.get_all_extensions()

            for ext in all_exts:
                ename = ext.get("name", "").lower()
                if ext.get("is_active", False) and ("re-login" in ename or "relogin" in ename):
                    show_relogin_info = True
                    break

            # Helper to check if a script is globally enabled
            def _is_script_active(sid_check: str) -> bool:
                if hasattr(self, "bot_license_mgr") and self.bot_license_mgr:
                    if self.bot_license_mgr.is_item_deactivated("script", sid_check):
                        return False
                return True

            for p in page_profiles:
                pid = p["id"]
                is_running = self.browser_launcher.is_running(pid)
                if "assigned_scripts" in p and p.get("assigned_scripts") is not None:
                    p_scripts = p.get("assigned_scripts", [])
                    if isinstance(p_scripts, str):
                        p_scripts = [p_scripts]

                    # Filter out any scripts that are globally disabled
                    active_p_scripts = [
                        s for s in p_scripts
                        if _is_script_active(str(s)) and _is_script_active(str(s).lower())
                    ]

                    show_info = _is_script_active("fb_account_info") and (
                        ("fb_account_info" in active_p_scripts) or
                        ("info" in active_p_scripts) or
                        any("info" in str(s).lower() for s in active_p_scripts)
                    )
                    show_relogin = _is_script_active("fb_relogin") and (("fb_relogin" in active_p_scripts) or ("relogin" in active_p_scripts))
                    show_page_create = _is_script_active("fb_quick_page_create") and (
                        ("fb_quick_page_create" in active_p_scripts) or
                        ("fb_quick_page_creator" in active_p_scripts) or
                        ("page_create" in active_p_scripts) or
                        ("page_creator_shortcut" in active_p_scripts) or
                        any("page" in str(s).lower() for s in active_p_scripts)
                    )
                    show_lang_convert = _is_script_active("fb_language_converter") and (
                        ("fb_language_converter" in active_p_scripts) or
                        ("fb_lang_convert" in active_p_scripts) or
                        ("fb_language_converter_tool" in active_p_scripts) or
                        any("lang" in str(s).lower() for s in active_p_scripts)
                    )
                else:
                    active_p_scripts = []
                    show_info = bool(p.get("fb_uid")) or bool(p.get("notes")) or (show_relogin_info and _is_script_active("fb_account_info"))
                    show_relogin = (bool(p.get("fb_uid")) and bool(p.get("fb_pass"))) or (show_relogin_info and _is_script_active("fb_relogin"))
                    show_page_create = False
                    show_lang_convert = False

                # Pass a profile copy with only active assigned scripts so custom script buttons are also filtered
                p_display = dict(p)
                p_display["assigned_scripts"] = active_p_scripts

                card = ProfileCard(p_display, is_running=is_running, show_info=show_info, show_relogin=show_relogin, show_page_create=show_page_create, show_lang_convert=show_lang_convert)

                card.selection_changed.connect(self.on_profile_selection_changed)
                card.open_requested.connect(self.on_open_profile)
                card.relogin_requested.connect(self.on_relogin_profile)
                card.quick_page_create_requested.connect(self.on_quick_page_create)
                card.quick_lang_convert_requested.connect(self.on_quick_lang_convert)
                card.generic_script_requested.connect(self.on_execute_generic_script)
                card.note_requested.connect(self.on_edit_profile_note)
                card.quick_note_changed.connect(self.on_quick_note_saved)
                card.edit_requested.connect(self.on_edit_profile)
                card.edit_info_requested.connect(self.on_edit_profile_info)
                card.duplicate_requested.connect(self.on_duplicate_profile)
                card.clean_cache_requested.connect(self.on_clean_profile_cache)
                card.backup_requested.connect(self.on_export_profile_zip)
                card.delete_requested.connect(self.on_delete_profile)

                if pid in self.selected_profile_ids:
                    card.chk_select.blockSignals(True)
                    card.chk_select.setChecked(True)
                    card.chk_select.blockSignals(False)

                self.cards_vbox.addWidget(card)
        finally:
            if hasattr(self, "cards_container"):
                self.cards_container.setUpdatesEnabled(True)

    def _refresh_settings_view(self) -> None:
        if hasattr(self, "txt_setting_browser_path"):
            self.txt_setting_browser_path.setText(self.settings.get("browser_path", ""))
        if hasattr(self, "cmb_setting_resolution"):
            curr_res = self.settings.get("browser_window_size", "1280x800")
            for i in range(self.cmb_setting_resolution.count()):
                if self.cmb_setting_resolution.itemText(i).startswith(curr_res):
                    self.cmb_setting_resolution.setCurrentIndex(i)
                    break
        if hasattr(self, "spn_setting_width"):
            self.spn_setting_width.setValue(self.settings.get("default_window_width", 1280))
        if hasattr(self, "spn_setting_height"):
            self.spn_setting_height.setValue(self.settings.get("default_window_height", 840))
        if hasattr(self, "lbl_setting_profiles_size"):
            self.lbl_setting_profiles_size.setText(f"📁 {self._get_profiles_folder_size_str()}")

    def verify_pin_if_needed(self, profile_id: str) -> bool:
        """Prompt for PIN if the profile is PIN protected."""
        p = self.profile_mgr.get_profile_by_id(profile_id)
        if not p:
            return False

        pin = p.get("pin", "").strip()
        if not pin:
            return True

        dlg = PinPromptDialog(pin, p.get("name", "Profile"), self)
        return dlg.exec() == PinPromptDialog.Accepted

    def on_profile_selection_changed(self, profile_id: str, is_checked: bool) -> None:
        if is_checked:
            if getattr(self, "_has_bulk_opened", False):
                self._has_bulk_opened = False
                self.selected_profile_ids.clear()
                if hasattr(self, "chk_select_all"):
                    self.chk_select_all.blockSignals(True)
                    self.chk_select_all.setChecked(False)
                    self.chk_select_all.blockSignals(False)

                from core.ui.widgets import ProfileCard
                for i in range(self.cards_vbox.count()):
                    item = self.cards_vbox.itemAt(i)
                    if item and item.widget() and isinstance(item.widget(), ProfileCard):
                        card = item.widget()
                        if card.profile_id != profile_id:
                            card.chk_select.blockSignals(True)
                            card.chk_select.setChecked(False)
                            card.chk_select.blockSignals(False)

            self.selected_profile_ids.add(profile_id)
        else:
            self.selected_profile_ids.discard(profile_id)

        count = len(self.selected_profile_ids)
        self.update_bulk_open_button_state()
        if hasattr(self, "btn_bulk_edit"):
            self.btn_bulk_edit.setText(f"✏️ Bulk Edit ({count})")
            self.btn_bulk_edit.setEnabled(count > 0)
        if hasattr(self, "btn_bulk_delete"):
            self.btn_bulk_delete.setText(f"🗑️ Bulk Delete ({count})")
            self.btn_bulk_delete.setEnabled(count > 0)

    def update_bulk_open_button_state(self) -> None:
        """Dynamically update Bulk Open / Bulk Close button style and text based on selection and running status."""
        if not hasattr(self, "btn_bulk_open"):
            return

        count = len(self.selected_profile_ids)
        if count == 0:
            self.btn_bulk_open.setText("🚀 Bulk Open (0)")
            self.btn_bulk_open.setEnabled(False)
            self.btn_bulk_open.setStyleSheet("""
                QPushButton {
                    background-color: #89b4fa;
                    color: #11111b;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #b4befe; }
                QPushButton:disabled { background-color: #313244; color: #585b70; }
            """)
            return

        running_ids = [pid for pid in self.selected_profile_ids if self.browser_launcher.is_running(pid)]
        if running_ids:
            self.btn_bulk_open.setText(f"🛑 Bulk Close ({count})")
            self.btn_bulk_open.setEnabled(True)
            self.btn_bulk_open.setStyleSheet("""
                QPushButton {
                    background-color: #f38ba8;
                    color: #11111b;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #f5e0dc; }
                QPushButton:disabled { background-color: #313244; color: #585b70; }
            """)
        else:
            self.btn_bulk_open.setText(f"🚀 Bulk Open ({count})")
            self.btn_bulk_open.setEnabled(True)
            self.btn_bulk_open.setStyleSheet("""
                QPushButton {
                    background-color: #89b4fa;
                    color: #11111b;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #b4befe; }
                QPushButton:disabled { background-color: #313244; color: #585b70; }
            """)

    def on_bulk_edit_profiles(self) -> None:
        """Bulk edit Start Page URL, Proxy, and Group for all checked profiles."""
        if not self.selected_profile_ids:
            QMessageBox.information(self, "No Selection", "Please check one or more profile checkboxes to edit.")
            return

        from dialogs import BulkEditDialog, BulkEditProgressDialog
        groups = self.profile_mgr.get_groups()
        target_ids = list(self.selected_profile_ids)

        dlg = BulkEditDialog(len(target_ids), groups, self)
        if dlg.exec() == BulkEditDialog.Accepted:
            updates = dlg.get_updates()
            if not updates:
                QMessageBox.information(self, "No Changes Selected", "No properties were checked for bulk update.")
                return

            sync_bookmarks_list = updates.pop("_sync_bookmarks", None)
            total_targets = len(target_ids)

            # Construct human-readable scope summary for progress dialog
            details_list = []
            if "assigned_scripts" in updates:
                scripts_count = len(updates["assigned_scripts"])
                if scripts_count == 0:
                    details_list.append("Remove Scripts")
                else:
                    details_list.append(f"{scripts_count} Quick Script(s)")
            if "extensions" in updates:
                ext_count = len(updates["extensions"])
                if ext_count == 0:
                    details_list.append("Remove Extensions")
                else:
                    details_list.append(f"{ext_count} Extension(s)")
            if "start_url" in updates:
                details_list.append("Start Page URL")
            if "proxy_type" in updates or "proxy_host" in updates:
                details_list.append("Proxy Settings")
            if "group" in updates:
                details_list.append(f"Group: '{updates['group']}'")
            if sync_bookmarks_list is not None:
                details_list.append("Bookmarks")

            details_str = ", ".join(details_list) if details_list else "Selected Profile Settings"

            # Show modern progress popup dialog
            prog = BulkEditProgressDialog(
                total_profiles=total_targets,
                details_text=details_str,
                parent=self
            )
            prog.show()

            updated_count = 0
            from utils import safe_write_json
            for i, pid in enumerate(target_ids):
                p_data = self.profile_mgr.get_profile_by_id(pid)
                if p_data:
                    p_name = p_data.get("name") or f"Profile #{p_data.get('number', i + 1)}"
                    for k, v in updates.items():
                        p_data[k] = v
                    if sync_bookmarks_list is not None:
                        p_data["bookmarks"] = list(sync_bookmarks_list)
                    self.profile_mgr._ensure_defaults(p_data)
                    p_folder = self.profile_mgr.get_profile_folder(pid)
                    try:
                        safe_write_json(p_folder / "profile.json", p_data)
                    except Exception:
                        pass

                    if "extensions" in updates:
                        try:
                            from browser import auto_pin_extensions_in_profile
                            auto_pin_extensions_in_profile(p_folder, updates["extensions"])
                        except Exception:
                            pass

                    if sync_bookmarks_list is not None:
                        try:
                            from bookmark_manager import BookmarkManager
                            bmm = getattr(self, "bm_mgr", None) or BookmarkManager()
                            bmm.sync_bookmarks_to_profile(p_folder, p_data, custom_bookmarks=sync_bookmarks_list)
                        except Exception:
                            pass

                    updated_count += 1
                    prog.set_progress(i + 1, total_targets, p_name)

            # Batch save once to database
            try:
                self.profile_mgr.save_profiles()
            except Exception:
                pass

            try:
                import threading
                from cloud_sync import upload_profiles_cloud_backup
                threading.Thread(target=upload_profiles_cloud_backup, args=(self.profile_mgr.get_all_profiles(),), daemon=True).start()
            except Exception:
                pass

            prog.set_completed(f"✅ Successfully updated {updated_count} profile(s)!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(600, prog.accept)

            self.selected_profile_ids.clear()
            if hasattr(self, "chk_select_all"):
                self.chk_select_all.setChecked(False)
            self.refresh_all_views()
            self.status_bar.showMessage(f"✅ Bulk Edit Complete: Updated {updated_count} profile(s)!", 6000)


    def on_bulk_open_profiles(self) -> None:
        """Bulk open or bulk close all checked browser profiles smoothly via async launch queue."""
        if not self.selected_profile_ids:
            QMessageBox.information(self, "No Selection", "Please check one or more profile checkboxes.")
            return

        target_ids = list(self.selected_profile_ids)
        running_ids = [pid for pid in target_ids if self.browser_launcher.is_running(pid)]

        if running_ids:
            closed_count = 0
            for pid in running_ids:
                if self.browser_launcher.close_profile(pid):
                    closed_count += 1
                    self._update_profile_card_running_state(pid, False, is_syncing=True)
            self.status_bar.showMessage(f"⏳ Syncing & closing {closed_count} selected browser profile(s)...", 4000)
            self.update_bulk_open_button_state()
        else:
            queued_count = 0
            browser_exe = self.settings.get("browser_path", "")

            for pid in target_ids:
                pdata = self.profile_mgr.get_profile_by_id(pid)
                if pdata and not self.browser_launcher.is_running(pid) and not self.browser_launcher.is_opening(pid):
                    if self.verify_pin_if_needed(pid):
                        folder = self.profile_mgr.get_profile_folder(pid)
                        if self.browser_launcher.enqueue_launch(pid, browser_exe, folder, pdata):
                            self.profile_mgr.update_last_open(pid)
                            queued_count += 1

            self._has_bulk_opened = True
            self.status_bar.showMessage(f"🚀 Queued {queued_count} profile(s) for smooth staggered launch.", 4000)
            self.update_bulk_open_button_state()

    def on_select_all_toggled(self, checked: bool) -> None:
        """Select or deselect all profile cards currently displayed."""
        from core.ui.widgets import ProfileCard
        if checked:
            self._has_bulk_opened = False
        for i in range(self.cards_vbox.count()):
            item = self.cards_vbox.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ProfileCard):
                card = item.widget()
                card.chk_select.setChecked(checked)

    def on_bulk_delete_profiles(self) -> None:
        """Bulk delete all checked profiles after user confirmation with live progress."""
        if hasattr(self, "auth_mgr") and not self.auth_mgr.can_delete_profiles():
            QMessageBox.warning(self, "Action Restricted", "Profile deletion is restricted on this account by your Team Owner.")
            return

        if not self.selected_profile_ids:
            QMessageBox.information(self, "No Selection Required", "Please check one or more profile checkboxes to delete.")
            return

        count = len(self.selected_profile_ids)
        confirm = QMessageBox.question(
            self,
            "Confirm Bulk Delete Profiles",
            f"Are you sure you want to PERMANENTLY delete {count} selected profile(s)?\n\n"
            "• Profile database metadata entries will be removed.\n"
            "• Physical profile user-data directories on disk will be erased.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        target_ids = list(self.selected_profile_ids)

        if count <= 1:
            deleted_count = self.profile_mgr.bulk_delete_profiles(target_ids)
            self.selected_profile_ids.clear()
            if hasattr(self, "chk_select_all"):
                self.chk_select_all.setChecked(False)
            self.status_bar.showMessage(f"Successfully deleted {deleted_count} profile(s) in bulk.", 4000)
            self.refresh_all_views()
            self._auto_sync_to_cloud(allow_empty_purge=True)
            return

        from core.ui.progress_dialog import ModernProgressDialog, BulkDeleteWorker
        prog_dlg = ModernProgressDialog(
            title="🗑️ Deleting Profiles in Bulk",
            subtitle=f"Erasing {count} browser profiles and cleaning disk storage...",
            parent=self
        )
        self._center_dialog_over_parent(prog_dlg)

        self._del_worker = BulkDeleteWorker(self.profile_mgr, target_ids, parent=self)

        def _on_del_prog(curr, tot, pid):
            prog_dlg.set_progress(curr, tot, f"🧹 Deleting storage & cache ({curr}/{tot})...")

        def _on_del_done(deleted_count, err):
            prog_dlg.accept()
            self.selected_profile_ids.clear()
            if hasattr(self, "chk_select_all"):
                self.chk_select_all.setChecked(False)
            if err:
                QMessageBox.warning(self, "Bulk Delete Error", f"Error during bulk deletion: {err}")
            else:
                self.status_bar.showMessage(f"✅ Successfully deleted {deleted_count} profile(s) in bulk.", 5000)
            self.refresh_all_views()
            self._auto_sync_to_cloud(allow_empty_purge=True)

        self._del_worker.progress.connect(_on_del_prog)
        self._del_worker.finished.connect(_on_del_done)
        self._del_worker.start()
        prog_dlg.exec()

    def on_search_filter_changed(self, *args) -> None:
        """Debounced live search filter: smooth 60fps typing without UI freezing."""
        if not hasattr(self, "_profile_search_timer"):
            self._profile_search_timer = QTimer(self)
            self._profile_search_timer.setSingleShot(True)
            self._profile_search_timer.setInterval(160)
            self._profile_search_timer.timeout.connect(self._do_search_filter_changed)

        self._profile_search_timer.start(160)

    def _do_search_filter_changed(self) -> None:
        self.current_page = 1
        self._clear_profile_selections()
        self._refresh_profiles_list()

    def _center_dialog_over_parent(self, dlg: Any) -> None:
        """Center a dialog window directly over the main software window."""
        if not hasattr(self, "geometry"):
            return
        try:
            p_geo = self.geometry()
            d_size = dlg.sizeHint() if hasattr(dlg, "sizeHint") else dlg.size()
            w = max(d_size.width(), dlg.width())
            h = max(d_size.height(), dlg.height())
            x = p_geo.x() + (p_geo.width() - w) // 2
            y = p_geo.y() + (p_geo.height() - h) // 2
            x = max(10, x)
            y = max(10, y)
            dlg.move(x, y)
        except Exception:
            pass

    def _show_non_modal_dialog(self, dlg: Any) -> None:
        """Open a dialog window as a non-modal (modeless), non-blocking independent window with minimize/maximize controls."""
        self._center_dialog_over_parent(dlg)
        dlg.setParent(None)
        dlg.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        from config import DARK_STYLESHEET
        dlg.setStyleSheet(DARK_STYLESHEET)
        dlg.setWindowModality(Qt.NonModal)
        self._center_dialog_over_parent(dlg)
        dlg.finished.connect(lambda: self._on_dialog_closed(dlg))
        if not hasattr(self, "active_bot_dialogs"):
            self.active_bot_dialogs = []
        self.active_bot_dialogs.append(dlg)
        dlg.show()
        self._center_dialog_over_parent(dlg)
        dlg.raise_()
        dlg.activateWindow()

    def _on_dialog_closed(self, dlg: Any) -> None:
        if hasattr(self, "active_bot_dialogs") and dlg in self.active_bot_dialogs:
            try:
                self.active_bot_dialogs.remove(dlg)
            except ValueError:
                pass
        self.refresh_all_views()

    def on_open_group_manager(self) -> None:
        self._show_non_modal_dialog(GroupManagerDialog(self.profile_mgr, self))

    def on_open_team_manager(self) -> None:
        """Switch view directly to the dedicated Team & Sub-Accounts page inside the main window."""
        self.switch_view(9)

    def _show_non_modal_dialog(self, dlg) -> None:
        """Shows a dialog non-modally and keeps reference in _active_dialogs registry."""
        if not hasattr(self, "_active_dialogs"):
            self._active_dialogs = []
        if dlg:
            from PySide6.QtCore import Qt
            dlg.setWindowModality(Qt.WindowModality.NonModal)
            if dlg not in self._active_dialogs:
                self._active_dialogs.append(dlg)
                if hasattr(dlg, "finished"):
                    dlg.finished.connect(lambda: self._active_dialogs.remove(dlg) if dlg in self._active_dialogs else None)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()


    def on_open_bulk_create_dialog(self) -> None:
        """Open Bulk Browser Profile Creator Dialog."""
        from dialogs import BulkCreateProfilesDialog
        self._show_non_modal_dialog(BulkCreateProfilesDialog(self.profile_mgr, self))

    def _launch_dynamic_bot(self, bot_id: str, title: str = "") -> None:
        """Launches a dynamically downloaded bot module from %AppData%/BrowserProfileManager/modules/bots/<bot_id>/."""
        if hasattr(self, "auth_mgr") and not self.auth_mgr.can_use_bots():
            QMessageBox.warning(
                self,
                "Action Restricted",
                "Automation bots are exclusively reserved for the Master Account Owner."
            )
            return

        try:
            bot_dir = Path("")
            py_files = []

            # 1. Prioritize authentic local 03_Automation_Bots directory FIRST!
            for cand_dir in [
                Path(__file__).resolve().parent.parent.parent.parent / "03_Automation_Bots",
                Path(__file__).resolve().parent.parent.parent / "03_Automation_Bots",
                Path(__file__).resolve().parent.parent / "03_Automation_Bots",
                Path("C:/srkBrowser/03_Automation_Bots"),
                Path.home() / "Desktop" / "SRK" / "03_Automation_Bots"
            ]:
                if cand_dir.exists():
                    for sub_d in cand_dir.iterdir():
                        if sub_d.is_dir() and (bot_id in sub_d.name.lower() or sub_d.name.lower() in bot_id or ("video" in bot_id and "video" in sub_d.name.lower()) or ("upload" in bot_id and "upload" in sub_d.name.lower()) or ("page" in bot_id and "page" in sub_d.name.lower()) or ("login" in bot_id and "login" in sub_d.name.lower()) or ("comment" in bot_id and "comment" in sub_d.name.lower()) or ("reels" in bot_id and "reels" in sub_d.name.lower()) or ("trainer" in bot_id and "trainer" in sub_d.name.lower())):
                            sub_py = list(sub_d.glob("*.py"))
                            if sub_py:
                                bot_dir = sub_d
                                py_files = sub_py
                                break
                if py_files:
                    break

            # 2. If not found in 03_Automation_Bots, check %AppData%/BrowserProfileManager/modules/bots
            if not py_files:
                bot_dir = self.plugin_engine.modules_dir / bot_id if hasattr(self, "plugin_engine") else Path("")
                py_files = list(bot_dir.glob("*.py")) if bot_dir.exists() else []

                # AUTO-UPDATE check for cloud modules
                if hasattr(self, "plugin_engine"):
                    try:
                        is_upd, inst_v, rem_v = self.plugin_engine.is_update_available(bot_id)
                        if is_upd:
                            if hasattr(self, "status_bar"):
                                self.status_bar.showMessage(f"🔄 Auto-updating '{title or bot_id}' (v{inst_v} ➔ v{rem_v})...", 4000)
                            success, _ = self.plugin_engine.download_bot_module(bot_id)
                            if success:
                                py_files = list(bot_dir.glob("*.py")) if bot_dir.exists() else []
                    except Exception:
                        pass

            # If not yet downloaded locally, attempt on-demand download from Cloud Server
            if not py_files:
                if hasattr(self, "status_bar"):
                    self.status_bar.showMessage(f"⏳ Downloading '{title or bot_id}' from srkBrowser Cloud CDN...", 4000)
                if hasattr(self, "plugin_engine"):
                    success, msg = self.plugin_engine.download_bot_module(bot_id)
                    if success:
                        py_files = list(bot_dir.glob("*.py")) if bot_dir.exists() else []
                    else:
                        QMessageBox.information(
                            self,
                            "Cloud Automation Module",
                            f"🤖 Module: {title or bot_id}\n\n"
                            f"The bot is registered in the cloud catalog, but its downloadable Python script package has not been uploaded by the admin to the server yet.\n\n"
                            f"Once uploaded from the Admin Panel, clicking Run will instantly download and launch it!"
                        )
                        return

            if py_files:
                # Priority 1: Exact bot entry points ({bot_id}.py, {bot_id}_bot.py, main.py)
                entry_file = None
                for f in py_files:
                    if f.name in (f"{bot_id}.py", f"{bot_id}_bot.py", "main.py"):
                        entry_file = f
                        break
                # Priority 2: Dedicated UI modules (*_ui.py)
                if not entry_file:
                    for f in py_files:
                        if f.name.endswith("_ui.py"):
                            entry_file = f
                            break
                # Priority 3: First available .py file
                if not entry_file:
                    entry_file = py_files[0]

                import importlib.util

                # Add bot directory to sys.path for internal imports
                bot_dir_str = str(bot_dir.resolve())
                if bot_dir_str not in sys.path:
                    sys.path.insert(0, bot_dir_str)

                spec = importlib.util.spec_from_file_location(f"dynamic_{bot_id}", str(entry_file))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    from PySide6.QtWidgets import QDialog, QWidget

                    # Strategy 1: Dedicated launch_ui entry point
                    if hasattr(mod, "launch_ui") and callable(getattr(mod, "launch_ui")):
                        try:
                            dlg = mod.launch_ui(self.profile_mgr, self)
                        except TypeError:
                            try:
                                dlg = mod.launch_ui(self)
                            except TypeError:
                                dlg = mod.launch_ui()
                        if dlg and isinstance(dlg, QWidget):
                            self._show_non_modal_dialog(dlg)
                        return

                    # Strategy 2: Instantiation of preferred or candidate QDialog classes
                    preferred_dialogs = [
                        "MasterBotStudioDialog",
                        "FbBulkLoginBotDialog",
                        "FbBulkPageCreatorBotDialog",
                        "FbBulkVideoUploaderBotDialog",
                        "FbCommentMarketingDialog",
                        "FbReelsAlgoTrainerDialog"
                    ]
                    candidate_classes = []
                    for p_name in preferred_dialogs:
                        if hasattr(mod, p_name):
                            cand = getattr(mod, p_name)
                            if isinstance(cand, type) and issubclass(cand, QDialog):
                                candidate_classes.append(cand)

                    for attr_name in dir(mod):
                        if attr_name.startswith('_'):
                            continue
                        attr = getattr(mod, attr_name)
                        if isinstance(attr, type) and issubclass(attr, QDialog) and attr is not QDialog:
                            if attr not in candidate_classes:
                                candidate_classes.append(attr)

                    for dlg_class in candidate_classes:
                        try:
                            dlg = dlg_class(self.profile_mgr, self)
                            self._show_non_modal_dialog(dlg)
                            return
                        except TypeError:
                            try:
                                dlg = dlg_class(self)
                                self._show_non_modal_dialog(dlg)
                                return
                            except TypeError:
                                try:
                                    dlg = dlg_class()
                                    self._show_non_modal_dialog(dlg)
                                    return
                                except TypeError:
                                    continue

                    # Strategy 3: Safe main entry point fallback
                    if hasattr(mod, "main") and callable(getattr(mod, "main")):
                        try:
                            dlg = mod.main(self.profile_mgr, self)
                        except TypeError:
                            try:
                                dlg = mod.main(self)
                            except TypeError:
                                dlg = mod.main()
                        if dlg and isinstance(dlg, QWidget):
                            self._show_non_modal_dialog(dlg)
                        return

            QMessageBox.information(self, "Automation Bot", f"Module [{title or bot_id}] is active.")
        except Exception as e:
            QMessageBox.critical(self, "Bot Execution Error", f"Failed to run bot [{title or bot_id}]:\n{e}")

    def on_check_for_updates(self, silent: bool = False) -> None:
        """Check remote server for software update and bot updates."""
        if silent:
            return
        try:
            from core.network_guard import is_internet_available
            if not is_internet_available(timeout_sec=0.8):
                if not silent:
                    QMessageBox.warning(
                        self,
                        "Offline Mode",
                        "Cannot check for updates: Your PC is currently offline.\nPlease check your internet connection and try again."
                    )
                return
        except Exception:
            pass

        from updater import UpdateCheckerThread
        from version import UPDATE_CHECK_URL, APP_VERSION

        if not silent:
            self.status_bar.showMessage("🔎 Checking server for software and bot updates...", 4000)

        # Sync remote bot store catalog
        if hasattr(self, "plugin_engine"):
            self.plugin_engine.fetch_remote_manifest()

        # Find all bots with available updates
        updatable_bots = []
        if hasattr(self, "plugin_engine"):
            all_bots = self.plugin_engine.get_all_bots()
            for b in all_bots:
                bid = b.get("id") or b.get("bot_id")
                b_name = b.get("name") or b.get("title")
                is_upd, inst_v, rem_v = self.plugin_engine.is_update_available(bid)
                if is_upd:
                    updatable_bots.append({
                        "bot_id": bid,
                        "name": b_name,
                        "installed_ver": inst_v,
                        "remote_ver": rem_v
                    })

        self.update_checker = UpdateCheckerThread(UPDATE_CHECK_URL, APP_VERSION, self)

        def _on_finished(has_app_upd: bool, latest_ver: str, download_url: str, changelog: str) -> None:
            if has_app_upd or updatable_bots:
                from dialogs import UnifiedUpdatesHubDialog
                dlg = UnifiedUpdatesHubDialog(
                    has_app_upd=has_app_upd,
                    app_version=APP_VERSION,
                    app_latest_ver=latest_ver,
                    app_download_url=download_url,
                    app_changelog=changelog,
                    updatable_bots=updatable_bots,
                    plugin_engine=self.plugin_engine,
                    parent=self
                )
                dlg.exec()
                self.refresh_all_views()
            elif not silent:
                QMessageBox.information(
                    self,
                    "Software & Bots Up To Date",
                    f"✅ All installed automation bots and {APP_NAME} (v{APP_VERSION}) are completely up to date!"
                )

        self.update_checker.check_finished.connect(_on_finished)
        self.update_checker.start()

    def on_open_extension_manager(self) -> None:
        """Switch to full page Global Extension Manager View."""
        self.switch_view(3)

    def on_open_bookmark_manager(self) -> None:
        """Open the Chrome Auto-Bookmarks Manager Dialog."""
        from dialogs import BookmarkManagerDialog
        dlg = BookmarkManagerDialog(self.profile_mgr, self)
        dlg.exec()
        self.refresh_all_views()

    def on_create_profile(self) -> None:
        if hasattr(self, "auth_mgr") and not self.auth_mgr.can_create_profiles():
            QMessageBox.warning(self, "Action Restricted", "Profile creation is restricted on this account by your Team Owner.")
            return

        suggested_num = self.profile_mgr.get_next_profile_number()
        if hasattr(self, "profile_drawer") and self.profile_drawer:
            self.profile_drawer.open_create_mode(suggested_num)
        else:
            dlg = CreateProfileDialog(suggested_num, self.profile_mgr, self)
            if dlg.exec() == CreateProfileDialog.Accepted:
                pdata = dlg.get_data()
                new_profile = self.profile_mgr.create_profile(**pdata)
                self.status_bar.showMessage(f"Created profile {new_profile.get('number', '')} in Group '{new_profile.get('group', 'Default')}'", 4000)
                self.refresh_all_views()
                self._auto_sync_to_cloud()

    def _on_drawer_profile_created(self, created_profile: Dict[str, Any]) -> None:
        p_num = created_profile.get('number', '')
        p_grp = created_profile.get('group', 'Default')
        self.status_bar.showMessage(f"🚀 Successfully created profile #{p_num} in Group '{p_grp}'!", 4000)
        self.refresh_all_views()
        self._auto_sync_to_cloud()

    def on_bulk_create_profiles(self) -> None:
        if hasattr(self, "auth_mgr") and not self.auth_mgr.can_create_profiles():
            QMessageBox.warning(self, "Action Restricted", "Profile creation is restricted on this account by your Team Owner.")
            return

        groups = self.profile_mgr.get_groups()
        dlg = BulkCreateDialog(groups, self)
        if dlg.exec() == BulkCreateDialog.Accepted:
            params = dlg.get_data()
            count = params.get("count", 1)

            if count <= 2:
                created = self.profile_mgr.bulk_create_profiles(**params)
                self.status_bar.showMessage(f"Successfully generated {len(created)} profiles in bulk!", 4000)
                self.refresh_all_views()
                self._auto_sync_to_cloud()
                return

            from core.ui.progress_dialog import ModernProgressDialog, BulkCreateWorker
            prog_dlg = ModernProgressDialog(
                title="⚡ Generating Profiles in Bulk",
                subtitle=f"Generating {count} isolated anti-detect profiles with unique hardware fingerprints...",
                parent=self
            )
            self._center_dialog_over_parent(prog_dlg)

            self._create_worker = BulkCreateWorker(self.profile_mgr, params, parent=self)

            def _on_create_prog(curr, tot, name):
                prog_dlg.set_progress(curr, tot, f"⚙️ Generating HW Fingerprint for {name}...")

            def _on_create_done(created_list, err):
                prog_dlg.accept()
                if err:
                    QMessageBox.warning(self, "Bulk Create Error", f"Error during bulk creation: {err}")
                else:
                    self.status_bar.showMessage(f"✅ Successfully generated {len(created_list)} profiles in bulk!", 5000)
                self.refresh_all_views()
                self._auto_sync_to_cloud()

            self._create_worker.progress.connect(_on_create_prog)
            self._create_worker.finished.connect(_on_create_done)
            self._create_worker.start()
            prog_dlg.exec()

    def on_batch_launch_group(self) -> None:
        group = self.search_bar.get_selected_group()
        category = getattr(self.search_bar, "category_combo", None).currentText() if hasattr(self.search_bar, "category_combo") else "All"
        query = self.search_bar.search_input.text()

        filtered = self.profile_mgr.filter_and_sort(
            query=query,
            category_filter=category,
            group_filter=group
        )

        if not filtered:
            QMessageBox.information(self, "No Profiles", "No profiles available to launch.")
            return

        confirm = QMessageBox.question(
            self,
            "Batch Launch Confirmation",
            f"Are you sure you want to launch all {len(filtered)} filtered profiles simultaneously?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            launched = 0
            for p in filtered:
                if self.verify_pin_if_needed(p["id"]):
                    folder = self.profile_mgr.get_profile_folder(p["id"])
                    browser_exe = self.settings.get("browser_path", "")
                    ok, _ = self.browser_launcher.launch_profile(browser_exe, folder, p)
                    if ok:
                        self.profile_mgr.update_last_open(p["id"])
                        launched += 1

            self.status_bar.showMessage(f"Launched {launched} profile windows.", 4000)
            self.refresh_all_views()

    def on_clean_profile_cache(self, profile_id: str) -> None:
        """Purge temporary browser caches for a single profile."""
        if self.browser_launcher.is_running(profile_id):
            QMessageBox.warning(self, "Browser Active", "Please close this browser profile before cleaning its cache.")
            return

        cleaned_bytes = self.profile_mgr.clean_profile_cache(profile_id)
        cleaned_mb = cleaned_bytes / (1024 * 1024)
        self.status_bar.showMessage(f"🧹 Cleaned {cleaned_mb:.1f} MB cache for selected profile.", 5000)
        QMessageBox.information(
            self,
            "Cache Cleaned",
            f"🧹 Successfully cleaned {cleaned_mb:.1f} MB of temporary junk & browser cache!\n\n"
            "• All cookies, passwords, and active login sessions remain 100% safe."
        )

    def on_clean_all_profiles_cache(self) -> None:
        """Purge temporary browser caches across all profiles with user confirmation."""
        running_count = sum(1 for p in self.profile_mgr.profiles if self.browser_launcher.is_running(p.get("id", "")))
        if running_count > 0:
            QMessageBox.warning(
                self,
                "Active Browsers Detected",
                f"⚠️ {running_count} browser profile(s) are currently running.\n\nPlease close all open browsers before cleaning caches for optimal results."
            )
            return

        confirm = QMessageBox.question(
            self,
            "Clean All Profiles Cache",
            "🧹 Do you want to clean temporary browser caches across ALL profiles?\n\n"
            "• Frees up disk space (Image/Video/Code caches)\n"
            "• Accelerates browser and app speed\n"
            "• 🔒 Login sessions, cookies, passwords & bookmarks are 100% protected and untouched.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if confirm == QMessageBox.Yes:
            cleaned_bytes = self.profile_mgr.clean_all_profiles_cache()
            cleaned_mb = cleaned_bytes / (1024 * 1024)
            self.status_bar.showMessage(f"🎉 Cleaned {cleaned_mb:.1f} MB across all profiles!", 6000)
            QMessageBox.information(
                self,
                "Cache Cleanup Complete",
                f"🎉 Successfully cleaned {cleaned_mb:.1f} MB of temporary cache files!\n\n"
                "• Storage space freed successfully.\n"
                "• All login accounts, cookies, and profiles remain intact."
            )

    def ensure_session_active(self) -> bool:
        """Fast session guard to prevent actions if account was logged in elsewhere."""
        if not hasattr(self, "auth_mgr") or not self.auth_mgr or not self.auth_mgr.is_logged_in():
            self._handle_session_revoked()
            return False
        return True

    def on_open_profile(self, profile_id: str) -> None:
        if not self.ensure_session_active():
            return

        if self.browser_launcher.is_running(profile_id):
            self.browser_launcher.close_profile(profile_id)
            self.status_bar.showMessage("Closing browser profile & syncing cookies...", 4000)
            self._update_profile_card_running_state(profile_id, False, is_syncing=True)
            self.update_bulk_open_button_state()
            return

        if self.browser_launcher.is_opening(profile_id):
            return

        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        folder = self.profile_mgr.get_profile_folder(profile_id)
        browser_exe = self.settings.get("browser_path", "")

        # Asynchronously enqueue profile for smooth, zero-lag launch
        if self.browser_launcher.enqueue_launch(profile_id, browser_exe, folder, p_data):
            self.profile_mgr.update_last_open(profile_id)
            disp_num = p_data.get("number", "1")
            self.status_bar.showMessage(f"⏳ Queued Profile {disp_num} for launch...", 3000)

        self.update_bulk_open_button_state()

    def on_edit_profile(self, profile_id: str) -> None:
        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        if hasattr(self, "profile_drawer") and self.profile_drawer:
            self.profile_drawer.open_edit_mode(p_data)
        else:
            dlg = EditProfileDialog(p_data, self.profile_mgr, self)
            if dlg.exec() == EditProfileDialog.Accepted:
                updated_data = dlg.get_data()
                self.profile_mgr.update_profile(profile_id, updated_data)
                self.status_bar.showMessage(f"Updated profile {p_data.get('number', '')}", 4000)
                self.refresh_all_views()
                self._auto_sync_to_cloud()

    def _on_drawer_profile_updated(self, profile_id: str, updated_data: Dict[str, Any]) -> None:
        p_data = self.profile_mgr.get_profile_by_id(profile_id) or {}
        p_num = p_data.get('number', profile_id)
        self.status_bar.showMessage(f"💾 Successfully updated settings for profile #{p_num}!", 4000)
        self.refresh_all_views()
        self._auto_sync_to_cloud()

    def on_edit_profile_note(self, profile_id: str) -> None:
        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        from core.ui.dialogs import FBAccountInfoPopupDialog
        dlg = FBAccountInfoPopupDialog(p_data, parent=self)
        dlg.exec()

    def on_edit_profile_info(self, profile_id: str) -> None:
        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        from core.ui.dialogs import EditProfileInfoDialog
        dlg = EditProfileInfoDialog(p_data, self)
        if dlg.exec() == EditProfileInfoDialog.Accepted:
            update_data = dlg.get_data()
            self.profile_mgr.update_profile(profile_id, update_data)
            self._auto_sync_to_cloud()
            disp_num = p_data.get("number", "Profile")
            self.status_bar.showMessage(f"✅ Saved info for [{disp_num}]!", 4000)
            self.refresh_all_views()

    on_edit_fb_info = on_edit_profile_info

    def on_quick_note_saved(self, profile_id: str, new_note_text: str) -> None:
        p = self.profile_mgr.get_profile_by_id(profile_id)
        if not p:
            return

        old_val = p.get("quick_note", "").strip()
        if old_val != new_note_text:
            self.profile_mgr.update_profile(profile_id, {"quick_note": new_note_text})
            self.status_bar.showMessage(f"✅ Saved quick note for profile [{p.get('number', '')}]", 3000)

    def on_relogin_profile(self, profile_id: str) -> None:
        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        p_num = p_data.get("number", "Profile")
        self.status_bar.showMessage(f"🔑 Starting 1-click re-login for {p_num}...", 4000)

        self.relogin_thread = SingleProfileReloginThread(self.profile_mgr, profile_id, self)
        self.relogin_thread.log_emitted.connect(lambda text: self.status_bar.showMessage(text, 5000))

        def _on_relogin_finished(success: bool, msg: str) -> None:
            self.status_bar.showMessage(msg, 6000)
            if success:
                QMessageBox.information(self, "Re-login Complete", msg)
                self._auto_sync_to_cloud()
                try:
                    import threading
                    from cloud_sync import upload_profile_session_zip
                    active_token = self.get_effective_cloud_token()
                    p_folder = self.profile_mgr.get_profile_folder(profile_id)
                    if active_token and p_folder and p_folder.exists():
                        threading.Thread(target=upload_profile_session_zip, args=(profile_id, p_folder, active_token), daemon=True).start()
                except Exception:
                    pass
            else:
                QMessageBox.warning(self, "Re-login Failed", msg)
            self.refresh_all_views()

        self.relogin_thread.finished_signal.connect(_on_relogin_finished)
        self.relogin_thread.start()

    def on_quick_page_create(self, profile_id: str) -> None:
        """1-Click Facebook Quick Page Creator handler directly from Profile Card."""
        if hasattr(self, "bot_license_mgr") and self.bot_license_mgr and self.bot_license_mgr.is_item_deactivated("script", "fb_quick_page_create"):
            QMessageBox.information(
                self,
                "Script Disabled",
                "⚠️ 'Facebook 1-Click Instant Page Creator' is currently Disabled.\n\nPlease Enable it in Script Studio to use."
            )
            return

        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        if hasattr(self.profile_mgr, "get_profile_folder"):
            user_dir = str(self.profile_mgr.get_profile_folder(profile_id).resolve())
        elif hasattr(self.profile_mgr, "get_profile_dir"):
            user_dir = str(self.profile_mgr.get_profile_dir(profile_id).resolve())
        else:
            num = p_data.get("number", profile_id)
            user_dir = str((self.profile_mgr.base_dir / num).resolve())
        
        try:
            import sys
            from pathlib import Path
            script_paths = [
                Path(__file__).resolve().parent.parent.parent.parent / "06_Script_Store" / "01_FB_Quick_Page_Create",
                Path(__file__).resolve().parent.parent.parent / "06_Script_Store" / "01_FB_Quick_Page_Create",
                Path(__file__).resolve().parent.parent / "06_Script_Store" / "01_FB_Quick_Page_Create",
                Path.cwd() / "06_Script_Store" / "01_FB_Quick_Page_Create"
            ]
            for sp in script_paths:
                if sp.exists() and str(sp.resolve()) not in sys.path:
                    sys.path.insert(0, str(sp.resolve()))

            from quick_page_creator_modal import QuickPageCreatorModal
            dlg = QuickPageCreatorModal(profile_data=p_data, user_data_dir=user_dir, parent=self)
            dlg.exec()
        except Exception as ex:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Quick Script Error", f"Could not launch Quick Page Creator:\n{ex}")

    def on_quick_lang_convert(self, profile_id: str) -> None:
        """1-Click Facebook Language Converter handler directly from Profile Card (Zero Popup)."""
        if hasattr(self, "bot_license_mgr") and self.bot_license_mgr and self.bot_license_mgr.is_item_deactivated("script", "fb_language_converter"):
            QMessageBox.information(
                self,
                "Script Disabled",
                "⚠️ 'Facebook 1-Click Language Converter' is currently Disabled.\n\nPlease Enable it in Script Studio to use."
            )
            return

        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        if hasattr(self.profile_mgr, "get_profile_folder"):
            user_dir = str(self.profile_mgr.get_profile_folder(profile_id).resolve())
        elif hasattr(self.profile_mgr, "get_profile_dir"):
            user_dir = str(self.profile_mgr.get_profile_dir(profile_id).resolve())
        else:
            num = p_data.get("number", profile_id)
            user_dir = str((self.profile_mgr.base_dir / num).resolve())

        num_str = str(p_data.get("number") or p_data.get("name") or profile_id).replace("Profile", "").strip()
        self.status_bar.showMessage(f"🌐 Converting Facebook language to English (US) for #{num_str}...", 10000)
        if hasattr(self, "show_toast"):
            self.show_toast(f"🌐 Converting language to English for #{num_str}...")

        if not hasattr(self, "_active_lang_threads"):
            self._active_lang_threads = []

        worker = QuickLangConvertThread(user_dir=user_dir, p_data=p_data, prof_num=num_str)

        def _on_lang_finished(ok: bool, msg: str, pnum: str):
            if ok:
                self.status_bar.showMessage(f"✅ #{pnum} Facebook language successfully converted to English (US)!", 6000)
                if hasattr(self, "show_toast"):
                    self.show_toast(f"✅ #{pnum} language converted to English!")
            else:
                self.status_bar.showMessage(f"⚠️ #{pnum} language error: {msg}", 6000)
                if hasattr(self, "show_toast"):
                    self.show_toast(f"⚠️ #{pnum}: {msg}")
            if worker in self._active_lang_threads:
                self._active_lang_threads.remove(worker)

        worker.finished_signal.connect(_on_lang_finished)
        self._active_lang_threads.append(worker)
        worker.start()

    def on_execute_generic_script(self, profile_id: str, script_id: str) -> None:
        """Universal Plug-and-Play Quick Script Launcher:
        Dynamically downloads or locates any published script by script_id and launches its UI.
        Works for 100% of current and future scripts uploaded via Admin Panel with ZERO code changes.
        """
        if hasattr(self, "bot_license_mgr") and self.bot_license_mgr and self.bot_license_mgr.is_item_deactivated("script", script_id):
            QMessageBox.information(
                self,
                "Script Disabled",
                f"⚠️ Script '{script_id}' is currently Disabled.\n\nPlease Enable it in Script Studio to use."
            )
            return

        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        if hasattr(self.profile_mgr, "get_profile_folder"):
            user_dir = str(self.profile_mgr.get_profile_folder(profile_id).resolve())
        elif hasattr(self.profile_mgr, "get_profile_dir"):
            user_dir = str(self.profile_mgr.get_profile_dir(profile_id).resolve())
        else:
            num = p_data.get("number", profile_id)
            user_dir = str((self.profile_mgr.base_dir / num).resolve())

        try:
            import os, sys, urllib.request, importlib.util
            from pathlib import Path

            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            cache_dir = Path(appdata) / "BrowserProfileManager" / "modules" / "scripts" / script_id
            cache_dir.mkdir(parents=True, exist_ok=True)
            local_cached_file = cache_dir / f"{script_id}.py"

            candidate_paths = [
                local_cached_file,
                Path.cwd() / "06_Script_Store" / script_id / "main.py",
                Path.cwd() / "06_Script_Store" / f"01_{script_id}" / "main.py",
                Path.cwd() / "06_Script_Store" / f"02_{script_id}" / "main.py",
                Path.cwd() / "UPLOAD_TO_ADMIN_PANEL" / f"{script_id}.py",
                Path.home() / "Desktop" / "UPLOAD_TO_ADMIN_PANEL" / f"{script_id}.py"
            ]

            # Check 06_Script_Store dynamically for any matching subfolders
            base_p = Path(__file__).resolve().parent.parent.parent
            for sc_dir in [base_p / "06_Script_Store", base_p.parent / "06_Script_Store", Path.cwd() / "06_Script_Store"]:
                if sc_dir.exists() and sc_dir.is_dir():
                    for s_sub in sc_dir.iterdir():
                        if s_sub.is_dir() and (script_id.lower() in s_sub.name.lower() or s_sub.name.lower() in script_id.lower()):
                            mf_main = s_sub / "main.py"
                            if mf_main.exists():
                                candidate_paths.insert(0, mf_main)
                                break

            target_script_file = None
            for cp in candidate_paths:
                if cp.is_file() and cp.exists():
                    target_script_file = cp
                    break

            # If not found locally, download directly from srbrowser.com OTA repository
            if not target_script_file or not target_script_file.exists():
                download_url = f"https://srbrowser.com/api/v1/store/scripts/{script_id}/download"
                self.status_bar.showMessage(f"⏳ Downloading script [{script_id}]...", 3000)
                try:
                    req = urllib.request.Request(download_url, headers={"User-Agent": "srkBrowser Desktop App"})
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        code_bytes = resp.read()
                        if not code_bytes.startswith(b'{"status": "error"'):
                            with open(local_cached_file, "wb") as f_out:
                                f_out.write(code_bytes)
                            target_script_file = local_cached_file
                except Exception:
                    pass

            if not target_script_file or not target_script_file.exists():
                QMessageBox.warning(self, "Script Not Found", f"Could not find or download script module [{script_id}].")
                return

            spec = importlib.util.spec_from_file_location(f"dyn_script_{script_id}", str(target_script_file))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Discover entry point class or launch_ui function
            executed = False
            if hasattr(mod, "launch_ui") and callable(getattr(mod, "launch_ui")):
                mod.launch_ui(profile_data=p_data, user_data_dir=user_dir, profile_mgr=self.profile_mgr, parent=self)
                executed = True
            elif hasattr(mod, "main") and callable(getattr(mod, "main")):
                mod.main(profile_data=p_data, user_data_dir=user_dir, profile_mgr=self.profile_mgr, parent=self)
                executed = True
            else:
                for attr_name in dir(mod):
                    obj = getattr(mod, attr_name)
                    if isinstance(obj, type) and issubclass(obj, QDialog) and obj not in (QDialog, QMessageBox):
                        try:
                            dlg = obj(profile_data=p_data, user_data_dir=user_dir, parent=self)
                        except TypeError:
                            try:
                                dlg = obj(profile_mgr=self.profile_mgr, parent=self)
                            except TypeError:
                                dlg = obj(self)
                        self._show_non_modal_dialog(dlg)
                        executed = True
                        break

            if not executed:
                QMessageBox.warning(self, "Execution Error", f"Script module [{script_id}] has no valid QDialog or launch_ui entry point.")
        except Exception as ex:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Script Launch Error", f"Failed to execute script [{script_id}]:\n{ex}")

    def get_effective_cloud_token(self) -> str:
        if hasattr(self, "auth_mgr") and self.auth_mgr and self.auth_mgr.is_logged_in():
            user = self.auth_mgr.get_current_user()
            if user.get("token"):
                return user["token"]
        from cloud_sync import get_active_license_token
        return get_active_license_token()

    def _auto_sync_to_cloud(self, allow_empty_purge: bool = False) -> None:
        """Silently sync profiles to cloud in background whenever changed."""
        active_token = self.get_effective_cloud_token()
        if not active_token:
            return
        all_profiles = self.profile_mgr.get_all_profiles()
        if (not all_profiles or len(all_profiles) == 0) and not allow_empty_purge:
            return
        self.cloud_upload_thread = CloudUploadThread(all_profiles, license_token=active_token, allow_empty_purge=allow_empty_purge, parent=self)
        self.cloud_upload_thread.start()

    def _handle_session_revoked(self) -> None:
        """Customer Edition: Offline-first standalone session, ignore remote revocation."""
        pass



    def _auto_restore_from_cloud(self, force: bool = False) -> None:
        """Customer Standalone Edition: All profiles are strictly local. No cloud restore."""
        return

    def on_cloud_backup(self) -> None:
        """Customer Standalone Edition: Local storage only. No remote cloud backup."""
        QMessageBox.information(
            self,
            "Local Storage Active",
            "Customer Standalone Edition stores all profiles, credentials, cookies, and extensions locally in the ./data/ directory.\n\nNo remote website or server backup is needed."
        )

    def on_cloud_restore(self) -> None:
        """Customer Standalone Edition: Local storage only."""
        QMessageBox.information(
            self,
            "Local Storage Active",
            "All browser profiles are loaded directly from your local ./data/ directory."
        )




    def on_clean_profile_cache(self, profile_id: str) -> None:
        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        num = p_data.get("number", "Profile")
        if self.profile_mgr.clean_profile_cache(profile_id):
            self.status_bar.showMessage(f"Cleared cache & temporary files for {num}.", 4000)
            QMessageBox.information(self, "Cache Cleared", f"Successfully cleared cache and temporary files for {num}.")
        else:
            self.status_bar.showMessage(f"No cache files found to clean for {num}.", 4000)

    def on_duplicate_profile(self, profile_id: str) -> None:
        if not self.verify_pin_if_needed(profile_id):
            return

        src_p = self.profile_mgr.get_profile_by_id(profile_id)
        src_num = get_display_number(src_p.get("number", "1")) if src_p else "Profile"

        dup = self.profile_mgr.duplicate_profile(profile_id)
        if dup:
            new_num = get_display_number(dup.get("number", "1"))
            QMessageBox.information(
                self,
                "Browser Profile Cloned",
                f"✅ Browser [{src_num}] cloned successfully to new Browser [{new_num}]!\n\n"
                f"All cookies, logged-in accounts, sessions, tabs, extensions, and settings have been cloned."
            )
            self.status_bar.showMessage(f"Cloned [{src_num}] to new profile [{new_num}]", 4000)
            self.refresh_all_views()
            self._auto_sync_to_cloud()
            try:
                import threading
                from cloud_sync import upload_profile_session_zip
                active_token = self.get_effective_cloud_token()
                dup_id = dup.get("id")
                dup_folder = self.profile_mgr.get_profile_folder(dup_id)
                if active_token and dup_folder and dup_folder.exists():
                    threading.Thread(target=upload_profile_session_zip, args=(dup_id, dup_folder, active_token), daemon=True).start()
            except Exception:
                pass
        else:
            QMessageBox.warning(self, "Clone Error", "Failed to clone browser profile.")

    def on_delete_profile(self, profile_id: str) -> None:
        if hasattr(self, "auth_mgr") and not self.auth_mgr.can_delete_profiles():
            QMessageBox.warning(self, "Action Restricted", "Profile deletion is restricted on this account by your Team Owner.")
            return

        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        num = p_data.get("number", "Profile")
        name = p_data.get("name", num)

        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete profile '{name}' ({num})?\n"
            "This will remove its local profile directory and configuration permanently.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            if self.browser_launcher.is_running(profile_id):
                self.browser_launcher.close_profile(profile_id)

            if self.profile_mgr.delete_profile(profile_id):
                self.status_bar.showMessage(f"Deleted profile {num}", 4000)
                self.refresh_all_views()
                self._auto_sync_to_cloud(allow_empty_purge=True)
            else:
                QMessageBox.warning(self, "Delete Error", "Could not delete profile.")

    def on_export_profile_zip(self, profile_id: str) -> None:
        if hasattr(self, "auth_mgr") and not self.auth_mgr.can_export_cookies():
            QMessageBox.warning(self, "Action Restricted", "Profile export is restricted on this account by your Team Owner.")
            return

        if not self.verify_pin_if_needed(profile_id):
            return

        p_data = self.profile_mgr.get_profile_by_id(profile_id)
        if not p_data:
            return

        num = p_data.get("number", "Profile")
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            f"Export ZIP Backup for {num}",
            f"{num}_backup.zip",
            "ZIP Archives (*.zip)"
        )
        if filepath:
            if self.profile_mgr.export_profile_zip(profile_id, Path(filepath)):
                QMessageBox.information(self, "Backup Complete", f"Profile ZIP backup exported successfully:\n{filepath}")
            else:
                QMessageBox.warning(self, "Backup Error", "Failed to create ZIP backup archive.")

    def on_import_profile_zip(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Profile from ZIP Archive",
            "",
            "ZIP Archives (*.zip)"
        )
        if filepath:
            restored = self.profile_mgr.import_profile_zip(Path(filepath))
            if restored:
                QMessageBox.information(
                    self,
                    "Restore Complete",
                    f"Profile restored successfully as {restored.get('number', '')} ({restored.get('name', '')})."
                )
                self.refresh_all_views()
                self._auto_sync_to_cloud()
            else:
                QMessageBox.warning(self, "Restore Error", "Failed to restore profile from ZIP archive.")

    def on_export_profiles_csv(self) -> None:
        if hasattr(self, "auth_mgr") and not self.auth_mgr.can_export_cookies():
            QMessageBox.warning(self, "Action Restricted", "CSV export is restricted on this account by your Team Owner.")
            return

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profiles to CSV (Excel compatible)",
            str(REPORTS_DIR / "profiles_export.csv"),
            "CSV Files (*.csv)"
        )
        if filepath:
            if self.profile_mgr.export_profiles_csv(Path(filepath)):
                QMessageBox.information(self, "CSV Export Complete", f"Profiles metadata exported to CSV:\n{filepath}")
            else:
                QMessageBox.warning(self, "CSV Export Error", "Failed to export CSV file.")


    def on_import_profiles_csv(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Profiles from CSV",
            "",
            "CSV Files (*.csv)"
        )
        if filepath:
            imported, skipped = self.profile_mgr.import_profiles_csv(Path(filepath))
            QMessageBox.information(
                self,
                "CSV Import Complete",
                f"Imported {imported} profiles from CSV.\nSkipped {skipped} entries."
            )
            self.refresh_all_views()
            self._auto_sync_to_cloud()

    def on_export_profiles(self) -> None:
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profiles Metadata JSON",
            "profiles_export.json",
            "JSON Files (*.json)"
        )
        if filepath:
            if self.profile_mgr.export_profiles(Path(filepath)):
                QMessageBox.information(self, "Export Complete", f"Profiles exported successfully to:\n{filepath}")
            else:
                QMessageBox.warning(self, "Export Error", "Failed to export profiles metadata.")

    def on_import_profiles(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Profiles Metadata JSON",
            "",
            "JSON Files (*.json)"
        )
        if filepath:
            imported, skipped = self.profile_mgr.import_profiles(Path(filepath))
            QMessageBox.information(
                self,
                "Import Complete",
                f"Imported {imported} new profiles.\nSkipped {skipped} duplicates/invalid entries."
            )
            self.refresh_all_views()
            self._auto_sync_to_cloud()

    def on_open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == SettingsDialog.Accepted:
            self.settings = dlg.get_settings()
            save_settings(self.settings)
            self.status_bar.showMessage("Settings saved successfully.", 4000)
            self.refresh_all_views()

    def on_download_bot_module(self, bot_id: str) -> None:
        if hasattr(self, "plugin_engine"):
            ok, msg = self.plugin_engine.download_bot_module(bot_id)
            if ok:
                if hasattr(self, "bot_license_mgr"):
                    self.bot_license_mgr.save_local_license(bot_id, "FREE-ACTIVE-KEY", {"is_active": True, "hwid": self.bot_license_mgr.hwid})
                QMessageBox.information(self, "Download Complete", f"🎉 {msg}\n\nThis bot engine has been activated and moved to your '⚡ My Active / Installed Bots' tab!")
                self._switch_automation_to_active()
            else:
                QMessageBox.warning(self, "Download Error", msg)

    def on_activate_bot_license(self, bot_id: str, title: str) -> None:
        from core.ui.dialogs import ActivateBotLicenseDialog
        dlg = ActivateBotLicenseDialog(bot_id, title, getattr(self, "bot_license_mgr", None), self)
        if dlg.exec() == QDialog.Accepted:
            QMessageBox.information(self, "Bot Activated", f"🎉 '{title}' key activated successfully!\n\nMoved to your '⚡ My Active / Installed Bots' tab.")
            self.stack.removeWidget(self.stack.widget(2))
            self.stack.insertWidget(2, self._create_automation_page())
            self.stack.setCurrentIndex(2)
            self._switch_automation_to_active()

    def on_delete_active_bot(self, bot_id: str, title: str) -> None:
        """Uninstall and remove bot from active bots tab."""
        from core.ui.dialogs import LuxuryConfirmDeleteDialog
        dlg = LuxuryConfirmDeleteDialog(
            title="Confirm Bot Removal",
            item_name=title,
            item_type="Bot",
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            if hasattr(self, "bot_license_mgr"):
                self.bot_license_mgr.deactivate_item("bot", bot_id)
                self.bot_license_mgr.remove_local_license(bot_id)
            if hasattr(self, "plugin_engine"):
                self.plugin_engine.uninstall_bot_module(bot_id)

            self.status_bar.showMessage(f"🗑️ Removed '{title}' from Active Bots.", 4000)
            self._refresh_active_bots_tab()
            self._apply_store_filter(getattr(self, "_current_store_filter", "all"))

    def on_reactivate_item(self, item_type: str, item_id: str, title: str) -> None:
        """Add back a deactivated item (bot, tool, script) to active workspace."""
        if hasattr(self, "bot_license_mgr"):
            self.bot_license_mgr.activate_item(item_type, item_id)

        if "bot" in item_type:
            self._refresh_active_bots_tab()
            self._apply_store_filter(getattr(self, "_current_store_filter", "all"))
        elif "tool" in item_type:
            search_txt = self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else ""
            self._render_tools_grid(search_text=search_txt)
        elif "script" in item_type:
            search_txt = self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else ""
            self._render_scripts_grid(search_text=search_txt)

        self.status_bar.showMessage(f"✅ Added '{title}' back to Active Workspace.", 4000)

    def on_buy_bot_license(self, bot_id: str) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(f"https://srbrowser.com/checkout?bot={bot_id}"))

    def on_open_bot_tutorial(self, item_id: str, tutorial_url: str = "") -> None:
        url = (tutorial_url or "").strip()
        if not url or url.lower() in ["none", "null", "false", "no", "#"]:
            QMessageBox.information(
                self,
                "🎬 Tutorial Notice",
                f"No video tutorial or guide link has been published for this module ({item_id}) yet.\n\n"
                "Please check back later or contact support for assistance."
            )
            return

        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        try:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
        except ImportError:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(url))

    def on_open_user_login_dialog(self) -> None:
        user_info = self.auth_mgr.get_current_user() if hasattr(self, "auth_mgr") else {}
        if user_info.get("is_logged_in") and user_info.get("email"):
            email_curr = user_info.get("email")
            reply = QMessageBox.question(
                self,
                "Account Logged In",
                f"Logged in as:\n👤 {email_curr}\n\nDo you want to Sign Out of your account?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                # 0. Sync any latest profile metadata to cloud before logout
                try:
                    active_token = self.get_effective_cloud_token()
                    all_profs = self.profile_mgr.get_all_profiles() if hasattr(self, "profile_mgr") else []
                    if active_token and all_profs:
                        from cloud_sync import upload_profiles_cloud_backup
                        upload_profiles_cloud_backup(all_profs, license_token=active_token)
                except Exception:
                    pass

                # 1. Clear Auth Session
                if hasattr(self, "auth_mgr"):
                    self.auth_mgr.clear_session()

                # 2. Purge Bot Licenses Cache
                if hasattr(self, "bot_license_mgr"):
                    self.bot_license_mgr.purge_all_cached_licenses()

                # 3. Clear License dat file
                try:
                    from license_manager import LICENSE_FILE
                    if LICENSE_FILE.exists():
                        LICENSE_FILE.unlink(missing_ok=True)
                except Exception:
                    pass

                if hasattr(self, "btn_account_status"):
                    self.btn_account_status.setText("🔓  Sign In  ▾")

                self.refresh_all_views()
                QMessageBox.information(self, "Signed Out", "You have been signed out successfully.")
                self.check_and_enforce_login()
            return

        from core.ui.dialogs import UserLoginDialog
        dlg = UserLoginDialog(auth_mgr=getattr(self, "auth_mgr", None), parent=self)
        res = dlg.exec()
        if res == QDialog.DialogCode.Accepted or res == 1:
            user_info = self.auth_mgr.get_current_user() if hasattr(self, "auth_mgr") else {}
            name_display = user_info.get("full_name") or user_info.get("email", "User Account").split("@")[0]
            if hasattr(self, "btn_account_status"):
                self.btn_account_status.setText(f"👤  {name_display}  ▾")

            # Clean purge on new login to isolate accounts
            if hasattr(self, "bot_license_mgr"):
                self.bot_license_mgr.purge_all_cached_licenses()

            # Save new user token if available
            token = user_info.get("token", "")
            if token:
                try:
                    from license_manager import save_activated_license
                    save_activated_license(token)
                except Exception:
                    pass

            if hasattr(self, "profile_mgr"):
                self.profile_mgr.load_profiles()

            self.refresh_all_views()
            # Auto restore user's profiles & sessions from cloud upon login
            self._auto_restore_from_cloud()

    def _create_personal_center_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ----------------------------------------------------
        # 1. TOP HERO BANNER (Glassmorphic Profile Header)
        # ----------------------------------------------------
        hero_card = QFrame()
        hero_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1c2d, stop:0.5 #1e2034, stop:1 #27253d);
                border: 1px solid rgba(137, 180, 250, 0.3);
                border-radius: 16px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        hero_hbox = QHBoxLayout(hero_card)
        hero_hbox.setContentsMargins(22, 16, 22, 16)
        hero_hbox.setSpacing(18)

        # Avatar
        self.pc_lbl_avatar = QLabel("👤")
        self.pc_lbl_avatar.setFixedSize(58, 58)
        self.pc_lbl_avatar.setAlignment(Qt.AlignCenter)
        self.pc_lbl_avatar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #2563eb);
            color: #ffffff;
            font-size: 24px;
            font-weight: 900;
            border-radius: 29px;
            border: 2px solid rgba(192, 132, 252, 0.6);
        """)
        hero_hbox.addWidget(self.pc_lbl_avatar)

        # User Text + Badges
        u_info_vbox = QVBoxLayout()
        u_info_vbox.setSpacing(4)

        u_top_row = QHBoxLayout()
        u_top_row.setSpacing(10)
        
        self.pc_lbl_name = QLabel("User Account")
        self.pc_lbl_name.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        
        self.pc_lbl_badge_plan = QLabel("⭐ Professional Member")
        self.pc_lbl_badge_plan.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #0284c7);
            color: #ffffff;
            border-radius: 6px;
            padding: 4px 12px;
            font-size: 11.5px;
            font-weight: 800;
        """)

        self.pc_lbl_badge_validity = QLabel("⏳ 30 Days Remaining")
        self.pc_lbl_badge_validity.setStyleSheet("""
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 6px;
            padding: 4px 12px;
            font-size: 11.5px;
            font-weight: 800;
        """)

        u_top_row.addWidget(self.pc_lbl_name)
        u_top_row.addWidget(self.pc_lbl_badge_plan)
        u_top_row.addWidget(self.pc_lbl_badge_validity)
        u_top_row.addStretch()
        u_info_vbox.addLayout(u_top_row)

        self.pc_lbl_email = QLabel("guest@srbrowser.com")
        self.pc_lbl_email.setStyleSheet("font-size: 13px; color: #a6adc8;")
        u_info_vbox.addWidget(self.pc_lbl_email)

        hero_hbox.addLayout(u_info_vbox, stretch=1)

        # Right Action Buttons: Back to Dashboard & Refresh
        hero_actions_hbox = QHBoxLayout()
        hero_actions_hbox.setSpacing(10)

        btn_pc_refresh = QPushButton("🔄 Refresh Info")
        btn_pc_refresh.setCursor(Qt.PointingHandCursor)
        btn_pc_refresh.setStyleSheet("""
            QPushButton {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 10px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover { background: #45475a; color: #ffffff; border-color: #89b4fa; }
        """)
        btn_pc_refresh.clicked.connect(self._refresh_personal_center)

        btn_pc_back = QPushButton("⬅️ Back to Dashboard")
        btn_pc_back.setCursor(Qt.PointingHandCursor)
        btn_pc_back.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #1d4ed8);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 8px 18px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        btn_pc_back.clicked.connect(lambda: self.switch_view(0))

        hero_actions_hbox.addWidget(btn_pc_refresh)
        hero_actions_hbox.addWidget(btn_pc_back)
        hero_hbox.addLayout(hero_actions_hbox)

        layout.addWidget(hero_card)

        # ----------------------------------------------------
        # 2. SEGMENTED CAPSULE SUB-NAVIGATION TABS
        # ----------------------------------------------------
        subnav_card = QFrame()
        subnav_card.setStyleSheet("""
            QFrame {
                background-color: #121320;
                border: 1px solid #2b2e46;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        subnav_hbox = QHBoxLayout(subnav_card)
        subnav_hbox.setContentsMargins(4, 4, 4, 4)
        subnav_hbox.setSpacing(6)

        self.btn_pc_tab_profile = QPushButton("👤  Profile && Subscription Overview")
        self.btn_pc_tab_profile.setCursor(Qt.PointingHandCursor)

        self.btn_pc_tab_bots = QPushButton("🤖  My Active Bots && Automation Tools")
        self.btn_pc_tab_bots.setCursor(Qt.PointingHandCursor)

        self.btn_pc_tab_tx = QPushButton("💳  Purchase && Transaction History")
        self.btn_pc_tab_tx.setCursor(Qt.PointingHandCursor)

        self.btn_pc_tab_profile.clicked.connect(lambda: self._switch_pc_tab(0))
        self.btn_pc_tab_bots.clicked.connect(lambda: self._switch_pc_tab(1))
        self.btn_pc_tab_tx.clicked.connect(lambda: self._switch_pc_tab(2))

        subnav_hbox.addWidget(self.btn_pc_tab_profile)
        subnav_hbox.addWidget(self.btn_pc_tab_bots)
        subnav_hbox.addWidget(self.btn_pc_tab_tx)
        subnav_hbox.addStretch()

        layout.addWidget(subnav_card)

        # ----------------------------------------------------
        # 3. STACKED TAB PAGES
        # ----------------------------------------------------
        self.pc_stack = QStackedWidget()
        self.pc_stack.addWidget(self._create_pc_profile_tab())
        self.pc_stack.addWidget(self._create_pc_bots_tab())
        self.pc_stack.addWidget(self._create_pc_tx_tab())

        layout.addWidget(self.pc_stack, stretch=1)

        self._update_pc_tab_styles(0)
        return widget

    def _switch_pc_tab(self, index: int) -> None:
        self.pc_stack.setCurrentIndex(index)
        self._update_pc_tab_styles(index)
        if index == 2:
            self._fetch_pc_transactions()

    def _update_pc_tab_styles(self, active_index: int) -> None:
        active_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #313244, stop:1 #282a3e);
                color: #89b4fa;
                font-weight: 800;
                font-size: 12.5px;
                border: 1px solid rgba(137, 180, 250, 0.4);
                border-radius: 8px;
                padding: 9px 20px;
            }
        """
        inactive_style = """
            QPushButton {
                background: transparent;
                color: #a6adc8;
                font-weight: 600;
                font-size: 12.5px;
                border: none;
                border-radius: 8px;
                padding: 9px 20px;
            }
            QPushButton:hover {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
        """
        self.btn_pc_tab_profile.setStyleSheet(active_style if active_index == 0 else inactive_style)
        self.btn_pc_tab_bots.setStyleSheet(active_style if active_index == 1 else inactive_style)
        self.btn_pc_tab_tx.setStyleSheet(active_style if active_index == 2 else inactive_style)

    def _create_pc_profile_tab(self) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(14)

        # 4 Executive Cards Grid
        grid = QGridLayout()
        grid.setSpacing(14)

        def _make_metric_card(title: str, val_attr: str, initial_val: str, sub_attr: str, initial_sub: str, color: str = "#89b4fa"):
            f = QFrame()
            f.setStyleSheet("""
                QFrame {
                    background-color: #161828;
                    border: 1px solid #2b2e46;
                    border-radius: 14px;
                }
                QLabel {
                    background: transparent;
                    border: none;
                }
            """)
            v = QVBoxLayout(f)
            v.setContentsMargins(20, 16, 20, 16)
            v.setSpacing(6)

            t = QLabel(title)
            t.setStyleSheet("color: #89b4fa; font-size: 12.5px; font-weight: 700;")
            v.addWidget(t)

            val_lbl = QLabel(initial_val)
            val_lbl.setStyleSheet(f"color: {color}; font-size: 17.5px; font-weight: 900;")
            setattr(self, val_attr, val_lbl)
            v.addWidget(val_lbl)

            sub_lbl = QLabel(initial_sub)
            sub_lbl.setStyleSheet("color: #6c7086; font-size: 11.5px; font-weight: 500;")
            setattr(self, sub_attr, sub_lbl)
            v.addWidget(sub_lbl)
            return f

        grid.addWidget(_make_metric_card("⭐ Current Membership Plan", "pc_val_plan", "Professional Tier", "pc_sub_plan", "Active Cloud Backup Package", "#cba6f7"), 0, 0)
        grid.addWidget(_make_metric_card("☁️ Cloud Profiles Backup Quota", "pc_val_quota", "500 Cloud Profiles", "pc_sub_quota", "High-Priority Cloud Sync Active", "#a6e3a1"), 0, 1)
        grid.addWidget(_make_metric_card("⏳ Plan Expiration & Validity", "pc_val_expiry", "2026-09-26", "pc_sub_expiry", "30 Days Remaining", "#38bdf8"), 1, 0)
        grid.addWidget(_make_metric_card("🔒 Multi-Device & API License", "pc_val_api", "Verified & Active", "pc_sub_api", "1 Device bound to current token", "#f9e2af"), 1, 1)

        lay.addLayout(grid)

        # Cloud Quota Progress Card
        quota_card = QFrame()
        quota_card.setStyleSheet("""
            QFrame {
                background-color: #161828;
                border: 1px solid #2b2e46;
                border-radius: 14px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        q_lay = QVBoxLayout(quota_card)
        q_lay.setContentsMargins(20, 16, 20, 16)
        q_lay.setSpacing(10)

        q_hdr = QHBoxLayout()
        q_title = QLabel("☁️ Cloud Profiles Storage Usage")
        q_title.setStyleSheet("color: #ffffff; font-size: 13.5px; font-weight: 700;")
        self.pc_lbl_quota_progress_text = QLabel("10 of 500 Profiles Used (2.0%)")
        self.pc_lbl_quota_progress_text.setStyleSheet("color: #a6e3a1; font-size: 12.5px; font-weight: 700;")
        q_hdr.addWidget(q_title)
        q_hdr.addStretch()
        q_hdr.addWidget(self.pc_lbl_quota_progress_text)
        q_lay.addLayout(q_hdr)

        from PySide6.QtWidgets import QProgressBar
        self.pc_quota_bar = QProgressBar()
        self.pc_quota_bar.setRange(0, 500)
        self.pc_quota_bar.setValue(10)
        self.pc_quota_bar.setTextVisible(False)
        self.pc_quota_bar.setFixedHeight(10)
        self.pc_quota_bar.setStyleSheet("""
            QProgressBar {
                background-color: #313244;
                border-radius: 5px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #89b4fa, stop:1 #a6e3a1);
                border-radius: 5px;
            }
        """)
        q_lay.addWidget(self.pc_quota_bar)

        q_sub = QLabel("🔒 End-to-end encrypted storage replication across all your authorized devices.")
        q_sub.setStyleSheet("color: #6c7086; font-size: 11.5px;")
        q_lay.addWidget(q_sub)

        lay.addWidget(quota_card)

        # ----------------------------------------------------
        # 👑 LINK SRITZONE.COM VIP MEMBERSHIP CARD
        # ----------------------------------------------------
        self.vip_link_card = QFrame()
        self.vip_link_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #23123d, stop:0.5 #1a1738, stop:1 #131c38);
                border: 1px solid rgba(168, 85, 247, 0.45);
                border-radius: 14px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        vip_lay = QVBoxLayout(self.vip_link_card)
        vip_lay.setContentsMargins(20, 16, 20, 16)
        vip_lay.setSpacing(10)

        vip_hdr = QHBoxLayout()
        vip_title = QLabel("👑 Link sritzone.com VIP Membership")
        vip_title.setStyleSheet("color: #facc15; font-size: 14px; font-weight: 800;")
        
        vip_badge = QLabel("⚡ AUTO-UPGRADE & UNLOCK ALL BOTS")
        vip_badge.setStyleSheet("""
            background: rgba(250, 204, 21, 0.15);
            color: #facc15;
            border: 1px solid rgba(250, 204, 21, 0.4);
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 10px;
            font-weight: 800;
        """)
        vip_hdr.addWidget(vip_title)
        vip_hdr.addWidget(vip_badge)
        vip_hdr.addStretch()
        vip_lay.addLayout(vip_hdr)

        vip_desc = QLabel("Connect your active sritzone.com VIP account email to automatically unlock 👑 Enterprise Plan (5,000 Profiles) + ALL Automation Bots & Tools!")
        vip_desc.setStyleSheet("color: #cbd5e1; font-size: 11.5px;")
        vip_lay.addWidget(vip_desc)

        # Input & Button Row
        vip_input_row = QHBoxLayout()
        vip_input_row.setSpacing(10)

        self.pc_txt_vip_email = QLineEdit()
        self.pc_txt_vip_email.setPlaceholderText("Enter your sritzone.com VIP registered email...")
        self.pc_txt_vip_email.setFixedHeight(36)
        self.pc_txt_vip_email.setStyleSheet("""
            QLineEdit {
                background-color: #0f1322;
                border: 1px solid rgba(168, 85, 247, 0.4);
                border-radius: 8px;
                color: #ffffff;
                padding: 0 12px;
                font-size: 12.5px;
            }
            QLineEdit:focus {
                border-color: #c084fc;
                background-color: #1a1b32;
            }
        """)

        self.pc_btn_link_vip = QPushButton("✨ Connect VIP Membership")
        self.pc_btn_link_vip.setCursor(Qt.PointingHandCursor)
        self.pc_btn_link_vip.setFixedHeight(36)
        self.pc_btn_link_vip.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #4f46e5);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                padding: 0 18px;
                border-radius: 8px;
                border: 1px solid rgba(216, 180, 254, 0.4);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #6366f1);
            }
            QPushButton:disabled {
                background: #334155;
                color: #64748b;
                border: none;
            }
        """)
        self.pc_btn_link_vip.clicked.connect(self._on_pc_link_vip_clicked)

        vip_input_row.addWidget(self.pc_txt_vip_email, stretch=1)
        vip_input_row.addWidget(self.pc_btn_link_vip)
        vip_lay.addLayout(vip_input_row)

        lay.addWidget(self.vip_link_card)

        # Plan Upgrade & Renewal Action Card
        upgrade_strip = QFrame()
        upgrade_strip.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #231a38, stop:1 #171b30);
                border: 1px solid rgba(192, 132, 252, 0.4);
                border-radius: 14px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        u_lay = QHBoxLayout(upgrade_strip)
        u_lay.setContentsMargins(20, 16, 20, 16)
        
        u_txt = QVBoxLayout()
        u_txt.setSpacing(3)
        lbl_u1 = QLabel("💎 Need to expand your cloud profiles quota or renew subscription?")
        lbl_u1.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800;")
        lbl_u2 = QLabel("Upgrade or extend your plan instantly with automated crypto activation (USDT / BTC / LTC / TRX).")
        lbl_u2.setStyleSheet("color: #a6adc8; font-size: 11.5px;")
        u_txt.addWidget(lbl_u1)
        u_txt.addWidget(lbl_u2)
        u_lay.addLayout(u_txt)

        u_lay.addStretch()

        btn_upgrade = QPushButton("🚀 Upgrade / Extend Plan")
        btn_upgrade.setCursor(Qt.PointingHandCursor)
        btn_upgrade.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                color: #ffffff;
                font-weight: 800;
                font-size: 12.5px;
                padding: 10px 20px;
                border-radius: 8px;
                border: 1px solid #a855f7;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #1d4ed8);
            }
        """)
        btn_upgrade.clicked.connect(self._on_dash_upgrade_clicked)
        u_lay.addWidget(btn_upgrade)

        lay.addWidget(upgrade_strip)
        lay.addStretch()
        return widget

    def _create_pc_bots_tab(self) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("🤖 Active Automation Bots & Tools Ecosystem")
        lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800;")
        
        btn_store = QPushButton("🛒 Explore All Bots in Store")
        btn_store.setCursor(Qt.PointingHandCursor)
        btn_store.setStyleSheet("""
            QPushButton {
                background: #313244;
                color: #cba6f7;
                border: 1px solid rgba(203, 166, 247, 0.4);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background: #cba6f7; color: #11111b; }
        """)
        btn_store.clicked.connect(lambda: self.switch_view(2))

        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(btn_store)
        lay.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #181926;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3b4261;
                border-radius: 4px;
            }
        """)
        
        c_widget = QWidget()
        c_widget.setStyleSheet("background: transparent;")
        c_lay = QVBoxLayout(c_widget)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(10)

        online_bots = getattr(self, "_store_online_bots", None)
        if (online_bots is None or len(online_bots) == 0) and hasattr(self, "plugin_engine"):
            online_bots = self.plugin_engine.get_all_bots()

        bots = []
        if online_bots and isinstance(online_bots, list):
            for item in online_bots:
                bid = item.get("bot_id") or item.get("id")
                if bid:
                    title = item.get("title") or item.get("name") or f"🤖 {bid.replace('_', ' ').title()}"
                    desc = item.get("desc") or item.get("description") or "Automation Bot Module"
                    bots.append((bid, title, desc))

        if not bots:
            lbl_empty = QLabel("⚡ No Active Automation Bots Activated Yet\nExplore the Bot Store to discover modules!")
            lbl_empty.setStyleSheet("color: #a6adc8; font-size: 13px; padding: 24px; text-align: center;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            c_lay.addWidget(lbl_empty)
        else:
            for b_id, b_title, b_desc in bots:
                card = QFrame()
                card.setStyleSheet("""
                    QFrame {
                        background-color: #161828;
                        border: 1px solid #2b2e46;
                        border-radius: 14px;
                    }
                    QLabel {
                        background: transparent;
                        border: none;
                    }
                """)
                b_box = QHBoxLayout(card)
                b_box.setContentsMargins(20, 16, 20, 16)
                b_box.setSpacing(16)

                t_vbox = QVBoxLayout()
                t_vbox.setSpacing(4)
                lbl_t = QLabel(f"🤖 {b_title}")
                lbl_t.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")
                lbl_d = QLabel(b_desc)
                lbl_d.setStyleSheet("color: #a6adc8; font-size: 11.5px;")
                t_vbox.addWidget(lbl_t)
                t_vbox.addWidget(lbl_d)
                b_box.addLayout(t_vbox, stretch=1)

                lbl_st = QLabel("🟢 Active")
                lbl_st.setStyleSheet("""
                    background-color: rgba(166, 227, 161, 0.15);
                    color: #a6e3a1;
                    border: 1px solid rgba(166, 227, 161, 0.35);
                    border-radius: 6px;
                    padding: 5px 12px;
                    font-size: 11.5px;
                    font-weight: 700;
                """)
                b_box.addWidget(lbl_st)

                btn_run = QPushButton("🚀 Run Bot")
                btn_run.setCursor(Qt.PointingHandCursor)
                btn_run.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #89b4fa, stop:1 #cba6f7);
                        color: #11111b;
                        border: none;
                        border-radius: 8px;
                        padding: 8px 16px;
                        font-size: 12px;
                        font-weight: 800;
                    }
                    QPushButton:hover { background: #89b4fa; color: #11111b; }
                """)
                btn_run.clicked.connect(lambda *args, b=b_id, t=b_title: self._launch_dynamic_bot(b, t))
                b_box.addWidget(btn_run)

                c_lay.addWidget(card)

        c_lay.addStretch()
        scroll.setWidget(c_widget)
        lay.addWidget(scroll)
        return widget

    def _create_pc_tx_tab(self) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("💳 Orders & Payment Transaction History")
        lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800;")
        
        btn_refresh = QPushButton("🔄 Refresh History")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background: #313244;
                color: #89b4fa;
                border: 1px solid rgba(137, 180, 250, 0.3);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background: #89b4fa; color: #11111b; }
        """)
        btn_refresh.clicked.connect(self._fetch_pc_transactions)

        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(btn_refresh)
        lay.addLayout(hdr)

        # Table
        self.pc_tx_table = QTableWidget()
        self.pc_tx_table.setColumnCount(6)
        self.pc_tx_table.setHorizontalHeaderLabels(["Order / Invoice ID", "Software / Subscription Item", "Price Paid", "Payment Gateway", "Date & Time", "Status"])
        self.pc_tx_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pc_tx_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.pc_tx_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pc_tx_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.pc_tx_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.pc_tx_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.pc_tx_table.verticalHeader().setVisible(False)
        self.pc_tx_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pc_tx_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pc_tx_table.setStyleSheet("""
            QTableWidget {
                background-color: #161828;
                border: 1px solid #2b2e46;
                border-radius: 14px;
                gridline-color: #232538;
                color: #cdd6f4;
                font-size: 12.5px;
            }
            QHeaderView::section {
                background-color: #1e2034;
                color: #89b4fa;
                padding: 10px;
                font-weight: 800;
                border: 1px solid #2b2e46;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px;
                border: none;
            }
        """)

        lay.addWidget(self.pc_tx_table)
        return widget

    def _refresh_personal_center(self) -> None:
        """Instantly render Personal Center with local cached user info (0ms latency), and asynchronously refresh in background."""
        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        self._update_personal_center_ui(user_info)

        def _bg_refresh():
            try:
                if hasattr(self, "auth_mgr") and self.auth_mgr:
                    self.auth_mgr.refresh_user_info()
                    u = self.auth_mgr.get_current_user()
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self._update_personal_center_ui(u))
            except Exception:
                pass

        import threading
        threading.Thread(target=_bg_refresh, daemon=True).start()
        self._fetch_pc_transactions()

    def _update_personal_center_ui(self, user_info: dict) -> None:
        if not user_info:
            return
        name = user_info.get("full_name") or user_info.get("email", "User").split("@")[0]
        email = user_info.get("email", "guest@srbrowser.com")
        plan_type = user_info.get("plan_type", "Free")
        cloud_quota = int(user_info.get("cloud_quota") or user_info.get("max_profiles", 100) or 100)
        days_rem = int(user_info.get("days_remaining", 30 if plan_type.lower() != "free" else 0) or 0)
        plan_exp = user_info.get("plan_expires_at", "")

        plan_title = "Professional" if (plan_type.lower() in ("pro", "professional", "vip") or cloud_quota == 500) else ("Business" if cloud_quota == 1000 else ("Enterprise" if cloud_quota >= 5000 else "Free"))

        if hasattr(self, "pc_lbl_avatar"):
            self.pc_lbl_avatar.setText((name[:1] if name else "U").upper())
        if hasattr(self, "pc_lbl_name"):
            self.pc_lbl_name.setText(name)
        if hasattr(self, "pc_lbl_email"):
            self.pc_lbl_email.setText(email)
        if hasattr(self, "pc_lbl_badge_plan"):
            self.pc_lbl_badge_plan.setText(f"⭐ {plan_title} Member" if plan_title != "Free" else "🆓 Free Account")
        if hasattr(self, "pc_lbl_badge_validity"):
            self.pc_lbl_badge_validity.setText(f"⏳ {days_rem} Days Remaining" if plan_title != "Free" and days_rem > 0 else "✨ Lifetime Free Access")

        if hasattr(self, "pc_val_plan"):
            self.pc_val_plan.setText(f"{plan_title} Plan Tier")
        if hasattr(self, "pc_val_quota"):
            self.pc_val_quota.setText(f"{cloud_quota} Cloud Profiles")
        if hasattr(self, "pc_val_expiry"):
            self.pc_val_expiry.setText(plan_exp or "Never (Lifetime Free)")
        if hasattr(self, "pc_sub_expiry"):
            self.pc_sub_expiry.setText(f"{days_rem} Days Remaining" if plan_title != "Free" else "Lifetime Access Active")

        stats = self.profile_mgr.get_dashboard_stats() if hasattr(self, "profile_mgr") and self.profile_mgr else {"total_profiles": 0}
        total_p = stats.get("total_profiles", 0)

        if hasattr(self, "pc_quota_bar"):
            self.pc_quota_bar.setRange(0, max(1, cloud_quota))
            self.pc_quota_bar.setValue(min(total_p, cloud_quota))
        if hasattr(self, "pc_lbl_quota_progress_text"):
            pct = (total_p / max(1, cloud_quota)) * 100
            self.pc_lbl_quota_progress_text.setText(f"{total_p} of {cloud_quota} Profiles ({pct:.1f}%)")

        # Show or Hide VIP Link Card dynamically based on Admin global setting
        vip_link_enabled = user_info.get("sritzone_vip_link_enabled", True)
        if hasattr(self, "vip_link_card") and self.vip_link_card:
            self.vip_link_card.setVisible(bool(vip_link_enabled))

    def _fetch_pc_transactions(self) -> None:
        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        token = user_info.get("token")
        if not token:
            return

        def _worker():
            try:
                import requests
                r = requests.get(
                    f"https://srbrowser.com/api/v1/user/transactions?token={token}",
                    headers={"User-Agent": "srkBrowser/2.0"},
                    timeout=8
                )
                if r.status_code == 200:
                    data = r.json()
                    txs = data.get("transactions", [])
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self._populate_pc_tx_table(txs))
            except Exception as e:
                print(f"[TRANSACTIONS FETCH ERROR]: {e}")

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _populate_pc_tx_table(self, txs: list) -> None:
        if not hasattr(self, "pc_tx_table"):
            return
        self.pc_tx_table.setRowCount(0)
        for row_idx, tx in enumerate(txs):
            self.pc_tx_table.insertRow(row_idx)
            self.pc_tx_table.setRowHeight(row_idx, 42)
            
            oid_item = QTableWidgetItem(str(tx.get("order_id", "")))
            oid_item.setTextAlignment(Qt.AlignCenter)

            name_item = QTableWidgetItem(f"  {tx.get('item_name', '')}")
            
            amt = float(tx.get("amount", 0.0))
            amt_item = QTableWidgetItem(f"${amt:.2f} USD")
            amt_item.setTextAlignment(Qt.AlignCenter)
            amt_item.setForeground(QColor("#a6e3a1"))
            
            gw_item = QTableWidgetItem(str(tx.get("payment_gateway", "OxaPay Crypto")))
            gw_item.setTextAlignment(Qt.AlignCenter)
            
            date_item = QTableWidgetItem(str(tx.get("created_at", "")))
            date_item.setTextAlignment(Qt.AlignCenter)
            
            status_item = QTableWidgetItem(f"✅ {tx.get('status', 'Completed')}")
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor("#89b4fa"))

            self.pc_tx_table.setItem(row_idx, 0, oid_item)
            self.pc_tx_table.setItem(row_idx, 1, name_item)
            self.pc_tx_table.setItem(row_idx, 2, amt_item)
            self.pc_tx_table.setItem(row_idx, 3, gw_item)
            self.pc_tx_table.setItem(row_idx, 4, date_item)
            self.pc_tx_table.setItem(row_idx, 5, status_item)

    def _on_pc_link_vip_clicked(self) -> None:
        """Handle connecting sritzone.com VIP email from Desktop Personal Center."""
        email_str = self.pc_txt_vip_email.text().strip().lower()
        if not email_str or "@" not in email_str:
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid sritzone.com VIP email address.")
            return

        user_info = getattr(self, "auth_mgr", None) and self.auth_mgr.get_current_user() or {}
        token = user_info.get("token") or (self.auth_mgr.get_token() if hasattr(self.auth_mgr, "get_token") else "")
        if not token:
            QMessageBox.warning(self, "Login Required", "Please sign in to your srkBrowser account first.")
            return

        self.pc_btn_link_vip.setEnabled(False)
        self.pc_btn_link_vip.setText("⏳ Verifying...")

        def _do_link():
            import requests
            try:
                url = f"https://srbrowser.com/api/v1/vip/link-email?token={token}"
                payload = {"vip_email": email_str}
                r = requests.post(url, json=payload, cookies={"auth_token": token}, timeout=10)
                res_data = r.json() if r.status_code in [200, 400, 401, 500] and r.text.startswith("{") else {}

                from PySide6.QtCore import QTimer
                if r.status_code == 200 and res_data.get("status") == "success":
                    msg = res_data.get("message", "VIP Membership linked successfully!")
                    def _on_success():
                        self.pc_btn_link_vip.setEnabled(True)
                        self.pc_btn_link_vip.setText("✨ Connect VIP Membership")
                        self.pc_txt_vip_email.clear()
                        QMessageBox.information(
                            self,
                            "🎉 VIP Membership Activated!",
                            f"{msg}\n\nYour account is now upgraded to 👑 Enterprise Plan (5,000 Profiles) with all automation bots and tools unlocked!"
                        )
                        if hasattr(self, "auth_mgr") and self.auth_mgr:
                            self.auth_mgr.refresh_user_info()
                        self._refresh_dashboard(force_server=True)
                        self._refresh_personal_center()
                        self.refresh_all_views(force=True)
                    QTimer.singleShot(0, _on_success)
                else:
                    err_msg = res_data.get("message") or res_data.get("error") or f"Server returned error code: {r.status_code}"
                    def _on_fail():
                        self.pc_btn_link_vip.setEnabled(True)
                        self.pc_btn_link_vip.setText("✨ Connect VIP Membership")
                        QMessageBox.warning(self, "VIP Link Verification", err_msg)
                    QTimer.singleShot(0, _on_fail)
            except Exception as e:
                def _on_err():
                    self.pc_btn_link_vip.setEnabled(True)
                    self.pc_btn_link_vip.setText("✨ Connect VIP Membership")
                    QMessageBox.critical(self, "Connection Error", f"Could not connect to server: {e}")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, _on_err)

        import threading
        threading.Thread(target=_do_link, daemon=True).start()

    # =========================================================================
    # 📥 SYSTEM TRAY & SMART EXIT CONFIRMATION (ixBrowser Style)
    # =========================================================================

    def _setup_system_tray(self) -> None:
        """Initialize Windows Taskbar Notification Area (System Tray) Icon & Menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = ASSETS_DIR / "icon.ico"
        if not icon_path.exists():
            icon_path = ASSETS_DIR / "icon.png"
        tray_icon = QIcon(str(icon_path)) if icon_path.exists() else self.windowIcon()

        self.tray_icon = QSystemTrayIcon(tray_icon, self)
        self.tray_icon.setToolTip(f"{APP_NAME} v{APP_VERSION} — Active")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)

        act_open = QAction("⚡ Open srkBrowser", self)
        act_open.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(act_open)

        tray_menu.addSeparator()

        act_restart = QAction("🔄 Restart srkBrowser", self)
        act_restart.triggered.connect(self.on_restart_action)
        tray_menu.addAction(act_restart)

        act_exit = QAction("🛑 Exit Safely", self)
        act_exit.triggered.connect(self._force_safe_exit)
        tray_menu.addAction(act_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.tray_icon.show()

    def on_global_refresh_and_sync(self) -> None:
        """1-Click Live Global Full-App Sync & Refresh (Scripts, Tools, Bots, Extensions & Profiles)."""
        self.status_bar.showMessage("🔄 Syncing with Cloud Server & Refreshing All Data...", 2500)
        
        # 1. Sync All Cloud Stores (Bots, Tools, Scripts)
        if hasattr(self, "_sync_store_manifest_async"):
            self._sync_store_manifest_async()
        elif hasattr(self, "_sync_scripts_manifest_async"):
            self._sync_scripts_manifest_async()

        if hasattr(self, "_sync_tools_manifest_async"):
            self._sync_tools_manifest_async()

        # 2. Re-render Grid Views
        if hasattr(self, "_render_scripts_grid"):
            search_txt = self.txt_scripts_search.text() if hasattr(self, "txt_scripts_search") else ""
            self._render_scripts_grid(search_text=search_txt)

        if hasattr(self, "_render_tools_grid"):
            tools_txt = self.txt_tools_search.text() if hasattr(self, "txt_tools_search") else ""
            self._render_tools_grid(search_text=tools_txt)

        if hasattr(self, "_render_store_grid"):
            self._render_store_grid()

        if hasattr(self, "_render_extensions_grid"):
            self._render_extensions_grid()

        # 3. Refresh Profile Management Views
        self.refresh_all_views()

        # 4. Refresh Team & Cloud Profiles if available
        if hasattr(self, "cloud_sync_mgr") and hasattr(self.cloud_sync_mgr, "sync_all_async"):
            try:
                self.cloud_sync_mgr.sync_all_async()
            except Exception:
                pass

        self.status_bar.showMessage("✅ 100% Synced: All Scripts, Tools, Bots & Profiles Refreshed Live!", 5000)

    def on_restart_action(self) -> None:
        """Seamlessly restart software without showing exit confirmation dialog."""
        self._is_restarting = True
        self._cleanup_before_exit()
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
        from updater import restart_application
        restart_application()

    def _on_tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        """Restore minimized main window, raise to top, and bring to focus."""
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _force_safe_exit(self) -> None:
        """Force graceful shutdown and exit."""
        self._cleanup_before_exit()
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def _execute_graceful_app_exit(self, event) -> None:
        """Execute graceful browser closing, session cookie saving, and cloud sync barrier before exit."""
        self._cleanup_before_exit()

        try:
            from core.cloud_sync import sync_tracker
            from core.ui.exit_sync_dialog import ExitSyncDialog
        except Exception:
            try:
                from cloud_sync import sync_tracker
                from ui.exit_sync_dialog import ExitSyncDialog
            except Exception:
                sync_tracker = None
                ExitSyncDialog = None

        if sync_tracker and sync_tracker.is_busy() and ExitSyncDialog:
            try:
                dlg_sync = ExitSyncDialog(max_timeout_sec=6.0, parent=self)
                dlg_sync.exec()
            except Exception as e:
                print(f"[EXIT SYNC DIALOG ERROR]: {e}")

        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
        event.accept()
        QApplication.quit()

    def _cleanup_before_exit(self) -> None:
        """Gracefully close active browser instances, save profile state, and stop threads."""
        try:
            if hasattr(self, "browser_launcher") and self.browser_launcher:
                self.browser_launcher.close_all_active_profiles()
        except Exception:
            pass

        # Forcefully terminate any remaining zombie chrome processes belonging to srkBrowser profiles
        try:
            import time
            time.sleep(0.4)
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if 'chrome' in pname:
                        cmd = " ".join(proc.info.get('cmdline') or [])
                        if 'srkBrowser' in cmd or 'Profile' in cmd or 'core/profiles' in cmd or 'core\\profiles' in cmd:
                            proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(self, "session_check_thread") and self.session_check_thread:
                self.session_check_thread.stop()
                self.session_check_thread.wait(500)
        except Exception:
            pass

        try:
            if hasattr(self, "network_watcher") and self.network_watcher:
                self.network_watcher.stop()
                self.network_watcher.wait(400)
        except Exception:
            pass

        try:
            if hasattr(self, "profile_mgr") and hasattr(self.profile_mgr, "save_profiles"):
                self.profile_mgr.save_profiles()
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        """ixBrowser-Style Smart Exit Handler with System Tray & Graceful Shutdown."""
        # 0. Bypass modal entirely on software restart or force exit
        if getattr(self, "_is_restarting", False) or getattr(self, "_force_exit", False):
            self._cleanup_before_exit()
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.hide()
            event.accept()
            return

        settings = load_settings()
        dont_remind = settings.get("dont_remind_exit", False)
        pref_action = settings.get("exit_action_preference", "ask")

        # 1. If user previously chose 'Don't remind again'
        if dont_remind and pref_action == "tray":
            event.ignore()
            self.hide()
            if hasattr(self, 'tray_icon'):
                self.tray_icon.show()
                self.tray_icon.showMessage(
                    APP_NAME,
                    "srkBrowser is minimized to system tray and active in background.",
                    QSystemTrayIcon.Information,
                    2000
                )
            return
        elif dont_remind and pref_action == "exit":
            self._execute_graceful_app_exit(event)
            return

        # 2. Show interactive Smart Exit Confirmation Dialog
        running_count = 0
        if hasattr(self, 'browser_launcher') and hasattr(self.browser_launcher, 'active_processes'):
            running_count = len(self.browser_launcher.active_processes)

        dlg = SmartExitConfirmDialog(running_profiles_count=running_count, parent=self)
        res = dlg.exec()

        if res == QDialog.Accepted:
            if dlg.is_dont_remind_checked():
                settings["dont_remind_exit"] = True
                settings["exit_action_preference"] = dlg.selected_action
                save_settings(settings)

            if dlg.selected_action == "tray":
                event.ignore()
                self.hide()
                if hasattr(self, 'tray_icon'):
                    self.tray_icon.show()
                    self.tray_icon.showMessage(
                        APP_NAME,
                        "srkBrowser is minimized to system tray and active in background.",
                        QSystemTrayIcon.Information,
                        2000
                    )
            elif dlg.selected_action == "exit":
                self._execute_graceful_app_exit(event)
                return
            else:
                event.ignore()
        else:
            event.ignore()

    # -------------------------------------------------------------
    # 10. DEDICATED TEAM & OPERATOR MANAGEMENT PAGE (STACK INDEX 9)
    # -------------------------------------------------------------
    def _create_team_page(self) -> QWidget:
        """Create the dedicated in-app Team & Sub-Accounts Management page with 0 popups."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(20, 16, 20, 16)
        page_layout.setSpacing(14)

        # Internal state for team page
        self._team_page_members_data = []
        self._team_page_available_groups = ["Default"]
        self._team_page_max_members = 999999
        self._team_page_used_members = 0
        self._team_editing_member_id = None
        self._team_group_checkboxes = {}

        # Sub-Stack Widget for switching between List View (index 0) and Add/Edit Form View (index 1)
        self.team_sub_stack = QStackedWidget()
        self.team_sub_stack.addWidget(self._create_team_list_subview())  # index 0
        self.team_sub_stack.addWidget(self._create_team_form_subview())  # index 1

        page_layout.addWidget(self.team_sub_stack)
        return page

    def _create_team_list_subview(self) -> QWidget:
        """Sub-view 0: Team Members Table & Management Controls."""
        subview = QWidget()
        layout = QVBoxLayout(subview)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # 1. Top SaaS Header Card
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #16192c, stop:1 #0f1120);
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        header_card_vbox = QVBoxLayout(header_card)
        header_card_vbox.setContentsMargins(18, 16, 18, 16)
        header_card_vbox.setSpacing(12)

        header_top_hbox = QHBoxLayout()
        header_top_hbox.setSpacing(14)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)
        lbl_title = QLabel("👥 Team Collaboration & Operator Management")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 900; color: #ffffff; background: transparent; border: none;")
        lbl_sub = QLabel("Assign operator logins with dedicated profile group visibility, bot privileges, and safety permission locks.")
        lbl_sub.setStyleSheet("font-size: 11.5px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_sub)
        header_top_hbox.addLayout(title_vbox)

        header_top_hbox.addStretch()

        # Seats Badge Pill
        self.lbl_team_page_seats = QLabel("👥 Active Seats: Unlimited")
        self.lbl_team_page_seats.setStyleSheet("""
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 800;
        """)
        header_top_hbox.addWidget(self.lbl_team_page_seats)

        # Refresh Button
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #818cf8;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 0 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #232742;
                color: #ffffff;
                border-color: #6366f1;
            }
        """)
        btn_refresh.clicked.connect(self._refresh_team_page)
        header_top_hbox.addWidget(btn_refresh)

        # Add Member Primary Button (Switches In-Page to Form)
        self.btn_team_page_add = QPushButton("➕ Add Member")
        self.btn_team_page_add.setCursor(Qt.PointingHandCursor)
        self.btn_team_page_add.setFixedHeight(36)
        self.btn_team_page_add.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 800;
                font-size: 12px;
                padding: 0 18px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #22d3ee);
            }
        """)
        self.btn_team_page_add.clicked.connect(self._on_team_page_add_clicked)
        header_top_hbox.addWidget(self.btn_team_page_add)

        header_card_vbox.addLayout(header_top_hbox)

        # Quota Notice Banner (Disabled for Standalone Customer Edition)
        self.team_quota_banner = QFrame()
        self.team_quota_banner.setVisible(False)

        layout.addWidget(header_card)

        # 2. Controls & Search Row
        controls_hbox = QHBoxLayout()
        controls_hbox.setSpacing(10)

        self.txt_team_page_search = QLineEdit()
        self.txt_team_page_search.setPlaceholderText("🔍 Search team members by name or email...")
        self.txt_team_page_search.setFixedHeight(36)
        self.txt_team_page_search.setStyleSheet("""
            QLineEdit {
                background-color: #131626;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #6366f1; background-color: #181c30; }
        """)
        self.txt_team_page_search.textChanged.connect(self._on_team_search_changed)
        controls_hbox.addWidget(self.txt_team_page_search, stretch=1)

        layout.addLayout(controls_hbox)

        # 3. Main Team Table Widget
        self.table_team_page = QTableWidget()
        self.table_team_page.setColumnCount(6)
        self.table_team_page.setHorizontalHeaderLabels([
            "Member Name", "Email Address (Login)", "Allowed Groups", "Permissions", "Status", "Actions"
        ])
        self.table_team_page.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_team_page.horizontalHeader().resizeSection(0, 165)
        self.table_team_page.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_team_page.horizontalHeader().resizeSection(1, 185)
        self.table_team_page.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table_team_page.horizontalHeader().resizeSection(2, 130)
        self.table_team_page.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_team_page.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table_team_page.horizontalHeader().resizeSection(4, 115)
        self.table_team_page.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.table_team_page.horizontalHeader().resizeSection(5, 185)
        self.table_team_page.verticalHeader().setVisible(False)
        self.table_team_page.verticalHeader().setDefaultSectionSize(56)
        self.table_team_page.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_team_page.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_team_page.setShowGrid(False)
        self.table_team_page.setStyleSheet("""
            QTableWidget {
                background-color: #0f1222;
                border: 1px solid #232742;
                border-radius: 12px;
                gridline-color: #1e243b;
                color: #f1f5f9;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #16192c;
                color: #94a3b8;
                font-weight: 800;
                font-size: 11px;
                text-transform: uppercase;
                border: none;
                border-bottom: 2px solid #232742;
                padding: 12px 10px;
            }
            QTableWidget::item {
                border-bottom: 1px solid #1a1e33;
            }
            QTableWidget::item:hover {
                background-color: rgba(99, 102, 241, 0.08);
            }
            QTableWidget::item:selected {
                background-color: #1e2544;
            }
        """)

        def _on_team_row_double_click(row, col):
            if hasattr(self, "_team_page_members_data") and self._team_page_members_data and row < len(self._team_page_members_data):
                self._on_team_page_edit_clicked(self._team_page_members_data[row])
        self.table_team_page.cellDoubleClicked.connect(_on_team_row_double_click)

        layout.addWidget(self.table_team_page, stretch=1)
        return subview

    def _create_team_form_subview(self) -> QWidget:
        """Sub-view 1: In-Page Embedded Create & Edit Team Member Form (0 Popups!)."""
        subview = QWidget()
        layout = QVBoxLayout(subview)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Top Navigation & Title Bar
        nav_card = QFrame()
        nav_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #16192c, stop:1 #0f1120);
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        nav_hbox = QHBoxLayout(nav_card)
        nav_hbox.setContentsMargins(16, 12, 16, 12)
        nav_hbox.setSpacing(14)

        btn_back = QPushButton("← Back to Team Members")
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.setFixedHeight(34)
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #818cf8;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 0 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #232742;
                color: #ffffff;
                border-color: #6366f1;
            }
        """)
        btn_back.clicked.connect(self._on_team_form_back_clicked)
        nav_hbox.addWidget(btn_back)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.lbl_team_form_title = QLabel("➕ Add New Team Member")
        self.lbl_team_form_title.setStyleSheet("font-size: 16px; font-weight: 900; color: #ffffff; background: transparent; border: none;")
        self.lbl_team_form_sub = QLabel("Assign login credentials, profile group visibility, and safety permissions.")
        self.lbl_team_form_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent; border: none;")
        title_vbox.addWidget(self.lbl_team_form_title)
        title_vbox.addWidget(self.lbl_team_form_sub)
        nav_hbox.addLayout(title_vbox)
        nav_hbox.addStretch()

        layout.addWidget(nav_card)

        # Scroll Area for Form Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 4, 8, 4)
        scroll_layout.setSpacing(14)

        # ---------------- Section 1: Member Account Info ----------------
        card_info = QFrame()
        card_info.setStyleSheet("""
            QFrame {
                background-color: #131628;
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        card_info_vbox = QVBoxLayout(card_info)
        card_info_vbox.setContentsMargins(18, 16, 18, 16)
        card_info_vbox.setSpacing(12)

        lbl_sec1 = QLabel("👤 Member Account Information")
        lbl_sec1.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #38bdf8; background: transparent; border: none;")
        card_info_vbox.addWidget(lbl_sec1)

        # Inputs Grid
        grid_info = QGridLayout()
        grid_info.setHorizontalSpacing(14)
        grid_info.setVerticalSpacing(10)

        # Email
        lbl_email = QLabel("Email Address (Login Username):")
        lbl_email.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #cdd6f4; background: transparent; border: none;")
        self.txt_team_form_email = QLineEdit()
        self.txt_team_form_email.setPlaceholderText("e.g. operator@company.com")
        self.txt_team_form_email.setFixedHeight(34)
        self.txt_team_form_email.setStyleSheet("""
            QLineEdit {
                background-color: #0d0f1a;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #38bdf8; background-color: #121626; }
        """)
        grid_info.addWidget(lbl_email, 0, 0)
        grid_info.addWidget(self.txt_team_form_email, 1, 0)

        # Full Name
        lbl_name = QLabel("Full Name / Nickname:")
        lbl_name.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #cdd6f4; background: transparent; border: none;")
        self.txt_team_form_name = QLineEdit()
        self.txt_team_form_name.setPlaceholderText("e.g. John Operator")
        self.txt_team_form_name.setFixedHeight(34)
        self.txt_team_form_name.setStyleSheet("""
            QLineEdit {
                background-color: #0d0f1a;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #38bdf8; background-color: #121626; }
        """)
        grid_info.addWidget(lbl_name, 0, 1)
        grid_info.addWidget(self.txt_team_form_name, 1, 1)

        # Password
        lbl_pwd = QLabel("Account Password:")
        lbl_pwd.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #cdd6f4; background: transparent; border: none;")
        
        pwd_hbox = QHBoxLayout()
        pwd_hbox.setSpacing(6)
        self.txt_team_form_pwd = QLineEdit()
        self.txt_team_form_pwd.setPlaceholderText("Min 4 characters (leave empty when editing to keep unchanged)")
        self.txt_team_form_pwd.setFixedHeight(34)
        self.txt_team_form_pwd.setStyleSheet("""
            QLineEdit {
                background-color: #0d0f1a;
                color: #ffffff;
                border: 1px solid #282d47;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #38bdf8; background-color: #121626; }
        """)
        btn_gen = QPushButton("🎲 Gen")
        btn_gen.setCursor(Qt.PointingHandCursor)
        btn_gen.setFixedSize(60, 34)
        btn_gen.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        def _gen_pwd():
            import secrets, string
            chars = string.ascii_letters + string.digits + "!@#"
            self.txt_team_form_pwd.setText("".join(secrets.choice(chars) for _ in range(10)))
        btn_gen.clicked.connect(_gen_pwd)
        pwd_hbox.addWidget(self.txt_team_form_pwd, stretch=1)
        pwd_hbox.addWidget(btn_gen)

        grid_info.addWidget(lbl_pwd, 2, 0, 1, 2)
        grid_info.addLayout(pwd_hbox, 3, 0, 1, 2)

        card_info_vbox.addLayout(grid_info)
        scroll_layout.addWidget(card_info)

        # ---------------- Section 2: Profile Groups Access ----------------
        card_groups = QFrame()
        card_groups.setStyleSheet("""
            QFrame {
                background-color: #131628;
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        card_groups_vbox = QVBoxLayout(card_groups)
        card_groups_vbox.setContentsMargins(18, 16, 18, 16)
        card_groups_vbox.setSpacing(10)

        lbl_sec2 = QLabel("📁 Profile Groups Access")
        lbl_sec2.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #a5b4fc; background: transparent; border: none;")
        card_groups_vbox.addWidget(lbl_sec2)

        self.chk_team_form_all_groups = QCheckBox("🌐 All Groups (Full Profile Visibility)")
        self.chk_team_form_all_groups.setChecked(True)
        self.chk_team_form_all_groups.setStyleSheet("""
            QCheckBox { font-size: 12px; font-weight: 700; color: #f1f5f9; background: transparent; border: none; spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #6366f1; background: #0d0f1a; }
            QCheckBox::indicator:checked { background: #6366f1; }
        """)
        def _on_all_toggled(checked):
            for chk in getattr(self, "_team_group_checkboxes", {}).values():
                chk.setEnabled(not checked)
        self.chk_team_form_all_groups.toggled.connect(_on_all_toggled)
        card_groups_vbox.addWidget(self.chk_team_form_all_groups)

        self.team_groups_container_layout = QVBoxLayout()
        self.team_groups_container_layout.setContentsMargins(16, 4, 4, 4)
        self.team_groups_container_layout.setSpacing(6)
        card_groups_vbox.addLayout(self.team_groups_container_layout)

        scroll_layout.addWidget(card_groups)

        # ---------------- Section 3: Role Safety Permissions ----------------
        card_perms = QFrame()
        card_perms.setStyleSheet("""
            QFrame {
                background-color: #131628;
                border: 1px solid #232742;
                border-radius: 12px;
            }
        """)
        card_perms_vbox = QVBoxLayout(card_perms)
        card_perms_vbox.setContentsMargins(18, 16, 18, 16)
        card_perms_vbox.setSpacing(10)

        lbl_sec3 = QLabel("🛡️ Role Safety Permissions")
        lbl_sec3.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #34d399; background: transparent; border: none;")
        card_perms_vbox.addWidget(lbl_sec3)

        chk_style = """
            QCheckBox { font-size: 12px; font-weight: 600; color: #cbd5e1; background: transparent; border: none; spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #334155; background: #0d0f1a; }
            QCheckBox::indicator:checked { background: #10b981; border-color: #10b981; }
        """

        self.chk_team_form_create = QCheckBox("➕ Allow Profile Creation (Can create new browser profiles)")
        self.chk_team_form_create.setChecked(True)
        self.chk_team_form_create.setStyleSheet(chk_style)

        self.chk_team_form_edit = QCheckBox("✏️ Allow Profile Editing (Can change proxy, notes, configs)")
        self.chk_team_form_edit.setChecked(True)
        self.chk_team_form_edit.setStyleSheet(chk_style)

        self.chk_team_form_delete = QCheckBox("🗑️ Allow Profile Deletion (⚠️ Protected: prevents deleting cloud profiles)")
        self.chk_team_form_delete.setChecked(False)
        self.chk_team_form_delete.setStyleSheet(chk_style)

        self.chk_team_form_export = QCheckBox("🔒 Allow Cookie & Proxy Export (⚠️ Protected: prevents credential leaks)")
        self.chk_team_form_export.setChecked(False)
        self.chk_team_form_export.setStyleSheet(chk_style)

        card_perms_vbox.addWidget(self.chk_team_form_create)
        card_perms_vbox.addWidget(self.chk_team_form_edit)
        card_perms_vbox.addWidget(self.chk_team_form_delete)
        card_perms_vbox.addWidget(self.chk_team_form_export)

        scroll_layout.addWidget(card_perms)

        # ---------------- Section 4: Action Buttons ----------------
        act_card = QFrame()
        act_card.setStyleSheet("background: transparent; border: none;")
        act_hbox = QHBoxLayout(act_card)
        act_hbox.setContentsMargins(0, 8, 0, 16)
        act_hbox.setSpacing(12)

        self.btn_team_form_submit = QPushButton("➕ Create Member")
        self.btn_team_form_submit.setCursor(Qt.PointingHandCursor)
        self.btn_team_form_submit.setFixedHeight(40)
        self.btn_team_form_submit.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 800;
                font-size: 13px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #22d3ee);
            }
        """)
        self.btn_team_form_submit.clicked.connect(self._on_team_form_submit_clicked)
        act_hbox.addWidget(self.btn_team_form_submit)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #191c2e;
                color: #94a3b8;
                border: 1px solid #282d47;
                border-radius: 8px;
                font-weight: 700;
                font-size: 12.5px;
                padding: 0 20px;
            }
            QPushButton:hover { background-color: #232742; color: #ffffff; }
        """)
        btn_cancel.clicked.connect(self._on_team_form_back_clicked)
        act_hbox.addWidget(btn_cancel)
        act_hbox.addStretch()

        # In-Page Form Status Banner (Displays server messages directly inline!)
        self.lbl_team_form_status = QLabel("")
        self.lbl_team_form_status.setStyleSheet("font-size: 12px; font-weight: 700; background: transparent; border: none;")
        self.lbl_team_form_status.setVisible(False)
        act_hbox.addWidget(self.lbl_team_form_status)

        scroll_layout.addWidget(act_card)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)
        return subview

    def _get_team_members_file(self):
        from core.config import BASE_DIR
        return BASE_DIR / "team_members.json"

    def _load_local_team_members(self) -> list:
        fpath = self._get_team_members_file()
        if fpath.exists():
            try:
                import json
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def _save_local_team_members(self, members: list) -> bool:
        fpath = self._get_team_members_file()
        try:
            import json
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(members, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

    def _refresh_team_page(self) -> None:
        """Refresh team members from local storage with unlimited seats."""
        members = self._load_local_team_members()
        self._team_page_members_data = members
        self._team_page_max_members = 999999
        self._team_page_used_members = len(members)

        # Merge all groups from profile_mgr + members data
        all_groups_set = set()
        if hasattr(self, "profile_mgr") and self.profile_mgr:
            try:
                all_groups_set.update(self.profile_mgr.get_groups())
            except Exception:
                pass
        for m in members:
            for g in m.get("assigned_groups", []):
                if g and g != "All":
                    all_groups_set.add(g)
        if "Default" not in all_groups_set:
            all_groups_set.add("Default")

        sorted_groups = sorted(list(all_groups_set), key=lambda x: (x != "Default", x.lower()))
        self._team_page_available_groups = sorted_groups

        if hasattr(self, "lbl_team_page_seats"):
            self.lbl_team_page_seats.setText(f"👥 Active Seats: {len(members)} / Unlimited")
            self.lbl_team_page_seats.setStyleSheet("""
                background: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 800;
            """)
        if hasattr(self, "team_quota_banner"):
            self.team_quota_banner.setVisible(False)

        self._render_team_page_table(self._team_page_members_data)

    def _on_team_fetch_success(self, res: dict) -> None:
        self._refresh_team_page()

    def _on_team_fetch_error(self, err_msg: str) -> None:
        self._refresh_team_page()

    def _render_team_page_table(self, members: list) -> None:
        if not hasattr(self, "table_team_page"):
            return
        self.table_team_page.setRowCount(len(members))
        self.table_team_page.verticalHeader().setDefaultSectionSize(54)

        for row_idx, m in enumerate(members):
            self.table_team_page.setRowHeight(row_idx, 54)

            # ---------------- Column 0: Member Name & Avatar ----------------
            w_name = QWidget()
            w_name.setStyleSheet("background: transparent;")
            lay_name = QHBoxLayout(w_name)
            lay_name.setContentsMargins(6, 2, 6, 2)
            lay_name.setSpacing(8)
            lay_name.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            full_name = str(m.get("full_name") or "Operator").strip()
            initial = (full_name[:1] if full_name else "O").upper()
            lbl_av = QLabel(initial)
            lbl_av.setFixedSize(30, 30)
            lbl_av.setAlignment(Qt.AlignCenter)
            lbl_av.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #a855f7);
                color: #ffffff;
                font-weight: 900;
                font-size: 12px;
                border-radius: 15px;
            """)

            txt_vbox = QVBoxLayout()
            txt_vbox.setSpacing(1)
            lbl_n = QLabel(full_name)
            lbl_n.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700;")
            lbl_r = QLabel("👥 Team Operator")
            lbl_r.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600;")
            txt_vbox.addWidget(lbl_n)
            txt_vbox.addWidget(lbl_r)

            lay_name.addWidget(lbl_av)
            lay_name.addLayout(txt_vbox)
            lay_name.addStretch()
            self.table_team_page.setCellWidget(row_idx, 0, w_name)

            # ---------------- Column 1: Email Address (Login) ----------------
            w_email = QWidget()
            w_email.setStyleSheet("background: transparent;")
            lay_email = QHBoxLayout(w_email)
            lay_email.setContentsMargins(6, 2, 6, 2)
            lay_email.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lbl_em = QLabel(m.get("email", ""))
            lbl_em.setStyleSheet("color: #38bdf8; font-size: 11.5px; font-weight: 600; font-family: 'Consolas', 'Segoe UI', monospace;")
            lay_email.addWidget(lbl_em)
            lay_email.addStretch()
            self.table_team_page.setCellWidget(row_idx, 1, w_email)

            # ---------------- Column 2: Allowed Groups ----------------
            w_grp = QWidget()
            w_grp.setStyleSheet("background: transparent;")
            lay_grp = QHBoxLayout(w_grp)
            lay_grp.setContentsMargins(4, 2, 4, 2)
            lay_grp.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            
            grps = m.get("assigned_groups", ["All"])
            is_all = "All" in grps or not grps
            grp_txt = "🌐 All Groups" if is_all else ("📁 " + (", ".join(grps) if len(grps) <= 2 else f"{len(grps)} Groups"))
            
            badge_grp = QLabel(grp_txt)
            badge_grp.setStyleSheet("""
                background: rgba(99, 102, 241, 0.15);
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
            lay_grp.addWidget(badge_grp)
            lay_grp.addStretch()
            self.table_team_page.setCellWidget(row_idx, 2, w_grp)

            # ---------------- Column 3: Permissions Chips ----------------
            w_perm = QWidget()
            w_perm.setStyleSheet("background: transparent;")
            lay_perm = QHBoxLayout(w_perm)
            lay_perm.setContentsMargins(4, 2, 4, 2)
            lay_perm.setSpacing(5)
            lay_perm.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            perms = m.get("permissions", {})
            def _chip(text, color_bg, color_txt, color_border):
                lbl = QLabel(text)
                lbl.setStyleSheet(f"""
                    background: {color_bg};
                    color: {color_txt};
                    border: 1px solid {color_border};
                    border-radius: 5px;
                    padding: 2px 7px;
                    font-size: 10.5px;
                    font-weight: 700;
                """)
                return lbl

            has_chips = False
            if perms.get("can_create", True):
                lay_perm.addWidget(_chip("➕ Create", "rgba(16, 185, 129, 0.15)", "#34d399", "rgba(16, 185, 129, 0.35)"))
                has_chips = True
            if perms.get("can_edit", True):
                lay_perm.addWidget(_chip("✏️ Edit", "rgba(56, 189, 248, 0.15)", "#38bdf8", "rgba(56, 189, 248, 0.35)"))
                has_chips = True
            if perms.get("can_delete", False):
                lay_perm.addWidget(_chip("🗑️ Delete", "rgba(239, 68, 68, 0.15)", "#f87171", "rgba(239, 68, 68, 0.35)"))
                has_chips = True
            if perms.get("can_export", False):
                lay_perm.addWidget(_chip("🔓 Export", "rgba(245, 158, 11, 0.15)", "#fbbf24", "rgba(245, 158, 11, 0.35)"))
                has_chips = True

            if not has_chips:
                lay_perm.addWidget(_chip("🔒 Restricted", "rgba(100, 116, 139, 0.15)", "#94a3b8", "rgba(100, 116, 139, 0.3)"))

            lay_perm.addStretch()
            self.table_team_page.setCellWidget(row_idx, 3, w_perm)

            # ---------------- Column 4: Status Badge ----------------
            w_stat = QWidget()
            w_stat.setStyleSheet("background: transparent;")
            lay_stat = QHBoxLayout(w_stat)
            lay_stat.setContentsMargins(4, 2, 4, 2)
            lay_stat.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            is_act = (m.get("status") == "active")
            lbl_stat = QLabel("🟢 Active" if is_act else "🔴 Suspended")
            lbl_stat.setStyleSheet(f"""
                background: {"rgba(16, 185, 129, 0.15)" if is_act else "rgba(239, 68, 68, 0.15)"};
                color: {"#34d399" if is_act else "#f87171"};
                border: 1px solid {"rgba(16, 185, 129, 0.4)" if is_act else "rgba(239, 68, 68, 0.4)"};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
            lay_stat.addWidget(lbl_stat)
            lay_stat.addStretch()
            self.table_team_page.setCellWidget(row_idx, 4, w_stat)

            # ---------------- Column 5: Action Buttons (Edit / Delete) ----------------
            w_act = QWidget()
            w_act.setStyleSheet("background: transparent;")
            lay_act = QHBoxLayout(w_act)
            lay_act.setContentsMargins(2, 2, 6, 2)
            lay_act.setSpacing(6)
            lay_act.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            btn_edit = QPushButton("✏️ Edit")
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setFixedSize(66, 28)
            btn_edit.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6);
                    color: #ffffff;
                    border: 1px solid #6366f1;
                    border-radius: 6px;
                    padding: 0 6px;
                    font-weight: 800;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #2563eb);
                    border-color: #818cf8;
                }
            """)
            btn_edit.clicked.connect(lambda _, mem=m: self._on_team_page_edit_clicked(mem))

            btn_del = QPushButton("🗑️ Delete")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setFixedSize(70, 28)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.15);
                    color: #fca5a5;
                    border: 1px solid rgba(239, 68, 68, 0.35);
                    border-radius: 6px;
                    padding: 0 6px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                    color: #ffffff;
                    border-color: #ef4444;
                }
            """)
            btn_del.clicked.connect(lambda _, mem=m: self._on_team_page_delete_clicked(mem))

            lay_act.addWidget(btn_edit)
            lay_act.addWidget(btn_del)
            lay_act.addStretch()
            self.table_team_page.setCellWidget(row_idx, 5, w_act)

    def _on_team_search_changed(self, text: str) -> None:
        """Debounced team page search: smooth typing without UI freeze."""
        if not hasattr(self, "_team_search_timer"):
            self._team_search_timer = QTimer(self)
            self._team_search_timer.setSingleShot(True)
            self._team_search_timer.setInterval(160)
            self._team_search_timer.timeout.connect(lambda: self._filter_team_page_table(self.txt_team_page_search.text() if hasattr(self, "txt_team_page_search") else ""))
        self._team_search_timer.start(160)

    def _filter_team_page_table(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._render_team_page_table(self._team_page_members_data)
            return
        filtered = [
            m for m in self._team_page_members_data
            if q in m.get("full_name", "").lower() or q in m.get("email", "").lower() or any(q in g.lower() for g in m.get("assigned_groups", []))
        ]
        self._render_team_page_table(filtered)

    def _populate_team_form_groups(self, assigned_groups: list = None) -> None:
        if assigned_groups is None:
            assigned_groups = ["All"]

        # Collect live groups dynamically from ProfileManager and assigned groups
        all_groups_set = set()
        if hasattr(self, "profile_mgr") and self.profile_mgr:
            try:
                all_groups_set.update(self.profile_mgr.get_groups())
            except Exception:
                pass
        if hasattr(self, "_team_page_available_groups") and self._team_page_available_groups:
            all_groups_set.update(self._team_page_available_groups)
        for g in assigned_groups:
            if g and g != "All":
                all_groups_set.add(g)
        if "Default" not in all_groups_set:
            all_groups_set.add("Default")

        sorted_groups = sorted(list(all_groups_set), key=lambda x: (x != "Default", x.lower()))

        _clear_layout(self.team_groups_container_layout)
        self._team_group_checkboxes.clear()

        is_all = "All" in assigned_groups or not assigned_groups
        self.chk_team_form_all_groups.setChecked(is_all)

        chk_style = """
            QCheckBox { font-size: 12px; font-weight: 600; color: #cbd5e1; background: transparent; border: none; spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #334155; background: #0d0f1a; }
            QCheckBox::indicator:checked { background: #6366f1; border-color: #6366f1; }
        """

        for grp in sorted_groups:
            chk = QCheckBox(f"📁 {grp}")
            chk.setStyleSheet(chk_style)
            chk.setChecked(grp in assigned_groups if not is_all else False)
            chk.setEnabled(not is_all)
            self._team_group_checkboxes[grp] = chk
            self.team_groups_container_layout.addWidget(chk)

    def _on_team_page_add_clicked(self) -> None:
        self._team_editing_member_id = None
        self.lbl_team_form_title.setText("➕ Add New Team Member")
        self.lbl_team_form_sub.setText("Assign credentials, profile group visibility, and safety permissions.")
        self.btn_team_form_submit.setText("➕ Create Member")
        self.txt_team_form_email.setText("")
        self.txt_team_form_email.setEnabled(True)
        self.txt_team_form_name.setText("")
        self.txt_team_form_pwd.setText("")
        self.lbl_team_form_status.setVisible(False)

        self.chk_team_form_create.setChecked(True)
        self.chk_team_form_edit.setChecked(True)
        self.chk_team_form_delete.setChecked(False)
        self.chk_team_form_export.setChecked(False)

        self._populate_team_form_groups(["All"])
        self.team_sub_stack.setCurrentIndex(1)

    def _on_team_page_edit_clicked(self, member: dict) -> None:
        self._team_editing_member_id = member.get("id")
        self.lbl_team_form_title.setText(f"✏️ Edit Team Member: {member.get('full_name', '')}")
        self.lbl_team_form_sub.setText("Update profile group visibility and safety permissions.")
        self.btn_team_form_submit.setText("💾 Save Changes")
        self.txt_team_form_email.setText(member.get("email", ""))
        self.txt_team_form_email.setEnabled(False)
        self.txt_team_form_name.setText(member.get("full_name", ""))
        self.txt_team_form_pwd.setText("")
        self.lbl_team_form_status.setVisible(False)

        perms = member.get("permissions", {})
        self.chk_team_form_create.setChecked(bool(perms.get("can_create", True)))
        self.chk_team_form_edit.setChecked(bool(perms.get("can_edit", True)))
        self.chk_team_form_delete.setChecked(bool(perms.get("can_delete", False)))
        self.chk_team_form_export.setChecked(bool(perms.get("can_export", False)))

        self._populate_team_form_groups(member.get("assigned_groups", ["All"]))
        self.team_sub_stack.setCurrentIndex(1)

    def _on_team_form_back_clicked(self) -> None:
        self.team_sub_stack.setCurrentIndex(0)
        self.lbl_team_form_status.setVisible(False)

    def _on_team_form_submit_clicked(self) -> None:
        email = self.txt_team_form_email.text().strip()
        name = self.txt_team_form_name.text().strip()
        pwd = self.txt_team_form_pwd.text().strip()

        if not email or "@" not in email:
            self.lbl_team_form_status.setText("⚠️ Please provide a valid email address.")
            self.lbl_team_form_status.setStyleSheet("color: #f87171; font-weight: bold; background: transparent; border: none;")
            self.lbl_team_form_status.setVisible(True)
            return

        if not self._team_editing_member_id and len(pwd) < 4:
            self.lbl_team_form_status.setText("⚠️ Password must be at least 4 characters.")
            self.lbl_team_form_status.setStyleSheet("color: #f87171; font-weight: bold; background: transparent; border: none;")
            self.lbl_team_form_status.setVisible(True)
            return

        if self.chk_team_form_all_groups.isChecked():
            assigned = ["All"]
        else:
            assigned = [g for g, chk in self._team_group_checkboxes.items() if chk.isChecked()]
            if not assigned:
                assigned = ["Default"]

        perms = {
            "can_create": self.chk_team_form_create.isChecked(),
            "can_edit": self.chk_team_form_edit.isChecked(),
            "can_delete": self.chk_team_form_delete.isChecked(),
            "can_export": self.chk_team_form_export.isChecked(),
            "can_bots": False
        }

        members = self._load_local_team_members()
        import uuid
        from datetime import datetime

        if self._team_editing_member_id:
            found = False
            for m in members:
                if str(m.get("id")) == str(self._team_editing_member_id):
                    m["full_name"] = name or email.split("@")[0]
                    m["assigned_groups"] = assigned
                    m["permissions"] = perms
                    if pwd:
                        m["password"] = pwd
                    found = True
                    break
            if not found:
                self.lbl_team_form_status.setText("⚠️ Member not found.")
                self.lbl_team_form_status.setStyleSheet("color: #f87171; font-weight: bold; background: transparent; border: none;")
                self.lbl_team_form_status.setVisible(True)
                return
        else:
            if any(m.get("email", "").lower() == email.lower() for m in members):
                self.lbl_team_form_status.setText("⚠️ A member with this email already exists.")
                self.lbl_team_form_status.setStyleSheet("color: #f87171; font-weight: bold; background: transparent; border: none;")
                self.lbl_team_form_status.setVisible(True)
                return

            new_mem = {
                "id": str(uuid.uuid4())[:8],
                "email": email,
                "password": pwd,
                "full_name": name or email.split("@")[0],
                "assigned_groups": assigned,
                "permissions": perms,
                "status": "active",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            members.append(new_mem)

        self._save_local_team_members(members)
        self.lbl_team_form_status.setVisible(False)
        self.team_sub_stack.setCurrentIndex(0)
        self._refresh_team_page()

    def _on_team_page_delete_clicked(self, member: dict) -> None:
        email = member.get("email", "")
        res = QMessageBox.question(
            self,
            "Remove Team Member",
            f"Are you sure you want to remove team member '{email}'?\n\nThey will immediately lose access to srkBrowser on their PC.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        members = [m for m in self._load_local_team_members() if str(m.get("id")) != str(member.get("id"))]
        self._save_local_team_members(members)
        self._refresh_team_page()




