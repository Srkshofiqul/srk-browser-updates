"""
Browser Profile Manager - Browser Launcher & Process Tracking Module
Python 3.13 / PySide6 Desktop Application
"""

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal, QTimer

from utils import get_system_browsers
from automation import ensure_profile_session_persistence
from config import load_settings


VIBRANT_PALETTES = [
    ("#1e3a8a", "#2563eb", "#60a5fa", "#ffffff"), # Bright Royal Blue
    ("#064e3b", "#16a34a", "#4ade80", "#ffffff"), # Bright Emerald Green
    ("#581c87", "#9333ea", "#c084fc", "#ffffff"), # Bright Purple
    ("#7c2d12", "#ea580c", "#fb923c", "#ffffff"), # Bright Orange
    ("#831843", "#db2777", "#f472b6", "#ffffff"), # Bright Pink
    ("#164e63", "#0891b2", "#22d3ee", "#ffffff"), # Bright Cyan
    ("#713f12", "#ca8a04", "#fde047", "#ffffff"), # Bright Gold
    ("#881337", "#e11d48", "#fb7185", "#ffffff"), # Bright Crimson Rose
]


SMART_PALETTE = [
    "#6366f1",  # Indigo
    "#06b6d4",  # Cyan
    "#10b981",  # Emerald Green
    "#f97316",  # Vibrant Orange
    "#ec4899",  # Electric Pink
    "#8b5cf6",  # Violet / Purple
    "#f59e0b",  # Golden Amber
    "#ef4444",  # Crimson Red
    "#14b8a6",  # Teal Sea
    "#3b82f6",  # Sapphire Blue
    "#d946ef",  # Fuchsia
    "#84cc16",  # Lime Green
]


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    try:
        hex_str = str(hex_str).lstrip("#")
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (2, 132, 199)


