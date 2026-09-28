# -*- coding: utf-8 -*-
"""
Helper utilities and tools for Facebook Reels Comment Marketing Bot:
- Portable Chromium & Profile directory resolution
- Text and comment line-by-line loading
- Profile number filtering
- CommentFormatterDialog: Standalone modal tool for multi-line comment conversion
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Callable, Union

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
        QPushButton, QGroupBox, QRadioButton, QMessageBox,
        QFileDialog, QApplication, QButtonGroup
    )
    from PySide6.QtCore import Qt, QTimer
except ImportError:
    QDialog = object
    QVBoxLayout = QHBoxLayout = QLabel = QTextEdit = None
    QPushButton = QGroupBox = QRadioButton = QMessageBox = None
    QFileDialog = QApplication = QButtonGroup = None
    Qt = QTimer = None


import json
import subprocess
import base64
import urllib.request
import hmac
import hashlib
import struct
import time
import shutil
import random


def get_base_dir() -> Path:
    """Returns the base srkBrowser application directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()

    cur = Path(__file__).resolve().parent
    # If in srkBrowser/03_Automation_Bots/04_FB_...
    for p in [cur] + list(cur.parents)[:5]:
        if (p / "chromium" / "chrome.exe").exists() or (p / "srkBrowser.exe").exists() or (p / "srkBrowser.exe").exists() or (p / "_internal").exists():
            return p
    return cur.parent.parent


def get_profiles_dir() -> Path:
    """Resolves profiles directory in srkBrowser / srkBrowser."""
    base = get_base_dir()
    candidates = [
        base / "data" / "profiles" / "users" / "customer_srbrowser_local",
        base / "data" / "profiles",
        base / "profiles",
        base / "_internal" / "data" / "profiles",
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "profiles",
    ]
    for c in candidates:
        if c.exists():
            return c

    u_base = base / "data" / "profiles" / "users"
    if u_base.exists():
        for sub in u_base.iterdir():
            if sub.is_dir():
                return sub

    p = base / "data" / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_chrome_executable_path() -> Optional[str]:
    """Finds srkBrowser's bundled Portable Chromium executable (ignores system browsers)."""
    # 1. Direct search from current file and base directory
    cur = Path(__file__).resolve().parent
    for p in [cur] + list(cur.parents)[:5]:
        cand = p / "chromium" / "chrome.exe"
        if cand.exists():
            return str(cand.resolve())

    # 2. Check if frozen executable directory
    if getattr(sys, 'frozen', False):
        exe_cand = Path(sys.executable).parent / "chromium" / "chrome.exe"
        if exe_cand.exists():
            return str(exe_cand.resolve())

    # 3. Check base directory
    base = get_base_dir()
    for cand in [
        base / "chromium" / "chrome.exe",
        base.parent / "chromium" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "BrowserProfileManager" / "chromium" / "chrome.exe",
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "chromium" / "chrome.exe",
    ]:
        if cand.exists():
            return str(cand.resolve())

    # 4. Check utils get_system_browsers
    try:
        from core.utils import get_system_browsers
        sb = get_system_browsers()
        for _, path in sb.items():
            if os.path.exists(path):
                return str(Path(path).resolve())
    except Exception:
        pass

    try:
        from utils import get_system_browsers
        sb = get_system_browsers()
        for _, path in sb.items():
            if os.path.exists(path):
                return str(Path(path).resolve())
    except Exception:
        pass

    return None


def resolve_user_data_dir(profile_data: Dict[str, Any], profile_mgr: Optional[Any] = None) -> str:
    """Smart resolution of the exact profile folder for srkBrowser with full login cookies."""
    if profile_data.get("user_data_dir") and Path(profile_data["user_data_dir"]).exists():
        return str(Path(profile_data["user_data_dir"]).resolve())

    pid = profile_data.get("id")

    # 1. Try passed profile_mgr
    if profile_mgr and pid and hasattr(profile_mgr, "get_profile_folder"):
        try:
            p_f = profile_mgr.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass

    # 2. Try initializing ProfileManager from core or profile_manager
    base = get_base_dir()
    for extra_p in [base / "_internal", base / "_internal" / "core", base / "core"]:
        if extra_p.exists() and str(extra_p) not in sys.path:
            sys.path.insert(0, str(extra_p))

    if pid:
        try:
            from profile_manager import ProfileManager
            pm = ProfileManager()
            p_f = pm.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass
        try:
            from core.profile_manager import ProfileManager
            pm = ProfileManager()
            p_f = pm.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass

    # 3. Direct disk scan in data/profiles/users/*/<candidates>
    pnum = str(profile_data.get("number", profile_data.get("name", ""))).strip()
    clean_digits = re.sub(r"\D", "", pnum)
    candidates = [pnum] if pnum else []
    if clean_digits:
        try:
            n_val = int(clean_digits)
            candidates.extend([f"Profile{n_val:03d}", f"Profile{n_val}", str(n_val)])
        except Exception:
            pass

    for u_base in [
        base / "data" / "profiles" / "users",
        base / "profiles" / "users",
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "profiles" / "users",
    ]:
        if u_base.exists():
            for u_folder in u_base.iterdir():
                if u_folder.is_dir():
                    for cand in candidates:
                        cand_dir = u_folder / cand
                        if cand_dir.exists() and cand_dir.is_dir():
                            return str(cand_dir.resolve())

    # 4. Fallback search in standard profiles directories
    for profiles_base in [
        base / "data" / "profiles",
        base / "profiles",
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "profiles"
    ]:
        if not profiles_base.exists():
            continue
        clean_digits = re.sub(r"\D", "", pnum)
        candidates = [pnum]
        if clean_digits:
            n_val = int(clean_digits)
            candidates.extend([f"Profile{n_val:03d}", f"Profile{n_val}", str(n_val)])

        for cand in candidates:
            p_dir = profiles_base / cand
            if p_dir.exists() and p_dir.is_dir():
                return str(p_dir.resolve())

    fallback = base / "data" / "profiles" / (pnum or "Profile001")
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback.resolve())


