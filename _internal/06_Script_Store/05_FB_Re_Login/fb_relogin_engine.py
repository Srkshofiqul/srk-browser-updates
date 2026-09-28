# -*- coding: utf-8 -*-
"""
srkBrowser FB 1-Click Auto Re-login Engine (FBRL)
Smart live-browser Facebook session recovery & re-authentication tool.
- Inspects active live browser tab first
- Skips cookie re-injection if Continue screen is already visible
- Submits password with human typing simulation
- Solves 2FA TOTP challenges automatically
- Persists fresh session cookies to database
"""

import os
import sys
import time
import re
import hmac
import hashlib
import struct
import base64
import random
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


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


def parse_cookie_string(raw_cookie: str) -> List[Dict[str, Any]]:
    """Parses raw cookie string (name=val; name2=val2) into Playwright cookie list."""
    results = []
    if not raw_cookie:
        return results
    for piece in str(raw_cookie).split(";"):
        piece = piece.strip()
        if "=" in piece:
            c_name, c_val = piece.split("=", 1)
            c_name = c_name.strip()
            c_val = c_val.strip()
            if c_name:
                results.append({
                    "name": c_name,
                    "value": c_val,
                    "domain": ".facebook.com",
                    "path": "/"
                })
    return results


def get_cdp_port_for_profile(profile_data: Optional[Dict[str, Any]] = None, user_data_dir: Optional[str] = None) -> int:
    """Calculates collision-free CDP port matching srkBrowser core architecture."""
    raw_num = ""
    if profile_data:
        raw_num = str(profile_data.get("number") or profile_data.get("name") or "").strip()
    if not raw_num and user_data_dir:
        m = re.search(r'Profile(\d+)', str(user_data_dir), re.IGNORECASE)
        raw_num = m.group(1) if m else "1"
    num_clean = re.sub(r"\D", "", raw_num)
    n_val = int(num_clean) if num_clean else 1
    return 9200 + (n_val % 500)


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
                        if not continue_btn.is_visible(timeout=300):
                            return "LOGGED_IN", f"Authenticated (c_user={ck.get('value')})"
        except Exception:
            pass

        return "UNKNOWN_OR_LOADING", "Page loading or unrecognized screen"
    except Exception as err:
        return "ERROR", str(err)


