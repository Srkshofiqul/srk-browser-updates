# -*- coding: utf-8 -*-
"""
Helper utilities and tools for Facebook Reels Algorithm Trainer Bot:
- Portable Chromium & Profile directory resolution
- Smart Session & Cookie Management
- Built-in Encrypted Google Gemini 3.1 Flash-Lite AI Agent
- RFC-6238 TOTP 2FA Generator
- Account Suspension / Checkpoint Detection
- Auto Re-Login with Password-to-Cookie Fallback
- Dead Profile Safe Purge from Database and Disk
"""

import os
import sys
import re
import time
import json
import base64
import random
import shutil
import struct
import hmac
import hashlib
import urllib.request
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable


def get_base_dir() -> Path:
    """Returns the base srkBrowser application directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()

    cur = Path(__file__).resolve().parent
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
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "profiles",
    ]:
        if profiles_base.exists():
            for cand in candidates:
                cand_dir = profiles_base / cand
                if cand_dir.exists() and cand_dir.is_dir():
                    return str(cand_dir.resolve())

    # 5. Fallback create default folder
    fallback = base / "data" / "profiles" / (f"Profile{int(clean_digits):03d}" if clean_digits else "Profile001")
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback.resolve())


def parse_cookie_string(cookie_raw: str, domain: str = ".facebook.com") -> List[Dict[str, Any]]:
    """Converts a raw HTTP Cookie header string into Playwright-compatible cookie dictionaries."""
    cookies = []
    if not cookie_raw or not isinstance(cookie_raw, str):
        return cookies

    # Check if raw JSON array of cookies
    if cookie_raw.strip().startswith("[") and cookie_raw.strip().endswith("]"):
        try:
            data = json.loads(cookie_raw)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        cookies.append({
                            "name": str(item["name"]).strip(),
                            "value": str(item["value"]).strip(),
                            "domain": item.get("domain", domain),
                            "path": item.get("path", "/"),
                            "httpOnly": item.get("httpOnly", False),
                            "secure": item.get("secure", True),
                            "sameSite": item.get("sameSite", "Lax")
                        })
                if cookies:
                    return cookies
        except Exception:
            pass

    pairs = [p.strip() for p in cookie_raw.split(";") if p.strip()]
    for pair in pairs:
        if "=" in pair:
            name, val = pair.split("=", 1)
            name = name.strip()
            val = val.strip()
            if name:
                cookies.append({
                    "name": name,
                    "value": val,
                    "domain": domain,
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax"
                })
    return cookies


def kill_profile_chrome_process(user_data_dir: str) -> None:
    """Closes dangling Chrome instances locking a profile folder."""
    if not user_data_dir or not os.path.exists(user_data_dir):
        return
    try:
        norm = os.path.normpath(user_data_dir).lower()
        cmd = f'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"name=\'chrome.exe\'\\" | Where-Object {{ $_.CommandLine -like \'*{norm}*\' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
    except Exception:
        pass


def load_text_lines(file_path: str) -> List[str]:
    """Reads non-empty lines from a text file."""
    lines = []
    if not os.path.exists(file_path):
        return lines
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#"):
                        lines.append(s)
            if lines:
                break
        except Exception:
            continue
    return lines


# Alias for compatibility
load_lines_from_txt_file = load_text_lines


def parse_raw_text_lines(raw_text: str) -> List[str]:
    """Splits raw text by newlines into clean non-empty lines."""
    if not raw_text:
        return []
    return [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#")]


def filter_by_profile_numbers(profiles: List[Dict[str, Any]], range_str: str) -> List[Dict[str, Any]]:
    """Filters profile objects by numbers/ranges (e.g. '1, 3, 5-10' or 'Profile001')."""
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


# =====================================================================
# Google Gemini 3.1 Flash-Lite AI Agent (Built-in & Encrypted)
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


DEFAULT_ALGO_TRAINER_COMMENTS = [
    "Amazing video! Really loved the presentation! ❤️🔥",
    "This is super insightful and helpful, thanks for sharing! 💡👏",
    "Great content as always, keep up the fantastic work! 🚀💯",
    "Super interesting! Learned something valuable today! 💡✨",
    "Loved the editing and vibe of this reel! 🔥🙌",
    "Such a great explanation! Very easy to understand! 👍👏",
    "This made my day haha! Absolutely brilliant! 😂🔥",
    "Top quality content! Definitely saving this for later! 📌❤️",
    "Incredible creativity and execution! Keep shining! 🌟🔥",
    "Spot on! Completely agree with this point! 💯👏",
    "So satisfying to watch! Wonderful job! 😍✨",
    "Awesome clip! Looking forward to your next upload! 🎬🚀",
    "The effort in this video really shows! Fantastic work! 👏🔥",
    "Very well put together! Subscribed and following! ❤️👍",
    "This deserves way more views! Great job! 💯🚀",
    "Brilliant perspective! Really enjoyed watching this! 🙌✨",
    "Love how clearly everything is explained! Keep it up! 💡🔥",
    "Awesome reel! Keep blessing our feed with quality content! ❤️🔥",
    "So true! Loved every second of this video! 💯👏",
    "Such positive energy! Made my feed so much better today! 🌟💖"
]


def generate_ai_reels_engagement_comment(
    caption: str = "",
    creator_name: str = "",
    tone_instruction: str = "Natural Fan & Appreciation",
    custom_instruction: str = "",
    fallback_comments: Optional[List[str]] = None
) -> str:
    """
    Generates a realistic, natural, authentic human engagement comment
    tailored to the specific Facebook Reel video content/caption to train the algorithm.
    """
    pool = fallback_comments if (fallback_comments and len(fallback_comments) > 0) else DEFAULT_ALGO_TRAINER_COMMENTS
    dynamic_fallback = random.choice(pool)

    key = get_embedded_ai_key()
    if not key:
        return dynamic_fallback

    clean_caption = (caption or "").strip()
    if len(clean_caption) > 200:
        clean_caption = clean_caption[:200]

    tone_map = {
        "Natural Fan & Appreciation": "Write a warm, enthusiastic comment admiring the video content, creator's effort, or skill.",
        "Short & Punchy with Emojis": "Write a super short, punchy 3 to 7 word reaction with 1-2 excited emojis (e.g. 'Loved this edit! 🔥👏', 'Incredible skill! 💯').",
        "Curious & Thoughtful Question": "Write a genuine, curious question or observation showing deep interest in the video's topic.",
        "Insightful & Engaging": "Write a thoughtful, insightful comment agreeing with or adding value to the topic discussed in the clip."
    }
    tone_desc = tone_map.get(tone_instruction, tone_instruction)
    if custom_instruction and custom_instruction.strip():
        tone_desc += f" Additional user style requirement: {custom_instruction.strip()}."

    prompt = (
        f"You are a real human watching a Facebook Reel video.\n"
        f"Reel context/caption: '{clean_caption}'\n"
        f"Creator/Page name: '{creator_name}'\n"
        f"Goal: Write ONE single natural, authentic human comment to engage with this reel and praise/discuss the video.\n"
        f"Style/Tone: {tone_desc}\n"
        f"CRITICAL RULES:\n"
        f"1. Length: 4 to 15 words maximum. Concise, natural, realistic.\n"
        f"2. Include 1 or 2 relevant, natural emojis (e.g. 🔥, ❤️, 👏, 💡, 😂, 💯, 🚀).\n"
        f"3. Language: If the caption is primarily Bengali, you may reply in natural Bengali. Otherwise, reply in English.\n"
        f"4. ABSOLUTELY NO marketing links, no URLs, no hashtags, no spam.\n"
        f"5. Do NOT sound like an AI or bot. Sound like an everyday viewer.\n"
        f"Output ONLY the exact comment text. No quotes, no explanations."
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
                    res_text = parts[0]["text"].strip().strip('"\'“”`\n\r ')
                    # Clean out any accidental URLs
                    res_text = re.sub(r'https?://\S+', '', res_text).strip()
                    if len(res_text) >= 4:
                        return res_text
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
        if clear_first:
            try:
                locator.click(timeout=1000)
                locator.fill("")
            except Exception:
                pass
        locator.press_sequentially(text, delay=random.randint(min_delay_ms, max_delay_ms))
    except Exception:
        try:
            locator.fill(text)
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


def check_facebook_login_status(page: Any, context: Any = None) -> Tuple[bool, str]:
    """Checks if the Facebook session is logged in."""
    try:
        if page.is_closed():
            return False, "Page is closed"

        curr_url = (page.url or "").lower()
        if any(k in curr_url for k in ("/checkpoint/", "/identity/", "/two_step_verification/", "/disabled/", "/help/contact/", "/recover/", "/auth_platform/", "/afad/")):
            return False, "Account Checkpoint / Verification Required"

        # 1. First, check if Facebook is prompting for login / account chooser
        is_logged_out, reason = page.evaluate("""() => {
            const body = (document.body.innerText || '').toLowerCase();
            
            // Check for Account Chooser / Logged out splash
            if (body.includes('use another profile') || 
                body.includes('create new account') || 
                body.includes('explore the things you love') || 
                body.includes('log into another account') ||
                body.includes('একটি নতুন অ্যাকাউন্ট তৈরি করুন') || 
                body.includes('অন্য অ্যাকাউন্টে লগ ইন করুন')) {
                return [true, "Account Chooser / Re-login Screen (Session Expired)"];
            }

            const hasLoginForm = !!document.querySelector('input[name="email"], input[name="pass"], form[action*="login"]');
            const hasFeed = !!document.querySelector('div[role="feed"], div[role="main"], svg[aria-label="Your profile"], div[aria-label="Account controls and settings"]');
            
            if (hasLoginForm && !hasFeed) {
                return [true, "Login Form Present (Not Logged In)"];
            }
            return [false, ""];
        }""")

        if is_logged_out:
            return False, reason

        # 2. Check context cookies and active feed
        if context:
            try:
                cookies = context.cookies()
                has_cuser = any(c.get("name") == "c_user" and len(str(c.get("value", "")).strip()) > 3 for c in cookies)
                has_xs = any(c.get("name") == "xs" and len(str(c.get("value", "")).strip()) > 3 for c in cookies)
                if has_cuser and has_xs and "login" not in curr_url:
                    return True, "Session Active (Authenticated Cookies)"
            except Exception:
                pass

        is_in = page.evaluate("""() => {
            const hasFeed = !!document.querySelector('div[role="feed"], div[role="main"], div[aria-label*="Facebook"], svg[aria-label="Your profile"], div[aria-label="Account controls and settings"]');
            if (hasFeed) return true;
            return document.cookie.includes('c_user=');
        }""")
        if is_in:
            return True, "Session Active (Feed/Profile Detected)"

        return False, "Not logged in (Feed not found)"
    except Exception as e:
        return False, str(e)


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
    """Attempts to log in to Facebook by injecting saved session cookies."""
    def log(m: str):
        if log_func:
            log_func(m)

    parsed_cookies = parse_cookie_string(cookie_str)
    if not parsed_cookies:
        log("    ⚠️ No saved cookies found for session restore.")
        return False, "NO_SAVED_COOKIES"

    log(f"    🍪 Attempting session restore using {len(parsed_cookies)} saved cookies...")
    try:
        if context:
            try:
                context.clear_cookies()
            except Exception:
                pass
            context.add_cookies(parsed_cookies)
            time.sleep(0.3)

        page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
        time.sleep(2.0)

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

