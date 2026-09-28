"""
Browser Profile Manager - Profile Data Management & Persistence Module
Python 3.13 / PySide6 Desktop Application
"""

import json
import os
import random
import re
import shutil
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import PROFILES_DIR, PROFILES_DB_FILE, load_groups, save_groups
from utils import (
    export_csv_helper, generate_random_user_agent, get_current_timestamp,
    import_csv_helper, is_created_today, safe_read_json, safe_write_json
)


def filter_by_profile_numbers(profiles: List[Dict[str, Any]], target_numbers_str: str) -> List[Dict[str, Any]]:
    """
    Filter profile list by comma-separated profile numbers (e.g. 'Profile001, Profile005, Profile018'
    or ranges 'Profile001-Profile005' or raw numbers '1, 5, 18' or '1-5').
    """
    if not target_numbers_str or not target_numbers_str.strip():
        return profiles

    target_numbers: Set[str] = set()
    parts = target_numbers_str.split(",")

    for item in parts:
        s = item.strip()
        if not s:
            continue

        if "-" in s:
            r_parts = s.split("-", 1)
            try:
                start_n = int(re.sub(r"\D", "", r_parts[0]))
                end_n = int(re.sub(r"\D", "", r_parts[1]))
                for n in range(min(start_n, end_n), max(start_n, end_n) + 1):
                    target_numbers.add(f"Profile{n:03d}".lower())
                    target_numbers.add(str(n))
            except Exception:
                target_numbers.add(s.lower())
        else:
            try:
                n_val = int(re.sub(r"\D", "", s))
                target_numbers.add(f"Profile{n_val:03d}".lower())
                target_numbers.add(str(n_val))
            except Exception:
                pass
            target_numbers.add(s.lower())

    filtered = []
    for p in profiles:
        num_str = str(p.get("number", "")).strip().lower()
        num_digits = re.sub(r"\D", "", num_str)

        if num_str in target_numbers or num_digits in target_numbers:
            filtered.append(p)

    return filtered


