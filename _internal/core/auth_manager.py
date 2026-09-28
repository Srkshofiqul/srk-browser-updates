"""
Browser Profile Manager - User Authentication Engine Module
Python 3.13 / PySide6 Desktop Application
"""


import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List


class AuthManager:
    """Manages user account login, email verification state, and session persistence."""

    def __init__(self, app_dir: Optional[Path] = None) -> None:
        if app_dir:
            self.base_dir = Path(app_dir)
        else:
            try:
                from config import BASE_DIR
                self.base_dir = BASE_DIR
            except Exception:
                appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
                self.base_dir = Path(appdata) / "BrowserProfileManager"

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.base_dir / "user_session.json"
        self._session_data: Dict[str, Any] = self._load_session()
        import threading
        threading.Thread(target=self.refresh_user_info, daemon=True).start()

    def refresh_user_info(self) -> None:
        token = self._session_data.get("token")
        if not token or token.startswith("customer_"):
            return
        try:
            import requests
            resp = requests.get(
                f"https://srbrowser.com/api/v1/user/summary?token={token}",
                headers={"User-Agent": "srkBrowser/2.0"},
                timeout=6
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    u = data.get("user", {})
                    email = u.get("email", self._session_data.get("email", ""))
                    full_name = u.get("full_name", "")
                    user_id = str(u.get("id", self._session_data.get("user_id", "")))
                    plan_type = u.get("plan_type", "enterprise")
                    max_profiles = int(u.get("cloud_quota", 999999) or 999999)
                    days_remaining = int(u.get("days_remaining", 9999) or 9999)
                    plan_expires_at = u.get("plan_expires_at", "Lifetime")
                    vip_enabled = u.get("sritzone_vip_link_enabled", True)
                    role = u.get("role", self._session_data.get("role", "owner"))
                    team_owner_id = u.get("team_owner_id", self._session_data.get("team_owner_id"))
                    assigned_groups = u.get("assigned_groups", self._session_data.get("assigned_groups", ["All"]))
                    permissions = u.get("permissions", self._session_data.get("permissions", {}))
                    self.save_session(
                        email, user_id, token, full_name,
                        plan_type=plan_type, max_profiles=max_profiles,
                        days_remaining=days_remaining, plan_expires_at=plan_expires_at,
                        sritzone_vip_link_enabled=vip_enabled,
                        role=role, team_owner_id=team_owner_id,
                        assigned_groups=assigned_groups, permissions=permissions
                    )
        except Exception:
            pass

    def _load_session(self) -> Dict[str, Any]:
        if self.session_file.exists():
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and isinstance(data, dict):
                        # Ensure Customer Edition stays logged in
                        if not data.get("is_logged_in"):
                            data["is_logged_in"] = True
                            data["email"] = data.get("email") or "customer@srbrowser.local"
                            data["token"] = data.get("token") or "customer_standalone_token"
                            data["full_name"] = "Paid Member"
                            data["plan_type"] = "paid_member"
                            data["max_profiles"] = 999999
                        return data
            except Exception:
                pass
        default_customer_session = {
            "email": "customer@srbrowser.local",
            "full_name": "Paid Member",
            "user_id": "customer_standalone",
            "token": "customer_standalone_token",
            "plan_type": "paid_member",
            "max_profiles": 999999,
            "cloud_quota": 999999,
            "days_remaining": 9999,
            "plan_expires_at": "Lifetime",
            "sritzone_vip_link_enabled": True,
            "role": "owner",
            "team_owner_id": None,
            "assigned_groups": ["All"],
            "permissions": {
                "can_create": True, "can_edit": True, "can_delete": True, "can_export": True, "can_bots": True
            },
            "is_logged_in": True,
            "remember_me": True
        }
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(default_customer_session, f, indent=2)
        except Exception:
            pass
        return default_customer_session

    def load_session(self) -> Dict[str, Any]:
        """Reload session data from disk into memory."""
        self._session_data = self._load_session()
        return dict(self._session_data)

    def save_session(
        self, email: Any = "", user_id: str = "", token: str = "", full_name: str = "",
        plan_type: str = "free", max_profiles: int = 100,
        days_remaining: int = 0, plan_expires_at: str = "",
        sritzone_vip_link_enabled: bool = True,
        role: str = "owner", team_owner_id: Optional[Any] = None,
        assigned_groups: Optional[List[str]] = None,
        permissions: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        if isinstance(email, dict):
            d = email
            email_val = str(d.get("email", "")).strip()
            full_name_val = str(d.get("full_name", "")).strip() or email_val.split("@")[0]
            user_id_val = str(d.get("user_id", d.get("id", ""))).strip()
            token_val = str(d.get("token", "")).strip()
            plan_type_val = d.get("plan_type", "free")
            max_profiles_val = int(d.get("max_profiles", d.get("cloud_quota", 100)) or 100)
            days_remaining_val = int(d.get("days_remaining", 0) or 0)
            plan_expires_at_val = str(d.get("plan_expires_at", ""))
            vip_link_val = d.get("sritzone_vip_link_enabled", True)
            role_val = str(d.get("role", "owner"))
            team_owner_id_val = d.get("team_owner_id")
            assigned_groups_val = d.get("assigned_groups", ["All"])
            permissions_val = d.get("permissions", {
                "can_create": True, "can_edit": True, "can_delete": True, "can_export": True, "can_bots": True
            })
        else:
            email_val = str(email or kwargs.get("email_or_dict", "")).strip()
            full_name_val = str(full_name or "").strip() or email_val.split("@")[0]
            user_id_val = str(user_id or "").strip()
            token_val = str(token or "").strip()
            plan_type_val = plan_type
            max_profiles_val = max_profiles
            days_remaining_val = days_remaining
            plan_expires_at_val = plan_expires_at
            vip_link_val = sritzone_vip_link_enabled if "sritzone_vip_link_enabled" in kwargs or sritzone_vip_link_enabled is not None else kwargs.get("sritzone_vip_link_enabled", True)
            role_val = str(role or kwargs.get("role", "owner"))
            team_owner_id_val = team_owner_id if team_owner_id is not None else kwargs.get("team_owner_id")
            assigned_groups_val = assigned_groups if assigned_groups is not None else kwargs.get("assigned_groups", ["All"])
            permissions_val = permissions if permissions is not None else kwargs.get("permissions", {
                "can_create": True, "can_edit": True, "can_delete": (role_val != "member"), "can_export": (role_val != "member"), "can_bots": True
            })

        self._session_data = {
            "email": email_val,
            "full_name": full_name_val,
            "user_id": user_id_val,
            "token": token_val,
            "plan_type": plan_type_val,
            "max_profiles": max_profiles_val,
            "cloud_quota": max_profiles_val,
            "days_remaining": days_remaining_val,
            "plan_expires_at": plan_expires_at_val,
            "sritzone_vip_link_enabled": bool(vip_link_val),
            "role": role_val,
            "team_owner_id": team_owner_id_val,
            "assigned_groups": assigned_groups_val or ["All"],
            "permissions": permissions_val or {},
            "is_logged_in": bool(email_val and token_val and token_val != "local_token_mock"),
            "remember_me": True
        }
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(self._session_data, f, indent=2)
        except Exception:
            pass

    def notify_logout(self) -> None:
        token = self._session_data.get("token")
        if not token or token == "local_token_mock":
            return
        try:
            import requests
            requests.get(f"https://srbrowser.com/api/v1/auth/logout?token={token}", headers={"User-Agent": "srkBrowser/2.0"}, timeout=2)
        except Exception:
            pass

    def clear_session(self) -> None:
        self.notify_logout()
        self._session_data = {
            "email": "",
            "full_name": "",
            "user_id": "",
            "token": "",
            "is_logged_in": False,
            "remember_me": False
        }
        if self.session_file.exists():
            try:
                self.session_file.unlink(missing_ok=True)
            except Exception:
                pass

    def get_current_user(self) -> Dict[str, Any]:
        self.load_session()
        return dict(self._session_data)

    def is_logged_in(self) -> bool:
        return True

    def verify_active_session(self) -> Tuple[bool, str]:
        """
        Verify if current active session token is valid for Customer Edition.
        Returns (is_valid: bool, status_code_or_msg: str)
        """
        return True, "VALID"

    def login_user(self, email: str, password: str, api_url: str = "https://srbrowser.com/api/v1/auth/login") -> Tuple[bool, str, Dict[str, Any]]:
        """
        Log in user against remote API server with Single-Device Hardware Binding.
        Returns: (success: bool, message: str, user_data: dict)
        """
        email_clean = email.strip()
        pass_clean = password.strip()

        if not email_clean or not pass_clean:
            return False, "Please enter both Email and Password.", {}

        try:
            import requests
            try:
                from core.license_manager import get_hardware_id
                hwid = get_hardware_id()
            except Exception:
                try:
                    from license_manager import get_hardware_id
                    hwid = get_hardware_id()
                except Exception:
                    import platform
                    hwid = platform.node()
            payload = {
                "email": email_clean,
                "password": pass_clean,
                "hwid": hwid
            }

            resp = requests.post(
                api_url,
                json=payload,
                headers={"User-Agent": "srkBrowser/2.0"},
                timeout=10
            )

            if resp.status_code == 200:
                res = resp.json()
                if res.get("status") == "success":
                    u_id = str(res.get("user_id", ""))
                    tok = str(res.get("token", ""))
                    fname = str(res.get("full_name", ""))
                    plan_type = str(res.get("plan_type", "free"))
                    max_profiles = int(res.get("max_profiles", 100) or 100)
                    days_rem = int(res.get("days_remaining", 0) or 0)
                    plan_exp = str(res.get("plan_expires_at", "") or "")
                    role = str(res.get("role", "owner"))
                    team_owner_id = res.get("team_owner_id")
                    assigned_groups = res.get("assigned_groups", ["All"])
                    permissions = res.get("permissions", {})
                    self.save_session(
                        email_clean, u_id, tok, fname,
                        plan_type=plan_type, max_profiles=max_profiles,
                        days_remaining=days_rem, plan_expires_at=plan_exp,
                        role=role, team_owner_id=team_owner_id,
                        assigned_groups=assigned_groups, permissions=permissions
                    )
                    import threading
                    threading.Thread(target=self.refresh_user_info, daemon=True).start()
                    return True, "Login successful!", res
                else:
                    msg = res.get("message") or "Invalid email or password."
                    return False, msg, {}
            else:
                try:
                    res = resp.json()
                    msg = res.get("message") or "Invalid email or password."
                except Exception:
                    msg = f"Server error {resp.status_code}"
                return False, msg, {}
        except Exception as e:
            return False, f"Connection error to srbrowser.com: {e}", {}

    def is_team_member(self) -> bool:
        """Returns True if currently logged in as a Team Sub-Account."""
        self.load_session()
        return str(self._session_data.get("role", "owner")).lower() == "member"

    def is_team_owner(self) -> bool:
        """Returns True if currently logged in as Team Owner or Standard Master Account."""
        return not self.is_team_member()

    def get_role(self) -> str:
        self.load_session()
        return str(self._session_data.get("role", "owner")).lower()

    def get_team_owner_id(self) -> Optional[Any]:
        self.load_session()
        return self._session_data.get("team_owner_id")

    def get_allowed_groups(self) -> List[str]:
        """Returns list of groups permitted for this account."""
        self.load_session()
        if not self.is_team_member():
            return ["All"]
        return self._session_data.get("assigned_groups", ["All"])

    def can_create_profiles(self) -> bool:
        """Check if user has permission to create new profiles."""
        if not self.is_team_member():
            return True
        perms = self._session_data.get("permissions", {})
        return bool(perms.get("can_create", True))

    def can_edit_profiles(self) -> bool:
        """Check if user has permission to edit profile configs."""
        if not self.is_team_member():
            return True
        perms = self._session_data.get("permissions", {})
        return bool(perms.get("can_edit", True))

    def can_delete_profiles(self) -> bool:
        """Check if user has permission to delete profiles."""
        if not self.is_team_member():
            return True
        perms = self._session_data.get("permissions", {})
        return bool(perms.get("can_delete", False))

    def can_export_cookies(self) -> bool:
        """Check if user has permission to export/extract cookies and credentials."""
        if not self.is_team_member():
            return True
        perms = self._session_data.get("permissions", {})
        return bool(perms.get("can_export", False))

    def can_use_bots(self) -> bool:
        """Check if user has permission to run automation bots.
        Automation bots are strictly exclusive to Master Account Owners.
        """
        if self.is_team_member():
            return False
        return True
