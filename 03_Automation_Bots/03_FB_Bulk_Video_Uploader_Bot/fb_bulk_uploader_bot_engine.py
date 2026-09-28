# -*- coding: utf-8 -*-
"""
Multi-Threaded Facebook Bulk Video / Reel Uploader Bot Engine:
- Meta Business Suite Bulk Upload Composer Integration (identical to proven 06_Script_Store engine)
- Native Portable Chromium & srkBrowser Profile resolution with full session cookies
- Pinned Color Badge Extension & Taskbar Icon per profile
- Active Facebook Login Verification & 2FA auto-recovery with clean UID normalization
- Global sequential video distribution with infinite circular looping
- Zero deletion of videos
- Dynamic Active-Worker Pool with INSTANT STOP & KILL BROWSER support
- Headless / Visible mode support
- Simultaneous batch injection into Meta's Bulk Upload Reels
- Auto-populates Titles & Descriptions for every row
- 100% upload progress tracking & automated Publish trigger
- Real-time progress reporting and CSV output
"""

import os
import sys
import re
import time
import json
import random
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Set
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Signal

from playwright.sync_api import sync_playwright

from fb_bulk_uploader_bot_helpers import (
    smart_sleep, human_type, human_click, human_scroll,
    human_copy_paste, human_mouse_jitter, human_mouse_move, get_stealth_init_script,
    parse_cookie_string, save_fresh_cookies_to_profile,
    generate_upload_csv_report,
    resolve_user_data_dir,
    get_chrome_executable_path,
    apply_bot_window_icon_win32,
    check_facebook_login_status,
    dismiss_facebook_popup_notices,
    auto_relogin_facebook,
    clean_uid_str,
    kill_profile_chrome_process,
    extract_asset_id_from_context,
    check_is_meta_error_page,
    ensure_core_paths,
    apply_user_links_to_descriptions,
    scan_managed_facebook_pages,
    capture_diagnostic_screenshot,
    init_upload_excel_report,
    append_upload_report_record_realtime
)

ensure_core_paths()


