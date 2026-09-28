import os
import re
import time
import random
import urllib.request
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

def parse_profile_numbers_input(text: str) -> List[int]:
    """
    Parses user-entered profile number strings supporting:
    - Single numbers: '5' -> [5]
    - Comma-separated lists: '1, 3, 7' -> [1, 3, 7]
    - Number ranges: '1-5, 8, 10-12' -> [1, 2, 3, 4, 5, 8, 10, 11, 12]
    - Formats with '#': '#01, #02, #05-#08' -> [1, 2, 5, 6, 7, 8]
    """
    if not text or not str(text).strip():
        return []

    cleaned = str(text).replace("#", "").replace("Profile", "").replace("profile", "")
    result = set()

    # Split by comma or semicolon or whitespace
    parts = re.split(r"[,;\s]+", cleaned)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            # Range e.g. 1-5 or 01-05
            sub_parts = part.split("-", 1)
            if len(sub_parts) == 2:
                s_raw, e_raw = re.sub(r"\D", "", sub_parts[0]), re.sub(r"\D", "", sub_parts[1])
                if s_raw.isdigit() and e_raw.isdigit():
                    s_val, e_val = int(s_raw), int(e_raw)
                    if s_val <= e_val:
                        for n in range(s_val, e_val + 1):
                            result.add(n)
                    else:
                        for n in range(e_val, s_val + 1):
                            result.add(n)
        else:
            num_clean = re.sub(r"\D", "", part)
            if num_clean.isdigit():
                result.add(int(num_clean))

    return sorted(list(result))

def filter_profiles_by_target(
    all_profiles: List[Dict[str, Any]],
    target_mode: str = "group",
    target_group: str = "All Groups",
    number_input: str = ""
) -> List[Dict[str, Any]]:
    """
    Filters profiles based on user selection:
    - target_mode='group': Filters by group name ('All Groups' includes all).
    - target_mode='numbers': Filters by matching integer profile numbers.
    """
    if not all_profiles:
        return []

    if target_mode == "numbers":
        target_nums = set(parse_profile_numbers_input(number_input))
        if not target_nums:
            return []

        matched = []
        for p in all_profiles:
            raw_num = str(p.get("number", p.get("name", "")))
            num_clean = re.sub(r"\D", "", raw_num)
            if num_clean.isdigit() and int(num_clean) in target_nums:
                matched.append(p)
        return matched

    # Otherwise filter by Group
    if target_group in ("All Groups", "All", "", None):
        return all_profiles

