"""
Browser Profile Manager - Cloud Backup & Restore Module
Python 3.13 / PySide6 Desktop Application
Developer: Srk Shofiqul (sritzone.com)
"""

import os
import json
import base64
import threading
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set

from config import WEBSITE_API_URL
from license_manager import load_activated_license, get_hardware_id

# Endpoint for Cloud Profile Backup Management (Live srkBrowser Cloud Production Endpoint)
LIVE_SYNC_API_URL = "https://srbrowser.com/api/v1/sync/metadata"
LOCAL_SYNC_API_URL = "http://127.0.0.1:5000/api/v1/sync/metadata"
WEBSITE_BACKUP_API_URL = os.environ.get("SYNC_API_URL") or LIVE_SYNC_API_URL


class CloudSyncTracker:
    """
    Centralized thread-safe tracker for ongoing cloud synchronization operations:
    - Profile deletions (waiting for cloud purge acknowledgment)
    - Session ZIP uploads (Chrome cookies & IndexedDB syncing to cloud)
    - Profile metadata backups
    Provides graceful shutdown barriers, exit dialog hooks, and offline queue recovery.
    """
    _instance = None
    _class_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._class_lock:
                if not cls._instance:
                    cls._instance = super(CloudSyncTracker, cls).__new__(cls)
                    cls._instance._init_tracker()
        return cls._instance

    def _init_tracker(self):
        self._pending_deletions: Set[str] = set()
        self._pending_session_uploads: Set[str] = set()
        self._active_threads: List[threading.Thread] = []
        self._data_lock = threading.Lock()
        self._queue_file: Optional[Path] = None

    def set_queue_file(self, path: Path) -> None:
        with self._data_lock:
            self._queue_file = Path(path)

    def register_deletion(self, profile_ids: List[str]) -> None:
        with self._data_lock:
            for pid in profile_ids:
                if pid:
                    self._pending_deletions.add(str(pid).strip())
        self.save_offline_queue()

    def mark_deletion_complete(self, profile_ids: List[str]) -> None:
        with self._data_lock:
            for pid in profile_ids:
                self._pending_deletions.discard(str(pid).strip())
        self.save_offline_queue()

    def register_session_upload(self, profile_id: str) -> None:
        with self._data_lock:
            if profile_id:
                self._pending_session_uploads.add(str(profile_id).strip())
        self.save_offline_queue()

    def mark_session_upload_complete(self, profile_id: str) -> None:
        with self._data_lock:
            self._pending_session_uploads.discard(str(profile_id).strip())
        self.save_offline_queue()

    def track_thread(self, thread: threading.Thread) -> None:
        with self._data_lock:
            self._active_threads = [t for t in self._active_threads if t.is_alive()]
            self._active_threads.append(thread)

    def is_busy(self) -> bool:
        with self._data_lock:
            self._active_threads = [t for t in self._active_threads if t.is_alive()]
            return (
                len(self._pending_deletions) > 0 or 
                len(self._pending_session_uploads) > 0 or 
                len(self._active_threads) > 0
            )

    def get_busy_counts(self) -> Tuple[int, int, int]:
        """Returns (pending_deletions_count, pending_uploads_count, active_threads_count)"""
        with self._data_lock:
            self._active_threads = [t for t in self._active_threads if t.is_alive()]
            return (
                len(self._pending_deletions),
                len(self._pending_session_uploads),
                len(self._active_threads)
            )

    def get_summary_text(self) -> str:
        d_cnt, u_cnt, t_cnt = self.get_busy_counts()
        parts = []
        if u_cnt > 0:
            parts.append(f"{u_cnt} session(s) uploading")
        if d_cnt > 0:
            parts.append(f"{d_cnt} deletion(s) syncing")
        if not parts and t_cnt > 0:
            parts.append("Cloud sync in progress")
        return ", ".join(parts) if parts else "All synced"

    def wait_for_idle(self, timeout_sec: float = 5.0, poll_interval: float = 0.1) -> bool:
        """Wait synchronously up to timeout_sec for all operations to settle."""
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            if not self.is_busy():
                return True
            time.sleep(poll_interval)
        return not self.is_busy()

    def save_offline_queue(self) -> None:
        if not self._queue_file:
            return
        try:
            with self._data_lock:
                q_data = {
                    "pending_deletions": list(self._pending_deletions),
                    "pending_session_uploads": list(self._pending_session_uploads),
                }
            self._queue_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._queue_file, "w", encoding="utf-8") as f:
                json.dump(q_data, f, indent=2)
        except Exception:
            pass

    def load_offline_queue(self) -> Dict[str, Any]:
        if not self._queue_file or not self._queue_file.exists():
            return {}
        try:
            with open(self._queue_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


sync_tracker = CloudSyncTracker()



def get_active_license_token() -> str:
    """Retrieve the currently logged-in user's API token or active license key from local storage."""
    # 1. Try logged-in user session token first
    try:
        from auth_manager import AuthManager
        auth = AuthManager()
        curr_user = auth.get_current_user()
        if curr_user and curr_user.get("is_logged_in") and curr_user.get("token"):
            return str(curr_user["token"]).strip()
    except Exception:
        pass

    # 2. Try license.dat
    saved_data = load_activated_license()
    if saved_data and isinstance(saved_data, dict):
        key = saved_data.get("license_key") or saved_data.get("token")
        if key:
            return str(key).strip()

    return ""


def build_lightweight_profile_payload(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract full credentials, extensions, hardware fingerprint noise, and metadata required for 100% A-to-Z restore.
    Excludes heavy local cache paths and browser temporary logs.
    """
    lightweight_list = []
    for p in profiles:
        if not isinstance(p, dict):
            continue
        
        # Build clean complete lightweight record
        record = {
            "id": p.get("id", ""),
            "number": p.get("number", ""),
            "name": p.get("name", "Unnamed Profile"),
            "group": p.get("group", "Default"),
            "category": p.get("category", "General"),
            "color": p.get("color", "#89b4fa"),
            "uid": p.get("uid", "") or p.get("fb_uid", ""),
            "fb_uid": p.get("fb_uid", "") or p.get("uid", ""),
            "password": p.get("password", "") or p.get("fb_pass", ""),
            "fb_pass": p.get("fb_pass", "") or p.get("password", ""),
            "cookie": p.get("cookie", "") or p.get("cookies", ""),
            "cookies": p.get("cookies", "") or p.get("cookie", ""),
            "cookies_json": p.get("cookies_json", []),
            "secret_2fa": p.get("secret_2fa", "") or p.get("fb_2fa", ""),
            "fb_2fa": p.get("fb_2fa", "") or p.get("secret_2fa", ""),
            "assigned_scripts": p.get("assigned_scripts", []),
            "pin": p.get("pin", ""),
            "notes": p.get("notes", ""),
            "user_agent": p.get("user_agent", ""),
            "proxy_type": p.get("proxy_type", "None"),
            "proxy_host": p.get("proxy_host", ""),
            "proxy_port": p.get("proxy_port", ""),
            "start_url": p.get("start_url", ""),
            "extensions": p.get("extensions", []),
            "cpu_cores": p.get("cpu_cores", 8),
            "ram_gb": p.get("ram_gb", 16),
            "language": p.get("language", "en-US"),
            "total_launches": p.get("total_launches", 0),
            "total_runtime_sec": p.get("total_runtime_sec", 0),
            "created_at": p.get("created_at", ""),
            "last_open": p.get("last_open", "")
        }
        lightweight_list.append(record)
        
    return lightweight_list


def upload_profiles_cloud_backup(
    profiles: List[Dict[str, Any]], 
    license_token: Optional[str] = None,
    api_url: str = WEBSITE_BACKUP_API_URL,
    allow_empty_purge: bool = False,
    deleted_profile_ids: Optional[List[str]] = None
) -> Tuple[bool, str, int]:
    # Customer Standalone Edition: All profiles are strictly local. No server backup.
    return True, "Local offline storage active", len(profiles or [])

    if clean_deleted_ids:
        sync_tracker.register_deletion(clean_deleted_ids)

    if (not profiles or len(profiles) == 0) and not allow_empty_purge and not clean_deleted_ids:
        # Safety guard: Never purge cloud with empty profiles unless explicitly intended
        return True, "No profiles to upload (empty purge skipped).", 0

    payload = build_lightweight_profile_payload(profiles or [])

    if len(payload) > 5000:
        # Rolling Window Cap: send latest 5,000 profiles
        payload = payload[-5000:]

    hwid = get_hardware_id()

    try:
        payload_json_str = json.dumps(payload)

        req_data = {
            "license_token": token,
            "hwid": hwid,
            "total_profiles": len(payload),
            "payload": payload_json_str,
            "data": payload,
            "profiles": payload,
            "full_mirror_purge": True,
            "allow_empty_purge": bool(allow_empty_purge),
            "deleted_profile_ids": clean_deleted_ids
        }

        response = requests.post(
            api_url,
            json=req_data,
            headers={
                "Content-Type": "application/json",
                "x-license-token": token,
                "X-Auth-Token": token,
                "User-Agent": "srkBrowser/2.0"
            },
            timeout=15
        )

        if response.status_code in [200, 201]:
            res_json = response.json()
            if res_json.get("success") is True or res_json.get("valid") is True:
                if clean_deleted_ids:
                    sync_tracker.mark_deletion_complete(clean_deleted_ids)
                msg = res_json.get("message", f"Successfully synced {len(payload)} profile(s) to cloud!")
                return True, msg, len(payload)
            else:
                reason = res_json.get("reason") or res_json.get("message") or "Cloud sync rejected by server."
                return False, reason, 0
        else:
            return False, f"Server HTTP {response.status_code}: {response.text[:100]}", 0

    except requests.exceptions.Timeout:
        return False, "Connection timeout while uploading to sritzone.com cloud server.", 0
    except requests.exceptions.ConnectionError:
        return False, "Failed to connect to sritzone.com server. Check your internet connection.", 0
    except Exception as err:
        return False, f"Cloud upload error: {err}", 0


def extract_profiles_from_response(obj: Any) -> List[Dict[str, Any]]:
    """Recursively extract profiles list from nested JSON server response."""
    if isinstance(obj, list):
        return [item for item in obj if isinstance(item, dict)]
    if isinstance(obj, str) and obj.strip():
        try:
            parsed = json.loads(obj)
            return extract_profiles_from_response(parsed)
        except Exception:
            pass
    if isinstance(obj, dict):
        for key in ["profiles", "payload", "data", "backup", "items", "records"]:
            if key in obj:
                val = obj[key]
                res = extract_profiles_from_response(val)
                if res and len(res) > 0:
                    return res
    return []


def download_profiles_cloud_backup(
    license_token: Optional[str] = None,
    api_url: str = WEBSITE_BACKUP_API_URL
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    # Customer Standalone Edition: All profiles are strictly local.
    return True, "Local offline storage active", []


    try:
        params = {
            "token": token,
            "license_token": token,
            "hwid": hwid
        }
        response = requests.get(
            api_url,
            params=params,
            headers={
                "Content-Type": "application/json",
                "x-license-token": token,
                "X-Auth-Token": token,
                "User-Agent": "srkBrowser/2.0"
            },
            timeout=15
        )

        if response.status_code == 200:
            res_json = response.json()
            profiles_list = extract_profiles_from_response(res_json)
            
            if profiles_list and len(profiles_list) > 0:
                msg = res_json.get("message", f"Fetched {len(profiles_list)} profile(s) from cloud!")
                return True, msg, profiles_list
            elif res_json.get("success") is True or "data" in res_json or "backup" in res_json:
                return True, "No profile backups found.", []
            else:
                reason = res_json.get("reason") or res_json.get("message") or "No cloud backup found."
                return False, reason, []

        else:
            return False, f"Server HTTP {response.status_code}: {response.text[:100]}", []


    except requests.exceptions.Timeout:
        return False, "Connection timeout while downloading from sritzone.com cloud server.", []
    except requests.exceptions.ConnectionError:
        return False, "Failed to connect to sritzone.com server. Check your internet connection.", []
    except Exception as err:
        return False, f"Cloud restore error: {err}", []


try:
    from PySide6.QtCore import QThread, Signal

    class CloudUploadThread(QThread):
        """Thread worker to upload profile backups in the background without freezing UI."""
        finished_signal = Signal(bool, str, int)

        def __init__(self, profiles: List[Dict[str, Any]], license_token: Optional[str] = None, allow_empty_purge: bool = False, parent=None):
            super().__init__(parent)
            self.profiles = profiles
            self.license_token = license_token
            self.allow_empty_purge = allow_empty_purge

        def run(self) -> None:
            ok, msg, count = upload_profiles_cloud_backup(self.profiles, self.license_token, allow_empty_purge=self.allow_empty_purge)
            self.finished_signal.emit(ok, msg, count)

    class CloudDownloadThread(QThread):
        """Thread worker to download cloud profile backups in the background without freezing UI."""
        finished_signal = Signal(bool, str, list)

        def __init__(self, license_token: Optional[str] = None, parent=None):
            super().__init__(parent)
            self.license_token = license_token

        def run(self) -> None:
            ok, msg, profiles = download_profiles_cloud_backup(self.license_token)
            self.finished_signal.emit(ok, msg, profiles)

    class CloudRestoreWorker(QThread):
        """
        High-performance threaded worker for restoring cloud profiles & session backups.
        Emits fine-grained progress signals so large datasets (1,000 - 2,000 profiles)
        render smoothly and incrementally in the desktop UI without UI freezes.
        """
        progress_signal = Signal(int, int, str)        # (current_step, total_steps, detail_text)
        batch_imported_signal = Signal(int, int, list)  # (imported_count, total_count, profiles_batch)
        finished_signal = Signal(bool, str, int)       # (success, message, total_profiles)

        def __init__(self, license_token: Optional[str] = None, batch_size: int = 50, restore_sessions: bool = True, base_dir: Optional[Path] = None, parent=None):
            super().__init__(parent)
            self.license_token = license_token
            self.batch_size = max(10, batch_size)
            self.restore_sessions = restore_sessions
            self.base_dir = base_dir
            self._is_cancelled = False

        def cancel(self):
            self._is_cancelled = True

        def run(self) -> None:
            self.progress_signal.emit(5, 100, "Connecting to srkBrowser Cloud...")
            
            # Step 1: Download metadata
            ok, msg, profiles = download_profiles_cloud_backup(self.license_token)
            if not ok or not isinstance(profiles, list):
                self.finished_signal.emit(False, msg or "Failed to connect to cloud backup.", 0)
                return

            total_profiles = len(profiles)
            if total_profiles == 0:
                self.finished_signal.emit(True, "No cloud backup profiles to restore.", 0)
                return

            self.progress_signal.emit(10, 100, f"Found {total_profiles} cloud profiles. Initializing local sync...")

            # Step 2: Stream in batches
            for i in range(0, total_profiles, self.batch_size):
                if self._is_cancelled:
                    break
                chunk = profiles[i:i + self.batch_size]
                current_imported = min(i + len(chunk), total_profiles)
                pct = int(10 + (current_imported / total_profiles) * 60) # 10% to 70%
                self.progress_signal.emit(pct, 100, f"Restoring profiles: {current_imported} / {total_profiles} ({int((current_imported/total_profiles)*100)}%)...")
                self.batch_imported_signal.emit(current_imported, total_profiles, chunk)
                import time
                time.sleep(0.02) # Small yield for ultra-smooth UI event loop

            if self._is_cancelled:
                self.finished_signal.emit(False, "Cloud restore cancelled.", total_profiles)
                return

            # Step 3: Session zips restore (if base_dir provided)
            if self.restore_sessions and self.base_dir and Path(self.base_dir).exists():
                session_targets = [p for p in profiles if p.get("id") and p.get("number")]
                total_sess = len(session_targets)
                if total_sess > 0:
                    for s_idx, p in enumerate(session_targets):
                        if self._is_cancelled:
                            break
                        pid = p["id"]
                        pnum = p["number"]
                        p_folder = Path(self.base_dir) / str(pnum)
                        p_name = p.get("name") or f"Profile #{pnum}"
                        
                        sess_pct = int(70 + ((s_idx + 1) / total_sess) * 30) # 70% to 100%
                        if s_idx % 5 == 0 or s_idx == total_sess - 1:
                            self.progress_signal.emit(sess_pct, 100, f"Restoring sessions: {s_idx + 1} / {total_sess} ({p_name})...")
                        
                        try:
                            download_and_restore_profile_session_zip(pid, p_folder, license_token=self.license_token)
                        except Exception:
                            pass

            self.progress_signal.emit(100, 100, f"All {total_profiles} profiles & sessions restored successfully!")
            self.finished_signal.emit(True, f"Successfully restored {total_profiles} cloud profiles & sessions!", total_profiles)

except ImportError:
    pass


import zipfile
import io

EXCLUDE_DIRS = {
    "cache", "code cache", "gpucache", "media cache", "crashpad",
    "cachestorage", "blob_storage", "system reporting", "safe browsing",
    "sessions", "session storage"
}

def create_lightweight_profile_session_zip(profile_folder: Path) -> Optional[bytes]:
    """
    Compress essential Chrome session files (Cookies, Local Storage, IndexedDB, Preferences, Bookmarks, Extensions)
    into a lightweight ZIP archive in memory, skipping heavy image & code caches.
    Handles Windows file lock retries when Chrome exits.
    """
    if not profile_folder.exists():
        return None

    import time
    time.sleep(1.2)

    mem_zip = io.BytesIO()
    has_files = False

    try:
        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Package all session files, cookies, preferences, bookmarks inside profile_folder
            for root, dirs, files in os.walk(profile_folder):
                dirs[:] = [d for d in dirs if d.lower() not in EXCLUDE_DIRS and "cache" not in d.lower()]
                for f in files:
                    f_name = f.lower()
                    if f_name.startswith("singleton") or f_name.endswith(".tmp") or f_name.endswith(".log"):
                        continue

                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(profile_folder)
                    for attempt in range(3):
                        try:
                            if full_path.exists() and full_path.stat().st_size <= 25 * 1024 * 1024:
                                zf.write(full_path, arcname=rel_path)
                                has_files = True
                                break
                        except PermissionError:
                            time.sleep(0.4)
                        except Exception:
                            break

            # 2. Package any external custom extensions referenced in profile.json
            prof_json_path = profile_folder / "profile.json"
            if prof_json_path.exists():
                try:
                    with open(prof_json_path, "r", encoding="utf-8") as pf:
                        p_data = json.load(pf)
                    for ext_path_str in p_data.get("extensions", []):
                        if isinstance(ext_path_str, str) and ext_path_str.strip():
                            ext_dir = Path(ext_path_str)
                            if ext_dir.exists() and ext_dir.is_dir() and (ext_dir / "manifest.json").exists():
                                try:
                                    ext_dir.relative_to(profile_folder)
                                except ValueError:
                                    # External extension: bundle it into extensions/<ext_name>
                                    ext_dest_prefix = Path("extensions") / ext_dir.name
                                    for e_root, _, e_files in os.walk(ext_dir):
                                        for ef in e_files:
                                            ef_path = Path(e_root) / ef
                                            ef_rel = ef_path.relative_to(ext_dir)
                                            arc_name = ext_dest_prefix / ef_rel
                                            if ef_path.exists() and ef_path.stat().st_size <= 25 * 1024 * 1024:
                                                zf.write(ef_path, arcname=str(arc_name))
                                                has_files = True
                except Exception:
                    pass

        if has_files:
            return mem_zip.getvalue()
    except Exception as e:
        print(f"[ZIP SESSION ERROR]: {e}")

    return None


def upload_profile_session_zip(profile_id: str, profile_folder: Path, license_token: Optional[str] = None) -> bool:
    """Customer Standalone Edition: Local sessions only."""
    return True


def download_and_restore_profile_session_zip(profile_id: str, profile_folder: Path, license_token: Optional[str] = None) -> bool:
    """Customer Standalone Edition: Local sessions only."""
    return True