class BulkVideoUploaderMasterThread(QThread):
    """
    Master Automation Orchestrator Thread:
    Distributes profiles and videos across concurrent threads with dynamic worker queue,
    instant stop/browser kill capabilities, looping, live stats, and automated reporting.
    """
    log_emitted = Signal(str, str)             # level (INFO/SUCCESS/WARNING/ERROR), message
    stats_updated = Signal(int, int, int, int)       # succ_profiles, fail_profiles, rem_profiles, total_videos
    progress_changed = Signal(int, int)              # completed_profiles, total_profiles
    finished_all = Signal(str, int, int, int, int)   # report_path, succ_profiles, fail_profiles, total_profiles, total_videos

    def __init__(
        self,
        profiles: List[Dict[str, Any]],
        video_files: List[Path],
        titles: List[str],
        descriptions: List[str],
        videos_per_profile: int = 1,
        concurrency: int = 1,
        stagger_sec: float = 2.0,
        is_headless: bool = False,
        publish_mode: str = "publish",         # "publish" or "draft"
        timeout_sec: int = 600,                # default 10 minutes
        reports_dir: Optional[Path] = None,
        profile_mgr: Optional[Any] = None,
        user_links: Optional[List[str]] = None,
        fail_group: Optional[str] = None,
        page_mode: str = "Selected Page",
        parent: Any = None
    ):
        super().__init__(parent)
        self.profiles = profiles
        self.video_files = video_files
        self.titles = titles
        self.user_links = user_links or []
        self.fail_group = (fail_group or "").strip()
        self.page_mode = (page_mode or "Selected Page").strip()
        # Only apply links if descriptions still contain unreplaced placeholders
        has_placeholders = any("{{link}}" in str(d).lower() for d in (descriptions or []))
        if has_placeholders and self.user_links:
            self.descriptions = apply_user_links_to_descriptions(descriptions, self.user_links)
        else:
            self.descriptions = list(descriptions) if descriptions else []
        self.videos_per_profile = max(1, videos_per_profile)
        self.concurrency = max(1, min(concurrency, 50))
        self.stagger_sec = max(0.5, stagger_sec)
        self.is_headless = is_headless
        self.publish_mode = publish_mode
        self.timeout_sec = max(30, timeout_sec)
        self.reports_dir = reports_dir or Path(__file__).resolve().parent / "reports"
        self.profile_mgr = profile_mgr

        self._is_cancelled = False
        self._lock = threading.Lock()
        self._global_video_index = 0
        self._global_title_index = 0
        self._global_desc_index = 0

        self.success_count = 0
        self.failed_count = 0
        self.total_target_uploads = len(self.profiles) * self.videos_per_profile
        self.records: List[Dict[str, Any]] = []
        self._active_contexts: List[Any] = []
        self._active_user_dirs: Set[str] = set()
        self.excel_report_file: Optional[Path] = None

    def _move_profile_to_fail_group(self, profile: Dict[str, Any], p_num: str) -> None:
        """
        Auto-moves failed profile to user-selected group in srkBrowser:
        - Updates profile manager database
        - Updates profile.json on disk
        - Updates in-memory profile dictionary
        - Emits user-facing warning log
        """
        if not self.fail_group or self.fail_group.lower() in ("none", ""):
            return

        p_id = profile.get("id")
        old_group = profile.get("group", "Default")
        if old_group == self.fail_group:
            return

        moved = False
        # Strategy A: Use profile_mgr.update_profile if available
        if self.profile_mgr and hasattr(self.profile_mgr, "update_profile") and p_id:
            try:
                if hasattr(self.profile_mgr, "create_group"):
                    try:
                        self.profile_mgr.create_group(self.fail_group)
                    except Exception:
                        pass
                moved = self.profile_mgr.update_profile(p_id, {"group": self.fail_group})
            except Exception:
                moved = False

        # Strategy B: Direct disk update fallback
        if not moved:
            try:
                user_dir = resolve_user_data_dir(profile)
                if user_dir:
                    p_json_file = user_dir / "profile.json"
                    if p_json_file.exists():
                        with open(p_json_file, "r", encoding="utf-8") as f:
                            pdata = json.load(f)
                        pdata["group"] = self.fail_group
                        with open(p_json_file, "w", encoding="utf-8") as f:
                            json.dump(pdata, f, indent=4)
                        moved = True
            except Exception:
                pass

        if moved:
            profile["group"] = self.fail_group
            self.log_emitted.emit("WARNING", f"[{p_num}] 📂 Profile moved to Fail Group: '{self.fail_group}'")

    def cancel(self) -> None:
        """Cancel the automation run cleanly and immediately terminate all active browser instances."""
        self._is_cancelled = True
        self.log_emitted.emit("WARNING", "🛑 Stop signal received. Terminating all active browser instances...")

        if hasattr(self, "_executor") and self._executor:
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

        with self._lock:
            for u_dir in list(self._active_user_dirs):
                try:
                    kill_profile_chrome_process(u_dir)
                except Exception:
                    pass
            self._active_user_dirs.clear()

    def run(self) -> None:
        """Main thread loop running dynamic active worker pool with instant stop."""
        if not self.profiles:
            self.log_emitted.emit("ERROR", "❌ No profiles selected for execution.")
            self.finished_all.emit("", 0, 0, 0, 0)
            return

        if not self.video_files:
            self.log_emitted.emit("ERROR", "❌ No video files available in queue.")
            self.finished_all.emit("", 0, 0, 0, 0)
            return

        self.total_profiles = len(self.profiles)
        self.succ_profiles = 0
        self.fail_profiles = 0
        self.total_videos_published = 0

        self.log_emitted.emit(
            "INFO",
            f"🚀 Starting Bulk Video Uploader Bot | Target IDs/Profiles: {self.total_profiles} | "
            f"Videos/ID: {self.videos_per_profile} | Total Videos Queue: {len(self.video_files)} | "
            f"Threads: {self.concurrency} | Headless: {self.is_headless}"
        )

        self.stats_updated.emit(0, 0, self.total_profiles, 0)
        self.progress_changed.emit(0, self.total_profiles)

        # Initialize real-time Excel report workbook
        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.excel_report_file = init_upload_excel_report(self.reports_dir, timestamp_str)
            if self.excel_report_file and Path(self.excel_report_file).exists():
                self.log_emitted.emit("INFO", f"📊 Real-time Excel report initialized: {self.excel_report_file.name}")
        except Exception as ex_rep:
            self.log_emitted.emit("WARNING", f"Excel report init notice: {ex_rep}")

        completed_tasks = 0
        prof_queue = list(enumerate(self.profiles))
        prof_iter = iter(prof_queue)

        self._executor = ThreadPoolExecutor(max_workers=self.concurrency)
        executor = self._executor
        try:
            futures = {}

            # Initial fill
            for _ in range(self.concurrency):
                if self._is_cancelled:
                    break
                try:
                    p_idx, profile = next(prof_iter)
                    f = executor.submit(self._process_single_profile, profile, p_idx + 1, len(self.profiles))
                    futures[f] = (p_idx, profile)
                    if p_idx > 0 and self.stagger_sec > 0:
                        smart_sleep(self.stagger_sec, self.stagger_sec + random.uniform(1.5, 3.5))
                except StopIteration:
                    break

            while futures and not self._is_cancelled:
                done_futures = [f for f in futures if f.done()]
                if not done_futures:
                    time.sleep(0.2)
                    continue

                for f in done_futures:
                    p_info = futures.pop(f)
                    try:
                        p_records, p_succ, p_fail = f.result()
                        with self._lock:
                            self.records.extend(p_records)
                            self.total_videos_published += p_succ
                            if p_succ > 0:
                                self.succ_profiles += 1
                            else:
                                self.fail_profiles += 1

                            completed_profiles = self.succ_profiles + self.fail_profiles
                            rem_profiles = max(0, self.total_profiles - completed_profiles)

                            self.stats_updated.emit(
                                self.succ_profiles,
                                self.fail_profiles,
                                rem_profiles,
                                self.total_videos_published
                            )
                            self.progress_changed.emit(completed_profiles, self.total_profiles)
                    except Exception as ex:
                        if not self._is_cancelled:
                            self.log_emitted.emit("ERROR", f"❌ Worker execution error: {ex}")

                    if self._is_cancelled:
                        break

                    # Dispatch next profile only if NOT cancelled
                    try:
                        next_p_idx, next_profile = next(prof_iter)
                        if self.stagger_sec > 0:
                            smart_sleep(self.stagger_sec, self.stagger_sec + random.uniform(1.5, 3.5))
                        if not self._is_cancelled:
                            new_f = executor.submit(self._process_single_profile, next_profile, next_p_idx + 1, len(self.profiles))
                            futures[new_f] = (next_p_idx, next_profile)
                    except StopIteration:
                        pass

            if self._is_cancelled:
                for f in list(futures.keys()):
                    try:
                        f.cancel()
                    except Exception:
                        pass
        finally:
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

        # Finalize Real-time Excel Report
        final_rep_path = str(self.excel_report_file) if (self.excel_report_file and Path(self.excel_report_file).exists()) else ""
        if final_rep_path:
            self.log_emitted.emit("SUCCESS", f"📊 Real-time Excel Report finalized: {Path(final_rep_path).name}")

        if self._is_cancelled:
            self.log_emitted.emit(
                "WARNING",
                f"🛑 Bot Automation Stopped by User! Successful IDs: {self.succ_profiles}/{self.total_profiles} | "
                f"Failed IDs: {self.fail_profiles} | Total Videos: {self.total_videos_published}"
            )
        else:
            self.log_emitted.emit(
                "SUCCESS" if self.fail_profiles == 0 else "INFO",
                f"🎉 Bot Automation Finished! Successful IDs: {self.succ_profiles}/{self.total_profiles} | "
                f"Failed IDs: {self.fail_profiles} | Total Videos Published: {self.total_videos_published}"
            )
        self.finished_all.emit(
            final_rep_path,
            self.succ_profiles,
            self.fail_profiles,
            self.total_profiles,
            self.total_videos_published
        )

    def _get_next_video_package(self) -> Tuple[Path, str, str]:
        """Thread-safe sequential video, title, and description dispenser with circular looping."""
        with self._lock:
            vid = self.video_files[self._global_video_index % len(self.video_files)]
            self._global_video_index += 1

            if self.titles:
                title = self.titles[self._global_title_index % len(self.titles)]
                self._global_title_index += 1
            else:
                title = vid.stem.replace("_", " ").replace("-", " ").title()

            if self.descriptions:
                desc = self.descriptions[self._global_desc_index % len(self.descriptions)]
                self._global_desc_index += 1
            else:
                desc = ""

            return vid, title, desc

    def _get_composer_rows_status(self, page: Any) -> List[Dict[str, Any]]:
        """
        Extracts reel row upload percentages strictly and exclusively from each video row:
        - Evaluates each contenteditable description box and resolves its parent row container.
        - Checks for upload percentage specifically on that row (e.g. 0%, 45%, 100%).
        - Checks for 'safe to publish' / 'no copyright issues' confirmation.
        - NO global body text scanning or style width scanning to avoid false positives (e.g. 30% width).
        """
        try:
            res = page.evaluate(r"""() => {
                let descs = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                if (!descs.length) return [];

                return descs.map((descEl, idx) => {
                    let row = descEl.closest('tr') || descEl.closest('[role="row"]');
                    if (!row) {
                        let el = descEl.parentElement;
                        while (el && el !== document.body) {
                            let hasThumbnail = !!(el.querySelector('img') || el.querySelector('video'));
                            let descBoxes = el.querySelectorAll('div[contenteditable="true"]');
                            if (hasThumbnail && descBoxes.length === 1) {
                                row = el;
                                if (el.querySelector('button') || el.querySelector('div[role="button"]')) {
                                    break;
                                }
                            }
                            el = el.parentElement;
                        }
                    }
                    if (!row) row = descEl.parentElement;

                    let pct = 0;
                    let is100 = false;
                    let rowText = (row ? (row.innerText || row.textContent || '') : '').trim();
                    let rowLower = rowText.toLowerCase();

                    if (rowLower.includes('safe to publish') || 
                        rowLower.includes('no copyright issues') || 
                        rowLower.includes('100%')) {
                        pct = 100;
                        is100 = true;
                    } else {
                        let matches = Array.from(rowText.matchAll(/\b(\d{1,3})\s*%/g));
                        for (let m of matches) {
                            let val = parseInt(m[1]);
                            if (!isNaN(val) && val >= 0 && val <= 100) {
                                pct = Math.max(pct, val);
                            }
                        }

                        if (row && pct === 0) {
                            let pb = row.querySelector('[role="progressbar"], [aria-valuenow]');
                            if (pb) {
                                let vn = pb.getAttribute('aria-valuenow');
                                if (vn) {
                                    let val = parseInt(vn);
                                    if (!isNaN(val) && val > 0 && val <= 100) pct = val;
                                }
                            }
                        }
                        if (pct >= 100) is100 = true;
                    }

                    let titleArea = row ? row.querySelector('textarea') : null;
                    let title = titleArea ? titleArea.value : (`Reel #${idx+1}`);

                    return {
                        index: idx,
                        pct: pct,
                        is100: is100,
                        title: title
                    };
                });
            }""")
            if isinstance(res, list):
                return res
            return []
        except Exception:
            return []

    def _execute_page_upload(
        self,
        page: Any,
        context: Any,
        bulk_url: str,
        batch_packages: List[Tuple[Path, str, str]],
        target_paths: List[str],
        p_num: str,
        p_name: str,
        page_label: str = "",
        uid: str = "",
        password: str = ""
    ) -> Tuple[bool, List[Dict[str, Any]], int, int]:
        """
        Executes complete upload flow on a single Meta Business Suite Bulk Composer page.
        Returns: (success_bool, records, succ_count, fail_count)
        """
        records: List[Dict[str, Any]] = []
        label_info = f" ({page_label})" if page_label else ""
        self.log_emitted.emit("INFO", f"[{p_num}] Opening Meta Bulk Composer{label_info} ({bulk_url})...")
        try:
            page.goto(bulk_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as ex_nav:
            self.log_emitted.emit("WARNING", f"[{p_num}] Composer navigation notice: {ex_nav}")

        # Wait for composer to finish loading (wait past the blue spinner until elements render)
        self.log_emitted.emit("INFO", f"[{p_num}] ⏳ Waiting for Meta Bulk Composer to finish loading...")
        composer_ready = False
        for _ in range(30):
            if self._is_cancelled:
                break
            if check_is_meta_error_page(page):
                break

            is_ready = page.evaluate(r"""() => {
                let hasFileInput = !!document.querySelector('input[type="file"]');
                let text = document.body ? (document.body.innerText || '') : '';
                let hasAddBtn = text.includes('Add videos') || text.includes('Bulk upload reels') || text.includes('Upload up to');
                return hasFileInput || hasAddBtn;
            }""")
            if is_ready:
                composer_ready = True
                break
            time.sleep(1.0)

        dismiss_facebook_popup_notices(page)

        # Check if Meta returned an Error page ("Sorry, something went wrong")
        if check_is_meta_error_page(page):
            self.log_emitted.emit("WARNING", f"[{p_num}] ⚠️ Meta returned 'Sorry, something went wrong'. Attempting Page Auto-Discovery...")
            try:
                page.goto("https://business.facebook.com/latest/home", timeout=35000, wait_until="domcontentloaded")
                smart_sleep(4.0, 6.0)
                dismiss_facebook_popup_notices(page)

                active_aid = extract_asset_id_from_context(context)
                if active_aid:
                    self.log_emitted.emit("INFO", f"[{p_num}] 📑 Discovered Page ID [{active_aid}]. Re-opening Bulk Composer...")
                    page.goto(f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={active_aid}", timeout=45000, wait_until="domcontentloaded")
                    smart_sleep(3.5, 5.0)
                    dismiss_facebook_popup_notices(page)
            except Exception as ex_rec:
                self.log_emitted.emit("WARNING", f"[{p_num}] Auto-recovery notice: {ex_rec}")

        # Final Error Page Guard: If page is STILL an error page, return fail!
        if check_is_meta_error_page(page):
            self.log_emitted.emit(
                "ERROR",
                f"[{p_num}] ❌ Facebook Page Error: 'Sorry, something went wrong' for {page_label or 'active page'}."
            )
            capture_diagnostic_screenshot(
                page=page,
                profile_name=p_name,
                label="meta_page_error",
                reports_dir=self.reports_dir,
                uid=uid,
                password=password,
                extra_info=f"Facebook Page Error: 'Sorry, something went wrong'{label_info}"
            )
            for pkg in batch_packages:
                records.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "profile_number": p_num,
                    "profile_name": p_name,
                    "video_name": pkg[0].name,
                    "video_path": str(pkg[0]),
                    "title": pkg[1],
                    "desc": pkg[2],
                    "status": "FAILED",
                    "duration": 0,
                    "error": f"Facebook Error ('Sorry, something went wrong'){label_info}"
                })
            return False, records, 0, len(batch_packages)

        smart_sleep(1.0, 2.0)

        # Discard previous draft popup if present
        try:
            discard_btn = page.locator("div[role='dialog'] button:has-text('Discard'), div[role='dialog'] div[role='button']:has-text('Discard')").first
            if discard_btn.is_visible(timeout=2000):
                human_click(discard_btn)
                smart_sleep(1.0, 2.0)
        except Exception:
            pass

        # Human Pause: 2.0 to 5.0 seconds randomized wait on upload page before injecting files
        pre_upload_delay = random.uniform(2.0, 5.0)
        self.log_emitted.emit(
            "INFO",
            f"[{p_num}] ⏱️ Meta Bulk Composer ready. Waiting {pre_upload_delay:.1f}s random pause before uploading videos..."
        )
        smart_sleep(pre_upload_delay, pre_upload_delay)
        human_mouse_jitter(page)

        # Step C: Inject target batch of videos all at once into Bulk Composer
        self.log_emitted.emit(
            "INFO",
            f"[{p_num}] 📤 Injecting {len(target_paths)} video(s) into Meta Bulk Upload Reels{label_info}..."
        )

        injection_success = False
        inputs = page.query_selector_all('input[type="file"]')
        for inp in inputs:
            accept_attr = (inp.get_attribute("accept") or "").lower()
            if "video" in accept_attr or accept_attr == "*" or not accept_attr:
                try:
                    inp.set_input_files(target_paths)
                    injection_success = True
                    break
                except Exception:
                    pass

        if not injection_success:
            try:
                add_btn = page.locator('div[role="button"]:has-text("Add videos"), button:has-text("Add videos"), div[role="button"]:has-text("Add video")').first
                if add_btn.is_visible(timeout=4000):
                    with page.expect_file_chooser(timeout=6000) as fc_info:
                        add_btn.click()
                    fc = fc_info.value
                    fc.set_files(target_paths)
                    injection_success = True
            except Exception:
                pass

        if not injection_success:
            try:
                page.locator('input[type="file"]').first.set_input_files(target_paths)
                injection_success = True
            except Exception as ex_inj:
                self.log_emitted.emit("ERROR", f"[{p_num}] Could not inject videos: {ex_inj}")

        if not injection_success:
            capture_diagnostic_screenshot(
                page=page,
                profile_name=p_name,
                label="injection_failed",
                reports_dir=self.reports_dir,
                uid=uid,
                password=password,
                extra_info=f"Failed to inject files into Meta Composer{label_info}"
            )
            for pkg in batch_packages:
                records.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "profile_number": p_num,
                    "profile_name": p_name,
                    "video_name": pkg[0].name,
                    "video_path": str(pkg[0]),
                    "title": pkg[1],
                    "desc": pkg[2],
                    "status": "FAILED",
                    "duration": 0,
                    "error": f"Failed to inject files into Meta Composer{label_info}"
                })
            return False, records, 0, len(batch_packages)

        # Step D: Wait for all rows to populate in Meta DOM
        self.log_emitted.emit("INFO", f"[{p_num}] ⏳ Waiting for {len(target_paths)} reel rows to populate...")
        for _ in range(25):
            if self._is_cancelled:
                break
            time.sleep(1.0)
            rendered_count = page.evaluate(r"""() => {
                let titles = document.querySelectorAll('textarea[placeholder*="title"], textarea');
                let descs = document.querySelectorAll('div[contenteditable="true"]');
                return Math.max(titles.length, descs.length);
            }""")
            if rendered_count >= len(target_paths):
                break

        time.sleep(1.5)

        # Step E: Verify Video Upload Activity BEFORE Setting Titles and Descriptions
        self.log_emitted.emit(
            "INFO",
            f"[{p_num}] 🔍 Verifying upload initiation for {len(target_paths)} reel(s){label_info}..."
        )

        upload_started = False
        pre_check_start = time.time()
        pre_check_timeout = 25.0  # 25s check window
        all_zero_aborted = False

        while not self._is_cancelled:
            elapsed_check = time.time() - pre_check_start
            rows_status = page.evaluate(r"""() => {
                let rows = document.querySelectorAll('div[role="row"], div[data-pagelet*="Row"], div.x1n2onr6');
                let statuses = [];
                for (let i = 0; i < rows.length; i++) {
                    let text = rows[i].innerText || "";
                    let pctMatch = text.match(/(\d{1,3})%/);
                    if (pctMatch) {
                        statuses.push({ index: i, pct: parseInt(pctMatch[1], 10) });
                    }
                }
                return statuses;
            }""")

            row_max = max([r["pct"] for r in rows_status], default=0)
            if row_max > 0:
                upload_started = True
                self.log_emitted.emit(
                    "SUCCESS",
                    f"[{p_num}] 🟢 Video upload verified active! (Detected progress: {row_max}% on video rows). Proceeding to set Titles & Descriptions..."
                )
                break

            pct_list_str = ", ".join([f"#{r['index']+1}: {r['pct']}%" for r in rows_status[:5]]) if rows_status else "Scanning video rows (0%)..."
            self.log_emitted.emit(
                "WARNING" if elapsed_check >= 12 else "INFO",
                f"[{p_num}] ⏳ Checking upload initiation ({int(elapsed_check)}s/{int(pre_check_timeout)}s): {pct_list_str}"
            )

            if elapsed_check >= pre_check_timeout:
                self.log_emitted.emit(
                    "ERROR",
                    f"[{p_num}] 🚫 All {len(batch_packages)} video(s) remained frozen at 0% for {int(elapsed_check)}s! "
                    f"Meta upload stalled on this page. Aborting without setting metadata..."
                )
                all_zero_aborted = True
                break

            smart_sleep(2.0, 3.0)

        if self._is_cancelled:
            return False, [], 0, 0

        if all_zero_aborted:
            capture_diagnostic_screenshot(
                page=page,
                profile_name=p_name,
                label="upload_stuck_0pct",
                reports_dir=self.reports_dir,
                uid=uid,
                password=password,
                extra_info=f"All videos stuck at 0% for {int(pre_check_timeout)}s{label_info}"
            )
            for pkg in batch_packages:
                records.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "profile_number": p_num,
                    "profile_name": p_name,
                    "video_name": pkg[0].name,
                    "video_path": str(pkg[0]),
                    "title": pkg[1],
                    "desc": pkg[2],
                    "status": "FAILED",
                    "duration": round(time.time() - pre_check_start, 1),
                    "error": f"All videos stuck at 0% for {int(pre_check_timeout)}s{label_info}"
                })
             # Step F: Fill individual Titles and Descriptions for each row (Row-Container Bound)
        self.log_emitted.emit("INFO", f"[{p_num}] ⚡ Setting Titles & Descriptions for {len(batch_packages)} reels{label_info}...")

        # Re-query live title textareas and description contenteditables
        for idx, pkg in enumerate(batch_packages):
            if self._is_cancelled:
                break
            vid_path, title_text, desc_text = pkg

            t_clean = (title_text or "").strip()
            d_clean = (desc_text or "").strip()

            # Robust per-row locator: find the exact row container for this index
            row_configured = False
            try:
                # Check whether the page provides separate title textareas
                title_handles = page.query_selector_all('textarea[placeholder*="title" i], textarea')
                has_title_input = (len(title_handles) > 0)

                if has_title_input:
                    # Layout A: Dedicated Title textarea exists
                    if idx < len(title_handles) and t_clean:
                        t_box = title_handles[idx]
                        t_box.scroll_into_view_if_needed(timeout=2000)
                        t_box.click(timeout=1500)
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                        page.keyboard.insert_text(t_clean)
                        time.sleep(0.08)
                        self.log_emitted.emit("INFO", f"[{p_num}] ✍️ Reel #{idx+1} Title set: '{t_clean[:25]}'")

                    # Fill Description Field strictly bound to this row's container
                    if d_clean:
                        desc_set = page.evaluate(r"""([idx, text]) => {
                            let textareas = Array.from(document.querySelectorAll('textarea[placeholder*="title" i], textarea'));
                            let descBoxes = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                            let dBox = null;
                            if (textareas.length > 0 && idx < textareas.length) {
                                let t = textareas[idx];
                                let curr = t;
                                let foundRow = null;
                                while (curr && curr !== document.body) {
                                    let hasDesc = curr.querySelector('div[contenteditable="true"]');
                                    if (hasDesc) {
                                        foundRow = curr;
                                        break;
                                    }
                                    curr = curr.parentElement;
                                }
                                dBox = foundRow ? foundRow.querySelector('div[contenteditable="true"]') : (descBoxes[idx] || null);
                            } else if (idx < descBoxes.length) {
                                dBox = descBoxes[idx];
                            }
                            if (dBox) {
                                dBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                dBox.focus();
                                return true;
                            }
                            return false;
                        }""", [idx, d_clean])

                        if desc_set:
                            time.sleep(0.08)
                            page.keyboard.press("Control+A")
                            page.keyboard.press("Backspace")
                            page.keyboard.insert_text(d_clean)
                            time.sleep(0.1)
                            self.log_emitted.emit("INFO", f"[{p_num}] ✍️ Reel #{idx+1} Description set ({len(d_clean)} chars)")
                        else:
                            # Fallback to direct desc handles
                            desc_handles = page.query_selector_all('div[contenteditable="true"]')
                            if idx < len(desc_handles):
                                d_box = desc_handles[idx]
                                d_box.scroll_into_view_if_needed(timeout=2000)
                                d_box.click(timeout=1500)
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                page.keyboard.insert_text(d_clean)
                                time.sleep(0.1)
                                self.log_emitted.emit("INFO", f"[{p_num}] ✍️ Reel #{idx+1} Description set via handle ({len(d_clean)} chars)")
                else:
                    # Layout B: Facebook Reels layout without title box ("Describe your reel so people know what it's about")
                    if t_clean and d_clean:
                        caption_text = f"{t_clean}\n\n{d_clean}"
                    elif t_clean:
                        caption_text = t_clean
                    elif d_clean:
                        caption_text = d_clean
                    else:
                        caption_text = ""

                    if caption_text:
                        typed_ok = False
                        desc_handles = page.query_selector_all('div[contenteditable="true"]')
                        if idx < len(desc_handles):
                            try:
                                d_box = desc_handles[idx]
                                d_box.scroll_into_view_if_needed(timeout=2000)
                                d_box.click(timeout=1500)
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                page.keyboard.insert_text(caption_text)
                                time.sleep(0.1)
                                typed_ok = True
                                self.log_emitted.emit("INFO", f"[{p_num}] ✍️ Reel #{idx+1} Caption/Title set: '{caption_text[:35]}...'")
                            except Exception:
                                typed_ok = False

                        if not typed_ok:
                            desc_set = page.evaluate(r"""([idx]) => {
                                let descBoxes = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                                if (idx < descBoxes.length) {
                                    descBoxes[idx].scrollIntoView({ behavior: 'smooth', block: 'center' });
                                    descBoxes[idx].focus();
                                    return true;
                                }
                                return false;
                            }""", [idx])
                            if desc_set:
                                time.sleep(0.08)
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                page.keyboard.insert_text(caption_text)
                                time.sleep(0.1)
                                self.log_emitted.emit("INFO", f"[{p_num}] ✍️ Reel #{idx+1} Caption set via focus ({len(caption_text)} chars)")
            except Exception as ex_fill:
                self.log_emitted.emit("WARNING", f"[{p_num}] Notice configuring Reel #{idx+1}: {ex_fill}")

            log_label = f"Title: '{t_clean[:25]}' | " if t_clean else ""
            self.log_emitted.emit("SUCCESS", f"[{p_num}] ⚡ Configured Reel #{idx+1}: {log_label}Desc: '{d_clean[:35]}...'")

            if idx < len(batch_packages) - 1:
                time.sleep(random.uniform(0.15, 0.25))

        # Step F.2: Strict Form Verification Pass with Multi-Pass Retry Loop
        self.log_emitted.emit("INFO", f"[{p_num}] 🔍 Verifying all {len(batch_packages)} reels have completed Titles & Descriptions...")
        
        all_metadata_complete = False
        for v_pass in range(5):
            if self._is_cancelled:
                break

            verif_data = page.evaluate(r"""() => {
                let titleBoxes = Array.from(document.querySelectorAll('textarea[placeholder*="title" i], textarea'));
                let descBoxes = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                let hasTitleLayout = titleBoxes.length > 0;

                if (hasTitleLayout) {
                    let rows = titleBoxes.map((t, idx) => {
                        let curr = t;
                        let foundRow = null;
                        while (curr && curr !== document.body) {
                            if (curr.querySelector('div[contenteditable="true"]')) {
                                foundRow = curr;
                                break;
                            }
                            curr = curr.parentElement;
                        }
                        let dBox = foundRow ? foundRow.querySelector('div[contenteditable="true"]') : (descBoxes[idx] || null);
                        let dText = dBox ? (dBox.innerText || '').trim() : '';
                        if (dText.toLowerCase().includes('describe your reel')) dText = '';
                        return {
                            idx: idx,
                            title: (t.value || '').trim(),
                            desc: dText
                        };
                    });
                    return { hasTitleLayout: true, rows: rows };
                } else {
                    // Layout without title box (e.g. Profile 1395 / Facebook Reels) - ONLY description boxes exist
                    let rows = descBoxes.map((dBox, idx) => {
                        let dText = (dBox.innerText || '').trim();
                        if (dText.toLowerCase().includes('describe your reel')) dText = '';
                        return {
                            idx: idx,
                            title: '',
                            desc: dText
                        };
                    });
                    return { hasTitleLayout: false, rows: rows };
                }
            }""")

            has_title_layout = verif_data.get("hasTitleLayout", False)
            rows_verif = verif_data.get("rows", [])

            missing_indices = []
            for v_idx, pkg in enumerate(batch_packages):
                _, req_title, req_desc = pkg
                req_title = (req_title or "").strip()
                req_desc = (req_desc or "").strip()
                curr_t = rows_verif[v_idx]["title"] if v_idx < len(rows_verif) else ""
                curr_d = rows_verif[v_idx]["desc"] if v_idx < len(rows_verif) else ""

                if has_title_layout:
                    t_missing = bool(req_title and len(curr_t) < 2)
                    d_missing = bool(req_desc and len(curr_d) < 3)
                    missing_desc_text = req_desc
                else:
                    t_missing = False
                    expected_caption = f"{req_title}\n\n{req_desc}".strip() if (req_title and req_desc) else (req_title or req_desc).strip()
                    d_missing = bool(expected_caption and len(curr_d) < min(3, len(expected_caption)))
                    missing_desc_text = expected_caption

                if t_missing or d_missing:
                    missing_indices.append((v_idx, t_missing, d_missing, req_title, missing_desc_text))

            if not missing_indices:
                all_metadata_complete = True
                verif_label = "Titles & Descriptions" if has_title_layout else "Captions/Titles"
                self.log_emitted.emit("SUCCESS", f"[{p_num}] ✅ All {len(batch_packages)} reels 100% verified: {verif_label} fully populated!")
                break
            else:
                self.log_emitted.emit("WARNING", f"[{p_num}] ⚠️ Verification pass {v_pass+1}: {len(missing_indices)} reel(s) incomplete! Re-applying...")
                for m_idx, t_miss, d_miss, r_t, r_d in missing_indices:
                    if t_miss:
                        try:
                            title_handles = page.query_selector_all('textarea[placeholder*="title" i], textarea')
                            if m_idx < len(title_handles):
                                tb = title_handles[m_idx]
                                tb.scroll_into_view_if_needed(timeout=2000)
                                tb.click(timeout=1500)
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                page.keyboard.insert_text(r_t.strip())
                                time.sleep(0.08)
                        except Exception:
                            pass

                    if d_miss and r_d:
                        try:
                            desc_handles = page.query_selector_all('div[contenteditable="true"]')
                            if m_idx < len(desc_handles):
                                db = desc_handles[m_idx]
                                db.scroll_into_view_if_needed(timeout=2000)
                                db.click(timeout=1500)
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                page.keyboard.insert_text(r_d.strip())
                                time.sleep(0.1)
                        except Exception:
                            pass
                time.sleep(1.0)

        # Safety Check: Never proceed to publish if any reel still lacks Title or Description!
        if not all_metadata_complete:
            self.log_emitted.emit("ERROR", f"[{p_num}] ❌ Titles/Descriptions could not be completed for all reels after 5 retries! Halting publish to prevent unconfigured uploads.")
            return False, records, 0, len(batch_packages)

        # Step G: Active Progress Monitoring, Stuck Video Pruning, and Configured Delay
        self.log_emitted.emit("INFO", f"[{p_num}] 📊 Verifying 100% upload completion (Safe to publish) for all reels...")
        
        stuck_tracker = {}  # {row_index: {"last_pct": int, "stuck_since": float}}
        stuck_timeout_sec = 35.0  # 35s freeze threshold before pruning a stuck row via Trash/Remove button
        max_upload_wait = min(self.timeout_sec, 300.0)  # Max 5m wait for upload completion
        start_wait_upload = time.time()

        while not self._is_cancelled:
            elapsed_upload = time.time() - start_wait_upload
            if elapsed_upload > max_upload_wait:
                self.log_emitted.emit("WARNING", f"[{p_num}] ⏱️ Max upload wait ({int(max_upload_wait)}s) reached. Proceeding with ready reels...")
                break

            status_info = page.evaluate(r"""() => {
                // Support both layouts: find rows via title textareas OR desc contenteditables
                let titleBoxes = Array.from(document.querySelectorAll('textarea[placeholder*="title" i], textarea'));
                let descBoxes = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                let anchorElements = titleBoxes.length > 0 ? titleBoxes : descBoxes;

                let rowsData = anchorElements.map((el, idx) => {
                    let curr = el;
                    let foundRow = null;
                    while (curr && curr !== document.body) {
                        let btns = Array.from(curr.querySelectorAll('div[role="button"], button'));
                        if (btns.some(b => (b.innerText || '').toLowerCase().includes('remove'))) {
                            foundRow = curr;
                            break;
                        }
                        curr = curr.parentElement;
                    }
                    let rTxt = foundRow ? (foundRow.innerText || '').toLowerCase() : (el.parentElement.parentElement.innerText || '').toLowerCase();
                    
                    // Match percentage: e.g. "8%", "9%", "12%", "13%", "25%", "100%"
                    let pctMatch = rTxt.match(/(\d{1,3})%/);
                    let pct = pctMatch ? parseInt(pctMatch[1], 10) : 0;
                    let hasSafeText = rTxt.includes('safe to publish') || rTxt.includes('no copyright issues');

                    // STRICT 100% check:
                    // If pct is between 1 and 99, it is STILL UPLOADING, NEVER 100%!
                    let is100 = false;
                    if (pct === 100) {
                        is100 = true;
                    } else if (pct === 0 && hasSafeText) {
                        is100 = true;
                        pct = 100;
                    } else if (pct > 0 && pct < 100) {
                        is100 = false;
                    } else {
                        is100 = false;
                    }

                    return { index: idx, pct: pct, is100: is100 };
                });

                return {
                    rows: rowsData
                };
            }""")

            rows_info = status_info.get("rows", [])
            all_ready = len(rows_info) > 0 and all(r["is100"] for r in rows_info)
            any_deleted = False
            now = time.time()

            for r_item in rows_info:
                r_idx = r_item["index"]
                r_pct = r_item["pct"]
                r_100 = r_item["is100"]

                if not r_100:
                    if r_idx not in stuck_tracker:
                        stuck_tracker[r_idx] = {"last_pct": r_pct, "stuck_since": now}
                    else:
                        if r_pct > stuck_tracker[r_idx]["last_pct"]:
                            stuck_tracker[r_idx]["last_pct"] = r_pct
                            stuck_tracker[r_idx]["stuck_since"] = now
                        else:
                            stuck_dur = now - stuck_tracker[r_idx]["stuck_since"]
                            if stuck_dur >= stuck_timeout_sec:
                                self.log_emitted.emit(
                                    "WARNING",
                                    f"[{p_num}] 🗑️ Reel #{r_idx+1} stuck at {r_pct}% for {int(stuck_dur)}s! Deleting stuck reel via Trash/Remove icon..."
                                )
                                deleted_ok = page.evaluate(r"""(idx) => {
                                    let titleBoxes = Array.from(document.querySelectorAll('textarea[placeholder*="title" i], textarea'));
                                    let descBoxes = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                                    let anchorElements = titleBoxes.length > 0 ? titleBoxes : descBoxes;
                                    if (idx >= anchorElements.length) return false;
                                    let el = anchorElements[idx];
                                    let curr = el;
                                    let foundRow = null;
                                    while (curr && curr !== document.body) {
                                        let btns = Array.from(curr.querySelectorAll('div[role="button"], button'));
                                        if (btns.some(b => (b.innerText || '').toLowerCase().includes('remove'))) {
                                            foundRow = curr;
                                            break;
                                        }
                                        curr = curr.parentElement;
                                    }
                                    if (!foundRow) return false;
                                    let remBtn = Array.from(foundRow.querySelectorAll('div[role="button"], button')).find(b => 
                                        (b.innerText || '').toLowerCase().includes('remove') ||
                                        (b.getAttribute('aria-label') || '').toLowerCase().includes('remove') ||
                                        (b.getAttribute('aria-label') || '').toLowerCase().includes('delete')
                                    );
                                    if (remBtn) {
                                        remBtn.click();
                                        return true;
                                    }
                                    return false;
                                }""", r_idx)
                                if deleted_ok:
                                    self.log_emitted.emit("INFO", f"[{p_num}] 🗑️ Pruned stuck reel #{r_idx+1} successfully.")
                                    any_deleted = True
                                    time.sleep(2.0)
                                    break
                else:
                    if r_idx in stuck_tracker:
                        del stuck_tracker[r_idx]

            if any_deleted:
                continue

            # Strict 100% upload requirement: EVERY reel must be 100%!
            if all_ready:
                self.log_emitted.emit("SUCCESS", f"[{p_num}] ✨ All {len(rows_info)} reel(s) verified 100% uploaded & ready (Safe to publish)!")
                break
            else:
                pct_summary = ", ".join([f"#{r['index']+1}: {r['pct']}%" for r in rows_info[:6]])
                if len(rows_info) > 6:
                    pct_summary += f"... (+{len(rows_info)-6} more)"
                self.log_emitted.emit("INFO", f"[{p_num}] ⏳ Uploading reels ({pct_summary}). Waiting for 100% completion on all videos...")

            smart_sleep(2.0, 3.5)

        # Human Pause: User-configured delay (e.g. 2.5 to 4.5s random jitter) after all videos reach 100% ready
        base_delay = max(2.0, self.stagger_sec)
        pub_delay = random.uniform(base_delay, base_delay + random.uniform(1.0, 1.8))
        self.log_emitted.emit("INFO", f"[{p_num}] ⏱️ All reels 100% uploaded & verified! Waiting {pub_delay:.1f}s configured delay before publishing...")
        smart_sleep(pub_delay, pub_delay)
        human_mouse_jitter(page)

        # Blur any focused text fields to ensure the button click is clean
        try:
            page.evaluate("() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); }")
            time.sleep(0.4)
        except Exception:
            pass

        # Guaranteed Publish Button Click (Single clean click, strictly Footer Publish ONLY, no repeat loops)
        wizard_success = False
        for attempt in range(3):
            if self._is_cancelled:
                break

            # 1. Check for intermediate "Next" button in multi-step wizard
            next_found = False
            try:
                next_found = page.evaluate(r"""() => {
                    let all = Array.from(document.querySelectorAll('button, div[role="button"]'));
                    let nextBtn = all.reverse().find(b => {
                        let txt = (b.innerText || '').trim();
                        let y = b.getBoundingClientRect().y;
                        return (txt === 'Next') && !b.disabled && b.getAttribute('aria-disabled') !== 'true' && y > 500;
                    });
                    if (nextBtn) {
                        nextBtn.click();
                        return true;
                    }
                    return false;
                }""")
            except Exception:
                next_found = False

            if next_found:
                self.log_emitted.emit("INFO", f"[{p_num}] 👆 Clicked 'Next' step...")
                smart_sleep(2.0, 3.0)
                continue

            # 2. Click real Publish button in bottom footer (y > 500, EXACT text 'Publish')
            pub_clicked = False
            try:
                pub_clicked = page.evaluate(r"""() => {
                    let all = Array.from(document.querySelectorAll('button, div[role="button"]'));
                    let pubBtn = all.find(b => {
                        let txt = (b.innerText || '').trim();
                        let y = b.getBoundingClientRect().y;
                        return txt === 'Publish' && y > 500 && !b.disabled && b.getAttribute('aria-disabled') !== 'true';
                    });
                    if (pubBtn) {
                        pubBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        pubBtn.focus();
                        pubBtn.click();
                        return true;
                    }
                    return false;
                }""")
            except Exception:
                pub_clicked = False

            if not pub_clicked:
                try:
                    # Safe fallback locator strictly targeting footer button
                    locs = page.locator('div[role="button"]:has-text("Publish"), button:has-text("Publish")').filter(has_not_text="now").filter(has_not_text="Cancel")
                    cnt = locs.count()
                    for li in range(cnt - 1, -1, -1):
                        item = locs.nth(li)
                        y_pos = item.evaluate("el => el.getBoundingClientRect().y")
                        if y_pos > 500 and item.is_visible(timeout=1000):
                            item.click(delay=80, timeout=2500, force=True)
                            pub_clicked = True
                            break
                except Exception:
                    pass

            if pub_clicked:
                self.log_emitted.emit("SUCCESS", f"[{p_num}] 📤 Footer 'Publish' button clicked! Verifying submission...")
                wizard_success = True
                # Break immediately! Do NOT re-click while Meta shows 'Processing your posts'
                break
            else:
                smart_sleep(1.0, 2.0)

        # Step H: Monitor Publishing Progress to Completion
        self.log_emitted.emit("INFO", f"[{p_num}] ⏳ Monitoring upload & publish progress (timeout: {int(self.timeout_sec/60)}m)...")
        start_monitor = time.time()
        published_completed = False
        succ_count = 0
        fail_count = 0

        while not self._is_cancelled:
            elapsed = time.time() - start_monitor
            if elapsed > self.timeout_sec:
                self.log_emitted.emit("ERROR", f"[{p_num}] ⏱️ Timeout reached ({int(self.timeout_sec/60)}m) while waiting for upload to complete.")
                break

            # 0. Check for Meta Error / Rejection Dialog ("Unable to process all your reels" / "Dismiss")
            reels_err_detected = False
            try:
                err_res = page.evaluate(r"""() => {
                    let text = document.body ? (document.body.innerText || '') : '';
                    let lower = text.toLowerCase();
                    
                    let hasErrPhrase = text.includes("Unable to process all your reels") ||
                                       text.includes("weren't able to be shared") ||
                                       text.includes("The following reels weren't processed") ||
                                       text.includes("Due to an error, some of your reels") ||
                                       (text.includes("Unable to process") && lower.includes("reel")) ||
                                       text.includes("Some of your reels couldn't be published");
                    
                    let hasDismissBtn = false;
                    let allButtons = Array.from(document.querySelectorAll('button, div[role="button"], a[role="button"]'));
                    for (let b of allButtons) {
                        let bt = (b.innerText || '').trim();
                        if (bt === 'Dismiss' || bt.includes('Dismiss')) {
                            hasDismissBtn = true;
                            break;
                        }
                    }

                    return hasErrPhrase || (hasDismissBtn && (lower.includes("error") || lower.includes("weren't") || lower.includes("unable")));
                }""")
                if err_res:
                    reels_err_detected = True
            except Exception:
                reels_err_detected = False

            if not reels_err_detected:
                for err_sel in [
                    "text=Unable to process all your reels",
                    "text=weren't able to be shared",
                    "text=The following reels weren't processed",
                    "div:has-text('Unable to process all your reels')",
                    "div:has-text('weren\'t able to be shared')"
                ]:
                    try:
                        if page.locator(err_sel).first.is_visible(timeout=300):
                            reels_err_detected = True
                            break
                    except Exception:
                        pass

            if reels_err_detected:
                self.log_emitted.emit(
                    "ERROR",
                    f"[{p_num}] 🚫 Meta Error Detected: 'Unable to process all your reels' (Dismiss popup on screen)!"
                )
                self.log_emitted.emit(
                    "INFO",
                    f"[{p_num}] 📸 Capturing error screenshot directly from screen..."
                )
                ss_file_path = capture_diagnostic_screenshot(
                    page=page,
                    profile_name=p_name,
                    label="meta_unable_to_process_reels_dismiss",
                    reports_dir=self.reports_dir,
                    uid=uid,
                    password=password,
                    extra_info=f"Meta Error: Unable to process all your reels (Dismiss popup on screen){label_info}"
                )

                if ss_file_path:
                    self.log_emitted.emit("INFO", f"[{p_num}] 📁 Saved error screenshot: {Path(ss_file_path).name}")

                fail_err = f"Meta Error: 'Unable to process all your reels' (Dismiss popup appeared - Account/Page restricted from publishing reels){label_info}"
                for pkg in batch_packages:
                    records.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "profile_number": p_num,
                        "profile_name": p_name,
                        "video_name": pkg[0].name,
                        "video_path": str(pkg[0]),
                        "title": pkg[1],
                        "desc": pkg[2],
                        "status": "FAILED",
                        "duration": round(time.time() - start_monitor, 1),
                        "error": fail_err
                    })

                self.log_emitted.emit("ERROR", f"[{p_num}] ❌ {fail_err}")
                return False, records, 0, len(batch_packages)

            # 1. Check for Meta bulk confirmation message ('Your bulk upload is processing')
            # USER RULE: Seeing 'Your bulk upload is processing' means 100% SUCCESS!
            # The bot must NOT click 'Done' or anywhere else!
            is_success_msg = False
            try:
                is_success_msg = page.evaluate(r"""() => {
                    let text = document.body ? (document.body.innerText || '') : '';
                    if (text.includes("Unable to process") || text.includes("weren't able to be shared") || text.includes("weren't processed")) {
                        return false;
                    }
                    return text.includes("Your bulk upload is processing") ||
                           text.includes("Your bulk upload is being processed") ||
                           text.includes("Your reels are published") ||
                           text.includes("Your videos are published") ||
                           text.includes("Your posts were published") ||
                           text.includes("published successfully") ||
                           text.includes("Your reel has been published");
                }""")
            except Exception:
                is_success_msg = False

            if is_success_msg:
                self.log_emitted.emit("SUCCESS", f"[{p_num}] 🎉 Meta confirmed: 'Your bulk upload is processing!'")
                self.log_emitted.emit("SUCCESS", f"[{p_num}] ✨ All {len(batch_packages)} Reels successfully posted without extra clicks (Done button omitted as instructed)!")
                published_completed = True
                break

            # 2. Check if Meta closed composer or navigated away to Content dashboard
            curr_url = page.url or ""
            if "bulk_upload_composer" not in curr_url and elapsed > 5:
                has_err = page.evaluate(r"""() => {
                    let text = document.body ? (document.body.innerText || '') : '';
                    return text.includes("Unable to process") || text.includes("weren't able to be shared") || text.includes("weren't processed");
                }""")
                if not has_err:
                    published_completed = True
                    self.log_emitted.emit("SUCCESS", f"[{p_num}] 🎉 All {len(batch_packages)} Reels Published Successfully{label_info} (Redirected to Content dashboard)!")
                    break

            smart_sleep(1.5, 2.5)

        # Build records
        if published_completed:
            for pkg in batch_packages:
                records.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "profile_number": p_num,
                    "profile_name": p_name,
                    "video_name": pkg[0].name,
                    "video_path": str(pkg[0]),
                    "title": pkg[1],
                    "desc": pkg[2],
                    "status": "SUCCESS",
                    "duration": round(time.time() - start_monitor, 1),
                    "error": ""
                })
                succ_count += 1
            return True, records, succ_count, 0
        else:
            capture_diagnostic_screenshot(
                page=page,
                profile_name=p_name,
                label="upload_stuck",
                reports_dir=self.reports_dir,
                uid=uid,
                password=password,
                extra_info=f"Upload stuck or incomplete{label_info}"
            )
            for pkg in batch_packages:
                records.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "profile_number": p_num,
                    "profile_name": p_name,
                    "video_name": pkg[0].name,
                    "video_path": str(pkg[0]),
                    "title": pkg[1],
                    "desc": pkg[2],
                    "status": "FAILED",
                    "duration": round(time.time() - start_monitor, 1),
                    "error": f"Upload stuck or incomplete{label_info}"
                })
                fail_count += 1
            return False, records, 0, fail_count

    def _process_single_profile(
        self,
        profile: Dict[str, Any],
        p_idx: int,
        total_p: int
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Process video uploads for one specific profile using native Meta Business Suite Bulk Upload Composer."""
        if self._is_cancelled:
            return [], 0, 0

        p_num = str(profile.get("number", p_idx))
        p_name = clean_uid_str(profile.get("name", f"Profile {p_num}"))
        p_records: List[Dict[str, Any]] = []
        p_success = 0
        p_failed = 0

        # Random pre-delay per profile to avoid simultaneous robotic bursts across accounts
        if p_idx > 1:
            pre_wait = random.uniform(2.0, 4.5)
            self.log_emitted.emit("INFO", f"[{p_num}] ⏳ Randomizing start delay ({round(pre_wait, 1)}s) for human pacing...")
            smart_sleep(pre_wait, pre_wait + 0.3)

        self.log_emitted.emit("INFO", f"[{p_num}] Initializing srkBrowser Portable profile '{p_name}' ({p_idx}/{total_p})...")

        # 1. Resolve exact user data directory with full session cookies
        user_dir = resolve_user_data_dir(profile, self.profile_mgr)
        chrome_exe = get_chrome_executable_path()
        p_dir = Path(user_dir)

        # Hydrate complete credentials (cookies, uid, pass, 2fa, notes) from disk and ProfileManager
        p_json = p_dir / "profile.json"
        if p_json.exists():
            try:
                with open(p_json, "r", encoding="utf-8") as pf:
                    disk_p = json.load(pf)
                if isinstance(disk_p, dict):
                    for k, v in disk_p.items():
                        if v and not profile.get(k):
                            profile[k] = v
            except Exception:
                pass

        if self.profile_mgr and hasattr(self.profile_mgr, "profiles"):
            for pm_p in getattr(self.profile_mgr, "profiles", []):
                if isinstance(pm_p, dict):
                    if (profile.get("id") and pm_p.get("id") == profile.get("id")) or \
                       (str(profile.get("number", "")) and str(pm_p.get("number", "")).strip() == str(profile.get("number", "")).strip()):
                        for k, v in pm_p.items():
                            if v and not profile.get(k):
                                profile[k] = v

        # Extract full credentials for diagnostic screenshots and live Excel reports
        prof_uid = str(profile.get("fb_uid") or profile.get("uid") or profile.get("email") or profile.get("username") or "").strip()
        if not prof_uid and "fb_" in str(p_name).lower():
            m = re.search(r"\d{10,20}", str(p_name))
            if m:
                prof_uid = m.group(0)
        prof_pass = str(profile.get("fb_pass") or profile.get("password") or profile.get("pass") or "").strip()
        prof_2fa = str(profile.get("fb_2fa") or profile.get("2fa_secret") or profile.get("two_factor") or profile.get("secret_2fa") or profile.get("2fa") or "").strip()
        prof_cookie = str(profile.get("cookies") or profile.get("fb_cookie") or profile.get("cookie") or profile.get("cookies_raw") or "").strip()

        notes = str(profile.get("notes") or "").strip()
        if notes:
            m_uid = re.search(r'(?:uid|fb\s*uid|id|user):\s*([0-9a-zA-Z\._\-]+)', notes, re.IGNORECASE)
            m_pwd = re.search(r'(?:pass|password|pwd):\s*([^\s\|]+)', notes, re.IGNORECASE)
            m_2fa = re.search(r'(?:2fa|totp|secret):\s*([0-9a-zA-Z\s]+)', notes, re.IGNORECASE)
            if m_uid and not prof_uid: prof_uid = m_uid.group(1).strip()
            if m_pwd and not prof_pass: prof_pass = m_pwd.group(1).strip()
            if m_2fa and not prof_2fa: prof_2fa = m_2fa.group(1).strip()

            if "|" in notes and (not prof_uid or not prof_pass):
                parts = [p.strip() for p in notes.split("|")]
                if len(parts) >= 2:
                    if not prof_uid: prof_uid = parts[0]
                    if not prof_pass: prof_pass = parts[1]
                    if len(parts) >= 3 and not prof_2fa: prof_2fa = parts[2]
                    if len(parts) >= 4 and not prof_cookie: prof_cookie = parts[3]

        # Prepare batch packages for this profile upfront so failures can be recorded with exact error details
        batch_packages = []
        for v_idx in range(self.videos_per_profile):
            pkg = self._get_next_video_package()
            batch_packages.append(pkg)

        with self._lock:
            self._active_user_dirs.add(user_dir)

        # 2. Clean leftover singleton locks and processes
        kill_profile_chrome_process(user_dir)
        for lock_name in ["SingletonLock", "lockfile"]:
            lock_f = p_dir / lock_name
            if lock_f.exists():
                try:
                    lock_f.unlink(missing_ok=True)
                except Exception:
                    pass

        # 3. Native Browser Language Setup: Ensure English (US)
        try:
            def_dir = p_dir / "Default"
            def_dir.mkdir(parents=True, exist_ok=True)
            pref_file = def_dir / "Preferences"
            pref_data = {}
            if pref_file.exists():
                try:
                    with open(pref_file, "r", encoding="utf-8") as f:
                        pref_data = json.load(f)
                except Exception:
                    pref_data = {}
            if not isinstance(pref_data, dict):
                pref_data = {}
            pref_data.setdefault("intl", {})["accept_languages"] = "en-US,en"
            pref_data.setdefault("intl", {})["selected_languages"] = "en-US,en"
            pref_data.setdefault("spellcheck", {})["dictionaries"] = ["en-US"]
            pref_data.setdefault("spellcheck", {})["dictionary"] = "en-US"
            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(pref_data, f, indent=2)
        except Exception:
            pass

        # 4. Color & Profile Badge Extension Setup
        raw_num = str(profile.get("number", p_idx)).replace("Profile", "").replace("#", "").strip()
        num_text = f"{int(raw_num):02d}" if raw_num.isdigit() else (raw_num or "01")
        prof_num_int = int(raw_num) if raw_num.isdigit() else 1
        ico_path = p_dir / "profile_icon.ico"
        color_name = profile.get("color", "SkyBlue")
        color_hex = "#38bdf8"
        try:
            from config import COLOR_PALETTE
            color_hex = COLOR_PALETTE.get(color_name, "#38bdf8") if isinstance(COLOR_PALETTE, dict) else "#38bdf8"
        except Exception:
            pass

        try:
            from core.browser import generate_profile_icon_ico, create_profile_inspector_extension
        except ImportError:
            try:
                from browser import generate_profile_icon_ico, create_profile_inspector_extension
            except ImportError:
                def generate_profile_icon_ico(*a, **kw): return False
                def create_profile_inspector_extension(*a, **kw): return ""

        try:
            generate_profile_icon_ico(num_text, ico_path, color_hex, prof_num_int)
        except Exception:
            pass

        badge_ext_path = ""
        try:
            badge_ext_path = create_profile_inspector_extension(p_dir, profile)
        except Exception:
            pass

        # Resolve user-configured or default window size matching srkBrowser
        win_size_str = "1280,800"
        try:
            from config import load_settings
            st = load_settings()
            raw_s = st.get("browser_window_size", "1280x800")
            win_size_str = raw_s.split(" ")[0].replace("x", ",").strip()
        except Exception:
            pass

        # Clean stale SingletonLock if inactive
        lock_file = p_dir / "SingletonLock"
        if lock_file.exists():
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Sanitize any abnormal/tiny cached window placement in Preferences
        try:
            pref_file = p_dir / "Default" / "Preferences"
            if pref_file.exists():
                with open(pref_file, "r", encoding="utf-8") as f:
                    pref_data = json.load(f)
                if isinstance(pref_data, dict) and "browser" in pref_data:
                    wp = pref_data["browser"].get("window_placement")
                    if isinstance(wp, dict):
                        w = wp.get("right", 0) - wp.get("left", 0)
                        h = wp.get("bottom", 0) - wp.get("top", 0)
                        if w < 900 or h < 600:
                            pref_data["browser"]["window_placement"] = {
                                "top": 40,
                                "left": 40,
                                "right": 1320,
                                "bottom": 840,
                                "maximized": False
                            }
                            with open(pref_file, "w", encoding="utf-8") as f:
                                json.dump(pref_data, f, indent=2)
        except Exception:
            pass

        # Authentic browser flags mimicking srkBrowser native runtime (Zero automation flags)
        launch_args = [
            f"--window-size={win_size_str}",
            "--window-position=40,40",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-background-mode",
            "--disable-session-crashed-bubble",
            "--no-service-autorun",
            "--disable-infobars",
            "--disable-signin-promo",
            "--signin-process-disabled",
            "--silent-debugger-extension-api",
            "--disable-component-update",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--deny-permission-prompts",
            "--lang=en-US",
            "--accept-lang=en-US,en;q=0.9",
            "--disable-save-password-bubble",
            "--disable-single-click-autofill",
            "--disable-autofill-keyboard-accessory-view",
            "--disable-password-generation",
            "--password-store=basic",
            "--credentials-enable-service=false",
            "--disable-blink-features=AutomationControlled",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--disable-site-isolation-trials",
            "--disable-features=IsolateOrigins,site-per-process,TranslateUI",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ]
        if badge_ext_path and os.path.exists(badge_ext_path):
            launch_args.append(f"--load-extension={badge_ext_path}")

        if self._is_cancelled:
            with self._lock:
                self._active_user_dirs.discard(user_dir)
            return [], 0, 0

        context = None
        try:
            with sync_playwright() as p:
                if self._is_cancelled:
                    return [], 0, 0

                launch_kwargs = {
                    "user_data_dir": str(p_dir.resolve()),
                    "headless": self.is_headless,
                    "args": launch_args,
                    "no_viewport": True,
                    "ignore_default_args": ["--enable-automation"]
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                with self._lock:
                    self._active_contexts.append(context)

                # Stealth & anti-detect injection to mask automation indicators
                try:
                    context.grant_permissions(["clipboard-read", "clipboard-write"])
                except Exception:
                    pass
                try:
                    context.add_init_script(script=get_stealth_init_script())
                except Exception:
                    pass

                # Set custom numbered profile icon on Windows taskbar and window
                if ico_path.exists() and os.name == "nt":
                    try:
                        apply_bot_window_icon_win32(ico_path, num_text)
                    except Exception:
                        pass

                # Pre-inject session cookies from profile database if available
                raw_cookie = str(profile.get("cookie") or profile.get("cookies") or profile.get("cookies_raw") or "").strip()
                if raw_cookie:
                    parsed_cks = parse_cookie_string(raw_cookie)
                    if parsed_cks:
                        try:
                            context.add_cookies(parsed_cks)
                            self.log_emitted.emit("INFO", f"[{p_num}] 🍪 Injected {len(parsed_cks)} saved session cookie(s) from database.")
                        except Exception as ck_ex:
                            self.log_emitted.emit("WARNING", f"[{p_num}] Cookie injection note: {ck_ex}")

                page = context.pages[0] if context.pages else context.new_page()

                if self._is_cancelled:
                    return [], 0, 0

                # Step A: Verify Facebook Session Health & Auto Re-Login
                self.log_emitted.emit("INFO", f"[{p_num}] Checking Facebook session health...")
                page.goto("https://web.facebook.com/", timeout=45000, wait_until="domcontentloaded")
                smart_sleep(2.0, 3.5)
                dismiss_facebook_popup_notices(page)
                smart_sleep(1.0, 2.0)

                if self._is_cancelled:
                    return [], 0, 0

                is_logged_in, login_status = check_facebook_login_status(page, timeout_sec=5.0)
                if not is_logged_in:
                    if login_status == "CHECKPOINT":
                        self.log_emitted.emit("ERROR", f"[{p_num}] 🔴 Facebook Checkpoint / Account Locked.")
                        capture_diagnostic_screenshot(
                            page=page,
                            profile_name=p_name,
                            label="checkpoint",
                            reports_dir=self.reports_dir,
                            uid=prof_uid,
                            password=prof_pass,
                            extra_info="Facebook Account Checkpoint / Locked"
                        )
                        for pkg in batch_packages:
                            p_records.append({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "profile_number": p_num,
                                "profile_name": p_name,
                                "video_name": pkg[0].name,
                                "video_path": str(pkg[0]),
                                "title": pkg[1],
                                "desc": pkg[2],
                                "status": "FAILED",
                                "duration": 0,
                                "error": "Facebook Account Checkpoint / Locked"
                            })
                        p_failed = len(batch_packages)
                        return p_records, 0, p_failed
                    else:
                        self.log_emitted.emit("WARNING", f"[{p_num}] ⚠️ Account not logged in. Initiating automated re-login using saved credentials...")
                        relogin_ok, relogin_msg = auto_relogin_facebook(
                            page=page,
                            context=context,
                            profile_data=profile,
                            profile_mgr=self.profile_mgr,
                            user_data_dir=user_dir,
                            log_func=lambda m: self.log_emitted.emit("INFO", f"[{p_num}] {m}"),
                            uid=prof_uid,
                            password=prof_pass,
                            twofa_secret=prof_2fa
                        )
                        if relogin_ok:
                            self.log_emitted.emit("SUCCESS", f"[{p_num}] 🟢 Auto-relogin successful! Resuming video upload...")
                            is_logged_in = True
                        else:
                            self.log_emitted.emit("ERROR", f"[{p_num}] ❌ Re-login failed: {relogin_msg}")
                            capture_diagnostic_screenshot(
                                page=page,
                                profile_name=p_name,
                                label="relogin_failed",
                                reports_dir=self.reports_dir,
                                uid=prof_uid,
                                password=prof_pass,
                                extra_info=relogin_msg
                            )
                            for pkg in batch_packages:
                                p_records.append({
                                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "profile_number": p_num,
                                    "profile_name": p_name,
                                    "video_name": pkg[0].name,
                                    "video_path": str(pkg[0]),
                                    "title": pkg[1],
                                    "desc": pkg[2],
                                    "status": "FAILED",
                                    "duration": 0,
                                    "error": f"Re-login Failed: {relogin_msg}"
                                    })
                            p_failed = len(batch_packages)
                            return p_records, 0, p_failed

                self.log_emitted.emit("SUCCESS", f"[{p_num}] 🟢 Facebook Session Active.")

                # User Requirement: 1 to 2 seconds random wait after Facebook Home loads before starting upload
                wait_sec = random.uniform(1.0, 2.0)
                self.log_emitted.emit("INFO", f"[{p_num}] ⏱️ Facebook Home loaded. Waiting {wait_sec:.1f}s before launching bulk upload...")
                smart_sleep(wait_sec, wait_sec)

                target_paths = [str(pkg[0].resolve()) for pkg in batch_packages]

                # Step B: Multi-Page Execution Strategy (Selected Page, Fallback on Fail, All Pages)
                if self.page_mode == "Fallback on Fail":
                    bulk_url = "https://business.facebook.com/latest/bulk_upload_composer?asset_id"
                    is_ok, recs, s_cnt, f_cnt = self._execute_page_upload(
                        page, context, bulk_url, batch_packages, target_paths, p_num, p_name, "Primary Page", uid=prof_uid, password=prof_pass
                    )
                    p_records.extend(recs)
                    p_success += s_cnt
                    p_failed += f_cnt

                    if not is_ok and not self._is_cancelled:
                        self.log_emitted.emit("WARNING", f"[{p_num}] ⚠️ Primary page upload failed. Scanning for backup pages on account...")
                        managed_pages = scan_managed_facebook_pages(page)
                        alt_page = None
                        for pg in managed_pages:
                            if pg.get("asset_id") and len(managed_pages) > 1:
                                alt_page = pg
                                break
                        if alt_page:
                            alt_aid = alt_page["asset_id"]
                            alt_name = alt_page.get("name", "Backup Page")
                            self.log_emitted.emit("INFO", f"[{p_num}] 🔄 Fallback: Retrying upload on alternative Page '{alt_name}' [{alt_aid}]...")
                            alt_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={alt_aid}"
                            is_ok_alt, recs_alt, s_alt, f_alt = self._execute_page_upload(
                                page, context, alt_url, batch_packages, target_paths, p_num, p_name, alt_name, uid=prof_uid, password=prof_pass
                            )
                            p_records.extend(recs_alt)
                            p_success += s_alt
                            p_failed += f_alt
                            if is_ok_alt:
                                self.log_emitted.emit("SUCCESS", f"[{p_num}] 🎉 Fallback upload SUCCEEDED on alternative Page '{alt_name}'!")
                        else:
                            self.log_emitted.emit("WARNING", f"[{p_num}] No alternative pages found on this account to fallback to.")

                elif self.page_mode == "All Pages":
                    self.log_emitted.emit("INFO", f"[{p_num}] 🔍 Scanning all managed pages for account...")
                    managed_pages = scan_managed_facebook_pages(page)
                    if managed_pages:
                        page_names = ", ".join([p["name"] for p in managed_pages])
                        self.log_emitted.emit("INFO", f"[{p_num}] 📑 Discovered {len(managed_pages)} Page(s): {page_names}")
                        for p_idx_pg, pg in enumerate(managed_pages):
                            if self._is_cancelled:
                                break
                            pg_name = pg.get("name", f"Page {p_idx_pg+1}")
                            pg_aid = pg.get("asset_id")
                            pg_url = f"https://business.facebook.com/latest/bulk_upload_composer?asset_id={pg_aid}" if pg_aid else "https://business.facebook.com/latest/bulk_upload_composer?asset_id"
                            self.log_emitted.emit("INFO", f"[{p_num}] 🚀 Posting to Page {p_idx_pg+1}/{len(managed_pages)}: '{pg_name}'...")
                            is_ok_p, recs_p, s_p, f_p = self._execute_page_upload(
                                page, context, pg_url, batch_packages, target_paths, p_num, p_name, pg_name, uid=prof_uid, password=prof_pass
                            )
                            p_records.extend(recs_p)
                            p_success += s_p
                            p_failed += f_p
                            smart_sleep(4.5, 8.0)
                            human_mouse_jitter(page)
                    else:
                        bulk_url = "https://business.facebook.com/latest/bulk_upload_composer?asset_id"
                        is_ok, recs, s_cnt, f_cnt = self._execute_page_upload(
                            page, context, bulk_url, batch_packages, target_paths, p_num, p_name, uid=prof_uid, password=prof_pass
                        )
                        p_records.extend(recs)
                        p_success += s_cnt
                        p_failed += f_cnt

                else:
                    # Default: "Selected Page"
                    bulk_url = "https://business.facebook.com/latest/bulk_upload_composer?asset_id"
                    is_ok, recs, s_cnt, f_cnt = self._execute_page_upload(
                        page, context, bulk_url, batch_packages, target_paths, p_num, p_name, uid=prof_uid, password=prof_pass
                    )
                    p_records.extend(recs)
                    p_success += s_cnt
                    p_failed += f_cnt

        except Exception as ex:
            if not self._is_cancelled:
                self.log_emitted.emit("ERROR", f"[{p_num}] Automation exception: {ex}")
                try:
                    if 'page' in locals() and page:
                        capture_diagnostic_screenshot(
                            page=page,
                            profile_name=p_name,
                            label="exception",
                            reports_dir=self.reports_dir,
                            uid=prof_uid,
                            password=prof_pass,
                            extra_info=str(ex)
                        )
                except Exception:
                    pass
                if not p_records:
                    for pkg in batch_packages:
                        p_records.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "profile_number": p_num,
                            "profile_name": p_name,
                            "video_name": pkg[0].name,
                            "video_path": str(pkg[0]),
                            "title": pkg[1],
                            "desc": pkg[2],
                            "status": "FAILED",
                            "duration": 0,
                            "error": f"Exception: {ex}"
                        })
                    p_failed = len(batch_packages)
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
                with self._lock:
                    if context in self._active_contexts:
                        self._active_contexts.remove(context)

            with self._lock:
                self._active_user_dirs.discard(user_dir)

            kill_profile_chrome_process(user_dir)

            # Instant per-profile real-time Excel reporting (Guaranteed to execute on every profile exit)
            if not self._is_cancelled:
                self.log_emitted.emit("INFO", f"[{p_num}] Profile finished: {p_success} Success, {p_failed} Failed.")
                if p_failed > 0 and p_success == 0:
                    self._move_profile_to_fail_group(profile, p_num)

                if self.excel_report_file:
                    try:
                        if p_success > 0:
                            append_upload_report_record_realtime(self.excel_report_file, {
                                "profile_number": p_num,
                                "uid": prof_uid,
                                "password": prof_pass,
                                "secret_2fa": prof_2fa,
                                "cookie": prof_cookie,
                                "status": "Success",
                                "error": ""
                            })
                            self.log_emitted.emit("SUCCESS", f"[{p_num}] 📊 Live Excel Report: Appended to 'Success' tab.")
                        else:
                            err_list = [r.get("error", "") for r in p_records if r.get("error")]
                            err_detail = "; ".join(dict.fromkeys(err_list)) if err_list else "Upload failed or incomplete"
                            append_upload_report_record_realtime(self.excel_report_file, {
                                "profile_number": p_num,
                                "uid": prof_uid,
                                "password": prof_pass,
                                "secret_2fa": prof_2fa,
                                "cookie": prof_cookie,
                                "status": "Failed",
                                "error": err_detail
                            })
                            self.log_emitted.emit("INFO", f"[{p_num}] 📊 Live Excel Report: Appended to 'Failed' tab.")
                    except Exception as ex_rep:
                        self.log_emitted.emit("WARNING", f"[{p_num}] Excel report append notice: {ex_rep}")

        return p_records, p_success, p_failed
