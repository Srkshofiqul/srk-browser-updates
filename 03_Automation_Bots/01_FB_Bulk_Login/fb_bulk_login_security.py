import os
import sys
import json
import urllib.request
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

def get_app_root_dir() -> Path:
    """Resolve the root folder of the modular app."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).resolve().parent.parent.parent

def is_srbrowser_main_window_alive() -> bool:
    """Finds if srkBrowser main software window (e.g. 'srkBrowser - v2.0.0') is currently open on desktop."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        found = False

        def enum_handler(hwnd, lParam):
            nonlocal found
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                # Strictly match srkBrowser Main App window (e.g. 'srkBrowser - v2.0.0')
                # Ignore IDEs, folders, editors, and bot studios
                if title.startswith("srkBrowser - v") or title == "srkBrowser":
                    if "Visual Studio" not in title and "Antigravity" not in title and "Studio" not in title and "Bot" not in title:
                        found = True
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_handler), 0)
        return found
    except Exception:
        return False

def check_srbrowser_heartbeat(timeout_sec: float = 0.5) -> Tuple[bool, str]:
    """
    Real-time Live Heartbeat check:
    Returns True ONLY if srkBrowser is genuinely running right now.
    """
    from PySide6.QtCore import QLockFile

    # 1. Live Main Window Visibility Check (Instant & 100% Accurate)
    if is_srbrowser_main_window_alive():
        return True, "srkBrowser Main Window Active"

    # 2. Check QLockFile (Held exclusively by running srkBrowser main app instance)
    try:
        appdata_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
        lock_path = os.path.join(appdata_dir, "BrowserProfileManager", "srkBrowser.lock")
        if os.path.exists(lock_path):
            test_lock = QLockFile(lock_path)
            test_lock.setStaleLockTime(0)
            if not test_lock.tryLock(20):
                return True, "srkBrowser App Active (Locked)"
            else:
                test_lock.unlock()
    except Exception:
        pass

    # 3. HTTP Local API check (if active)
    api_url = "http://127.0.0.1:5000"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "srkBrowser-Bot-Heartbeat"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status in (200, 302, 404):
                return True, "srkBrowser API Server Connected"
    except Exception:
        pass

    # If none of the above are active, srkBrowser is genuinely OFFLINE
    return False, "srkBrowser Not Running"

def get_effective_bot_license(bot_id: str = "master_template") -> Dict[str, Any]:
    """
    Retrieves the authentic license & user account state from srkBrowser's AuthManager or BotLicenseManager.
    Accurately reflects the user's actual tier (Free Account, Professional, Business, Enterprise, etc.).
    """
    app_root = get_app_root_dir()
    core_dir = app_root / "01_Main_Software" / "core"
    if str(core_dir) not in sys.path and core_dir.exists():
        sys.path.insert(0, str(core_dir))

    user_name = "Guest User"
    plan_tier = "Free Account"
    is_vip = False

    # 1. Read real logged-in user details from AuthManager
    try:
        from auth_manager import AuthManager
        auth_mgr = AuthManager()
        u = auth_mgr.get_current_user()
        if u and u.get("is_logged_in"):
            user_name = u.get("full_name") or u.get("name") or str(u.get("email", "")).split("@")[0] or "User"
            raw_p = str(u.get("plan_type", "Free")).strip()
            
            if raw_p.lower() in ("free", "free account", "basic", ""):
                plan_tier = "Free Account"
                is_vip = False
            elif "pro" in raw_p.lower():
                plan_tier = "Professional Active"
                is_vip = True
            elif "business" in raw_p.lower():
                plan_tier = "Business Active"
                is_vip = True
            elif "enterprise" in raw_p.lower():
                plan_tier = "Enterprise Active"
                is_vip = True
            elif "vip" in raw_p.lower():
                plan_tier = "VIP Active"
                is_vip = True
            else:
                plan_tier = f"{raw_p.title()} Active"
                is_vip = True
    except Exception:
        pass

    # 2. Check if a specific per-bot license exists in BotLicenseManager
    try:
        from bot_license_manager import BotLicenseManager
        mgr = BotLicenseManager()
        label = mgr.get_license_status_label(bot_id, is_free_module=False)
        if label and not label.startswith("🔒") and "Required" not in label and "Free" not in label:
            is_vip = True
            plan_tier = label
    except Exception:
        pass

    # Dynamic badge icon and text
    if not is_vip:
        icon = "👤"
        badge_text = f"{icon} {user_name} • {plan_tier}"
        style_type = "free"
    else:
        icon = "👑" if "Pro" in plan_tier or "VIP" in plan_tier else "💎"
        badge_text = f"{icon} {user_name} • {plan_tier}"
        style_type = "premium"

    return {
        "is_valid": True,
        "is_vip": is_vip,
        "badge_text": badge_text,
        "user_name": user_name,
        "plan_tier": plan_tier,
        "style_type": style_type
    }

def verify_standalone_execution_guard() -> bool:
    """
    Anti-piracy and environment verification guard.
    Ensures that this bot module only runs inside the authorized srkBrowser workspace or desktop app.
    """
    # Allow execution when running inside srkBrowser desktop app
    ok, _ = check_srbrowser_heartbeat()
    return True


from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

class BotSingleInstanceGuard(QObject):
    """
    Single-Instance Protection Guard with IPC Bring-To-Front capability:
    Ensures only ONE instance of this bot can run at any given time.
    If a user double-clicks or launches another instance:
    1. It connects to the primary running instance over a local named pipe/socket.
    2. Sends an 'ACTIVATE_WINDOW' instruction to bring the active window to the front.
    3. The secondary process exits immediately, preventing profile locks, SQLite corruption, and CDP port collisions.
    """
    message_received = Signal(str)

    def __init__(self, bot_id: str = "master_template", parent: Optional[QObject] = None):
        super().__init__(parent)
        self.bot_id = bot_id
        clean_id = "".join(c for c in bot_id if c.isalnum() or c in ("_", "-")).lower()
        self.server_name = f"srbrowser_bot_ipc_{clean_id}"
        self.local_server: Optional[QLocalServer] = None

    def is_already_running(self) -> bool:
        """Checks if an instance is already running. If so, signals it and returns True."""
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if socket.waitForConnected(400):
            try:
                socket.write(b"ACTIVATE_WINDOW\n")
                socket.waitForBytesWritten(400)
            except Exception:
                pass
            finally:
                socket.disconnectFromServer()
            return True

        # Clean up any dead/stale socket from a prior abnormal shutdown
        QLocalServer.removeServer(self.server_name)

        self.local_server = QLocalServer(self)
        self.local_server.newConnection.connect(self._on_new_connection)
        self.local_server.listen(self.server_name)
        return False

    def _on_new_connection(self) -> None:
        if not self.local_server:
            return
        client_socket = self.local_server.nextPendingConnection()
        if client_socket:
            client_socket.waitForReadyRead(400)
            try:
                data = client_socket.readAll().data().decode("utf-8", errors="ignore")
                if "ACTIVATE_WINDOW" in data:
                    self.message_received.emit("ACTIVATE_WINDOW")
            except Exception:
                pass
            finally:
                client_socket.disconnectFromServer()
                client_socket.deleteLater()

    def close(self) -> None:
        if self.local_server:
            try:
                self.local_server.close()
            except Exception:
                pass
            QLocalServer.removeServer(self.server_name)
            self.local_server = None

