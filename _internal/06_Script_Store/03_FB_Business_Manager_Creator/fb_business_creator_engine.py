import os
import sys
import time
import re
import json
import random
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List, Callable

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BM_DEFAULT_NAMES = [
    "Caleb Diaz", "Leo Lee", "Luke Wilson", "Willow Thompson", "Elijah Lewis", 
    "Eleanor Cox", "Julian Watson", "Camila Campbell", "Lucy Diaz", "Joshua Moore", 
    "Everleigh Wright", "Leilani Gutierrez", "Henry Peterson", "Everett White", 
    "Amelia Cox", "Jack Cook", "Sebastian Mitchell", "Angel Morris", "Theo Cooper", 
    "Cameron Cruz", "Emily Cruz", "Roman Ramos", "Charles Adams", "Alice Brown", 
    "Jordan Mitchell", "Julian Perez", "Raelynn Cruz", "Valentina Brown", 
    "Jack Cooper", "Jaxon Rodriguez", "Sophia Miller", "Mason Taylor", "Oliver Davis"
]

def generate_random_bm_name() -> Tuple[str, str, str]:
    """Returns (first_name, last_name, full_name)."""
    full = random.choice(BM_DEFAULT_NAMES)
    parts = full.split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else "Smith"
    return first, last, full

def execute_bm_creation_flow(
    user_data_dir: str,
    max_bms: int = 10,
    profile_data: Optional[Dict[str, Any]] = None,
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Executes automated Facebook Business Manager creation in background:
    
    1. Connects to the live browser session via Smart CDP.
    2. Keeps the active tab on the standard Facebook homepage (NO ugly Meta Suite redirects).
    3. Solves DTSG, LSD, session user ID, and haste_session from active page.
    4. Dispatches background HTTP requests via context.request with full cookies.
    5. Iteratively creates BMs, capturing BM ID and links in real time.
    6. Detects Facebook BM limits gracefully.
    """
    def notify(event_type: str, data: Optional[Dict[str, Any]] = None):
        if progress_cb:
            payload = {"type": event_type}
            if data:
                payload.update(data)
            progress_cb(payload)

    if not sync_playwright:
        notify("error", {"message": "Playwright is not installed in the Python environment."})
        return {"success": False, "error": "Playwright not installed", "created": []}

    if not user_data_dir or not Path(user_data_dir).exists():
        notify("error", {"message": f"Profile user directory not found: {user_data_dir}"})
        return {"success": False, "error": "User dir not found", "created": []}

    # Restrict max_bms to 10
    max_bms = max(1, min(10, int(max_bms)))

    # Calculate deterministic CDP port
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

    created_bms = []

    try:
        with sync_playwright() as p:
            browser = None
            context = None
            connected_via_cdp = False

            notify("status", {"message": f"🔗 Connecting to live browser on Port {cdp_port}..."})

            try:
                browser = p.chromium.connect_over_cdp(cdp_url, timeout=3500)
                if browser and browser.contexts:
                    context = browser.contexts[0]
                    connected_via_cdp = True
                    notify("status", {"message": f"✅ Connected to live Profile #{n_val}!"})
            except Exception:
                connected_via_cdp = False

            if not context:
                notify("status", {"message": "🚀 Launching profile browser context..."})
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check",
                    "--no-first-run",
                    "--disable-infobars",
                    "--disable-notifications"
                ]
                launch_kwargs = {
                    "user_data_dir": str(user_data_dir),
                    "headless": False,
                    "args": launch_args
                }
                if exec_path:
                    launch_kwargs["executable_path"] = exec_path
                context = p.chromium.launch_persistent_context(**launch_kwargs)

            # Locate active Facebook page (Keep user on facebook.com homepage!)
            page = None
            for pg in context.pages:
                try:
                    u = (pg.url or "").lower()
                    if "facebook.com" in u and "business.facebook.com" not in u:
                        page = pg
                        break
                except Exception:
                    pass

            if not page and context.pages:
                page = context.pages[0]

            if not page:
                page = context.new_page()

            curr_url = (page.url or "").lower()
            if "facebook.com" not in curr_url or "business.facebook.com" in curr_url:
                notify("status", {"message": "🌐 Navigating to Facebook homepage..."})
                try:
                    page.goto("https://web.facebook.com/", timeout=30000, wait_until="domcontentloaded")
                    time.sleep(1.5)
                except Exception:
                    pass

            # Extract session credentials directly from Facebook tab
            cred_script = r"""() => {
                let token = null;
                try { token = (window.require && (window.require("DTSGInitialData")?.token || window.require("DTSGInitData")?.token)) || null; } catch(e) {}
                if (!token) {
                    const inputDtsg = document.querySelector('input[name="fb_dtsg"]');
                    if (inputDtsg) token = inputDtsg.value;
                }

                let userId = "";
                try { userId = (window.require && window.require("CurrentUserInitialData")?.USER_ID) || ""; } catch(e) {}
                if (!userId) {
                    const uidMatch = document.cookie.match(/c_user=(\d+)/);
                    if (uidMatch) userId = uidMatch[1];
                }

                let haste = "";
                try { haste = (window.require && window.require("SiteData")?.haste_session) || ""; } catch(e) {}

                let lsd = "";
                try { lsd = document.querySelector('input[name="lsd"]')?.value || ""; } catch(e) {}

                return { token, userId, haste, lsd };
            }"""

            creds = page.evaluate(cred_script)
            if not creds or not creds.get("token") or not creds.get("userId"):
                time.sleep(1.5)
                creds = page.evaluate(cred_script)

            if not creds or not creds.get("token") or not creds.get("userId"):
                notify("error", {"message": "Could not extract Facebook session. Please ensure profile is logged into Facebook."})
                if not connected_via_cdp:
                    try: context.close()
                    except Exception: pass
                return {"success": False, "error": "No session token", "created": []}

            token = creds.get("token")
            user_id = creds.get("userId")
            haste = creds.get("haste") or ""
            lsd = creds.get("lsd") or ""

            notify("status", {"message": "⚡ Facebook session validated! Creating Business Managers in background..."})

            # Headers matching exact Facebook business creation
            req_headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "origin": "https://business.facebook.com",
                "referer": "https://business.facebook.com/business/loginpage/",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty"
            }

            limit_reached = False
            error_reason = ""

            for idx in range(1, max_bms + 1):
                first_n, last_n, full_n = generate_random_bm_name()
                rand_mail = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8)) + "@gmail.com"

                notify("progress", {
                    "bm_num": idx,
                    "max_bms": max_bms,
                    "message": f"🛠️ Creating BM {idx} of {max_bms} ({full_n})..."
                })

                post_form = {
                    "brand_name": full_n,
                    "first_name": first_n,
                    "last_name": last_n,
                    "email": rand_mail,
                    "timezone_id": "53",
                    "business_category": "OTHER",
                    "entry_point": "bizweb_unified_login_business_manager_landing",
                    "is_b2b": "false",
                    "__a": "1",
                    "__user": user_id,
                    "__hs": haste,
                    "lsd": lsd,
                    "fb_dtsg": token
                }

                # Background POST via context.request with live browser cookies
                try:
                    resp = context.request.post(
                        "https://business.facebook.com/business/create_account",
                        form=post_form,
                        headers=req_headers,
                        timeout=25000
                    )
                    text_resp = resp.text()
                except Exception as ex_post:
                    # Fallback to in-page evaluation if context.request encounters network glitch
                    fb_eval_js = r"""async ({ brandName, firstName, lastName, email, token, userId, haste, lsd }) => {
                        try {
                            const p = new URLSearchParams({
                                brand_name: brandName,
                                first_name: firstName,
                                last_name: lastName,
                                email: email,
                                timezone_id: "53",
                                business_category: "OTHER",
                                entry_point: "bizweb_unified_login_business_manager_landing",
                                is_b2b: "false",
                                __a: "1",
                                __user: userId,
                                __hs: haste,
                                lsd: lsd,
                                fb_dtsg: token
                            });
                            const r = await fetch("https://business.facebook.com/business/create_account", {
                                method: "POST",
                                body: p.toString(),
                                headers: {
                                    "Content-Type": "application/x-www-form-urlencoded",
                                    "accept": "*/*"
                                },
                                credentials: "include"
                            });
                            return await r.text();
                        } catch(e) {
                            return JSON.stringify({ error: e.message });
                        }
                    }"""
                    text_resp = page.evaluate(fb_eval_js, {
                        "brandName": full_n,
                        "firstName": first_n,
                        "lastName": last_n,
                        "email": rand_mail,
                        "token": token,
                        "userId": user_id,
                        "haste": haste,
                        "lsd": lsd
                    })

                # Parse JSON and regex
                clean_json_str = re.sub(r"^for\s*\(\s*;\s*;\s*\);", "", text_resp).strip()
                json_data = None
                try:
                    json_data = json.loads(clean_json_str)
                except Exception:
                    pass

                bm_match = re.search(r'"business_id"\s*:\s*"?(\d+)"?', text_resp) or re.search(r'business_id=(\d+)', text_resp)
                business_id = bm_match.group(1) if bm_match else None

                err_summary_match = re.search(r'"errorSummary"\s*:\s*"([^"]+)"', text_resp)
                err_summary = err_summary_match.group(1) if err_summary_match else None

                has_error = ('"error"' in text_resp and not business_id) or err_summary or (json_data and (json_data.get("error") or json_data.get("errors")))

                if has_error or not business_id:
                    err_msg = ""
                    if json_data and isinstance(json_data.get("error"), dict):
                        err_msg = json_data["error"].get("message") or ""
                    if not err_msg:
                        err_msg = err_summary or "Limit Reached For The Number Of Businesses"

                    error_reason = err_msg
                    limit_reached = True
                    notify("failed", {
                        "bm_num": idx,
                        "reason": err_msg,
                        "message": f"⛔ BM {idx} Failed: {err_msg}"
                    })
                    break

                bm_url = f"https://business.facebook.com/latest/settings/ad_accounts?business_id={business_id}"
                bm_entry = {
                    "bm_num": idx,
                    "name": full_n,
                    "business_id": business_id,
                    "url": bm_url
                }
                created_bms.append(bm_entry)

                notify("bm_created", {
                    "bm_num": idx,
                    "name": full_n,
                    "business_id": business_id,
                    "url": bm_url,
                    "total_created": len(created_bms)
                })

                time.sleep(1.0)

            total = len(created_bms)
            done_msg = f"🏁 Done! Created {total} BM{'s' if total != 1 else ''} successfully."
            if limit_reached:
                done_msg = f"⛔ BM Limit Reached: Total {total} BM{'s' if total != 1 else ''} created."

            notify("done", {
                "total_created": total,
                "limit_reached": limit_reached,
                "reason": error_reason,
                "message": done_msg,
                "created_list": created_bms
            })

            if not connected_via_cdp:
                try:
                    context.close()
                except Exception:
                    pass

            return {
                "success": total > 0,
                "total_created": total,
                "limit_reached": limit_reached,
                "reason": error_reason,
                "created": created_bms
            }

    except Exception as ex:
        err_str = f"Execution error: {ex}"
        notify("error", {"message": err_str})
        return {"success": False, "error": err_str, "created": created_bms}