def execute_relogin(
    profile_data: Dict[str, Any],
    profile_mgr: Optional[Any] = None,
    log_func: Optional[Any] = None,
    user_data_dir: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Executes 1-Click FB Auto Re-login (FBRL).
    Connects to live browser tab over CDP.
    Directly handles Continue Screen without clearing cookies if already present.
    """
    def log(m: str):
        if log_func:
            log_func(m)
        else:
            print(m)

    if not sync_playwright:
        return False, "Playwright library is not available in the environment."

    pname = profile_data.get("name", "Profile")
    pnum = profile_data.get("number", "01")
    profile_id = profile_data.get("id") or str(profile_data.get("number", "1"))

    # Extract credentials
    email = str(profile_data.get("fb_uid") or profile_data.get("email") or profile_data.get("uid") or profile_data.get("username") or "").strip()
    if not email and "fb_" in str(pname).lower():
        m = re.search(r"\d{10,20}", str(pname))
        if m:
            email = m.group(0)
    password = str(profile_data.get("fb_pass") or profile_data.get("password") or "").strip()
    two_factor = str(profile_data.get("fb_2fa") or profile_data.get("2fa_secret") or profile_data.get("two_factor") or profile_data.get("secret_2fa") or "").strip()
    cookies_raw = profile_data.get("cookies") or profile_data.get("fb_cookie") or profile_data.get("cookie") or ""

    # Parse credentials from notes if present
    notes = str(profile_data.get("notes") or "").strip()
    if notes and ("|" in notes or ":" in notes) and (not email or not password):
        parts = [p.strip() for p in (notes.split("|") if "|" in notes else notes.split(":"))]
        if len(parts) >= 2:
            if not email: email = parts[0]
            if not password: password = parts[1]
            if len(parts) >= 3 and not two_factor: two_factor = parts[2]
            if len(parts) >= 4 and not cookies_raw: cookies_raw = parts[3]

    log(f"🔑 [FBRL] Starting 1-Click Auto Re-login for {pname} (#{pnum})...")

    # Determine CDP connection port
    cdp_port = get_cdp_port_for_profile(profile_data, user_data_dir)
    cdp_url = f"http://127.0.0.1:{cdp_port}"

    pw = sync_playwright().start()
    browser_cdp = None
    context = None

    # Connect to live running browser (retrying over CDP)
    log(f"  🔌 Connecting to live browser on port {cdp_port}...")
    for _ in range(8):
        try:
            browser_cdp = pw.chromium.connect_over_cdp(cdp_url)
            if browser_cdp and browser_cdp.contexts:
                context = browser_cdp.contexts[0]
                break
        except Exception:
            time.sleep(0.6)

    if not context:
        log(f"  ⚠️ Browser not detected on port {cdp_port}. Please open the profile first.")
        try: pw.stop()
        except Exception: pass
        return False, f"Browser window for #{pnum} is not currently open."

    try:
        # Find active tab
        page = context.pages[0] if context.pages else context.new_page()

        # Bring window to front
        try: page.bring_to_front()
        except Exception: pass

        curr_url = page.url.lower()
        log(f"  📄 Current Tab URL: {curr_url}")

        # STEP 1: SMART STATE FIRST INSPECTION
        # Check if tab is ALREADY on Facebook
        is_on_fb = "facebook.com" in curr_url
        current_state = "NOT_ON_FB"
        state_desc = ""

        if is_on_fb:
            current_state, state_desc = detect_facebook_tab_state(page)
            log(f"  🔍 Live Tab State: [{current_state}] - {state_desc}")

        # -------------------------------------------------------------
        # CASE A: CURRENT TAB ALREADY HAS CONTINUE SCREEN (User's specific requirement!)
        # DO NOT re-inject cookies! DO NOT reload page! Directly submit password!
        # -------------------------------------------------------------
        if current_state == "CONTINUE_SCREEN":
            log("  🎯 Facebook Continue Screen detected! Directly submitting password...")
            
            # 1. Click Continue button if visible
            cont_btn = page.locator("div[role='button']:has-text('Continue'), button:has-text('Continue'), div[role='button']:has-text('Log In As'), div[role='button']:has-text('Continue as')").first
            if cont_btn.is_visible(timeout=1000):
                log("  👉 Clicking 'Continue' button...")
                cont_btn.click()
                time.sleep(1.2)

            # 2. Enter Password
            pass_selectors = [
                "input#pass",
                "input[name='pass']",
                "input[type='password']"
            ]
            pass_entered = False
            for sel in pass_selectors:
                inp = page.locator(sel).first
                if inp.is_visible(timeout=1500):
                    log("  ⌨️ Typing password into Continue Screen...")
                    human_type(inp, password, clear_first=True)
                    pass_entered = True
                    break

            if pass_entered:
                time.sleep(0.5)
                # Click Submit or press Enter
                sub_btn = page.locator("button[name='login'], button#loginbutton, button[type='submit'], div[role='button']:has-text('Log In')").first
                if sub_btn.is_visible(timeout=1000):
                    sub_btn.click()
                else:
                    page.keyboard.press("Enter")
                
                log("  ⏳ Waiting for authentication response...")
                time.sleep(3.5)

        # -------------------------------------------------------------
        # CASE B: TAB IS NOT ON FB OR ON OTHER PAGE -> Navigate & Cookie Re-Auth
        # -------------------------------------------------------------
        elif current_state not in ("LOGGED_IN", "2FA_REQUIRED"):
            if not is_on_fb or "login" in curr_url or current_state == "LOGIN_FORM_READY":
                # Inject cookies if available
                if cookies_raw:
                    cks = parse_cookie_string(str(cookies_raw))
                    if cks:
                        log(f"  🍪 Injecting {len(cks)} saved session cookies...")
                        try:
                            context.add_cookies(cks)
                        except Exception as ce:
                            log(f"  ⚠️ Cookie injection note: {ce}")

                log("  🌐 Opening facebook.com...")
                try:
                    page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                except Exception as ne:
                    log(f"  ⚠️ Navigation note: {ne}")

                time.sleep(2.5)

                # Re-check state after navigation
                current_state, state_desc = detect_facebook_tab_state(page)
                log(f"  🔍 Post-Navigation State: [{current_state}] - {state_desc}")

                # If Continue screen appeared after navigation
                if current_state == "CONTINUE_SCREEN":
                    cont_btn = page.locator("div[role='button']:has-text('Continue'), button:has-text('Continue')").first
                    if cont_btn.is_visible(timeout=1000):
                        cont_btn.click()
                        time.sleep(1.0)
                    for sel in ["input#pass", "input[name='pass']", "input[type='password']"]:
                        inp = page.locator(sel).first
                        if inp.is_visible(timeout=1200):
                            log("  ⌨️ Typing password into Continue Screen...")
                            human_type(inp, password, clear_first=True)
                            page.keyboard.press("Enter")
                            time.sleep(3.0)
                            break

                # If standard Login Form is ready
                elif current_state == "LOGIN_FORM_READY" and email and password:
                    log(f"  🔑 Entering UID [{email[:15]}...] and Password...")
                    e_inp = page.locator("input#email, input[name='email']").first
                    if e_inp.is_visible(timeout=1500):
                        human_type(e_inp, email, clear_first=True)
                    time.sleep(0.5)
                    p_inp = page.locator("input#pass, input[name='pass'], input[type='password']").first
                    if p_inp.is_visible(timeout=1500):
                        human_type(p_inp, password, clear_first=True)
                    time.sleep(0.6)
                    page.keyboard.press("Enter")
                    time.sleep(3.5)

        # -------------------------------------------------------------
        # STEP 2: 2FA TOTP AUTO-SOLVER CHECK
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
                        time.sleep(0.6)
                        page.keyboard.press("Enter")
                        time.sleep(3.0)

                        # Check for Trust This Device / Save Browser button
                        for btn_text in ["Save Browser", "Trust", "Continue", "Don't Save", "Remember"]:
                            btn = page.locator(f"button:has-text('{btn_text}'), div[role='button']:has-text('{btn_text}')").first
                            if btn.is_visible(timeout=1000):
                                btn.click()
                                time.sleep(1.5)
                                break
            else:
                log("  ⚠️ 2FA required by Facebook, but no 2FA Secret Key is configured for this profile.")

        # -------------------------------------------------------------
        # STEP 3: FINAL VERIFICATION & FRESH COOKIE PERSISTENCE
        # -------------------------------------------------------------
        time.sleep(2.0)
        current_state, state_desc = detect_facebook_tab_state(page)
        log(f"  🏁 Final Verification State: [{current_state}] - {state_desc}")

        if current_state == "LOGGED_IN":
            # Extract fresh cookies from active session
            fresh_cookies = context.cookies()
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

                # Update Chromium SQLite cookies and extension injector
                try:
                    p_folder = None
                    if profile_mgr and hasattr(profile_mgr, "get_profile_folder"):
                        p_folder = profile_mgr.get_profile_folder(profile_id)
                    elif user_data_dir:
                        p_folder = Path(user_data_dir)

                    if p_folder and p_folder.exists():
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

            return True, f"✅ Re-login SUCCESSFUL for [{pname}]! Active Facebook session restored and cookies saved."

        elif current_state == "ON_CHECKPOINT":
            return False, f"🚨 Account on Security Checkpoint ({state_desc}). Action required on phone or browser."

        elif current_state == "CONTINUE_SCREEN":
            return False, f"❌ Incorrect Password. Facebook rejected the credentials on Continue screen."

        else:
            return False, f"⚠️ Re-login incomplete ({state_desc}). Please check browser screen."

    except Exception as run_err:
        log(f"  ❌ Re-login Exception: {run_err}")
        return False, f"Re-login Execution Error: {run_err}"


def launch_ui(profile_mgr=None, parent=None, profile_data=None, **kwargs):
    """Entry point when executed from profile card or scripts manager."""
    if profile_data:
        return execute_relogin(profile_data, profile_mgr=profile_mgr)
    return False, "No profile specified."


def main(profile_mgr=None, parent=None, profile_data=None, **kwargs):
    return launch_ui(profile_mgr=profile_mgr, parent=parent, profile_data=profile_data, **kwargs)