class ProfileManager:
    """
    Manages browser profile persistence, group organization, sequential folder generation,
    bulk operations, cache cleaning, CSV import/export, PIN protection, and usage analytics.
    """

    def _resolve_user_dir(self) -> Tuple[Path, Path]:
        """Resolve isolated directory and db file per logged-in user email/ID."""
        try:
            from auth_manager import AuthManager
            auth = AuthManager()
            curr = auth.get_current_user()
            if curr and curr.get("is_logged_in") and curr.get("email"):
                safe_email = re.sub(r"[^a-zA-Z0-9_]", "_", curr["email"].strip().lower())
                u_dir = PROFILES_DIR / "users" / safe_email
                u_dir.mkdir(parents=True, exist_ok=True)
                return u_dir, u_dir / "profiles.json"
        except Exception:
            pass
        default_dir = PROFILES_DIR / "users" / "default"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir, default_dir / "profiles.json"

    def __init__(self, base_dir: Path = PROFILES_DIR, db_file: Path = PROFILES_DB_FILE) -> None:
        self.base_dir, self.db_file = self._resolve_user_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        try:
            from cloud_sync import sync_tracker
            sync_tracker.set_queue_file(self.base_dir / "sync_queue.json")
        except Exception:
            pass

        self.groups_file = self.base_dir / "groups.json"
        if self.groups_file.exists():
            self.groups: List[str] = safe_read_json(self.groups_file) or []
        else:
            self.groups: List[str] = load_groups()
        if "Default" not in self.groups:
            self.groups.insert(0, "Default")
            safe_write_json(self.groups_file, self.groups)

        self.profiles: List[Dict[str, Any]] = self.load_profiles()

    @property
    def tombstone_file(self) -> Path:
        """Path to persistent tombstone ledger of locally deleted profile IDs."""
        return self.base_dir / "deleted_profile_ids.json"

    def get_tombstone_ids(self) -> Set[str]:
        """Return set of profile IDs explicitly deleted locally."""
        try:
            if self.tombstone_file.exists():
                data = safe_read_json(self.tombstone_file)
                if isinstance(data, list):
                    return {str(x).strip() for x in data if str(x).strip()}
        except Exception:
            pass
        return set()

    def record_deleted_profiles(self, profile_ids: List[str]) -> None:
        """Persist deleted profile IDs to local tombstone ledger."""
        if not profile_ids:
            return
        with self._lock:
            try:
                current = self.get_tombstone_ids()
                for pid in profile_ids:
                    if pid:
                        current.add(str(pid).strip())
                # Cap tombstone ledger to last 5,000 IDs to keep it lightweight
                capped = list(current)[-5000:]
                safe_write_json(self.tombstone_file, capped)
            except Exception as e:
                print(f"[TOMBSTONE WRITE ERROR]: {e}")

    def clear_tombstones(self, confirmed_ids: List[str]) -> None:
        """Remove confirmed cloud-purged IDs from tombstone ledger."""
        if not confirmed_ids:
            return
        with self._lock:
            try:
                current = self.get_tombstone_ids()
                for pid in confirmed_ids:
                    current.discard(str(pid).strip())
                safe_write_json(self.tombstone_file, list(current))
            except Exception:
                pass


    def load_profiles(self, force_repair: bool = False) -> List[Dict[str, Any]]:
        """Load profiles list from database JSON file and auto-sync with profiles directory."""
        self.base_dir, self.db_file = self._resolve_user_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.groups_file = self.base_dir / "groups.json"
        if self.groups_file.exists():
            self.groups = safe_read_json(self.groups_file) or []
        else:
            self.groups = load_groups()
        if "Default" not in self.groups:
            self.groups.insert(0, "Default")
            safe_write_json(self.groups_file, self.groups)

        data = safe_read_json(self.db_file)
        if isinstance(data, list) and len(data) > 0:
            for p in data:
                self._ensure_defaults(p)
            self.profiles = data
        else:
            self.profiles = []

        if force_repair or not getattr(self, "_initial_repaired", False):
            self._initial_repaired = True
            return self.sync_and_repair_profiles()

        return self.profiles

    def sync_and_repair_profiles(self) -> List[Dict[str, Any]]:
        """
        Deep Crash-Proof Profile Scanner & Auto-Recoverer:
        Scans strictly within the current logged-in user's isolated base_dir on disk.
        If a folder exists on disk (with Default/ or profile.json) but is missing in self.profiles or db_file,
        reads its profile.json (or auto-reconstructs it) and restores it seamlessly into self.profiles and db_file.
        """
        with self._lock:
            existing_ids = {p.get("id") for p in self.profiles if isinstance(p, dict) and "id" in p}
            existing_numbers = {str(p.get("number", "")).strip().lower() for p in self.profiles if isinstance(p, dict) and "number" in p}

            # STRICT ISOLATION: Only scan self.base_dir! Never cross into other users' folders or root directory.
            candidate_dirs = [self.base_dir]

            repaired_count = 0
            for scan_dir in candidate_dirs:
                if not scan_dir.exists():
                    continue
                for folder in sorted(scan_dir.iterdir()):
                    if not folder.is_dir():
                        continue
                    folder_name = folder.name
                    if folder_name.startswith(".") or folder_name.startswith("temp_") or folder_name in ("users", "backups", "Default"):
                        continue

                    p_json_file = folder / "profile.json"
                    default_dir = folder / "Default"

                    # Check if this folder is a profile folder
                    is_profile = (
                        p_json_file.exists() or
                        default_dir.exists() or
                        folder_name.lower().startswith("profile") or
                        folder_name.lower().startswith("p_")
                    )
                    if not is_profile:
                        continue

                    p_data = None
                    if p_json_file.exists():
                        p_data = safe_read_json(p_json_file)

                    if not isinstance(p_data, dict) or "id" not in p_data:
                        p_id = str(uuid.uuid4())
                        p_number = folder_name
                        p_name = folder_name
                        p_data = {
                            "id": p_id,
                            "number": p_number,
                            "name": p_name,
                            "created_at": get_current_timestamp(),
                            "last_open": "",
                            "notes": "Auto-recovered profile",
                            "group": "Default",
                            "category": "General",
                            "color": "#89b4fa"
                        }

                    self._ensure_defaults(p_data)
                    p_id = p_data.get("id")
                    p_num = str(p_data.get("number", folder_name)).strip().lower()

                    if p_id not in existing_ids and p_num not in existing_numbers:
                        safe_write_json(p_json_file, p_data)
                        self.profiles.append(p_data)
                        existing_ids.add(p_id)
                        existing_numbers.add(p_num)
                        repaired_count += 1

            if repaired_count > 0 or not self.db_file.exists() or len(self.profiles) > len(safe_read_json(self.db_file) or []):
                self.save_profiles()
                if repaired_count > 0:
                    print(f"✨ [Auto-Repair] Successfully recovered {repaired_count} profile(s) from disk into active workspace.")

            return self.profiles

    def save_profiles(self) -> bool:
        """Save profiles list to database JSON file."""
        return safe_write_json(self.db_file, self.profiles)

    def _ensure_defaults(self, profile: Dict[str, Any]) -> None:
        """Guarantee required schema fields exist on a profile dictionary."""
        defaults = {
            "name": "Unnamed Profile",
            "notes": "",
            "group": "Default",
            "category": "General",
            "color": "#89b4fa",
            "start_url": "",
            "proxy_type": "None",
            "proxy_host": "",
            "proxy_port": "",
            "user_agent": generate_random_user_agent(),
            "cpu_cores": random.choice([4, 8, 12, 16]),
            "ram_gb": random.choice([4, 8, 16, 32]),
            "pin": "",
            "uid": "",
            "password": "",
            "cookie": "",
            "language": "en-US",
            "extensions": [],
            "assigned_scripts": [],
            "bookmarks": [],
            "total_launches": 0,
            "total_runtime_sec": 0,
            "launch_history": []
        }
        for k, v in defaults.items():
            if k not in profile:
                profile[k] = v

    def get_groups(self) -> List[str]:
        """Return list of existing profile groups including all groups assigned to profiles."""
        g_set = set(self.groups)
        for p in self.profiles:
            g = p.get("group", "Default")
            if g and g.strip():
                g_set.add(g.strip())
        return sorted(list(g_set), key=lambda x: (x != "Default", x.lower()))


    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Return full list of profiles."""
        return list(self.profiles)

    def get_all_groups(self) -> List[str]:
        """Return list of all group names."""
        return self.get_groups()


    def add_group(self, name: str) -> bool:
        """Pre-create a new profile group name."""
        g_name = name.strip()
        if not g_name or g_name in self.groups:
            return False
        self.groups.append(g_name)
        safe_write_json(getattr(self, "groups_file", self.base_dir / "groups.json"), self.groups)
        return True

    def rename_group(self, old_name: str, new_name: str) -> bool:
        """Rename an existing profile group across all profiles."""
        old_g = old_name.strip()
        new_g = new_name.strip()
        if not new_g or old_g == "Default" or old_g not in self.groups or new_g in self.groups:
            return False

        idx = self.groups.index(old_g)
        self.groups[idx] = new_g
        safe_write_json(getattr(self, "groups_file", self.base_dir / "groups.json"), self.groups)

        for p in self.profiles:
            if p.get("group") == old_g:
                p["group"] = new_g
                p_folder = self.get_profile_folder(p["id"])
                safe_write_json(p_folder / "profile.json", p)

        self.save_profiles()
        return True

    def delete_group(self, name: str) -> bool:
        """Delete a profile group and reassign its profiles to 'Default'."""
        g_name = name.strip()
        if g_name == "Default" or g_name not in self.groups:
            return False

        self.groups.remove(g_name)
        safe_write_json(getattr(self, "groups_file", self.base_dir / "groups.json"), self.groups)

        for p in self.profiles:
            if p.get("group") == g_name:
                p["group"] = "Default"
                p_folder = self.get_profile_folder(p["id"])
                safe_write_json(p_folder / "profile.json", p)

        self.save_profiles()
        return True

    def purge_temp_profiles(self) -> int:
        """Purge any temporary verification profiles from database and disk."""
        with self._lock:
            purged = 0
            to_remove = []
            for p in self.profiles:
                p_num = str(p.get("number", ""))
                p_name = str(p.get("name", ""))
                p_id = str(p.get("id", ""))
                if p_num.startswith("temp_") or p_name.startswith("temp_"):
                    to_remove.append(p)

            for p in to_remove:
                self.profiles.remove(p)
                purged += 1
                p_id = p.get("id", "")
                p_folder = self.get_profile_folder(p_id)
                if p_folder and p_folder.exists():
                    shutil.rmtree(p_folder, ignore_errors=True)

            if purged > 0:
                self.save_profiles()
            return purged

    def get_next_profile_number(self) -> str:
        """
        Get the next strictly auto-incrementing profile number (read-only).
        Never reuses deleted numbers or fills missing integer gaps.
        """
        existing_numbers = set()

        for path in self.base_dir.iterdir():
            if path.is_dir() and path.name.startswith("Profile"):
                digits = path.name[7:]
                if digits.isdigit():
                    existing_numbers.add(int(digits))

        for p in self.profiles:
            num_str = p.get("number", "")
            raw_digits = "".join(ch for ch in str(num_str) if ch.isdigit())
            if raw_digits:
                existing_numbers.add(int(raw_digits))

        try:
            from config import load_settings
            settings = load_settings()
            saved_counter = settings.get("last_profile_counter", 0)
        except Exception:
            saved_counter = 0

        max_existing = max(existing_numbers, default=0)
        next_counter = max(max_existing, saved_counter) + 1

        return f"Profile{next_counter:03d}"

    def _commit_profile_number(self, profile_num_str: str) -> None:
        """Commit the profile counter to settings when a profile is actually created."""
        raw_digits = "".join(ch for ch in str(profile_num_str) if ch.isdigit())
        if raw_digits:
            num_val = int(raw_digits)
            try:
                from config import load_settings, save_settings
                settings = load_settings()
                current_saved = settings.get("last_profile_counter", 0)
                if num_val >= current_saved:
                    settings["last_profile_counter"] = num_val
                    save_settings(settings)
            except Exception:
                pass

    def create_profile(
        self,
        name: str = "",
        notes: str = "",
        group: str = "Default",
        category: str = "General",
        color: str = "#89b4fa",
        start_url: str = "",
        proxy_type: str = "None",
        proxy_host: str = "",
        proxy_port: str = "",
        user_agent: str = "",
        cpu_cores: Optional[int] = None,
        ram_gb: Optional[int] = None,
        pin: str = "",
        uid: str = "",
        password: str = "",
        cookie: str = "",
        secret_2fa: str = "",
        language: str = "en-US",
        extensions: Optional[List[str]] = None,
        save_db: bool = True,
        sync_cloud: bool = True,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create a new browser profile directory and record in database."""
        with self._lock:
            profile_number = self.get_next_profile_number()
            self._commit_profile_number(profile_number)
            profile_id = str(uuid.uuid4())
            display_name = name.strip() if name.strip() else profile_number

            now_str = get_current_timestamp()

            grp = group.strip() if group.strip() else "Default"
            if grp not in self.groups:
                self.add_group(grp)

            ua_val = user_agent.strip() if user_agent and user_agent.strip() else generate_random_user_agent()
            cores_val = cpu_cores if cpu_cores is not None else random.choice([4, 8, 12, 16])
            ram_val = ram_gb if ram_gb is not None else random.choice([4, 8, 16, 32])
            lang_val = language.strip() if language and language.strip() else str(kwargs.get("language", "en-US")).strip() or "en-US"

            ext_list = extensions or []
            try:
                from extension_manager import ExtensionManager
                ext_mgr = ExtensionManager()
                auto_exts = ext_mgr.get_active_extensions_for_profile({"group": grp, "extensions": ext_list})
                for ax in auto_exts:
                    if ax not in ext_list:
                        ext_list.append(ax)
            except Exception:
                pass

            sec_2fa_val = secret_2fa.strip() if secret_2fa else str(kwargs.get("secret_2fa", "")).strip()
            uid_val = uid.strip() or str(kwargs.get("fb_uid", "")).strip()
            pass_val = password.strip() or str(kwargs.get("fb_pass", "")).strip()

            profile_data = {
                "id": profile_id,
                "number": profile_number,
                "name": display_name,
                "created_at": now_str,
                "last_open": "",
                "notes": notes.strip(),
                "group": grp,
                "category": category,
                "platform": str(kwargs.get("platform", "Facebook")).strip(),
                "color": color,
                "start_url": start_url.strip(),
                "proxy_type": proxy_type,
                "proxy_host": proxy_host.strip(),
                "proxy_port": str(proxy_port).strip(),
                "proxy_user": str(kwargs.get("proxy_user", "")).strip(),
                "proxy_pass": str(kwargs.get("proxy_pass", "")).strip(),
                "user_agent": ua_val,
                "cpu_cores": cores_val,
                "ram_gb": ram_val,
                "screen_resolution": str(kwargs.get("screen_resolution", "1920x1080")).strip(),
                "language": lang_val,
                "pin": pin.strip(),
                "uid": uid_val,
                "fb_uid": uid_val,
                "password": pass_val,
                "fb_pass": pass_val,
                "cookie": cookie.strip(),
                "secret_2fa": sec_2fa_val,
                "fb_2fa": sec_2fa_val,
                "custom_notes": str(kwargs.get("custom_notes", "")).strip(),
                "extensions": ext_list,
                "assigned_scripts": kwargs.get("assigned_scripts", []),
                "bookmarks": kwargs.get("bookmarks", []),
                "total_launches": 0,
                "total_runtime_sec": 0,
                "launch_history": []
            }

            folder_path = self.base_dir / profile_number
            folder_path.mkdir(parents=True, exist_ok=True)
            safe_write_json(folder_path / "profile.json", profile_data)

            try:
                from browser import auto_pin_extensions_in_profile
                auto_pin_extensions_in_profile(folder_path, ext_list)
            except Exception:
                pass

            try:
                from bookmark_manager import BookmarkManager
                bm_mgr = BookmarkManager()
                bm_mgr.sync_bookmarks_to_profile(folder_path, profile_data, custom_bookmarks=profile_data.get("bookmarks"))
            except Exception:
                pass

            self.profiles.append(profile_data)
            if save_db:
                self.save_profiles()

            if sync_cloud:
                try:
                    all_profs = self.get_all_profiles()
                    if all_profs and len(all_profs) > 0:
                        import threading
                        from cloud_sync import upload_profiles_cloud_backup
                        threading.Thread(target=upload_profiles_cloud_backup, args=(all_profs,), daemon=True).start()
                except Exception:
                    pass

            return profile_data

    def bulk_create_profiles(
        self,
        count: int = 5,
        name_prefix: str = "Profile",
        group: str = "Default",
        category: str = "General",
        color: str = "#89b4fa",
        start_url: str = "",
        language: str = "en-US",
        proxy_lines: Optional[List[str]] = None,
        extensions: Optional[List[str]] = None,
        assigned_scripts: Optional[List[str]] = None,
        selected_bookmarks: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Any] = None,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Create multiple profiles with batch I/O optimization and live progress feedback."""
        created_list = []
        parsed_proxies = [px.strip() for px in (proxy_lines or []) if px.strip()]
        lang_val = language.strip() if language and language.strip() else str(kwargs.get("language", "en-US")).strip() or "en-US"
        scripts_val = assigned_scripts or kwargs.get("assigned_scripts", [])

        for i in range(count):
            p_proxy_type = "None"
            p_proxy_host = ""
            p_proxy_port = ""
            p_proxy_user = ""
            p_proxy_pass = ""

            if parsed_proxies:
                curr_px = parsed_proxies[i % len(parsed_proxies)]
                parts = curr_px.split(":")
                if len(parts) >= 2:
                    p_proxy_type = "HTTP"
                    p_proxy_host = parts[0].strip()
                    p_proxy_port = parts[1].strip()
                if len(parts) >= 4:
                    p_proxy_user = parts[2].strip()
                    p_proxy_pass = parts[3].strip()

            num = self.get_next_profile_number()
            prefix_clean = name_prefix.strip()
            if prefix_clean and prefix_clean.lower() != "profile":
                custom_name = f"{prefix_clean}{i+1:02d}"
            else:
                custom_name = num

            p = self.create_profile(
                name=custom_name,
                notes=f"Bulk created profile {i+1} of {count}",
                group=group,
                category=category,
                color=color,
                start_url=start_url,
                proxy_type=p_proxy_type,
                proxy_host=p_proxy_host,
                proxy_port=p_proxy_port,
                proxy_user=p_proxy_user,
                proxy_pass=p_proxy_pass,
                language=lang_val,
                extensions=extensions or [],
                assigned_scripts=scripts_val,
                bookmarks=selected_bookmarks or [],
                save_db=False,
                sync_cloud=False
            )

            if selected_bookmarks is not None:
                try:
                    p_folder = self.get_profile_folder(p["id"])
                    from bookmark_manager import BookmarkManager
                    bm_mgr = BookmarkManager()
                    bm_mgr.sync_bookmarks_to_profile(p_folder, p, custom_bookmarks=selected_bookmarks)
                except Exception:
                    pass

            created_list.append(p)
            if progress_callback and callable(progress_callback):
                progress_callback(i + 1, count, custom_name)

        # Batch save once at the end for lightning-fast disk I/O
        self.save_profiles()

        try:
            all_profs = self.get_all_profiles()
            if all_profs and len(all_profs) > 0:
                import threading
                from cloud_sync import upload_profiles_cloud_backup
                threading.Thread(target=upload_profiles_cloud_backup, args=(all_profs,), daemon=True).start()
        except Exception:
            pass

        return created_list


    def record_launch_session(self, profile_id: str, duration_sec: int) -> bool:
        """Record launch history entry and update total launch stats."""
        p = self.get_profile_by_id(profile_id)
        if not p:
            return False

        p["total_launches"] = p.get("total_launches", 0) + 1
        p["total_runtime_sec"] = p.get("total_runtime_sec", 0) + max(0, duration_sec)

        history = p.get("launch_history", [])
        history.append({
            "timestamp": get_current_timestamp(),
            "duration_sec": max(0, duration_sec)
        })
        p["launch_history"] = history[-20:]
        p_folder = self.get_profile_folder(profile_id)
        try:
            disk_profile = safe_read_json(p_folder / "profile.json")
            if isinstance(disk_profile, dict) and disk_profile.get("group"):
                p["group"] = disk_profile["group"]
        except Exception:
            pass
        self.save_profiles()
        safe_write_json(p_folder / "profile.json", p)
        return True

    def get_profile_by_id(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve profile dict by unique ID."""
        for p in self.profiles:
            if p["id"] == profile_id:
                return p
        return None

    def get_profile_folder(self, profile_id: str) -> Path:
        """Get absolute filesystem Path for a profile."""
        p = self.get_profile_by_id(profile_id)
        if p:
            num = p.get("number", p["id"])
            return self.base_dir / num
        return self.base_dir / profile_id

    def get_profile_dir(self, profile_id: str) -> Path:
        """Alias for get_profile_folder to get filesystem directory Path."""
        return self.get_profile_folder(profile_id)

    def update_profile(self, profile_id: str, updated_fields: Dict[str, Any]) -> bool:
        """Update profile fields while guaranteeing immutable number and id remain locked."""
        p = self.get_profile_by_id(profile_id)
        if not p:
            return False

        old_number = p.get("number")
        old_id = p.get("id")

        p.update(updated_fields)
        if old_number:
            p["number"] = old_number
        if old_id:
            p["id"] = old_id

        self._ensure_defaults(p)
        self.save_profiles()

        p_folder = self.get_profile_folder(profile_id)
        safe_write_json(p_folder / "profile.json", p)

        if "bookmarks" in updated_fields:
            try:
                from bookmark_manager import BookmarkManager
                bm_mgr = BookmarkManager()
                bm_mgr.sync_bookmarks_to_profile(p_folder, p, custom_bookmarks=updated_fields.get("bookmarks"))
            except Exception:
                pass

        try:
            import threading
            from cloud_sync import upload_profiles_cloud_backup
            threading.Thread(target=upload_profiles_cloud_backup, args=(self.get_all_profiles(),), daemon=True).start()
        except Exception:
            pass

        return True


    def update_last_open(self, profile_id: str) -> bool:
        """Update last_open timestamp to current time."""
        p = self.get_profile_by_id(profile_id)
        if p:
            p["last_open"] = get_current_timestamp()
            self.save_profiles()
            p_folder = self.get_profile_folder(profile_id)
            safe_write_json(p_folder / "profile.json", p)
            return True
        return False

    def sync_profile_cookies_from_disk(self, profile_id: str) -> bool:
        """Extract decrypted cookies and c_user UID from profile's Chromium SQLite DB and save to profile.json."""
        p = self.get_profile_by_id(profile_id)
        if not p:
            return False

        folder_path = self.get_profile_folder(profile_id)
        if not folder_path.exists():
            return False

        import base64, json, sqlite3, shutil, uuid, tempfile
        from pathlib import Path

        # 1. Extract Windows Chromium AES Key via DPAPI
        aes_key = b""
        local_state_paths = [
            folder_path / "Local State",
            folder_path.parent / "Local State",
            folder_path.parent.parent / "Local State"
        ]
        for ls_p in local_state_paths:
            if ls_p.exists():
                try:
                    with open(ls_p, "r", encoding="utf-8") as f:
                        ls_data = json.load(f)
                    enc_key_b64 = ls_data.get("os_crypt", {}).get("encrypted_key", "")
                    if enc_key_b64:
                        raw_enc_key = base64.b64decode(enc_key_b64)
                        if raw_enc_key.startswith(b"DPAPI"):
                            import ctypes
                            from ctypes import wintypes
                            class DATA_BLOB(ctypes.Structure):
                                _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
                            enc_bytes = raw_enc_key[5:]
                            p_blob_in = DATA_BLOB(len(enc_bytes), ctypes.cast(ctypes.create_string_buffer(enc_bytes, len(enc_bytes)), ctypes.POINTER(ctypes.c_char)))
                            p_blob_out = DATA_BLOB()
                            if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(p_blob_in), None, None, None, None, 0, ctypes.byref(p_blob_out)):
                                aes_key = ctypes.string_at(p_blob_out.pbData, p_blob_out.cbData)
                                ctypes.windll.kernel32.LocalFree(p_blob_out.pbData)
                                break
                except Exception:
                    pass

        # 2. Locate SQLite Cookies DB
        cookie_db_paths = [
            folder_path / "Default" / "Network" / "Cookies",
            folder_path / "Default" / "Cookies"
        ]
        target_db = next((path for path in cookie_db_paths if path.exists() and path.stat().st_size > 0), None)
        if not target_db:
            return False

        temp_db = Path(tempfile.gettempdir()) / f"temp_ck_{uuid.uuid4().hex[:8]}.db"
        try:
            shutil.copy2(target_db, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
            if not cursor.fetchone():
                conn.close()
                temp_db.unlink(missing_ok=True)
                return False

            cursor.execute("SELECT host_key, name, value, encrypted_value, path, is_secure, is_httponly FROM cookies")
            rows = cursor.fetchall()
            conn.close()
            temp_db.unlink(missing_ok=True)

            if not rows:
                return False

            cookie_parts = []
            cookies_json_list = []
            cuser_uid = ""

            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            for host, name, val, enc_val, c_path, is_sec, is_http in rows:
                cookie_val = val
                if not cookie_val and enc_val:
                    try:
                        if enc_val.startswith(b"v10") or enc_val.startswith(b"v11"):
                            if aes_key:
                                nonce = enc_val[3:15]
                                ciphertext = enc_val[15:]
                                aesgcm = AESGCM(aes_key)
                                dec_bytes = aesgcm.decrypt(nonce, ciphertext, None)
                                # Modern Chromium v120+ has a 32-byte signature header prefix
                                if len(dec_bytes) > 32 and dec_bytes[32:].isascii():
                                    cookie_val = dec_bytes[32:].decode("utf-8", errors="ignore")
                                elif len(dec_bytes) > 32:
                                    cookie_val = dec_bytes[32:].decode("utf-8", errors="ignore")
                                else:
                                    cookie_val = dec_bytes.decode("utf-8", errors="ignore")
                        else:
                            import ctypes
                            from ctypes import wintypes
                            class DATA_BLOB(ctypes.Structure):
                                _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
                            p_blob_in = DATA_BLOB(len(enc_val), ctypes.cast(ctypes.create_string_buffer(enc_val, len(enc_val)), ctypes.POINTER(ctypes.c_char)))
                            p_blob_out = DATA_BLOB()
                            if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(p_blob_in), None, None, None, None, 0, ctypes.byref(p_blob_out)):
                                cookie_val = ctypes.string_at(p_blob_out.pbData, p_blob_out.cbData).decode("utf-8", errors="ignore")
                                ctypes.windll.kernel32.LocalFree(p_blob_out.pbData)
                    except Exception:
                        pass

                if name and cookie_val:
                    cookie_parts.append(f"{name}={cookie_val}")
                    cookies_json_list.append({
                        "domain": host,
                        "name": name,
                        "value": cookie_val,
                        "path": c_path or "/",
                        "secure": bool(is_sec),
                        "httpOnly": bool(is_http)
                    })
                    if name in ["c_user", "cuser"] and str(cookie_val).isdigit():
                        cuser_uid = str(cookie_val)

            cookie_str = "; ".join(cookie_parts)
            if cookie_str or cookies_json_list:
                p["cookie"] = cookie_str
                p["cookies_json"] = cookies_json_list
                if cuser_uid:
                    p["uid"] = cuser_uid
                try:
                    disk_profile = safe_read_json(folder_path / "profile.json")
                    if isinstance(disk_profile, dict) and disk_profile.get("group"):
                        p["group"] = disk_profile["group"]
                except Exception:
                    pass
                self.save_profiles()
                safe_write_json(folder_path / "profile.json", p)
                return True
        except Exception as e:
            if temp_db.exists():
                temp_db.unlink(missing_ok=True)
            print(f"[EXTRACT COOKIES ERROR]: {e}")

        return False

    def delete_profile(self, profile_id: str, save_db: bool = True, sync_cloud: bool = True) -> bool:
        """Delete a profile metadata entry and erase its filesystem folder."""
        # 1. Record in local persistent tombstone ledger immediately
        self.record_deleted_profiles([profile_id])

        folder_path = self.get_profile_folder(profile_id)
        if folder_path and folder_path.exists():
            try:
                shutil.rmtree(folder_path, ignore_errors=True)
            except Exception as err:
                print(f"[Error] Failed to remove folder {folder_path}: {err}")

        self.profiles = [item for item in self.profiles if item.get("id") != profile_id]
        if save_db:
            self.save_profiles()

        if sync_cloud:
            try:
                import threading
                from cloud_sync import upload_profiles_cloud_backup, sync_tracker

                sync_tracker.register_deletion([profile_id])

                def _sync_single_delete_worker():
                    try:
                        ok, msg, _ = upload_profiles_cloud_backup(
                            profiles=self.profiles,
                            allow_empty_purge=True,
                            deleted_profile_ids=[profile_id]
                        )
                        if ok:
                            self.clear_tombstones([profile_id])
                    except Exception as e:
                        print(f"[CLOUD UPLOAD ON DELETE ERROR]: {e}")
                    finally:
                        sync_tracker.mark_deletion_complete([profile_id])

                t = threading.Thread(target=_sync_single_delete_worker, daemon=False)
                sync_tracker.track_thread(t)
                t.start()
            except Exception as e:
                print(f"[CLOUD DELETE THREAD ERROR]: {e}")

        return True

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Return list of all current profiles."""
        return list(self.profiles)

    def bulk_delete_profiles(self, profile_ids: List[str], progress_callback: Optional[Any] = None) -> int:
        """Delete multiple profiles with batch I/O optimization and live progress feedback."""
        if not profile_ids:
            return 0

        # 1. Record all target IDs into persistent tombstone ledger immediately
        self.record_deleted_profiles(profile_ids)

        deleted_count = 0
        total = len(profile_ids)
        for idx, pid in enumerate(profile_ids):
            if self.delete_profile(pid, save_db=False, sync_cloud=False):
                deleted_count += 1
            if progress_callback and callable(progress_callback):
                progress_callback(idx + 1, total, pid)

        # Batch save once at the end
        self.save_profiles()

        try:
            import threading
            from cloud_sync import upload_profiles_cloud_backup, sync_tracker

            sync_tracker.register_deletion(profile_ids)

            def _sync_bulk_delete_worker():
                try:
                    ok, msg, _ = upload_profiles_cloud_backup(
                        profiles=self.profiles,
                        allow_empty_purge=True,
                        deleted_profile_ids=profile_ids
                    )
                    if ok:
                        self.clear_tombstones(profile_ids)
                except Exception as ex:
                    print(f"[BULK DELETE CLOUD SYNC ERROR]: {ex}")
                finally:
                    sync_tracker.mark_deletion_complete(profile_ids)

            t = threading.Thread(target=_sync_bulk_delete_worker, daemon=False)
            sync_tracker.track_thread(t)
            t.start()
        except Exception as e:
            print(f"[BULK DELETE THREAD ERROR]: {e}")

        return deleted_count

    def bulk_update_group(self, profile_ids: List[str], new_group: str) -> int:
        """Bulk reassign group for multiple profiles."""
        count = 0
        for pid in profile_ids:
            if self.update_profile(pid, {"group": new_group}):
                count += 1
        return count

    def duplicate_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Duplicate an existing profile, creating a new directory and metadata."""
        src_profile = self.get_profile_by_id(profile_id)
        if not src_profile:
            return None

        src_folder = self.get_profile_folder(profile_id)
        new_number = self.get_next_profile_number()
        new_id = str(uuid.uuid4())
        new_name = f"{src_profile['name']} (Copy)"
        now_str = get_current_timestamp()

        new_profile_data = src_profile.copy()
        new_profile_data.update({
            "id": new_id,
            "number": new_number,
            "name": new_name,
            "created_at": now_str,
            "last_open": "",
            "total_launches": 0,
            "total_runtime_sec": 0,
            "launch_history": []
        })

        new_folder = self.base_dir / new_number
        new_folder.mkdir(parents=True, exist_ok=True)

        if src_folder.exists():
            for item in src_folder.iterdir():
                if item.name == "profile.json":
                    continue
                try:
                    if item.is_dir():
                        shutil.copytree(item, new_folder / item.name)
                    else:
                        shutil.copy2(item, new_folder / item.name)
                except Exception as err:
                    print(f"[Warning] Error copying {item.name}: {err}")

        safe_write_json(new_folder / "profile.json", new_profile_data)
        self.profiles.append(new_profile_data)
        self.save_profiles()
        return new_profile_data

    def filter_and_sort(
        self,
        query: str = "",
        sort_mode: str = "Newest",
        category_filter: str = "All",
        group_filter: str = "All Groups"
    ) -> List[Dict[str, Any]]:
        """Filter profiles by query, group, category, and sort mode."""
        results = self.profiles.copy()

        if group_filter != "All Groups":
            results = [p for p in results if p.get("group", "Default") == group_filter]

        if category_filter != "All":
            results = [p for p in results if p.get("category", "General") == category_filter]

        if query.strip():
            raw_q = query.strip().lower()

            # Check for multiple search tokens (comma/semicolon-separated or multiple space-separated numbers)
            multi_tokens = []
            if "," in raw_q or ";" in raw_q:
                multi_tokens = [t.strip() for t in re.split(r"[,;]+", raw_q) if t.strip()]
            else:
                parts = raw_q.split()
                if len(parts) > 1 and all(re.sub(r"\D", "", p) for p in parts):
                    multi_tokens = parts

            if len(multi_tokens) > 1:
                # Multi-profile search mode
                parsed_numbers = set()
                parsed_strings = set()
                for tok in multi_tokens:
                    c_tok = tok.lstrip("#").strip()
                    digits = re.sub(r"\D", "", c_tok)
                    if digits:
                        parsed_numbers.add(digits)
                    if c_tok:
                        parsed_strings.add(c_tok)

                def _matches_multi(p: Dict[str, Any]) -> bool:
                    p_num = str(p.get("number", "")).lower().strip()
                    p_num_clean = p_num.lstrip("#").strip()
                    num_digits = re.sub(r"\D", "", p_num)

                    p_name = str(p.get("name", "")).lower().strip()
                    p_name_clean = p_name.lstrip("#").strip()
                    name_digits = re.sub(r"\D", "", p_name)

                    # 1. Direct number matches
                    if num_digits and num_digits in parsed_numbers:
                        return True
                    if name_digits and name_digits in parsed_numbers:
                        return True
                    if p_num_clean in parsed_strings or p_num in parsed_strings:
                        return True
                    if p_name_clean in parsed_strings or p_name in parsed_strings:
                        return True

                    # 2. Substring match for string tokens
                    for s in parsed_strings:
                        if len(s) >= 2 and (s in p_name or s in p_num or s in str(p.get("notes", "")).lower()):
                            return True
                    return False

                results = [p for p in results if _matches_multi(p)]
            else:
                q = raw_q
                clean_q = q.lstrip("#").strip()

                def _matches_query(p: Dict[str, Any]) -> bool:
                    p_num = str(p.get("number", "")).lower()
                    p_num_clean = p_num.lstrip("#")
                    p_name = str(p.get("name", "")).lower()
                    p_name_clean = p_name.lstrip("#")
                    num_digits = re.sub(r"\D", "", p_num)

                    # Smart number match (e.g. user typed '5' and profile is '#5' or user typed '1405')
                    if clean_q and (p_num_clean == clean_q or p_name_clean == clean_q or (clean_q.isdigit() and num_digits == clean_q)):
                        return True
                    if q in p_name or q in p_num or (clean_q and (clean_q in p_num_clean or clean_q in p_name_clean)):
                        return True
                    if q in str(p.get("notes", "")).lower():
                        return True
                    if q in str(p.get("group", "")).lower():
                        return True
                    if q in str(p.get("category", "")).lower():
                        return True
                    if q in str(p.get("start_url", "")).lower():
                        return True
                    return False

                results = [p for p in results if _matches_query(p)]
                if clean_q.isdigit():
                    # Prioritize exact number match at the very top of results
                    results.sort(
                        key=lambda p: 0 if str(p.get("number", "")).lower().lstrip("#") == clean_q or str(p.get("name", "")).lower().lstrip("#") == clean_q or re.sub(r"\D", "", str(p.get("number", ""))) == clean_q else 1
                    )

        def _get_sort_num(p: Dict[str, Any]) -> int:
            raw = str(p.get("number") or p.get("name") or "")
            digits = re.sub(r"\D", "", raw)
            return int(digits) if digits else 0

        if sort_mode in ("Newest", "Newest First", "Newest (# Desc)"):
            results.sort(key=lambda x: (_get_sort_num(x), str(x.get("created_at", ""))), reverse=True)
        elif sort_mode in ("Oldest", "Oldest First", "Oldest (# Asc)"):
            results.sort(key=lambda x: (_get_sort_num(x), str(x.get("created_at", ""))))
        elif sort_mode == "Alphabetical":
            results.sort(key=lambda x: str(x.get("name", "")).lower())

        return results

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Calculate statistics for the dashboard view."""
        today_count = sum(1 for p in self.profiles if is_created_today(p.get("created_at", "")))
        sorted_recent = sorted(self.profiles, key=lambda x: x.get("last_open", ""), reverse=True)
        recent_five = [p for p in sorted_recent if p.get("last_open")][:5]

        return {
            "total_profiles": len(self.profiles),
            "created_today": today_count,
            "recently_opened": recent_five
        }

    def export_profiles_csv(self, csv_filepath: Path) -> bool:
        """Export profile metadata list to a CSV file with clear Profile Number ordering."""
        formatted_rows = []
        for p in self.profiles:
            formatted_rows.append({
                "Profile_Number": p.get("number", ""),
                "Profile_Name": p.get("name", ""),
                "UID": p.get("uid", ""),
                "Password": p.get("password", ""),
                "Cookie": p.get("cookie", ""),
                "Group": p.get("group", "Default"),
                "Category": p.get("category", "Social"),
                "Created_At": p.get("created_at", "")
            })
        return export_csv_helper(csv_filepath, formatted_rows)

    def import_profiles_csv(self, csv_filepath: Path) -> Tuple[int, int]:
        """Import profile list from CSV file."""
        rows = import_csv_helper(csv_filepath)
        if not rows:
            return 0, 0

        imported = 0
        skipped = 0
        existing_numbers = {p["number"] for p in self.profiles}

        for row in rows:
            if not isinstance(row, dict) or "name" not in row:
                skipped += 1
                continue

            num = row.get("number") or self.get_next_profile_number()
            if num in existing_numbers:
                num = self.get_next_profile_number()

            item_id = str(uuid.uuid4())
            new_item = {
                "id": item_id,
                "number": num,
                "name": row.get("name", num),
                "created_at": row.get("created_at", get_current_timestamp()),
                "last_open": row.get("last_open", ""),
                "notes": row.get("notes", ""),
                "group": row.get("group", "Default"),
                "category": row.get("category", "General"),
                "color": row.get("color", "#89b4fa"),
                "start_url": row.get("start_url", ""),
                "proxy_type": row.get("proxy_type", "None"),
                "proxy_host": row.get("proxy_host", ""),
                "proxy_port": row.get("proxy_port", ""),
                "user_agent": row.get("user_agent", generate_random_user_agent()),
                "pin": row.get("pin", ""),
                "extensions": [],
                "total_launches": 0,
                "total_runtime_sec": 0,
                "launch_history": []
            }
            folder_path = self.base_dir / num
            folder_path.mkdir(parents=True, exist_ok=True)
            safe_write_json(folder_path / "profile.json", new_item)

            self.profiles.append(new_item)
            existing_numbers.add(num)
            imported += 1

        self.save_profiles()
        return imported, skipped

    def export_profile_zip(self, profile_id: str, zip_path: Path) -> bool:
        """Export an entire profile directory into a standalone ZIP archive."""
        p_folder = self.get_profile_folder(profile_id)
        if not p_folder.exists():
            return False

        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in p_folder.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(p_folder)
                        zf.write(file_path, arcname=rel_path)
            return True
        except Exception as err:
            print(f"[Error] Failed to create ZIP backup for profile {profile_id}: {err}")
            return False

    def import_profile_zip(self, zip_path: Path) -> Optional[Dict[str, Any]]:
        """Restore a profile directory from a ZIP archive."""
        if not zip_path.exists():
            return None

        new_num = self.get_next_profile_number()
        new_folder = self.base_dir / new_num
        new_id = str(uuid.uuid4())

        try:
            new_folder.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(new_folder)

            p_json_path = new_folder / "profile.json"
            p_data = safe_read_json(p_json_path) if p_json_path.exists() else {}

            p_data.update({
                "id": new_id,
                "number": new_num,
                "name": p_data.get("name", f"Restored_{new_num}"),
                "created_at": get_current_timestamp(),
                "last_open": ""
            })

            safe_write_json(p_json_path, p_data)
            self._ensure_defaults(p_data)

            self.profiles.append(p_data)
            self.save_profiles()
            return p_data

        except Exception as err:
            print(f"[Error] Failed to import profile ZIP {zip_path}: {err}")
            if new_folder.exists():
                shutil.rmtree(new_folder, ignore_errors=True)
            return None

    def export_profiles(self, json_filepath: Path) -> bool:
        """Export profile database to JSON."""
        return safe_write_json(json_filepath, self.profiles)

    def import_profiles(self, json_filepath: Path) -> Tuple[int, int]:
        """Import profiles metadata from JSON file."""
        data = safe_read_json(json_filepath)
        if not isinstance(data, list):
            return 0, 0

        imported = 0
        skipped = 0
        existing_ids = {p["id"] for p in self.profiles}
        existing_numbers = {p["number"] for p in self.profiles}

        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                skipped += 1
                continue

            if item["id"] in existing_ids:
                skipped += 1
                continue

            num = item.get("number") or self.get_next_profile_number()
            if num in existing_numbers:
                num = self.get_next_profile_number()

            item["number"] = num
            self._ensure_defaults(item)

            folder_path = self.base_dir / num
            folder_path.mkdir(parents=True, exist_ok=True)
            safe_write_json(folder_path / "profile.json", item)

            self.profiles.append(item)
            existing_ids.add(item["id"])
            existing_numbers.add(num)
            imported += 1

        self.save_profiles()
        return imported, skipped

    def import_cloud_backup_profiles(self, cloud_profiles: List[Dict[str, Any]], full_mirror: bool = True) -> Tuple[int, int]:
        """
        Import or update profile records from cloud backup JSON list.
        When full_mirror=True, mirrors cloud state exactly: removes deleted local profiles
        and adds/updates active ones.
        Returns (new_imported_count, updated_existing_count).
        """
        if not isinstance(cloud_profiles, list):
            return 0, 0

        # Filter out tombstones: Never restore profiles explicitly deleted locally
        tombstone_ids = self.get_tombstone_ids()
        if tombstone_ids:
            cloud_profiles = [
                p for p in cloud_profiles 
                if isinstance(p, dict) and str(p.get("id", "")).strip() not in tombstone_ids
            ]

        with self._lock:
            cloud_ids = {str(item.get("id")) for item in cloud_profiles if isinstance(item, dict) and item.get("id")}
            cloud_nums = {str(item.get("number")).lower() for item in cloud_profiles if isinstance(item, dict) and item.get("number")}

            # 1. Full Mirror Reconciliation: Remove local profiles that no longer exist in cloud
            if full_mirror and len(cloud_profiles) > 0:
                surviving_profiles = []
                for lp in self.profiles:
                    lp_id = str(lp.get("id", ""))
                    lp_num = str(lp.get("number", "")).lower()
                    if lp_id in cloud_ids or lp_num in cloud_nums:
                        surviving_profiles.append(lp)
                    else:
                        # Clean local obsolete folder
                        f_path = self.base_dir / lp.get("number", lp_id)
                        if f_path.exists():
                            try:
                                shutil.rmtree(f_path, ignore_errors=True)
                            except Exception:
                                pass
                self.profiles = surviving_profiles

            existing_by_id = {p.get("id"): p for p in self.profiles if isinstance(p, dict) and "id" in p}
            existing_by_num = {p.get("number"): p for p in self.profiles if isinstance(p, dict) and "number" in p}

            new_count = 0
            updated_count = 0

            for item in cloud_profiles:
                if not isinstance(item, dict):
                    continue

                p_id = item.get("id")
                p_num = item.get("number")

                # Match existing profile
                target_p = None
                if p_id and p_id in existing_by_id:
                    target_p = existing_by_id[p_id]
                elif p_num and p_num in existing_by_num:
                    target_p = existing_by_num[p_num]

                if target_p:
                    # Update credentials, extensions, hardware noise & metadata
                    for k, v in item.items():
                        if k not in ["id", "number"] and v is not None:
                            target_p[k] = v
                    self._ensure_defaults(target_p)

                    grp = target_p.get("group", "Default")
                    if grp and grp not in self.groups:
                        self.groups.append(grp)
                        safe_write_json(getattr(self, "groups_file", self.base_dir / "groups.json"), self.groups)
                    
                    folder_path = self.base_dir / target_p.get("number", "Profile001")
                    folder_path.mkdir(parents=True, exist_ok=True)
                    safe_write_json(folder_path / "profile.json", target_p)

                    try:
                        ext_list = target_p.get("extensions", [])
                        if ext_list:
                            from browser import auto_pin_extensions_in_profile
                            auto_pin_extensions_in_profile(folder_path, ext_list)
                    except Exception:
                        pass

                    try:
                        from bookmark_manager import BookmarkManager
                        bm_mgr = BookmarkManager()
                        bm_mgr.sync_bookmarks_to_profile(folder_path, target_p)
                    except Exception:
                        pass

                    updated_count += 1
                else:
                    # Create new profile from cloud snapshot
                    num = p_num or self.get_next_profile_number()
                    new_id = p_id or str(uuid.uuid4())
                    
                    new_p = dict(item)
                    new_p["id"] = new_id
                    new_p["number"] = num
                    self._ensure_defaults(new_p)

                    grp = new_p.get("group", "Default")
                    if grp and grp not in self.groups:
                        self.groups.append(grp)
                        safe_write_json(getattr(self, "groups_file", self.base_dir / "groups.json"), self.groups)

                    folder_path = self.base_dir / num
                    folder_path.mkdir(parents=True, exist_ok=True)
                    safe_write_json(folder_path / "profile.json", new_p)

                    try:
                        ext_list = new_p.get("extensions", [])
                        if ext_list:
                            from browser import auto_pin_extensions_in_profile
                            auto_pin_extensions_in_profile(folder_path, ext_list)
                    except Exception:
                        pass

                    try:
                        from bookmark_manager import BookmarkManager
                        bm_mgr = BookmarkManager()
                        bm_mgr.sync_bookmarks_to_profile(folder_path, new_p)
                    except Exception:
                        pass

                    self.profiles.append(new_p)
                    existing_by_id[new_id] = new_p
                    existing_by_num[num] = new_p
                    new_count += 1

            self.save_profiles()

            # Restore full session ZIPs in background for imported profiles
            try:
                import threading
                from cloud_sync import download_and_restore_profile_session_zip
                def _restore_all_session_zips():
                    for p in self.profiles:
                        pid = p.get("id")
                        p_num = p.get("number", pid)
                        f_path = self.base_dir / p_num
                        if pid and f_path.exists():
                            download_and_restore_profile_session_zip(pid, f_path)
                threading.Thread(target=_restore_all_session_zips, daemon=True).start()
            except Exception:
                pass

            return new_count, updated_count

    def clear_all_profiles(self) -> None:
        """Purge all profiles, local profile directories, and clear profiles.json on logout/account switch."""
        with self._lock:
            for p in self.profiles:
                p_num = p.get("number")
                if p_num:
                    folder_path = self.base_dir / p_num
                    if folder_path.exists():
                        try:
                            shutil.rmtree(folder_path, ignore_errors=True)
                        except Exception:
                            pass
            self.profiles = []
            safe_write_json(self.db_file, [])

    def clean_profile_cache(self, profile_id: str) -> int:
        """
        Safely purge temporary browser render/image/GPU caches ONLY (GPUCache, Code Cache, Media Cache, Crashpad).
        Strictly protects all cookies, local storage, IndexedDB, service workers, sessions, extensions, and bookmarks.
        Guarantees 0 account logouts. Returns total bytes cleaned.
        """
        folder = self.get_profile_folder(profile_id)
        if not folder or not folder.exists():
            return 0

        # Safe pure-cache relative paths (NEVER touch Service Worker, Cookies, Storage, IndexedDB, Sessions)
        safe_cache_targets = [
            folder / "Default" / "Cache" / "Cache_Data",
            folder / "Default" / "Cache",
            folder / "Default" / "Code Cache" / "js",
            folder / "Default" / "Code Cache" / "wasm",
            folder / "Default" / "Code Cache",
            folder / "Default" / "GPUCache",
            folder / "Default" / "DawnCache",
            folder / "Default" / "Media Cache",
            folder / "Default" / "GrShaderCache",
            folder / "Default" / "ShaderCache",
            folder / "Default" / "Crashpad" / "reports",
            folder / "Default" / "Crashpad",
            folder / "Default" / "System Reporting",
            folder / "GPUCache",
            folder / "DawnCache",
            folder / "Media Cache",
            folder / "GrShaderCache",
            folder / "ShaderCache",
            folder / "Crashpad"
        ]

        # Explicit forbidden keywords that must NEVER be touched under any circumstances
        forbidden_keywords = [
            "cookie", "storage", "bookmark", "extension", "preference", 
            "indexeddb", "session", "service worker", "login data", 
            "web data", "local state", "network", "leveldb"
        ]

        cleaned_bytes = 0
        for cache_path in safe_cache_targets:
            if cache_path.exists() and cache_path.is_dir():
                path_str = str(cache_path).lower()
                if any(kw in path_str for kw in forbidden_keywords):
                    continue
                try:
                    for f in cache_path.glob("**/*"):
                        if f.is_file():
                            try:
                                cleaned_bytes += f.stat().st_size
                            except Exception:
                                pass
                    shutil.rmtree(cache_path, ignore_errors=True)
                    cache_path.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass

        # Clean standalone temporary dump/log files
        try:
            for f in folder.glob("*.tmp"):
                if f.is_file():
                    cleaned_bytes += f.stat().st_size
                    f.unlink(missing_ok=True)
            for f in folder.glob("*.dmp"):
                if f.is_file():
                    cleaned_bytes += f.stat().st_size
                    f.unlink(missing_ok=True)
        except Exception:
            pass

        return cleaned_bytes

    def clean_all_profiles_cache(self) -> int:
        """
        Safely purge temporary caches across ALL profiles and trim RAM.
        Returns total bytes cleaned across all profiles.
        """
        total_cleaned = 0
        with self._lock:
            for p in self.profiles:
                pid = p.get("id")
                if pid:
                    total_cleaned += self.clean_profile_cache(pid)

        # Free working set memory on Windows OS
        try:
            import ctypes
            if os.name == "nt":
                ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass

        return total_cleaned

