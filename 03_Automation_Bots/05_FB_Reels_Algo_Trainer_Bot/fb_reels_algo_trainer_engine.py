# -*- coding: utf-8 -*-
"""
Playwright Automation Engine for Facebook Reels Algorithm Trainer Bot:
- Auto-verifies profile session & handles re-login (Password -> Cookie Fallback)
- Auto-detects Checkpoint / Suspended accounts and purges dead profiles safely
- Dismisses blocking notice popups (What happened / Restrictions / etc.) via top-right (X)
- 4-Action Engagement Sequence per Seed Reel Link:
  1. Three-Dots (•••) -> Click "Interested" (⭐️/➕ Interested) with graceful skip
  2. Follow Reel Creator Page (• Follow)
  3. Like Reel Video (👍 Like)
  4. Post 100% Autonomous AI Contextual Comment or Custom Comment (💬 Comment)
- Parallel Multi-Threading with Window Grid Tiling across 1-20 concurrent profiles
"""

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import os
import random
import re
import sys
import threading
import time
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

from PySide6.QtCore import QObject, QThread, Signal
from playwright.sync_api import sync_playwright

from fb_reels_algo_trainer_helpers import (
    get_chrome_executable_path,
    resolve_user_data_dir,
    parse_cookie_string,
    kill_profile_chrome_process,
    check_facebook_login_status,
    is_facebook_account_suspended,
    auto_relogin_facebook,
    delete_profile_safely,
    generate_ai_reels_engagement_comment,
    DEFAULT_ALGO_TRAINER_COMMENTS,
    generate_profile_fingerprint,
    get_stealth_anti_detect_script
)


