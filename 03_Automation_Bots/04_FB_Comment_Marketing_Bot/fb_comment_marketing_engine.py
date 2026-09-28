# -*- coding: utf-8 -*-
"""
Playwright Automation Engine for Facebook Reels Comment Marketing Bot:
- Auto-verifies profile session & handles re-login
- Dismisses blocking popups and notices
- Priming phase (optional seed reels)
- Navigates Reels feed (https://www.facebook.com/reel)
- Scans right-hand comments drawer for target keywords / links (e.g. WhatsApp, Telegram, etc.)
- When a keyword matches, humanized types and posts the marketing comment
- Verifies comment is posted and stays visible
- Smooth mouse wheel scrolling to next reel
- Multi-threaded execution across multiple profile workers
"""

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import random
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

from PySide6.QtCore import QObject, QThread, Signal
from playwright.sync_api import sync_playwright

from fb_comment_marketing_helpers import (
    get_chrome_executable_path,
    resolve_user_data_dir,
    parse_cookie_string,
    kill_profile_chrome_process,
    generate_ai_comment,
    is_facebook_account_suspended,
    auto_relogin_facebook,
    delete_profile_safely,
    VIRAL_ENGLISH_HOOKS,
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
                    // 1. Never touch elements containing comment textbox / editor
                    if (el.querySelector('div[data-pagelet*="Comment"], div[data-lexical-editor="true"], div[role="textbox"]')) {
                        return true;
                    }
                    const pagelet = (el.getAttribute('data-pagelet') || '').toLowerCase();
                    if (pagelet.includes('comment')) return true;
                    // 2. Reels comments drawer is docked on the right side of the screen
                    const r = el.getBoundingClientRect();
                    if (r.right >= window.innerWidth * 0.90 && r.left > window.innerWidth * 0.45 && r.width > 200) {
                        return true;
                    }
                    return false;
                };

                // Target all modal dialogs (centered notices, warnings, overlays)
                const dialogs = document.querySelectorAll('div[role="dialog"], div[role="alertdialog"], div[aria-modal="true"]');
                for (const d of dialogs) {
                    if (!d || d.getBoundingClientRect().width <= 0) continue;
                    if (isCommentsDrawer(d)) continue;

                    // Dismiss modals including warnings/notices via close button
                    let dialogClosed = false;

                // Priority 0: Explicit AI Content / Added AI label dialogs
                const aiModals = Array.from(document.querySelectorAll('div[role="dialog"], div[aria-modal="true"]')).filter(el => {
                    const txt = (el.innerText || el.textContent || '').toLowerCase();
                    return txt.includes('ai content') || txt.includes('added an ai label') || txt.includes('identifying ai content');
                });
                for (const am of aiModals) {
                    const cb = am.querySelector('div[role="button"][aria-label*="Close" i], div[role="button"][aria-label*="Dismiss" i], button[aria-label*="Close" i], button, div[role="button"]');
                    if (cb) {
                        const target = cb.closest('div[role="button"]') || cb.closest('button') || cb;
                        forceClick(target);
                        dialogClosed = true;
                        count++;
                    }
                }

                // Priority 1: Top-Right circular close button (X) inside modal header
                // Directly matches the close button requested by user in all notice modals
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

                    // Priority 3: Fallback action buttons (Continue, OK, Got it, Review details, See why)
                    if (!dialogClosed) {
                        const actionBtns = d.querySelectorAll('div[role="button"], button');
                        for (const btn of actionBtns) {
                            const txt = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                            if (["ok", "got it", "continue", "dismiss", "close", "review details", "see why", "ঠিক আছে", "চালিয়ে যান", "বন্ধ করুন"].includes(txt)) {
                                forceClick(btn);
                                dialogClosed = true;
                                count++;
                                break;
                            }
                        }
                    }
                }

                // Also check for standalone cookie banners or notification prompts (excluding comments drawer)
                const popSelectors = [
                    'div[aria-label*="Close notification" i]',
                    'div[aria-label*="Dismiss notification" i]',
                    'div[aria-label*="Not now" i]',
                    'div[role="button"]:has-text("Not now")',
                    'div[role="button"]:has-text("এখন নয়")',
                    'div[aria-label="Decline optional cookies"]',
                    'div[aria-label="Allow all cookies"]',
                    'div[aria-label="Only allow essential cookies"]'
                ];
                for (const sel of popSelectors) {
                    try {
                        const elems = document.querySelectorAll(sel);
                        for (const el of elems) {
                            if (!el || isCommentsDrawer(el)) continue;
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.left < window.innerWidth * 0.85) {
                                forceClick(el);
                                count++;
                            }
                        }
                    } catch(e) {}
                }

                // Check if any non-drawer modal dialog remains visible
                const remainingModals = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"], div[aria-modal="true"]'))
                    .filter(el => el.getBoundingClientRect().width > 0 && !isCommentsDrawer(el));

                return { count, hasRemaining: remainingModals.length > 0 };
            }""")

            closed_in_round = js_res.get("count", 0) if isinstance(js_res, dict) else 0
            has_remaining = js_res.get("hasRemaining", False) if isinstance(js_res, dict) else False

            if closed_in_round > 0:
                total_dismissed += closed_in_round
                time.sleep(0.3)

            # Fallback: If a non-drawer modal dialog is still open after JS attempt, press Escape key
            if has_remaining:
                try:
                    page.keyboard.press("Escape")
                    time.sleep(0.3)
                    total_dismissed += 1
                except Exception:
                    pass
            elif closed_in_round == 0:
                # No popups found or closed in this round, clean!
                break

        if total_dismissed > 0 and log_func:
            log_func(f"    🛡️ Dismissed {total_dismissed} Facebook popup(s)/notice modal(s).")
        return total_dismissed > 0
    except Exception:
        return total_dismissed > 0


def is_already_following_reel_creator(page: Any) -> bool:
    """Checks if the profile is already following the reel creator."""
    try:
        res = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('div[role="button"], a[role="link"], span'));
            for (const b of btns) {
                const txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                if (txt === 'following' || txt === 'অনুসরণ করছেন' || aria.includes('following') || aria.includes('অনুসরণ করছেন')) {
                    const r = b.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.top < window.innerHeight * 0.45) {
                        return true;
                    }
                }
            }
            return false;
        }""")
        return bool(res)
    except Exception:
        return False