def parse_cookie_string(cookie_str: str, default_domain: str = ".facebook.com") -> List[Dict[str, Any]]:
    """Convert raw semicolon/pipe/JSON cookie strings into Playwright cookie list."""
    if not cookie_str or not str(cookie_str).strip():
        return []

    cookies = []
    clean_str = str(cookie_str).strip()

    # Format 1: JSON array string [{"name": "c_user", "value": "..."}, ...]
    if clean_str.startswith("[") and clean_str.endswith("]"):
        try:
            json_arr = json.loads(clean_str)
            for c in json_arr:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    ck = {
                        "name": str(c["name"]).strip(),
                        "value": str(c["value"]).strip(),
                        "domain": c.get("domain", default_domain),
                        "path": c.get("path", "/")
                    }
                    cookies.append(ck)
            if cookies:
                return cookies
        except Exception:
            pass

    # Format 2: Semicolon or pipe separated string: "c_user=123; xs=abc; datr=xyz" or "c_user=123|xs=abc"
    pairs = [p.strip() for p in clean_str.split(";") if p.strip()]
    if len(pairs) == 1 and "|" in pairs[0] and "=" not in pairs[0]:
        pairs = pairs[0].split("|")
    elif len(pairs) == 1 and "|" in pairs[0]:
        pairs = [p.strip() for p in pairs[0].split("|") if p.strip()]

    for pair in pairs:
        if "=" in pair:
            parts = pair.split("=", 1)
            name = parts[0].strip()
            val = parts[1].strip()
            if name and val:
                cookies.append({
                    "name": name,
                    "value": val,
                    "domain": default_domain,
                    "path": "/"
                })

    return cookies


def kill_profile_chrome_process(user_data_dir: str) -> None:
    """Forcefully terminates any Chrome / Chromium process locking a given profile folder."""
    if not user_data_dir:
        return
    folder_name = Path(user_data_dir).name
    if not folder_name:
        return

    # Method 1: Instant psutil termination
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = " ".join(p.info.get('cmdline') or [])
                if folder_name in cmd:
                    p.kill()
            except Exception:
                pass
    except Exception:
        pass

    # Method 2: Windows WMIC & PowerShell fallback
    if os.name == 'nt' and len(folder_name) > 1:
        try:
            cmd_wmic = f'wmic process where "name=\'chrome.exe\' and commandline like \'%%{folder_name}%%\'" call terminate'
            subprocess.run(cmd_wmic, shell=True, capture_output=True, timeout=2)
            cmd_ps = f'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name = \'chrome.exe\' and CommandLine like \'%{folder_name}%\'\\" | Invoke-CimMethod -MethodName Terminate"'
            subprocess.run(cmd_ps, shell=True, capture_output=True, timeout=2)
        except Exception:
            pass



