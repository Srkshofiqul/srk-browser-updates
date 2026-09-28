"""
Browser Profile Manager - Bookmark Manager Module
Manages custom bookmarks list, bookmarklet scripts, group targeting, and auto-syncing to Chrome profiles.
"""

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import BOOKMARKS_DB_FILE
from utils import safe_read_json, safe_write_json, get_current_timestamp

DEFAULT_GET_TOKEN_COOKIE_SCRIPT = (
    "javascript:(function(){"
    "var c=document.cookie;"
    "var uid=(c.match(/c_user=(\\d+)/)||[])[1]||'';"
    "var xs=(c.match(/xs=([^;]+)/)||[])[1]||'';"
    "var text='UID: '+uid+'\\n\\nFull Cookie:\\n'+c;"
    "if(confirm(text+'\\n\\nPress OK to copy UID & Cookies to Clipboard!')){"
    "  navigator.clipboard.writeText('UID: '+uid+' | Cookie: '+c);"
    "  alert('✅ Successfully Copied UID & Cookies to Clipboard!');"
    "}"
    "})();"
)

# Start clean by default so no unwanted bookmarks appear until configured by user
DEFAULT_BOOKMARKS: List[Dict[str, Any]] = []


def normalize_bookmark_url(url: str) -> str:
    """Ensure URL has a valid scheme (http, https, javascript, chrome, file). Auto-prepend https:// if missing."""
    u = str(url).strip()
    if not u:
        return "https://google.com"
    u_lower = u.lower()
    if u_lower.startswith(("http://", "https://", "javascript:", "chrome://", "file:///", "edge://", "about:")):
        return u
    return "https://" + u


