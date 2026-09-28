"""
Browser Profile Manager - Extension Manager Module
Manages Chrome Extensions storage, manifest parsing, target scope syncing, and profile integration.
"""

import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import EXTENSIONS_DIR, EXTENSIONS_DB_FILE
from utils import safe_read_json, safe_write_json, get_current_timestamp


class ExtensionManager:
    """
    Manages Chrome extensions (.crx, .zip, or unpacked directories).
    Parses manifest.json and controls target scope syncing (all profiles, new profiles, groups).
    """

    def __init__(self, extensions_dir: Path = EXTENSIONS_DIR, db_file: Path = EXTENSIONS_DB_FILE) -> None:
        self.extensions_dir = extensions_dir
        self.db_file = db_file
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        self._load_extensions()

    def _load_extensions(self) -> None:
        """Load extensions metadata list from extensions.json."""
        data = safe_read_json(self.db_file)
        if isinstance(data, list):
            self.extensions = data
        else:
            self.extensions = []

        # Filter out old ext_relogin_helper entries as it is now managed via Tools/Scripts
        original_count = len(self.extensions)
        self.extensions = [e for e in self.extensions if e.get("id") != "ext_relogin_helper" and not ("relogin" in e.get("id", ""))]
        if len(self.extensions) != original_count:
            self._save_extensions()

    def _save_extensions(self) -> bool:
        """Save extensions metadata list to extensions.json."""
        return safe_write_json(self.db_file, self.extensions)

    def get_all_extensions(self) -> List[Dict[str, Any]]:
        """Return list of all registered extensions."""
        valid_exts = []
        changed = False
        for ext in self.extensions:
            p = Path(ext.get("path", ""))
            if p.exists() and (p / "manifest.json").exists():
                info = self.parse_manifest(p)
                if info.get("name") and (ext.get("name", "").startswith("ext_") or ext.get("name") != info.get("name")):
                    ext["name"] = info["name"]
                    changed = True
                if info.get("description") and ext.get("description") != info.get("description"):
                    ext["description"] = info["description"]
                    changed = True
                if info.get("icon_path") and ext.get("icon_path") != info.get("icon_path"):
                    ext["icon_path"] = info["icon_path"]
                    changed = True
                valid_exts.append(ext)
            else:
                changed = True

        if changed:
            self.extensions = valid_exts
            self._save_extensions()

        return self.extensions

    def _resolve_locale_msg(self, msg_ref: str, ext_folder: Path, default_locale: str = "en") -> str:
        """Resolve Chrome extension __MSG_key__ i18n messages from _locales."""
        if not str(msg_ref).startswith("__MSG_") or not str(msg_ref).endswith("__"):
            return str(msg_ref)

        key = msg_ref[6:-2].strip()
        locales_dir = ext_folder / "_locales"
        if not locales_dir.exists():
            return msg_ref

        candidates = [default_locale, "en", "en_US", "en_GB"]
        if locales_dir.exists():
            for p in locales_dir.iterdir():
                if p.is_dir():
                    candidates.append(p.name)

        for loc in candidates:
            msg_file = locales_dir / loc / "messages.json"
            if msg_file.exists():
                try:
                    with open(msg_file, "r", encoding="utf-8") as f:
                        msg_data = json.load(f)
                    if key in msg_data and "message" in msg_data[key]:
                        val = msg_data[key]["message"]
                        if val:
                            return str(val)
                    for k, v in msg_data.items():
                        if k.lower() == key.lower() and isinstance(v, dict) and "message" in v:
                            return str(v["message"])
                except Exception:
                    pass

        return msg_ref

    def _find_icon_path(self, data: dict, ext_folder: Path) -> str:
        """Extract icon file path from manifest icons dictionary."""
        icons_def = data.get("icons")
        if not icons_def:
            icons_def = data.get("action", {}).get("default_icon")
        if not icons_def:
            icons_def = data.get("browser_action", {}).get("default_icon")

        rel_path = ""
        if isinstance(icons_def, dict):
            for sz in ["128", "48", "32", "16", 128, 48, 32, 16]:
                if sz in icons_def:
                    rel_path = icons_def[sz]
                    break
            if not rel_path and icons_def:
                rel_path = list(icons_def.values())[0]
        elif isinstance(icons_def, str):
            rel_path = icons_def

        if rel_path:
            full_p = ext_folder / rel_path
            if full_p.exists():
                return str(full_p.resolve())

        for candidate_name in ["icon.png", "icon128.png", "icon48.png", "icon16.png", "logo.png"]:
            candidate = ext_folder / candidate_name
            if candidate.exists():
                return str(candidate.resolve())

        return ""

    def parse_manifest(self, ext_folder: Path) -> Dict[str, Any]:
        """Parse manifest.json inside extension directory."""
        manifest_path = ext_folder / "manifest.json"
        if not manifest_path.exists():
            return {}

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            default_locale = data.get("default_locale", "en")
            raw_name = data.get("name", ext_folder.name)
            name = self._resolve_locale_msg(raw_name, ext_folder, default_locale)
            if name.startswith("__MSG_"):
                name = ext_folder.name

            raw_desc = data.get("description", "")
            description = self._resolve_locale_msg(raw_desc, ext_folder, default_locale)
            if description.startswith("__MSG_"):
                description = ""

            version = data.get("version", "1.0")
            icon_path = self._find_icon_path(data, ext_folder)

            return {
                "name": str(name),
                "version": str(version),
                "description": str(description),
                "icon_path": icon_path
            }
        except Exception:
            return {"name": ext_folder.name, "version": "1.0", "description": "", "icon_path": ""}

    def add_extension(self, source_path_str: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Import an unpacked extension directory, .zip, or .crx archive.
        """
        source = Path(source_path_str).resolve()
        if not source.exists():
            return False, "File or folder does not exist.", None

        ext_id = f"ext_{uuid.uuid4().hex[:8]}"
        target_folder = self.extensions_dir / ext_id

        try:
            if source.is_dir():
                if not (source / "manifest.json").exists():
                    return False, "Selected folder does not contain a valid manifest.json file.", None
                shutil.copytree(source, target_folder)
            elif source.is_file() and source.suffix.lower() in (".zip", ".crx"):
                target_folder.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(source, "r") as zf:
                    zf.extractall(target_folder)

                # Check if extracted into a single nested folder
                subitems = list(target_folder.iterdir())
                if len(subitems) == 1 and subitems[0].is_dir() and (subitems[0] / "manifest.json").exists():
                    nested = subitems[0]
                    temp_move = self.extensions_dir / f"temp_{ext_id}"
                    shutil.move(str(nested), str(temp_move))
                    shutil.rmtree(str(target_folder), ignore_errors=True)
                    shutil.move(str(temp_move), str(target_folder))
            else:
                return False, "Unsupported file format. Please select a .zip, .crx file or unpacked extension folder.", None

            if not (target_folder / "manifest.json").exists():
                shutil.rmtree(str(target_folder), ignore_errors=True)
                return False, "Extension does not contain a valid manifest.json.", None

            info = self.parse_manifest(target_folder)
            record = {
                "id": ext_id,
                "name": info.get("name", source.stem),
                "version": info.get("version", "1.0"),
                "description": info.get("description", ""),
                "path": str(target_folder.resolve()),
                "is_active": True,
                "target_mode": "manual",  # "manual", "all", "new_only", "groups"
                "target_groups": [],
                "date_added": get_current_timestamp()
            }

            self.extensions.append(record)
            self._save_extensions()
            return True, f"Successfully uploaded '{record['name']}' (v{record['version']}).", record

        except Exception as err:
            if target_folder.exists():
                shutil.rmtree(str(target_folder), ignore_errors=True)
            return False, f"Failed to import extension: {str(err)}", None

    def update_extension(self, ext_id: str, updates: Dict[str, Any]) -> bool:
        """Update metadata for an existing extension."""
        for ext in self.extensions:
            if ext.get("id") == ext_id:
                ext.update(updates)
                self._save_extensions()
                return True
        return False

    def delete_extension(self, ext_id: str) -> bool:
        """Remove extension record and delete unpacked folder."""
        for i, ext in enumerate(self.extensions):
            if ext.get("id") == ext_id:
                ext_path = Path(ext.get("path", ""))
                if ext_path.exists():
                    try:
                        shutil.rmtree(str(ext_path), ignore_errors=True)
                    except Exception:
                        pass
                self.extensions.pop(i)
                self._save_extensions()
                return True
        return False

    def get_active_extension_paths_for_profile(self, profile_data: Dict[str, Any]) -> List[str]:
        """
        Get active extension folder paths targeting this profile.
        """
        active_paths = []
        prof_group = str(profile_data.get("group", "Default")).strip().lower()

        # Build lookup of disabled extension paths to prevent loading when deactivated
        disabled_identifiers = set()
        for ext in self.get_all_extensions():
            if not ext.get("is_active", True):
                p = ext.get("path", "")
                if p:
                    try:
                        disabled_identifiers.add(str(Path(p).resolve()).lower())
                    except Exception:
                        pass
                    disabled_identifiers.add(str(p).lower())
                    disabled_identifiers.add(Path(p).name.lower())
                eid = ext.get("id", "")
                if eid:
                    disabled_identifiers.add(str(eid).lower())

        for ext in self.get_all_extensions():
            if not ext.get("is_active", False):
                continue

            p = ext.get("path", "")
            if not p or not Path(p).exists():
                continue

            target_mode = ext.get("target_mode", "manual")
            if target_mode == "all":
                active_paths.append(p)
            elif target_mode == "groups":
                target_groups = [str(g).strip().lower() for g in ext.get("target_groups", [])]
                if prof_group in target_groups:
                    active_paths.append(p)
            # If target_mode is "manual", "new_only", or other, only attach if present in profile's own list

        # Combine with profile-specific extension list (strictly filtering out any disabled extensions)
        prof_exts = profile_data.get("extensions", [])
        if isinstance(prof_exts, list):
            for px in prof_exts:
                if not px:
                    continue
                px_p = Path(px)
                px_res = ""
                try:
                    px_res = str(px_p.resolve()).lower()
                except Exception:
                    pass
                if px_res in disabled_identifiers or str(px).lower() in disabled_identifiers or px_p.name.lower() in disabled_identifiers:
                    continue
                if px not in active_paths and px_p.exists():
                    active_paths.append(px)

        return active_paths

    get_active_extensions_for_profile = get_active_extension_paths_for_profile

    def sync_extension_to_profiles(
        self,
        ext_id: str,
        target_mode: str,
        target_groups: List[str] = None,
        profile_mgr = None,
        progress_callback = None
    ) -> bool:
        """
        Sync extension assignments across profiles according to target_mode.
        Optimized with batch saves and progress callback.
        """
        ext_record = None
        for ext in self.extensions:
            if ext.get("id") == ext_id:
                ext_record = ext
                break

        if not ext_record:
            return False

        ext_path = ext_record.get("path", "")
        ext_record["target_mode"] = target_mode
        ext_record["target_groups"] = target_groups or []
        self._save_extensions()

        if profile_mgr and ext_path:
            all_profs = profile_mgr.get_all_profiles()
            total_profs = len(all_profs)
            for i, prof in enumerate(all_profs):
                pid = prof.get("id")
                ext_list = prof.get("extensions", [])
                if not isinstance(ext_list, list):
                    ext_list = []

                if target_mode == "all":
                    if ext_path not in ext_list:
                        ext_list.append(ext_path)
                elif target_mode == "groups" and target_groups:
                    target_groups_clean = [str(g).strip().lower() for g in target_groups]
                    p_grp = str(prof.get("group", "Default")).strip().lower()
                    if p_grp in target_groups_clean:
                        if ext_path not in ext_list:
                            ext_list.append(ext_path)
                    else:
                        if ext_path in ext_list:
                            ext_list.remove(ext_path)
                else:
                    if ext_path in ext_list:
                        ext_list.remove(ext_path)

                prof["extensions"] = ext_list
                p_folder = profile_mgr.get_profile_folder(pid)
                try:
                    safe_write_json(p_folder / "profile.json", prof)
                except Exception:
                    pass

                try:
                    from browser import auto_pin_extensions_in_profile
                    auto_pin_extensions_in_profile(p_folder, ext_list)
                except Exception:
                    pass

                if progress_callback:
                    p_name = prof.get("name") or f"Profile #{prof.get('number', i + 1)}"
                    progress_callback(i + 1, total_profs, p_name)

            # Batch save once to profiles.json
            try:
                profile_mgr.save_profiles()
            except Exception:
                pass

            try:
                import threading
                from cloud_sync import upload_profiles_cloud_backup
                threading.Thread(target=upload_profiles_cloud_backup, args=(all_profs,), daemon=True).start()
            except Exception:
                pass

        return True

    apply_extension_to_profiles = sync_extension_to_profiles