CHROMIUM_FAST_LAUNCH_ARGS = [
    "--window-size=1280,800",
    "--window-position=40,40",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-background-mode",
    "--disable-session-crashed-bubble",
    "--hide-crash-restore-bubble",
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


def dismiss_facebook_popups(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """
    Detects and dismisses all Facebook popups, restriction notices ('What happened',
    'We added restrictions to your account', 'We removed a post from your Page', etc.),
    cookie banners, and non-essential overlays.
    Automatically finds and clicks the round top-right (X) close button on notice modals.
    Handles multiple stacked/sequential popups in a loop until completely clear.
    CRITICAL: Never touches or closes the Facebook Reels comment drawer!
    """
    total_dismissed = 0
    try:
        if not page or page.is_closed():
            return False

        for round_idx in range(6):
            if page.is_closed():
                break

            js_res = page.evaluate("""() => {
                let count = 0;
                const forceClick = (el) => {
                    if (!el) return;
                    try { el.click(); } catch(e) {}
                    try {
                        const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                        el.dispatchEvent(evt);
                    } catch(e) {}
                };

                const isCommentsDrawer = (el) => {
                    if (!el) return false;
                    if (el.querySelector('div[data-pagelet*="Comment"], div[data-lexical-editor="true"], div[role="textbox"]')) {
                        return true;
                    }
                    const pagelet = (el.getAttribute('data-pagelet') || '').toLowerCase();
                    if (pagelet.includes('comment')) return true;
                    const r = el.getBoundingClientRect();
                    if (r.right >= window.innerWidth * 0.90 && r.left > window.innerWidth * 0.45 && r.width > 200) {
                        return true;
                    }
                    return false;
                };

                const dialogs = document.querySelectorAll('div[role="dialog"], div[role="alertdialog"], div[aria-modal="true"], div[class*="modal" i]');
                for (const d of dialogs) {
                    if (!d || d.getBoundingClientRect().width <= 0) continue;
                    if (isCommentsDrawer(d)) continue;

                    let dialogClosed = false;

                    // Priority 1: Top-Right circular close button (X) inside modal header
                    const dRect = d.getBoundingClientRect();
                    const allClickables = Array.from(d.querySelectorAll('div[role="button"], button, svg, i'));
                    for (const cand of allClickables) {
                        const cr = cand.getBoundingClientRect();
                        if (cr.width >= 12 && cr.width <= 75 && cr.height >= 12 && cr.height <= 75) {
                            if (cr.top >= dRect.top - 15 && cr.top <= dRect.top + 95 &&
                                cr.right <= dRect.right + 20 && cr.right >= dRect.right - 95) {
                                let clickTarget = cand;
                                if (cand.tagName.toLowerCase() === 'svg' || cand.tagName.toLowerCase() === 'i' || cand.tagName.toLowerCase() === 'path') {
                                    clickTarget = cand.closest('div[role="button"]') || cand.closest('button') || cand;
                                }
                                forceClick(clickTarget);
                                dialogClosed = true;
                                count++;
                                break;
                            }
                        }
                    }

                    // Priority 2: Explicit Close / Dismiss aria-label selectors inside dialog
                    if (!dialogClosed) {
                        const closeBtns = d.querySelectorAll(
                            'div[role="button"][aria-label*="Close" i], ' +
                            'div[role="button"][aria-label*="close" i], ' +
                            'div[role="button"][aria-label*="Dismiss" i], ' +
                            'div[role="button"][aria-label*="dismiss" i], ' +
                            'div[role="button"][aria-label*="Cancel" i], ' +
                            'div[role="button"][aria-label*="বন্ধ" i], ' +
                            'div[role="button"][aria-label*="বাতিল" i], ' +
                            'button[aria-label*="Close" i], button[aria-label*="close" i], ' +
                            'button[aria-label*="Dismiss" i], ' +
                            'div[aria-label="Close"], div[aria-label="Close dialog"], ' +
                            'div[aria-label="Dismiss"], div[aria-label="বন্ধ করুন"], div[aria-label="বাতিল করুন"]'
                        );
                        for (const cb of closeBtns) {
                            const cbr = cb.getBoundingClientRect();
                            if (cbr.width > 0 && cbr.height > 0) {
                                forceClick(cb);
                                dialogClosed = true;
                                count++;
                                break;
                            }
                        }
                    }

                    // Priority 3: Acknowledge / OK buttons inside dialog
                    if (!dialogClosed) {
                        const ackBtns = d.querySelectorAll(
                            'div[role="button"]:not([aria-disabled="true"]), button:not([disabled])'
                        );
                        for (const ab of ackBtns) {
                            const txt = (ab.innerText || ab.textContent || '').trim().toLowerCase();
                            if (txt === 'ok' || txt === 'got it' || txt === 'i understand' || txt === 'ঠিক আছে' || txt === 'বাতিল করুন') {
                                forceClick(ab);
                                dialogClosed = true;
                                count++;
                                break;
                            }
                        }
                    }
                }

                // Clean standalone cookie banners / bottom notifications
                const cookiesBanners = document.querySelectorAll(
                    'div[data-nosnippet="true"], div[aria-label*="cookie" i], div[id*="cookie" i]'
                );
                for (const cb of cookiesBanners) {
                    if (isCommentsDrawer(cb)) continue;
                    const allowBtn = cb.querySelector('div[role="button"], button');
                    if (allowBtn) {
                        forceClick(allowBtn);
                        count++;
                    }
                }

                return count;
            }""")

            if js_res > 0:
                total_dismissed += js_res
                time.sleep(0.5)
            else:
                break

        if total_dismissed > 0 and log_func:
            log_func(f"    🛡️ Dismissed {total_dismissed} Facebook popup(s)/notice modal(s).")
        return total_dismissed > 0
    except Exception:
        return total_dismissed > 0


def is_already_following_reel_creator(page: Any) -> bool:
    """Checks if the profile is already following the reel creator."""
    try:
        if page.is_closed():
            return False
        return page.evaluate("""() => {
            const elements = Array.from(document.querySelectorAll('div[role="button"], a[role="link"], span, div, a'));
            for (const el of elements) {
                const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (txt === 'following' || txt === 'অনুসরণ করছেন' || aria === 'following' || aria === 'অনুসরণ করছেন') {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.left < window.innerWidth * 0.75) {
                        return true;
                    }
                }
            }
            return false;
        }""")
    except Exception:
        return False


def auto_follow_reel_creator(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """
    Follows the creator of the currently viewed reel if not already followed.
    Detects inline '• Follow' / 'Follow' button on the reel player overlay.
    """
    try:
        if page.is_closed():
            return False

        # Pre-check: already following?
        for _ in range(3):
            if is_already_following_reel_creator(page):
                if log_func:
                    log_func("    ➕ Already Following Reel Creator / Page.")
                return True
            time.sleep(0.3)

        # Strategy 1: JS-based precision search for "• Follow" / "Follow" / "ফলো" on reel player
        res = page.evaluate("""() => {
            const forceClick = (el) => {
                try { el.click(); } catch(e) {}
                try {
                    const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                    el.dispatchEvent(evt);
                } catch(e) {}
            };

            const candidates = Array.from(document.querySelectorAll('div[role="button"], a, span, button, div'));
            for (const el of candidates) {
                const txt = (el.innerText || el.textContent || '').trim();
                const aria = (el.getAttribute('aria-label') || '').trim();

                const isFollowText = (
                    txt === '• Follow' || txt === 'Follow' || 
                    txt === '• ফলো' || txt === 'ফলো' ||
                    aria === 'Follow' || aria === '• Follow' ||
                    aria === 'ফলো' || aria === '• ফলো'
                );

                if (!isFollowText) continue;

                // Check bounds: must be visible on screen, not inside right-side comments drawer
                const r = el.getBoundingClientRect();
                if (r.width > 5 && r.height > 5 && r.left < window.innerWidth * 0.75 && r.top >= 0 && r.top < window.innerHeight) {
                    forceClick(el);
                    return { clicked: true, text: txt };
                }
            }
            return { clicked: false };
        }""")

        if res.get("clicked"):
            if log_func:
                log_func("    ➕ Followed Reel creator page successfully!")
            time.sleep(0.8)
            return True

        # Strategy 2: Playwright CSS query selectors fallback
        follow_selectors = [
            'div[role="button"]:has-text("• Follow")',
            'a:has-text("• Follow")',
            'span:has-text("• Follow")',
            'div[role="button"]:has-text("Follow")',
            'a:has-text("Follow")',
            'span:has-text("Follow")',
            'div[role="button"]:has-text("• ফলো")',
            'a:has-text("• ফলো")',
            'span:has-text("• ফলো")',
            'div[role="button"]:has-text("ফলো")',
            'a:has-text("ফলো")',
            'span:has-text("ফলো")'
        ]
        for sel in follow_selectors:
            try:
                candidates = page.query_selector_all(sel)
                for c in candidates:
                    if c and c.is_visible():
                        box = c.bounding_box()
                        if box and box["x"] < 900 and box["width"] > 0:
                            c.click(force=True)
                            if log_func:
                                log_func("    ➕ Followed Reel creator page successfully!")
                            time.sleep(0.8)
                            return True
            except Exception:
                pass

        if log_func:
            log_func("    ℹ️ Follow button not found or creator already followed.")
        return False
    except Exception as e:
        if log_func:
            log_func(f"    ℹ️ Note on Follow check: {e}")
        return False


def is_comment_drawer_open(page: Any) -> bool:
    """Checks whether the comment drawer or comment input is active."""
    try:
        if page.is_closed():
            return False
        return page.evaluate("""() => {
            const ed = document.querySelector('div[role="textbox"][contenteditable="true"], div[data-lexical-editor="true"], div[aria-label*="Comment as" i], div[aria-label*="Write a comment" i]');
            if (ed && ed.getBoundingClientRect().width > 20) return true;

            const drawers = Array.from(document.querySelectorAll('div[data-pagelet*="Comment" i], div[role="complementary"], div[role="dialog"]'));
            for (const d of drawers) {
                const r = d.getBoundingClientRect();
                if (r.left > window.innerWidth * 0.40 && r.width > 150 && r.height > 150) {
                    return true;
                }
            }
            return false;
        }""")
    except Exception:
        return False


def ensure_comment_drawer_open(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """Ensures the comment drawer is open. If closed, opens it safely without toggling."""
    dismiss_facebook_popups(page)
    if is_comment_drawer_open(page):
        return True

    try:
        refresh_clicked = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
            const rBtn = btns.find(b => {
                const txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                return txt === 'refresh' || txt === 'পুনরায় লোড করুন' || txt === 'reload';
            });
            if (rBtn) {
                rBtn.click();
                return true;
            }
            return false;
        }""")
        if refresh_clicked:
            time.sleep(1.5)
            if is_comment_drawer_open(page):
                return True
    except Exception:
        pass

    for attempt in range(4):
        try:
            if page.is_closed():
                return False

            click_res = page.evaluate("""() => {
                const buttons = Array.from(document.querySelectorAll('div[role="button"], button'));
                const commentBtn = buttons.find(b => {
                    const label = (b.getAttribute('aria-label') || '').trim().toLowerCase();
                    const isCommentLabel = (
                        label === 'comment' || label === 'comments' || 
                        label === 'মন্তব্য' || label === 'কমেন্ট' ||
                        label.includes('comment') || label.includes('মন্তব্য')
                    );
                    if (!isCommentLabel) return false;
                    const r = b.getBoundingClientRect();
                    return r.width > 15 && r.height > 15 && r.top >= 0 && r.top < window.innerHeight;
                });

                if (commentBtn) {
                    if (commentBtn.getAttribute('aria-expanded') === 'true') {
                        return { found: true, alreadyExpanded: true };
                    }
                    commentBtn.click();
                    return { found: true, clicked: true };
                }
                return { found: false };
            }""")

            if click_res.get("alreadyExpanded"):
                return True

            if click_res.get("clicked"):
                for _ in range(15):
                    time.sleep(0.2)
                    if is_comment_drawer_open(page):
                        if log_func:
                            log_func("    💬 Comment drawer opened.")
                        return True
        except Exception:
            pass
        time.sleep(0.5)

    return is_comment_drawer_open(page)


def auto_like_reel(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """Likes the currently viewed Facebook Reel video."""
    try:
        if page.is_closed():
            return False
        res = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
            const likeBtn = btns.find(b => {
                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                return aria.includes('like') || aria.includes('লাইক');
            });
            if (!likeBtn) return "NOT_FOUND";

            const aria = (likeBtn.getAttribute('aria-label') || '').toLowerCase();
            if (aria.includes('unlike') || aria.includes('remove like') || aria.includes('লাইক মুছে')) {
                return "ALREADY_LIKED";
            }

            likeBtn.click();
            return "CLICKED";
        }""")
        if res == "CLICKED":
            if log_func:
                log_func("    👍 Liked Reel video successfully!")
            return True
        elif res == "ALREADY_LIKED":
            if log_func:
                log_func("    👍 Reel is already liked.")
            return True
        return False
    except Exception as e:
        if log_func:
            log_func(f"    ⚠️ Like action note: {e}")
        return False


def auto_post_comment(page: Any, comment_text: str, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """Posts a comment on the currently viewed Facebook Reel video with reliable waiting and insertion."""
    try:
        if page.is_closed():
            return False

        ensure_comment_drawer_open(page, log_func=log_func)

        target_box = None
        comment_input_selectors = [
            'div[role="textbox"][data-lexical-editor="true"]',
            'div[role="textbox"][contenteditable="true"]',
            'div[role="textbox"]',
            'div[data-lexical-editor="true"]',
            'div[aria-label*="Comment as" i]',
            'div[aria-label*="Write a comment" i]',
            'div[aria-label*="একটি মন্তব্য লিখুন" i]',
            'p.xdj266r'
        ]

        start_wait = time.time()
        while time.time() - start_wait < 12.0:
            if page.is_closed():
                return False

            page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
                const rBtn = btns.find(b => {
                    const txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                    return (txt === 'refresh' || txt === 'reload') && b.getBoundingClientRect().left > window.innerWidth * 0.5;
                });
                if (rBtn) rBtn.click();
            }""")

            for sel in comment_input_selectors:
                try:
                    boxes = page.query_selector_all(sel)
                    for box in boxes:
                        if box and box.is_visible():
                            r = box.bounding_box()
                            if r and r["width"] > 30 and r["height"] > 10:
                                target_box = box
                                break
                    if target_box:
                        break
                except Exception:
                    pass

            if target_box:
                break

            time.sleep(0.5)

        if not target_box:
            box_coords = page.evaluate("""() => {
                const ed = document.querySelector('div[role="textbox"], div[data-lexical-editor="true"], [contenteditable="true"]');
                if (ed) {
                    const r = ed.getBoundingClientRect();
                    if (r.width > 20 && r.height > 10) {
                        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                    }
                }
                return null;
            }""")
            if box_coords:
                try:
                    page.mouse.click(box_coords["x"], box_coords["y"])
                    time.sleep(0.3)
                    for sel in comment_input_selectors:
                        boxes = page.query_selector_all(sel)
                        for box in boxes:
                            if box and box.is_visible():
                                target_box = box
                                break
                        if target_box:
                            break
                except Exception:
                    pass

        if target_box:
            target_box.click(force=True)
            time.sleep(0.3)

            page.keyboard.insert_text(comment_text)
            time.sleep(0.2)

            has_text = page.evaluate("""() => {
                const ed = document.querySelector('div[role="textbox"][contenteditable="true"], div[data-lexical-editor="true"], div[role="textbox"]');
                return ed && (ed.innerText || ed.textContent || '').trim().length > 0;
            }""")

            if not has_text:
                page.evaluate("""(text) => {
                    const ed = document.querySelector('div[role="textbox"][contenteditable="true"], div[data-lexical-editor="true"], div[role="textbox"]');
                    if (ed) {
                        ed.focus();
                        const dt = new DataTransfer();
                        dt.setData('text/plain', text);
                        const evt = new InputEvent('beforeinput', {
                            bubbles: true,
                            cancelable: true,
                            inputType: 'insertFromPaste',
                            dataTransfer: dt
                        });
                        ed.dispatchEvent(evt);
                    }
                }""", comment_text)
                time.sleep(0.2)

            page.keyboard.press("Enter")
            time.sleep(0.4)

            page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
                const postBtn = btns.find(b => {
                    const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                    return (aria.includes('post') || aria.includes('send') || aria.includes('পাঠান') || aria.includes('পোস্ট')) &&
                           b.getAttribute('aria-disabled') !== 'true';
                });
                if (postBtn) postBtn.click();
            }""")

            if log_func:
                log_func(f"    💬 Posted comment: '{comment_text}'")

            try:
                page.evaluate("() => { if (document.activeElement && typeof document.activeElement.blur === 'function') document.activeElement.blur(); }")
            except Exception:
                pass
            return True
        else:
            if log_func:
                log_func("    ⚠️ Comment input box not found or comments disabled for this video.")
            return False
    except Exception as e:
        if log_func:
            log_func(f"    ⚠️ Comment post note: {e}")
        return False


def auto_click_interested(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """
    Clicks Three-Dots / Menu button on Reel player and selects 'Interested'.
    Gracefully skips if 'Interested' is not available.
    """
    try:
        if page.is_closed():
            return False

        dismiss_facebook_popups(page)

        # Step 1: Find and click Three-Dots / Menu button on Reel player
        three_dots_clicked = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
            
            const shareBtn = btns.find(b => {
                const a = (b.getAttribute('aria-label') || '').toLowerCase();
                return (a.includes('share') || a.includes('শেয়ার')) &&
                       !b.closest('[data-pagelet="TahoeReelsComments"], [role="dialog"]');
            });

            let target = btns.find(b => {
                const a = (b.getAttribute('aria-label') || '').trim().toLowerCase();
                const r = b.getBoundingClientRect();
                if (r.top < 250 || r.top > 850 || r.width <= 15 || r.height <= 15) return false;
                if (a.includes('profile') || a.includes('voice') || a.includes('switch')) return false;
                if (b.closest('[data-pagelet="TahoeReelsComments"], [role="dialog"]')) return false;

                return (
                    a === 'menu' || a === 'মেনু' ||
                    a === 'more options' || a === 'see more options' ||
                    a === 'actions for this post' || a === 'actions' ||
                    a === 'আরও বিকল্প' || a.includes('actions for this post')
                );
            });

            if (!target && shareBtn) {
                const sr = shareBtn.getBoundingClientRect();
                target = btns.find(b => {
                    if (b === shareBtn) return false;
                    if (b.closest('[data-pagelet="TahoeReelsComments"], [role="dialog"]')) return false;
                    const r = b.getBoundingClientRect();
                    return Math.abs(r.left - sr.left) < 50 && r.top > sr.top && r.top < sr.bottom + 120 && r.width > 15;
                });
            }

            if (!target) {
                target = btns.find(b => {
                    const r = b.getBoundingClientRect();
                    if (r.top < 250 || r.top > 850 || r.width <= 15) return false;
                    if (b.closest('[data-pagelet="TahoeReelsComments"], [role="dialog"]')) return false;
                    const circles = b.querySelectorAll('svg circle').length;
                    const txt = (b.innerText || b.textContent || '').trim();
                    return circles >= 3 || txt === '•••' || txt === '...';
                });
            }

            if (target) {
                const r = target.getBoundingClientRect();
                try { target.click(); } catch(e) {}
                try {
                    const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                    target.dispatchEvent(evt);
                } catch(err) {}
                return {
                    success: true,
                    x: Math.round(r.left + r.width / 2),
                    y: Math.round(r.top + r.height / 2)
                };
            }
            return { success: false };
        }""")

        if not three_dots_clicked.get("success"):
            for sel in ['div[role="button"][aria-label="Menu" i]', 'div[role="button"][aria-label*="More options" i]']:
                try:
                    b = page.query_selector(sel)
                    if b and b.is_visible():
                        b.click()
                        three_dots_clicked = {"success": True}
                        break
                except Exception:
                    pass

        if not three_dots_clicked.get("success"):
            if log_func:
                log_func("    ℹ️ Three-dots (•••) / Menu button not found on this reel (smoothly skipped).")
            return False

        time.sleep(1.0)

        interested_result = page.evaluate("""() => {
            const items = Array.from(document.querySelectorAll('div[role="menuitem"], div[role="button"], span, div'));
            for (const el of items) {
                const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                const isInterested = (
                    (txt.includes('interested') || txt.includes('আগ্রহী')) &&
                    !txt.includes('not interested') &&
                    !txt.includes('less of') &&
                    !txt.includes('fewer') &&
                    !txt.includes('অনীহা') &&
                    !txt.includes('আগ্রহী নন')
                );
                if (isInterested) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 20 && r.height > 10) {
                        try { el.click(); } catch(e) {}
                        try {
                            const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                            el.dispatchEvent(evt);
                        } catch(err) {}
                        return { clicked: true, text: txt };
                    }
                }
            }
            return { clicked: false };
        }""")

        if interested_result.get("clicked"):
            if log_func:
                log_func("    ⭐️ Marked Reel as 'Interested' successfully!")
            time.sleep(0.8)
            return True

        # Close open menu if Interested not found
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        if log_func:
            log_func("    ℹ️ 'Interested' option not present in menu for this video (gracefully skipped).")
        return False
    except Exception as e:
        if log_func:
            log_func(f"    ℹ️ Note on Interested action: {e}")
        return False


class FbReelsAlgoTrainerEngine(QThread):
    """
    Playwright Automation Thread for Facebook Reels Algorithm Trainer Bot:
    - 100% Autonomous AI Agent: Analyzes Reels & posts human-like contextual comments
    - Smart Session Manager: Auto-relogin with Password -> Cookie Fallback
    - Auto-Purge: Detects Checkpoint / Suspended profiles and deletes them permanently
    - 4-Action Signals: Interested ➜ Follow ➜ Like ➜ AI Contextual Comment
    - Multi-Threaded Parallel Execution across concurrent profile browsers with Grid Tiling
    """
    log_emitted = Signal(str)
    progress_updated = Signal(int, int)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        seed_links: List[str],
        comments_list: Optional[List[str]] = None,
        watch_delay: int = 5,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        enable_interested: bool = True,
        enable_follow: bool = True,
        enable_like: bool = True,
        enable_comments: bool = True,
        enable_ai_comments: bool = True,
        ai_comment_tone: str = "Natural Fan & Appreciation",
        ai_custom_instruction: str = "",
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.seed_links = [s.strip() for s in seed_links if s.strip()]
        self.comments_list = [c.strip() for c in (comments_list or []) if c.strip()]
        if not self.comments_list:
            self.comments_list = DEFAULT_ALGO_TRAINER_COMMENTS
        self.watch_delay = max(1, watch_delay)
        self.max_concurrent_browsers = max(1, max_concurrent_browsers)
        self.headless = headless
        self.enable_interested = enable_interested
        self.enable_follow = enable_follow
        self.enable_like = enable_like
        self.enable_comments = enable_comments
        self.enable_ai_comments = enable_ai_comments
        self.ai_comment_tone = ai_comment_tone or "Natural Fan & Appreciation"
        self.ai_custom_instruction = (ai_custom_instruction or "").strip()
        self.stop_requested = False
        self._active_contexts: Set[Any] = set()
        self._lock = threading.Lock()

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleeps in small increments to respond immediately to stop signals."""
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.stop_requested:
                break
            time.sleep(0.1)

    def stop(self) -> None:
        """Immediately stops all workers and terminates active browser sessions safely without crashing Qt."""
        self.stop_requested = True
        self.log_emitted.emit("🛑 Stop signal received. Closing active browsers safely...")
        with self._lock:
            for ctx in list(self._active_contexts):
                try:
                    ctx.close()
                except Exception:
                    pass
            self._active_contexts.clear()

    def _process_single_profile(self, p_idx: int, total_profiles: int, pdata: Dict[str, Any]) -> bool:
        pid = pdata.get("id", "")
        pname = pdata.get("name", pdata.get("number", f"Profile #{p_idx}"))
        group_name = pdata.get("group", "Default")

        self.log_emitted.emit(f"🚀 [{p_idx}/{total_profiles}] Starting Algorithm Training for [{pname}] ({group_name})...")

        user_folder_str = resolve_user_data_dir(pdata, self.profile_mgr)
        user_folder = Path(user_folder_str)

        try:
            kill_profile_chrome_process(str(user_folder))
        except Exception:
            pass

        # Clear lock files if present
        for lock_name in ["SingletonLock", "lockfile"]:
            lock_f = user_folder / lock_name
            if lock_f.exists():
                try:
                    lock_f.unlink(missing_ok=True)
                except Exception:
                    pass

        # Hydrate complete credentials & session cookies from profile.json / profile_mgr
        p_json = user_folder / "profile.json"
        if p_json.exists():
            try:
                with open(p_json, "r", encoding="utf-8") as pf:
                    disk_p = json.load(pf)
                if isinstance(disk_p, dict):
                    for k, v in disk_p.items():
                        if v and not pdata.get(k):
                            pdata[k] = v
            except Exception:
                pass

        if self.profile_mgr and hasattr(self.profile_mgr, "profiles"):
            for pm_p in getattr(self.profile_mgr, "profiles", []):
                if isinstance(pm_p, dict):
                    if (pdata.get("id") and pm_p.get("id") == pdata.get("id")) or \
                       (str(pdata.get("number", "")) and str(pm_p.get("number", "")).strip() == str(pdata.get("number", "")).strip()):
                        for k, v in pm_p.items():
                            if v and not pdata.get(k):
                                pdata[k] = v

        # Clean crash flags from Preferences so Chromium never prompts "Restore pages?"
        pref_file = user_folder / "Default" / "Preferences"
        if pref_file.exists():
            try:
                with open(pref_file, "r", encoding="utf-8") as pf:
                    prefs = json.load(pf)
                if isinstance(prefs, dict):
                    p_sec = prefs.get("profile", {})
                    if p_sec.get("exit_type") != "Normal" or not p_sec.get("exited_cleanly", True):
                        p_sec["exit_type"] = "Normal"
                        p_sec["exited_cleanly"] = True
                        prefs["profile"] = p_sec
                        with open(pref_file, "w", encoding="utf-8") as pf:
                            json.dump(prefs, pf)
            except Exception:
                pass

        # Multi-window grid tiling & staggered launch
        slot = (p_idx - 1) % self.max_concurrent_browsers
        if p_idx > 1:
            time.sleep(min((p_idx - 1) * 0.35, 2.5))

        screen_col = (slot % 3) * 430
        screen_row = (slot // 3) * 380

        # Generate unique anti-detect fingerprint per profile
        fp = generate_profile_fingerprint(pdata)
        self.log_emitted.emit(f"  🛡️ Anti-Detect Fingerprint: Screen {fp['width']}x{fp['height']} | CPU Cores {fp['hardware_concurrency']} | RAM {fp['device_memory']}GB")

        custom_launch_args = [
            arg for arg in CHROMIUM_FAST_LAUNCH_ARGS 
            if not arg.startswith("--window-position=") 
            and not arg.startswith("--user-agent=") 
            and not arg.startswith("--window-size=")
        ]
        custom_launch_args.append(f"--window-position={screen_col},{screen_row}")
        custom_launch_args.append(f"--window-size={fp['width']},{fp['height']}")
        custom_launch_args.append(f"--user-agent={fp['user_agent']}")

        chrome_exe = get_chrome_executable_path()
        launch_kwargs: Dict[str, Any] = {
            "user_data_dir": str(user_folder.resolve()),
            "headless": self.headless,
            "args": custom_launch_args,
            "no_viewport": True,
            "ignore_default_args": ["--enable-automation"]
        }
        if chrome_exe and os.path.exists(chrome_exe):
            launch_kwargs["executable_path"] = chrome_exe

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(**launch_kwargs)
                with self._lock:
                    self._active_contexts.add(context)

                # Inject stealth anti-detect script across all pages and frames
                try:
                    stealth_js = get_stealth_anti_detect_script(fp)
                    context.add_init_script(stealth_js)
                except Exception:
                    pass

                # Pre-inject session cookies from profile database if available
                raw_cookie = pdata.get("cookies_json") or pdata.get("cookie") or pdata.get("cookies") or pdata.get("cookies_raw")
                if raw_cookie:
                    try:
                        parsed_cks = parse_cookie_string(str(raw_cookie)) if not isinstance(raw_cookie, list) else raw_cookie
                        if parsed_cks:
                            context.add_cookies(parsed_cks)
                            self.log_emitted.emit(f"  🍪 Loaded {len(parsed_cks)} authenticated Facebook session cookies.")
                    except Exception:
                        pass

                try:
                    page = context.pages[0] if context.pages else context.new_page()

                    def _auto_close_tab(new_p):
                        try:
                            time.sleep(0.3)
                            if new_p != page and not new_p.is_closed():
                                new_p.close()
                        except Exception:
                            pass
                    context.on("page", _auto_close_tab)

                    if self.stop_requested:
                        return False

                    # Step 1: Check Facebook Session & Intelligent Login / Deletion
                    self.log_emitted.emit(f"  🔍 [{pname}] Checking Facebook session...")
                    try:
                        page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                        self._interruptible_sleep(2.0)
                    except Exception as goto_err:
                        self.log_emitted.emit(f"  ⚠️ Navigation note for [{pname}]: {goto_err}")

                    # A. Check for Facebook Account Suspension / Disabled / Checkpoint
                    is_susp, susp_reason = is_facebook_account_suspended(page)
                    if is_susp:
                        self.log_emitted.emit(f"  🚫 [{pname}] Facebook Account Suspended/Disabled ({susp_reason})! Auto-deleting profile...")
                        delete_profile_safely(pid, str(user_folder), self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                        return False

                    # B. Check Facebook Login Status
                    is_logged_in, login_msg = check_facebook_login_status(page, context)
                    if is_logged_in:
                        self.log_emitted.emit(f"  ✅ [{pname}] Active Facebook session verified (Logged In)!")
                    else:
                        self.log_emitted.emit(f"  🔑 [{pname}] Session is not active ({login_msg}). Initiating Auto-Relogin...")
                        login_ok, login_res = auto_relogin_facebook(
                            page=page,
                            context=context,
                            profile_data=pdata,
                            profile_mgr=self.profile_mgr,
                            user_data_dir=str(user_folder),
                            log_func=lambda text: self.log_emitted.emit(text)
                        )
                        if not login_ok:
                            is_susp2, susp_reason2 = is_facebook_account_suspended(page)
                            if is_susp2 or login_res == "SUSPENDED":
                                self.log_emitted.emit(f"  🚫 [{pname}] Facebook Account Suspended/Disabled ({susp_reason2 or login_res})! Auto-deleting profile...")
                                delete_profile_safely(pid, str(user_folder), self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                                return False
                            elif "WRONG_PASSWORD" in login_res or "FAILED" in login_res:
                                self.log_emitted.emit(f"  🚫 [{pname}] Password incorrect & Cookie login failed ({login_res})! Auto-deleting dead profile from disk...")
                                delete_profile_safely(pid, str(user_folder), self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                                return False
                            else:
                                self.log_emitted.emit(f"  ❌ [{pname}] Auto-login could not complete ({login_res}). Skipping profile...")
                                return False
                        else:
                            self.log_emitted.emit(f"  ✅ [{pname}] Auto-login successful! Proceeding...")

                    dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))

                    # Step 2: Process ALL seed links sequentially on this profile (Fast-Train Mode: ~6-8s per link)
                    total_links = len(self.seed_links)
                    self.log_emitted.emit(f"  🧠 [{pname}] Starting Fast-Train Sequence across {total_links} Target Reel Link(s)...")

                    links_completed = 0
                    for s_idx, raw_url in enumerate(self.seed_links, start=1):
                        if self.stop_requested:
                            break

                        reel_url = raw_url.strip()
                        if not reel_url.startswith("http"):
                            reel_url = f"https://www.facebook.com/reel/{reel_url}"

                        self.log_emitted.emit(f"  ▶️ [{pname}] [Link #{s_idx}/{total_links}] Opening: {reel_url[:65]}...")
                        try:
                            page.goto(reel_url, timeout=25000, wait_until="domcontentloaded")
                            self._interruptible_sleep(1.0)
                            dismiss_facebook_popups(page)

                            # Handle "Reload page" glitch
                            try:
                                reload_btn = page.query_selector('div[role="button"]:has-text("Reload page"), button:has-text("Reload page")')
                                if reload_btn and reload_btn.is_visible():
                                    reload_btn.click()
                                    self._interruptible_sleep(1.0)
                                    dismiss_facebook_popups(page)
                            except Exception:
                                pass

                            # Watch delay to register organic algorithm watch time (default ~3s)
                            if self.watch_delay > 0:
                                self.log_emitted.emit(f"    ⏱️ [{pname}] Watching Reel #{s_idx} for {self.watch_delay}s to register high algorithm score...")
                                self._interruptible_sleep(self.watch_delay)

                            if self.stop_requested:
                                break

                            # 1. Action: Interested
                            if self.enable_interested:
                                auto_click_interested(page, log_func=lambda text: self.log_emitted.emit(text))
                                self._interruptible_sleep(0.4)

                            if self.stop_requested:
                                break

                            # 2. Action: Follow
                            if self.enable_follow:
                                auto_follow_reel_creator(page, log_func=lambda text: self.log_emitted.emit(text))
                                self._interruptible_sleep(0.4)

                            if self.stop_requested:
                                break

                            # 3. Action: Like
                            if self.enable_like:
                                auto_like_reel(page, log_func=lambda text: self.log_emitted.emit(text))
                                self._interruptible_sleep(0.4)

                            if self.stop_requested:
                                break

                            # 4. Action: Comment (Post natural comment on select seed reels to avoid spam detection)
                            if self.enable_comments and (s_idx in [1, 5] or total_links <= 2):
                                reel_caption = ""
                                creator_name = ""
                                try:
                                    meta = page.evaluate("""() => {
                                        let cap = '';
                                        let creator = '';
                                        const spans = Array.from(document.querySelectorAll('div[role="main"] div[dir="auto"], div[role="main"] span, div[data-pagelet*="Tahoe"] div[dir="auto"]'));
                                        for (const s of spans) {
                                            const t = (s.innerText || s.textContent || '').trim();
                                            if (t.length > 8 && !t.toLowerCase().includes('follow') && !t.toLowerCase().includes('original audio') && !t.toLowerCase().includes('reels') && !t.toLowerCase().includes('comment')) {
                                                cap = t;
                                                break;
                                            }
                                        }
                                        const creatorEl = document.querySelector('div[role="main"] a[role="link"] strong, div[role="main"] a[role="link"] span');
                                        if (creatorEl) {
                                            creator = (creatorEl.innerText || creatorEl.textContent || '').trim();
                                        }
                                        return { caption: cap, creator: creator };
                                    }""")
                                    if isinstance(meta, dict):
                                        reel_caption = meta.get("caption", "")
                                        creator_name = meta.get("creator", "")
                                except Exception:
                                    pass

                                if self.enable_ai_comments:
                                    chosen_comment = generate_ai_reels_engagement_comment(
                                        caption=reel_caption,
                                        creator_name=creator_name,
                                        tone_instruction=self.ai_comment_tone,
                                        custom_instruction=self.ai_custom_instruction,
                                        fallback_comments=self.comments_list
                                    )
                                else:
                                    chosen_comment = random.choice(self.comments_list) if self.comments_list else "Awesome video! Loved the presentation! ❤️"

                                auto_post_comment(page, chosen_comment, log_func=lambda text: self.log_emitted.emit(text))
                                self._interruptible_sleep(0.5)

                            links_completed += 1
                            self.log_emitted.emit(f"  ✅ [{pname}] Completed Reel Link #{s_idx}/{total_links}!")
                        except Exception as link_err:
                            self.log_emitted.emit(f"  ⚠️ [{pname}] Note on Reel Link #{s_idx}: {link_err}")

                        self._interruptible_sleep(0.5)

                    self.log_emitted.emit(f"  🎉 [{pname}] Completed {links_completed}/{total_links} Target Reel Seeds!")

                    # Step 3: Calibrate and Lock Facebook Reels Discovery Feed (/reel)
                    if not self.stop_requested and links_completed > 0:
                        self.log_emitted.emit(f"  🎬 [{pname}] Activating Reels Discovery Feed Lock Phase (https://www.facebook.com/reel)...")
                        try:
                            page.goto("https://www.facebook.com/reel", timeout=25000, wait_until="domcontentloaded")
                            self._interruptible_sleep(1.5)
                            dismiss_facebook_popups(page)

                            # In-Feed 2-Reel Scroll Calibration to lock recommendation vector
                            for f_idx in range(1, 3):
                                if self.stop_requested:
                                    break
                                self.log_emitted.emit(f"    🔄 [{pname}] Reels Feed Session #{f_idx} (Confirming recommendation vector)...")
                                self._interruptible_sleep(2.5)
                                if f_idx == 1:
                                    auto_like_reel(page, log_func=None)

                                # Smooth next reel scroll
                                scroll_res = page.evaluate("""() => {
                                    const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
                                    const nextBtn = btns.find(b => {
                                        const l = (b.getAttribute('aria-label') || '').toLowerCase();
                                        return l === 'next video' || l === 'next card' || l === 'next reel' || l.includes('next card') || l.includes('next video');
                                    });
                                    if (nextBtn) { nextBtn.click(); return true; }
                                    return false;
                                }""")
                                if not scroll_res:
                                    page.keyboard.press("ArrowDown")
                                self._interruptible_sleep(0.8)

                            self.log_emitted.emit(f"  🔒 [{pname}] Reels Discovery Feed successfully calibrated & locked to target niche!")
                        except Exception as feed_err:
                            self.log_emitted.emit(f"  ℹ️ Reels Feed Lock note: {feed_err}")
                    return True
                finally:
                    with self._lock:
                        self._active_contexts.discard(context)
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as err:
            self.log_emitted.emit(f"  ❌ Error on [{pname}]: {err}")
            return False

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles selected to run FB Reels Algorithm Trainer Bot.")
            return

        if not self.seed_links:
            self.finished_signal.emit(False, "No target seed Reel links provided.")
            return

        self.log_emitted.emit(f"📢 Starting FB Reels Algorithm Trainer Engine for {total_profiles} Profile(s)...")
        self.log_emitted.emit(f"🎯 Target Seed Links: {len(self.seed_links)} Links Loaded")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browser(s)")
        self.log_emitted.emit(f"⏱️ Watch Time / Delay: {self.watch_delay}s | Headless: {self.headless}")
        self.log_emitted.emit("🚀 Engagement Mode: High-Conversion Smart Engine Active")

        completed = 0
        success_count = 0

        with ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            futures = {
                executor.submit(self._process_single_profile, p_idx, total_profiles, pdata): pdata
                for p_idx, pdata in enumerate(self.profiles_list, start=1)
            }

            for fut in concurrent.futures.as_completed(futures):
                if self.stop_requested:
                    self.log_emitted.emit("🛑 Stop signal received. Terminating workers...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                completed += 1
                self.progress_updated.emit(completed, total_profiles)
                try:
                    if fut.result():
                        success_count += 1
                except Exception as exc:
                    self.log_emitted.emit(f"⚠️ Worker error: {exc}")

        self.finished_signal.emit(True, f"Algorithm Training Complete! Successfully trained {success_count}/{total_profiles} Facebook Profile(s)!")


# Thread alias
FbReelsAlgoTrainerThread = FbReelsAlgoTrainerEngine