def auto_follow_facebook_reel_creator(page: Any, log_func: Optional[Any] = None) -> bool:
    """Follows the creator of the currently viewed reel if not already followed."""
    try:
        try:
            page.evaluate("""() => {
                if (document.activeElement && typeof document.activeElement.blur === 'function') {
                    document.activeElement.blur();
                }
            }""")
            time.sleep(0.3)
        except Exception:
            pass

        if is_already_following_reel_creator(page):
            if log_func:
                log_func("    ➕ Already Following Reel Creator / Page.")
            return True

        follow_selectors = [
            'a:has-text("Follow")',
            'a:has-text("• Follow")',
            'a:has-text("ফলো")',
            'div[role="button"]:has-text("• Follow")',
            'div[role="button"]:has-text("• ফলো")',
            'div[role="button"]:has-text("Follow")',
            'div[role="button"]:has-text("ফলো")',
        ]
        for sel in follow_selectors:
            try:
                candidates = page.query_selector_all(sel)
                for c in candidates:
                    if c and c.is_visible():
                        box = c.bounding_box()
                        if box and box["y"] < 350 and box["width"] > 0:
                            c.click(force=True)
                            if log_func:
                                log_func("    ➕ Followed Reel creator successfully!")
                            time.sleep(1.0)
                            return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def check_for_facebook_comment_limit(page: Any) -> Tuple[bool, str]:
    """
    Detects if Facebook temporarily blocked / limited commenting on this profile.
    Handles smart quotes ('’' and '"'), modal messages ("You can't use this feature right now"),
    and drawer errors ("Couldn't post your comment. Try again").
    CRITICAL: Does NOT flag informational notice modals ("What happened", "We added restrictions",
    "We removed a post from your Page") as comment limits!
    """
    try:
        res = page.evaluate("""() => {
            const cleanText = (raw) => {
                return (raw || '').toLowerCase()
                    .replace(/[\u2018\u2019\u201A\u201B\u2032\u2035]/g, "'")
                    .replace(/[\u201C\u201D\u201E\u201F\u2033\u2036]/g, '"')
                    .replace(/\\s+/g, ' ')
                    .trim();
            };

            const isNoticeModal = (txt) => {
                return txt.includes("what happened") || 
                       txt.includes("restrictions to your account") || 
                       txt.includes("we added restrictions") || 
                       txt.includes("we removed a post") ||
                       txt.includes("you can't create ads") ||
                       txt.includes("you can't start or join calls") || 
                       txt.includes("you can't use groups") ||
                       txt.includes("community standards on");
            };

            const limitPhrases = [
                "you can't use this feature right now",
                "couldn't post your comment",
                "could not post your comment",
                "temporarily blocked from using this feature",
                "temporarily blocked from commenting",
                "we limit how often you can post",
                "you're temporarily blocked",
                "help protect the community from spam",
                "action blocked",
                "you can't comment right now",
                "এই ফিচারটি এখন ব্যবহার করতে পারবেন না",
                "আপনার মন্তব্যটি পোস্ট করা যায়নি",
                "আপনি সাময়িকভাবে ব্লক হয়েছেন",
                "অ্যাকশন ব্লক করা হয়েছে"
            ];

            // 1. Check inside modal dialogs (role="dialog", role="alertdialog", aria-modal="true")
            const dialogs = document.querySelectorAll('div[role="dialog"], div[role="alertdialog"], div[aria-modal="true"]');
            for (const d of dialogs) {
                if (!d || d.getBoundingClientRect().width <= 0) continue;
                const dText = cleanText(d.innerText || d.textContent || '');
                // Skip benign notice popups ("What happened", "restrictions to your account", etc.)
                if (isNoticeModal(dText)) {
                    continue;
                }
                for (const phrase of limitPhrases) {
                    if (dText.includes(phrase)) {
                        return { isLimited: true, reason: phrase, snippet: dText.slice(0, 140) };
                    }
                }
            }

            // 2. Check inside the comment drawer for failed comment alerts / warnings
            const drawer = document.querySelector('div[data-pagelet*="Comment"], div[role="complementary"]') || document.body;
            const drawerText = cleanText(drawer.innerText || drawer.textContent || '');
            if (drawerText.includes("couldn't post your comment") || (drawerText.includes("couldn't post") && drawerText.includes("try again"))) {
                return { isLimited: true, reason: "Couldn't post your comment. Try again", snippet: "Comment posting failed in drawer" };
            }

            // 3. Check for red error indicators in comments drawer
            const errorBadges = drawer.querySelectorAll('div[aria-label*="error" i], div[aria-label*="failed" i], svg[aria-label*="error" i]');
            if (errorBadges.length > 0) {
                return { isLimited: true, reason: "Error badge in comment drawer", snippet: "Comment error icon visible" };
            }

            // 4. Check full page body text (strictly fatal phrases only)
            const bodyText = cleanText(document.body.innerText || document.body.textContent || '');
            const fatalBodyPhrases = [
                "you can't use this feature right now",
                "you can't comment right now",
                "temporarily blocked from using this feature",
                "temporarily blocked from commenting",
                "action blocked",
                "এই ফিচারটি এখন ব্যবহার করতে পারবেন না",
                "অ্যাকশন ব্লক করা হয়েছে"
            ];
            for (const phrase of fatalBodyPhrases) {
                if (bodyText.includes(phrase)) {
                    return { isLimited: true, reason: phrase, snippet: phrase };
                }
            }

            return { isLimited: false, reason: "", snippet: "" };
        }""")
        if res and res.get("isLimited"):
            return True, res.get("snippet") or res.get("reason", "Comment Feature Limit Hit")
        return False, ""
    except Exception as e:
        return False, str(e)


def pause_reels_video(page: Any) -> None:
    """Instantly pauses active videos to preserve 100% bandwidth for comment queries."""
    try:
        if not page.is_closed():
            page.evaluate("""() => {
                const videos = document.querySelectorAll('video');
                for (const v of videos) {
                    try {
                        v.pause();
                        v.muted = true;
                    } catch(e) {}
                }
            }""")
    except Exception:
        pass


