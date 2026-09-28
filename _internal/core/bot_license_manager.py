"""
Browser Profile Manager - Per-Bot Licensing & Machine HWID Security Module
Python 3.13 / PySide6 Desktop Application
"""

import json
import os
import platform
import uuid
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_machine_hwid() -> str:
    """Generate a unique, stable hardware identification string for the host system."""
    try:
        raw = f"{platform.node()}-{platform.processor()}-{uuid.getnode()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32].upper()
    except Exception:
        return "HWID-DEFAULT-0000000000000000"


class BotLicenseManager:
    """Manages per-bot license keys, HWID verification, and local license caching."""

    def __init__(self, app_dir: Optional[Path] = None) -> None:
        if app_dir:
            self.base_dir = Path(app_dir)
        else:
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            self.base_dir = Path(appdata) / "BrowserProfileManager"

        self.licenses_dir = self.base_dir / "licenses"
        self.licenses_dir.mkdir(parents=True, exist_ok=True)
        self.hwid = get_machine_hwid()

    def _get_cache_path(self, bot_id: str) -> Path:
        clean_id = str(bot_id).strip().lower().replace(" ", "_")
        return self.licenses_dir / f"lic_{clean_id}.json"

    def quick_online_check(self, key: str, bot_id: str) -> Tuple[bool, str]:
        """Fast 3-second online check to verify if key was revoked by Admin."""
        try:
            payload = json.dumps({
                "action": "verify",
                "key": key,
                "license_key": key,
                "hwid": self.hwid,
                "bot_id": bot_id
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://srbrowser.com/api/v1/bot/verify",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "srkBrowserApp/2.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("status") == "success" or res.get("valid"):
                    return True, "Valid"
                else:
                    return False, res.get("message", "Revoked")
        except urllib.error.HTTPError as e:
            if e.code in [403, 404]:
                return False, "Revoked"
            return True, "Offline"
        except Exception:
            return True, "Offline"

    def send_bot_pulse(self, bot_id: str, token: str = "") -> None:
        """Sends lightweight heartbeat pulse while bot is running."""
        try:
            payload = json.dumps({
                "bot_id": bot_id,
                "hwid": self.hwid,
                "token": token
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://srbrowser.com/api/v1/bot/pulse",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "srkBrowserApp/2.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
        except Exception:
            pass

    def send_bot_stop(self, bot_id: str, token: str = "") -> None:
        """Notifies server when bot execution completes or dialog closes."""
        try:
            payload = json.dumps({
                "bot_id": bot_id,
                "hwid": self.hwid,
                "token": token
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://srbrowser.com/api/v1/bot/stop_session",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "srkBrowserApp/2.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                pass
        except Exception:
            pass

    def purge_all_cached_licenses(self) -> None:
        """Purge all cached license files when key is revoked."""
        try:
            for p in self.licenses_dir.glob("lic_*.json"):
                try:
                    p.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    def _async_sync_online(self, bot_id: str, key: str) -> None:
        """Non-blocking daemon thread to sync remaining days from server without lagging UI."""
        try:
            payload = json.dumps({
                "action": "verify",
                "key": key,
                "license_key": key,
                "hwid": self.hwid,
                "bot_id": bot_id
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://srbrowser.com/api/v1/bot/verify",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "srkBrowserApp/2.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("status") == "success" or res.get("valid"):
                    exp_date = res.get("expiry_date")
                    exp_days = res.get("expiry_days", 30)
                    if exp_date:
                        lic_data = {
                            "key": key,
                            "expiry_date": exp_date,
                            "expiry_days": exp_days,
                            "is_active": True
                        }
                        self.save_local_license(bot_id, key, lic_data)
                        self.save_local_license("all_bots", key, lic_data)
                else:
                    self.purge_all_cached_licenses()
        except urllib.error.HTTPError as e:
            if e.code in [401, 403, 404]:
                self.purge_all_cached_licenses()
        except Exception:
            pass

    def get_local_license(self, bot_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_cache_path(bot_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("hwid") == self.hwid and data.get("is_active", True):
                        return data
            except Exception:
                pass
        return None

    def get_license_status_label(self, bot_id: str, is_free_module: bool = False) -> str:
        """Returns user-friendly string for license validity and remaining days."""
        # 1. Check logged-in user Enterprise account status
        try:
            from auth_manager import AuthManager
            auth_mgr = AuthManager()
            user = auth_mgr.get_current_user()
            if user and (user.get("is_logged_in") or user.get("token")):
                plan_str = str(user.get("plan_type", "")).upper()
                m_type = str(user.get("membership_type", "")).upper()
                p_id = str(user.get("plan_id", "")).upper()
                u_role = str(user.get("role", "")).upper()
                if "ENTERPRISE" in plan_str or "ENTERPRISE" in m_type or "ENTERPRISE" in p_id or "ADMIN" in u_role or "LIFETIME" in m_type or "LIFETIME" in plan_str:
                    return "⭐ License: Enterprise Access"
        except Exception:
            pass

        # 2. Check for active license for this specific bot OR all_bots Master VIP license
        lic = self.get_local_license(bot_id) or self.get_local_license("all_bots")
        if not lic:
            # Check any cached lic file in licenses_dir
            for p in self.licenses_dir.glob("lic_*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        if d.get("key", "").startswith("SRVIP-MASTER") or d.get("bot_id") in ["all_bots", "SRVIP_MASTER"]:
                            lic = d
                            break
                except Exception:
                    pass

        if lic:
            key_str = str(lic.get("key", "")).upper()
            if key_str and not getattr(self, "_synced_bg", False):
                self._synced_bg = True
                import threading
                threading.Thread(target=self._async_sync_online, args=(bot_id, key_str), daemon=True).start()

            exp_date = str(lic.get("expiry_date", "")).strip()
            exp_days = lic.get("expiry_days", 30)

            rem_days = exp_days
            if exp_date and len(exp_date) >= 10 and "lifetime" not in exp_date.lower():
                try:
                    from datetime import datetime
                    import math
                    exp_dt = datetime.strptime(exp_date.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    diff = exp_dt - datetime.now()
                    rem_days = max(0, math.ceil(diff.total_seconds() / 86400.0))
                except Exception:
                    pass

            days_label = "Lifetime Active" if "lifetime" in exp_date.lower() else f"{rem_days} Days Left"

            if "SRVIP-MASTER" in key_str or lic.get("bot_id") in ["all_bots", "SRVIP_MASTER"]:
                return f"👑 VIP User ({days_label})"
            else:
                return f"🔑 License: Active ({days_label})"

        if is_free_module:
            return "🎁 License: Free Module"

        return "🔒 License: Premium Required"

    def save_local_license(self, bot_id: str, key: str, status_data: Dict[str, Any]) -> None:
        clean_k = key.strip()
        payload = {
            "bot_id": bot_id,
            "key": clean_k,
            "hwid": self.hwid,
            "is_active": True,
            "expiry_days": status_data.get("expiry_days", 30),
            "expiry_date": status_data.get("expiry_date", "Lifetime Access"),
            "activated_at": status_data.get("activated_at", "")
        }

        path = self._get_cache_path(bot_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

        # If it's an SRVIP Master Key, ALSO save lic_all_bots.json as wildcard VIP license!
        if clean_k.startswith("SRVIP-MASTER") or bot_id in ["all_bots", "SRVIP_MASTER"]:
            payload["bot_id"] = "all_bots"
            path_master = self._get_cache_path("all_bots")
            try:
                with open(path_master, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception:
                pass

    def remove_local_license(self, bot_id: str) -> bool:
        """Remove cached local license for a bot so it can be uninstalled/deactivated."""
        path = self._get_cache_path(bot_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception:
                pass
        return False

    def verify_bot_license(
        self,
        bot_id: str,
        license_key: str,
        api_url: str = "https://srbrowser.com/api/v1/bot/verify"
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verifies per-bot key against remote server API.
        Returns: (success: bool, message: str, license_info: dict)
        """
        clean_key = license_key.strip()
        if not clean_key:
            return False, "Please enter a valid License Key.", {}

        endpoints = [
            "https://srbrowser.com/api/v1/bot/verify",
            "https://srbrowser.com/api/verify-license.php",
            api_url
        ]

        last_err = "License Key verification failed. Internet connection required."

        for endpoint in endpoints:
            try:
                payload = json.dumps({
                    "action": "verify",
                    "key": clean_key,
                    "license_key": clean_key,
                    "hwid": self.hwid,
                    "bot_id": bot_id
                }).encode("utf-8")

                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "srkBrowserApp/2.0"
                    },
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=8) as response:
                    res_raw = response.read().decode("utf-8")
                    res = json.loads(res_raw)

                    if res.get("status") == "success" or res.get("valid"):
                        info = {
                            "bot_id": bot_id,
                            "key": clean_key,
                            "expiry_date": res.get("expiry_date", "30 Days Active"),
                            "expiry_days": res.get("expiry_days", 30)
                        }
                        self.save_local_license(bot_id, clean_key, info)
                        return True, "License key verified and activated successfully!", info
                    else:
                        msg = res.get("message") or "Invalid or expired License Key."
                        return False, msg, {}
            except Exception as e:
                last_err = str(e)
                continue

        # Check offline cache if server unreachable
        cached = self.get_local_license(bot_id)
        if cached and cached.get("key") == clean_key and cached.get("hwid") == self.hwid:
            return True, "License active (Offline Mode).", cached

        return False, f"License verification failed: {last_err}", {}

    @property
    def deactivated_file(self) -> Path:
        return self.base_dir / "user_deactivated_items.json"

    def get_deactivated_items(self) -> Dict[str, List[str]]:
        if not self.deactivated_file.exists():
            return {"bots": [], "tools": [], "scripts": []}
        try:
            with open(self.deactivated_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {
                        "bots": list(data.get("bots", [])),
                        "tools": list(data.get("tools", [])),
                        "scripts": list(data.get("scripts", []))
                    }
        except Exception:
            pass
        return {"bots": [], "tools": [], "scripts": []}

    def deactivate_item(self, item_type: str, item_id: str) -> None:
        data = self.get_deactivated_items()
        clean_id = str(item_id).strip()
        t = "bots" if "bot" in item_type else ("tools" if "tool" in item_type else "scripts")
        if clean_id not in data[t]:
            data[t].append(clean_id)
        if clean_id == "fb_quick_page_create" and "fb_quick_page_creator" not in data[t]:
            data[t].append("fb_quick_page_creator")
        elif clean_id == "fb_quick_page_creator" and "fb_quick_page_create" not in data[t]:
            data[t].append("fb_quick_page_create")
        try:
            self.deactivated_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.deactivated_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def activate_item(self, item_type: str, item_id: str) -> None:
        data = self.get_deactivated_items()
        clean_id = str(item_id).strip()
        t = "bots" if "bot" in item_type else ("tools" if "tool" in item_type else "scripts")
        if clean_id in data[t]:
            data[t].remove(clean_id)
        if clean_id == "fb_quick_page_create" and "fb_quick_page_creator" in data[t]:
            data[t].remove("fb_quick_page_creator")
        elif clean_id == "fb_quick_page_creator" and "fb_quick_page_create" in data[t]:
            data[t].remove("fb_quick_page_create")
        try:
            self.deactivated_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.deactivated_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def is_item_deactivated(self, item_type: str, item_id: str) -> bool:
        data = self.get_deactivated_items()
        clean_id = str(item_id).strip()
        t = "bots" if "bot" in item_type else ("tools" if "tool" in item_type else "scripts")
        items = data.get(t, [])
        if clean_id in items:
            return True
        if clean_id == "fb_quick_page_create" and "fb_quick_page_creator" in items:
            return True
        if clean_id == "fb_quick_page_creator" and "fb_quick_page_create" in items:
            return True
        return False
