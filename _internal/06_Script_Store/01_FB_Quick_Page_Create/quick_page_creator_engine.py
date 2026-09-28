import os
import sys
import time
import random
import re
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from playwright.sync_api import sync_playwright

INJECT_SCRIPT_PATH = Path(__file__).resolve().parent / "quick_page_creator_inject.js"
INJECT_SCRIPT_CODE = ""
if INJECT_SCRIPT_PATH.exists():
    try:
        with open(INJECT_SCRIPT_PATH, "r", encoding="utf-8") as f:
            INJECT_SCRIPT_CODE = f.read()
    except Exception:
        INJECT_SCRIPT_CODE = ""


BRAND_PREFIXES = [
    "Tech", "Digital", "Smart", "Creative", "Prime", "Apex", "Global",
    "Elite", "NextGen", "Nova", "Vibe", "Alpha", "Hyper", "Zenith", "Ultra",
    "Future", "Epic", "Pro", "Pulse", "Cyber", "Matrix", "Fusion", "Nexus"
]

BRAND_SUFFIXES = [
    "Hub", "Studio", "Media", "Lab", "Network", "World", "Zone", "Station",
    "Point", "Spot", "Club", "Collective", "Space", "Forge", "Sphere", "HQ",
    "Solutions", "Arena", "Dynamics", "Vision", "Nexus", "Official"
]


def generate_random_page_name(profile_data: Optional[Dict[str, Any]] = None) -> str:
    """Generates a stylish, natural-sounding Facebook Page name."""
    if profile_data:
        prof_name = str(profile_data.get("name", "")).strip()
        num_str = str(profile_data.get("number", "")).strip()
        if prof_name.startswith("FB_") and len(prof_name) > 6:
            uid_tail = prof_name[-4:]
            return f"{random.choice(BRAND_PREFIXES)} {random.choice(BRAND_SUFFIXES)} {uid_tail}"
        elif num_str:
            return f"{random.choice(BRAND_PREFIXES)} {random.choice(BRAND_SUFFIXES)} {num_str}"
        elif prof_name:
            return f"{prof_name} {random.choice(BRAND_SUFFIXES)}"

    return f"{random.choice(BRAND_PREFIXES)} {random.choice(BRAND_SUFFIXES)} {random.randint(10, 999)}"


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
            if btn.is_visible(timeout=300):
                btn.click()
                time.sleep(0.2)
        except Exception:
            pass


