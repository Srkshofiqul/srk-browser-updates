import os
import sys
import time
import json
import random
import string
import re
import hmac
import hashlib
import struct
import base64
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Optional openpyxl for styled Excel exports
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


# =========================================================================
# 1. PARSE PAGE NAMES FROM FILE / TEXT
# =========================================================================

def parse_page_names_file_or_text(
    file_path: Optional[str] = None, 
    text_content: Optional[str] = None
) -> List[str]:
    """
    Parses a serial list of Facebook Page Names from:
    - Excel (.xlsx) file
    - CSV (.csv) file
    - Text (.txt) file
    - Direct pasted text string (1 name per line)
    """
    names: List[str] = []

    if file_path and os.path.exists(file_path):
        p = Path(file_path)
        if p.suffix.lower() == ".xlsx" and OPENPYXL_AVAILABLE:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    header = [str(c).strip().lower() for c in rows[0] if c is not None]
                    target_col = 0
                    has_header = False
                    for idx, h in enumerate(header):
                        if "page" in h or "name" in h or "title" in h:
                            target_col = idx
                            has_header = True
                            break
                    start_row = 1 if has_header else 0
                    for r in rows[start_row:]:
                        if r and len(r) > target_col and r[target_col]:
                            val = str(r[target_col]).strip()
                            if val and val.lower() not in ["page name", "name", "page", "title"]:
                                names.append(val)
                return names
            except Exception:
                pass
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read()
            except Exception:
                pass

    if text_content:
        for line in text_content.splitlines():
            clean = line.strip()
            if not clean:
                continue
            # If line is comma/pipe/tab separated, take the first column
            parts = re.split(r"[,\|\t]", clean)
            candidate = parts[0].strip().strip('"').strip("'")
            if candidate and candidate.lower() not in ["page name", "name", "page", "title"]:
                names.append(candidate)

    return names


# =========================================================================
# 2. 2FA TOTP GENERATOR & AUTH HELPERS
# =========================================================================