def scroll_to_next_facebook_reel(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """Navigates swiftly to next Reel video without clicking any profile, link, or badge."""
    initial_url = page.url
    dismiss_facebook_popups(page, log_func=log_func)

    # 1. Blur active element to remove focus from comment textbox / drawer
    try:
        page.evaluate("""() => {
            if (document.activeElement && typeof document.activeElement.blur === 'function') {
                document.activeElement.blur();
            }
        }""")
    except Exception:
        pass

    # 2. Press Escape key to close any temporary hover badges, menus, or modals without clicking anything
    try:
        page.keyboard.press("Escape")
        time.sleep(0.03)
    except Exception:
        pass

    # Priority 1: Dedicated Facebook Reels 'Next Card' / 'Next video' floating button (STRICT match, NEVER an <a> link or profile)
    try:
        clicked_btn = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('div[role="button"], button'));
            for (const b of btns) {
                const l = (b.getAttribute('aria-label') || '').toLowerCase().trim();
                if (
                    l === 'next card' || l.includes('next card') ||
                    l.includes('পরবর্তী কার্ড') ||
                    l === 'next video' || l.includes('next video') ||
                    l.includes('পরবর্তী ভিডিও') ||
                    l === 'next reel' || l.includes('next reel')
                ) {
                    const r = b.getBoundingClientRect();
                    // Must be rendered on screen, reasonable button size, and NOT an <a> link or profile
                    if (r.width >= 24 && r.height >= 24 && !b.closest('a') && !b.querySelector('a') && !b.hasAttribute('href')) {
                        b.click();
                        return true;
                    }
                }
            }
            return false;
        }""")
        if clicked_btn:
            for _ in range(15):
                time.sleep(0.05)
                if page.url != initial_url:
                    pause_reels_video(page)
                    if log_func:
                        log_func("    ➡️ Moved to next Reel via Next Card button click.")
                    return True
    except Exception:
        pass

    # Priority 2: Native Facebook ArrowDown on video/main container
    try:
        page.evaluate("""() => {
            if (document.activeElement && typeof document.activeElement.blur === 'function') {
                document.activeElement.blur();
            }
            window.focus();
            const v = document.querySelector('video');
            if (v && typeof v.focus === 'function') v.focus();
            const main = document.querySelector('div[role="main"]');
            if (main && typeof main.focus === 'function') main.focus();
        }""")
        page.keyboard.press("ArrowDown")
        for _ in range(12):
            time.sleep(0.05)
            if page.url != initial_url:
                pause_reels_video(page)
                if log_func:
                    log_func("    ➡️ Moved to next Reel via keyboard ArrowDown.")
                return True
    except Exception:
        pass

    # Priority 3: Safe Natural Mouse Wheel on center of Reel video player
    try:
        video_coords = page.evaluate("""() => {
            const v = document.querySelector('video');
            if (v) {
                const r = v.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) {
                    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                }
            }
            return { x: 450, y: 400 };
        }""")
        cx = (video_coords or {}).get("x", 450)
        cy = (video_coords or {}).get("y", 400)
        page.mouse.move(cx, cy)
        time.sleep(0.02)
        page.mouse.wheel(0, 950)
        for _ in range(12):
            time.sleep(0.05)
            if page.url != initial_url:
                pause_reels_video(page)
                if log_func:
                    log_func("    ➡️ Moved to next Reel via Mouse Wheel.")
                return True
    except Exception:
        pass

    # Priority 4: Keyboard PageDown
    try:
        page.keyboard.press("PageDown")
        for _ in range(10):
            time.sleep(0.05)
            if page.url != initial_url:
                pause_reels_video(page)
                if log_func:
                    log_func("    ➡️ Moved to next Reel via keyboard PageDown.")
                return True
    except Exception:
        pass

    pause_reels_video(page)
    return False


def is_comment_drawer_open(page: Any) -> bool:
    """Checks whether the comment drawer is currently open on Facebook Reels."""
    try:
        if page.is_closed():
            return False
        return page.evaluate("""() => {
            // 1. Is there an active comment input textbox?
            const ed = document.querySelector('div[role="textbox"][contenteditable="true"], div[data-lexical-editor="true"]');
            if (ed && ed.getBoundingClientRect().width > 20) return true;

            // 2. Is the visible comment button expanded?
            const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
            const cBtn = buttons.find(b => {
                const label = (b.getAttribute('aria-label') || '').trim().toLowerCase();
                const isCommentLabel = label === 'comment' || 
                                       label === 'comments' || 
                                       label === 'মন্তব্য' || 
                                       label === 'কমেন্ট' ||
                                       label.endsWith(' comment') ||
                                       label.endsWith(' comments') ||
                                       label.startsWith('comment ') ||
                                       label.startsWith('মন্তব্য ');
                if (!isCommentLabel) return false;
                const r = b.getBoundingClientRect();
                return r.width > 20 && r.height > 20 && r.top >= 0 && r.top < window.innerHeight;
            });
            if (cBtn && (cBtn.getAttribute('aria-expanded') === 'true' || cBtn.getAttribute('aria-pressed') === 'true')) {
                return true;
            }

            // 3. Is there an active right-side dialog or complementary comments panel?
            const drawers = Array.from(document.querySelectorAll('div[data-pagelet*="Comment"], div[role="complementary"], div[role="dialog"]'));
            for (const d of drawers) {
                const r = d.getBoundingClientRect();
                if (r.left > window.innerWidth * 0.45 && r.width > 150 && r.height > 150) {
                    const text = (d.innerText || '').toLowerCase();
                    if (text.includes("what happened") || text.includes("restrictions to your account") || text.includes("we removed a post")) {
                        continue;
                    }
                    const hasCommentContent = d.querySelector('div[role="article"], div[data-pagelet*="CommentRow"], div[role="textbox"]') ||
                                              text.includes('comment') || text.includes('মন্তব্য') || text.includes('relevant');
                    if (hasCommentContent) return true;
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

    # Try up to 5 attempts (total ~2.5s) to find button and click it
    for attempt in range(5):
        try:
            if page.is_closed():
                return False
            dismiss_facebook_popups(page)

            click_res = page.evaluate("""() => {
                const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
                const commentBtn = buttons.find(b => {
                    const label = (b.getAttribute('aria-label') || '').trim().toLowerCase();
                    const isCommentLabel = label === 'comment' || 
                                           label === 'comments' || 
                                           label === 'মন্তব্য' || 
                                           label === 'কমেন্ট' ||
                                           label.endsWith(' comment') ||
                                           label.endsWith(' comments') ||
                                           label.startsWith('comment ') ||
                                           label.startsWith('মন্তব্য ');
                    if (!isCommentLabel) return false;
                    const r = b.getBoundingClientRect();
                    return r.width > 20 && r.height > 20 && r.top >= 0 && r.top < window.innerHeight;
                });

                if (!commentBtn) return { found: false };

                if (commentBtn.getAttribute('aria-expanded') === 'true') {
                    return { found: true, alreadyExpanded: true };
                }

                commentBtn.click();
                const r = commentBtn.getBoundingClientRect();
                return { 
                    found: true, 
                    clicked: true, 
                    x: r.x + r.width / 2, 
                    y: r.y + r.height / 2 
                };
            }""")

            if click_res.get("alreadyExpanded"):
                return True

            if click_res.get("clicked"):
                # Wait for drawer or expanded state
                for _ in range(15):
                    time.sleep(0.1)
                    if is_comment_drawer_open(page):
                        if log_func:
                            log_func("    💬 Comment drawer opened.")
                        return True

                # Fallback: Mouse click at coordinates if JS click wasn't enough
                if click_res.get("x") and click_res.get("y"):
                    try:
                        page.mouse.click(click_res["x"], click_res["y"])
                        time.sleep(0.3)
                        if is_comment_drawer_open(page):
                            if log_func:
                                log_func("    💬 Comment drawer opened via coordinate click.")
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(0.3)

    return is_comment_drawer_open(page)


def scan_facebook_reel_comments(
    page: Any, 
    keywords: List[str], 
    own_comments: List[str], 
    profile_name: str,
    max_wait_seconds: float = 3.5,
    poll_interval: float = 0.08
) -> Dict[str, Any]:
    """
    Scans the Facebook Reels comments drawer for target keywords.
    - Synchronizes active video Creator/Page name with drawer header to guarantee
      comments belong to the current video and are fully loaded on slow internet.
    - Zero-Click Initial Scanner: DOES NOT click 'See more', 'View more comments', or 'View replies'.
    - Checks visible initial comments and <a> link URLs (href) directly as rendered.
    - Returns immediately as soon as a keyword match is detected for maximum speed.
    """
    start_time = time.time()
    last_res = {
        "drawerFound": True, 
        "matched": False, 
        "kw": "", 
        "isLoading": False, 
        "noComments": False,
        "activeAuthor": "",
        "drawerAuthor": "",
        "isSynced": False
    }
    
    # Fast video pause to preserve 100% bandwidth for comment queries
    pause_reels_video(page)
    
    while (time.time() - start_time) < max_wait_seconds:
        if page.is_closed():
            return last_res

        res = None
        try:
            res = page.evaluate("""(args) => {
            const { keywords, ownComments, profileName } = args;

            // 1. Locate Comments Drawer on the right side
            const drawer = Array.from(document.querySelectorAll('div[data-pagelet*="Comment"], div[role="complementary"], div[role="dialog"]'))
                .find(el => {
                    const r = el.getBoundingClientRect();
                    return r.left > window.innerWidth * 0.30 && r.width > 150 && r.height > 150;
                });

            if (!drawer) {
                return { 
                    drawerFound: false, 
                    isLoading: false, 
                    matched: false, 
                    kw: '', 
                    noComments: false,
                    activeAuthor: '',
                    drawerAuthor: '',
                    isSynced: false
                };
            }

            // 2. Extract Creator / Page Name from Active Reel Video (Left Side)
            let activeAuthor = '';
            const main = document.querySelector('div[role="main"]') || document.body;
            const leftLinks = Array.from(main.querySelectorAll('a[role="link"], strong, span[dir="auto"]')).filter(el => {
                const r = el.getBoundingClientRect();
                return r.left < window.innerWidth * 0.55 && r.width > 15 && r.height > 10;
            });
            for (const el of leftLinks) {
                const txt = (el.innerText || el.textContent || '').trim();
                if (txt && txt.length >= 2 && txt.length <= 45) {
                    const lower = txt.toLowerCase();
                    if (!lower.includes('follow') && !lower.includes('অনুসরণ') && !lower.includes('original audio') && !lower.includes('reels')) {
                        const parentText = (el.parentElement ? el.parentElement.innerText || '' : '').toLowerCase();
                        if (parentText.includes('follow') || parentText.includes('অনুসরণ') || el.closest('a[href*="/"]')) {
                            activeAuthor = lower;
                            break;
                        }
                    }
                }
            }

            // 3. Extract Creator / Page Name from Drawer Header (Right Side Top Section)
            let drawerAuthor = '';
            const dr = drawer.getBoundingClientRect();
            const topHeaderEls = Array.from(drawer.querySelectorAll('h2, a[role="link"], strong, span[dir="auto"]')).filter(el => {
                const r = el.getBoundingClientRect();
                return (r.top - dr.top) >= 0 && (r.top - dr.top) < 170 && r.width > 15 && r.height > 10;
            });
            for (const el of topHeaderEls) {
                const txt = (el.innerText || el.textContent || '').trim();
                if (txt && txt.length >= 2 && txt.length <= 45) {
                    const lower = txt.toLowerCase();
                    if (!lower.includes('follow') && !lower.includes('অনুসরণ') && !lower.includes('most relevant') && !lower.includes('all comments') && !lower.includes('comments') && !lower.includes('মন্তব্য')) {
                        drawerAuthor = lower;
                        break;
                    }
                }
            }

            // Check author sync between active video and comment drawer
            let isAuthorSynced = true;
            if (activeAuthor && drawerAuthor) {
                isAuthorSynced = drawerAuthor.includes(activeAuthor) || activeAuthor.includes(drawerAuthor);
            }

            // 4. Check for skeleton loading states
            const isBusy = drawer.getAttribute('aria-busy') === 'true';
            const hasSkeleton = !!drawer.querySelector(
                'div[data-visualcompletion="loading-state"], [role="progressbar"], svg[aria-label*="Loading" i], ' +
                'div.x135pm9v, div[style*="animation"], div[class*="skeleton"]'
            );

            const commentItems = Array.from(drawer.querySelectorAll('div[role="article"], div[data-pagelet*="CommentRow"], ul > li, div.x1r8uery'));
            const drawerText = (drawer.innerText || drawer.textContent || '').toLowerCase();
            const hasNoCommentsMsg = drawerText.includes('no comments yet') || 
                                     drawerText.includes('be the first to comment') || 
                                     drawerText.includes('কোন মন্তব্য নেই') ||
                                     drawerText.includes('কোনো মন্তব্য নেই');

            // Wait if skeleton active, or if author not yet synced and comments not loaded
            const isStillLoading = (isBusy || hasSkeleton || (!isAuthorSynced && commentItems.length === 0)) && !hasNoCommentsMsg;
            if (isStillLoading) {
                return { 
                    drawerFound: true, 
                    isLoading: true, 
                    matched: false, 
                    kw: '', 
                    noComments: false,
                    activeAuthor,
                    drawerAuthor,
                    isSynced: isAuthorSynced
                };
            }

            // 5. Extract comments, EXCLUDING input box and bot's own comments
            // ZERO-CLICK: We DO NOT click 'See more' or 'View more comments'.
            // Initial comments and anchor hrefs are extracted directly.
            const inputBox = drawer.querySelector('div[role="textbox"], div[data-lexical-editor="true"]');

            // Collect links inside drawer (capturing href even if text displays '... See more')
            const links = Array.from(drawer.querySelectorAll('a')).filter(a => {
                if (inputBox && inputBox.contains(a)) return false;
                return true;
            }).map(a => {
                let h = a.getAttribute('href') || a.href || '';
                try { h = decodeURIComponent(h); } catch(e) {}
                return (h + ' ' + (a.innerText || '')).toLowerCase();
            });

            // Collect text snippets inside drawer
            const textBlocks = [];
            const textNodes = drawer.querySelectorAll('div[dir="auto"], span[dir="auto"], div[role="article"]');
            for (const node of textNodes) {
                if (inputBox && inputBox.contains(node)) continue;
                const txt = (node.innerText || node.textContent || '').trim().toLowerCase();
                if (!txt) continue;

                // Check if this text belongs to bot's own comment
                let isOwn = false;
                if (profileName && txt.includes(profileName.toLowerCase()) && (txt.includes('posting...') || txt.includes('just now') || txt.includes('এইমাত্র'))) {
                    isOwn = true;
                }
                if (txt.includes('posting...')) {
                    isOwn = true;
                }
                for (const oc of ownComments) {
                    const ocTrim = (oc || '').trim().toLowerCase();
                    if (ocTrim.length > 20 && txt === ocTrim) {
                        isOwn = true;
                        break;
                    }
                }

                if (!isOwn) {
                    textBlocks.push(txt);
                }
            }

            // Include current reel description/caption (from left video side)
            const captionEl = document.querySelector('div[role="main"] div[dir="auto"]');
            if (captionEl && (!inputBox || !inputBox.contains(captionEl))) {
                textBlocks.push((captionEl.innerText || captionEl.textContent || '').toLowerCase());
            }

            const combined = textBlocks.join(' ') + ' ' + links.join(' ');

            // 6. Check for keyword matches
            for (const kw of keywords) {
                const kw_l = kw.trim().toLowerCase();
                if (kw_l && combined.includes(kw_l)) {
                    return { 
                        drawerFound: true, 
                        isLoading: false, 
                        matched: true, 
                        kw: kw_l, 
                        noComments: false,
                        activeAuthor,
                        drawerAuthor,
                        isSynced: isAuthorSynced
                    };
                }
            }

            return { 
                drawerFound: true, 
                isLoading: false, 
                matched: false, 
                kw: '', 
                noComments: hasNoCommentsMsg || (commentItems.length === 0 && !hasSkeleton),
                activeAuthor,
                drawerAuthor,
                isSynced: isAuthorSynced
            };
        }""", {
            "keywords": keywords,
            "ownComments": own_comments,
            "profileName": profile_name
        })
        except Exception:
            res = None

        if isinstance(res, dict):
            last_res = res
            if res.get("matched"):
                return res
            if res.get("noComments"):
                return res
            if not res.get("isLoading"):
                # If author is synced or comments have loaded, return immediately
                if res.get("isSynced") or (time.time() - start_time) >= 1.0:
                    return res

        time.sleep(poll_interval)

    return last_res


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
            
            // Check for Account Chooser / Logged out splash ("Use another profile", "Create new account", "Explore the things you love")
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

        if "login" in curr_url:
            return False, "Login Page"
        return False, "No active feed/cookies"
    except Exception as ex:
        return False, str(ex)


class FbCommentMarketingThread(QThread):
    """
    Playwright Automation Thread for Facebook Reels Comment Marketing Bot.
    Scans Reels feed, inspects comments for target link keywords (e.g. WhatsApp, Telegram),
    auto-posts custom marketing comments on matching Reels, and skips non-matching Reels.
    """

    log_emitted = Signal(str)
    progress_updated = Signal(int, int)
    stats_updated = Signal(dict)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        target_keywords: List[str],
        comments_list: List[str],
        max_comments: int = 5,
        max_reels: int = 50,
        comment_delay: Optional[int] = None,
        scan_delay: Optional[int] = None,
        min_delay: int = 1,
        max_delay: int = 1,
        scan_min_delay: int = 1,
        scan_max_delay: int = 1,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        seed_comment_chance: int = 0,
        enable_seed_priming: bool = False,
        seed_links: Optional[List[str]] = None,
        seed_max_videos: int = 3,
        seed_min_watch: int = 5,
        seed_max_watch: int = 12,
        seed_like_chance: int = 30,
        enable_ai_comments: bool = True,
        ai_prompt_instruction: str = "",
        user_offer_text: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list or []
        self.target_keywords = [k.strip() for k in target_keywords if k and k.strip()]
        self.comments_list = [c.strip() for c in comments_list if c and c.strip()]
        self.max_comments = max(1, max_comments)
        self.max_reels = max(1, max_reels)
        self.enable_ai_comments = enable_ai_comments
        self.ai_prompt_instruction = (ai_prompt_instruction or "").strip()
        self.user_offer_text = (user_offer_text or "").strip()
        self.stats = {
            "active_profile": "",
            "total_posted": 0,
            "total_scanned": 0,
            "profile_status": {}
        }

        # Allow fast delays down to 0s
        if comment_delay is not None:
            self.min_delay = max(0, comment_delay)
            self.max_delay = max(0, comment_delay)
        else:
            self.min_delay = max(0, min_delay)
            self.max_delay = max(self.min_delay, max_delay)

        if scan_delay is not None:
            self.scan_min_delay = max(0, scan_delay)
            self.scan_max_delay = max(0, scan_delay)
        else:
            self.scan_min_delay = max(0, scan_min_delay)
            self.scan_max_delay = max(self.scan_min_delay, scan_max_delay)

        self.max_concurrent_browsers = max(1, max_concurrent_browsers)
        self.headless = headless
        self.seed_comment_chance = seed_comment_chance
        self.enable_seed_priming = enable_seed_priming
        self.seed_links = seed_links or []
        self.seed_max_videos = max(1, seed_max_videos)
        self.seed_min_watch = max(1, seed_min_watch)
        self.seed_max_watch = max(self.seed_min_watch, seed_max_watch)
        self.seed_like_chance = seed_like_chance

        self.stop_requested = False
        self._lock = threading.Lock()
        self._active_contexts: Set[Any] = set()

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleeps in small 0.1s slices so stop signal is detected instantly."""
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.stop_requested:
                break
            time.sleep(0.1)

    def stop(self) -> None:
        """Stops the thread and closes all active browser contexts."""
        self.stop_requested = True
        self.log_emitted.emit("🛑 Stop requested by user! Closing browser contexts...")
        with self._lock:
            for ctx in list(self._active_contexts):
                try:
                    ctx.close()
                except Exception:
                    pass
            self._active_contexts.clear()

    def _process_single_profile(self, p_idx: int, total_profiles: int, pdata: Dict[str, Any]) -> bool:
        """Processes a single profile in a dedicated worker thread."""
        if self.stop_requested:
            return False

        pid = pdata.get("id") or pdata.get("number", "001")
        pname = pdata.get("name") or f"Profile {pid}"
        user_folder = resolve_user_data_dir(pdata, self.profile_mgr)
        group_name = pdata.get("group", "Default")
        p_dir = Path(user_folder)

        # 1. Terminate leftover orphan processes & singleton locks
        kill_profile_chrome_process(user_folder)
        for lock_name in ["SingletonLock", "lockfile"]:
            lock_f = p_dir / lock_name
            if lock_f.exists():
                try:
                    lock_f.unlink(missing_ok=True)
                except Exception:
                    pass

        # 2. Hydrate complete credentials & session cookies from profile.json / profile_mgr
        p_json = p_dir / "profile.json"
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
        pref_file = p_dir / "Default" / "Preferences"
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
        launch_kwargs = {
            "user_data_dir": str(p_dir.resolve()),
            "headless": self.headless,
            "args": custom_launch_args,
            "no_viewport": True,
            "ignore_default_args": ["--enable-automation"]
        }
        if chrome_exe and os.path.exists(chrome_exe):
            launch_kwargs["executable_path"] = chrome_exe
            self.log_emitted.emit(f"  🚀 Using srkBrowser Portable Chromium: {Path(chrome_exe).name}")

        with self._lock:
            self.stats["active_profile"] = pname
            self.stats["profile_status"][pname] = "Launching Browser..."
        self.stats_updated.emit(dict(self.stats))

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
                        if isinstance(raw_cookie, list):
                            parsed_cks = []
                            for c in raw_cookie:
                                if isinstance(c, dict) and "name" in c and "value" in c:
                                    ck = {
                                        "name": str(c["name"]).strip(),
                                        "value": str(c["value"]).strip(),
                                        "domain": c.get("domain", ".facebook.com"),
                                        "path": c.get("path", "/")
                                    }
                                    parsed_cks.append(ck)
                        else:
                            parsed_cks = parse_cookie_string(str(raw_cookie))
                        if parsed_cks:
                            context.add_cookies(parsed_cks)
                            self.log_emitted.emit(f"  🍪 Loaded {len(parsed_cks)} authenticated Facebook session cookies.")
                    except Exception as ck_ex:
                        pass

                try:
                    context.grant_permissions(["clipboard-read", "clipboard-write"])
                except Exception:
                    pass

                try:
                    page = context.pages[0] if context.pages else context.new_page()

                    # Auto-close unwanted new popups / accidental profile clicks
                    def _auto_close_popup_tab(new_p):
                        try:
                            if not self.stop_requested and new_p != page and not new_p.is_closed():
                                self.log_emitted.emit("    🛡️ Auto-Tab Guard: Closed unwanted newly opened extra tab.")
                                new_p.close()
                        except Exception:
                            pass
                    try:
                        context.on("page", _auto_close_popup_tab)
                    except Exception:
                        pass

                    # Speed Optimization: Abort heavy Facebook telemetry, tracking pixels and ad beacons
                    def _route_filter(route, request):
                        url = request.url.lower()
                        if any(b in url for b in [
                            "facebook.com/tr/",
                            "facebook.com/ajax/bz",
                            "connect.facebook.net",
                            "facebook.com/privacy_sandbox",
                            "facebook.com/signals"
                        ]):
                            try:
                                route.abort()
                            except Exception:
                                pass
                        else:
                            try:
                                route.continue_()
                            except Exception:
                                pass

                    try:
                        page.route("**/*", _route_filter)
                    except Exception:
                        pass

                    # Step 1: Check Facebook Login
                    self.log_emitted.emit(f"  🔍 [{pname}] Checking Facebook session...")
                    try:
                        page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                        self._interruptible_sleep(2.0)
                    except Exception as goto_err:
                        self.log_emitted.emit(f"  ⚠️ Navigation warning for [{pname}]: {goto_err}")

                    # First: Check for Facebook Account Suspension / Disabled / Checkpoint
                    is_susp, susp_reason = is_facebook_account_suspended(page)
                    if is_susp:
                        self.log_emitted.emit(f"  🚫 [{pname}] Facebook Account Suspended/Disabled ({susp_reason})!")
                        with self._lock:
                            self.stats["profile_status"][pname] = "Suspended (Auto-Deleted)"
                        self.stats_updated.emit(dict(self.stats))
                        delete_profile_safely(pid, user_folder, self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                        return False

                    # Second: Check Facebook Login Status
                    is_logged_in, login_msg = check_facebook_login_status(page, context)
                    if is_logged_in:
                        self.log_emitted.emit(f"  ✅ [{pname}] Active Facebook session verified (Logged In)!")
                        with self._lock:
                            self.stats["active_profile"] = pname
                            self.stats["profile_status"][pname] = f"Active (0/{self.max_comments} posted)"
                        self.stats_updated.emit(dict(self.stats))
                    else:
                        self.log_emitted.emit(f"  🔑 [{pname}] Session is not active ({login_msg}). Initiating Auto-Relogin...")
                        with self._lock:
                            self.stats["profile_status"][pname] = "Auto-Logging In..."
                        self.stats_updated.emit(dict(self.stats))
                        login_ok, login_res = auto_relogin_facebook(
                            page=page,
                            context=context,
                            profile_data=pdata,
                            profile_mgr=self.profile_mgr,
                            user_data_dir=user_folder,
                            log_func=lambda text: self.log_emitted.emit(text)
                        )
                        if not login_ok:
                            is_susp2, susp_reason2 = is_facebook_account_suspended(page)
                            if is_susp2 or login_res == "SUSPENDED":
                                self.log_emitted.emit(f"  🚫 [{pname}] Facebook Account Suspended/Disabled ({susp_reason2 or login_res})! Auto-deleting profile...")
                                with self._lock:
                                    self.stats["profile_status"][pname] = "Suspended (Auto-Deleted)"
                                self.stats_updated.emit(dict(self.stats))
                                delete_profile_safely(pid, user_folder, self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                                return False
                            elif "WRONG_PASSWORD" in login_res or "FAILED" in login_res:
                                self.log_emitted.emit(f"  🚫 [{pname}] Password incorrect & Cookie login failed ({login_res})! Auto-deleting dead profile from disk...")
                                with self._lock:
                                    self.stats["profile_status"][pname] = "Dead Profile (Auto-Deleted)"
                                self.stats_updated.emit(dict(self.stats))
                                delete_profile_safely(pid, user_folder, self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                                return False
                            else:
                                self.log_emitted.emit(f"  ❌ [{pname}] Auto-login could not complete ({login_res}). Skipping profile...")
                                with self._lock:
                                    self.stats["profile_status"][pname] = f"Login Failed ({login_res})"
                                self.stats_updated.emit(dict(self.stats))
                                return False
                        else:
                            self.log_emitted.emit(f"  ✅ [{pname}] Auto-login successful! Proceeding...")
                            with self._lock:
                                self.stats["active_profile"] = pname
                                self.stats["profile_status"][pname] = f"Active (0/{self.max_comments} posted)"
                            self.stats_updated.emit(dict(self.stats))

                    dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))

                    # Phase 1: Seed Priming (Optional)
                    if self.enable_seed_priming and self.seed_links:
                        target_seeds = self.seed_links[:self.seed_max_videos]
                        self.log_emitted.emit(f"  🧠 Phase 1: Starting Reels Algorithm Priming with {len(target_seeds)} Seed Video Link(s)...")

                        for s_idx, seed_url in enumerate(target_seeds, start=1):
                            if self.stop_requested:
                                break
                            if not seed_url.startswith("http"):
                                seed_url = f"https://www.facebook.com/reel/{seed_url}"

                            self.log_emitted.emit(f"    ▶️ [Seed #{s_idx}/{len(target_seeds)}] Opening target seed Reel: {seed_url[:60]}...")
                            try:
                                page.goto(seed_url, timeout=30000, wait_until="domcontentloaded")
                                self._interruptible_sleep(2.0)
                                dismiss_facebook_popups(page)

                                s_min = max(1, self.seed_min_watch)
                                s_max = max(s_min, self.seed_max_watch)
                                watch_dur = random.randint(s_min, s_max)
                                self.log_emitted.emit(f"    👀 Watching seed video for {watch_dur}s to train Facebook recommendation algorithm...")
                                self._interruptible_sleep(watch_dur)

                                if self.stop_requested:
                                    break

                                # Like seed video
                                if random.randint(1, 100) <= self.seed_like_chance:
                                    try:
                                        like_btns = page.query_selector_all('div[role="button"][aria-label*="Like"], div[role="button"][aria-label*="লাইক"]')
                                        for lbtn in like_btns:
                                            if lbtn and lbtn.is_visible():
                                                lbtn.click(force=True)
                                                self.log_emitted.emit(f"    👍 [Seed #{s_idx}] Liked target seed video!")
                                                self._interruptible_sleep(1.0)
                                                break
                                    except Exception:
                                        pass

                                # Comment on seed video
                                if random.randint(1, 100) <= self.seed_comment_chance and self.comments_list:
                                    try:
                                        chosen_comm = random.choice(self.comments_list)
                                        page.evaluate("""() => {
                                            const btns = document.querySelectorAll('div[role="button"][aria-label*="Comment"], div[role="button"][aria-label*="কমেন্ট"]');
                                            for (const b of btns) {
                                                if (b.getAttribute('aria-expanded') !== 'true') b.click();
                                            }
                                        }""")
                                        self._interruptible_sleep(1.2)

                                        comment_input_selectors = [
                                            'div[data-lexical-editor="true"] p[dir="auto"]',
                                            'div[role="textbox"][contenteditable="true"] p[dir="auto"]',
                                            'div[data-lexical-editor="true"]',
                                            'div[role="textbox"][contenteditable="true"]',
                                            'p[dir="auto"]'
                                        ]
                                        target_box = None
                                        for sel in comment_input_selectors:
                                            boxes = page.query_selector_all(sel)
                                            for box in boxes:
                                                if box and box.is_visible():
                                                    target_box = box
                                                    break
                                            if target_box:
                                                break

                                        if target_box:
                                            target_box.click(force=True)
                                            self._interruptible_sleep(0.3)
                                            page.keyboard.insert_text(chosen_comm)
                                            self._interruptible_sleep(0.6)
                                            page.keyboard.press("Enter")
                                            self.log_emitted.emit(f"    💬 [Seed #{s_idx}] Posted seed comment on target video!")
                                            self._interruptible_sleep(1.5)
                                    except Exception:
                                        pass
                            except Exception as seed_err:
                                self.log_emitted.emit(f"    ⚠️ Note on seed video #{s_idx}: {seed_err}")

                            self._interruptible_sleep(random.uniform(1.5, 2.5))

                        self.log_emitted.emit(f"  ✨ Phase 1 Complete! Transitioning to Phase 2 (Main Feed Scanning)...")

                    if self.stop_requested:
                        return False

                    # Phase 2: Main Reels Feed Scanning & Marketing Commenting
                    self.log_emitted.emit(f"  🎬 [{pname}] Phase 2: Navigating to Facebook Reels Feed (https://www.facebook.com/reel)...")
                    try:
                        page.goto("https://www.facebook.com/reel", timeout=30000, wait_until="domcontentloaded")
                    except Exception:
                        try:
                            page.goto("https://www.facebook.com/watch/reels", timeout=30000, wait_until="domcontentloaded")
                        except Exception as goto_err:
                            self.log_emitted.emit(f"  ⚠️ Reels navigation warning: {goto_err}")

                    self._interruptible_sleep(2.0)
                    pause_reels_video(page)
                    dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))

                    # Post-reels navigation login verification
                    is_susp_reels, susp_r_msg = is_facebook_account_suspended(page)
                    if is_susp_reels:
                        self.log_emitted.emit(f"  🚫 [{pname}] Account Suspended on Reels feed ({susp_r_msg})! Auto-deleting...")
                        with self._lock:
                            self.stats["profile_status"][pname] = "Suspended (Auto-Deleted)"
                        self.stats_updated.emit(dict(self.stats))
                        delete_profile_safely(pid, user_folder, self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                        return False

                    is_logged_in, login_msg = check_facebook_login_status(page, context)
                    if not is_logged_in:
                        self.log_emitted.emit(f"  🔑 [{pname}] Session logged out on Reels feed. Attempting Auto-Relogin...")
                        with self._lock:
                            self.stats["profile_status"][pname] = "Auto-Logging In..."
                        self.stats_updated.emit(dict(self.stats))
                        login_ok, login_res = auto_relogin_facebook(
                            page=page,
                            context=context,
                            profile_data=pdata,
                            profile_mgr=self.profile_mgr,
                            user_data_dir=user_folder,
                            log_func=lambda text: self.log_emitted.emit(text)
                        )
                        if not login_ok:
                            is_susp_r, susp_r_msg = is_facebook_account_suspended(page)
                            if is_susp_r or login_res == "SUSPENDED":
                                self.log_emitted.emit(f"  🚫 [{pname}] Facebook Account Suspended on Reels feed ({susp_r_msg or login_res})! Auto-deleting profile...")
                                with self._lock:
                                    self.stats["profile_status"][pname] = "Suspended (Auto-Deleted)"
                            else:
                                self.log_emitted.emit(f"  🚫 [{pname}] Password incorrect & Cookie login failed on Reels ({login_res})! Auto-deleting dead profile from disk...")
                                with self._lock:
                                    self.stats["profile_status"][pname] = "Dead Profile (Auto-Deleted)"
                            self.stats_updated.emit(dict(self.stats))
                            delete_profile_safely(pid, user_folder, self.profile_mgr, log_func=lambda text: self.log_emitted.emit(text))
                            return False
                        self.log_emitted.emit(f"  ✅ [{pname}] Auto-login successful on Reels feed! Resuming...")

                    # Pre-check if this profile already has an Action Block / Limit
                    dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))
                    is_limited, limit_info = check_for_facebook_comment_limit(page)
                    if is_limited:
                        self.log_emitted.emit(f"  🚫 [{pname}] Account already has Facebook Action Block: '{limit_info}'!")
                        self.log_emitted.emit(f"  🛑 Closing Profile [{pname}] and moving to next profile...")
                        return False

                    # Step 2A: Open comment drawer ONCE on initial Reel (drawer persists across reels without toggling)
                    initial_drawer_opened = ensure_comment_drawer_open(page, log_func=lambda text: self.log_emitted.emit(text))
                    if initial_drawer_opened:
                        self.log_emitted.emit(f"  💬 Comment drawer opened on initial Reel for [{pname}]. Drawer will persist across Reels.")

                    reels_checked = 0
                    comments_posted = 0
                    commented_reel_ids: Set[str] = set()
                    visited_reel_ids: Set[str] = set()

                    for reel_idx in range(1, self.max_reels + 1):
                        if self.stop_requested:
                            self.log_emitted.emit(f"  🛑 [{pname}] Stop signal received. Ending Reel scan!")
                            break
                        if page.is_closed():
                            self.log_emitted.emit(f"  ⚠️ [{pname}] Browser window was closed. Terminating profile.")
                            return False
                        if comments_posted >= self.max_comments:
                            self.log_emitted.emit(f"  🎯 Profile '{pname}' reached target comment limit ({comments_posted}/{self.max_comments} comments posted). Ending scan!")
                            break

                        if len(context.pages) > 1:
                            for extra_p in list(context.pages):
                                if extra_p != page and not extra_p.is_closed():
                                    try:
                                        extra_p.close()
                                    except Exception:
                                        pass
                            try:
                                page.bring_to_front()
                            except Exception:
                                pass

                        reels_checked += 1
                        pause_reels_video(page)
                        dismiss_facebook_popups(page)
                        current_url = page.url
                        reel_id_match = re.search(r'/reel/(\d+)', current_url)
                        current_reel_id = reel_id_match.group(1) if reel_id_match else current_url.split('?')[0]

                        # Limit / Restriction check on each Reel
                        is_limited, limit_info = check_for_facebook_comment_limit(page)
                        if is_limited:
                            self.log_emitted.emit(f"  🚫 [{pname}] Facebook Action Block / Restriction Detected: '{limit_info}'!")
                            self.log_emitted.emit(f"  🛑 Closing Profile [{pname}] immediately and moving to next profile...")
                            return False

                        if current_reel_id in visited_reel_ids or current_reel_id in commented_reel_ids:
                            # Allow sync window for slow network URL update before declaring visited
                            for _ in range(15):
                                self._interruptible_sleep(0.05)
                                current_url = page.url
                                reel_id_match = re.search(r'/reel/(\d+)', current_url)
                                new_rid = reel_id_match.group(1) if reel_id_match else current_url.split('?')[0]
                                if new_rid not in visited_reel_ids and new_rid not in commented_reel_ids:
                                    current_reel_id = new_rid
                                    break

                        if current_reel_id in visited_reel_ids or current_reel_id in commented_reel_ids:
                            self.log_emitted.emit(f"    ⏭️ Reel ID already visited (...{current_reel_id[-8:]}). Navigating to next Reel...")
                            scroll_to_next_facebook_reel(page, log_func=lambda text: self.log_emitted.emit(text))
                            self._interruptible_sleep(0.05)
                            current_url = page.url
                            reel_id_match = re.search(r'/reel/(\d+)', current_url)
                            new_rid = reel_id_match.group(1) if reel_id_match else current_url.split('?')[0]
                            if new_rid not in visited_reel_ids and new_rid not in commented_reel_ids:
                                current_reel_id = new_rid
                            else:
                                continue

                        visited_reel_ids.add(current_reel_id)
                        with self._lock:
                            self.stats["active_profile"] = pname
                            self.stats["total_scanned"] += 1
                        self.stats_updated.emit(dict(self.stats))
                        self.log_emitted.emit(f"  🎬 [{pname}] Checking Reel #{reel_idx}/{self.max_reels} (ID: ...{current_reel_id[-10:]})")
                        self._interruptible_sleep(0.08)

                        # Step 2: Ensure comment drawer is active & scan comments
                        link_found = False
                        matched_kw = ""

                        try:
                            # Step 2A: Ensure comment drawer is active (safely without toggling)
                            if not is_comment_drawer_open(page):
                                ensure_comment_drawer_open(page, log_func=lambda text: self.log_emitted.emit(text))

                            # Step 2B: Robust Scoped Comment Scanning (with Creator sync and zero-click initial scan)
                            scan_res = scan_facebook_reel_comments(
                                page=page,
                                keywords=self.target_keywords,
                                own_comments=self.comments_list,
                                profile_name=pname,
                                max_wait_seconds=3.5,
                                poll_interval=0.08
                            )

                            if not scan_res.get("drawerFound"):
                                ensure_comment_drawer_open(page, log_func=lambda text: self.log_emitted.emit(text))
                                scan_res = scan_facebook_reel_comments(
                                    page=page,
                                    keywords=self.target_keywords,
                                    own_comments=self.comments_list,
                                    profile_name=pname,
                                    max_wait_seconds=2.5,
                                    poll_interval=0.08
                                )

                            if scan_res.get("matched"):
                                link_found = True
                                matched_kw = scan_res.get("kw")
                                author_info = f" (Creator: {scan_res.get('activeAuthor')})" if scan_res.get('activeAuthor') else ""
                                self.log_emitted.emit(f"    🎯 MATCH DETECTED! Keyword '{matched_kw}' found in Reel #{reel_idx}{author_info} comments/links!")
                            else:
                                self.log_emitted.emit(f"    ℹ️ No target keyword matching {self.target_keywords[:3]} in Reel #{reel_idx} comments.")
                        except Exception as scan_err:
                            self.log_emitted.emit(f"    ⚠️ Comment scan note on Reel #{reel_idx}: {scan_err}")

                        if self.stop_requested:
                            break

                        # Step 3: Post marketing comment if matched
                        if link_found and current_reel_id not in commented_reel_ids:
                            chosen_comment = ""
                            fallback_comment = random.choice(self.comments_list) if self.comments_list else f"Watch Full Video Here 🎬🔥👇\n{self.user_offer_text}"

                            if getattr(self, "enable_ai_comments", False):
                                try:
                                    reel_caption = page.evaluate("""() => {
                                        const main = document.querySelector('div[role="main"]') || document.body;
                                        const spans = Array.from(main.querySelectorAll('span[dir="auto"], div[dir="auto"]')).filter(el => {
                                            const r = el.getBoundingClientRect();
                                            return r.left < window.innerWidth * 0.55 && r.width > 20 && r.height > 10;
                                        });
                                        for (const s of spans) {
                                            const t = (s.innerText || s.textContent || '').trim();
                                            if (t.length > 8 && !t.toLowerCase().includes('follow') && !t.toLowerCase().includes('original audio') && !t.toLowerCase().includes('reels')) {
                                                return t;
                                            }
                                        }
                                        return '';
                                    }""")
                                except Exception:
                                    reel_caption = ""

                                self.log_emitted.emit(f"    🚀 [Viral Engine] Generating viral contextual hook for Reel #{reel_idx}...")
                                chosen_comment = generate_ai_comment(
                                    caption=reel_caption,
                                    matched_keyword=matched_kw,
                                    user_offer_text=self.user_offer_text,
                                    custom_instruction=getattr(self, "ai_prompt_instruction", ""),
                                    fallback_comment=fallback_comment
                                )
                                self.log_emitted.emit(f"    ✨ [Comment Ready] '{chosen_comment}'")
                            elif self.comments_list:
                                chosen_comment = fallback_comment
                                self.log_emitted.emit(f"    💬 Preparing to post marketing comment: '{chosen_comment[:35]}...'")

                            if chosen_comment:
                                # 100% Guaranteed English Viral Hook on top (User rule: কোনো কমেন্টেই যেন মিস না হয়)
                                lines = [ln.strip() for ln in chosen_comment.splitlines() if ln.strip()]
                                if lines:
                                    first_line = lines[0]
                                    if any(first_line.startswith(prefix) for prefix in ("http://", "https://", "wa.me", "t.me", "chat.whatsapp", "www.")):
                                        hook = random.choice(VIRAL_ENGLISH_HOOKS)
                                        chosen_comment = f"{hook}\n{chosen_comment}"

                                posted_ok = False
                                dismiss_facebook_popups(page)

                                # Ensure comments drawer is open
                                if not is_comment_drawer_open(page):
                                    ensure_comment_drawer_open(page)

                                # 1. Find and focus the comment editor element
                                target_box = None
                                page.evaluate("""() => {
                                    const ed = document.querySelector('div[role="textbox"][contenteditable="true"], div[data-lexical-editor="true"]');
                                    if (ed) {
                                        ed.focus();
                                        let p = ed.querySelector('p');
                                        if (!p) {
                                            p = document.createElement('p');
                                            p.className = 'xdj266r x11i5rnm xat24cr x1mh8g0r';
                                            ed.appendChild(p);
                                        }
                                        const range = document.createRange();
                                        range.selectNodeContents(p);
                                        range.collapse(false);
                                        const sel = window.getSelection();
                                        sel.removeAllRanges();
                                        sel.addRange(range);
                                    }
                                }""")

                                comment_input_selectors = [
                                    'div[role="textbox"][data-lexical-editor="true"]',
                                    'div[role="textbox"][contenteditable="true"]',
                                    'div[role="textbox"]',
                                    'div[data-lexical-editor="true"]',
                                    'div[aria-label*="Comment as"]',
                                    'div[aria-label*="Write a comment"]'
                                ]
                                for sel in comment_input_selectors:
                                    try:
                                        boxes = page.query_selector_all(sel)
                                        for box in boxes:
                                            if box and box.is_visible():
                                                target_box = box
                                                break
                                        if target_box:
                                            break
                                    except Exception:
                                        pass

                                if not target_box:
                                    dismiss_facebook_popups(page)
                                    box_coords = page.evaluate("""() => {
                                        const ed = document.querySelector('div[role="textbox"], div[data-lexical-editor="true"]');
                                        if (ed) {
                                            const r = ed.getBoundingClientRect();
                                            if (r.width > 0 && r.height > 0) return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                                        }
                                        return null;
                                    }""")
                                    if box_coords:
                                        try:
                                            page.mouse.click(box_coords["x"], box_coords["y"])
                                            self._interruptible_sleep(0.3)
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
                                    try:
                                        target_box.click(force=True)
                                        self._interruptible_sleep(0.2)

                                        # Fast instant comment insertion
                                        self.log_emitted.emit(f"    ⚡ Inserting comment instantly into Reel #{reel_idx}...")
                                        page.keyboard.insert_text(chosen_comment)
                                        self._interruptible_sleep(0.08)

                                        # Verification of editor text entry
                                        has_content = page.evaluate("""() => {
                                            const ed = document.querySelector('div[role="textbox"][contenteditable="true"], div[data-lexical-editor="true"]');
                                            return ed && (ed.innerText || ed.textContent || '').trim().length > 0;
                                        }""")
                                        if not has_content:
                                            # Backup insertion via beforeinput event
                                            page.evaluate("""(text) => {
                                                const ed = document.querySelector('div[role="textbox"][contenteditable="true"], div[data-lexical-editor="true"]');
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
                                            }""", chosen_comment)
                                            self._interruptible_sleep(0.1)

                                        # Dual Submission: Enter Key + Post Button Click
                                        page.keyboard.press("Enter")
                                        self.log_emitted.emit(f"    🚀 Pressed Enter to post comment!")
                                        self._interruptible_sleep(0.15)

                                        post_btn_selectors = [
                                            'div[role="button"][aria-label="Post comment"]',
                                            'div[aria-label="Post comment"]',
                                            'div[role="button"][aria-label*="Post"]',
                                            'div[role="button"][aria-label*="Send"]',
                                            'div[aria-label*="Send"]',
                                            'div[role="button"][aria-label*="পোস্ট"]',
                                            'div[role="button"][aria-label*="পাঠান"]'
                                        ]
                                        for p_sel in post_btn_selectors:
                                            try:
                                                p_btns = page.query_selector_all(p_sel)
                                                for pb in p_btns:
                                                    if pb and pb.is_visible() and pb.get_attribute("aria-disabled") != "true":
                                                        try: pb.click(force=True)
                                                        except Exception: page.evaluate("b => b.click()", pb)
                                                        break
                                            except Exception:
                                                pass

                                        # Blur active element so cursor leaves textbox
                                        try:
                                            page.evaluate("() => { if (document.activeElement && typeof document.activeElement.blur === 'function') document.activeElement.blur(); }")
                                        except Exception:
                                            pass

                                        # Step 3B: Wait for Facebook server response and check for Action Block / Limit
                                        self._interruptible_sleep(1.2)
                                        dismiss_facebook_popups(page)

                                        is_limited, limit_reason = check_for_facebook_comment_limit(page)
                                        if is_limited:
                                            self.log_emitted.emit(f"  🚫 [{pname}] Facebook Action Block / Restriction Detected: '{limit_reason}'!")
                                            self.log_emitted.emit(f"  🛑 Terminating Profile [{pname}] immediately and moving to next profile...")
                                            return False

                                        # Verify comment was posted
                                        verify_status = page.evaluate("""(msg) => {
                                            const drawer = document.querySelector('div[data-pagelet*="Comment"], div[role="complementary"]') || document.body;
                                            const dText = (drawer.innerText || drawer.textContent || '').toLowerCase();
                                            const hasText = dText.includes(msg.toLowerCase()) || dText.includes('posting...');
                                            const hasError = dText.includes("couldn't post") || dText.includes("could not post");
                                            const ed = document.querySelector('div[role="textbox"]');
                                            const edFound = !!ed;
                                            const edEmpty = edFound && (ed.innerText || ed.textContent || '').trim() === '';
                                            return { hasText, hasError, edFound, edEmpty };
                                        }""", chosen_comment[:20])

                                        if verify_status.get("hasError"):
                                            self.log_emitted.emit(f"  🚫 [{pname}] Comment posting failed in drawer ('Couldn't post your comment')!")
                                            self.log_emitted.emit(f"  🛑 Terminating Profile [{pname}] immediately and moving to next profile...")
                                            return False

                                        if verify_status.get("hasText") or (verify_status.get("edFound") and verify_status.get("edEmpty")):
                                            posted_ok = True
                                    except Exception as post_err:
                                        self.log_emitted.emit(f"    ❌ Failed to post comment on Reel #{reel_idx}: {post_err}")
                                else:
                                    self.log_emitted.emit(f"    ❌ Comment input box could not be focused on Reel #{reel_idx}")

                                if posted_ok:
                                    comments_posted += 1
                                    commented_reel_ids.add(current_reel_id)
                                    with self._lock:
                                        self.stats["total_posted"] += 1
                                        self.stats["profile_status"][pname] = f"Active ({comments_posted}/{self.max_comments} posted)"
                                    self.stats_updated.emit(dict(self.stats))
                                    self.log_emitted.emit(f"    ✅ Successfully posted marketing comment on Reel #{reel_idx}! (Profile: {comments_posted}/{self.max_comments} | System Total: {self.stats['total_posted']})")

                                    post_pause = self.min_delay if self.min_delay == self.max_delay else random.randint(self.min_delay, self.max_delay)
                                    if post_pause > 0:
                                        self.log_emitted.emit(f"    ⏱️ Post-Comment Delay: Pausing {post_pause}s...")
                                        self._interruptible_sleep(post_pause)
                                    else:
                                        self._interruptible_sleep(0.05)

                                    if comments_posted >= self.max_comments:
                                        self.log_emitted.emit(f"  🎯 Target comment limit reached ({comments_posted}/{self.max_comments}) for Profile '{pname}'!")
                                        break
                                else:
                                    fail_pause = self.scan_min_delay if self.scan_min_delay == self.scan_max_delay else random.randint(self.scan_min_delay, self.scan_max_delay)
                                    if fail_pause > 0:
                                        self.log_emitted.emit(f"    ⏱️ Safe Pause: Pausing {fail_pause}s before scrolling...")
                                        self._interruptible_sleep(fail_pause)
                                    else:
                                        self._interruptible_sleep(0.05)
                        else:
                            scan_pause = self.scan_min_delay if self.scan_min_delay == self.scan_max_delay else random.randint(self.scan_min_delay, self.scan_max_delay)
                            if scan_pause > 0:
                                self.log_emitted.emit(f"    ⏱️ Scan Delay: Pausing {scan_pause}s before scrolling to next Reel...")
                                self._interruptible_sleep(scan_pause)
                            else:
                                self._interruptible_sleep(0.05)

                        if self.stop_requested:
                            break

                        # Step 4: Navigate to Next Reel video via Next Card
                        self.log_emitted.emit(f"    ⬇️ Step 4: Navigating to Next Reel video (Next Card)...")
                        scroll_to_next_facebook_reel(page, log_func=lambda text: self.log_emitted.emit(text))

                    with self._lock:
                        self.stats["profile_status"][pname] = f"Completed ({comments_posted}/{self.max_comments} posted)"
                    self.stats_updated.emit(dict(self.stats))
                    self.log_emitted.emit(f"  🎉 [{pname}] Finished! Scanned {reels_checked} Reels | Posted {comments_posted}/{self.max_comments} Target Comments.")
                    return True
                finally:
                    with self._lock:
                        self._active_contexts.discard(context)
                    try:
                        context.close()
                    except Exception:
                        pass
                    if user_folder:
                        kill_profile_chrome_process(user_folder)
        except Exception as err:
            self.log_emitted.emit(f"  ❌ Error processing [{pname}]: {err}")
            return False

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles selected to run FB Comment Marketing Bot.")
            return

        self.log_emitted.emit(f"📢 Starting FB Comment Marketing Bot Engine for {total_profiles} Profile(s)...")
        self.log_emitted.emit(f"🎯 Keywords Filter: {', '.join(self.target_keywords[:5])}...")
        self.log_emitted.emit(f"⚙️ Target Limit: {self.max_comments} Comment(s)/ID | Scan Limit: {self.max_reels} Reels | Scan Delay: {self.scan_min_delay}s | Post-Comment Delay: {self.min_delay}s")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browsers")

        completed = 0
        success_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            futures = {
                executor.submit(self._process_single_profile, p_idx, total_profiles, pdata): pdata
                for p_idx, pdata in enumerate(self.profiles_list, start=1)
            }

            for fut in concurrent.futures.as_completed(futures):
                if self.stop_requested:
                    self.log_emitted.emit("🛑 Stop signal acknowledged. Terminating active profile workers...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                completed += 1
                self.progress_updated.emit(completed, total_profiles)
                try:
                    if fut.result():
                        success_count += 1
                except Exception as exc:
                    self.log_emitted.emit(f"⚠️ Exception in worker: {exc}")

        self.finished_signal.emit(True, f"FB Comment Marketing Bot Complete! Processed {success_count}/{total_profiles} Profile(s) successfully!")