class BookmarkManager:
    """
    Manages custom bookmarks database, target group assignment, and Chrome Bookmarks bar sync.
    """

    def __init__(self, db_file: Path = BOOKMARKS_DB_FILE) -> None:
        self.db_file = db_file
        self._load_bookmarks()

    def _load_bookmarks(self) -> None:
        """Load bookmarks list from bookmarks.json database."""
        data = safe_read_json(self.db_file)
        if isinstance(data, list):
            self.bookmarks = data
        else:
            self.bookmarks = []
            self._save_bookmarks()

    def _save_bookmarks(self) -> bool:
        """Save bookmarks list to bookmarks.json database."""
        return safe_write_json(self.db_file, self.bookmarks)

    def get_all_bookmarks(self) -> List[Dict[str, Any]]:
        """Return list of all registered bookmarks."""
        return list(self.bookmarks)

    def add_bookmark(
        self,
        name: str,
        url: str,
        target_mode: str = "all",
        target_groups: List[str] = None
    ) -> Dict[str, Any]:
        """Add a new bookmark entry with target group scope."""
        bm_id = f"bm_{uuid.uuid4().hex[:8]}"
        record = {
            "id": bm_id,
            "name": name.strip() or "New Bookmark",
            "url": normalize_bookmark_url(url),
            "is_active": True,
            "target_mode": target_mode,  # "all", "new_only", "groups"
            "target_groups": target_groups or [],
            "date_added": get_current_timestamp()
        }
        self.bookmarks.append(record)
        self._save_bookmarks()
        return record

    def update_bookmark(self, bm_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing bookmark fields."""
        if "url" in updates:
            updates["url"] = normalize_bookmark_url(updates["url"])
        for bm in self.bookmarks:
            if bm.get("id") == bm_id:
                bm.update(updates)
                self._save_bookmarks()
                return True
        return False

    def delete_bookmark(self, bm_id: str) -> bool:
        """Delete bookmark by ID."""
        for i, bm in enumerate(self.bookmarks):
            if bm.get("id") == bm_id:
                self.bookmarks.pop(i)
                self._save_bookmarks()
                return True
        return False

    def sync_bookmarks_to_profile(
        self,
        profile_dir: Path,
        profile_data: Optional[Dict[str, Any]] = None,
        custom_bookmarks: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """
        Write active matching bookmarks into <profile_dir>/Default/Bookmarks
        and enable show_bookmark_bar in Chrome Preferences.
        """
        try:
            default_dir = profile_dir / "Default"
            default_dir.mkdir(parents=True, exist_ok=True)

            prof_group = ""
            if profile_data and isinstance(profile_data, dict):
                prof_group = str(profile_data.get("group", "Default")).strip().lower()

            matching_bms = []
            if custom_bookmarks is not None:
                # Explicit list of bookmarks chosen during Bulk / Single creation
                matching_bms = list(custom_bookmarks)
            elif profile_data and profile_data.get("bookmarks"):
                matching_bms = list(profile_data.get("bookmarks"))
            else:
                for b in self.bookmarks:
                    if not b.get("is_active", True):
                        continue

                    target_mode = b.get("target_mode", "all")
                    if target_mode in ("manual_only", "library_only", "none"):
                        # Skip auto-sync: Saved to Library Only
                        continue
                    elif target_mode in ("all", "new_only"):
                        matching_bms.append(b)
                    elif target_mode == "groups" and prof_group:
                        t_grps = [str(g).strip().lower() for g in b.get("target_groups", [])]
                        if prof_group in t_grps:
                            matching_bms.append(b)

            bm_file = default_dir / "Bookmarks"
            existing_children = []
            existing_urls = set()
            existing_other = []
            existing_synced = []

            # Set of known system library bookmark URLs to avoid re-adding unchecked bookmarks
            system_known_urls = set()
            for b_item in getattr(self, "bookmarks", []):
                u_str = normalize_bookmark_url(b_item.get("url", "")).lower().rstrip("/")
                if u_str:
                    system_known_urls.add(u_str)

            # 1. Read and preserve any bookmarks created manually by user inside Chromium
            if bm_file.exists():
                try:
                    with open(bm_file, "r", encoding="utf-8") as f:
                        old_bm = json.load(f)
                    roots = old_bm.get("roots", {})
                    old_bar = roots.get("bookmark_bar", {}).get("children", [])
                    if isinstance(old_bar, list):
                        for c in old_bar:
                            if isinstance(c, dict):
                                c_url = str(c.get("url", "")).strip()
                                c_norm = c_url.lower().rstrip("/")
                                # Skip old template landing pages
                                if not c_url or "127.0.0.1:5000/landing" in c_url:
                                    continue
                                # If bookmarks are explicitly customized, do NOT retain unchecked system bookmarks
                                if custom_bookmarks is not None and c_norm in system_known_urls:
                                    continue
                                existing_children.append(c)
                                existing_urls.add(c_norm)
                    old_other = roots.get("other", {}).get("children", [])
                    if isinstance(old_other, list):
                        existing_other = old_other
                    old_synced = roots.get("synced", {}).get("children", [])
                    if isinstance(old_synced, list):
                        existing_synced = old_synced
                except Exception:
                    pass

            children = []

            # 👑 First Bookmark: Clean Icon + Profile Number
            num_clean = str(profile_data.get("number", "1")).replace("Profile", "").replace("#", "").strip() if profile_data else "1"
            landing_url = f"http://127.0.0.1:5000/landing?id={profile_data.get('id', '')}&no={num_clean}"
            children.append({
                "date_added": "13300000000000000",
                "guid": "00000000-0000-0000-0000-000000000001",
                "id": "100",
                "name": f"👑 {num_clean}",
                "type": "url",
                "url": landing_url
            })
            existing_urls.add(landing_url.lower().rstrip("/"))

            # Append existing user-created bookmarks (e.g. personal sites added inside Chrome)
            for c in existing_children:
                children.append(c)

            # Append configured matching bookmarks
            cur_idx = 200 + len(children)
            for b in matching_bms:
                bm_name = "Bookmark"
                bm_url = ""
                if isinstance(b, dict):
                    bm_name = b.get("name") or b.get("title") or "Bookmark"
                    bm_url = normalize_bookmark_url(b.get("url", ""))
                elif isinstance(b, str):
                    found = next((x for x in self.bookmarks if x.get("id") == b or x.get("url") == b or x.get("name") == b), None)
                    if found:
                        bm_name = found.get("name", "Bookmark")
                        bm_url = normalize_bookmark_url(found.get("url", ""))
                    else:
                        bm_name = "Bookmark"
                        bm_url = normalize_bookmark_url(b)

                norm_b_url = bm_url.lower().rstrip("/")
                if bm_url and norm_b_url not in existing_urls:
                    children.append({
                        "date_added": "13300000000000000",
                        "guid": str(uuid.uuid4()),
                        "id": str(cur_idx),
                        "name": bm_name,
                        "type": "url",
                        "url": bm_url
                    })
                    existing_urls.add(norm_b_url)
                    cur_idx += 1

            bookmarks_json_data = {
                "checksum": "00000000000000000000000000000000",
                "roots": {
                    "bookmark_bar": {
                        "children": children,
                        "date_added": "13300000000000000",
                        "date_modified": "13300000000000000",
                        "guid": "00000000-0000-0000-0000-000000000002",
                        "id": "1",
                        "name": "Bookmarks bar",
                        "type": "folder"
                    },
                    "other": {
                        "children": existing_other,
                        "date_added": "13300000000000000",
                        "date_modified": "0",
                        "guid": "00000000-0000-0000-0000-000000000003",
                        "id": "2",
                        "name": "Other bookmarks",
                        "type": "folder"
                    },
                    "synced": {
                        "children": existing_synced,
                        "date_added": "13300000000000000",
                        "date_modified": "0",
                        "guid": "00000000-0000-0000-0000-000000000004",
                        "id": "3",
                        "name": "Mobile bookmarks",
                        "type": "folder"
                    }
                },
                "version": 1
            }

            # Write Bookmarks file
            with open(bm_file, "w", encoding="utf-8") as f:
                json.dump(bookmarks_json_data, f, indent=2)

            # Ensure Bookmark Bar is set to ALWAYS VISIBLE in Chrome Preferences (never touch Secure Preferences directly)
            pref_path = default_dir / "Preferences"
            try:
                pref_path.parent.mkdir(parents=True, exist_ok=True)
                p_data = {}
                if pref_path.exists():
                    try:
                        with open(pref_path, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                    except Exception:
                        p_data = {}

                if not isinstance(p_data, dict):
                    p_data = {}

                if "bookmark_bar" not in p_data or not isinstance(p_data["bookmark_bar"], dict):
                    p_data["bookmark_bar"] = {}

                p_data["bookmark_bar"]["show_on_all_tabs"] = True

                if "browser" not in p_data or not isinstance(p_data["browser"], dict):
                    p_data["browser"] = {}

                p_data["browser"]["show_bookmark_bar"] = True

                with open(pref_path, "w", encoding="utf-8") as f:
                    json.dump(p_data, f, indent=2)
            except Exception:
                pass

            return len(matching_bms)
        except Exception:
            return 0
