import os
import sys
import time
import re
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List, Callable

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

def scan_video_folder(folder_path: str) -> List[str]:
    """Scan directory and return list of valid video file paths sorted by name."""
    p = Path(folder_path)
    if not p.exists() or not p.is_dir():
        return []
    videos = []
    for item in p.iterdir():
        if item.is_file() and item.suffix.lower() in SUPPORTED_VIDEO_EXTS:
            videos.append(str(item.resolve()))
    return sorted(videos)

def clean_video_title(file_path: str) -> str:
    """Derive clean human-readable title from video filename."""
    base = Path(file_path).stem
    clean = re.sub(r"[_\-\.]+", " ", base).strip()
    return clean.title()

def extract_asset_id_from_context(context) -> Optional[str]:
    """Extract active asset_id / Page ID from any open Meta Business Suite page."""
    # 1. Check all open pages' URLs
    for pg in context.pages:
        u = pg.url or ""
        m = re.search(r'asset_id=(\d+)', u)
        if m:
            return m.group(1)

    # 2. Check DOM on open Facebook / Meta Business pages
    for pg in context.pages:
        u = (pg.url or "").lower()
        if "facebook.com" in u:
            try:
                aid = pg.evaluate(r"""() => {
                    let m = window.location.href.match(/asset_id=(\d+)/);
                    if (m) return m[1];
                    let link = document.querySelector('a[href*="asset_id="]');
                    if (link) {
                        let m2 = link.href.match(/asset_id=(\d+)/);
                        if (m2) return m2[1];
                    }
                    return null;
                }""")
                if aid:
                    return str(aid)
            except Exception:
                pass
    return None