def get_2fa_totp_code(secret_key: str) -> Optional[str]:
    """Generates standard 6-digit TOTP code using RFC 6238 HMAC-SHA1 algorithm with fallback."""
    if not secret_key:
        return None
    cleaned_key = re.sub(r'[\s\-]', '', str(secret_key)).strip().upper()
    if not cleaned_key or len(cleaned_key) < 8:
        return None

    # Method 1: Local standard Python HMAC-SHA1
    try:
        pad_len = (8 - (len(cleaned_key) % 8)) % 8
        padded_key = cleaned_key + ('=' * pad_len)
        key_bytes = base64.b32decode(padded_key, casefold=True)
        counter = int(time.time() // 30)
        counter_bytes = struct.pack(">Q", counter)
        mac = hmac.new(key_bytes, counter_bytes, hashlib.sha1).digest()
        offset = mac[-1] & 0x0F
        code_int = struct.unpack(">I", mac[offset:offset+4])[0] & 0x7FFFFFFF
        totp = f"{code_int % 1000000:06d}"
        if len(totp) == 6 and totp.isdigit():
            return totp
    except Exception:
        pass

    # Method 2: Fallback 2fa.live API
    try:
        url = f"https://2fa.live/tok/{urllib.parse.quote(cleaned_key)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'srkBrowser/2.0'})
        with urllib.request.urlopen(req, timeout=6) as response:
            res_data = json.loads(response.read().decode())
            token = str(res_data.get("token", "")).strip()
            if len(token) == 6 and token.isdigit():
                return token
    except Exception:
        pass

    return None


# =========================================================================
# 3. AUTO RE-LOGIN FACEBOOK ACCOUNT (UID + PASS + 2FA + COOKIES)
# =========================================================================

def clean_uid_str(val: Any) -> str:
    """Clean UID or username: strip spaces, trailing .0, and FB_ prefix."""
    s = str(val or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    if s.upper().startswith("FB_"):
        s = s[3:]
    return s.strip()


def parse_cookie_string(cookie_raw: str, default_domain: str = ".facebook.com") -> List[Dict[str, Any]]:
    """Robust parser for cookies stored as JSON array string or standard key=value; pairs."""
    if not cookie_raw:
        return []
    raw = str(cookie_raw).strip()
    cookies = []

    # 1. Try JSON array format
    if raw.startswith("[") and raw.endswith("]"):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        domain = item.get("domain") or default_domain
                        if not domain.startswith("."):
                            domain = "." + domain
                        cookies.append({
                            "name": str(item["name"]),
                            "value": str(item["value"]),
                            "domain": domain,
                            "path": item.get("path", "/")
                        })
                return cookies
        except Exception:
            pass

    # 2. Key=Value; format
    pairs = raw.split(";")
    for p in pairs:
        if "=" in p:
            parts = p.split("=", 1)
            k = parts[0].strip()
            v = parts[1].strip()
            if k and v:
                cookies.append({
                    "name": k,
                    "value": v,
                    "domain": default_domain,
                    "path": "/"
                })
    return cookies


def is_continue_button_present(page: Any) -> bool:
    """Checks if the Facebook Continue / Account Chooser button is visible on page."""
    for sel in [
        "div[role='button']:has-text('Continue')",
        "button:has-text('Continue')",
        "div[role='button']:has-text('চালিয়ে যান')",
        "button:has-text('চালিয়ে যান')",
        "div[role='button']:has-text('Continuer')",
        "button[value='Continue']",
        "a[role='button']:has-text('Continue')"
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=600):
                return True
        except Exception:
            pass
    return False


def is_device_approval_screen(page: Any) -> bool:
    """
    Checks if Facebook is prompting 'Check your other device' / tap number on another device.
    This is an unrecoverable on-device challenge that requires physical owner action.
    """
    try:
        curr_url = (page.url or "").lower()
        if "auth_platform" in curr_url or "afad" in curr_url:
            return True
        is_approval = page.evaluate("""() => {
            const text = (document.body?.innerText || '').toLowerCase();
            return (
                text.includes("check your other device") ||
                text.includes("open the notification on your other device") ||
                text.includes("waiting for approval") ||
                text.includes("approve from another device") ||
                (text.includes("tap ") && text.includes("to verify it's you")) ||
                (text.includes("try another way") && text.includes("approval")) ||
                text.includes("অন্য ডিভাইস") ||
                text.includes("অনুমোদনের জন্য অপেক্ষা")
            );
        }""")
        return bool(is_approval)
    except Exception:
        return False


def handle_2fa_challenge(
    page: Any, 
    twofa_secret: str, 
    log_func: Optional[Any] = None
) -> bool:
    """Detects and solves Facebook 2FA challenge via TOTP."""
    def log(m: str):
        if log_func:
            log_func(m)

    curr_url = (page.url or "").lower()
    body_text = ""
    try:
        body_text = (page.locator("body").inner_text(timeout=1500) or "").lower()
    except Exception:
        pass

    has_2fa = (
        any(term in curr_url for term in ["two_step_verification", "two_factor", "login_approvals"]) or
        any(term in body_text for term in ["two-factor", "two factor", "approvals_code", "enter login code", "6-digit code", "authentication code", "লগইন কোড"])
    )

    if not has_2fa:
        return False

    if not twofa_secret:
        log("⚠️ 2FA required by Facebook, but no 2FA Secret Key is saved in database!")
        return False

    log("🛡️ 2FA Checkpoint detected. Generating 6-digit TOTP code...")
    totp_code = get_2fa_totp_code(twofa_secret)
    if not totp_code:
        log("❌ Failed to calculate TOTP code from secret key.")
        return False

    log(f"🔑 Submitting 2FA TOTP Code [{totp_code}]...")
    otp_selectors = [
        'input[name="approvals_code"]',
        'input#approvals_code',
        'input[placeholder*="Code"]',
        'input[placeholder*="code"]',
        'input[placeholder*="6-digit"]',
        'input[type="number"]',
        'input[autocomplete="one-time-code"]',
        'input[type="text"]'
    ]
    otp_filled = False
    for osel in otp_selectors:
        try:
            oinp = page.locator(osel).first
            if oinp.is_visible(timeout=1200):
                oinp.click()
                time.sleep(0.3)
                oinp.fill(totp_code)
                otp_filled = True
                break
        except Exception:
            pass

    if otp_filled:
        time.sleep(0.8)
        submit_2fa_btns = [
            '#checkpointSubmitButton',
            'button[value="Continue"]',
            'button:has-text("Continue")',
            'button:has-text("Submit")',
            'button[type="submit"]',
            'button:has-text("Confirm")',
            'button:has-text("জমা দিন")'
        ]
        s_clicked = False
        for s_sel in submit_2fa_btns:
            try:
                s_b = page.locator(s_sel).first
                if s_b.is_visible(timeout=1000):
                    s_b.click()
                    s_clicked = True
                    break
            except Exception:
                pass
        if not s_clicked:
            page.keyboard.press("Enter")

        time.sleep(4.0)
        dismiss_facebook_popup_notices(page)

        # Handle "Trust this device" prompt
        trust_btns = [
            "button:has-text('Trust this device')",
            "button:has-text('Trust')",
            "button:has-text('Always confirm it’s me')",
            "button:has-text('Always confirm')",
            "div[role='button']:has-text('Trust')",
            "button:has-text('Continue')"
        ]
        for tsel in trust_btns:
            try:
                tb = page.locator(tsel).first
                if tb.is_visible(timeout=1500):
                    tb.click()
                    time.sleep(2.0)
                    break
            except Exception:
                pass
        return True

    return False


def handle_facebook_continue_and_login(
    page: Any, 
    password: str, 
    twofa_secret: str = "",
    log_func: Optional[Any] = None,
    popup_wait_sec: float = 16.0,
    auth_wait_sec: float = 15.0
) -> Tuple[bool, str]:
    """
    Handles Facebook's Remembered Account / Account Chooser screen:
    1. Detects and clicks the 'Continue' (or 'Continue as...') button.
    2. Patiently waits for the password popup/modal to appear (handles Facebook lag without reloading).
    3. Enters the password and submits.
    4. Patiently waits for authentication response (does NOT reload or navigate away!).
    5. Automatically solves 2FA if prompted.
    6. Returns (is_authenticated, message).
    """
    def log(m: str):
        if log_func:
            log_func(m)

    continue_selectors = [
        "div[role='button']:has-text('Continue')",
        "button:has-text('Continue')",
        "div[role='button']:has-text('চালিয়ে যান')",
        "button:has-text('চালিয়ে যান')",
        "div[role='button']:has-text('Continuer')",
        "button:has-text('Continuer')",
        "button[value='Continue']",
        "div[aria-label*='Continue']",
        "div[aria-label*='চালিয়ে যান']",
        "a[role='button']:has-text('Continue')"
    ]

    continue_btn = None
    for sel in continue_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                continue_btn = loc
                break
        except Exception:
            pass

    if not continue_btn:
        return False, "Continue button not visible"

    log("👉 [CONTINUE DETECTED] Facebook remembered profile found. Clicking 'Continue'...")
    try:
        continue_btn.click()
    except Exception:
        try:
            page.evaluate("(sel) => document.querySelector(sel)?.click()", "div[role='button']:has-text('Continue'), button:has-text('Continue')")
        except Exception:
            pass

    # Wait 5-7 seconds for password popup to render as requested by user
    log("⏳ Clicked 'Continue'. Waiting 5-7 seconds for password popup to render...")
    time.sleep(5.5)

    password_selectors = [
        "div[role='dialog'] input[type='password']",
        "div[role='dialog'] input[name='pass']",
        "input[type='password']",
        "input[name='pass']",
        "input#pass",
        "input[placeholder*='Password']",
        "input[placeholder*='password']",
        "input[placeholder*='পাসওয়ার্ড']",
        "input[aria-label*='Password']",
        "input[aria-label*='পাসওয়ার্ড']"
    ]

    pass_input = None
    # Check if already authenticated or find password field
    is_in, _ = check_facebook_login_status(page, timeout_sec=0.5)
    if is_in:
        log("🎉 Instantly authenticated after clicking Continue!")
        return True, "Authenticated via Continue"

    start_find = time.time()
    while time.time() - start_find < 6.0:
        for p_sel in password_selectors:
            try:
                p_loc = page.locator(p_sel).first
                if p_loc.is_visible(timeout=400):
                    pass_input = p_loc
                    break
            except Exception:
                pass
        if pass_input:
            break
        time.sleep(0.5)

    if not pass_input:
        # Check one more time if logged in directly
        is_in, _ = check_facebook_login_status(page, timeout_sec=1.5)
        if is_in:
            log("🎉 Authenticated after Continue!")
            return True, "Authenticated via Continue"
        return False, "Password popup did not appear"

    if not password:
        return False, "Password popup appeared, but no password found in profile database"

    log("🔑 [PASSWORD POPUP] Password popup detected! Entering password...")
    try:
        time.sleep(0.6)
        pass_input.click()
        time.sleep(0.4)
        pass_input.fill(str(password))
        time.sleep(0.8)

        # Submit password
        submit_selectors = [
            "div[role='dialog'] button[type='submit']",
            "div[role='dialog'] button:has-text('Log In')",
            "div[role='dialog'] button:has-text('Log in')",
            "div[role='dialog'] button:has-text('লগ ইন')",
            "div[role='dialog'] div[role='button']:has-text('Log In')",
            "div[role='dialog'] div[role='button']:has-text('Log in')",
            "div[role='dialog'] div[role='button']:has-text('লগ ইন')",
            "button[name='login']",
            "button[type='submit']",
            "div[role='button']:has-text('Log In')",
            "div[role='button']:has-text('Log in')"
        ]
        clicked_sub = False
        for s_sel in submit_selectors:
            try:
                s_loc = page.locator(s_sel).first
                if s_loc.is_visible(timeout=800):
                    s_loc.click()
                    clicked_sub = True
                    break
            except Exception:
                pass
        if not clicked_sub:
            page.keyboard.press("Enter")

        # As requested: Wait solid 8-10 seconds for next page to load with NO actions in between!
        log("⏳ Password submitted. Waiting 8-10 seconds for next page to load (no actions in between)...")
        time.sleep(8.5)

        dismiss_facebook_popup_notices(page)

        # 0. Check for unrecoverable Device Approval ("Check your other device" / Tap number)
        if is_device_approval_screen(page):
            log("⚠️ [DEVICE APPROVAL DETECTED] Facebook requested physical device approval ('Check your other device'). This account cannot be automated. Exiting immediately...")
            return False, "Device Approval Required (Check other device)"

        # 1. Check if logged in
        is_in, _ = check_facebook_login_status(page, timeout_sec=1.5)
        if is_in:
            log("🎉 Facebook Login successfully verified via Continue popup!")
            return True, "Login successful"

        # 2. Check for 2FA challenge
        if handle_2fa_challenge(page, twofa_secret, log_func):
            time.sleep(3.0)
            is_in, _ = check_facebook_login_status(page, timeout_sec=3.0)
            if is_in:
                log("🎉 Facebook Login successfully verified after 2FA!")
                return True, "Login successful"

        # 3. Check for errors
        body_text = ""
        try:
            body_text = (page.locator("body").inner_text(timeout=1000) or "").lower()
        except Exception:
            pass
        if "incorrect password" in body_text or "wrong password" in body_text or "ভুল পাসওয়ার্ড" in body_text:
            log("❌ Facebook reported: Incorrect password.")
            return False, "Incorrect Password"
        if "suspended" in body_text or "account is locked" in body_text or "account was locked" in body_text:
            log("🔴 Facebook reported: Account Locked / Suspended.")
            return False, "Account Checkpoint / Locked"

        # 4. Final verification
        is_in, status_c = check_facebook_login_status(page, timeout_sec=3.0)
        if is_in:
            log("🎉 Facebook Login successfully verified via Continue popup!")
            return True, "Login successful"

        return False, f"Continue login did not complete ({status_c})"

    except Exception as e_sub:
        log(f"⚠️ Exception in continue login flow: {e_sub}")
        return False, f"Continue exception: {str(e_sub)}"


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
    except Exception as err:
        print(f"[FBRL TOTP ERROR]: {err}")
        return ""


def human_type(locator: Any, text: str, min_delay_ms: int = 45, max_delay_ms: int = 125, clear_first: bool = False) -> None:
    """Simulates natural human typing cadence."""
    try:
        locator.click(timeout=3000)
        time.sleep(random.uniform(0.15, 0.35))
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


def detect_facebook_tab_state(page: Any) -> Tuple[str, str]:
    """
    Detects current Facebook page state (ON_CHECKPOINT, 2FA_REQUIRED, CONTINUE_SCREEN, LOGIN_FORM_READY, LOGGED_IN).
    Strict Priority:
      1. Checkpoint / Suspended Account Check
      2. 2FA Two-Factor Challenge Check
      3. Continue / Account Switcher Screen Check (e.g. "Continue as", [Continue] button, avatar)
      4. Standard Login Form Check (email/pass fields)
      5. Genuinely Logged-in Home Feed Check (requires actual feed/post/profile elements, NEVER generic role='main')
    """
    try:
        url = (page.url or "").lower()

        # 1. Checkpoint / Security Lock
        if any(k in url for k in ("/checkpoint/", "/identity/", "/two_step_verification/", "/disabled/", "/help/contact/", "/recover/", "/auth_platform/", "/afad/")):
            return "ON_CHECKPOINT", "Facebook Security Checkpoint URL"

        checkpoint_selectors = [
            "div:has-text('Your account has been locked')",
            "div:has-text('Account locked')",
            "div:has-text('Help us confirm it')",
            "div:has-text('Suspicious activity detected')",
            "div:has-text('Confirm you\\'re human')",
            "div:has-text('Your account has been suspended')",
            "div#checkpointSubmitButton"
        ]
        for sel in checkpoint_selectors:
            if page.locator(sel).first.is_visible(timeout=350):
                return "ON_CHECKPOINT", "Facebook Security Checkpoint"

        # 2. 2FA Two-Factor Authentication Check
        two_fa_selectors = [
            "input[name='approvals_code']",
            "input#approvals_code",
            "input[name='code']",
            "input[id*='code']",
            "div:has-text('Two-factor authentication')",
            "div:has-text('Enter login code')",
            "div:has-text('Check your notifications on another device')"
        ]
        for sel in two_fa_selectors:
            if page.locator(sel).first.is_visible(timeout=350):
                return "2FA_REQUIRED", "Two-Factor Authentication Prompt"

        # 3. Continue / Profile Avatar Screen Check (MUST be checked BEFORE Logged-In check!)
        continue_btn = page.locator("div[role='button']:has-text('Continue'), button:has-text('Continue'), div[role='button']:has-text('Log In As'), div[role='button']:has-text('Continue as'), a:has-text('Continue'), div:has-text('Use another profile'), a:has-text('Use another profile')").first
        if continue_btn.is_visible(timeout=500):
            return "CONTINUE_SCREEN", "Continue Profile Screen Detected"

        pass_input_continue = page.locator("input#pass, input[name='pass'], input[type='password']").first
        avatar_img = page.locator("img[alt*='profile'], img[src*='profile'], div[aria-label*='Profile photo'], div._aa_").first
        if pass_input_continue.is_visible(timeout=400) and (avatar_img.is_visible(timeout=400) or continue_btn.is_visible(timeout=400)):
            return "CONTINUE_SCREEN", "Continue Password Screen with Avatar"

        # 4. Standard Login Form Ready
        email_inp = page.locator("input#email, input[name='email']").first
        if email_inp.is_visible(timeout=400):
            return "LOGIN_FORM_READY", "Standard Login Form Ready"

        if "login" in url or "recover" in url:
            return "LOGIN_FORM_READY", "Facebook Login URL"

        # 5. Genuinely Logged-in Home Feed Check
        # STRICT RULE: NEVER include generic 'div[role="main"]' as it exists on login/continue pages!
        feed_selectors = [
            "div[role='feed']",
            "div[aria-label*='Stories']",
            "div[aria-label*='Create a post']",
            "div[aria-label*='একটি পোস্ট তৈরি করুন']",
            "div[data-pagelet='LeftRail']",
            "input[placeholder*='Search Facebook']",
            "input[placeholder*='ফেসবুক সার্চ']",
            "svg[aria-label='Your profile']",
            "div[aria-label*='Account controls']",
            "a[href*='/friends/']"
        ]
        for sel in feed_selectors:
            if page.locator(sel).first.is_visible(timeout=400):
                return "LOGGED_IN", "Active Home Feed Verified"

        # Check cookies in context
        try:
            for ck in page.context.cookies():
                if ck.get("name") in ("c_user", "cuser") and str(ck.get("value", "")).isdigit():
                    if "login" not in url and "checkpoint" not in url:
                        # Extra safeguard: Ensure continue button is not on screen before declaring logged in via cookie
                        if not continue_btn.is_visible(timeout=300):
                            return "LOGGED_IN", f"Authenticated (c_user={ck.get('value')})"
        except Exception:
            pass

        return "UNKNOWN_OR_LOADING", "Page loading or unrecognized screen"
    except Exception as err:
        return "ERROR", str(err)


def capture_diagnostic_screenshot(
    page: Any,
    profile_name: str = "profile",
    label: str = "error",
    reports_dir: Optional[Path] = None,
    uid: str = "",
    password: str = "",
    extra_info: str = ""
) -> str:
    """
    Captures a high-resolution diagnostic screenshot of the browser page state when failure occurs.
    Saved under reports/screenshots/UID_{uid}_{pname}_{label}_{timestamp}.png
    Also overlays a clear diagnostic header banner at top with UID, Profile, Status and Timestamp.
    """
    try:
        import datetime
        if not reports_dir:
            reports_dir = Path(__file__).resolve().parent / "reports"
        ss_dir = reports_dir / "screenshots"
        ss_dir.mkdir(parents=True, exist_ok=True)

        clean_pname = re.sub(r"[^\w\-]", "_", str(profile_name)).strip("_") or "profile"
        clean_label = re.sub(r"[^\w\-]", "_", str(label)).strip("_") or "error"
        t_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        clean_uid = re.sub(r"[^\w\-]", "", str(uid)).strip()
        if not clean_uid and "fb_" in clean_pname.lower():
            match = re.search(r"\d{10,20}", clean_pname)
            if match:
                clean_uid = match.group(0)

        if clean_uid:
            file_name = f"UID_{clean_uid}_{clean_pname}_{clean_label}_{t_stamp}.png"
        else:
            file_name = f"{clean_pname}_{clean_label}_{t_stamp}.png"

        ss_file = ss_dir / file_name

        if not page or page.is_closed():
            return ""

        page.screenshot(path=str(ss_file), full_page=False, timeout=5000)

        # Draw banner if PIL is available
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
                info_snippet = f" | {extra_info[:35]}..." if extra_info else ""

                banner_text = f"UID: {disp_uid}  |  Profile: {disp_prof}  |  Status: {disp_lbl}{info_snippet}  |  Time: {t_stamp}"
                draw.text((16, 14), banner_text, fill=(240, 244, 248))
                banner_img.save(str(ss_file), optimize=True)
        except Exception:
            pass

        return str(ss_file.resolve())
    except Exception as err:
        print(f"[SCREENSHOT ERROR]: {err}")
        return ""


def auto_relogin_facebook(
    page: Any,
    context: Optional[Any] = None,
    profile_data: Optional[Dict[str, Any]] = None,
    profile_mgr: Optional[Any] = None,
    user_data_dir: str = "",
    log_func: Optional[Any] = None,
    timeout_sec: float = 30.0,
    **kwargs
) -> Tuple[bool, str]:
    """
    1-Click FB Auto Re-login (FBRL engine):
    - Connects to current live page
    - Inspects active tab state (CONTINUE_SCREEN, 2FA, LOGIN_FORM, etc.)
    - Handles Continue Screen directly (types password, clicks Login, no unnecessary reloads)
    - Automatically solves 2FA TOTP challenges
    - Injects session cookies if standard login form or new tab
    - Verifies genuine LOGGED_IN state with c_user
    - Persists fresh cookies to database & profile files
    """
    def log(m: str):
        if log_func:
            log_func(m)

    pdata = profile_data or {}
    pname = pdata.get("name", "Profile")
    profile_id = pdata.get("id") or str(pdata.get("number", "1"))

    # Extract credentials
    email = str(pdata.get("fb_uid") or pdata.get("email") or pdata.get("uid") or pdata.get("username") or "").strip()
    if not email and "fb_" in str(pname).lower():
        m = re.search(r"\d{10,20}", str(pname))
        if m:
            email = m.group(0)
    password = str(pdata.get("fb_pass") or pdata.get("password") or pdata.get("pass") or "").strip()
    two_factor = str(pdata.get("fb_2fa") or pdata.get("2fa_secret") or pdata.get("two_factor") or pdata.get("secret_2fa") or pdata.get("2fa") or "").strip()
    cookies_raw = pdata.get("cookies") or pdata.get("fb_cookie") or pdata.get("cookie") or ""

    # Parse credentials from notes if present
    notes = str(pdata.get("notes") or "").strip()
    if notes:
        m_uid = re.search(r'(?:uid|fb\s*uid|id|user):\s*([0-9a-zA-Z\._\-]+)', notes, re.IGNORECASE)
        m_pwd = re.search(r'(?:pass|password|pwd):\s*([^\s\|]+)', notes, re.IGNORECASE)
        m_2fa = re.search(r'(?:2fa|totp|secret):\s*([0-9a-zA-Z\s]+)', notes, re.IGNORECASE)
        if m_uid and not email: email = m_uid.group(1).strip()
        if m_pwd and not password: password = m_pwd.group(1).strip()
        if m_2fa and not two_factor: two_factor = m_2fa.group(1).strip()

        if "|" in notes and (not email or not password):
            parts = [p.strip() for p in notes.split("|")]
            if len(parts) >= 2:
                if not email: email = parts[0]
                if not password: password = parts[1]
                if len(parts) >= 3 and not two_factor: two_factor = parts[2]
                if len(parts) >= 4 and not cookies_raw: cookies_raw = parts[3]

    log(f"🔑 [AUTO RE-LOGIN] Authenticating profile '{pname}'...")

    try:
        # Check current tab state
        current_state, state_desc = detect_facebook_tab_state(page)
        log(f"  🔍 Tab State: [{current_state}] - {state_desc}")

        if current_state == "LOGGED_IN":
            return True, "Already logged in"

        # -------------------------------------------------------------
        # CASE A: CONTINUE SCREEN ALREADY VISIBLE
        # DO NOT reload! DO NOT inject cookies! Directly type password!
        # -------------------------------------------------------------
        if current_state == "CONTINUE_SCREEN":
            log("  🎯 Continue Screen detected! Authenticating...")
            has_pass_now = False
            for sel in ["input#pass", "input[name='pass']", "input[type='password']"]:
                if page.locator(sel).first.is_visible(timeout=400):
                    has_pass_now = True
                    break

            if not has_pass_now:
                cont_btn = page.locator("div[role='button']:has-text('Continue'), button:has-text('Continue'), div[role='button']:has-text('Log In As'), div[role='button']:has-text('Continue as'), a:has-text('Continue')").first
                if cont_btn.is_visible(timeout=1000):
                    log("  👉 Clicking 'Continue' button...")
                    cont_btn.click()
                    time.sleep(1.5)

            pass_entered = False
            for sel in ["input#pass", "input[name='pass']", "input[type='password']"]:
                inp = page.locator(sel).first
                if inp.is_visible(timeout=2500):
                    log("  ⌨️ Typing password into Continue Screen...")
                    human_type(inp, password, clear_first=True)
                    time.sleep(0.4)
                    sub_btn = page.locator("button[name='login'], button#loginbutton, button[type='submit'], div[role='button']:has-text('Log In')").first
                    if sub_btn.is_visible(timeout=1000):
                        sub_btn.click()
                    else:
                        page.keyboard.press("Enter")
                    time.sleep(3.5)
                    pass_entered = True
                    break

        # -------------------------------------------------------------
        # CASE B: NOT ON FB OR LOGIN FORM
        # -------------------------------------------------------------
        elif current_state not in ("LOGGED_IN", "2FA_REQUIRED"):
            curr_url = (page.url or "").lower()
            if "facebook.com" not in curr_url or "login" in curr_url or current_state == "LOGIN_FORM_READY":
                if cookies_raw and context:
                    cks = parse_cookie_string(str(cookies_raw))
                    if cks:
                        log(f"  🍪 Injecting {len(cks)} saved session cookie(s)...")
                        try:
                            context.add_cookies(cks)
                        except Exception:
                            pass

                log("  🌐 Loading facebook.com...")
                try:
                    page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                except Exception:
                    pass
                time.sleep(2.5)

                current_state, state_desc = detect_facebook_tab_state(page)
                log(f"  🔍 Post-Navigation State: [{current_state}] - {state_desc}")

                if current_state == "CONTINUE_SCREEN":
                    has_pass_now = False
                    for sel in ["input#pass", "input[name='pass']", "input[type='password']"]:
                        if page.locator(sel).first.is_visible(timeout=400):
                            has_pass_now = True
                            break
                    if not has_pass_now:
                        cont_btn = page.locator("div[role='button']:has-text('Continue'), button:has-text('Continue'), a:has-text('Continue')").first
                        if cont_btn.is_visible(timeout=1000):
                            cont_btn.click()
                            time.sleep(1.5)
                    for sel in ["input#pass", "input[name='pass']", "input[type='password']"]:
                        inp = page.locator(sel).first
                        if inp.is_visible(timeout=2500):
                            log("  ⌨️ Typing password into Continue Screen...")
                            human_type(inp, password, clear_first=True)
                            time.sleep(0.4)
                            sub_btn = page.locator("button[name='login'], button#loginbutton, button[type='submit'], div[role='button']:has-text('Log In')").first
                            if sub_btn.is_visible(timeout=1000):
                                sub_btn.click()
                            else:
                                page.keyboard.press("Enter")
                            time.sleep(3.5)
                            break

                elif current_state == "LOGIN_FORM_READY" and email and password:
                    log(f"  🔑 Entering UID [{email[:15]}...] and Password...")
                    e_inp = page.locator("input#email, input[name='email']").first
                    if e_inp.is_visible(timeout=1500):
                        human_type(e_inp, email, clear_first=True)
                    time.sleep(0.4)
                    p_inp = page.locator("input#pass, input[name='pass'], input[type='password']").first
                    if p_inp.is_visible(timeout=1500):
                        human_type(p_inp, password, clear_first=True)
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    time.sleep(3.5)

        # -------------------------------------------------------------
        # STEP 2: 2FA TOTP AUTO-SOLVER
        # -------------------------------------------------------------
        current_state, state_desc = detect_facebook_tab_state(page)
        if current_state == "2FA_REQUIRED":
            log("  🔐 2FA Challenge detected on screen!")
            if two_factor:
                totp_code = generate_totp_2fa_code(two_factor)
                if totp_code:
                    log(f"  ⚡ Generated Live TOTP Code: [{totp_code}]. Submitting...")
                    code_inp = page.locator("input[name='approvals_code'], input#approvals_code, input[name='code'], input[type='number'], input[type='text']").first
                    if code_inp.is_visible(timeout=2000):
                        human_type(code_inp, totp_code, clear_first=True)
                        time.sleep(0.5)
                        page.keyboard.press("Enter")
                        time.sleep(3.0)

                        for btn_text in ["Save Browser", "Trust", "Continue", "Don't Save", "Remember"]:
                            btn = page.locator(f"button:has-text('{btn_text}'), div[role='button']:has-text('{btn_text}')").first
                            if btn.is_visible(timeout=1000):
                                btn.click()
                                time.sleep(1.5)
                                break
            else:
                log("  ⚠️ 2FA required by Facebook, but no 2FA secret key was found in profile.")

        # -------------------------------------------------------------
        # STEP 3: FINAL VERIFICATION & FRESH COOKIE PERSISTENCE
        # -------------------------------------------------------------
        time.sleep(2.0)
        current_state, state_desc = detect_facebook_tab_state(page)
        log(f"  🏁 Final Verification State: [{current_state}] - {state_desc}")

        if current_state == "LOGGED_IN":
            ctx = context or getattr(page, "context", None)
            if ctx:
                try:
                    fresh_cookies = ctx.cookies()
                    if fresh_cookies:
                        cookie_pairs = [f"{c['name']}={c['value']}" for c in fresh_cookies if c.get("name") and c.get("value")]
                        fresh_cookie_str = "; ".join(cookie_pairs)

                        if profile_mgr and hasattr(profile_mgr, "update_profile"):
                            try:
                                profile_mgr.update_profile(
                                    profile_id,
                                    cookie=fresh_cookie_str,
                                    start_url="https://www.facebook.com"
                                )
                                log("  💾 Updated fresh session cookies in software database!")
                            except Exception as pe:
                                log(f"  ⚠️ Database update notice: {pe}")

                        try:
                            p_folder = None
                            if profile_mgr and hasattr(profile_mgr, "get_profile_folder"):
                                p_folder = profile_mgr.get_profile_folder(profile_id)
                            elif user_data_dir:
                                p_folder = Path(user_data_dir)

                            if p_folder and Path(p_folder).exists():
                                try:
                                    from browser import inject_cookies_to_chromium_profile, create_cookie_injector_extension
                                    inject_cookies_to_chromium_profile(p_folder, fresh_cookie_str)
                                    updated_p = profile_mgr.get_profile_by_id(profile_id) if profile_mgr else profile_data
                                    if updated_p:
                                        create_cookie_injector_extension(p_folder, updated_p)
                                    log("  💾 Synchronized fresh cookies to Chromium profile files & injector extension!")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

            return True, f"Re-login SUCCESSFUL for [{pname}]! Active Facebook session restored."

        elif current_state == "ON_CHECKPOINT":
            return False, f"Account on Security Checkpoint ({state_desc})"

        elif current_state == "CONTINUE_SCREEN":
            return False, "Facebook rejected the credentials on Continue screen."

        else:
            return False, f"Re-login incomplete ({state_desc})"

    except Exception as e:
        return False, f"Login exception: {str(e)}"


def dismiss_facebook_popup_notices(page: Any) -> None:
    """Dismisses Facebook popups, Remember password dialogs, and cookie banners."""
    dismiss_selectors = [
        "div[role='button']:has-text('Not now')",
        "div[role='button']:has-text('Not Now')",
        "div[role='button']:has-text('এখন নয়')",
        "button:has-text('Not now')",
        "button:has-text('Not Now')",
        "button:has-text('OK')",
        "button:has-text('Ok')",
        "div[aria-label='Close']",
        "div[aria-label='বন্ধ করুন']",
        "button[data-cookiebanner='accept_button']",
        "button:has-text('Allow all cookies')",
        "button:has-text('Decline optional cookies')"
    ]
    for sel in dismiss_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=350):
                btn.click()
                time.sleep(0.2)
        except Exception:
            pass


def apply_bot_window_icon_win32(ico_path: Path, num_text: str = "") -> None:
    """
    Applies the custom numbered profile icon (.ico) to the active browser window
    and taskbar button on Windows via Win32 API.
    """
    if os.name != "nt" or not ico_path.exists():
        return

    main_pid = os.getpid()

    def _worker():
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        GCLP_HICON = -14
        GCLP_HICONSM = -34

        hIcon = user32.LoadImageW(
            None,
            str(ico_path.resolve()),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE
        )
        if not hIcon:
            return

        tag_bracket = f"[{num_text}]" if num_text else ""
        tag_hash = f"#{num_text}" if num_text else ""

        for _ in range(15):
            time.sleep(0.3)
            hwnds = []

            def EnumWindowsProc(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    lpdwProcessId = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdwProcessId))
                    if lpdwProcessId.value == main_pid:
                        return True

                    buf = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd, buf, 256)
                    t_val = buf.value or ""

                    # Match Chrome/Edge browser window
                    if any(k in t_val.lower() for k in ["facebook", "chrome", "edge", "google"]) or (tag_bracket and tag_bracket in t_val) or (tag_hash and tag_hash in t_val):
                        hwnds.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(EnumWindowsProc), 0)

            if hwnds:
                for hwnd in hwnds:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hIcon)
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hIcon)
                    try:
                        if ctypes.sizeof(ctypes.c_void_p) == 8:
                            user32.SetClassLongPtrW(hwnd, GCLP_HICON, hIcon)
                            user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, hIcon)
                        else:
                            user32.SetClassLongW(hwnd, GCLP_HICON, hIcon)
                            user32.SetClassLongW(hwnd, GCLP_HICONSM, hIcon)
                    except Exception:
                        pass
                    try:
                        user32.SetPropW(hwnd, "AppUserModelID", f"srkBrowser.Profile.{num_text}")
                    except Exception:
                        pass
                break

    import threading
    threading.Thread(target=_worker, daemon=True).start()