def parse_accounts_file_or_text(file_path: Optional[str] = None, text_content: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parses Facebook accounts from Excel (.xlsx), CSV (.csv), or raw text input.
    Supports formats:
    - UID|Password|2FA_Secret|Cookies
    - UID|Password|2FA_Secret
    - UID|Password
    - UID:Password:2FA_Secret:Cookies
    - Excel columns with or without headers
    """
    accounts = []
    
    # 1. If file_path is provided
    if file_path and os.path.exists(file_path):
        f_ext = Path(file_path).suffix.lower()
        if f_ext == ".xlsx":
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True):
                    if not row or not any(row):
                        continue
                    row_strs = [str(c).strip() if c is not None else "" for c in row]
                    # Check if header row
                    first_cell = row_strs[0].lower()
                    if first_cell in ("uid", "email", "user", "username", "id", "account", "phone"):
                        continue
                    
                    uid = row_strs[0] if len(row_strs) > 0 else ""
                    pwd = row_strs[1] if len(row_strs) > 1 else ""
                    two_fa = row_strs[2] if len(row_strs) > 2 else ""
                    cookie = row_strs[3] if len(row_strs) > 3 else ""
                    
                    is_cookie = any(k in two_fa for k in ["c_user", "datr", "sb=", "xs=", "fr=", ";", "="]) or two_fa.startswith("[")
                    if is_cookie and not cookie:
                        cookie = two_fa
                        two_fa = ""
                    
                    if uid and pwd:
                        accounts.append({
                            "uid": uid,
                            "password": pwd,
                            "two_factor": two_fa,
                            "cookie": cookie,
                            "notes": f"FB UID: {uid}"
                        })
            except Exception as ex:
                print(f"[XLSX READ ERROR]: {ex}")
        elif f_ext == ".csv":
            try:
                import csv
                with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                    sample = f.read(2048)
                    f.seek(0)
                    delimiter = ","
                    for d in ["\t", ";", "|", ","]:
                        if d in sample:
                            delimiter = d
                            break
                    reader = csv.reader(f, delimiter=delimiter)
                    for row in reader:
                        if not row or not any(row):
                            continue
                        row_strs = [str(c).strip() for c in row]
                        first_cell = row_strs[0].lower()
                        if first_cell in ("uid", "email", "user", "username", "id", "account", "phone"):
                            continue
                        
                        uid = row_strs[0] if len(row_strs) > 0 else ""
                        pwd = row_strs[1] if len(row_strs) > 1 else ""
                        two_fa = row_strs[2] if len(row_strs) > 2 else ""
                        cookie = row_strs[3] if len(row_strs) > 3 else ""
                        
                        is_cookie = any(k in two_fa for k in ["c_user", "datr", "sb=", "xs=", "fr=", ";", "="]) or two_fa.startswith("[")
                        if is_cookie and not cookie:
                            cookie = two_fa
                            two_fa = ""

                        if uid and pwd:
                            accounts.append({
                                "uid": uid,
                                "password": pwd,
                                "two_factor": two_fa,
                                "cookie": cookie,
                                "notes": f"FB UID: {uid}"
                            })
            except Exception as ex:
                print(f"[CSV READ ERROR]: {ex}")
        else: # Text file .txt
            try:
                with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                    text_content = f.read()
            except Exception as ex:
                print(f"[TXT READ ERROR]: {ex}")

    # 2. If text_content is provided (or loaded from .txt)
    if text_content and isinstance(text_content, str):
        lines = text_content.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            
            delimiter = None
            if "|" in line:
                delimiter = "|"
            elif "\t" in line:
                delimiter = "\t"
            elif "----" in line:
                delimiter = "----"
            elif ":" in line:
                delimiter = ":"
            elif ";" in line:
                delimiter = ";"

            if delimiter:
                parts = [p.strip() for p in line.split(delimiter)]
            else:
                parts = line.split()

            if len(parts) >= 2:
                uid = parts[0]
                pwd = parts[1]
                two_fa = parts[2] if len(parts) > 2 else ""
                cookie = parts[3] if len(parts) > 3 else ""

                is_cookie = any(k in two_fa for k in ["c_user", "datr", "sb=", "xs=", "fr=", ";", "="]) or two_fa.startswith("[")
                if is_cookie and not cookie:
                    cookie = two_fa
                    two_fa = ""

                if uid.lower() in ("uid", "email", "user", "username", "id", "account"):
                    continue

                if uid and pwd:
                    accounts.append({
                        "uid": uid,
                        "password": pwd,
                        "two_factor": two_fa,
                        "cookie": cookie,
                        "notes": f"FB UID: {uid}"
                    })

    return accounts

def parse_cookie_string(cookie_str: str, default_domain: str = ".facebook.com") -> List[Dict[str, Any]]:
    """Convert raw semicolon/pipe/JSON cookie strings into Playwright cookie list."""
    if not cookie_str or not str(cookie_str).strip():
        return []

    cookies = []
    clean_str = cookie_str.strip()

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

    pairs = [p.strip() for p in clean_str.split(";") if p.strip()]
    if len(pairs) == 1 and "|" in pairs[0] and "=" not in pairs[0]:
        pairs = pairs[0].split("|")

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

def check_facebook_login_status(page: Any, context: Any = None) -> Tuple[bool, str]:
    """
    Strictly verifies if the browser has reached the authenticated Facebook Home Feed.
    Rejects Captcha challenges, checkpoints, 2FA pages, login forms, and Continue landing pages.
    """
    try:
        url = page.url.lower()
        body = ""
        try:
            body = page.locator("body").inner_text(timeout=1500).lower()
        except Exception:
            pass

        # 1. Negative Checks
        clean_url = url.split("?")[0].rstrip("/")
        if "/checkpoint/" in clean_url or "checkpoint/start" in url or "account_disabled" in url:
            return False, "ON_CHECKPOINT"
        if "arkose" in body or "matchkey" in body or "security check" in body or "challenge" in url:
            return False, "ON_CAPTCHA_CHALLENGE"
        if "two_step_verification" in clean_url or "two_factor" in clean_url or "login_approvals" in url or "approvals_code" in body or "6-digit code" in body:
            return False, "ON_2FA_PAGE"
        if "wrong password" in body or "incorrect password" in body:
            return False, "WRONG_PASSWORD"

        # Check if Continue landing screen is active
        try:
            if page.locator("button:has-text('Continue'), div[role='button']:has-text('Continue'), button:has-text('Use another profile')").first.is_visible(timeout=500):
                return False, "CONTINUE_SCREEN_VISIBLE"
        except Exception:
            pass

        # Check if password box is currently visible
        try:
            pass_inputs = page.locator("input[name='pass'], input[type='password']").all()
            for p_elem in pass_inputs:
                if p_elem.is_visible(timeout=500):
                    return False, "PASSWORD_INPUT_VISIBLE"
        except Exception:
            pass

        # Check if Login button is active
        try:
            if page.locator("button[name='login'], #loginbutton").first.is_visible(timeout=500):
                return False, "LOGIN_BUTTON_VISIBLE"
        except Exception:
            pass

        # 2. Positive Checks: Real Logged-in Home Feed UI signals ONLY
        home_feed_signals = ["what's on your mind", "create story", "create a post"]
        has_post_composer = any(sig in body for sig in home_feed_signals)

        home_selectors = [
            "input[placeholder*='Search Facebook']",
            "input[aria-label*='Search Facebook']",
            "div[aria-label*='Account controls and settings']",
            "div[aria-label*='Your profile']",
            "div[aria-label*='Menu'][role='button']"
        ]
        has_home_nav = False
        for sel in home_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=600):
                    has_home_nav = True
                    break
            except Exception:
                pass

        if has_post_composer or has_home_nav:
            return True, "LOGGED_IN"

    except Exception:
        pass
    return False, "NOT_LOGGED_IN"

def detect_facebook_captcha_challenge(page: Any) -> Tuple[bool, str]:
    """Detects Arkose MatchKey or Security Checkpoint challenges."""
    try:
        url = page.url.lower()
        if "checkpoint" in url or "challenge" in url or "two_factor" in url:
            return True, f"Security Checkpoint Challenge ({url})"
        body_text = page.locator("body").inner_text(timeout=1000).lower()
        if "arkose" in body_text or "matchkey" in body_text:
            return True, "Arkose Labs MatchKey Captcha Challenge Required"
        if "security check" in body_text or "confirm your identity" in body_text:
            return True, "Facebook Security Identity Check Required"
    except Exception:
        pass
    return False, "OK"

def handle_facebook_profile_continue_screen(
    page: Any,
    email: str = '',
    password: str = '',
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Handles Facebook Account Chooser / Continue Landing screen.
    If the continue button works and password prompt opens -> fills password.
    If continue button fails or user wants to switch account -> clicks 'Utiliser un autre profil' / 'Use another profile' or opens /login.php to get the full email/password form.
    """
    def log(m: str):
        if log_func: log_func(m)

    try:
        url = page.url.lower()
        body = ""
        try:
            body = page.locator("body").inner_text(timeout=1000).lower()
        except Exception:
            pass

        if "two_step_verification" in url or "two_factor" in url or "enter the 6-digit code" in body:
            return False, "IS_2FA_PAGE"

        # First attempt: Click 'Continuer' / 'Continue'
        continue_selectors = [
            "button:has-text('Continuer')",
            "button:has-text('Continue')",
            "button:has-text('Continuar')",
            "button:has-text('Weiter')",
            "div[role='button']:has-text('Continuer')",
            "div[role='button']:has-text('Continue')"
        ]
        found_btn = None
        for sel in continue_selectors:
            try:
                elem = page.locator(sel).first
                if elem.is_visible(timeout=1000):
                    found_btn = elem
                    break
            except Exception:
                pass

        if found_btn:
            log("  👉 Detected Profile Chooser. Clicking 'Continuer' button...")
            found_btn.click(force=True)
            time.sleep(random.uniform(2.0, 3.5))

            # Check if password prompt appeared
            try:
                pass_inp = page.locator("input[name='pass'], #pass, input[type='password'], input[placeholder*='Mot de passe'], input[placeholder*='Password']").first
                if pass_inp.is_visible(timeout=2000) and password:
                    log("  🔑 Entering Password on Continue screen...")
                    pass_inp.click()
                    time.sleep(0.3)
                    pass_inp.fill("")
                    pass_inp.press_sequentially(password, delay=random.randint(60, 90))
                    time.sleep(0.5)

                    sub_btn = page.locator("button[name='login'], #loginbutton, button[type='submit'], button:has-text('Continuer'), button:has-text('Se connecter')").first
                    if sub_btn.is_visible(timeout=1500):
                        sub_btn.click()
                    else:
                        pass_inp.press("Enter")

                    time.sleep(random.uniform(4.0, 6.0))
                    return True, "PASSWORD_SUBMITTED"
            except Exception:
                pass

        # If password box did not appear: Click 'Utiliser un autre profil' / 'Use another profile' to switch to clean login form
        switch_selectors = [
            "button:has-text('Utiliser un autre profil')",
            "button:has-text('Use another profile')",
            "button:has-text('Usar otro perfil')",
            "button:has-text('Anderes Profil verwenden')",
            "a:has-text('Utiliser un autre profil')",
            "a:has-text('Use another profile')",
            "a:has-text('Log Into Another Account')",
            "a:has-text('Se connecter à un autre compte')",
            "div[role='button']:has-text('Utiliser un autre profil')",
            "div[role='button']:has-text('Use another profile')"
        ]
        for s_sel in switch_selectors:
            try:
                s_elem = page.locator(s_sel).first
                if s_elem.is_visible(timeout=1000):
                    log("  🔄 Clicking 'Utiliser un autre profil' (Switching to standard login form)...")
                    s_elem.click(force=True)
                    time.sleep(random.uniform(2.0, 3.5))
                    return True, "SWITCHED_TO_LOGIN_FORM"
            except Exception:
                pass

        # Fallback: Navigate directly to clean Facebook login page
        log("  🌐 Navigating to clean Facebook login page (facebook.com/login.php)...")
        page.goto("https://www.facebook.com/login.php", timeout=25000, wait_until="domcontentloaded")
        time.sleep(2.0)
        return True, "NAVIGATED_TO_LOGIN"

    except Exception as err:
        log(f"  ⚠️ Note on Continue screen: {err}")
    return False, "NOT_FOUND"

def get_2fa_totp_code(secret_key: str) -> Optional[str]:
    """Generates 6-digit TOTP code via 2fa.live API or local fallback."""
    if not secret_key or not str(secret_key).strip():
        return None
    clean_secret = re.sub(r"\s+", "", str(secret_key).strip())
    
    # 1. API fetch via 2fa.live
    try:
        req = urllib.request.Request(f"https://2fa.live/tok/{clean_secret}", headers={"User-Agent": "srkBrowser-2FA"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("token") and str(data["token"]).isdigit():
                return str(data["token"])
    except Exception:
        pass

    # 2. Local fallback using standard python HMAC
    try:
        import hmac, hashlib, struct, base64
        key = base64.b32decode(clean_secret.upper() + '=' * (-len(clean_secret) % 8))
        counter = struct.pack(">Q", int(time.time()) // 30)
        h = hmac.new(key, counter, hashlib.sha1).digest()
        offset = h[19] & 0xF
        code = ((struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000)
        return f"{code:06d}"
    except Exception:
        pass

    return None

def handle_facebook_2fa_verification(page: Any, secret_2fa: str, context: Any = None, log_func: Optional[Any] = None) -> bool:
    """Handles 2FA OTP submission."""
    def log(m: str):
        if log_func: log_func(m)

    if not secret_2fa:
        return False

    try:
        url = page.url.lower()
        body = ""
        try:
            body = page.locator("body").inner_text(timeout=1000).lower()
        except Exception:
            pass

        if "two_step_verification" in url or "two_factor" in url or "enter the 6-digit code" in body:
            log("  🔐 2FA Screen Detected. Generating 6-Digit TOTP Code...")
            totp = get_2fa_totp_code(secret_2fa)
            if not totp:
                log("  ❌ Failed to generate 2FA TOTP code.")
                return False

            code_inp = page.locator("input[name='approvals_code'], input[type='text'], input[placeholder*='code']").first
            if code_inp.is_visible(timeout=3000):
                code_inp.click()
                code_inp.fill(totp)
                time.sleep(0.5)

                sub_btn = page.locator("button:has-text('Continue'), button:has-text('Submit'), #checkpointSubmitButton").first
                if sub_btn.is_visible(timeout=2000):
                    sub_btn.click()
                else:
                    code_inp.press("Enter")
                log(f"  👉 Submitted 2FA Code: [{totp}]. Waiting for feed...")
                time.sleep(5)
                return True
    except Exception as err:
        log(f"  ⚠️ 2FA verification note: {err}")
    return False

def dismiss_facebook_popup_notices(page: Any, log_func: Optional[Any] = None) -> None:
    """Dismisses cookie acceptance, remember password, and notification popups."""
    dismiss_selectors = [
        "button[data-cookiebanner='accept_button']",
        "button:has-text('Allow essential and optional cookies')",
        "button:has-text('Allow all cookies')",
        "button:has-text('Decline optional cookies')",
        "button:has-text('Not Now')",
        "button:has-text('Save Info')",
        "button:has-text('Save info')",
        "div[role='button']:has-text('Not Now')"
    ]
    for sel in dismiss_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=600):
                btn.click()
                time.sleep(0.4)
        except Exception:
            pass

def create_single_bot_profile(
    profile_mgr: Any = None,
    group_name: str = "Default",
    bot_title: str = "Master Bot",
    custom_notes: str = "",
    language: str = "en-US"
) -> Optional[Dict[str, Any]]:
    """
    On-The-Fly Profile Creator:
    Dynamically creates 1 fresh, clean browser profile inside srkBrowser
    with an auto-increment number, unique user-agent, and assigned group.
    Language strictly defaults to 'en-US' (English US).
    Returns the created profile dictionary (or None).
    """
    pm = profile_mgr
    if pm is None or not hasattr(pm, "create_profile"):
        try:
            from profile_manager import ProfileManager
            pm = ProfileManager()
        except Exception:
            try:
                from core.profile_manager import ProfileManager
                pm = ProfileManager()
            except Exception:
                pm = None

    if not pm or not hasattr(pm, "create_profile"):
        return None

    try:
        next_num = pm.get_next_profile_number() if hasattr(pm, "get_next_profile_number") else f"Profile{len(pm.get_all_profiles()) + 1:03d}"
        notes = custom_notes or f"Auto-created by {bot_title}"
        pdata = pm.create_profile(
            name=next_num,
            number=next_num,
            group=group_name or "Default",
            notes=notes,
            language=language or "en-US"
        )
        return pdata
    except Exception as e:
        print(f"[CREATE SINGLE PROFILE ERROR]: {e}")
        return None

def bulk_create_bot_profiles(
    profile_mgr: Any = None,
    count: int = 5,
    group_name: str = "Default",
    bot_title: str = "Master Bot",
    language: str = "en-US"
) -> List[Dict[str, Any]]:
    """
    Dynamically creates X new browser profiles inside srkBrowser ProfileManager
    with sequential auto-increment profile numbers, unique user-agents, and assigned group.
    Language strictly defaults to 'en-US' (English US).
    Returns the list of newly created profile dictionaries.
    """
    if count <= 0:
        return []

    new_profs = []
    for _ in range(count):
        p = create_single_bot_profile(profile_mgr, group_name, bot_title, language=language)
        if p:
            new_profs.append(p)
    return new_profs

# ==============================================================================
# 🛡️ UNIVERSAL ANTI-DETECT HUMAN-LIKE AUTOMATION UTILITIES
# ==============================================================================

def smart_sleep(min_sec: float = 1.5, max_sec: float = 3.5) -> None:
    """Natural randomized human-like delay between actions."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

def human_type(
    locator_or_page: Any,
    text: str,
    selector: Optional[str] = None,
    min_delay_ms: int = 35,
    max_delay_ms: int = 110,
    clear_first: bool = True
) -> None:
    """
    Human-like typing simulation:
    Types character-by-character with randomized keystroke intervals and micro-pauses
    to completely evade anti-bot typing cadence detectors.
    """
    if not text:
        return

    target = locator_or_page
    if selector:
        target = locator_or_page.locator(selector).first

    if clear_first:
        try:
            target.click()
            target.fill("")
            time.sleep(0.15)
        except Exception:
            pass

    for char in str(text):
        target.type(char, delay=random.randint(min_delay_ms, max_delay_ms))
        if random.random() < 0.08:
            time.sleep(random.uniform(0.15, 0.35))

def human_click(
    locator_or_page: Any,
    selector: Optional[str] = None,
    delay_before: float = 0.2,
    delay_after: float = 0.3
) -> bool:
    """Human-like smooth click with hover and natural reaction delays."""
    try:
        target = locator_or_page
        if selector:
            target = locator_or_page.locator(selector).first
        target.scroll_into_view_if_needed(timeout=3000)
        time.sleep(delay_before)
        target.hover()
        time.sleep(random.uniform(0.08, 0.2))
        target.click()
        time.sleep(delay_after)
        return True
    except Exception:
        try:
            target.click(force=True)
            return True
        except Exception:
            return False

def human_scroll(
    page: Any,
    scroll_steps: int = 3,
    distance_px: int = 320,
    direction: str = "down",
    delay_between: float = 0.7
) -> None:
    """Simulates realistic human mouse-wheel scrolling with natural momentum."""
    sign = 1 if direction.lower() == "down" else -1
    for _ in range(scroll_steps):
        step_dist = random.randint(int(distance_px * 0.7), int(distance_px * 1.3)) * sign
        page.mouse.wheel(0, step_dist)
        time.sleep(random.uniform(delay_between * 0.6, delay_between * 1.4))

def generate_totp_2fa_code(secret_key: str) -> str:
    """
    Pure Python RFC-6238 TOTP Two-Factor Authentication Generator.
    Calculates live 6-digit 2FA OTP codes instantaneously without external dependencies.
    """
    import hmac, hashlib, struct, base64
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
    except Exception as err:
        print(f"[TOTP GENERATION ERROR]: {err}")
        return ""

def capture_diagnostic_screenshot(
    page: Any,
    profile_name: str = "profile",
    label: str = "error",
    reports_dir: Optional[Path] = None,
    uid: str = "",
    password: str = ""
) -> str:
    """
    Captures a high-resolution, full-page diagnostic screenshot of the current page state.
    Saved under reports/screenshots/UID_{uid}_{pname}_{label}_{timestamp}.png
    Also overlays a clear diagnostic header banner at the top with UID, Profile, Status, and Password info.
    """
    try:
        import datetime
        if not reports_dir:
            reports_dir = Path(__file__).parent / "reports"
        ss_dir = reports_dir / "screenshots"
        ss_dir.mkdir(parents=True, exist_ok=True)

        clean_pname = re.sub(r"[^\w\-]", "_", str(profile_name)).strip("_") or "profile"
        clean_label = re.sub(r"[^\w\-]", "_", str(label)).strip("_") or "error"
        t_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Resolve clean UID
        clean_uid = re.sub(r"[^\w\-]", "", str(uid)).strip()
        if not clean_uid and "fb_" in clean_pname.lower():
            match = re.search(r"\d{10,20}", clean_pname)
            if match:
                clean_uid = match.group(0)

        # Build filename with UID at the beginning as requested
        if clean_uid:
            file_name = f"UID_{clean_uid}_{clean_pname}_{clean_label}_{t_stamp}.png"
        else:
            file_name = f"{clean_pname}_{clean_label}_{t_stamp}.png"

        ss_file = ss_dir / file_name

        # 1. Standard Viewport Screenshot (Fast, lightweight, minimal disk usage)
        try:
            page.screenshot(path=str(ss_file), full_page=False, timeout=5000)
        except Exception as ss_err:
            print(f"[SCREENSHOT ERROR]: {ss_err}")
            return ""

        # 2. Add Informative Diagnostic Header Banner at the top
        try:
            from PIL import Image, ImageDraw
            with Image.open(ss_file) as img:
                img = img.convert("RGB")
                w, h = img.size
                bar_h = 44
                banner_img = Image.new("RGB", (w, h + bar_h), color=(18, 24, 38))
                banner_img.paste(img, (0, bar_h))

                draw = ImageDraw.Draw(banner_img)
                disp_uid = clean_uid if clean_uid else "N/A"
                disp_prof = clean_pname
                disp_lbl = clean_label.replace("_", " ").upper()
                disp_pass = str(password).strip() if password else "N/A"
                if len(disp_pass) > 24:
                    disp_pass = disp_pass[:21] + "..."

                banner_text = f"UID: {disp_uid}  |  Profile: {disp_prof}  |  Status: {disp_lbl}  |  Pass: {disp_pass}  |  Time: {t_stamp}"
                draw.text((16, 14), banner_text, fill=(240, 244, 248))
                banner_img.save(str(ss_file), optimize=True)
        except Exception as banner_err:
            print(f"[SCREENSHOT BANNER NOTICE]: {banner_err}")

        return str(ss_file.resolve())
    except Exception as err:
        print(f"[SCREENSHOT ERROR]: {err}")
        return ""

def _save_fresh_cookies_to_profile(context: Any, pdata: Dict[str, Any]) -> None:
    """Extracts and formats all fresh cookies from Playwright context into profile data."""
    try:
        if not context:
            return
        fresh_cookies = context.cookies()
        if not fresh_cookies:
            return

        cookie_pairs = []
        cuser_uid = ""
        for ck in fresh_cookies:
            c_name = ck.get("name", "")
            c_val = ck.get("value", "")
            if c_name and c_val:
                cookie_pairs.append(f"{c_name}={c_val}")
                if c_name.lower() in ("c_user", "cuser") and str(c_val).isdigit():
                    cuser_uid = str(c_val)

        cookie_str = "; ".join(cookie_pairs)
        pdata["cookie"] = cookie_str
        pdata["cookies"] = cookie_str
        pdata["cookies_json"] = fresh_cookies
        if cuser_uid and not pdata.get("uid"):
            pdata["uid"] = cuser_uid
    except Exception as e:
        print(f"[SAVE FRESH COOKIES ERROR]: {e}")

def detect_facebook_state(page: Any) -> Tuple[str, str]:
    """
    Ultra-Strict Multi-State & Multi-Lingual Analyzer for Facebook web pages.
    Guarantees negative checks (Checkpoint, Captcha, Locked, Continue, Login Form) are evaluated FIRST.
    Only returns LOGGED_IN if the user is truly on the authenticated Home Feed.
    """
    try:
        url = page.url.lower()
        clean_url = url.split("?")[0].rstrip("/")
        body_text = ""
        try:
            body_text = page.locator("body").inner_text(timeout=1500).lower()
        except Exception:
            pass

        # ----------------- 1. POSITIVE SUCCESS / TRUST PROMPTS (EVALUATE FIRST!) -----------------
        # Check 'Trust this device?' Prompt (Multi-Lingual) - Note: Often appears on /checkpoint/ URL!
        trust_device_signals = [
            "trust this device", "you're logged in", "you are logged in",
            "faire confiance à cet appareil", "vous êtes connecté", "vous êtes connectée",
            "confiar en este dispositivo", "has iniciado sesión",
            "dieses gerät als vertrauenswürdig", "du bist angemeldet",
            "confiar neste dispositivo", "você entrou",
            "always confirm it's me", "toujours me demander confirmation"
        ]
        if any(sig in body_text for sig in trust_device_signals):
            return "TRUST_DEVICE_PROMPT", "Trust This Device Prompt (Logged In)"

        try:
            trust_btn = page.locator("button:has-text('Trust this device'), button:has-text('Trust'), button:has-text('Faire confiance'), button:has-text('Confiar en este dispositivo'), button:has-text('Confiar')").first
            if trust_btn.is_visible(timeout=300):
                return "TRUST_DEVICE_PROMPT", "Trust This Device Prompt (Logged In)"
        except Exception:
            pass

        # Check 'We suspect automated behavior on your account' Advisory Notice (Multi-Lingual)
        # Note: Often appears on /checkpoint/ URL or home URL! Must be evaluated before generic /checkpoint/ check.
        automated_behavior_signals = [
            "we suspect automated behavior", "suspect automated behavior",
            "automated behavior on your account",
            "prevent your account from being temporarily restricted",
            "comportement automatisé", "nous soupçonnons un comportement automatisé",
            "comportamiento automatizado", "sospechamos de un comportamiento automatizado",
            "automatisiertes verhalten", "wir vermuten automatisiertes verhalten",
            "comportamento automatizado", "suspeitamos de comportamento automatizado",
            "স্বয়ংক্রিয় আচরণ"
        ]
        if any(sig in body_text for sig in automated_behavior_signals):
            return "AUTOMATED_BEHAVIOR_NOTICE", "Automated Behavior Warning Notice"

        try:
            auto_btn = page.locator("div[role='dialog'] button:has-text('Dismiss'), div[role='dialog'] div[role='button']:has-text('Dismiss'), button:has-text('Dismiss')").first
            if auto_btn.is_visible(timeout=250):
                if any(sig in body_text for sig in ["automated behavior", "terms of use", "temporarily restricted", "unauthorized access"]):
                    return "AUTOMATED_BEHAVIOR_NOTICE", "Automated Behavior Warning Notice"
        except Exception:
            pass

        # Check genuine Home Feed elements
        home_feed_signals = [
            "what's on your mind", "create story", "create a post",
            "que voulez-vous dire", "créer une publication", "créer une story",
            "¿en qué estás pensando?", "crear una publicación"
        ]
        has_post_composer = any(sig in body_text for sig in home_feed_signals)

        home_selectors = [
            "input[placeholder*='Search Facebook']",
            "input[aria-label*='Search Facebook']",
            "input[placeholder*='Rechercher sur Facebook']",
            "input[placeholder*='Buscar en Facebook']",
            "div[aria-label*='Account controls and settings']",
            "div[aria-label*='Your profile']",
            "div[aria-label*='Votre profil']",
            "div[aria-label*='Tu perfil']",
            "div[role='feed']"
        ]
        has_home_nav = False
        for sel in home_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=500):
                    has_home_nav = True
                    break
            except Exception:
                pass

        if has_post_composer or has_home_nav:
            return "LOGGED_IN", "Authenticated Feed Active"

        # ----------------- 2. 2FA / LOGIN APPROVALS -----------------
        if any(term in clean_url for term in ["two_step_verification", "two_factor", "login_approvals"]) or \
           any(term in body_text for term in ["two-factor authentication", "approvals_code", "enter login code", "6-digit code", "code à 6 chiffres", "código de 6 dígitos"]):
            return "2FA_REQUIRED", "2FA Security Code Verification Required"

        # ----------------- 3. REAL CHECKPOINTS / LOCKS / CAPTCHAS -----------------
        if any(term in body_text for term in ["confirm you're human", "enter the text from the image", "can't read this text", "arkose", "matchkey"]) or \
           page.locator("iframe[src*='arkoselabs']").count() > 0:
            return "CAPTCHA_DETECTED", "Captcha Challenge"

        if any(term in body_text for term in ["confirm this is your meta account", "account was locked", "account is locked", "what happens next", "upload your id", "suspended your account", "we suspended your account", "your account has been disabled"]):
            return "ON_CHECKPOINT", "Facebook Security Checkpoint"

        if "/checkpoint/" in url or "account_disabled" in url:
            return "ON_CHECKPOINT", "Facebook Security Checkpoint"

        # ----------------- 4. WRONG PASSWORD -----------------
        if any(term in body_text for term in [
            "incorrect password", "wrong password", "the password you’ve entered is incorrect",
            "the password that you've entered is incorrect", "mot de passe incorrect", "contraseña incorrecta"
        ]):
            return "WRONG_PASSWORD", "Incorrect Password"

        # ----------------- 5. DEVICE APPROVAL -----------------
        if any(term in body_text for term in ["approve from another device", "check your notifications on another device", "approuvez à partir d'un autre appareil"]):
            return "DEVICE_APPROVAL_NEEDED", "Device Approval Needed"

        # ----------------- 6. CONTINUE SCREEN -----------------
        continue_signals = [
            "explorez les sujets", "explore the things you love", "explora las cosas que te encantan",
            "utiliser un autre profil", "use another profile", "usar otro perfil",
            "créer un nouveau compte", "create new account"
        ]
        has_continue_text = any(sig in body_text for sig in continue_signals)

        continue_selectors = [
            "button:has-text('Continuer')",
            "button:has-text('Continue')",
            "button:has-text('Continuar')",
            "button:has-text('Weiter')",
            "div[role='button']:has-text('Continuer')",
            "div[role='button']:has-text('Continue')",
            "button:has-text('Utiliser un autre profil')",
            "button:has-text('Use another profile')"
        ]
        has_continue_btn = False
        for c_sel in continue_selectors:
            try:
                if page.locator(c_sel).first.is_visible(timeout=400):
                    has_continue_btn = True
                    break
            except Exception:
                pass

        if has_continue_text or has_continue_btn:
            return "CONTINUE_SCREEN", "Account Chooser / Continue Landing Screen"

        # ----------------- 7. LOGIN FORM -----------------
        has_login_form = False
        try:
            pass_inputs = page.locator("input[name='pass'], #pass, input[type='password']").all()
            for p_elem in pass_inputs:
                if p_elem.is_visible(timeout=300):
                    has_login_form = True
                    break
        except Exception:
            pass

        if not has_login_form:
            try:
                login_btn = page.locator("button[name='login'], #loginbutton").first
                if login_btn.is_visible(timeout=300):
                    has_login_form = True
            except Exception:
                pass

        if has_login_form:
            return "LOGIN_FORM_READY", "Login Form Ready"

        # ----------------- 8. LOADING SPLASH / HYDRATING PAGE -----------------
        # If no login form, no continue button, no feed, no 2FA, and no checkpoint is found on facebook.com:
        # It is genuinely the Facebook Loading Splash Screen / Hydration Phase!
        if "facebook.com" in url:
            return "FACEBOOK_LOADING", "Facebook Loading Splash Screen"

        return "UNKNOWN_SCREEN", f"Unrecognized Page Layout ({url})"
    except Exception as e:
        return "UNKNOWN_SCREEN", str(e)


def wait_for_facebook_hydration(
    page: Any, 
    max_wait_sec: float = 20.0, 
    log_func: Optional[Any] = None
) -> Tuple[str, str]:
    """
    Intelligently waits for Facebook to transition from Loading Splash Screen to Home Feed or actionable states.
    Polls every 1.2 - 1.8 seconds for up to max_wait_sec (default 20 seconds).
    """
    def log(m: str):
        if log_func: log_func(m)

    start_t = time.time()
    last_logged = start_t

    while time.time() - start_t < max_wait_sec:
        state, desc = detect_facebook_state(page)

        # If it transitioned to any actionable state, exit immediately
        if state != "FACEBOOK_LOADING":
            return state, desc

        # Check if feed / auth is already available in DOM or context
        try:
            cookies = page.context.cookies()
            c_user = any(c.get("name") == "c_user" and c.get("value") for c in cookies)
            has_feed = page.evaluate("""() => {
                return !!(
                    document.querySelector('[role="feed"]') || 
                    document.querySelector('[role="navigation"]') || 
                    document.querySelector('[aria-label*="Facebook"]') ||
                    document.querySelector('[aria-label*="Your profile"]') ||
                    document.querySelector('[data-pagelet="LeftRail"]')
                );
            }""")
            if c_user and has_feed:
                return "LOGGED_IN", "Authenticated Feed Active"
        except Exception:
            pass

        if time.time() - last_logged >= 3.5:
            elapsed = int(time.time() - start_t)
            log(f"  ⏳ Facebook Splash Screen loading... waiting for feed hydration ({elapsed}/{int(max_wait_sec)}s)...")
            last_logged = time.time()

        smart_sleep(1.2, 1.8)

    # If still stuck after max_wait_sec and c_user exists, try a quick navigate to force feed
    try:
        cookies = page.context.cookies()
        c_user = any(c.get("name") == "c_user" and c.get("value") for c in cookies)
        if c_user:
            log("  🔄 Attempting quick page refresh to complete feed loading...")
            page.goto("https://www.facebook.com/", timeout=15000, wait_until="domcontentloaded")
            smart_sleep(2.0, 3.5)
            state, desc = detect_facebook_state(page)
            return state, desc
    except Exception:
        pass

    state, desc = detect_facebook_state(page)
    return state, desc


def handle_facebook_trust_device_prompt(page: Any, log_func: Optional[Any] = None) -> bool:
    """
    Multi-Lingual handler for 'You're logged in. Trust this device?' Facebook prompt.
    Clicks 'Trust this device' / 'Always confirm' or bypasses directly to Home Feed.
    """
    def log(m: str):
        if log_func: log_func(m)

    trust_button_selectors = [
        "button:has-text('Trust this device')",
        "button:has-text('Trust')",
        "button:has-text('Faire confiance à cet appareil')",
        "button:has-text('Faire confiance')",
        "button:has-text('Confiar en este dispositivo')",
        "button:has-text('Confiar')",
        "button:has-text('Dieses Gerät als vertrauenswürdig')",
        "button:has-text('Confiar neste dispositivo')",
        "div[role='button']:has-text('Trust')",
        "div[role='button']:has-text('Faire confiance')",
        "div[role='button']:has-text('Confiar')",
        "button:has-text('Always confirm it’s me')",
        "button:has-text('Always confirm')",
        "div[role='dialog'] button",
        "button[type='submit']"
    ]

    for sel in trust_button_selectors:
        try:
            elem = page.locator(sel).first
            if elem.is_visible(timeout=1000):
                log("  🛡️ Clicking 'Trust this device' button...")
                elem.click(force=True)
                time.sleep(random.uniform(2.0, 3.5))
                return True
        except Exception:
            pass

    # If button click was not needed or done, navigate directly to facebook.com
    try:
        page.goto("https://www.facebook.com/", timeout=15000)
        time.sleep(2.0)
        return True
    except Exception:
        return False


def handle_facebook_automated_behavior_notice(page: Any, log_func: Optional[Any] = None) -> bool:
    """
    Multi-Lingual handler for Facebook's 'We suspect automated behavior on your account' dialog.
    Clicks 'Dismiss', waits random 8.0 - 14.0 seconds (user requested 8 to 12-14s),
    and allows Facebook to transition to the authenticated Home Feed.
    """
    def log(m: str):
        if log_func: log_func(m)

    log("  🛡️ Facebook 'We suspect automated behavior on your account' notice detected.")

    dismiss_selectors = [
        "div[role='dialog'] button:has-text('Dismiss')",
        "div[role='dialog'] div[role='button']:has-text('Dismiss')",
        "button:has-text('Dismiss')",
        "div[role='button']:has-text('Dismiss')",
        "div[aria-label='Dismiss']",
        "div[role='dialog'] button:has-text('Ignorer')",
        "button:has-text('Ignorer')",
        "div[role='dialog'] button:has-text('Descartar')",
        "button:has-text('Descartar')",
        "div[role='dialog'] button:has-text('Schließen')",
        "button:has-text('Schließen')",
        "div[role='dialog'] button:has-text('Dispensar')",
        "button:has-text('Dispensar')",
        "button:has-text('খারিজ করুন')",
        "div[role='dialog'] button",
        "div[role='dialog'] div[role='button']"
    ]

    clicked = False
    for sel in dismiss_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                log(f"  🖱️ Clicking 'Dismiss' button on automated behavior notice ({sel})...")
                try:
                    human_click(btn, delay_before=0.3, delay_after=0.5)
                except Exception:
                    btn.click(force=True)
                clicked = True
                break
        except Exception:
            pass

    if not clicked:
        log("  ⚠️ Direct Dismiss button not clicked; attempting Escape key press...")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    # Wait random 8 to 12-14 seconds as specified by user (8 to 12-14 seconds)
    wait_sec = round(random.uniform(8.0, 14.0), 1)
    log(f"  ⏳ Waiting {wait_sec}s for Facebook to process Dismissal and load Home Feed...")
    smart_sleep(wait_sec, wait_sec + 0.5)

    return clicked


def change_facebook_language_to_english(page: Any, log_func: Optional[Any] = None) -> Tuple[bool, str]:
    """
    Switches account language to English (en_US) via GraphQL mutation
    after a randomized human-like delay (1.0 to 4.0 seconds).
    """
    def log(m: str):
        if log_func: log_func(m)

    delay = round(random.uniform(1.0, 4.0), 1)
    log(f"  ⏳ [Language] Anti-Bot Delay: waiting {delay}s before converting language to English (en_US)...")
    smart_sleep(delay, delay + 0.3)

    try:
        res = page.evaluate(r"""async () => {
            try {
                let token = null;
                try {
                    token = (window.require && (window.require("DTSGInitialData")?.token || window.require("DTSGInitData")?.token)) || null;
                } catch(e) {}

                if (!token) {
                    const inputDtsg = document.querySelector('input[name="fb_dtsg"]');
                    if (inputDtsg) token = inputDtsg.value;
                }

                const uidMatch = document.cookie.match(/c_user=(\d+)/);
                const uid = uidMatch ? uidMatch[1] : null;

                if (!token || !uid) {
                    return { success: false, reason: "DTSG token or UID not found in session" };
                }

                const params = new URLSearchParams({
                    fb_dtsg: token,
                    __a: "1",
                    __user: uid,
                    doc_id: "29960775910235124",
                    variables: JSON.stringify({
                        locale: "en_US",
                        referrer: "WWW_COMET_NAVBAR",
                        fallback_locale: null
                    })
                });

                const response = await fetch("https://www.facebook.com/api/graphql/", {
                    method: "POST",
                    body: params,
                    credentials: "include",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                });

                return { success: response.ok, status: response.status };
            } catch (err) {
                return { success: false, error: err.message };
            }
        }""")

        if res and res.get("success"):
            log("  🌐 [Language] Successfully converted account language to English (en_US) ✅")
            return True, "Language converted to English (en_US)"
        else:
            reason = res.get("reason") or res.get("error") or f"HTTP {res.get('status')}" if res else "Unknown"
            log(f"  ⚠️ [Language] Note: Could not switch language ({reason})")
            return False, reason
    except Exception as ex:
        log(f"  ⚠️ [Language] Language change notice: {ex}")
        return False, str(ex)


def dismiss_facebook_popup_notices(page: Any, log_func: Optional[Any] = None) -> None:
    """Dismisses Facebook cookie consents, Save Browser prompts, and notification dialogs."""
    def log(m: str):
        if log_func: log_func(m)

    # 1. Cookie Banners (Multi-Lingual)
    cookie_selectors = [
        "button:has-text('Allow all cookies')",
        "button:has-text('Accept All')",
        "button:has-text('Autoriser tous les cookies')",
        "button:has-text('Tout accepter')",
        "button:has-text('Permitir todas las cookies')",
        "button:has-text('Aceptar todas')",
        "button:has-text('Allow essential and optional cookies')",
        "button:has-text('Only allow essential cookies')",
        "button:has-text('Uniquement autoriser les cookies essentiels')",
        "button[data-cookiebanner='accept_button']",
        "button[data-cookiebanner='accept_only_essential_button']"
    ]
    for sel in cookie_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                log("  🍪 Dismissing Cookie Consent banner...")
                btn.click()
                time.sleep(1.0)
                break
        except Exception:
            pass

    # 2. Save Login Info / Remember Password Prompt
    save_info_selectors = [
        "button:has-text('Save Info')",
        "button:has-text('Save')",
        "button:has-text('Enregistrer les identifiants')",
        "button:has-text('Guardar información')",
        "button:has-text('Not Now')",
        "button:has-text('Plus tard')",
        "button:has-text('Jetzt nicht')",
        "button:has-text('Ahora no')"
    ]
    for sel in save_info_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                log("  🔐 Handling 'Save Login Info' prompt...")
                btn.click()
                time.sleep(1.0)
                break
        except Exception:
            pass

def submit_facebook_2fa_code(page: Any, secret_2fa: str, log_func: Optional[Any] = None) -> Tuple[bool, str]:
    """Auto-generates 6-digit TOTP code from 2FA Secret and submits it to Facebook."""
    def log(m: str):
        if log_func: log_func(m)

    if not secret_2fa or not str(secret_2fa).strip():
        return False, "No 2FA secret key provided"

    totp_code = generate_totp_2fa_code(secret_2fa)
    if not totp_code:
        log("  ❌ Failed to generate 2FA TOTP code.")
        return False, "Failed to generate TOTP code"

    log(f"  🔑 Generated 2FA TOTP Code: [{totp_code}]. Submitting to Facebook...")

    otp_inputs = [
        "input[name='approvals_code']",
        "input#approvals_code",
        "input[type='text'][placeholder*='code']",
        "input[type='number']",
        "input[placeholder*='6-digit']",
        "input[placeholder*='6 chiffres']",
        "input[placeholder*='6 dígitos']",
        "input[type='text']"
    ]
    found_inp = None
    for sel in otp_inputs:
        try:
            inp = page.locator(sel).first
            if inp.is_visible(timeout=1500):
                found_inp = inp
                break
        except Exception:
            pass

    if not found_inp:
        return False, "2FA OTP input field not found on page"

    # Natural pause to simulate user looking up the 2FA code from authenticator app
    smart_sleep(2.0, 3.8)

    try:
        found_inp.scroll_into_view_if_needed(timeout=2000)
        found_inp.click()
        smart_sleep(0.3, 0.7)
        human_type(found_inp, totp_code, min_delay_ms=80, max_delay_ms=170, clear_first=True)
        smart_sleep(1.2, 2.4)

        submit_buttons = [
            "button#checkpointSubmitButton",
            "button:has-text('Continue')",
            "button:has-text('Continuer')",
            "button:has-text('Continuar')",
            "button:has-text('Submit')",
            "button[type='submit']",
            "button:has-text('Confirm')"
        ]
        clicked = False
        for s_btn in submit_buttons:
            try:
                btn = page.locator(s_btn).first
                if btn.is_visible(timeout=1000):
                    human_click(btn, delay_before=0.3, delay_after=0.4)
                    clicked = True
                    break
            except Exception:
                pass

        if not clicked:
            found_inp.press("Enter")

        smart_sleep(4.0, 6.0)
        return True, "2FA Submitted"
    except Exception as err:
        return False, f"2FA Submission error: {err}"

handle_facebook_2fa_verification = submit_facebook_2fa_code

def perform_facebook_login_flow(
    page: Any,
    context: Any,
    pdata: Dict[str, Any],
    auto_convert_en: bool = False,
    log_func: Optional[Any] = None
) -> Tuple[bool, str, str]:
    """
    Bulletproof Facebook Login Execution Flow with Multi-State Intelligence & Auto-Screenshots.
    Returns (success: bool, status_message: str, screenshot_path: str)
    """
    def log(m: str):
        if log_func: log_func(m)

    def _finalize_login_success():
        if auto_convert_en:
            change_facebook_language_to_english(page, log_func=log)
        _save_fresh_cookies_to_profile(context, pdata)
        return True, "Login Successful (Feed Active)", ""

    pname = pdata.get("name", "Profile")
    pnum = pdata.get("number", "01")

    # Extract credentials from profile data or notes
    email = str(pdata.get("fb_uid") or pdata.get("email") or pdata.get("uid") or pdata.get("username") or "").strip()
    password = str(pdata.get("fb_pass") or pdata.get("password") or "").strip()
    two_factor = str(pdata.get("fb_2fa") or pdata.get("2fa_secret") or pdata.get("two_factor") or pdata.get("secret_2fa") or "").strip()
    cookies_raw = pdata.get("cookies") or pdata.get("fb_cookie") or pdata.get("cookie") or ""

    # Parse credentials from notes if present (Format: UID|PASS|2FA|COOKIE or Email:Pass)
    notes = str(pdata.get("notes") or "").strip()
    if notes and ("|" in notes or ":" in notes) and (not email or not password):
        parts = [p.strip() for p in (notes.split("|") if "|" in notes else notes.split(":"))]
        if len(parts) >= 2:
            if not email: email = parts[0]
            if not password: password = parts[1]
            if len(parts) >= 3 and not two_factor: two_factor = parts[2]
            if len(parts) >= 4 and not cookies_raw: cookies_raw = parts[3]

    # Resolve target UID cleanly for failure screenshots & reports
    target_uid = str(pdata.get("fb_uid") or pdata.get("uid") or email or "").strip()
    if not target_uid and "fb_" in str(pname).lower():
        m_uid = re.search(r"\d{10,20}", str(pname))
        if m_uid:
            target_uid = m_uid.group(0)
    if not target_uid and email:
        target_uid = email

    def _capture_ss(lbl: str) -> str:
        return capture_diagnostic_screenshot(
            page=page,
            profile_name=pnum,
            label=lbl,
            uid=target_uid,
            password=password
        )

    # Step 1: Inject cookies if available
    if cookies_raw and context:
        parsed_cks = parse_cookie_string(str(cookies_raw))
        if parsed_cks:
            try:
                log(f"  🍪 Injecting {len(parsed_cks)} Session Cookie(s)...")
                context.add_cookies(parsed_cks)
            except Exception as ck_err:
                log(f"  ⚠️ Cookie injection notice: {ck_err}")

    # Step 2: Navigate to Facebook
    log("  🌐 Opening Facebook...")
    try:
        page.goto("https://www.facebook.com/", timeout=35000, wait_until="domcontentloaded")
    except Exception as n_err:
        log(f"  ⚠️ Initial navigation timeout, continuing: {n_err}")

    smart_sleep(2.5, 4.0)
    dismiss_facebook_popup_notices(page, log_func=log)

    # Step 3: Initial State Check & Splash Screen Hydration Wait
    state, desc = detect_facebook_state(page)
    if state == "FACEBOOK_LOADING":
        state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)

    # Handle Trust Device Prompt if detected
    if state == "TRUST_DEVICE_PROMPT":
        log("  🛡️ 'Trust this device' prompt detected. Account is authenticated! Dismissing prompt...")
        handle_facebook_trust_device_prompt(page, log_func=log)
        smart_sleep(2.0, 3.5)
        dismiss_facebook_popup_notices(page, log_func=log)
        state, desc = detect_facebook_state(page)
        if state in ("LOGGED_IN", "TRUST_DEVICE_PROMPT"):
            log("  🎉 Active Authenticated Feed verified! Session is alive.")
            return _finalize_login_success()

    # Handle Automated Behavior Notice if detected on landing/after cookies
    if state == "AUTOMATED_BEHAVIOR_NOTICE":
        log("  ⚠️ 'We suspect automated behavior' notice detected on initial page load.")
        handle_facebook_automated_behavior_notice(page, log_func=log)
        smart_sleep(1.0, 2.0)
        dismiss_facebook_popup_notices(page, log_func=log)
        state, desc = detect_facebook_state(page)
        if state == "FACEBOOK_LOADING":
            state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)
        elif state == "AUTOMATED_BEHAVIOR_NOTICE":
            try:
                page.goto("https://www.facebook.com/", timeout=15000, wait_until="domcontentloaded")
                smart_sleep(3.0, 5.0)
                state, desc = detect_facebook_state(page)
            except Exception:
                pass

        if state == "TRUST_DEVICE_PROMPT":
            log("  🛡️ 'Trust this device' prompt detected after Dismiss! Dismissing prompt...")
            handle_facebook_trust_device_prompt(page, log_func=log)
            smart_sleep(2.0, 3.5)
            dismiss_facebook_popup_notices(page, log_func=log)
            state, desc = detect_facebook_state(page)

        if state in ("LOGGED_IN", "TRUST_DEVICE_PROMPT"):
            log("  🎉 Active Authenticated Feed verified after Dismiss! Session is alive.")
            return _finalize_login_success()

    # Handle Continue / Chooser Screen if detected
    if state == "CONTINUE_SCREEN":
        log("  👉 Detected Account Chooser / Continue Landing. Submitting Password...")
        submitted, sub_msg = handle_facebook_profile_continue_screen(page, email=email, password=password, log_func=log)
        smart_sleep(3.0, 5.0)
        dismiss_facebook_popup_notices(page, log_func=log)
        state, desc = detect_facebook_state(page)
        if state == "FACEBOOK_LOADING":
            state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)

        # 2FA Checkpoint right after continue screen password submit:
        if state == "2FA_REQUIRED" and two_factor:
            log("  🛡️ 2FA Checkpoint triggered after Continue. Solving TOTP...")
            ok_2fa, msg_2fa = handle_facebook_2fa_verification(page, two_factor, log_func=log)
            if ok_2fa:
                smart_sleep(3.0, 5.0)
                dismiss_facebook_popup_notices(page, log_func=log)
                state, desc = detect_facebook_state(page)
                if state == "FACEBOOK_LOADING":
                    state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)

        if state == "AUTOMATED_BEHAVIOR_NOTICE":
            log("  ⚠️ 'We suspect automated behavior' notice detected after Continue screen.")
            handle_facebook_automated_behavior_notice(page, log_func=log)
            smart_sleep(1.0, 2.0)
            dismiss_facebook_popup_notices(page, log_func=log)
            state, desc = detect_facebook_state(page)
            if state == "FACEBOOK_LOADING":
                state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)

        # If already on true Home Feed
        if state in ("LOGGED_IN", "TRUST_DEVICE_PROMPT"):
            log("  🎉 Active Authenticated Feed verified! Session is alive.")
            return _finalize_login_success()

        # If password was submitted on continue screen:
        # DO NOT retry with UID/Password because password was already submitted and rejected!
        if submitted and sub_msg == "PASSWORD_SUBMITTED":
            ss_label = "wrong_password" if state in ("WRONG_PASSWORD", "CONTINUE_SCREEN") else state.lower()
            ss_path = _capture_ss(ss_label)
            if state == "WRONG_PASSWORD":
                log(f"  ❌ Password rejected on Continue Screen: {desc}")
                return False, "Incorrect Password (Wrong Password)", ss_path
            elif state in ("ON_CHECKPOINT", "CAPTCHA_DETECTED", "DEVICE_APPROVAL_NEEDED"):
                log(f"  ❌ Account Blocked/Challenged: {desc}")
                return False, desc, ss_path
            elif state == "FACEBOOK_LOADING":
                log(f"  ❌ Facebook feed loading timeout after password submission.")
                return False, "Facebook Loading Timeout (Splash Screen)", ss_path
            else:
                log(f"  ❌ Password submission failed on Continue Screen ({desc}). Skipping duplicate UID retry.")
                return False, f"Incorrect Password or Login Error ({desc})", ss_path

    # If already on true Home Feed
    if state == "LOGGED_IN":
        log("  🎉 Active Authenticated Feed verified! Session is alive.")
        return _finalize_login_success()

    # If Checkpoint / Locked / Captcha / Wrong Password
    if state in ("ON_CHECKPOINT", "CAPTCHA_DETECTED", "DEVICE_APPROVAL_NEEDED", "WRONG_PASSWORD"):
        ss_path = _capture_ss(state.lower())
        log(f"  ❌ Account Blocked/Challenged: {desc}")
        return False, desc, ss_path

    # Step 4: If not logged in, attempt Credential Login (Email/UID + Password)
    if not email or not password:
        log("  ❌ No valid Email/UID or Password provided to login.")
        ss_path = _capture_ss("no_credentials")
        return False, "Missing Email/Password for login", ss_path

    log(f"  🔑 Entering Credentials for UID: [{email[:15]}...]...")

    email_selectors = [
        "input#email",
        "input[name='email']",
        "input[type='email']",
        "input[placeholder*='Email']",
        "input[placeholder*='Mobile']",
        "input[placeholder*='E-mail']",
        "input[placeholder*='Numéro de mobile']",
        "input[aria-label*='Email']",
        "input[aria-label*='Mobile']"
    ]
    email_entered = False
    for sel in email_selectors:
        try:
            inp = page.locator(sel).first
            if inp.is_visible(timeout=1500):
                human_type(inp, email)
                email_entered = True
                break
        except Exception:
            pass

    if not email_entered:
        # If email input is not visible, check if we're on continue screen or need to force /login.php
        state, desc = detect_facebook_state(page)
        if state == "CONTINUE_SCREEN":
            handle_facebook_profile_continue_screen(page, email=email, password=password, log_func=log)
            smart_sleep(3.0, 5.0)
            state, desc = detect_facebook_state(page)

        # Re-check email input
        for sel in email_selectors:
            try:
                inp = page.locator(sel).first
                if inp.is_visible(timeout=1500):
                    human_type(inp, email)
                    email_entered = True
                    break
            except Exception:
                pass

    if not email_entered and state != "LOGGED_IN":
        log("  ❌ Email input field not found on Facebook page.")
        ss_path = _capture_ss("email_input_missing")
        return False, f"Email input box not found ({desc})", ss_path

    if email_entered:
        smart_sleep(1.0, 2.0)
        pass_selectors = [
            "input#pass",
            "input[name='pass']",
            "input[type='password']",
            "input[placeholder*='Password']",
            "input[placeholder*='Mot de passe']",
            "input[placeholder*='Contraseña']"
        ]
        pass_entered = False
        for sel in pass_selectors:
            try:
                inp = page.locator(sel).first
                if inp.is_visible(timeout=1500):
                    inp.scroll_into_view_if_needed(timeout=2000)
                    smart_sleep(0.3, 0.7)
                    human_type(inp, password, min_delay_ms=80, max_delay_ms=160, clear_first=True)
                    pass_entered = True
                    break
            except Exception:
                pass

        if not pass_entered:
            log("  ❌ Password input field not found.")
            ss_path = _capture_ss("pass_input_missing")
            return False, "Password input box not found", ss_path

        smart_sleep(1.2, 2.4)

        # Click Log In button
        login_btn_selectors = [
            "button[name='login']",
            "button#loginbutton",
            "button[type='submit']",
            "button:has-text('Log In')",
            "button:has-text('Log in')",
            "button:has-text('Se connecter')",
            "button:has-text('Iniciar sesión')"
        ]
        btn_clicked = False
        for b_sel in login_btn_selectors:
            try:
                btn = page.locator(b_sel).first
                if btn.is_visible(timeout=1200):
                    human_click(btn, delay_before=0.3, delay_after=0.4)
                    btn_clicked = True
                    break
            except Exception:
                pass

        if not btn_clicked:
            try:
                page.keyboard.press("Enter")
            except Exception:
                pass

        log("  ⏳ Submitted credentials. Waiting for Facebook response...")
        
        # Wait dynamically for Facebook server response and page transition (up to 15s)
        for check_i in range(10):
            # 1. Immediately exit wait if Facebook transitioned to 2FA, Feed, Trust, Checkpoint, etc.
            curr_state, _ = detect_facebook_state(page)
            if curr_state in ("2FA_REQUIRED", "LOGGED_IN", "TRUST_DEVICE_PROMPT", "AUTOMATED_BEHAVIOR_NOTICE", "ON_CHECKPOINT", "CAPTCHA_DETECTED", "DEVICE_APPROVAL_NEEDED", "WRONG_PASSWORD"):
                break

            # 2. Check if explicit red error alert box appeared
            err_box = page.locator("div._9ay7, div[role='alert'], div#error_box")
            if err_box.count() > 0 and err_box.first.is_visible(timeout=100):
                break

            # 3. Only if still on LOGIN_FORM_READY, check if the specific login button is actively spinning
            is_spinning = False
            try:
                login_btn = page.locator("button[name='login'], #loginbutton, button[type='submit']").first
                if login_btn.is_visible(timeout=200):
                    if login_btn.get_attribute("aria-busy") == "true" or login_btn.locator("svg, .uiLoading").count() > 0:
                        is_spinning = True
            except Exception:
                pass

            if is_spinning:
                log(f"  ⏳ Facebook server is authenticating credentials... (waiting {check_i+1}/10)")
                smart_sleep(1.5, 2.5)
                continue

            smart_sleep(1.0, 1.8)
            if check_i >= 3 and curr_state == "LOGIN_FORM_READY":
                break

        dismiss_facebook_popup_notices(page, log_func=log)

    # Step 5: Post-Submission Multi-State Analysis & Hydration Wait
    state, desc = detect_facebook_state(page)
    if state == "FACEBOOK_LOADING":
        state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)

    # State: Trust Device Prompt
    if state == "TRUST_DEVICE_PROMPT":
        log("  🛡️ 'Trust this device' prompt detected. Account is authenticated! Dismissing prompt...")
        handle_facebook_trust_device_prompt(page, log_func=log)
        smart_sleep(2.0, 3.5)
        dismiss_facebook_popup_notices(page, log_func=log)
        state, desc = detect_facebook_state(page)
        if state in ("LOGGED_IN", "TRUST_DEVICE_PROMPT"):
            log("  🎉 Login Successful! Facebook Authenticated Feed is active.")
            return _finalize_login_success()

    # State: Automated Behavior Notice
    if state == "AUTOMATED_BEHAVIOR_NOTICE":
        log("  ⚠️ 'We suspect automated behavior' notice detected post-login.")
        handle_facebook_automated_behavior_notice(page, log_func=log)
        smart_sleep(1.0, 2.0)
        dismiss_facebook_popup_notices(page, log_func=log)
        state, desc = detect_facebook_state(page)
        if state == "FACEBOOK_LOADING":
            state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)
        elif state == "AUTOMATED_BEHAVIOR_NOTICE":
            try:
                page.goto("https://www.facebook.com/", timeout=15000, wait_until="domcontentloaded")
                smart_sleep(3.0, 5.0)
                state, desc = detect_facebook_state(page)
            except Exception:
                pass

        if state == "TRUST_DEVICE_PROMPT":
            log("  🛡️ 'Trust this device' prompt detected after Dismiss! Dismissing prompt...")
            handle_facebook_trust_device_prompt(page, log_func=log)
            smart_sleep(2.0, 3.5)
            dismiss_facebook_popup_notices(page, log_func=log)
            state, desc = detect_facebook_state(page)

        if state in ("LOGGED_IN", "TRUST_DEVICE_PROMPT"):
            log("  🎉 Login Successful! Facebook Authenticated Feed is active.")
            return _finalize_login_success()

    # State: 2FA Prompt
    if state == "2FA_REQUIRED":
        log("  🔐 2FA Screen detected. Attempting automated TOTP verification...")
        if two_factor:
            ok_2fa, msg_2fa = submit_facebook_2fa_code(page, two_factor, log_func=log)
            smart_sleep(3.0, 5.0)
            dismiss_facebook_popup_notices(page, log_func=log)
            state, desc = detect_facebook_state(page)
            if state == "FACEBOOK_LOADING":
                state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)

            # Check if 2FA verification led to 'Trust this device' prompt
            if state == "TRUST_DEVICE_PROMPT":
                log("  🛡️ 'Trust this device' prompt detected after 2FA! Dismissing prompt...")
                handle_facebook_trust_device_prompt(page, log_func=log)
                smart_sleep(2.0, 3.5)
                dismiss_facebook_popup_notices(page, log_func=log)
                state, desc = detect_facebook_state(page)

            # Check if 2FA verification led to 'Automated Behavior' notice
            if state == "AUTOMATED_BEHAVIOR_NOTICE":
                log("  ⚠️ 'We suspect automated behavior' notice detected after 2FA! Dismissing notice...")
                handle_facebook_automated_behavior_notice(page, log_func=log)
                smart_sleep(2.0, 3.5)
                dismiss_facebook_popup_notices(page, log_func=log)
                state, desc = detect_facebook_state(page)
                if state == "FACEBOOK_LOADING":
                    state, desc = wait_for_facebook_hydration(page, max_wait_sec=20.0, log_func=log)

            if state in ("LOGGED_IN", "TRUST_DEVICE_PROMPT"):
                log("  🎉 Login Successful! Facebook Authenticated Feed is active.")
                return _finalize_login_success()
            elif state == "2FA_REQUIRED":
                log("  ❌ 2FA Code was rejected by Facebook (Invalid 2FA Secret Key).")
                ss_path = _capture_ss("2fa_code_rejected")
                return False, "2FA Code Required (Invalid 2FA Key)", ss_path
        else:
            log("  ❌ 2FA Required but no 2FA Secret Key provided for this profile.")
            ss_path = _capture_ss("2fa_key_missing")
            return False, "2FA Code Required", ss_path

    # State: Logged In Success (Strict Verification)
    if state == "LOGGED_IN":
        log("  🎉 Login Successful! Facebook Authenticated Feed is active.")
        return _finalize_login_success()

    # State: Wrong Password
    if state == "WRONG_PASSWORD":
        log("  ❌ Error: Incorrect Password provided.")
        ss_path = _capture_ss("wrong_password")
        return False, "Incorrect Password", ss_path

    # State: Checkpoint / Locked
    if state == "ON_CHECKPOINT":
        log(f"  🚨 Notice: {desc}")
        ss_path = _capture_ss("checkpoint_locked")
        return False, "Facebook Security Checkpoint", ss_path

    # State: Device Approval
    if state == "DEVICE_APPROVAL_NEEDED":
        log("  📱 Notice: Approval needed on another phone/device.")
        ss_path = _capture_ss("device_approval")
        return False, "Device Approval Needed", ss_path

    # State: Captcha
    if state == "CAPTCHA_DETECTED":
        log(f"  🧩 Notice: {desc}")
        ss_path = _capture_ss("captcha_detected")
        return False, "Captcha Challenge", ss_path

    # State: Re-loaded login form or stuck on login.php (Facebook rejected credentials)
    if state in ("LOGIN_FORM_READY", "CONTINUE_SCREEN") or "login.php" in page.url.lower():
        err_msg = ""
        try:
            err_elem = page.locator("div._9ay7, div[role='alert'], div#error_box, div:has-text('incorrect'), div:has-text('invalid')").first
            if err_elem.is_visible(timeout=1000):
                err_msg = err_elem.inner_text().strip()
        except Exception:
            pass

        log(f"  ❌ Credentials rejected by Facebook: {err_msg or 'Incorrect Password or Invalid Credentials'}")
        ss_path = _capture_ss("wrong_password")
        return False, "Incorrect Password", ss_path

    # State: Persistent Splash Screen Timeout
    if state == "FACEBOOK_LOADING":
        log("  ❌ Facebook feed loading timeout (stuck on Splash Screen after 18s).")
        ss_path = _capture_ss("facebook_loading_timeout")
        return False, "Facebook Loading Timeout (Splash Screen)", ss_path

    # Unrecognized / Error
    log(f"  ⚠️ Unrecognized Screen State: {desc}")
    ss_path = _capture_ss("unrecognized_state")
    return False, desc or "Login Failed", ss_path

class LiveAutomationReporter:
    """
    Real-Time / Instant Automation Report Writer (Multi-Sheet Excel & CSV).
    - Creates the formatted report file immediately on disk when automation starts.
    - Appends and flushes each profile/account row immediately the second it finishes.
    - Guarantees zero data loss even in sudden power outages or system crashes.
    """
    def __init__(
        self,
        bot_title: str = "Facebook_Bulk_ID_Login_Studio",
        reports_dir: Optional[Path] = None
    ) -> None:
        import datetime
        import threading
        self.lock = threading.Lock()
        if not reports_dir:
            reports_dir = Path(__file__).parent / "reports"
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.clean_bot_name = re.sub(r"[^\w\-]", "_", bot_title).strip("_")
        self.report_file = self.reports_dir / f"Report_{self.clean_bot_name}_{self.timestamp}.xlsx"
        self.csv_file = self.reports_dir / f"Report_{self.clean_bot_name}_{self.timestamp}.csv"

        self.success_headers = ["Profile_Number", "UID", "Password", "2FA_Secret", "Status", "Cookie"]
        self.failed_headers = ["UID", "Password", "2FA_Secret", "Status", "Message", "Cookie"]

        self.wb = None
        self.ws_success = None
        self.ws_failed = None
        self.use_excel = True
        self.row_count = 0
        self.success_count = 0
        self.failed_count = 0
        self._init_files()

    def _clean_profile_num(self, val: Any) -> str:
        s = str(val or "")
        match = re.search(r"\d+", s)
        return match.group(0) if match else s

    def _clean_failure_message(self, raw_msg: Any) -> str:
        s = str(raw_msg or "").strip()
        s = re.sub(r"\(?https?://[^\s\)]+\)?", "", s)
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        low = s.lower()
        if "checkpoint" in low or "locked" in low:
            return "Facebook Security Checkpoint"
        if "incorrect password" in low or "wrong password" in low or "mot de passe" in low or "identifiants incorrects" in low:
            return "Incorrect Password"
        if "2fa" in low or "two_factor" in low or "two-factor" in low or "totp" in low:
            return "2FA Code Required"
        if "captcha" in low or "human" in low or "arkose" in low:
            return "Captcha Challenge"
        if "disabled" in low or "suspended" in low:
            return "Account Suspended"
        if "approval" in low or "another device" in low:
            return "Device Approval Needed"
        if "missing" in low or "credentials" in low:
            return "Missing Credentials"
        return s or "Login Failed"

    def _init_files(self) -> None:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            self.wb = openpyxl.Workbook()
            self.ws_success = self.wb.active
            self.ws_success.title = "Success"
            self.ws_failed = self.wb.create_sheet(title="Failed")

            header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            success_header_fill = PatternFill(start_color="166534", end_color="166534", fill_type="solid") # Emerald Green
            failed_header_fill = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")  # Crimson Red
            center_align = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style='thin', color='CBD5E1'),
                right=Side(style='thin', color='CBD5E1'),
                top=Side(style='thin', color='CBD5E1'),
                bottom=Side(style='thin', color='CBD5E1')
            )

            # Setup Success Sheet
            self.ws_success.append(self.success_headers)
            for col_idx in range(1, len(self.success_headers) + 1):
                cell = self.ws_success.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = success_header_fill
                cell.alignment = center_align
                cell.border = thin_border
            self.ws_success.row_dimensions[1].height = 26
            self.ws_success.column_dimensions['A'].width = 16
            self.ws_success.column_dimensions['B'].width = 22
            self.ws_success.column_dimensions['C'].width = 20
            self.ws_success.column_dimensions['D'].width = 24
            self.ws_success.column_dimensions['E'].width = 14
            self.ws_success.column_dimensions['F'].width = 60

            # Setup Failed Sheet
            self.ws_failed.append(self.failed_headers)
            for col_idx in range(1, len(self.failed_headers) + 1):
                cell = self.ws_failed.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = failed_header_fill
                cell.alignment = center_align
                cell.border = thin_border
            self.ws_failed.row_dimensions[1].height = 26
            self.ws_failed.column_dimensions['A'].width = 22
            self.ws_failed.column_dimensions['B'].width = 20
            self.ws_failed.column_dimensions['C'].width = 24
            self.ws_failed.column_dimensions['D'].width = 14
            self.ws_failed.column_dimensions['E'].width = 45
            self.ws_failed.column_dimensions['F'].width = 60

            self.wb.save(str(self.report_file))
            self.use_excel = True
        except Exception as ex:
            print(f"[LIVE REPORT] openpyxl init warning: {ex}")
            self.use_excel = False
            # Only create CSV if openpyxl failed completely
            try:
                import csv
                with open(self.csv_file, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    writer.writerow(self.success_headers)
            except Exception:
                pass

    def append_row(self, r: Dict[str, Any]) -> None:
        """Immediately writes single account result to disk."""
        with self.lock:
            self.row_count += 1
            raw_status = str(r.get("Status", r.get("status", "Failed"))).strip()
            is_success = raw_status.lower() == "success"
            status_text = "Success" if is_success else "Failed"

            raw_num = r.get("Profile_Number", r.get("number", ""))
            num_clean = self._clean_profile_num(raw_num)

            uid_val = str(r.get("UID", r.get("uid", r.get("name", "")))).strip()
            pwd_val = str(r.get("Password", r.get("password", "")))
            two_fa_val = str(r.get("2FA_Secret", r.get("two_factor", r.get("2fa", ""))) or "")
            msg_val = self._clean_failure_message(r.get("Message", r.get("message", "Login Failed")))
            cookie_val = str(r.get("Cookie", r.get("cookie", ""))).strip()

            if is_success:
                self.success_count += 1
                row_vals = [num_clean, uid_val, pwd_val, two_fa_val, status_text, cookie_val]
            else:
                self.failed_count += 1
                row_vals = [uid_val, pwd_val, two_fa_val, status_text, msg_val, cookie_val]

            # 1. Write to Excel (.xlsx)
            if self.use_excel and self.wb:
                try:
                    from openpyxl.styles import Font, Alignment, Border, Side

                    data_font = Font(name="Segoe UI", size=10)
                    center_align = Alignment(horizontal="center", vertical="center")
                    left_align = Alignment(horizontal="left", vertical="center")
                    thin_border = Border(
                        left=Side(style='thin', color='CBD5E1'),
                        right=Side(style='thin', color='CBD5E1'),
                        top=Side(style='thin', color='CBD5E1'),
                        bottom=Side(style='thin', color='CBD5E1')
                    )

                    ws = self.ws_success if is_success else self.ws_failed
                    ws.append(row_vals)
                    r_idx = ws.max_row
                    ws.row_dimensions[r_idx].height = 20

                    for col_idx in range(1, len(row_vals) + 1):
                        c = ws.cell(row=r_idx, column=col_idx)
                        c.font = data_font
                        c.border = thin_border
                        c.number_format = '@'
                        if is_success and col_idx in (1, 5):
                            c.alignment = center_align
                        elif (not is_success) and col_idx == 4:
                            c.alignment = center_align
                        else:
                            c.alignment = left_align

                    self.wb.save(str(self.report_file))
                except PermissionError:
                    # Occurs if user has Excel open; save shadow copy so no data is ever lost
                    try:
                        shadow_file = self.reports_dir / f"Report_{self.clean_bot_name}_{self.timestamp}_live.xlsx"
                        self.wb.save(str(shadow_file))
                    except Exception:
                        pass
                except Exception as save_err:
                    print(f"[LIVE REPORT] Excel save error: {save_err}")

            # 2. Append to CSV ONLY if Excel is not available
            elif not self.use_excel:
                try:
                    import csv
                    with open(self.csv_file, "a", newline="", encoding="utf-8-sig") as f:
                        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                        writer.writerow(row_vals)
                except Exception:
                    pass

    def get_report_path(self) -> str:
        if self.use_excel and self.report_file.exists():
            return str(self.report_file.resolve())
        elif self.csv_file.exists():
            return str(self.csv_file.resolve())
        return ""


def save_automation_report_excel(
    report_rows: List[Dict[str, Any]],
    bot_title: str = "Facebook_Bulk_ID_Login_Studio",
    reports_dir: Optional[Path] = None
) -> str:
    """
    Generates a professional Multi-Sheet Excel (.xlsx) Report inside reports/ folder.
    - Sheet 1 (Success): Contains all successfully logged in accounts
    - Sheet 2 (Failed): Contains all failed accounts
    Columns: Profile_Number, UID, Password, 2FA_Secret, Status, Cookie
    """
    reporter = LiveAutomationReporter(bot_title=bot_title, reports_dir=reports_dir)
    for r in report_rows:
        reporter.append_row(r)
    return reporter.get_report_path()

def save_automation_report_csv(
    report_rows: List[Dict[str, Any]],
    bot_title: str = "Facebook_Bulk_ID_Login_Studio",
    reports_dir: Optional[Path] = None
) -> str:
    """Alias to save_automation_report_excel for full backward compatibility."""
    return save_automation_report_excel(report_rows, bot_title=bot_title, reports_dir=reports_dir)


def get_all_logged_in_accounts_list(profile_mgr: Any) -> List[Dict[str, Any]]:
    """
    Extracts all profiles containing Facebook credentials or active cookies from ProfileManager database.
    """
    if not profile_mgr:
        return []

    all_profs = []
    if hasattr(profile_mgr, 'get_all_profiles'):
        all_profs = profile_mgr.get_all_profiles()
    elif hasattr(profile_mgr, 'profiles'):
        all_profs = getattr(profile_mgr, 'profiles', [])

    results = []
    for p in all_profs:
        if not isinstance(p, dict):
            continue

        uid = str(p.get("fb_uid") or p.get("uid") or "").strip()
        pwd = str(p.get("fb_pass") or p.get("password") or "").strip()
        two_fa = str(p.get("fb_2fa") or p.get("secret_2fa") or p.get("2fa_secret") or "").strip()
        ck = str(p.get("cookie") or p.get("fb_cookie") or "").strip()

        # Parse notes as fallback
        notes = str(p.get("notes", "") or p.get("custom_notes", "")).strip()
        if notes and (not uid or not pwd or not ck):
            for line in notes.split("\n"):
                ls = line.strip()
                if ls.startswith("FB UID:") or ls.startswith("UID:"):
                    uid = uid or ls.split(":", 1)[1].strip()
                elif ls.startswith("Pass:") or ls.startswith("Password:"):
                    pwd = pwd or ls.split(":", 1)[1].strip()
                elif "2fa" in ls.lower() and ":" in ls:
                    two_fa = two_fa or ls.split(":", 1)[1].strip()
                elif ls.startswith("Cookie:"):
                    ck = ck or ls.split(":", 1)[1].strip()

        # Include if has any FB identity or cookie
        if uid or pwd or ck or "fb_" in str(p.get("assigned_scripts", "")):
            status_text = "Active Logged-in" if (ck and "c_user" in ck) else ("Session Saved" if ck else "Credentials Saved")
            results.append({
                "profile_id": p.get("id", ""),
                "profile_number": p.get("number", ""),
                "profile_name": p.get("name", f"Profile {p.get('number', '')}"),
                "uid": uid,
                "password": pwd,
                "secret_2fa": two_fa,
                "status": status_text,
                "cookie": ck,
                "group": p.get("group", "Default"),
                "category": p.get("category", "Social"),
                "created_at": p.get("created_at", "")
            })

    return results


def export_all_logged_in_accounts_backup(
    profile_mgr: Any,
    target_filepath: Path,
    format_type: str = "xlsx"
) -> Tuple[bool, int, str]:
    """
    Exports all Facebook accounts in the database to a formatted Excel (.xlsx), Text (.txt), or CSV (.csv) file.
    Returns (success: bool, count: int, filepath: str).
    """
    accounts = get_all_logged_in_accounts_list(profile_mgr)
    if not accounts:
        return False, 0, "No Facebook accounts found in database."

    target_filepath = Path(target_filepath)
    target_filepath.parent.mkdir(parents=True, exist_ok=True)
    ext = target_filepath.suffix.lower()

    try:
        if ext == ".txt" or format_type == "txt":
            with open(target_filepath, "w", encoding="utf-8") as f:
                for acc in accounts:
                    uid = acc.get("uid", "")
                    pwd = acc.get("password", "")
                    two_fa = acc.get("secret_2fa", "")
                    ck = acc.get("cookie", "")
                    parts = [p for p in [uid, pwd, two_fa, ck] if p]
                    f.write("|".join(parts) + "\n")
            return True, len(accounts), str(target_filepath.resolve())

        elif ext == ".csv" or format_type == "csv":
            import csv
            headers = ["Profile_Number", "Profile_Name", "UID", "Password", "2FA_Secret", "Status", "Cookie", "Group", "Created_At"]
            with open(target_filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                writer.writerow(headers)
                for acc in accounts:
                    writer.writerow([
                        acc.get("profile_number", ""),
                        acc.get("profile_name", ""),
                        acc.get("uid", ""),
                        acc.get("password", ""),
                        acc.get("secret_2fa", ""),
                        acc.get("status", ""),
                        acc.get("cookie", ""),
                        acc.get("group", ""),
                        acc.get("created_at", "")
                    ])
            return True, len(accounts), str(target_filepath.resolve())

        else:
            # Default to Excel (.xlsx)
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "FB Logged-In Accounts"

            headers = ["Profile #", "Profile Name", "UID / Email", "Password", "2FA Secret Key", "Status", "Live Cookie", "Target Group", "Created At"]
            ws.append(headers)

            header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid") # Deep Violet
            data_font = Font(name="Segoe UI", size=10)
            center_align = Alignment(horizontal="center", vertical="center")
            left_align = Alignment(horizontal="left", vertical="center")
            thin_border = Border(
                left=Side(style='thin', color='CBD5E1'),
                right=Side(style='thin', color='CBD5E1'),
                top=Side(style='thin', color='CBD5E1'),
                bottom=Side(style='thin', color='CBD5E1')
            )

            # Format Header
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = thin_border
            ws.row_dimensions[1].height = 28

            # Populate Rows
            for r_idx, acc in enumerate(accounts, start=2):
                row_vals = [
                    acc.get("profile_number", ""),
                    acc.get("profile_name", ""),
                    acc.get("uid", ""),
                    acc.get("password", ""),
                    acc.get("secret_2fa", ""),
                    acc.get("status", ""),
                    acc.get("cookie", ""),
                    acc.get("group", ""),
                    acc.get("created_at", "")
                ]
                ws.append(row_vals)
                for col_idx in range(1, len(headers) + 1):
                    c = ws.cell(row=r_idx, column=col_idx)
                    c.font = data_font
                    c.border = thin_border
                    c.number_format = '@'
                    if col_idx in (1, 6): # Profile #, Status
                        c.alignment = center_align
                    else:
                        c.alignment = left_align
                ws.row_dimensions[r_idx].height = 22

            # Column dimensions
            ws.column_dimensions['A'].width = 14  # Profile #
            ws.column_dimensions['B'].width = 18  # Profile Name
            ws.column_dimensions['C'].width = 22  # UID
            ws.column_dimensions['D'].width = 20  # Password
            ws.column_dimensions['E'].width = 24  # 2FA
            ws.column_dimensions['F'].width = 18  # Status
            ws.column_dimensions['G'].width = 65  # Cookie
            ws.column_dimensions['H'].width = 16  # Group
            ws.column_dimensions['I'].width = 20  # Created At

            wb.save(str(target_filepath))
            return True, len(accounts), str(target_filepath.resolve())

    except Exception as err:
        return False, 0, str(err)


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




