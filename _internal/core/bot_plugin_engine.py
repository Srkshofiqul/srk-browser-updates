"""
Browser Profile Manager - Dynamic Cloud Bot Plugin Downloader & Execution Engine
Python 3.13 / PySide6 Desktop Application
Developer: Srk Shofiqul (srbrowser.com)
"""

import json
import os
import shutil
import urllib.request
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class BotPluginEngine:
    """Manages downloadable bot modules, version tracking, remote downloading, and runtime execution."""

    DEFAULT_BOTS_MANIFEST: List[Dict[str, Any]] = []

    def __init__(self, app_dir: Optional[Path] = None) -> None:
        if app_dir:
            self.base_dir = Path(app_dir)
        else:
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            self.base_dir = Path(appdata) / "BrowserProfileManager"

        self.modules_dir = self.base_dir / "modules" / "bots"
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        self._remote_manifest = self._load_remote_manifest_cache()

    def _load_remote_manifest_cache(self) -> List[Dict[str, Any]]:
        manifest_file = self.base_dir / "remote_bots_manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def get_all_bots(self) -> List[Dict[str, Any]]:
        """Returns bots manifest from memory/cache or disk without blocking on network calls, merging local bundled bots."""
        bots = list(self._remote_manifest) if (self._remote_manifest and len(self._remote_manifest) > 0) else []
        if not bots:
            cached = self._load_remote_manifest_cache()
            if cached:
                bots = list(cached)

        # Merge bundled local manifests so newly added bots (like 04_FB_Comment_Marketing_Bot, 05_FB_Reels_Algo_Trainer_Bot) are always included
        try:
            base_cand = Path(__file__).resolve().parent.parent.parent
            for cand in [
                Path(sys.executable).parent / "03_Automation_Bots" / "bots_manifest.json",
                base_cand / "03_Automation_Bots" / "bots_manifest.json",
                base_cand.parent / "03_Automation_Bots" / "bots_manifest.json",
                Path(__file__).resolve().parent.parent / "03_Automation_Bots" / "bots_manifest.json"
            ]:
                if cand.exists():
                    with open(cand, "r", encoding="utf-8") as f:
                        local_data = json.load(f)
                        if isinstance(local_data, list):
                            existing_ids = set((b.get("bot_id") or b.get("id")) for b in bots)
                            for lb in local_data:
                                lbid = lb.get("bot_id") or lb.get("id")
                                if lbid and lbid not in existing_ids:
                                    bots.append(lb)
                                    existing_ids.add(lbid)
                    break
        except Exception:
            pass

        self._remote_manifest = bots
        return list(bots)

    def fetch_remote_manifest(self) -> List[Dict[str, Any]]:
        """Syncs latest published bots manifest from srbrowser.com API if online, preserving bundled bots."""
        try:
            from core.network_guard import is_internet_available
            if not is_internet_available(timeout_sec=0.8):
                return self.get_all_bots()
        except Exception:
            pass

        remote_url = "https://srbrowser.com/api/v1/bot/manifest"
        try:
            req = urllib.request.Request(remote_url, headers={"User-Agent": "srkBrowser Desktop App"})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, list):
                    self._remote_manifest = data
                    merged = self.get_all_bots()
                    manifest_file = self.base_dir / "remote_bots_manifest.json"
                    with open(manifest_file, "w", encoding="utf-8") as f:
                        json.dump(merged, f, indent=2)
                    return merged
        except Exception:
            pass
        return self.get_all_bots()

    def _load_installed_versions(self) -> Dict[str, str]:
        ver_file = self.base_dir / "installed_versions.json"
        if ver_file.exists():
            try:
                with open(ver_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_installed_version(self, bot_id: str, version: str) -> None:
        versions = self._load_installed_versions()
        versions[bot_id] = version
        ver_file = self.base_dir / "installed_versions.json"
        try:
            with open(ver_file, "w", encoding="utf-8") as f:
                json.dump(versions, f, indent=2)
        except Exception:
            pass

    def get_installed_version(self, bot_id: str) -> str:
        versions = self._load_installed_versions()
        if bot_id in versions:
            return str(versions[bot_id])
        # If locally bundled in 03_Automation_Bots, read version from local manifest
        try:
            base_cand = Path(__file__).resolve().parent.parent.parent
            for cand in [
                base_cand / "03_Automation_Bots" / "bots_manifest.json",
                base_cand.parent / "03_Automation_Bots" / "bots_manifest.json",
                Path(__file__).resolve().parent.parent / "03_Automation_Bots" / "bots_manifest.json"
            ]:
                if cand.exists():
                    with open(cand, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                        for b in manifest:
                            if (b.get("id") or b.get("bot_id")) == bot_id:
                                ver = str(b.get("version", "2.0.0"))
                                self._save_installed_version(bot_id, ver)
                                return ver
                    break
        except Exception:
            pass
        return "2.0.0"

    def get_remote_version(self, bot_id: str) -> str:
        manifest = self._remote_manifest or []
        for b in manifest:
            b_id = b.get("id") or b.get("bot_id")
            if b_id == bot_id:
                return str(b.get("version", "2.0.0"))
        return "2.0.0"

    def is_update_available(self, bot_id: str) -> Tuple[bool, str, str]:
        """Returns (is_update_available, installed_ver, remote_ver)."""
        installed = self.get_installed_version(bot_id)
        remote = self.get_remote_version(bot_id)
        
        def parse_ver(v_str):
            try:
                parts = [int(x) for x in str(v_str).replace("v", "").strip().split(".")]
                while len(parts) < 3:
                    parts.append(0)
                return parts
            except Exception:
                return [1, 0, 0]

        is_newer = parse_ver(remote) > parse_ver(installed)
        return is_newer, installed, remote

    def is_bot_installed(self, bot_id: str) -> bool:
        """Checks if bot files exist in the user's local modules directory or bundled 03_Automation_Bots."""
        bot_dir = self.modules_dir / bot_id
        if bot_dir.exists():
            py_files = list(bot_dir.glob("*.py"))
            if py_files:
                return True
        # Check bundled 03_Automation_Bots
        try:
            base_cand = Path(__file__).resolve().parent.parent.parent
            for cand in [
                Path(sys.executable).parent / "03_Automation_Bots",
                base_cand / "03_Automation_Bots",
                base_cand.parent / "03_Automation_Bots",
                Path(__file__).resolve().parent.parent / "03_Automation_Bots"
            ]:
                if cand.exists():
                    for sd in cand.iterdir():
                        if sd.is_dir() and (bot_id in sd.name.lower() or sd.name.lower() in bot_id or ("video" in bot_id and "video" in sd.name.lower()) or ("page" in bot_id and "page" in sd.name.lower()) or ("login" in bot_id and "login" in sd.name.lower()) or ("comment" in bot_id and "comment" in sd.name.lower()) or ("algo" in bot_id and "algo" in sd.name.lower())):
                            if list(sd.glob("*.py")):
                                return True
        except Exception:
            pass
        return False

    def uninstall_bot_module(self, bot_id: str) -> bool:
        """Uninstalls and removes downloaded bot module directory."""
        target_dir = self.modules_dir / bot_id
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir, ignore_errors=True)
                return True
            except Exception:
                pass
        return True

    def download_bot_module(self, bot_id: str, remote_url: str = "") -> Tuple[bool, str]:
        """Downloads dynamic bot module package from srbrowser.com into %AppData%/BrowserProfileManager/modules/bots/<bot_id>/."""
        target_dir = self.modules_dir / bot_id
        target_dir.mkdir(parents=True, exist_ok=True)

        target_dest = target_dir / f"{bot_id}_bot.py"
        download_src = remote_url or f"https://srbrowser.com/api/v1/store/bots/{bot_id}/download"

        try:
            req = urllib.request.Request(download_src, headers={"User-Agent": "srkBrowser Desktop App"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                content = resp.read()
                # If server returned JSON error instead of script
                if content.startswith(b'{"status": "error"') or content.startswith(b'{"status":"error"'):
                    try:
                        err_data = json.loads(content.decode("utf-8"))
                        return False, err_data.get("message", "Module download error")
                    except Exception:
                        pass

                with open(target_dest, "wb") as out_f:
                    out_f.write(content)

            remote_ver = self.get_remote_version(bot_id)
            self._save_installed_version(bot_id, remote_ver)
            return True, f"Successfully downloaded bot '{bot_id}' (v{remote_ver})!"
        except Exception as e:
            return False, f"Download failed: {e}"