def check_facebook_login_status(driver_or_page: Any, timeout_sec: float = 5.0) -> Tuple[bool, str]:
    """
    Checks if the active browser session is genuinely logged into Facebook and healthy (not checkpointed or locked).
    Returns: (is_healthy_login, status_code) where status_code is 'OK', 'CHECKPOINT', or 'LOGGED_OUT'.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            # Playwright Page instance
            if hasattr(driver_or_page, "evaluate"):
                curr_url = (driver_or_page.url or "").lower()
                
                # Check for explicit Checkpoint / Suspend URLs
                if any(k in curr_url for k in ("/checkpoint/", "/identity/", "/two_step_verification/", "/disabled/", "/help/contact/", "/recover/", "/auth_platform/", "/afad/")):
                    return False, "CHECKPOINT"

                # Check for Checkpoint DOM markers
                is_checkpoint = driver_or_page.evaluate("""() => {
                    const text = (document.body?.innerText || '').toLowerCase();
                    return (
                        text.includes("confirm you're human") ||
                        text.includes("confirm your identity") ||
                        text.includes("your account has been suspended") ||
                        text.includes("help us confirm it's you") ||
                        text.includes("account disabled") ||
                        text.includes("check your other device") ||
                        text.includes("waiting for approval") ||
                        text.includes("open the notification on your other device") ||
                        text.includes("approve from another device") ||
                        text.includes("আপনাকে যাচাই করুন") ||
                        text.includes("আমরা সন্দেহজনক কার্যকলাপ") ||
                        text.includes("অন্য ডিভাইস")
                    );
                }""")
                if is_checkpoint:
                    return False, "CHECKPOINT"

                has_login_form = driver_or_page.evaluate("""() => {
                    return !!(
                        document.querySelector('input[name="email"]') && 
                        document.querySelector('input[name="pass"]')
                    );
                }""")
                if has_login_form or "login" in curr_url:
                    return False, "LOGGED_OUT"

                has_continue_screen = driver_or_page.evaluate("""() => {
                    return Array.from(document.querySelectorAll("div[role='button'], button, a")).some(b => {
                        const t = (b.innerText || '').trim();
                        return t === 'Continue' || t.startsWith('Continue as') || t.includes('Use another profile') || t.includes('Log In As');
                    });
                }""")
                if has_continue_screen:
                    return False, "LOGGED_OUT"

                cookies = driver_or_page.context.cookies()
                c_user = any(c.get("name") == "c_user" and c.get("value") for c in cookies)
                has_feed = driver_or_page.evaluate("""() => {
                    return !!(
                        document.querySelector('[role="feed"]') || 
                        document.querySelector('[role="navigation"]') || 
                        document.querySelector('[aria-label*="Facebook"]') ||
                        document.querySelector('input[placeholder*="Search"]') ||
                        document.querySelector('[aria-label*="Your profile"]') ||
                        document.querySelector('[data-pagelet="LeftRail"]')
                    );
                }""")
                if (c_user or has_feed) and not has_login_form and not has_continue_screen:
                    return True, "OK"

            # Selenium WebDriver instance
            elif hasattr(driver_or_page, "execute_script"):
                curr_url = (driver_or_page.current_url or "").lower()
                if any(k in curr_url for k in ("/checkpoint/", "/identity/", "/two_step_verification/", "/disabled/", "/recover/")):
                    return False, "CHECKPOINT"

                is_checkpoint = driver_or_page.execute_script("""
                    const text = (document.body?.innerText || '').toLowerCase();
                    return (
                        text.includes("confirm you're human") ||
                        text.includes("confirm your identity") ||
                        text.includes("your account has been suspended") ||
                        text.includes("help us confirm it's you") ||
                        text.includes("account disabled")
                    );
                """)
                if is_checkpoint:
                    return False, "CHECKPOINT"

                has_login_form = driver_or_page.execute_script("""
                    return !!(
                        document.querySelector('input[name="email"]') && 
                        document.querySelector('input[name="pass"]')
                    );
                """)
                if has_login_form or "login" in curr_url:
                    return False, "LOGGED_OUT"

                cookies = driver_or_page.get_cookies()
                c_user = any(c.get("name") == "c_user" and c.get("value") for c in cookies)
                has_feed = driver_or_page.execute_script("""
                    return !!(
                        document.querySelector('[role="feed"]') || 
                        document.querySelector('[role="navigation"]') || 
                        document.querySelector('[aria-label*="Facebook"]') ||
                        document.querySelector('input[placeholder*="Search"]') ||
                        document.querySelector('[aria-label*="Your profile"]') ||
                        document.querySelector('[data-pagelet="LeftRail"]')
                    );
                """)
                if (c_user or has_feed) and not has_login_form:
                    return True, "OK"
        except Exception:
            pass
        time.sleep(1.0)

    return False, "TIMEOUT"


# =========================================================================
# 4. EXTRACT FACEBOOK DTSG & SESSIONS
# =========================================================================

def extract_facebook_tokens(driver_or_page: Any) -> Dict[str, str]:
    """Extracts fb_dtsg, c_user, lsd, and cookie header from live browser session."""
    tokens = {
        "c_user": "",
        "fb_dtsg": "",
        "lsd": "",
        "cookie_str": ""
    }
    try:
        if hasattr(driver_or_page, "evaluate"):
            # Extract cookies
            cookies = driver_or_page.context.cookies()
            cookie_pairs = [f"{c.get('name')}={c.get('value')}" for c in cookies if c.get('name') and c.get('value')]
            tokens["cookie_str"] = "; ".join(cookie_pairs)
            for c in cookies:
                if c.get("name") == "c_user":
                    tokens["c_user"] = c.get("value")

            # Extract fb_dtsg & lsd
            js_code = r"""() => {
                let dtsg = '';
                try {
                    dtsg = document.querySelector('[name="fb_dtsg"]')?.value || '';
                } catch(e){}
                if (!dtsg) {
                    try {
                        let m = document.documentElement.innerHTML.match(/["']token["']\s*:\s*["']([^"']{20,})["']/);
                        if (m) dtsg = m[1];
                    } catch(e){}
                }
                if (!dtsg) {
                    try {
                        let m2 = document.documentElement.innerHTML.match(/DTSGInitialData[^{]*{[^}]*["']token["']\s*:\s*["']([^"']+)["']/);
                        if (m2) dtsg = m2[1];
                    } catch(e){}
                }
                let lsd = '';
                try {
                    let lm = document.cookie.match(/lsd=([^;]+)/);
                    if (lm) lsd = lm[1];
                } catch(e){}
                return { dtsg: dtsg, lsd: lsd };
            }"""
            res = driver_or_page.evaluate(js_code)
            if res:
                tokens["fb_dtsg"] = res.get("dtsg", "")
                tokens["lsd"] = res.get("lsd", "")
    except Exception:
        pass

    return tokens


# =========================================================================
# 5. GRAPHQL MUTATION: CREATE FACEBOOK PAGE (PROFILE PLUS)
# =========================================================================

def create_facebook_page_graphql(
    page_name: str,
    tokens: Dict[str, str],
    category_id: str = "180164625353584", # Community / Public Figure
    bio_text: str = ""
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Executes AdditionalProfilePlusCreationMutation via Facebook GraphQL backend.
    Returns: (success: bool, message: str, data: dict)
    """
    c_user = tokens.get("c_user", "")
    fb_dtsg = tokens.get("fb_dtsg", "")
    cookie_str = tokens.get("cookie_str", "")

    if not fb_dtsg or not c_user or not cookie_str:
        return False, "Missing required authentication tokens (fb_dtsg / c_user / cookies)", {}

    url = "https://www.facebook.com/api/graphql/"
    
    # Common doc_ids for AdditionalProfilePlusCreationMutation
    doc_id = "5674061809312154" 

    variables = {
        "input": {
            "name": page_name,
            "bio": bio_text,
            "categories": [category_id],
            "creation_source": "comet",
            "page_referrer": "comet_left_nav",
            "actor_id": c_user,
            "client_mutation_id": str(random.random())
        }
    }

    form_data = {
        "av": c_user,
        "__user": c_user,
        "__a": "1",
        "fb_dtsg": fb_dtsg,
        "fb_api_req_friendly_name": "AdditionalProfilePlusCreationMutation",
        "doc_id": doc_id,
        "variables": json.dumps(variables)
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie_str,
        "Origin": "https://www.facebook.com",
        "Referer": "https://www.facebook.com/pages/creation/",
        "x-fb-friendly-name": "AdditionalProfilePlusCreationMutation"
    }

    try:
        encoded_data = urllib.parse.urlencode(form_data).encode("utf-8")
        req = urllib.request.Request(url, data=encoded_data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_resp = response.read().decode("utf-8")
            # Strip for (;;); if present
            clean_resp = raw_resp.replace("for (;;);", "").strip()
            res_json = json.loads(clean_resp)

            # Check response payload for created page ID
            additional_profile = res_json.get("data", {}).get("additional_profile_plus_create", {})
            created_profile = additional_profile.get("additional_profile", {}) or additional_profile.get("profile", {})
            page_id = created_profile.get("id") or created_profile.get("profile_id")

            if page_id:
                page_link = f"https://www.facebook.com/{page_id}"
                return True, f"Page '{page_name}' created successfully! (ID: {page_id})", {
                    "page_id": page_id,
                    "page_name": page_name,
                    "page_link": page_link,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
            # Error checking
            errors = res_json.get("errors", [])
            err_msg = errors[0].get("message") if errors else "GraphQL mutation response did not contain new page ID"
            return False, err_msg, res_json

    except Exception as e:
        return False, f"Network/API Error: {str(e)}", {}


# =========================================================================
# 6. EXPORT MASTER REPORTS (EXCEL / TXT / CSV)
# =========================================================================

def export_created_pages_report(
    report_items: List[Dict[str, Any]],
    target_filepath: str,
    format_type: str = "xlsx"
) -> Tuple[bool, str]:
    """
    Exports structured report of all processed profiles in Facebook Bulk Page Creator
    into an Excel workbook with two dedicated tabs:
      - Tab 1: 'Success' (Profiles where page was successfully created)
      - Tab 2: 'Fail' (Profiles where page creation failed)
    """
    if not report_items:
        return False, "No data to export."

    p = Path(target_filepath)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Separate items into Success and Fail
    success_items = []
    fail_items = []

    for item in report_items:
        status_val = str(item.get("status", "")).strip().lower()
        if "fail" in status_val or "error" in status_val or "reject" in status_val:
            fail_items.append(item)
        else:
            success_items.append(item)

    try:
        if format_type.lower() == "xlsx" and OPENPYXL_AVAILABLE:
            wb = openpyxl.Workbook()

            # -------------------------------------------------------------
            # TAB 1: SUCCESS
            # -------------------------------------------------------------
            ws_success = wb.active
            ws_success.title = "Success"

            headers_success = [
                "Profile Number",
                "UID",
                "Password",
                "2FA Secret",
                "Cookie",
                "Status",
                "Page Name",
                "Page URL"
            ]
            ws_success.append(headers_success)

            # Success Header Styling: Dark Emerald Green & Bold White
            h_success_fill = PatternFill(start_color="064e3b", end_color="064e3b", fill_type="solid")
            h_success_font = Font(name="Segoe UI", size=11, bold=True, color="ffffff")
            ws_success.row_dimensions[1].height = 26

            for col_idx in range(1, len(headers_success) + 1):
                c = ws_success.cell(row=1, column=col_idx)
                c.fill = h_success_fill
                c.font = h_success_font
                c.alignment = Alignment(horizontal="center", vertical="center")

            cell_font_normal = Font(name="Segoe UI", size=10, color="1e293b")
            cell_font_bold = Font(name="Segoe UI", size=10, bold=True, color="0f172a")
            stat_success_fill = PatternFill(start_color="dcfce7", end_color="dcfce7", fill_type="solid")
            stat_success_font = Font(name="Segoe UI", size=10, bold=True, color="15803d")
            link_font = Font(name="Segoe UI", size=10, color="0284c7", underline="single")

            for item in success_items:
                prof_num = str(item.get("profile_number") or item.get("number") or item.get("name") or "").strip()
                uid = str(item.get("uid") or item.get("creator_uid") or item.get("fb_uid") or "").strip()
                pwd = str(item.get("password") or item.get("fb_pass") or "").strip()
                secret_2fa = str(item.get("secret_2fa") or item.get("fb_2fa") or item.get("two_factor") or item.get("two_factor_secret") or item.get("2fa") or "").strip()
                cookie = str(item.get("cookie") or item.get("cookies") or "").strip()
                p_name = str(item.get("page_name") or "").strip()

                p_id = str(item.get("page_id") or "").strip()
                p_link = str(item.get("page_url") or item.get("page_link") or "").strip()
                if p_id and p_id.isdigit() and (not p_link or p_link.endswith("/pages/")):
                    p_link = f"https://www.facebook.com/profile.php?id={p_id}"

                row_vals = [
                    prof_num,
                    uid,
                    pwd,
                    secret_2fa,
                    cookie,
                    "Success",
                    p_name,
                    p_link
                ]
                ws_success.append(row_vals)
                row_idx = ws_success.max_row
                ws_success.row_dimensions[row_idx].height = 20

                # Format cells
                ws_success.cell(row=row_idx, column=1).font = cell_font_bold
                ws_success.cell(row=row_idx, column=1).alignment = Alignment(horizontal="center", vertical="center")

                c_uid = ws_success.cell(row=row_idx, column=2)
                c_uid.number_format = "@"
                c_uid.font = cell_font_normal
                c_uid.alignment = Alignment(horizontal="center", vertical="center")

                ws_success.cell(row=row_idx, column=3).font = cell_font_normal
                ws_success.cell(row=row_idx, column=3).alignment = Alignment(horizontal="left", vertical="center")

                ws_success.cell(row=row_idx, column=4).font = cell_font_normal
                ws_success.cell(row=row_idx, column=4).alignment = Alignment(horizontal="left", vertical="center")

                ws_success.cell(row=row_idx, column=5).font = cell_font_normal
                ws_success.cell(row=row_idx, column=5).alignment = Alignment(horizontal="left", vertical="center")

                c_stat = ws_success.cell(row=row_idx, column=6)
                c_stat.fill = stat_success_fill
                c_stat.font = stat_success_font
                c_stat.alignment = Alignment(horizontal="center", vertical="center")

                ws_success.cell(row=row_idx, column=7).font = cell_font_bold
                ws_success.cell(row=row_idx, column=7).alignment = Alignment(horizontal="left", vertical="center")

                c_url = ws_success.cell(row=row_idx, column=8)
                c_url.alignment = Alignment(horizontal="left", vertical="center")
                if p_link and p_link.startswith("http"):
                    c_url.hyperlink = p_link
                    c_url.font = link_font
                else:
                    c_url.font = cell_font_normal

            ws_success.freeze_panes = "A2"

            # Auto Column Widths for Success
            for col in ws_success.columns:
                col_letter = get_column_letter(col[0].column)
                if col_letter == "E":  # Cookie
                    ws_success.column_dimensions[col_letter].width = 30
                elif col_letter in ("C", "D"):  # Password, 2FA
                    ws_success.column_dimensions[col_letter].width = 20
                elif col_letter == "H":  # Page URL
                    ws_success.column_dimensions[col_letter].width = 45
                else:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    ws_success.column_dimensions[col_letter].width = min(max(max_len + 3, 13), 40)

            # -------------------------------------------------------------
            # TAB 2: FAIL
            # -------------------------------------------------------------
            ws_fail = wb.create_sheet(title="Fail")

            headers_fail = [
                "Profile Number",
                "UID",
                "Password",
                "2FA Secret",
                "Cookie",
                "Status",
                "Failure Reason"
            ]
            ws_fail.append(headers_fail)

            # Fail Header Styling: Dark Crimson Red & Bold White
            h_fail_fill = PatternFill(start_color="881337", end_color="881337", fill_type="solid")
            h_fail_font = Font(name="Segoe UI", size=11, bold=True, color="ffffff")
            ws_fail.row_dimensions[1].height = 26

            for col_idx in range(1, len(headers_fail) + 1):
                c = ws_fail.cell(row=1, column=col_idx)
                c.fill = h_fail_fill
                c.font = h_fail_font
                c.alignment = Alignment(horizontal="center", vertical="center")

            stat_fail_fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")
            stat_fail_font = Font(name="Segoe UI", size=10, bold=True, color="991b1b")
            reason_font = Font(name="Segoe UI", size=9.5, color="7f1d1d")

            for item in fail_items:
                prof_num = str(item.get("profile_number") or item.get("number") or item.get("name") or "").strip()
                uid = str(item.get("uid") or item.get("creator_uid") or item.get("fb_uid") or "").strip()
                pwd = str(item.get("password") or item.get("fb_pass") or "").strip()
                secret_2fa = str(item.get("secret_2fa") or item.get("fb_2fa") or item.get("two_factor") or item.get("two_factor_secret") or item.get("2fa") or "").strip()
                cookie = str(item.get("cookie") or item.get("cookies") or "").strip()
                reason = str(item.get("failure_reason") or "Failed to create page").strip()

                row_vals = [
                    prof_num,
                    uid,
                    pwd,
                    secret_2fa,
                    cookie,
                    "Fail",
                    reason
                ]
                ws_fail.append(row_vals)
                row_idx = ws_fail.max_row
                ws_fail.row_dimensions[row_idx].height = 20

                # Format cells
                ws_fail.cell(row=row_idx, column=1).font = cell_font_bold
                ws_fail.cell(row=row_idx, column=1).alignment = Alignment(horizontal="center", vertical="center")

                c_uid = ws_fail.cell(row=row_idx, column=2)
                c_uid.number_format = "@"
                c_uid.font = cell_font_normal
                c_uid.alignment = Alignment(horizontal="center", vertical="center")

                ws_fail.cell(row=row_idx, column=3).font = cell_font_normal
                ws_fail.cell(row=row_idx, column=3).alignment = Alignment(horizontal="left", vertical="center")

                ws_fail.cell(row=row_idx, column=4).font = cell_font_normal
                ws_fail.cell(row=row_idx, column=4).alignment = Alignment(horizontal="left", vertical="center")

                ws_fail.cell(row=row_idx, column=5).font = cell_font_normal
                ws_fail.cell(row=row_idx, column=5).alignment = Alignment(horizontal="left", vertical="center")

                c_stat = ws_fail.cell(row=row_idx, column=6)
                c_stat.fill = stat_fail_fill
                c_stat.font = stat_fail_font
                c_stat.alignment = Alignment(horizontal="center", vertical="center")

                c_reason = ws_fail.cell(row=row_idx, column=7)
                c_reason.font = reason_font
                c_reason.alignment = Alignment(horizontal="left", vertical="center")

            ws_fail.freeze_panes = "A2"

            # Auto Column Widths for Fail
            for col in ws_fail.columns:
                col_letter = get_column_letter(col[0].column)
                if col_letter == "E":  # Cookie
                    ws_fail.column_dimensions[col_letter].width = 30
                elif col_letter in ("C", "D"):  # Password, 2FA
                    ws_fail.column_dimensions[col_letter].width = 20
                elif col_letter == "G":  # Failure Reason
                    ws_fail.column_dimensions[col_letter].width = 45
                else:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    ws_fail.column_dimensions[col_letter].width = min(max(max_len + 3, 13), 40)

            try:
                wb.save(target_filepath)
            except PermissionError:
                alt_p = target_filepath.replace(".xlsx", "_live_update.xlsx")
                try:
                    wb.save(alt_p)
                    return True, str(Path(alt_p).resolve())
                except Exception:
                    pass
            return True, str(p.resolve())
        else:
            import csv
            with open(target_filepath, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Profile Number", "UID", "Password", "2FA Secret", "Cookie", "Status", "Page Name", "Page URL", "Failure Reason"
                ])
                for item in report_items:
                    stat = str(item.get("status", "")).strip().lower()
                    is_fail = "fail" in stat or "error" in stat or "reject" in stat
                    prof_num = str(item.get("profile_number") or item.get("number") or item.get("name") or "").strip()
                    uid = str(item.get("uid") or item.get("creator_uid") or item.get("fb_uid") or "").strip()
                    pwd = str(item.get("password") or item.get("fb_pass") or "").strip()
                    secret_2fa = str(item.get("secret_2fa") or item.get("fb_2fa") or item.get("two_factor") or item.get("two_factor_secret") or item.get("2fa") or "").strip()
                    cookie = str(item.get("cookie") or item.get("cookies") or "").strip()
                    p_name = str(item.get("page_name") or "").strip() if not is_fail else ""
                    p_link = str(item.get("page_url") or item.get("page_link") or "").strip() if not is_fail else ""
                    reason = str(item.get("failure_reason") or "").strip()
                    writer.writerow([
                        prof_num, uid, pwd, secret_2fa, cookie, "Fail" if is_fail else "Success", p_name, p_link, reason
                    ])
            return True, str(p.resolve())
    except Exception as e:
        return False, f"Failed to export: {str(e)}"


# =========================================================================
# 7. SWITCH FACEBOOK ACTIVE SESSION TO CREATED PAGE / PROFILE PLUS
# =========================================================================

def switch_facebook_to_page_profile(
    page: Any, 
    page_id: str, 
    page_name: str = "", 
    timeout_sec: float = 20.0
) -> Tuple[bool, str]:
    """
    Automates switching Facebook active session from personal account to the newly created Page / Profile Plus.
    Follows the 2-step Facebook Switch Flow:
      1. Navigate to https://web.facebook.com/profile.php?id={page_id}
      2. Wait 4-5 seconds for Facebook's 'Switch Now' banner to render.
      3. Click [ Switch Now ] button.
      4. Wait 4-5 seconds for 'Welcome to your new Page!' modal to appear.
      5. Click [ Use Page ] button.
      6. Wait 3-4 seconds to ensure Facebook persists the switched session into cookies.
    """
    if not page:
        return False, "Browser page handle is invalid"

    try:
        # Step 1: Navigate directly to the Page profile URL
        if page_id and str(page_id).isdigit():
            target_url = f"https://web.facebook.com/profile.php?id={page_id}"
        else:
            target_url = "https://web.facebook.com/pages/"

        curr_url = page.url or ""
        if page_id and str(page_id) not in curr_url:
            page.goto(target_url, timeout=35000, wait_until="domcontentloaded")
            # Wait 4.5 seconds as requested by user for Facebook UI to initialize
            time.sleep(4.5)
        else:
            time.sleep(3.0)

        switched_step1 = False

        # Step 2: Click "Switch Now" button on the Page banner (Image 1)
        switch_selectors = [
            'div[role="button"]:has-text("Switch Now")',
            'div[role="button"]:has-text("Switch now")',
            'div[aria-label*="Switch Now" i]',
            'div[aria-label*="Switch into" i]',
            'div[aria-label*="Switch to" i]',
            'div[aria-label*="Switch" i][role="button"]',
            'button:has-text("Switch Now")',
            'button:has-text("Switch now")',
            'button:has-text("Switch")',
            'div[role="button"]:has-text("Switch")',
            'div[role="button"]:has-text("সুইচ করুন")',
            'div[role="button"]:has-text("সুইচ")',
            'div[aria-label*="সুইচ করুন" i]',
            'div[aria-label*="সুইচ" i]'
        ]

        for sel in switch_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    switched_step1 = True
                    break
            except Exception:
                continue

        # Stealth JS fallback for Step 1
        if not switched_step1:
            try:
                switched_step1 = page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('div[role="button"], button, a, div[aria-label]'));
                    for (const b of btns) {
                        const txt = (b.innerText || b.textContent || b.getAttribute('aria-label') || '').trim().toLowerCase();
                        if (txt === 'switch now' || txt.startsWith('switch into') || txt === 'switch' || txt === 'সুইচ করুন' || txt === 'সুইচ') {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
            except Exception:
                pass

        # If Step 1 clicked or even if popup was auto-triggered, wait 4.5 seconds for "Welcome to your new Page!" modal (Image 2)
        time.sleep(4.5)

        # Step 3: Click "Use Page" button on "Welcome to your new Page!" modal (Image 2)
        use_page_selectors = [
            'div[role="button"]:has-text("Use Page")',
            'div[role="button"]:has-text("Use page")',
            'div[aria-label*="Use Page" i]',
            'button:has-text("Use Page")',
            'button:has-text("Use page")',
            'div[role="button"]:has-text("পেজ ব্যবহার করুন")',
            'div[role="button"]:has-text("Take tour")',
            'div[role="button"]:has-text("Not now")',
            'div[aria-label="Close" i][role="button"]'
        ]

        clicked_modal = False
        for sel in use_page_selectors:
            try:
                m_btn = page.query_selector(sel)
                if m_btn and m_btn.is_visible():
                    m_btn.click()
                    clicked_modal = True
                    break
            except Exception:
                continue

        # Stealth JS fallback for Step 2
        if not clicked_modal:
            try:
                clicked_modal = page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('div[role="button"], button, a, div[aria-label]'));
                    for (const b of btns) {
                        const txt = (b.innerText || b.textContent || b.getAttribute('aria-label') || '').trim().toLowerCase();
                        if (txt === 'use page' || txt === 'পেজ ব্যবহার করুন' || txt === 'take tour' || txt === 'not now') {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
            except Exception:
                pass

        if switched_step1 or clicked_modal:
            time.sleep(3.5)
            return True, "Successfully switched to Page session via [Switch Now] -> [Use Page] flow!"

        # Step 4: Top-Right Profile Switcher Menu fallback if banner wasn't present
        try:
            profile_btn = (
                page.query_selector('div[aria-label="Your profile" i]') or
                page.query_selector('div[aria-label="আপনার প্রোফাইল" i]') or
                page.query_selector('svg[aria-label="Your profile" i]') or
                page.query_selector('div[role="button"][aria-label*="profile" i]')
            )
            if profile_btn and profile_btn.is_visible():
                profile_btn.click()
                time.sleep(2.0)

                # Look for "See all profiles"
                see_all = (
                    page.query_selector('div[role="button"]:has-text("See all profiles")') or
                    page.query_selector('div:has-text("See all profiles")') or
                    page.query_selector('div:has-text("সব প্রোফাইল দেখুন")') or
                    page.query_selector('div[aria-label*="See all profiles" i]')
                )
                if see_all and see_all.is_visible():
                    see_all.click()
                    time.sleep(2.0)

                # Find Page entry
                page_candidates = []
                if page_name:
                    page_candidates.append(f'div[role="button"]:has-text("{page_name}")')
                    page_candidates.append(f'div[aria-label*="{page_name}" i]')
                if page_id:
                    page_candidates.append(f'div[aria-label*="{page_id}"]')
                    page_candidates.append(f'a[href*="{page_id}"]')

                for p_sel in page_candidates:
                    try:
                        p_el = page.query_selector(p_sel)
                        if p_el and p_el.is_visible():
                            p_el.click()
                            time.sleep(4.0)

                            # Handle any "Use Page" / "Welcome to your new Page!" popup
                            for sel in use_page_selectors:
                                try:
                                    m_btn = page.query_selector(sel)
                                    if m_btn and m_btn.is_visible():
                                        m_btn.click()
                                        break
                                except Exception:
                                    pass

                            time.sleep(3.0)
                            return True, "Switched via Top-Right Profile Switcher menu"
                    except Exception:
                        pass
        except Exception:
            pass

        return False, "Switch button not found or already in Page session"

    except Exception as ex:
        return False, f"Exception during switch: {str(ex)}"