def load_lines_from_txt_file(file_path: str) -> List[str]:
    """Loads clean non-empty lines from a text file with multi-encoding support."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
                return lines
        except (UnicodeDecodeError, Exception):
            continue
    return []


def parse_raw_text_lines(raw_text: str) -> List[str]:
    """Splits raw text by newlines into clean non-empty lines."""
    if not raw_text:
        return []
    return [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#")]


def filter_by_profile_numbers(profiles: List[Dict[str, Any]], range_str: str) -> List[Dict[str, Any]]:
    """
    Filters profile objects by numbers/ranges (e.g. '1, 3, 5-10' or 'Profile001').
    """
    if not range_str or not range_str.strip():
        return profiles

    target_numbers = set()
    parts = [p.strip() for p in range_str.replace(";", ",").split(",") if p.strip()]

    for part in parts:
        clean_part = re.sub(r'(?i)profile', '', part).strip()
        if "-" in clean_part:
            try:
                sub_parts = clean_part.split("-")
                start = int(sub_parts[0].strip())
                end = int(sub_parts[1].strip())
                for n in range(min(start, end), max(start, end) + 1):
                    target_numbers.add(n)
            except Exception:
                pass
        else:
            try:
                target_numbers.add(int(clean_part))
            except Exception:
                pass

    if not target_numbers:
        return profiles

    filtered = []
    for p in profiles:
        raw_num = p.get("number")
        if raw_num is not None:
            try:
                if int(raw_num) in target_numbers:
                    filtered.append(p)
                    continue
            except Exception:
                pass
        p_name = str(p.get("name", "")).lower()
        for num in target_numbers:
            if f"profile{num}" in p_name or f"profile {num}" in p_name or p_name == str(num):
                filtered.append(p)
                break

    return filtered


class CommentFormatterDialog(QDialog):
    """
    Standalone & Modular Tool: Comment Line-by-Line Formatter & Converter.
    Converts multi-line comments (paragraphs, WhatsApp URLs, emojis) into single-line strings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️ Comment Line-by-Line Formatter & Converter Tool")
        self.resize(720, 600)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', Arial, sans-serif; }
            QLabel { color: #cdd6f4; font-size: 13px; }
            QTextEdit { background-color: #181825; border: 1px solid #45475a; border-radius: 8px; color: #a6e3a1; font-family: 'Consolas', monospace; font-size: 12px; padding: 8px; }
            QGroupBox { border: 1px solid #45475a; border-radius: 8px; margin-top: 10px; font-weight: bold; color: #89b4fa; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px; padding: 8px 16px; font-size: 13px; }
            QPushButton:hover { background-color: #b4befe; }
            QRadioButton { color: #cdd6f4; font-size: 12px; }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Title / Description
        lbl_title = QLabel("🛠️ Marketing Comment Line-by-Line Formatter")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Paste your multi-line marketing comments (containing paragraphs, WhatsApp links, and emojis) below.<br/>"
            "This tool will instantly convert them into clean <b>1-comment-per-line format</b> for your FB Comment Marketing Bot!"
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # Mode Box
        mode_box = QGroupBox("Separation Mode")
        mode_layout = QHBoxLayout(mode_box)
        self.radio_blank_lines = QRadioButton("Separate by Blank Lines (Double Newlines)")
        self.radio_separator = QRadioButton("Separate by '---' Separator")
        self.radio_blank_lines.setChecked(True)

        mode_group = QButtonGroup(self)
        mode_group.addButton(self.radio_blank_lines)
        mode_group.addButton(self.radio_separator)

        mode_layout.addWidget(self.radio_blank_lines)
        mode_layout.addWidget(self.radio_separator)
        layout.addWidget(mode_box)

        # Input Box
        layout.addWidget(QLabel("<b>1. Paste Raw Multi-Line Comments Here:</b>"))
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText(
            "Example Multi-Line Comment 1:\n"
            "📌 এই ভিডিওটা শুরুতে সিম্পল লাগছিল... কিন্তু ধীরে ধীরে একদম অন্য দিকে চলে গেল! 😲\n"
            "👉 https://wa.me/message/YOUR_LINK\n"
            "🔥 সত্যি অন্য লেভেল!\n\n"
            "Example Multi-Line Comment 2:\n"
            "🚀 দারুণ কনটেন্ট! আরও চমৎকার আপডেট পেতে আমাদের পেজে ফলো দিন!\n"
            "👉 https://t.me/yourchannel\n"
        )
        layout.addWidget(self.txt_input)

        # Convert Button
        btn_convert = QPushButton("⚡ Convert to Line-by-Line Format >>")
        btn_convert.setCursor(Qt.PointingHandCursor)
        btn_convert.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-size: 13.5px; font-weight: 800; padding: 10px 18px;")
        btn_convert.clicked.connect(self._convert_comments)
        layout.addWidget(btn_convert)

        # Output Box
        self.lbl_output_header = QLabel("<b>2. Formatted Line-by-Line Comments (0 Total):</b>")
        layout.addWidget(self.lbl_output_header)
        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(False)
        layout.addWidget(self.txt_output)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy to Clipboard")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_output)
        btn_layout.addWidget(btn_copy)

        btn_export = QPushButton("💾 Save as TXT...")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._export_output)
        btn_layout.addWidget(btn_export)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background-color: #313244; color: #cdd6f4;")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _convert_comments(self):
        raw_text = self.txt_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "No Input", "Please paste your raw marketing comments first!")
            return

        comments = []
        if self.radio_separator.isChecked():
            parts = raw_text.split("---")
            for p in parts:
                cleaned = " ".join([line.strip() for line in p.splitlines() if line.strip()])
                if cleaned:
                    comments.append(cleaned)
        else:
            chunks = re.split(r'\n\s*\n', raw_text)
            for ch in chunks:
                cleaned = " ".join([line.strip() for line in ch.splitlines() if line.strip()])
                if cleaned:
                    comments.append(cleaned)

        formatted_text = "\n".join(comments)
        self.txt_output.setPlainText(formatted_text)
        self.lbl_output_header.setText(f"<b>2. Formatted Line-by-Line Comments ({len(comments)} Total):</b>")
        QMessageBox.information(self, "Success", f"✅ Successfully converted {len(comments)} comment(s) into 1-line-per-comment format!")

    def _copy_output(self):
        text = self.txt_output.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Output", "Convert comments first before copying!")
            return
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "📋 Formatted comments copied to Clipboard!")

    def _export_output(self):
        text = self.txt_output.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Output", "Convert comments first before exporting!")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Formatted Comments TXT File", "reels_comment_marketing.txt", "Text Files (*.txt)")
        if path:
            try:
                Path(path).write_text(text + "\n", encoding="utf-8")
                QMessageBox.information(self, "Exported", f"💾 Successfully saved formatted comments to '{Path(path).name}'!")
            except Exception as ex:
                QMessageBox.critical(self, "Export Error", f"Failed to save file: {ex}")

    def get_formatted_text(self) -> str:
        return self.txt_output.toPlainText().strip()


# =====================================================================
# Google Gemini AI Agent Marketing Comment Generator (Built-in & Encrypted)
# =====================================================================
_SEC_ENCODED_TOKEN = "MiNFHgBKPTlFKT80NAg8e3pjdSBCCRc4Cz4YMUgmMSwgKGZ7Wm8qMwZnVkUMNSNdBiYxAR4="
_SEC_CIPHER_SEED = b"srk_browser_ai_2026"
_ai_opener = None


def get_embedded_ai_key() -> str:
    """Decrypts built-in embedded Google Gemini API key securely in memory."""
    try:
        raw = base64.b64decode(_SEC_ENCODED_TOKEN)
        return bytes([b ^ _SEC_CIPHER_SEED[i % len(_SEC_CIPHER_SEED)] for i, b in enumerate(raw)]).decode("utf-8")
    except Exception:
        return ""


def get_ai_opener():
    """Returns a direct proxy-bypassing opener to prevent Windows proxy discovery latency."""
    global _ai_opener
    if _ai_opener is None:
        _ai_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return _ai_opener


VIRAL_ENGLISH_HOOKS = [
    "Watch Full Video Here 🎬🔥👇",
    "Full Video Link Available Here 👇🔞👀",
    "Watch Full Viral Video Now 👇💥🍿",
    "Full Video Below Guys 👇🎬⚡",
    "Click Below To Watch Complete Video 👇🔥👇",
    "Watch Full Uncut Video Here 👇😱🍿",
    "Full Video Available Here 👇✨👀",
    "Full Video Stream Link 👇🎬🔥",
    "Don't Miss The Full Video Here 👇👀💥",
    "Watch Full Clip Now 👇🎥🔥",
    "Full Video Link 👇🔞🔥",
    "Watch Full Video On Channel 👇🍿🎬",
    "Complete Viral Video Link Below 👇🔥👀",
    "Watch Uncensored Full Clip Here 👇😱🎬",
    "Full Viral Clip Below Guys 👇💥⚡",
    "Click Here To Watch Full Video 👇🎥🔥",
    "Full Video Updated On Link Below 👇🔞🍿",
    "Watch The Complete Story Here 👇🎬✨",
    "Viral Full Video Available Now 👇🔥👀",
    "Watch Full HD Video Below 👇🍿💥",
    "Full Clip Link Updated Here 👇🔞🎬",
    "Don't Miss Out! Watch Full Video Here 👇⚡🔥",
    "Full Video Access Link Below 👇🎬👀",
    "Watch The Real Full Clip Here 👇😱🔥",
    "Instant Full Video Link Below 👇🍿⚡",
    "Check Out The Full Viral Clip Here 👇🎬🔥",
    "Click To Watch Entire Video Now 👇👀💥",
    "Original Full Video Link Below 👇🎥🔞",
    "Watch The Trending Full Clip Here 👇🔥🍿",
    "Full Video Link Dropped Below 👇⚡🎬",
    "Stream Full Viral Video Here 👇🔞🍿",
    "Tap Below For Full Video 👇🎬🔥"
]


def generate_ai_comment(
    caption: str = "",
    matched_keyword: str = "",
    user_offer_text: str = "",
    custom_instruction: str = "",
    fallback_comment: str = ""
) -> str:
    """
    Generates a unique, viral English marketing comment specifically designed for 'Full Video' / 'Watch Full Video' with exciting emojis.
    CRITICAL: Guarantees that user_offer_text (the user's 2-3 links) is 100% included at the bottom,
    with an engaging English Full Video hook strictly on top of EVERY comment without exception.
    """
    user_offer = (user_offer_text or "").strip()
    if not user_offer:
        user_offer = "https://whatsapp.com/channel/..."

    random_hook = random.choice(VIRAL_ENGLISH_HOOKS)
    dynamic_fallback = f"{random_hook}\n{user_offer}".strip()

    key = get_embedded_ai_key()
    if not key:
        return dynamic_fallback

    clean_caption = (caption or "").strip()
    if len(clean_caption) > 150:
        clean_caption = clean_caption[:150]

    prompt = (
        f"You are a viral Facebook Reel marketing assistant.\n"
        f"Reel video caption/context: {clean_caption}\n"
        f"Target keyword matched: {matched_keyword}\n"
        f"CRITICAL REQUIREMENTS:\n"
        f"1. Write ONE short, catchy, exciting viral English hook telling viewers to click the link below to watch the full video (e.g. 'Watch Full Video Here 🎬🔥👇', 'Full Viral Video Link Below 👇🔞👀', 'Watch Complete Uncut Video Now 👇💥🍿', 'Full Video Available Below Guys 👇🎬⚡').\n"
        f"2. MUST BE IN ENGLISH with exciting emojis (🎬, 🔥, 👇, 👀, 🔞, 💥, 🍿, ⚡).\n"
        f"3. STRICTLY DO NOT WRITE ANY BENGALI TEXT. ONLY ENGLISH.\n"
        f"4. DO NOT write any URLs or links in your output. Only write the catchy 1-line hook with emojis pointing down (👇).\n"
        f"Output ONLY the single line hook text. No quotes, no explanations, no URLs."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 45
        }
    }

    try:
        opener = get_ai_opener()
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        with opener.open(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    hook = parts[0]["text"].strip()
                    hook = hook.strip('"\'“”`\n\r ')
                    # If model generated Bengali text or too short, use random hook
                    has_bengali = any(0x0980 <= ord(ch) <= 0x09FF for ch in hook)
                    if has_bengali or len(hook) < 5:
                        return f"{random.choice(VIRAL_ENGLISH_HOOKS)}\n{user_offer}".strip()
                    # Strip any accidental URLs from hook
                    hook = re.sub(r'https?://\S+', '', hook).strip()
                    if not any(emo in hook for emo in ["👇", "🎬", "🔥", "👀", "🍿", "⚡"]):
                        hook = f"{hook} 🎬🔥👇"
                    return f"{hook}\n{user_offer}".strip()
    except Exception:
        pass

    return dynamic_fallback


# =====================================================================
# Account State & Auto-Login / Auto-Deletion Utilities
# =====================================================================
def generate_totp_2fa_code(secret_key: str) -> str:
    """Pure Python RFC-6238 TOTP Generator without external dependencies."""
    cleaned = str(secret_key).strip().replace(" ", "").replace("-", "").upper()
    if not cleaned:
        return ""
    missing_padding = len(cleaned) % 8
    if missing_padding:
        cleaned += "=" * (8 - missing_padding)
    try:
        key = base64.b32decode(cleaned)
        counter = int(time.time() // 30)
        counter_bytes = struct.pack(">Q", counter)
        mac = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        offset = mac[-1] & 0x0F
        code_int = struct.unpack(">I", mac[offset:offset+4])[0] & 0x7FFFFFFF
        return f"{code_int % 1000000:06d}"
    except Exception:
        return ""


def human_type(locator: Any, text: str, min_delay_ms: int = 40, max_delay_ms: int = 100, clear_first: bool = False) -> None:
    """Simulates natural human typing cadence."""
    try:
        locator.click(timeout=2500)
        time.sleep(random.uniform(0.1, 0.25))
        if clear_first:
            locator.fill("")
            time.sleep(0.1)
        for ch in str(text):
            locator.type(ch, delay=random.randint(min_delay_ms, max_delay_ms))
    except Exception:
        try:
            locator.fill(str(text))
        except Exception:
            pass


def is_facebook_account_suspended(page: Any) -> Tuple[bool, str]:
    """Detects if Facebook account is suspended, disabled, checkpointed, or locked."""
    try:
        if page.is_closed():
            return False, ""
        curr_url = (page.url or "").lower()
        if any(k in curr_url for k in ["/checkpoint/", "/identity/", "/disabled/", "/suspended/"]):
            return True, f"Suspended URL detected: {curr_url}"

        res = page.evaluate("""() => {
            const body = (document.body.innerText || document.body.textContent || '').toLowerCase();
            const suspendedPhrases = [
                "we suspended your account",
                "your account has been suspended",
                "your account has been disabled",
                "account disabled",
                "help us confirm that this is your account",
                "confirm your identity",
                "your account is locked",
                "account locked",
                "you can't use facebook right now",
                "আমরা আপনার অ্যাকাউন্ট স্থগিত করেছি",
                "আপনার অ্যাকাউন্ট নিষ্ক্রিয় করা হয়েছে",
                "আপনার অ্যাকাউন্ট লক করা হয়েছে"
            ];
            for (const p of suspendedPhrases) {
                if (body.includes(p)) {
                    return { isSuspended: true, reason: p };
                }
            }
            return { isSuspended: false, reason: "" };
        }""")
        if res and res.get("isSuspended"):
            return True, res.get("reason", "Suspended Account")
        return False, ""
    except Exception as e:
        return False, str(e)


def detect_facebook_tab_state(page: Any) -> Tuple[str, str]:
    """
    Detects current Facebook tab state:
    ON_CHECKPOINT, 2FA_REQUIRED, CONTINUE_SCREEN, LOGIN_FORM_READY, LOGGED_IN, UNKNOWN
    """
    try:
        if page.is_closed():
            return "UNKNOWN", "Page closed"
        url = (page.url or "").lower()

        # 1. Suspended / Checkpoint Check
        is_susp, susp_reason = is_facebook_account_suspended(page)
        if is_susp:
            return "ON_CHECKPOINT", susp_reason

        # 2. 2FA Check
        two_fa_selectors = [
            "input[name='approvals_code']",
            "input#approvals_code",
            "input[name='code']",
            "div:has-text('Two-factor authentication')",
            "div:has-text('Enter login code')"
        ]
        for sel in two_fa_selectors:
            if page.locator(sel).first.is_visible(timeout=250):
                return "2FA_REQUIRED", "Two-Factor Authentication Prompt"

        # 3. Continue / Account Chooser Screen Check
        continue_btn = page.locator("div[role='button']:has-text('Continue'), button:has-text('Continue'), div[role='button']:has-text('Log In As'), div[role='button']:has-text('Continue as'), a:has-text('Continue')").first
        if continue_btn.is_visible(timeout=350):
            return "CONTINUE_SCREEN", "Continue Profile Screen Detected"

        pass_input = page.locator("input#pass, input[name='pass'], input[type='password']").first
        if pass_input.is_visible(timeout=300) and continue_btn.is_visible(timeout=200):
            return "CONTINUE_SCREEN", "Continue Password Screen"

        # 4. Standard Login Form
        email_inp = page.locator("input#email, input[name='email']").first
        if email_inp.is_visible(timeout=300):
            return "LOGIN_FORM_READY", "Standard Login Form Ready"

        if "login" in url or "recover" in url:
            return "LOGIN_FORM_READY", "Facebook Login URL"

        # 5. Logged In Check
        feed_selectors = [
            "div[role='feed']",
            "div[aria-label*='Stories']",
            "div[aria-label*='Create a post']",
            "div[data-pagelet='LeftRail']",
            "input[placeholder*='Search Facebook']",
            "input[placeholder*='ফেসবুক সার্চ']",
            "a[href*='/friends/']",
            "svg[aria-label='Your profile']"
        ]
        for sel in feed_selectors:
            if page.locator(sel).first.is_visible(timeout=300):
                return "LOGGED_IN", "Active Home Feed Verified"

        # Context cookies check
        try:
            for ck in page.context.cookies():
                if ck.get("name") in ("c_user", "cuser") and str(ck.get("value", "")).isdigit():
                    if "login" not in url and "checkpoint" not in url:
                        return "LOGGED_IN", f"Authenticated (c_user={ck.get('value')})"
        except Exception:
            pass

        return "UNKNOWN", "Page loading or unrecognized screen"
    except Exception as err:
        return "ERROR", str(err)


def handle_facebook_continue_and_login(
    page: Any,
    password: str,
    twofa_secret: str = "",
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """Handles Continue screen: enters password and submits."""
    def log(m: str):
        if log_func:
            log_func(m)

    continue_selectors = [
        "div[role='button']:has-text('Continue')",
        "button:has-text('Continue')",
        "div[role='button']:has-text('চালিয়ে যান')",
        "button:has-text('চালিয়ে যান')",
        "div[aria-label*='Continue']",
        "div[role='button']:has-text('Log In As')",
        "div[role='button']:has-text('Continue as')"
    ]

    continue_btn = None
    for sel in continue_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=500):
                continue_btn = loc
                break
        except Exception:
            pass

    direct_pass = None
    for p_sel in ["input[type='password']", "input#pass", "input[name='pass']"]:
        try:
            p_loc = page.locator(p_sel).first
            if p_loc.is_visible(timeout=400):
                direct_pass = p_loc
                break
        except Exception:
            pass

    if not direct_pass and continue_btn:
        try:
            continue_btn.click(timeout=1500)
            time.sleep(1.0)
            for p_sel in ["input[type='password']", "input#pass", "input[name='pass']"]:
                p_loc = page.locator(p_sel).first
                if p_loc.is_visible(timeout=800):
                    direct_pass = p_loc
                    break
        except Exception:
            pass

    if direct_pass and password:
        log("    🔑 Entering saved password into Continue dialog...")
        human_type(direct_pass, password, clear_first=True)
        time.sleep(0.3)
        page.keyboard.press("Enter")
        time.sleep(3.0)

        # Check 2FA
        st, _ = detect_facebook_tab_state(page)
        if st == "2FA_REQUIRED" and twofa_secret:
            totp = generate_totp_2fa_code(twofa_secret)
            if totp:
                code_inp = page.locator("input[name='approvals_code'], input#approvals_code, input[name='code'], input[type='text']").first
                if code_inp.is_visible(timeout=1500):
                    human_type(code_inp, totp, clear_first=True)
                    time.sleep(0.3)
                    page.keyboard.press("Enter")
                    time.sleep(2.5)

        st, _ = detect_facebook_tab_state(page)
        if st == "LOGGED_IN":
            return True, "Login successful"

    return False, "Failed to complete Continue login"


def is_facebook_password_error(page: Any) -> Tuple[bool, str]:
    """Detects if Facebook page shows an incorrect password error or invalid credentials."""
    try:
        if page.is_closed():
            return False, ""
        res = page.evaluate("""() => {
            const body = (document.body.innerText || document.body.textContent || '').toLowerCase();
            const errPhrases = [
                "the password that you've entered is incorrect",
                "the password you’ve entered is incorrect",
                "the password you've entered is incorrect",
                "incorrect password",
                "wrong password",
                "wrong credentials",
                "invalid username or password",
                "পাসওয়ার্ডটি সঠিক নয়",
                "পাসওয়ার্ড সঠিক নয়",
                "ভুল পাসওয়ার্ড",
                "ভুল পাসওয়ার্ড"
            ];
            for (const p of errPhrases) {
                if (body.includes(p)) {
                    return { isErr: true, msg: p };
                }
            }
            const errBox = document.querySelector('div[role="alert"], div#error_box, div._9ay7');
            if (errBox) {
                const txt = (errBox.innerText || errBox.textContent || '').trim();
                if (txt.length > 5) return { isErr: true, msg: txt };
            }
            return { isErr: false, msg: "" };
        }""")
        if isinstance(res, dict) and res.get("isErr"):
            return True, res.get("msg", "Incorrect password")
        return False, ""
    except Exception as e:
        return False, str(e)


def try_facebook_cookie_login(
    context: Any,
    page: Any,
    cookie_str: str,
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Attempts to log in to Facebook by injecting saved session cookies.
    """
    def log(m: str):
        if log_func:
            log_func(m)

    parsed_cookies = parse_cookie_string(cookie_str)
    if not parsed_cookies:
        log("    ⚠️ No saved cookies found for session restore.")
        return False, "NO_SAVED_COOKIES"

    log(f"    🍪 Attempting session restore using {len(parsed_cookies)} saved cookies...")
    try:
        # Clear existing context cookies to avoid stale session conflict
        if context:
            try:
                context.clear_cookies()
            except Exception:
                pass
            context.add_cookies(parsed_cookies)
            time.sleep(0.3)

        # Navigate to Facebook home
        page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
        time.sleep(2.0)

        # Check account state
        is_susp, susp_reason = is_facebook_account_suspended(page)
        if is_susp:
            log(f"    🚫 Account suspended or checkpoint on cookie restore: {susp_reason}")
            return False, "SUSPENDED"

        st, st_desc = detect_facebook_tab_state(page)
        if st == "LOGGED_IN":
            log(f"    ✅ Session restored successfully via Cookies! ({st_desc})")
            return True, "COOKIE_LOGIN_SUCCESS"
        else:
            log(f"    ❌ Cookie session restore failed: {st_desc} (State: {st})")
            return False, "COOKIE_EXPIRED"
    except Exception as e:
        log(f"    ❌ Cookie injection error: {e}")
        return False, str(e)


def auto_relogin_facebook(
    page: Any,
    context: Optional[Any] = None,
    profile_data: Optional[Dict[str, Any]] = None,
    profile_mgr: Optional[Any] = None,
    user_data_dir: str = "",
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Auto re-login handler for Facebook with Intelligent Cookie Fallback:
    1. Checks if already logged in or suspended.
    2. Handles Continue Screen / standard Password login (+ 2FA TOTP).
    3. If password login fails or shows 'incorrect password':
       -> Automatically attempts fallback login with saved Cookies!
    4. If both Password and Cookies fail:
       -> Returns (False, "WRONG_PASSWORD_AND_COOKIE_FAILED") for auto-deletion.
    """
    def log(m: str):
        if log_func:
            log_func(m)

    pdata = profile_data or {}
    pname = pdata.get("name", "Profile")

    email = str(pdata.get("fb_uid") or pdata.get("email") or pdata.get("uid") or pdata.get("username") or "").strip()
    if not email and "fb_" in str(pname).lower():
        m = re.search(r"\d{10,20}", str(pname))
        if m:
            email = m.group(0)
    password = str(pdata.get("fb_pass") or pdata.get("password") or pdata.get("pass") or "").strip()
    two_factor = str(pdata.get("fb_2fa") or pdata.get("2fa_secret") or pdata.get("two_factor") or pdata.get("2fa") or "").strip()
    cookies_raw = pdata.get("cookies") or pdata.get("fb_cookie") or pdata.get("cookie") or ""

    # Parse notes if UID/pass/2FA/cookies in notes
    notes = str(pdata.get("notes") or "").strip()
    if notes:
        m_uid = re.search(r'(?:uid|fb\s*uid|id|user):\s*([0-9a-zA-Z\._\-]+)', notes, re.IGNORECASE)
        m_pwd = re.search(r'(?:pass|password|pwd):\s*([^\s\|]+)', notes, re.IGNORECASE)
        m_2fa = re.search(r'(?:2fa|totp|secret):\s*([0-9a-zA-Z\s]+)', notes, re.IGNORECASE)
        m_ck = re.search(r'(?:cookie|cookies|fb_cookie):\s*(.+)', notes, re.IGNORECASE)
        if m_uid and not email: email = m_uid.group(1).strip()
        if m_pwd and not password: password = m_pwd.group(1).strip()
        if m_2fa and not two_factor: two_factor = m_2fa.group(1).strip()
        if m_ck and not cookies_raw: cookies_raw = m_ck.group(1).strip()
        if "|" in notes and (not email or not password or not cookies_raw):
            parts = [p.strip() for p in notes.split("|")]
            if len(parts) >= 2:
                if not email: email = parts[0]
                if not password: password = parts[1]
                if len(parts) >= 3 and not two_factor: two_factor = parts[2]
                if len(parts) >= 4 and not cookies_raw: cookies_raw = parts[3]

    # Check for external cookies file if not in profile_data
    if not cookies_raw and user_data_dir:
        for ck_fname in ["facebook_cookies.json", "cookies.json"]:
            ck_p = Path(user_data_dir) / ck_fname
            if ck_p.exists():
                try:
                    cookies_raw = ck_p.read_text(encoding="utf-8").strip()
                    break
                except Exception:
                    pass

    st, st_desc = detect_facebook_tab_state(page)
    if st == "LOGGED_IN":
        return True, "Already logged in"
    if st == "ON_CHECKPOINT":
        return False, "SUSPENDED"

    # Step A: Continue Screen handling
    if st == "CONTINUE_SCREEN":
        log(f"    🎯 Continue screen detected for [{pname}]! Submitting password...")
        ok, msg = handle_facebook_continue_and_login(page, password, two_factor, log_func=log)
        if ok:
            return True, "Continue login successful"

    # Step B: Standard login attempt with Email + Password
    if email and password:
        log(f"    🔑 Entering credentials for [{pname}] ({email[:12]}...)...")
        try:
            page.goto("https://www.facebook.com/login", timeout=25000, wait_until="domcontentloaded")
            time.sleep(1.5)
            e_inp = page.locator("input#email, input[name='email']").first
            p_inp = page.locator("input#pass, input[name='pass']").first
            if e_inp.is_visible(timeout=1500) and p_inp.is_visible(timeout=1500):
                human_type(e_inp, email, clear_first=True)
                time.sleep(0.2)
                human_type(p_inp, password, clear_first=True)
                time.sleep(0.3)
                page.keyboard.press("Enter")
                time.sleep(3.0)

                # Check 2FA
                st, _ = detect_facebook_tab_state(page)
                if st == "2FA_REQUIRED" and two_factor:
                    totp = generate_totp_2fa_code(two_factor)
                    if totp:
                        code_inp = page.locator("input[name='approvals_code'], input#approvals_code, input[name='code'], input[type='text']").first
                        if code_inp.is_visible(timeout=2000):
                            human_type(code_inp, totp, clear_first=True)
                            time.sleep(0.3)
                            page.keyboard.press("Enter")
                            time.sleep(3.0)

                st, _ = detect_facebook_tab_state(page)
                if st == "LOGGED_IN":
                    return True, "Login successful"
                if st == "ON_CHECKPOINT":
                    return False, "SUSPENDED"
        except Exception as e:
            log(f"    ⚠️ Password login attempt warning: {e}")

    # Check if login resulted in success
    st, _ = detect_facebook_tab_state(page)
    if st == "LOGGED_IN":
        return True, "Login successful"

    # Check for password error message
    is_pw_err, pw_err_msg = is_facebook_password_error(page)
    if is_pw_err:
        log(f"    ⚠️ Password incorrect for [{pname}] ({pw_err_msg})!")

    # Step C: Fallback to Cookies (User Requirement: পাসওয়ার্ড ভুল হলে কুকি দিয়ে চেষ্টা করবে)
    log(f"    🔄 Password login failed or incorrect. Trying fallback login with Cookies for [{pname}]...")
    ck_ok, ck_res = try_facebook_cookie_login(context, page, cookies_raw, log_func=log)
    if ck_ok:
        return True, "COOKIE_LOGIN_SUCCESS"

    if ck_res == "SUSPENDED":
        return False, "SUSPENDED"

    # Step D: Neither Password nor Cookies worked (User Requirement: যদি কুকি দিয়ে লগইন না হয় তাহলে ডিলিট করে দিবে)
    log(f"    ❌ Neither password nor cookies could log in for [{pname}]! (Cookie result: {ck_res})")
    return False, "WRONG_PASSWORD_AND_COOKIE_FAILED"


def delete_profile_safely(
    profile_id: str,
    user_folder: str,
    profile_mgr: Optional[Any] = None,
    log_func: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Safely kills Chrome processes, removes profile from profile_mgr database,
    and purges profile directory from disk.
    """
    try:
        if log_func:
            log_func(f"    🗑️ Terminating processes and deleting profile data for ID {profile_id}...")

        # 1. Kill chrome process for this profile
        kill_profile_chrome_process(user_folder)
        time.sleep(0.5)

        # 2. Delete from profile manager if available
        if profile_mgr and hasattr(profile_mgr, "delete_profile") and callable(profile_mgr.delete_profile):
            try:
                profile_mgr.delete_profile(profile_id)
            except Exception as d_ex:
                if log_func:
                    log_func(f"    ⚠️ Warning deleting from profile DB: {d_ex}")

        # 3. Delete directory from disk
        if user_folder and os.path.exists(user_folder):
            shutil.rmtree(user_folder, ignore_errors=True)
            if log_func:
                log_func(f"    ✅ Profile folder completely purged from disk: {Path(user_folder).name}")

        return True
    except Exception as ex:
        if log_func:
            log_func(f"    ❌ Failed to delete profile {profile_id}: {ex}")
        return False


# ==============================================================================
# ANTI-DETECT BROWSER FINGERPRINT ROTATION SYSTEM
# ==============================================================================

CHROME_REAL_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

VIEWPORT_CONFIGS = [
    {"width": 1366, "height": 768, "device_memory": 8, "hardware_concurrency": 8},
    {"width": 1440, "height": 900, "device_memory": 16, "hardware_concurrency": 12},
    {"width": 1536, "height": 864, "device_memory": 8, "hardware_concurrency": 8},
    {"width": 1600, "height": 900, "device_memory": 16, "hardware_concurrency": 16},
    {"width": 1920, "height": 1080, "device_memory": 16, "hardware_concurrency": 12},
    {"width": 1280, "height": 800, "device_memory": 8, "hardware_concurrency": 6},
]


def generate_profile_fingerprint(pdata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a consistent, unique anti-detect fingerprint profile per profile ID/number.
    Ensures Facebook sees different User-Agents, screen dimensions, CPU cores, and memory across profiles.
    """
    seed_str = str(pdata.get("id") or pdata.get("number") or pdata.get("name") or "default")
    seed_num = sum(ord(c) for c in seed_str)

    ua = CHROME_REAL_USER_AGENTS[seed_num % len(CHROME_REAL_USER_AGENTS)]
    vp = VIEWPORT_CONFIGS[seed_num % len(VIEWPORT_CONFIGS)]

    return {
        "user_agent": ua,
        "width": vp["width"],
        "height": vp["height"],
        "device_memory": vp["device_memory"],
        "hardware_concurrency": vp["hardware_concurrency"]
    }


def get_stealth_anti_detect_script(fp: Dict[str, Any]) -> str:
    """
    Returns stealth JavaScript code injected into every new page to mask automation
    (navigator.webdriver) and spoof unique hardware per profile.
    """
    hw = fp.get("hardware_concurrency", 8)
    mem = fp.get("device_memory", 8)
    return f"""
    (() => {{
        try {{
            // 1. Mask navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined,
                configurable: true
            }});
            delete Object.getPrototypeOf(navigator).webdriver;
        }} catch(e) {{}}

        try {{
            // 2. Spoof Hardware Concurrency & Device Memory
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {hw},
                configurable: true
            }});
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => {mem},
                configurable: true
            }});
        }} catch(e) {{}}

        try {{
            // 3. Spoof Plugins list to mimic genuine Chrome
            Object.defineProperty(navigator, 'plugins', {{
                get: () => [1, 2, 3, 4, 5],
                configurable: true
            }});
        }} catch(e) {{}}

        try {{
            // 4. Spoof window.chrome
            if (!window.chrome) {{
                window.chrome = {{ runtime: {{}} }};
            }}
        }} catch(e) {{}}
    }})();
    """