def render_smart_profile_badge_image(text: str, size: int, color_hex: str = None, profile_num: int = 1):
    """
    Render ultra-high-contrast, razor-sharp Profile Number Badge:
    - Dark obsidian high-contrast background (#12121c) to guarantee 100% readability on both Light & Dark Windows taskbars
    - Thick glowing border in the profile's vibrant theme color
    - Extra-large bold white typography with solid black stroke outline
    - Unsharp mask edge sharpening on small taskbar icon sizes (<= 48px)
    """
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter

        BASE_S = 512
        img = Image.new("RGBA", (BASE_S, BASE_S), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        clean_text = str(text).replace("Profile", "").replace("#", "").strip()
        if not clean_text:
            clean_text = "1"

        if not color_hex or color_hex in ["#0284c7", "#38bdf8", "SkyBlue", "Default"]:
            try:
                num_val = int(clean_text)
            except Exception:
                num_val = profile_num
            color_hex = SMART_PALETTE[(num_val - 1) % len(SMART_PALETTE)]

        r, g, b = hex_to_rgb(color_hex)

        # 1. Dark Obsidian High-Contrast Container (#12121c)
        corner_r = int(BASE_S * 0.20)
        margin = 10
        box = [margin, margin, BASE_S - margin, BASE_S - margin]

        # Heavy drop shadow
        draw.rounded_rectangle(
            [margin - 4, margin + 4, BASE_S - margin + 4, BASE_S - margin + 8],
            radius=corner_r + 4,
            fill=(0, 0, 0, 220)
        )

        # Deep Dark Obsidian Tile
        draw.rounded_rectangle(box, radius=corner_r, fill=(18, 18, 28, 255))

        # Thick Vibrant Profile-Color Border (Glow effect)
        draw.rounded_rectangle(box, radius=corner_r, outline=(r, g, b, 255), width=26)

        # Inner subtle contrast ring
        inner_box = [margin + 20, margin + 20, BASE_S - margin - 20, BASE_S - margin - 20]
        draw.rounded_rectangle(inner_box, radius=corner_r - 8, outline=(255, 255, 255, 140), width=6)

        # 2. Typography - Extra Bold with Solid Black Stroke
        n_len = len(clean_text)
        if n_len == 1:
            base_font_ratio = 0.72
        elif n_len == 2:
            base_font_ratio = 0.62
        elif n_len == 3:
            base_font_ratio = 0.50
        elif n_len == 4:
            base_font_ratio = 0.40
        else:
            base_font_ratio = 0.32

        font_size = int(BASE_S * base_font_ratio)
        font = None
        for fn in ["impact.ttf", "ariblk.ttf", "arialbd.ttf", "segoeuib.ttf", "tahomabd.ttf"]:
            try:
                font = ImageFont.truetype(fn, font_size)
                break
            except Exception:
                pass
        if font is None:
            font = ImageFont.load_default()

        # Measure text
        bbox = draw.textbbox((0, 0), clean_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # Constrain width so text never touches border
        max_tw = (BASE_S - margin * 2) * 0.82
        if tw > max_tw:
            font_size = int(font_size * max_tw / tw)
            for fn in ["impact.ttf", "ariblk.ttf", "arialbd.ttf", "segoeuib.ttf"]:
                try:
                    font = ImageFont.truetype(fn, font_size)
                    break
                except Exception:
                    pass
            bbox = draw.textbbox((0, 0), clean_text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

        # Center coordinates
        tx = (BASE_S - tw) / 2 - bbox[0]
        ty = (BASE_S - th) / 2 - bbox[1] - 4

        # Heavy black stroke for razor-sharp digit definition
        stroke_w = max(5, int(font_size * 0.08))
        draw.text(
            (tx, ty), 
            clean_text, 
            fill=(255, 255, 255, 255), 
            stroke_width=stroke_w, 
            stroke_fill=(0, 0, 0, 255), 
            font=font
        )

        if size == BASE_S:
            return img

        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        if size <= 48:
            # Apply unsharp mask sharpening so low-res taskbar icons stay crisp
            resized = resized.filter(ImageFilter.UnsharpMask(radius=1.2, percent=160, threshold=3))
        return resized
    except Exception as e:
        print(f"[Icon Render Error] {e}")
        return None


def render_toolbar_badge_image(text: str, size: int, color_hex: str = None, profile_num: int = 1) -> Any:
    """Render square box badge image."""
    return render_smart_profile_badge_image(text, size, color_hex, profile_num)


def create_badge_extension(profile_dir: Path, profile_data: Dict[str, Any]) -> str:
    """Remove badge extension completely so no extensions or toolbar icons appear."""
    try:
        ext_dir = profile_dir / "badge_extension"
        if ext_dir.exists():
            import shutil
            shutil.rmtree(ext_dir, ignore_errors=True)
    except Exception:
        pass
    return ""


def generate_unpacked_extension_ids(folder_path: str) -> List[str]:
    """Generate candidate 32-character Chromium extension IDs for an unpacked extension directory."""
    import hashlib
    import base64
    ids = []

    folder = Path(folder_path).resolve()
    manifest_file = folder / "manifest.json"

    # 1. Check if manifest has explicit "key"
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            pub_key = data.get("key")
            if pub_key:
                key_bytes = base64.b64decode(pub_key)
                h = hashlib.sha256(key_bytes).hexdigest()[:32]
                eid = ''.join(chr(ord('a') + int(c, 16)) for c in h)
                ids.append(eid)
                return ids
        except Exception:
            pass

    # 2. Path variations for Chromium on Windows
    native_str = str(folder)
    slash_str = native_str.replace("\\", "/")

    variations = [
        native_str,
        slash_str,
        native_str.lower(),
        slash_str.lower()
    ]

    for var in variations:
        h = hashlib.sha256(var.encode("utf-8")).hexdigest()[:32]
        eid = ''.join(chr(ord('a') + int(c, 16)) for c in h)
        if eid not in ids:
            ids.append(eid)

    return ids


def suppress_all_chromium_prompts(profile_dir: Path) -> None:
    """Pre-configure Preferences, Local State, and initial_preferences to completely silence all startup prompts."""
    # Fast path: If already configured on previous launch, skip heavy disk I/O
    init_pref = profile_dir / "initial_preferences"
    local_state_path = profile_dir / "Local State"
    if init_pref.exists() and local_state_path.exists() and init_pref.stat().st_size > 0:
        return

    pref_paths = [
        profile_dir / "Default" / "Preferences",
        profile_dir / "Default" / "Secure Preferences",
        profile_dir / "Preferences",
        profile_dir / "Secure Preferences"
    ]
    for pref_path in pref_paths:
        try:
            pref_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if pref_path.exists():
                try:
                    with open(pref_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            if not isinstance(data, dict):
                data = {}

            # 1. Disable startup prompts & default browser check
            if "browser" not in data or not isinstance(data["browser"], dict):
                data["browser"] = {}
            data["browser"]["has_seen_welcome_page"] = True
            data["browser"]["check_default_browser"] = False
            data["browser"]["has_seen_win10_promo"] = True
            data["browser"]["should_reset_check_default_browser"] = False
            data["browser"]["default_browser_infobar_last_declined"] = "13360000000000000"

            # 2. Disable background mode & startup boost
            if "background_mode" not in data or not isinstance(data["background_mode"], dict):
                data["background_mode"] = {}
            data["background_mode"]["enabled"] = False
            data["background_mode"]["never_prompt"] = True
            data["background_mode"]["allow_start_on_startup"] = False

            if "startup_boost" not in data or not isinstance(data["startup_boost"], dict):
                data["startup_boost"] = {}
            data["startup_boost"]["enabled"] = False

            if "system" not in data or not isinstance(data["system"], dict):
                data["system"] = {}
            data["system"]["startup_boost_enabled"] = False

            # Explicitly neutralize internal Chromium LaunchOnStartup infobar
            data["launch_on_login"] = {
                "foreground": {"enabled": False},
                "infobar_accepted": True,
                "infobar_declined_count": 99,
                "infobar_last_declined_time": "13360000000000000"
            }

            # 3. Clean profile avatar & clean exit flags
            if "profile" not in data or not isinstance(data["profile"], dict):
                data["profile"] = {}
            data["profile"]["has_seen_welcome_page"] = True
            data["profile"]["exit_type"] = "Normal"
            data["profile"]["exited_cleanly"] = True
            data["profile"]["avatar_index"] = 26
            data["profile"]["name"] = ""
            data["profile"]["using_default_name"] = True
            data["profile"]["using_default_avatar"] = True

            if "signin" not in data or not isinstance(data["signin"], dict):
                data["signin"] = {}
            data["signin"]["allowed"] = False
            data["signin"]["allowed_on_next_startup"] = False

            # 4. Enterprise policy suppressions
            if "policy" not in data or not isinstance(data["policy"], dict):
                data["policy"] = {}
            data["policy"]["StartupBoostEnabled"] = False
            data["policy"]["BackgroundModeEnabled"] = False
            data["policy"]["PromotionsEnabled"] = False
            data["policy"]["DefaultBrowserSettingEnabled"] = False

            with open(pref_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # Local State suppression
    try:
        ls_data = {}
        if local_state_path.exists():
            try:
                with open(local_state_path, "r", encoding="utf-8") as f:
                    ls_data = json.load(f)
            except Exception:
                ls_data = {}
        ls_data["background_mode"] = {"enabled": False, "never_prompt": True, "allow_start_on_startup": False}
        ls_data["startup_boost"] = {"enabled": False}
        ls_data["system"] = {"startup_boost_enabled": False}
        ls_data["launch_on_login"] = {
            "foreground": {"enabled": False},
            "infobar_accepted": True,
            "infobar_declined_count": 99,
            "infobar_last_declined_time": "13360000000000000"
        }
        if "browser" not in ls_data:
            ls_data["browser"] = {}
        ls_data["browser"]["has_seen_welcome_page"] = True
        ls_data["browser"]["check_default_browser"] = False
        ls_data["browser"]["has_seen_win10_promo"] = True
        with open(local_state_path, "w", encoding="utf-8") as f:
            json.dump(ls_data, f, indent=2)
    except Exception:
        pass

    # Profile-level initial_preferences & master_preferences to enforce silent behavior
    try:
        init_data = {
            "distribution": {
                "import_bookmarks": False,
                "import_history": False,
                "import_home_page": False,
                "import_search_engine": False,
                "import_saved_passwords": False,
                "do_not_create_desktop_shortcut": True,
                "do_not_create_quick_launch_shortcut": True,
                "do_not_create_taskbar_shortcut": True,
                "do_not_register_for_update_launch": True,
                "make_chrome_default": False,
                "make_chrome_default_for_user": False,
                "suppress_first_run_bubble": True,
                "suppress_first_run_default_browser_prompt": True,
                "suppress_first_run_win10_prompt": True,
                "skip_first_run_ui": True,
                "show_welcome_page": False,
                "suppress_check_default_browser_infobar": True
            },
            "background_mode": {
                "enabled": False,
                "never_prompt": True,
                "allow_start_on_startup": False
            },
            "startup_boost": {
                "enabled": False
            },
            "system": {
                "startup_boost_enabled": False
            },
            "launch_on_login": {
                "foreground": {"enabled": False},
                "infobar_accepted": True,
                "infobar_declined_count": 99,
                "infobar_last_declined_time": "13360000000000000"
            },
            "browser": {
                "has_seen_welcome_page": True,
                "check_default_browser": False,
                "has_seen_win10_promo": True,
                "should_reset_check_default_browser": False,
                "default_browser_infobar_last_declined": "13360000000000000"
            },
            "signin": {
                "allowed": False,
                "allowed_on_next_startup": False
            },
            "profile": {
                "has_seen_welcome_page": True,
                "avatar_index": 26,
                "name": "",
                "using_default_name": True,
                "using_default_avatar": True
            }
        }
        with open(profile_dir / "initial_preferences", "w", encoding="utf-8") as f:
            json.dump(init_data, f, indent=2)
        with open(profile_dir / "master_preferences", "w", encoding="utf-8") as f:
            json.dump(init_data, f, indent=2)
    except Exception:
        pass

    # Clean any unwanted Windows Startup Registry keys
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                for subk in ["Chromium", "Google Chrome", "chrome", "chromium"]:
                    try:
                        winreg.DeleteValue(key, subk)
                    except Exception:
                        pass
        except Exception:
            pass


def auto_pin_extensions_in_profile(profile_dir: Path, valid_ext_paths: List[str]) -> None:
    """Pre-configure profile Preferences to automatically pin loaded extensions to Chrome's top toolbar."""
    target_ids = []
    if valid_ext_paths:
        for ext_p in valid_ext_paths:
            cands = generate_unpacked_extension_ids(ext_p)
            for c in cands:
                if c not in target_ids:
                    target_ids.append(c)

    # Always ensure the deterministic badge extension ID is included for toolbar pinning
    badge_ext_id = "jhhkklodcogmmgmmlgildphlbmeegnje"
    if badge_ext_id not in target_ids:
        target_ids.append(badge_ext_id)

    pref_path = profile_dir / "Default" / "Preferences"
    try:
        pref_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if pref_path.exists():
            try:
                with open(pref_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        if not isinstance(data, dict):
            data = {}

        if "extensions" not in data or not isinstance(data["extensions"], dict):
            data["extensions"] = {}

        # Fast path: if already pinned, skip disk write
        curr_pinned = data["extensions"].get("pinned_extensions", [])
        if curr_pinned == target_ids and data.get("background_mode", {}).get("enabled") is False:
            return

        data["extensions"]["pinned_extensions"] = target_ids
        data["extensions"]["toolbar"] = list(target_ids)

        # Disable Chromium auto-start background prompt
        if "background_mode" not in data or not isinstance(data["background_mode"], dict):
            data["background_mode"] = {}
        data["background_mode"]["enabled"] = False
        data["background_mode"]["allow_start_on_startup"] = False

        # Disable Google account signin & avatar button on toolbar
        if "signin" not in data or not isinstance(data["signin"], dict):
            data["signin"] = {}
        data["signin"]["allowed"] = False
        data["signin"]["allowed_on_next_startup"] = False

        if "profile" not in data or not isinstance(data["profile"], dict):
            data["profile"] = {}
        data["profile"]["avatar_index"] = 26
        data["profile"]["name"] = ""
        data["profile"]["using_default_name"] = True
        data["profile"]["using_default_avatar"] = True

        # Force Chrome Enterprise Policy ExtensionSettings for badge extension only
        if "policy" not in data or not isinstance(data["policy"], dict):
            data["policy"] = {}
        if "extension_settings" not in data["policy"] or not isinstance(data["policy"]["extension_settings"], dict):
            data["policy"]["extension_settings"] = {}

        for tid in target_ids:
            data["policy"]["extension_settings"][tid] = {"toolbar_pin": "force_pinned"}

        with open(pref_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def generate_profile_icon_ico(text: str, ico_path: Path, color_hex: str = "#89b4fa", profile_num: int = 1) -> bool:
    try:
        sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
        images = []
        for size in sizes:
            img = render_smart_profile_badge_image(text, size, color_hex, profile_num)
            if img:
                images.append(img)
            
        if images:
            images[0].save(ico_path, format="ICO", append_images=images[1:])
            return True
    except Exception:
        pass
    return False


def apply_window_icon_win32(pid: int, ico_path: Path, num_text: str = "") -> None:
    if os.name != "nt" or not ico_path.exists():
        return

    main_pid = os.getpid()

    def _worker():
        import time
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010

        hIcon = user32.LoadImageW(
            None,
            str(ico_path.resolve()),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE
        )
        if not hIcon:
            return

        # Find target process and all child processes created by Chromium for this profile
        target_pids = {pid}
        try:
            import psutil
            parent_proc = psutil.Process(pid)
            for child in parent_proc.children(recursive=True):
                target_pids.add(child.pid)
        except Exception:
            pass

        tag_bracket = f"[{num_text}]" if num_text else ""
        tag_hash = f"#{num_text}" if num_text else ""

        for _ in range(8):
            time.sleep(0.25)
            hwnds = []

            def EnumWindowsProc(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    lpdwProcessId = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdwProcessId))
                    
                    # Strictly NEVER touch the main srkBrowser application window
                    if lpdwProcessId.value == main_pid:
                        return True

                    # 1. Match if HWND belongs strictly to this profile's browser process tree
                    if lpdwProcessId.value in target_pids:
                        hwnds.append(hwnd)
                    # 2. Or match strictly if title contains this exact profile number
                    elif tag_bracket or tag_hash:
                        try:
                            buf = ctypes.create_unicode_buffer(256)
                            user32.GetWindowTextW(hwnd, buf, 256)
                            t_val = buf.value
                            if t_val and (tag_bracket in t_val or tag_hash in t_val) and "srkBrowser - v" not in t_val and "srkBrowser - v" not in t_val:
                                hwnds.append(hwnd)
                        except Exception:
                            pass
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(EnumWindowsProc), 0)

            if hwnds:
                for hwnd in hwnds:
                    # Apply specific icon ONLY to this profile's window
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hIcon)
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hIcon)
                    try:
                        user32.SetPropW(hwnd, "AppUserModelID", f"srkBrowser.Profile.{num_text}")
                    except Exception:
                        pass
                break

    import threading
    threading.Thread(target=_worker, daemon=True).start()


def create_cookie_injector_extension(profile_dir: Path, profile_data: Dict[str, Any]) -> str:
    """
    Creates/updates a dedicated Chrome Extension inside profile_dir/sr_cookie_injector
    containing cookies_payload.json for instant 100% cookie and session injection on launch.
    Always updates cookies_payload.json with fresh database tokens.
    """
    cookie_val = str(profile_data.get("cookie", "") or "").strip()
    cookies_list = profile_data.get("cookies_json", [])
    if not cookie_val and not cookies_list:
        return ""

    try:
        ext_dir = profile_dir / "sr_cookie_injector"
        ext_dir.mkdir(parents=True, exist_ok=True)

        manifest_src = Path(__file__).parent / "extensions" / "sr_cookie_injector" / "manifest.json"
        bg_src = Path(__file__).parent / "extensions" / "sr_cookie_injector" / "background.js"

        import shutil
        if manifest_src.exists():
            shutil.copy2(manifest_src, ext_dir / "manifest.json")
        if bg_src.exists():
            shutil.copy2(bg_src, ext_dir / "background.js")

        payload = {
            "cookie": cookie_val,
            "cookies": cookies_list,
            "profile_id": profile_data.get("id", ""),
            "updated_at": str(time.time())
        }

        with open(ext_dir / "cookies_payload.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return str(ext_dir.resolve())
    except Exception as e:
        print(f"[COOKIE INJECTOR EXTENSION ERROR]: {e}")
        return ""


def create_profile_inspector_extension(profile_dir: Path, profile_data: Dict[str, Any]) -> str:
    """
    Creates/updates a lightweight Manifest V3 extension inside profile_dir/sr_profile_inspector
    that displays a smart toolbar badge and popup with profile and proxy information.
    """
    try:
        ext_dir = profile_dir / "sr_profile_inspector"
        ext_dir.mkdir(parents=True, exist_ok=True)

        src_dir = Path(__file__).parent / "extensions" / "sr_profile_inspector"
        if src_dir.exists():
            import shutil
            for src_f in src_dir.iterdir():
                if src_f.is_file():
                    shutil.copy2(src_f, ext_dir / src_f.name)

        # Write dynamic profile_info.json for this specific profile
        num_clean = str(profile_data.get("number", "1")).replace("Profile", "").replace("#", "").strip()
        info = {
            "id": profile_data.get("id", ""),
            "number": num_clean or "1",
            "name": profile_data.get("name", f"Profile {num_clean}"),
            "group": profile_data.get("group", "Default"),
            "proxy_type": profile_data.get("proxy_type", "None"),
            "proxy_host": profile_data.get("proxy_host", ""),
            "proxy_port": profile_data.get("proxy_port", ""),
            "color": profile_data.get("color", "#8b5cf6")
        }
        with open(ext_dir / "profile_info.json", "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        return str(ext_dir.resolve())
    except Exception as e:
        print(f"[PROFILE INSPECTOR EXTENSION ERROR]: {e}")
        return ""


def inject_cookies_to_chromium_profile(profile_folder: Path, cookie_str: str) -> bool:
    """Parse cookie string and inject non-encrypted cookies into Chromium SQLite Cookies DB."""
    if not cookie_str or not cookie_str.strip():
        return False

    default_dir = profile_folder / "Default"
    network_dir = default_dir / "Network"
    network_dir.mkdir(parents=True, exist_ok=True)
    db_path = network_dir / "Cookies"

    import sqlite3, time
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cookies (
                creation_utc INTEGER NOT NULL,
                host_key TEXT NOT NULL,
                top_frame_site_key TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                encrypted_value BLOB NOT NULL DEFAULT x'',
                path TEXT NOT NULL DEFAULT '/',
                expires_utc INTEGER NOT NULL,
                is_secure INTEGER NOT NULL DEFAULT 0,
                is_httponly INTEGER NOT NULL DEFAULT 0,
                has_expires INTEGER NOT NULL DEFAULT 1,
                is_persistent INTEGER NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 1,
                samesite INTEGER NOT NULL DEFAULT -1,
                source_scheme INTEGER NOT NULL DEFAULT 2,
                source_port INTEGER NOT NULL DEFAULT 443,
                is_same_party INTEGER NOT NULL DEFAULT 0,
                last_access_utc INTEGER NOT NULL,
                last_update_utc INTEGER NOT NULL,
                PRIMARY KEY (host_key, name, path)
            )
        """)

        now_micros = int((time.time() + 11644473600) * 1000000)
        exp_micros = now_micros + (365 * 86400 * 1000000)

        is_fb_str = any(k in cookie_str for k in ["c_user", "cuser", "datr", "xs", "sb", "fr"])
        fb_keys = {"c_user", "cuser", "xs", "fr", "datr", "sb", "presence", "wd", "locale", "ps_l", "ps_n", "vpd", "dpr", "m_page_voice", "usida", "act", "checkpoint", "spin"}

        cols = [r[1] for r in cursor.execute("PRAGMA table_info(cookies)").fetchall()]

        items = cookie_str.split(";")
        for item in items:
            if "=" in item:
                parts = item.strip().split("=", 1)
                k_clean = parts[0].strip()
                v_clean = parts[1].strip()
                if k_clean and v_clean:
                    if k_clean in fb_keys or is_fb_str:
                        domain = ".facebook.com"
                    elif any(gk in k_clean.lower() for gk in ["sid", "hsid", "ssid", "apisid", "sapisid", "nid", "1p_jar"]):
                        domain = ".google.com"
                    else:
                        domain = ".facebook.com"

                    is_httponly = 1 if k_clean in ["c_user", "xs", "datr", "sb", "fr", "SID", "HSID", "SSID"] else 0
                    is_secure = 1

                    if cols:
                        col_defaults = {
                            "creation_utc": now_micros,
                            "host_key": domain,
                            "top_frame_site_key": "",
                            "name": k_clean,
                            "value": v_clean,
                            "encrypted_value": b"",
                            "path": "/",
                            "expires_utc": exp_micros,
                            "is_secure": is_secure,
                            "is_httponly": is_httponly,
                            "last_access_utc": now_micros,
                            "last_update_utc": now_micros,
                            "has_expires": 1,
                            "is_persistent": 1,
                            "priority": 1,
                            "samesite": -1,
                            "source_scheme": 2,
                            "source_port": 443,
                            "source_type": 0,
                            "has_cross_site_ancestor": 0
                        }
                        present_cols = [c for c in cols if c in col_defaults]
                        placeholders = ", ".join(["?"] * len(present_cols))
                        col_names = ", ".join(present_cols)
                        values = [col_defaults[c] for c in present_cols]
                        cursor.execute(f"INSERT OR REPLACE INTO cookies ({col_names}) VALUES ({placeholders})", values)
                    else:
                        cursor.execute("""
                            INSERT OR REPLACE INTO cookies 
                            (creation_utc, host_key, top_frame_site_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly, last_access_utc, last_update_utc)
                            VALUES (?, ?, '', ?, ?, x'', '/', ?, ?, ?, ?, ?)
                        """, (now_micros, domain, k_clean, v_clean, exp_micros, is_secure, is_httponly, now_micros, now_micros))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[COOKIE INJECTION ERROR]: {e}")
        return False


class BrowserLauncher(QObject):
    """
    Manages browser process execution with dedicated user-data directories,
    proxy options, user-agent overrides, extension loaders, and start URLs.
    Includes asynchronous launch queue for zero-lag staggered opening and active polling timer.
    """

    process_opening = Signal(str)    # profile_id (queued / opening state)
    process_started = Signal(str)    # profile_id (running)
    process_syncing = Signal(str)    # profile_id (closing & syncing state)
    process_finished = Signal(str)   # profile_id (ready & idle state)
    launch_failed = Signal(str, str) # profile_id, error_msg

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        # Store dict mapping profile_id -> (subprocess.Popen, start_timestamp: float)
        self._active_processes: Dict[str, Tuple[subprocess.Popen, float]] = {}

        # Thread-safe persistent session tracking for crash / power-outage recovery
        self._session_lock = threading.Lock()
        self._persisted_cache: Optional[Dict[str, Any]] = None
        self._persisted_cache_time: float = 0.0

        # Asynchronous FIFO Launch Queue for smooth staggered opening (ixBrowser style)
        import queue
        self._launch_queue = queue.Queue()
        self._pending_launch_ids = set()
        self._worker_thread = threading.Thread(target=self._launch_worker, daemon=True)
        self._worker_thread.start()

        # Real-time process polling timer (checks process state every 1 second)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check_active_processes)
        self._timer.start()

    @property
    def active_processes(self) -> Dict[str, Tuple[subprocess.Popen, float]]:
        return self._active_processes

    def _get_active_sessions_file_path(self) -> Path:
        """Return persistent active sessions JSON file path."""
        try:
            from config import BASE_DIR
            return BASE_DIR / "active_sessions.json"
        except Exception:
            import os
            base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "BrowserProfileManager"
            base.mkdir(parents=True, exist_ok=True)
            return base / "active_sessions.json"

    def _load_persisted_active_sessions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Load crash-proof persistent active browser profile sessions with 500ms memory caching."""
        with self._session_lock:
            now = time.time()
            if not force_refresh and self._persisted_cache is not None and (now - self._persisted_cache_time < 0.5):
                return dict(self._persisted_cache)

            fpath = self._get_active_sessions_file_path()
            if not fpath.exists():
                self._persisted_cache = {}
                self._persisted_cache_time = now
                return {}

            try:
                from utils import safe_read_json
                data = safe_read_json(fpath)
                if isinstance(data, dict):
                    sessions = data.get("sessions", data) if "sessions" in data and isinstance(data.get("sessions"), dict) else data
                    result = {str(k): v for k, v in sessions.items() if not str(k).startswith("_")}
                    self._persisted_cache = result
                    self._persisted_cache_time = now
                    return dict(result)
                elif isinstance(data, list):
                    result = {str(pid): {"start_time": now} for pid in data}
                    self._persisted_cache = result
                    self._persisted_cache_time = now
                    return dict(result)
            except Exception as e:
                print(f"[ACTIVE SESSIONS] Failed to load {fpath}: {e}")

            self._persisted_cache = {}
            self._persisted_cache_time = now
            return {}

    def _save_persisted_active_sessions(self, sessions: Dict[str, Any]) -> bool:
        """Atomically persist active sessions to disk to survive abrupt power cuts."""
        with self._session_lock:
            fpath = self._get_active_sessions_file_path()
            try:
                from utils import safe_write_json
                payload = {
                    "_last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "sessions": {str(k): v for k, v in sessions.items() if not str(k).startswith("_")}
                }
                ok = safe_write_json(fpath, payload)
                if ok:
                    self._persisted_cache = {str(k): v for k, v in sessions.items() if not str(k).startswith("_")}
                    self._persisted_cache_time = time.time()
                return ok
            except Exception as e:
                print(f"[ACTIVE SESSIONS] Failed to save {fpath}: {e}")
                return False

    def mark_session_active(self, profile_id: str, extra_meta: Optional[Dict[str, Any]] = None) -> None:
        """Mark a profile session as active on disk immediately upon launching."""
        try:
            sessions = self._load_persisted_active_sessions(force_refresh=True)
            pid_str = str(profile_id)
            meta = {
                "started_at": time.time(),
                "started_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if extra_meta and isinstance(extra_meta, dict):
                meta.update(extra_meta)
            sessions[pid_str] = meta
            self._save_persisted_active_sessions(sessions)
        except Exception as e:
            print(f"[ACTIVE SESSIONS] Error marking active {profile_id}: {e}")

    def mark_session_closed(self, profile_id: str) -> None:
        """Unmark a profile session from disk when closed by user or exited naturally."""
        try:
            sessions = self._load_persisted_active_sessions(force_refresh=True)
            pid_str = str(profile_id)
            if pid_str in sessions:
                sessions.pop(pid_str, None)
                self._save_persisted_active_sessions(sessions)
        except Exception as e:
            print(f"[ACTIVE SESSIONS] Error marking closed {profile_id}: {e}")

    def is_opening(self, profile_id: str) -> bool:
        """Check if profile is currently queued or in the process of launching."""
        return profile_id in self._pending_launch_ids

    def enqueue_launch(
        self,
        profile_id: str,
        browser_exe: str,
        profile_dir: Path,
        profile_data: Dict[str, Any],
        window_position: Optional[Tuple[int, int]] = None,
        window_size: Optional[Tuple[int, int]] = None,
        start_url: Optional[str] = None
    ) -> bool:
        """Non-blocking queue method for ixBrowser/AdsPower style smooth staggered profile launching."""
        if self.is_running(profile_id) or self.is_opening(profile_id):
            return False
        self._pending_launch_ids.add(profile_id)
        self.process_opening.emit(profile_id)
        self._launch_queue.put((
            profile_id, browser_exe, profile_dir, profile_data, window_position, window_size, start_url
        ))
        return True

    def _launch_worker(self) -> None:
        """Background worker thread processing launch queue with smooth staggered interval."""
        while True:
            try:
                task = self._launch_queue.get()
                if task is None:
                    break
                (pid, exe, pdir, pdata, win_pos, win_sz, s_url) = task

                if pid in self._active_processes:
                    self._pending_launch_ids.discard(pid)
                    self._launch_queue.task_done()
                    continue

                success, msg = self.launch_profile(exe, pdir, pdata, win_pos, win_sz, s_url)
                self._pending_launch_ids.discard(pid)
                if not success:
                    self.launch_failed.emit(pid, msg)

                self._launch_queue.task_done()
                # Smooth stagger delay (350ms) to ensure flat CPU/RAM consumption and 0% UI lag
                time.sleep(0.35)
            except Exception as e:
                print(f"[LAUNCH WORKER EXCEPTION]: {e}")
                time.sleep(0.2)

    def _check_active_processes(self) -> None:
        """Periodically poll active browser processes and notify UI as soon as they exit."""
        finished_ids = []
        now = time.time()

        for pid, (proc, start_t) in list(self._active_processes.items()):
            if proc.poll() is not None:
                duration_sec = max(1, int(now - start_t))
                finished_ids.append((pid, duration_sec))

        if not finished_ids:
            return

        parent = self.parent()
        active_token = ""
        if parent and hasattr(parent, "get_effective_cloud_token"):
            active_token = parent.get_effective_cloud_token()
        if not active_token:
            from cloud_sync import get_active_license_token
            active_token = get_active_license_token()

        for pid, duration in finished_ids:
            self._active_processes.pop(pid, None)
            self.mark_session_closed(pid)
            self.process_syncing.emit(pid)

            if parent and hasattr(parent, "profile_mgr"):
                try:
                    # 1. Extract fresh session cookies and structured multi-domain cookies
                    parent.profile_mgr.sync_profile_cookies_from_disk(pid)
                    parent.profile_mgr.record_launch_session(pid, duration)

                    # 2. Upload session ZIP in tracked background thread
                    p_folder = parent.profile_mgr.get_profile_folder(pid)
                    if active_token and p_folder and p_folder.exists():
                        import threading
                        from cloud_sync import upload_profile_session_zip, sync_tracker
                        sync_tracker.register_session_upload(pid)

                        def _tracked_session_upload(target_pid=pid, folder=p_folder, tok=active_token):
                            try:
                                upload_profile_session_zip(target_pid, folder, tok)
                            finally:
                                sync_tracker.mark_session_upload_complete(target_pid)

                        t_zip = threading.Thread(
                            target=_tracked_session_upload,
                            daemon=False
                        )
                        sync_tracker.track_thread(t_zip)
                        t_zip.start()
                except Exception:
                    pass

            # Gracefully notify UI after brief delay ensuring file locks are released
            QTimer.singleShot(1200, lambda target_pid=pid: self.process_finished.emit(target_pid))

        # 3. Single Batched Cloud Metadata Upload for all finished profiles
        if parent and hasattr(parent, "profile_mgr") and active_token:
            all_profs = parent.profile_mgr.get_all_profiles()
            if all_profs:
                import threading
                from cloud_sync import upload_profiles_cloud_backup, sync_tracker
                t_meta = threading.Thread(
                    target=upload_profiles_cloud_backup,
                    args=(all_profs, active_token),
                    daemon=False
                )
                sync_tracker.track_thread(t_meta)
                t_meta.start()


    def get_default_browser_executable(self) -> str:
        """Find an available browser executable path on the system, auto-downloading if missing."""
        system_browsers = get_system_browsers()
        if system_browsers:
            for label, exe in system_browsers.items():
                if os.path.exists(exe):
                    return exe
        try:
            from browser_downloader import ensure_portable_chromium_available
            parent_widget = self.parent() if hasattr(self, 'parent') else None
            exe = ensure_portable_chromium_available(parent=parent_widget)
            if exe and os.path.exists(exe):
                return exe
        except Exception:
            pass
        return ""

    def is_running(self, profile_id: str) -> bool:
        """Check if a browser process is currently active for the given profile ID."""
        pid_str = str(profile_id)
        if pid_str in self._active_processes:
            proc, _ = self._active_processes[pid_str]
            if proc.poll() is None:
                return True
            else:
                self._active_processes.pop(pid_str, None)
                self.mark_session_closed(pid_str)

        try:
            parent = self.parent()
            pm = getattr(parent, "profile_mgr", None) if parent else None
            if not pm:
                try:
                    from profile_manager import ProfileManager
                    pm = ProfileManager()
                except Exception:
                    pm = None
            if pm:
                p_folder = pm.get_profile_folder(pid_str)
                for fname in ["lockfile", "SingletonLock"]:
                    lf = p_folder / fname
                    if lf.exists():
                        try:
                            with open(lf, "a+b") as f:
                                pass
                        except (PermissionError, OSError):
                            return True
        except Exception:
            pass

        try:
            persisted = self._load_persisted_active_sessions()
            if pid_str in persisted:
                return True
        except Exception:
            pass

        return False

    def launch_profile(
        self,
        browser_exe: str,
        profile_dir: Path,
        profile_data: Dict[str, Any],
        window_position: Optional[Tuple[int, int]] = None,
        window_size: Optional[Tuple[int, int]] = None,
        start_url: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Launch the browser process with full configurations (proxy, user-agent, extensions, start URL).
        Supports custom desktop grid window positioning and sizing for Multi-Browser Action Synchronizer.
        """
        profile_id = profile_data["id"]

        portable_exe = self.get_default_browser_executable()
        if portable_exe and os.path.exists(portable_exe):
            browser_exe = portable_exe
        elif not browser_exe or not os.path.exists(browser_exe):
            return False, "Portable Chromium executable not found. Please verify chromium directory."

        # Ensure directory exists and session persistence configuration is intact
        profile_dir.mkdir(parents=True, exist_ok=True)
        suppress_all_chromium_prompts(profile_dir)
        try:
            default_cookies = profile_dir / "Default" / "Network" / "Cookies"
            if not default_cookies.exists() or default_cookies.stat().st_size == 0:
                from cloud_sync import download_and_restore_profile_session_zip
                download_and_restore_profile_session_zip(profile_id, profile_dir)

            ensure_profile_session_persistence(profile_dir)
            if profile_data.get("cookie"):
                inject_cookies_to_chromium_profile(profile_dir, str(profile_data.get("cookie")))

            # Clean leftover old tab session files to prevent opening stale unauthenticated tabs on launch
            sessions_dir = profile_dir / "Default" / "Sessions"
            if sessions_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(sessions_dir, ignore_errors=True)
                except Exception:
                    pass
        except Exception:
            pass

        # Clean leftover SingletonLock and lock files if inactive
        for lf_name in ["SingletonLock", "lockfile", "SingletonCookie", "SingletonSocket"]:
            lock_file = profile_dir / lf_name
            if lock_file.exists() and not self.is_running(profile_id):
                try:
                    lock_file.unlink(missing_ok=True)
                except Exception:
                    pass

        settings = load_settings()
        if window_size and len(window_size) == 2:
            win_size = f"{window_size[0]},{window_size[1]}"
        else:
            raw_size = settings.get("browser_window_size", "1280x800")
            win_size = raw_size.split(" ")[0].replace("x", ",").strip()

        raw_num = str(profile_data.get("number", "01")).replace("Profile", "").replace("#", "").strip()
        if raw_num.isdigit():
            num_text = f"{int(raw_num):02d}"
        else:
            num_text = raw_num if raw_num else "01"

        color_name = profile_data.get("color", "SkyBlue")
        try:
            from config import COLOR_PALETTE
            color_hex = COLOR_PALETTE.get(color_name, "#38bdf8") if isinstance(COLOR_PALETTE, dict) else "#38bdf8"
        except Exception:
            color_hex = "#38bdf8"

        prof_num_int = int(raw_num) if raw_num.isdigit() else 1
        ico_path = profile_dir / "profile_icon.ico"
        generate_profile_icon_ico(num_text, ico_path, color_hex, prof_num_int)

        # Profile Language Resolution (Defaults strictly to en-US)
        lang_code = str(profile_data.get("language", "en-US")).strip() or "en-US"

        # Native Preferences Injection for Chromium Locale & Accept-Languages
        try:
            import json
            def_dir = profile_dir / "Default"
            def_dir.mkdir(parents=True, exist_ok=True)
            pref_file = def_dir / "Preferences"
            pref_data = {}
            if pref_file.exists():
                try:
                    with open(pref_file, "r", encoding="utf-8") as f:
                        pref_data = json.load(f)
                except Exception:
                    pref_data = {}
            if not isinstance(pref_data, dict):
                pref_data = {}
            pref_data.setdefault("intl", {})["accept_languages"] = f"{lang_code},en"
            pref_data.setdefault("intl", {})["selected_languages"] = f"{lang_code},en"
            pref_data.setdefault("spellcheck", {})["dictionaries"] = [lang_code]
            pref_data.setdefault("spellcheck", {})["dictionary"] = lang_code
            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(pref_data, f, indent=2)
        except Exception:
            pass

        try:
            n_val = int(str(num_text).replace("Profile", "").replace("#", "").strip().lstrip("0") or "1")
            cdp_port = 9200 + (n_val % 500)
        except Exception:
            cdp_port = 9222

        cmd = [
            browser_exe,
            f"--user-data-dir={str(profile_dir.resolve())}",
            f"--class=srkBrowser_Profile_{num_text}",
            f"--window-size={win_size}",
            f"--remote-debugging-port={cdp_port}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-background-mode",
            "--disable-session-crashed-bubble",
            "--no-service-autorun",
            "--disable-infobars",
            "--disable-signin-promo",
            "--signin-process-disabled",
            "--silent-debugger-extension-api",
            "--disable-component-update",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--deny-permission-prompts",
            f"--lang={lang_code}",
            f"--accept-lang={lang_code},en;q=0.9",
            "--disable-save-password-bubble",
            "--disable-single-click-autofill",
            "--disable-autofill-keyboard-accessory-view",
            "--disable-password-generation",
            "--password-store=basic",
            "--credentials-enable-service=false",
            # Anti-Detect Core Flags & Bloatware/AI Disablers
            "--disable-blink-features=AutomationControlled",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--disable-site-isolation-trials",
            "--disable-features=IsolateOrigins,site-per-process,TranslateUI,AutofillServerCommunication,OptimizationGuideModelDownloading,SidePanelSearchCompanion,LensOverlay,Translate,ChromeWhatsNewUI,IPH_SidePanelGenericPannelHelpBubble,LensSearch,SignInProfileAvatar,ProfilePicker,IdentityConsistency,EnableTokenBinding,AvatarToolbarButton,AppDiscoveryForProfiles,AppPreloadService,PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies,StartupBoost,BackgroundMode,Windows10StartupPrompt,CalculateNativeWinOcclusion,DefaultBrowserPrompt,LaunchOnStartup,ChromeSignin,ProfileCustomization,AvatarPillPromo,SupervisedUserSignInIPH",
            "--suppress-message-center-popups",
            "--enable-bookmark-bar",
            # 🚀 Ultra-Lite Memory & CPU Performance Flags (Optimized 512MB sweet spot, prevents OOM on heavy Facebook/Meta pages)
            '--js-flags=--max_old_space_size=512',
            "--renderer-process-limit=2",
            "--disable-breakpad",
            "--disable-sync",
            "--disable-domain-reliability",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--disable-speech-api",
            "--disable-wake-on-wifi",
            "--enable-low-res-tiling",
            "--enable-features=HighEfficiencyModeAvailable,HighEfficiencyMode"
        ]
        if window_position and len(window_position) == 2:
            cmd.append(f"--window-position={window_position[0]},{window_position[1]}")
        else:
            cmd.append("--window-position=100,100")

        # 1. Proxy settings
        proxy_type = profile_data.get("proxy_type", "None")
        proxy_host = profile_data.get("proxy_host", "").strip()
        proxy_port = profile_data.get("proxy_port", "").strip()

        if proxy_type in ("HTTP", "SOCKS5") and proxy_host and proxy_port:
            scheme = "socks5" if proxy_type == "SOCKS5" else "http"
            cmd.append(f"--proxy-server={scheme}://{proxy_host}:{proxy_port}")

        # 2. Custom User-Agent
        user_agent = profile_data.get("user_agent", "").strip()
        if user_agent:
            cmd.append(f"--user-agent={user_agent}")

        # 3. Extensions Loader & Floating Profile Badge Injector
        extensions = profile_data.get("extensions", [])
        valid_exts = []

        # Build lookup of globally disabled extensions so they are NEVER loaded into browser when deactivated
        disabled_ext_identifiers = set()
        try:
            from extension_manager import ExtensionManager
            ext_mgr = ExtensionManager()
            for ext in ext_mgr.get_all_extensions():
                if not ext.get("is_active", True):
                    p = ext.get("path", "")
                    if p:
                        try:
                            disabled_ext_identifiers.add(str(Path(p).resolve()).lower())
                        except Exception:
                            pass
                        disabled_ext_identifiers.add(str(p).lower())
                        disabled_ext_identifiers.add(Path(p).name.lower())
                    eid = ext.get("id", "")
                    if eid:
                        disabled_ext_identifiers.add(str(eid).lower())
        except Exception:
            pass

        for ext in extensions:
            if not isinstance(ext, str) or not ext.strip():
                continue
            ext_p = Path(ext)
            ext_res = ""
            try:
                ext_res = str(ext_p.resolve()).lower()
            except Exception:
                pass
            if ext_res in disabled_ext_identifiers or str(ext).lower() in disabled_ext_identifiers or ext_p.name.lower() in disabled_ext_identifiers:
                continue

            if ext_p.exists() and (ext_p / "manifest.json").exists():
                valid_exts.append(str(ext_p.resolve()))
            else:
                # Portable cross-PC extension resolution
                ext_name = ext_p.name
                if ext_name.lower() in disabled_ext_identifiers:
                    continue
                candidates = [
                    profile_dir / "extensions" / ext_name,
                    profile_dir / ext_name,
                    Path(__file__).parent / "extensions" / ext_name,
                    Path(__file__).parent.parent / "extensions" / ext_name,
                ]
                try:
                    from config import EXTENSIONS_DIR
                    candidates.append(EXTENSIONS_DIR / ext_name)
                    candidates.append(EXTENSIONS_DIR / ext_p.stem)
                except Exception:
                    pass

                for cand in candidates:
                    if cand.exists() and (cand / "manifest.json").exists():
                        cand_str = str(cand.resolve())
                        if cand_str.lower() in disabled_ext_identifiers or cand.name.lower() in disabled_ext_identifiers:
                            continue
                        if cand_str not in valid_exts:
                            valid_exts.append(cand_str)
                        break
        
        try:
            from extension_manager import ExtensionManager
            ext_mgr = ExtensionManager()
            active_global_exts = ext_mgr.get_active_extensions_for_profile(profile_data)
            for g_ext in active_global_exts:
                if g_ext not in valid_exts and os.path.exists(g_ext):
                    valid_exts.append(g_ext)
        except Exception:
            pass

        # Smart Profile Inspector Extension (Pinned on toolbar)
        inspector_path = create_profile_inspector_extension(profile_dir, profile_data)
        if inspector_path and os.path.exists(inspector_path):
            valid_exts.append(inspector_path)

        cookie_inj_path = create_cookie_injector_extension(profile_dir, profile_data)
        if cookie_inj_path and os.path.exists(cookie_inj_path):
            valid_exts.append(cookie_inj_path)

        # Auto-Pin all loaded extensions to Chrome's top toolbar
        auto_pin_extensions_in_profile(profile_dir, valid_exts)

        if valid_exts:
            ext_arg = ",".join(valid_exts)
            cmd.append(f"--load-extension={ext_arg}")

        # Auto-Sync Bookmarks and enable Bookmark Bar
        try:
            from bookmark_manager import BookmarkManager
            bm_mgr = BookmarkManager()
            bm_mgr.sync_bookmarks_to_profile(profile_dir, profile_data, custom_bookmarks=profile_data.get("bookmarks"))
        except Exception:
            pass

        # 4. Start URL (Opens custom URL if configured by user; otherwise starts clean Google New Tab with [Number] in title)
        start_url_raw = start_url or profile_data.get("start_url", "").strip()
        start_url_lower = start_url_raw.lower()
        if start_url_raw and not any(ign in start_url_lower for ign in ("about:blank", "chrome://newtab")):
            if not (start_url_raw.startswith("http://") or start_url_raw.startswith("https://") or start_url_raw.startswith("file://")):
                start_url_raw = "https://" + start_url_raw
            cmd.append(start_url_raw)
        elif start_url and not any(ign in str(start_url).lower() for ign in ("about:blank", "chrome://newtab")):
            cmd.append(start_url)
        else:
            # Clean Google New Tab with [Number] New Tab in tab title
            cmd.append(f"http://127.0.0.1:5000/landing?id={profile_id}&no={num_text}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            pid_str = str(profile_id)
            self._active_processes[pid_str] = (proc, time.time())
            self.mark_session_active(pid_str, extra_meta={"browser_exe": browser_exe, "cdp_port": cdp_port})
            if ico_path.exists():
                apply_window_icon_win32(proc.pid, ico_path, num_text)
            self.process_started.emit(pid_str)
            return True, f"Browser launched for {profile_data.get('number', 'Profile')}."
        except Exception as err:
            return False, f"Failed to launch browser: {str(err)}"

    def close_profile(self, profile_id: str) -> bool:
        """Terminate active browser process for a profile, extract cookies, and sync to cloud."""
        pid_str = str(profile_id)
        if pid_str in self._active_processes:
            proc, start_t = self._active_processes.pop(pid_str, (None, time.time()))
            self.mark_session_closed(pid_str)
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

            self.process_syncing.emit(pid_str)
            duration_sec = max(1, int(time.time() - start_t))
            parent = self.parent()

            def _async_sync_and_finish():
                import time
                time.sleep(0.6)
                active_token = ""
                if parent and hasattr(parent, "get_effective_cloud_token"):
                    active_token = parent.get_effective_cloud_token()
                if not active_token:
                    from cloud_sync import get_active_license_token
                    active_token = get_active_license_token()

                if parent and hasattr(parent, "profile_mgr"):
                    try:
                        parent.profile_mgr.sync_profile_cookies_from_disk(pid_str)
                        parent.profile_mgr.record_launch_session(pid_str, duration_sec)
                        p_folder = parent.profile_mgr.get_profile_folder(pid_str)
                        all_profs = parent.profile_mgr.get_all_profiles()

                        if active_token and p_folder and p_folder.exists():
                            from cloud_sync import upload_profile_session_zip, upload_profiles_cloud_backup, sync_tracker
                            upload_profile_session_zip(pid_str, p_folder, active_token)
                            upload_profiles_cloud_backup(all_profs, active_token)
                    except Exception:
                        pass

                time.sleep(0.6)
                self.process_finished.emit(pid_str)

            import threading
            from cloud_sync import sync_tracker
            t_close = threading.Thread(target=_async_sync_and_finish, daemon=False)
            sync_tracker.track_thread(t_close)
            t_close.start()
            return True

        # Orphaned / crash recovery session handling (power outage, crash, forced termination)
        persisted = self._load_persisted_active_sessions(force_refresh=True)
        is_persisted = pid_str in persisted
        parent = self.parent()
        pm = getattr(parent, "profile_mgr", None) if parent else None
        if not pm:
            try:
                from profile_manager import ProfileManager
                pm = ProfileManager()
            except Exception:
                pm = None

        p_folder = pm.get_profile_folder(pid_str) if pm else None
        has_locks = False
        if p_folder and p_folder.exists():
            for fname in ["lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]:
                if (p_folder / fname).exists():
                    has_locks = True
                    break

        if is_persisted or has_locks:
            self.mark_session_closed(pid_str)
            self.process_syncing.emit(pid_str)

            # Terminate any lingering background Chrome process that might still hold this profile folder
            if p_folder and p_folder.exists():
                folder_str = str(p_folder.resolve()).lower()
                try:
                    import psutil
                    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            name = (p.info.get('name') or '').lower()
                            if 'chrome' in name:
                                cmd = " ".join(p.info.get('cmdline') or []).lower()
                                if folder_str in cmd:
                                    p.kill()
                        except Exception:
                            pass
                except Exception:
                    pass

                # Delete all stale lock files
                for fname in ["lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]:
                    lf = p_folder / fname
                    if lf.exists():
                        try:
                            lf.unlink(missing_ok=True)
                        except Exception:
                            pass

            def _async_orphaned_sync(target_pid=pid_str):
                import time
                time.sleep(0.4)
                if pm and p_folder and p_folder.exists():
                    try:
                        pm.sync_profile_cookies_from_disk(target_pid)
                    except Exception:
                        pass
                time.sleep(0.4)
                self.process_finished.emit(target_pid)

            import threading
            t_rec = threading.Thread(target=_async_orphaned_sync, daemon=True)
            t_rec.start()
            return True

        return False

    def close_all_active_profiles(self) -> int:
        """Gracefully terminate active browser processes and ensure session cookies and zips are queued."""
        closed = 0
        pids = list(self._active_processes.keys())
        for pid in pids:
            proc, start_time = self._active_processes.pop(pid, (None, 0))
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    closed += 1
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

                # Immediately extract cookies and queue session zip upload
                if self.parent and hasattr(self.parent, "profile_mgr"):
                    try:
                        duration = int(time.time() - start_time) if start_time else 0
                        self.parent.profile_mgr.sync_profile_cookies_from_disk(pid)
                        self.parent.profile_mgr.record_launch_session(pid, duration)

                        p_folder = self.parent.profile_mgr.get_profile_folder(pid)
                        active_token = self.parent.get_effective_cloud_token() if hasattr(self.parent, "get_effective_cloud_token") else None
                        if not active_token:
                            from cloud_sync import get_active_license_token
                            active_token = get_active_license_token()

                        if active_token and p_folder and p_folder.exists():
                            import threading
                            from cloud_sync import upload_profile_session_zip, sync_tracker
                            sync_tracker.register_session_upload(pid)

                            def _exit_zip_worker(target_pid=pid, folder=p_folder, tok=active_token):
                                try:
                                    upload_profile_session_zip(target_pid, folder, tok)
                                finally:
                                    sync_tracker.mark_session_upload_complete(target_pid)

                            t_exit = threading.Thread(target=_exit_zip_worker, daemon=False)
                            sync_tracker.track_thread(t_exit)
                            t_exit.start()
                    except Exception:
                        pass

        if closed > 0 and self.parent and hasattr(self.parent, "profile_mgr"):
            try:
                import threading
                from cloud_sync import upload_profiles_cloud_backup, sync_tracker, get_active_license_token
                all_p = self.parent.profile_mgr.get_all_profiles()
                token = self.parent.get_effective_cloud_token() if hasattr(self.parent, "get_effective_cloud_token") else get_active_license_token()
                if all_p and token:
                    t_meta = threading.Thread(target=upload_profiles_cloud_backup, args=(all_p, token), daemon=False)
                    sync_tracker.track_thread(t_meta)
                    t_meta.start()
            except Exception:
                pass

        return closed