def execute_quick_page_creation(
    user_data_dir: str,
    target_page_name: str,
    category_id: str = "2347428775505624",
    category_name: str = "Digital Creator",
    headless: bool = False,
    chrome_exe: Optional[str] = None,
    profile_data: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str, str, str, str]:
    """
    Executes fast 1-click Facebook Page Creation on a single profile.
    Automatically detects if browser is already open and attaches directly via Smart CDP!
    Returns: (success: bool, message/page_id: str, page_link: str, page_name: str, category_name: str)
    """
    if not user_data_dir or not os.path.exists(user_data_dir):
        return False, "Profile user data directory not found", "", "", ""

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
            except Exception:
                connected_via_cdp = False

            # 2. Fallback: Launch standalone persistent context if browser is not open
            if not context:
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--test-type",
                    "--disable-notifications",
                    "--no-default-browser-check",
                    "--disable-dev-shm-usage"
                ]
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    executable_path=chrome_exe,
                    headless=headless,
                    args=launch_args,
                    viewport={"width": 1280, "height": 800}
                )

            # 3. Resolve active page
            if connected_via_cdp:
                target_page = None
                for pg in context.pages:
                    try:
                        if "facebook.com" in pg.url.lower():
                            target_page = pg
                            break
                    except Exception:
                        pass
                if not target_page:
                    target_page = context.new_page()
                    target_page.goto("https://web.facebook.com/", timeout=45000, wait_until="domcontentloaded")
                else:
                    target_page.bring_to_front()
                    if "facebook.com" not in target_page.url.lower():
                        target_page.goto("https://web.facebook.com/", timeout=45000, wait_until="domcontentloaded")
                page = target_page
            else:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://web.facebook.com/", timeout=45000, wait_until="domcontentloaded")

            time.sleep(1.5)
            dismiss_facebook_popup_notices(page)

            # Check Facebook login
            cookies = context.cookies()
            is_logged_in = any(c.get("name") == "c_user" and c.get("value") for c in cookies)
            if not is_logged_in:
                # Also check DOM if cookie is partitioned
                try:
                    is_logged_in = page.locator("svg[aria-label='Facebook'], a[aria-label='Facebook'], [aria-label*='Your profile']").first.is_visible(timeout=1500)
                except Exception:
                    pass

            if not is_logged_in:
                if not connected_via_cdp:
                    try:
                        context.close()
                    except Exception:
                        pass
                return False, "Profile is not logged into Facebook", "", "", ""

            # 1. Install Network Capture Hook
            page.evaluate(r"""() => {
                window.__captured_created_page_id = "";
                window.__captured_created_page_url = "";

                const origFetch = window.fetch;
                window.fetch = async function(...args) {
                    const resp = await origFetch.apply(this, args);
                    try {
                        const clone = resp.clone();
                        clone.text().then(txt => {
                            if (txt.includes('additional_profile') || txt.includes('profile_plus') || txt.includes('created_page') || txt.includes('AdditionalProfilePlusCreationMutation')) {
                                const m = txt.match(/"id"\s*:\s*"(\d{10,})"/);
                                if (m && m[1]) {
                                    window.__captured_created_page_id = m[1];
                                    window.__captured_created_page_url = "https://www.facebook.com/profile.php?id=" + m[1];
                                }
                            }
                        }).catch(()=>{});
                    } catch(e){}
                    return resp;
                };
            }""")

            # 2. Inject Script with 100% Invisible Stealth
            if INJECT_SCRIPT_CODE:
                # Pre-inject CSS style so #jsi-box and #jsi-overlay NEVER appear on the browser screen
                page.evaluate("""() => {
                    if (!document.getElementById('__stealth_hide_jsi__')) {
                        const style = document.createElement('style');
                        style.id = '__stealth_hide_jsi__';
                        style.textContent = `
                            #jsi-box, #jsi-overlay, div[id*="jsi-"], div[class*="jsi-"], [id^="jsi-"] {
                                position: fixed !important;
                                top: -99999px !important;
                                left: -99999px !important;
                                width: 1px !important;
                                height: 1px !important;
                                opacity: 0 !important;
                                visibility: hidden !important;
                                pointer-events: none !important;
                                z-index: -99999 !important;
                                transform: translate(-99999px, -99999px) !important;
                                clip: rect(0, 0, 0, 0) !important;
                            }
                        `;
                        (document.head || document.documentElement).appendChild(style);
                    }
                }""")

                page.evaluate(INJECT_SCRIPT_CODE)
                time.sleep(0.4)

                # 4. Trigger Create Facebook Page tool
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('#jsi-box button, #jsi-box div, #jsi-box a'));
                    for (const b of btns) {
                        if ((b.innerText || b.textContent || '').includes('CREATE FACEBOOK PAGE')) {
                            b.click();
                            break;
                        }
                    }
                }""")
                time.sleep(0.6)

                # 5. Set Name, Category & Go
                page.evaluate("""({name, catId}) => {
                    window.__selected_category_id = catId;
                    const inp = document.querySelector('#pc-name');
                    if (inp) {
                        inp.value = name;
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    const goBtn = document.querySelector('#pc-go');
                    if (goBtn) {
                        goBtn.click();
                    }
                }""", {"name": target_page_name, "catId": str(category_id)})

                # 6. Monitor result
                created_ok = False
                for _ in range(16):
                    time.sleep(1.0)
                    log_text = page.evaluate("""() => {
                        const el = document.querySelector('#jsi-log');
                        return el ? (el.innerText || el.textContent || '') : '';
                    }""")
                    if "Page created" in log_text or "created:" in log_text.lower():
                        created_ok = True
                        break
                    if "error" in log_text.lower() or "fail" in log_text.lower():
                        break

                captured = page.evaluate("""() => {
                    return {
                        id: window.__captured_created_page_id || '',
                        url: window.__captured_created_page_url || ''
                    };
                }""")

                created_page_id = captured.get("id") or ""
                created_page_link = captured.get("url") or ""

                if not created_page_id or not created_page_id.isdigit():
                    curr_url = page.url
                    m_id = re.search(r'facebook\.com/(?:pages/)?(?:profile\.php\?id=)?(\d+)', curr_url)
                    if m_id:
                        created_page_id = m_id.group(1)
                        created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"

                # Clean up DOM
                try:
                    page.evaluate("""() => {
                        document.querySelector('#jsi-overlay')?.remove();
                        document.querySelector('#jsi-box')?.remove();
                        document.querySelector('#__stealth_hide_jsi__')?.remove();
                    }""")
                except Exception:
                    pass

                time.sleep(1.0)

                if created_ok or created_page_id:
                    if not created_page_link and created_page_id:
                        created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"

                    # Seamlessly switch active Facebook session to the created Page voice
                    try:
                        target_url = f"https://web.facebook.com/profile.php?id={created_page_id}"
                        page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
                        time.sleep(3.5)
                        # Step 1: Click "Switch Now"
                        page.evaluate("""() => {
                            const btns = Array.from(document.querySelectorAll('div[role="button"], button, a, div[aria-label]'));
                            for (const b of btns) {
                                const txt = (b.innerText || b.textContent || b.getAttribute('aria-label') || '').trim().toLowerCase();
                                if (txt === 'switch now' || txt.startsWith('switch into') || txt === 'switch' || txt === 'সুইচ করুন' || txt === 'সুইচ') {
                                    b.click();
                                    break;
                                }
                            }
                        }""")
                        time.sleep(3.5)
                        # Step 2: Click "Use Page"
                        page.evaluate("""() => {
                            const btns = Array.from(document.querySelectorAll('div[role="button"], button, a, div[aria-label]'));
                            for (const b of btns) {
                                const txt = (b.innerText || b.textContent || b.getAttribute('aria-label') || '').trim().toLowerCase();
                                if (txt === 'use page' || txt === 'পেজ ব্যবহার করুন' || txt === 'take tour' || txt === 'not now') {
                                    b.click();
                                    break;
                                }
                            }
                        }""")
                        time.sleep(2.0)
                    except Exception:
                        pass
                    finally:
                        if not connected_via_cdp:
                            try:
                                context.close()
                            except Exception:
                                pass

                    return True, created_page_id, created_page_link, target_page_name, category_name
                else:
                    if not connected_via_cdp:
                        try:
                            context.close()
                        except Exception:
                            pass
                    return False, "Facebook mutation did not complete", "", target_page_name, category_name

            if not connected_via_cdp:
                try:
                    context.close()
                except Exception:
                    pass
            return False, "Inject script not found", "", "", ""

    except Exception as e:
        return False, f"Execution error: {str(e)}", "", "", ""
