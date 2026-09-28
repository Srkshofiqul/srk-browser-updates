import os
import sys
import time
import random
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

# Playwright imports with safe fallback
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


SUPPORTED_LOCALES = {
    "en_US": "English (US)",
    "en_GB": "English (UK)",
    "es_LA": "Español (Latinoamérica)",
    "fr_FR": "Français (France)",
    "pt_BR": "Português (Brasil)",
    "bn_IN": "বাংলা (Bengali)",
    "ar_AR": "العربية (Arabic)",
    "hi_IN": "हिन्दी (Hindi)"
}


import re

def execute_language_conversion(
    user_data_dir: str,
    target_locale: str = "en_US",
    delay_sec: float = 0.0,
    headless: bool = True,
    log_func: Optional[Any] = None,
    profile_data: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Executes 1-click language conversion via Facebook's internal GraphQL API:
    Doc ID: 29960775910235124
    
    1. Connects to live running browser directly via Smart CDP (or launches if closed).
    2. Dispatches GraphQL language change mutation with DTSG token.
    3. Reloads the live Facebook tab in English.
    4. Verifies response and returns (success: bool, message: str).
    """
    def log(m: str):
        if log_func:
            log_func(m)
        else:
            print(m)

    if not sync_playwright:
        return False, "Playwright library is not installed in the environment."

    if not user_data_dir or not Path(user_data_dir).exists():
        return False, f"Profile user data directory not found: {user_data_dir}"

    locale_name = SUPPORTED_LOCALES.get(target_locale, target_locale)
    log(f"🌐 [Language Converter] Target Locale: {locale_name} ({target_locale})")

    # Anti-bot random delay
    if delay_sec > 0:
        actual_delay = round(random.uniform(max(0.2, delay_sec - 0.2), delay_sec + 0.4), 1)
        log(f"⏳ Anti-bot human delay: waiting {actual_delay}s...")
        time.sleep(actual_delay)

    # Calculate deterministic CDP port matching srkBrowser core browser manager
    raw_num = ""
    if profile_data:
        raw_num = str(profile_data.get("number") or profile_data.get("name") or "").strip()
    if not raw_num:
        m = re.search(r'Profile(\d+)', str(user_data_dir), re.IGNORECASE)
        raw_num = m.group(1) if m else "1"

    num_clean = re.sub(r"\D", "", raw_num)
    n_val = int(num_clean) if num_clean else 1
    cdp_port = 9200 + (n_val % 500)
    cdp_url = f"http://127.0.0.1:{cdp_port}"

    # Locate Chromium executable
    root_dir = Path(__file__).resolve().parent.parent.parent
    chromium_candidates = [
        root_dir / "chromium" / "chrome.exe",
        root_dir / "01_Main_Software" / "chromium" / "chrome.exe",
        Path.home() / "AppData" / "Local" / "ms-playwright" / "chromium" / "chrome-win" / "chrome.exe"
    ]
    exec_path = None
    for cand in chromium_candidates:
        if cand.exists():
            exec_path = str(cand)
            break

    try:
        with sync_playwright() as p:
            context = None
            browser = None
            connected_via_cdp = False

            # 1. Smart CDP: Attempt connecting to the ALREADY RUNNING browser session
            try:
                browser = p.chromium.connect_over_cdp(cdp_url, timeout=3000)
                if browser and browser.contexts:
                    context = browser.contexts[0]
                    connected_via_cdp = True
                    log(f"🔗 Connected to live browser for Profile #{n_val} on Port {cdp_port}!")
            except Exception:
                connected_via_cdp = False

            # 2. Fallback: Launch standalone persistent context if browser is not open
            if not context:
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check",
                    "--no-first-run",
                    "--disable-infobars",
                    "--disable-notifications"
                ]
                log("🚀 Launching profile browser context...")
                launch_kwargs = {
                    "user_data_dir": str(user_data_dir),
                    "headless": headless,
                    "args": launch_args
                }
                if exec_path:
                    launch_kwargs["executable_path"] = exec_path

                context = p.chromium.launch_persistent_context(**launch_kwargs)

            # 3. Resolve active Facebook page
            page = None
            if connected_via_cdp:
                for pg in context.pages:
                    try:
                        if "facebook.com" in (pg.url or "").lower():
                            page = pg
                            break
                    except Exception:
                        pass
                if not page:
                    page = context.new_page()
                    page.goto("https://web.facebook.com/", timeout=30000, wait_until="domcontentloaded")
                else:
                    page.bring_to_front()
            else:
                page = context.pages[0] if context.pages else context.new_page()
                curr_url = page.url or ""
                if "facebook.com" not in curr_url:
                    log("🌐 Navigating to Facebook...")
                    try:
                        page.goto("https://web.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                        time.sleep(1.5)
                    except Exception as n_err:
                        log(f"⚠️ Navigation warning: {n_err}")

            # Execute GraphQL Language Change Mutation
            log("⚡ Dispatching GraphQL Language Change Mutation...")
            res = page.evaluate(r"""async (targetLocale) => {
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
                        return { success: false, reason: "DTSG session token or UID not found in active page." };
                    }

                    const params = new URLSearchParams({
                        fb_dtsg: token,
                        __a: "1",
                        __user: uid,
                        doc_id: "29960775910235124",
                        variables: JSON.stringify({
                            locale: targetLocale,
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
            }""", target_locale)

            # If successful and live browser is running, reload the tab to immediately reflect English UI
            if res and res.get("success"):
                if connected_via_cdp and page:
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=12000)
                    except Exception:
                        try:
                            page.evaluate("location.reload()")
                        except Exception:
                            pass

            if not connected_via_cdp:
                try:
                    context.close()
                except Exception:
                    pass

            if res and res.get("success"):
                msg = f"Language successfully converted to {locale_name} ({target_locale})!"
                log(f"✅ {msg}")
                return True, msg
            else:
                reason = res.get("reason") or res.get("error") or (f"HTTP {res.get('status')}" if res else "Unknown GraphQL error")
                msg = f"Could not convert language: {reason}"
                log(f"❌ {msg}")
                return False, msg

    except Exception as ex:
        err_msg = f"Language conversion execution error: {ex}"
        log(f"❌ {err_msg}")
        return False, err_msg