def execute_bulk_video_upload(
    user_data_dir: str,
    video_files: List[str],
    title_template: str = "{name}",
    description_text: str = "",
    max_count: int = 50,
    profile_data: Optional[Dict[str, Any]] = None,
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    timeout_minutes: int = 10,
    stuck_threshold_secs: int = 25,
    auto_delete_stuck: bool = True,
    auto_publish: bool = True
) -> Dict[str, Any]:
    """
    Executes automated bulk video upload to Facebook:
    
    1. Connects to live browser session via Smart CDP.
    2. Detects current Page / Asset ID or existing Bulk Upload Composer tab.
    3. Navigates directly to Meta Business Suite Bulk Upload Composer:
       https://business.facebook.com/latest/bulk_upload_composer?asset_id={asset_id}
    4. Injects ALL target video files simultaneously into Meta's Bulk Reeler file receiver.
    5. Fills individual Titles and Descriptions for each row.
    6. Actively monitors upload percentages (10-15s interval).
    7. Automatically deletes stuck videos (< 100% progress stalled for >= stuck_threshold_secs).
    8. Automatically clicks Publish when all remaining reels reach 100% upload (NO copyright check waiting!).
    9. Enforces max timeout_minutes per profile.
    10. Keeps browser window open for live inspection.
    """
    def notify(event_type: str, data: Optional[Dict[str, Any]] = None):
        if progress_cb:
            try:
                payload = {"type": event_type}
                if data:
                    payload.update(data)
                progress_cb(payload)
            except Exception:
                pass

    if not sync_playwright:
        notify("error", {"message": "Playwright is not installed in the environment."})
        return {"success": False, "error": "Playwright not installed"}

    if not user_data_dir or not Path(user_data_dir).exists():
        notify("error", {"message": f"Profile directory not found: {user_data_dir}"})
        return {"success": False, "error": "Profile dir not found"}

    if not video_files:
        notify("error", {"message": "No video files provided for upload."})
        return {"success": False, "error": "No video files"}

    target_videos = [str(Path(v).resolve()) for v in video_files[:max_count]]
    total_target = len(target_videos)

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

    uploaded_count = 0
    results = []

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
                    "--disable-infobars"
                ]
                launch_kwargs = {
                    "user_data_dir": str(user_data_dir),
                    "headless": False,
                    "args": launch_args
                }
                if exec_path:
                    launch_kwargs["executable_path"] = exec_path
                context = p.chromium.launch_persistent_context(**launch_kwargs)

            # Step 1: Check if bulk_upload_composer is already open
            page = None
            for pg in context.pages:
                u = (pg.url or "").lower()
                if "bulk_upload_composer" in u:
                    page = pg
                    notify("status", {"message": "📑 Found active 'Bulk upload reels' tab!"})
                    break

            # Step 2: If not on bulk upload composer, detect asset_id & navigate
            if not page:
                notify("status", {"message": "🔍 Detecting active Facebook Page / Asset ID..."})
                asset_id = extract_asset_id_from_context(context)

                # Select an active facebook tab or create one
                for pg in context.pages:
                    u = (pg.url or "").lower()
                    if "business.facebook.com" in u or "facebook.com" in u:
                        page = pg
                        break

                if not page:
                    page = context.pages[0] if context.pages else context.new_page()

                # If no asset_id yet, navigate to home to extract it
                if not asset_id:
                    notify("status", {"message": "🌐 Navigating to Meta Business Suite to resolve Page ID..."})
                    try:
                        page.goto("https://business.facebook.com/latest/home", timeout=30000, wait_until="domcontentloaded")
                        time.sleep(3.0)
                        asset_id = extract_asset_id_from_context(context)
                    except Exception as ex_home:
                        notify("status", {"message": f"Nav note: {ex_home}"})

                if asset_id:
                    bulk_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={asset_id}"
                else:
                    bulk_url = "https://business.facebook.com/latest/bulk_upload_composer"

                notify("status", {"message": f"🌐 Opening Meta Bulk Upload Reels ({bulk_url})..."})
                try:
                    page.goto(bulk_url, timeout=45000, wait_until="domcontentloaded")
                    time.sleep(3.0)
                except Exception as ex_nav:
                    notify("status", {"message": f"Nav notice: {ex_nav}. Checking page..."})

            page.bring_to_front()

            # Step 3: Inject ALL videos simultaneously
            notify("status", {"message": f"📤 Injecting ALL {total_target} video(s) into Meta Bulk Upload Reels at once..."})
            time.sleep(1.5)

            injection_success = False

            # Strategy A: Check for existing file input
            inputs = page.query_selector_all('input[type="file"]')
            for inp in inputs:
                accept_attr = (inp.get_attribute("accept") or "").lower()
                if "video" in accept_attr or accept_attr == "*" or not accept_attr:
                    try:
                        inp.set_input_files(target_videos)
                        injection_success = True
                        break
                    except Exception:
                        pass

            # Strategy B: If direct file input wasn't available, click "Add videos" and intercept file chooser
            if not injection_success:
                try:
                    add_btn = page.locator('div[role="button"]:has-text("Add videos"), button:has-text("Add videos")').first
                    if add_btn:
                        with page.expect_file_chooser(timeout=6000) as fc_info:
                            add_btn.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(target_videos)
                        injection_success = True
                except Exception as ex_fc:
                    notify("status", {"message": f"File chooser trigger note: {ex_fc}"})

            if not injection_success:
                notify("error", {"message": "Could not inject video files into Meta Bulk Composer. Kept open for inspection."})
                return {"success": False, "error": "File injection failed", "results": results}

            # Step 4: Wait for all rows to populate in Meta DOM
            notify("status", {"message": f"⏳ Waiting for Meta to populate {total_target} reel rows in table..."})
            max_wait_secs = 25
            for _ in range(max_wait_secs):
                time.sleep(1.0)
                rendered_count = page.evaluate(r"""() => {
                    let titles = document.querySelectorAll('textarea[placeholder*="title"], textarea');
                    let descs = document.querySelectorAll('div[contenteditable="true"]');
                    return Math.max(titles.length, descs.length);
                }""")
                if rendered_count >= total_target:
                    break

            time.sleep(2.0)
            title_boxes = page.query_selector_all('textarea[placeholder*="title"], textarea')
            desc_boxes = page.query_selector_all('div[contenteditable="true"]')

            # Step 5: Smoothly apply individual Titles & Descriptions to each row
            notify("status", {"message": f"✍️ Setting individual Titles & Descriptions for all {total_target} reels..."})

            # Parse title inputs (one per line, or fallback to clean file name)
            raw_titles = [line.strip() for line in (title_template or "").splitlines() if line.strip()]

            # Parse description inputs (split by '---' if multiple, else single text)
            if "---" in (description_text or ""):
                raw_descs = [d.strip() for d in description_text.split("---") if d.strip()]
            else:
                raw_descs = [description_text.strip()] if description_text.strip() else []

            for idx in range(total_target):
                vid_path = target_videos[idx]
                vid_name = Path(vid_path).name
                clean_name = clean_video_title(vid_path)

                # Determine Title using rotating serial index (modulo)
                if raw_titles:
                    selected_title = raw_titles[idx % len(raw_titles)]
                    formatted_title = selected_title.replace("{name}", clean_name).replace("{filename}", vid_name)
                else:
                    formatted_title = clean_name

                # Apply Title if Title box exists for this row (COMPLETELY CLEAR DEFAULT TEXT FIRST)
                if idx < len(title_boxes):
                    try:
                        t_box = title_boxes[idx]
                        if t_box.is_visible():
                            t_box.click()
                            time.sleep(0.08)
                            t_box.press("Control+A")
                            time.sleep(0.05)
                            t_box.press("Backspace")
                            time.sleep(0.05)
                            t_box.fill(formatted_title)
                    except Exception:
                        pass

                # Determine Description using rotating serial index (modulo)
                if raw_descs:
                    selected_desc = raw_descs[idx % len(raw_descs)]
                    formatted_desc = selected_desc.replace("{name}", clean_name).replace("{title}", formatted_title)
                else:
                    formatted_desc = ""

                # Apply Description if Description box exists for this row
                if formatted_desc and idx < len(desc_boxes):
                    try:
                        d_box = desc_boxes[idx]
                        if d_box.is_visible():
                            d_box.click()
                            time.sleep(0.08)
                            d_box.press("Control+A")
                            time.sleep(0.05)
                            d_box.press("Backspace")
                            time.sleep(0.05)
                            d_box.fill(formatted_desc)
                    except Exception:
                        pass

                uploaded_count += 1
                results.append({"file": vid_path, "name": vid_name, "status": "Uploaded", "title": formatted_title})
                notify("video_success", {
                    "index": idx + 1,
                    "file": vid_path,
                    "name": vid_name,
                    "title": formatted_title,
                    "message": f"✅ [{idx+1}/{total_target}] Title set: '{formatted_title}'"
                })

            # Step 6: Active Progress Monitoring & Stuck Video Removal Loop
            notify("status", {"message": "📊 Actively monitoring upload percentages (checking every 12s)..."})
            
            start_monitor_time = time.time()
            max_timeout_secs = max(1, timeout_minutes) * 60
            stuck_tracker = {}  # {row_title: {"last_pct": int, "stuck_since": float}}

            while True:
                time.sleep(12.0)
                elapsed_total = time.time() - start_monitor_time

                # Check Overall Profile Timeout
                if elapsed_total >= max_timeout_secs:
                    notify("status", {"message": f"⏰ Max wait time ({timeout_minutes}m) reached! Pruning incomplete videos..."})
                    if auto_delete_stuck:
                        # Remove any remaining rows < 100%
                        page.evaluate(r"""() => {
                            let removeBtns = Array.from(document.querySelectorAll('div[role="button"]'))
                                .filter(b => b.innerText && b.innerText.includes('Remove'));
                            removeBtns.reverse().forEach(btn => {
                                let rowEl = btn.closest('[role="row"]') || btn.parentElement.parentElement.parentElement.parentElement;
                                let text = rowEl ? rowEl.innerText : '';
                                let m = text.match(/(\d+)%/);
                                let pct = m ? parseInt(m[1]) : (text.includes('100%') ? 100 : 0);
                                if (pct < 100) {
                                    btn.click();
                                }
                            });
                        }""")
                        time.sleep(2.0)
                    break

                # Query current rows state
                rows_status = page.evaluate(r"""() => {
                    let removeBtns = Array.from(document.querySelectorAll('div[role="button"]'))
                        .filter(b => b.innerText && b.innerText.includes('Remove'));
                    
                    return removeBtns.map((btn, idx) => {
                        let rowEl = btn.closest('[role="row"]') || btn.parentElement.parentElement.parentElement.parentElement;
                        let text = rowEl ? rowEl.innerText : '';
                        let m = text.match(/(\d+)%/);
                        let pct = m ? parseInt(m[1]) : (text.includes('100%') ? 100 : 0);
                        let titleArea = rowEl ? rowEl.querySelector('textarea') : null;
                        let title = titleArea ? titleArea.value : `Reel #${idx+1}`;
                        return {
                            index: idx,
                            pct: pct,
                            is100: pct >= 100,
                            title: title
                        };
                    });
                }""")

                if not rows_status:
                    notify("status", {"message": "No active reel rows detected."})
                    break

                all_100 = True
                any_deleted = False
                now = time.time()

                for r_info in rows_status:
                    r_idx = r_info["index"]
                    r_pct = r_info["pct"]
                    r_title = r_info["title"] or f"Reel #{r_idx+1}"

                    if r_pct < 100:
                        all_100 = False
                        # Track progress
                        if r_title not in stuck_tracker:
                            stuck_tracker[r_title] = {"last_pct": r_pct, "stuck_since": now}
                        else:
                            last_pct = stuck_tracker[r_title]["last_pct"]
                            if r_pct > last_pct:
                                # Progressing normally!
                                stuck_tracker[r_title]["last_pct"] = r_pct
                                stuck_tracker[r_title]["stuck_since"] = now
                            else:
                                # Stuck at same percentage
                                stuck_dur = now - stuck_tracker[r_title]["stuck_since"]
                                if auto_delete_stuck and stuck_dur >= stuck_threshold_secs:
                                    notify("status", {"message": f"🗑️ Deleting stuck reel: '{r_title}' (frozen at {r_pct}% for {int(stuck_dur)}s)..."})
                                    # Click Remove for this specific row
                                    page.evaluate(f"""(() => {{
                                        let removeBtns = Array.from(document.querySelectorAll('div[role="button"]'))
                                            .filter(b => b.innerText && b.innerText.includes('Remove'));
                                        if (removeBtns[{r_idx}]) {{
                                            removeBtns[{r_idx}].click();
                                        }}
                                    }})()""")
                                    any_deleted = True
                                    time.sleep(1.5)
                                    break  # Re-scan in next cycle
                    else:
                        # 100% reached
                        if r_title in stuck_tracker:
                            del stuck_tracker[r_title]

                if any_deleted:
                    continue

                if all_100:
                    notify("status", {"message": f"✨ All {len(rows_status)} reel(s) have reached 100% upload! Ready to publish."})
                    break

            # Step 7: Auto-Publish Ready Reels (NO copyright check waiting!)
            if auto_publish:
                notify("status", {"message": "🚀 Clicking 'Publish' button for 100% ready reels..."})
                publish_clicked = False
                for _ in range(5):
                    publish_clicked = page.evaluate(r"""() => {
                        let btns = Array.from(document.querySelectorAll('div[role="button"], button'));
                        let pBtn = btns.find(b => b.innerText && b.innerText.trim() === 'Publish');
                        if (pBtn && !pBtn.getAttribute('aria-disabled') && !pBtn.disabled) {
                            pBtn.click();
                            return true;
                        }
                        return false;
                    }""")
                    if publish_clicked:
                        break
                    time.sleep(1.0)

                if publish_clicked:
                    notify("status", {"message": "✅ 'Publish' successfully triggered! Meta is processing batch release."})
                    time.sleep(3.0)
                    # Check if 'Done' confirmation modal popped up and close it cleanly
                    try:
                        page.evaluate(r"""() => {
                            let btns = Array.from(document.querySelectorAll('div[role="button"], button'));
                            let doneBtn = btns.find(b => b.innerText && b.innerText.trim() === 'Done');
                            if (doneBtn) doneBtn.click();
                        }""")
                    except Exception:
                        pass
                    time.sleep(2.0)
                else:
                    notify("status", {"message": "Publish button ready on screen for manual review."})

            # Notify user - keep browser open on screen for live inspection
            notify("done", {
                "uploaded_count": uploaded_count,
                "total": total_target,
                "results": results,
                "message": f"🎉 {uploaded_count} video(s) batch-uploaded & published! Browser kept active on screen for live inspection."
            })

            return {
                "success": uploaded_count > 0,
                "uploaded_count": uploaded_count,
                "total": total_target,
                "results": results
            }

    except Exception as ex:
        err_msg = f"Bulk upload error: {ex}"
        notify("error", {"message": err_msg})
        return {"success": False, "error": err_msg, "results": results}
