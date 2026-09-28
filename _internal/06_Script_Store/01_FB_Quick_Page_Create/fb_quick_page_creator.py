"""
⚡ FB 1-Click Page Creator (Automation Bot & Quick Script for srkBrowser)
Version: 2.2.0
Author: srkBrowser Automation Lab
Description: Instant 1-click Facebook page creation with Random & Custom modes.
Compatible with both Automation Bots tab and Profile Cards.
"""

import os
import sys
import time
import random
import re
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QRadioButton,
    QButtonGroup, QFrame, QProgressBar
)

from playwright.sync_api import sync_playwright

# Injected Bookmarklet JavaScript (bundled for standalone self-contained execution)
INJECT_SCRIPT_CODE = r"""
javascript:(() => {
    // Check if inject script exists on disk or memory
    window.__captured_created_page_id = "";
    window.__captured_created_page_url = "";
})();
"""

INJECT_FILE = Path(__file__).resolve().parent / "quick_page_creator_inject.js"
if INJECT_FILE.exists():
    try:
        with open(INJECT_FILE, "r", encoding="utf-8") as f:
            INJECT_SCRIPT_CODE = f.read()
    except Exception:
        pass


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
    category_id: str = "181475575221097",
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
        return False, "Invalid Profile Data Directory", "", "", ""

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
                args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check",
                    "--no-first-run",
                    "--disable-infobars"
                ]
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    executable_path=chrome_exe,
                    headless=headless,
                    args=args,
                    viewport={"width": 1280, "height": 800},
                    ignore_default_args=["--enable-automation"]
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
                try:
                    page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass

            time.sleep(1.2)
            dismiss_facebook_popup_notices(page)

            # Check if logged in
            curr_url = page.url
            if "login" in curr_url or "checkpoint" in curr_url:
                if not connected_via_cdp:
                    try:
                        context.close()
                    except Exception:
                        pass
                return False, "Facebook profile is not logged in! Please login first.", "", "", ""

            # 2. Inject Bookmarklet JS
            if INJECT_SCRIPT_CODE:
                page.evaluate(INJECT_SCRIPT_CODE)

                # Stealth Hide injected overlay & container
                page.evaluate("""() => {
                    const box = document.querySelector('#jsi-box');
                    const overlay = document.querySelector('#jsi-overlay');
                    if (box) { box.style.opacity = '0'; box.style.pointerEvents = 'none'; box.style.zIndex = '-9999'; }
                    if (overlay) { overlay.style.opacity = '0'; overlay.style.pointerEvents = 'none'; overlay.style.zIndex = '-9999'; }
                }""")
                time.sleep(0.4)

                # Click "CREATE FACEBOOK PAGE" button
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('#jsi-box button, #jsi-box div, #jsi-box a'));
                    for (const b of btns) {
                        if ((b.innerText || b.textContent || '').includes('CREATE FACEBOOK PAGE')) {
                            b.click();
                            break;
                        }
                    }
                }""")
                time.sleep(0.5)

                # Fill Page Name and Category
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

                # Wait for status response in log container
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
                    }""")
                except Exception:
                    pass

                time.sleep(1.0)
                if not connected_via_cdp:
                    try:
                        context.close()
                    except Exception:
                        pass

                if created_ok or created_page_id:
                    if not created_page_link and created_page_id:
                        created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"
                    return True, created_page_id, created_page_link, target_page_name, category_name
                else:
                    return False, "Facebook mutation did not complete", "", target_page_name, category_name

            if not connected_via_cdp:
                try:
                    context.close()
                except Exception:
                    pass
            return False, "Inject script not found", "", "", ""

    except Exception as e:
        return False, f"Execution error: {str(e)}", "", "", ""


class QuickCreationWorker(QThread):
    finished_signal = Signal(bool, str, str, str, str)

    def __init__(self, user_data_dir: str, page_name: str, cat_id: str, cat_name: str, headless: bool = False, profile_data: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.user_data_dir = user_data_dir
        self.page_name = page_name
        self.cat_id = cat_id
        self.cat_name = cat_name
        self.headless = headless
        self.profile_data = profile_data or {}

    def run(self):
        ok, p_id, p_link, name, cat = execute_quick_page_creation(
            user_data_dir=self.user_data_dir,
            target_page_name=self.page_name,
            category_id=self.cat_id,
            category_name=self.cat_name,
            headless=self.headless
        )
        self.finished_signal.emit(ok, p_id, p_link, name, cat)


class QuickPageCreatorModal(QDialog):
    """
    Cute, Compact & Cyber-Themed 1-Click Page Creator Modal.
    Supports launch from both Profile Card and Bot Store / Automation tab.
    """
    def __init__(self, *args, **kwargs):
        # Universal parameter resolution:
        # Signature 1 (from Bot Store): (profile_mgr, parent=MainWindow)
        # Signature 2 (from Profile Card): (profile_data=dict, user_data_dir=str, parent=MainWindow)
        parent = None
        self.profile_mgr = None
        self.profile_data = {}
        self.user_data_dir = ""
        self.all_profiles: List[Dict[str, Any]] = []

        if len(args) >= 1:
            first_arg = args[0]
            if hasattr(first_arg, "get_all_profiles"):
                self.profile_mgr = first_arg
                if len(args) >= 2 and isinstance(args[1], QWidget):
                    parent = args[1]
            elif isinstance(first_arg, dict):
                self.profile_data = first_arg
                if len(args) >= 2 and isinstance(args[1], str):
                    self.user_data_dir = args[1]
                if len(args) >= 3 and isinstance(args[2], QWidget):
                    parent = args[2]
            elif isinstance(first_arg, QWidget):
                parent = first_arg

        if "parent" in kwargs:
            parent = kwargs["parent"]
        if "profile_mgr" in kwargs:
            self.profile_mgr = kwargs["profile_mgr"]
        if "profile_data" in kwargs:
            self.profile_data = kwargs["profile_data"] or self.profile_data
        if "user_data_dir" in kwargs:
            self.user_data_dir = kwargs["user_data_dir"] or self.user_data_dir

        super().__init__(parent)
        self._drag_pos = QPoint()

        # If profile_mgr is available, load profiles list
        if self.profile_mgr and hasattr(self.profile_mgr, "get_all_profiles"):
            try:
                self.all_profiles = self.profile_mgr.get_all_profiles() or []
            except Exception:
                self.all_profiles = []

        # If profile_data not set, pick first available profile
        if not self.profile_data and self.all_profiles:
            self.profile_data = self.all_profiles[0]
            self._resolve_user_data_dir(self.profile_data)

        self.setWindowTitle("⚡ FB 1-Click Page Creator")
        self.setFixedSize(500, 420 if self.all_profiles else 360)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._init_ui()

    def _resolve_user_data_dir(self, p_data: Dict[str, Any]) -> None:
        if not p_data:
            return
        if self.profile_mgr:
            p_id = p_data.get("id") or p_data.get("number")
            try:
                self.user_data_dir = str(self.profile_mgr.get_profile_dir(p_id).resolve())
            except Exception:
                num = str(p_data.get("number") or p_id)
                self.user_data_dir = str((self.profile_mgr.base_dir / num).resolve())
        elif not self.user_data_dir:
            num = str(p_data.get("number") or p_data.get("id") or "")
            self.user_data_dir = os.path.join(os.getcwd(), "profiles", num)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        main_card = QFrame(self)
        main_card.setStyleSheet("""
            QFrame {
                background-color: #090a18;
                border: 1.5px solid #8b5cf6;
                border-radius: 16px;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel { background: transparent; }
        """)

        layout = QVBoxLayout(main_card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # Header with Drag & Close
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        lbl_icon = QLabel("📄")
        lbl_icon.setStyleSheet("font-size: 24px; border: none;")

        v_title = QVBoxLayout()
        v_title.setSpacing(1)
        lbl_title = QLabel("⚡ FB 1-Click Page Creator")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #c084fc; border: none;")
        lbl_sub = QLabel("Fast Automatic Facebook Page Creation in ~1.5s")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; border: none;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #94a3b8;
                border: 1px solid #7c3aed44;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #dc2626;
                color: white;
                border-color: #ef4444;
            }
        """)
        btn_close.clicked.connect(self.reject)

        top_bar.addWidget(lbl_icon)
        top_bar.addLayout(v_title)
        top_bar.addStretch()
        top_bar.addWidget(btn_close)
        layout.addLayout(top_bar)

        # Profile Selector (if opened from Bot Store with multiple profiles)
        if self.all_profiles and len(self.all_profiles) > 0:
            layout.addWidget(QLabel("Select Target Facebook Profile:"))
            self.combo_profiles = QComboBox()
            self.combo_profiles.setStyleSheet("""
                QComboBox {
                    background: #13122c;
                    color: #e2e8f0;
                    border: 1px solid #7c3aed66;
                    border-radius: 8px;
                    padding: 6px 10px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QComboBox QAbstractItemView {
                    background: #0d0e24;
                    color: #f1f5f9;
                    selection-background-color: #8b5cf6;
                    border: 1px solid #7c3aed;
                }
            """)
            for p in self.all_profiles:
                p_label = f"👤 {p.get('name', 'Profile')} ({p.get('number', '')})"
                self.combo_profiles.addItem(p_label, p)

            self.combo_profiles.currentIndexChanged.connect(self._on_profile_selected)
            layout.addWidget(self.combo_profiles)

        # Mode Selection: Random vs Custom
        layout.addWidget(QLabel("Page Name Option:"))
        h_mode = QHBoxLayout()
        h_mode.setSpacing(14)

        self.rb_random = QRadioButton("🎲 Smart Random Name")
        self.rb_random.setChecked(True)
        self.rb_random.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11px; border: none;")

        self.rb_custom = QRadioButton("✍️ Custom Name")
        self.rb_custom.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px; border: none;")

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.rb_random)
        self.btn_group.addButton(self.rb_custom)
        self.btn_group.buttonClicked.connect(self._toggle_name_mode)

        h_mode.addWidget(self.rb_random)
        h_mode.addWidget(self.rb_custom)
        h_mode.addStretch()
        layout.addLayout(h_mode)

        # Page Name Input Field
        self.txt_page_name = QLineEdit()
        initial_name = generate_random_page_name(self.profile_data)
        self.txt_page_name.setText(initial_name)
        self.txt_page_name.setPlaceholderText("Enter Facebook Page Name...")
        self.txt_page_name.setStyleSheet("""
            QLineEdit {
                background: #13122c;
                color: #38bdf8;
                border: 1px solid #7c3aed66;
                border-radius: 8px;
                padding: 7px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit:focus {
                border: 1.5px solid #38bdf8;
            }
        """)
        layout.addWidget(self.txt_page_name)

        # Category ComboBox
        layout.addWidget(QLabel("Category:"))
        self.combo_category = QComboBox()
        self.combo_category.setStyleSheet("""
            QComboBox {
                background: #13122c;
                color: #e2e8f0;
                border: 1px solid #7c3aed66;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11.5px;
                font-weight: 600;
            }
            QComboBox QAbstractItemView {
                background: #0d0e24;
                color: #f1f5f9;
                selection-background-color: #8b5cf6;
                border: 1px solid #7c3aed;
            }
        """)

        categories = [
            ("Digital Creator", "181475575221097"),
            ("Personal Blog", "180164628683562"),
            ("Entrepreneur", "182449195116744"),
            ("Public Figure", "181533221876527"),
            ("News & Media Website", "190565860965313"),
            ("Community", "2612"),
            ("E-commerce Website", "180556108643801"),
            ("App Page", "181048688591873"),
            ("Software Company", "181423855222067"),
            ("Video Creator", "2703")
        ]
        for name, cid in categories:
            self.combo_category.addItem(name, cid)

        layout.addWidget(self.combo_category)

        # Status Label & Progress Bar
        self.lbl_status = QLabel("Ready to create page.")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        layout.addWidget(self.lbl_status)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setFixedHeight(5)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setVisible(False)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                background: #13122c;
                border: none;
                border-radius: 2.5px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #38bdf8);
                border-radius: 2.5px;
            }
        """)
        layout.addWidget(self.prog_bar)

        # Action Buttons
        h_btn = QHBoxLayout()
        h_btn.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #18112e;
                color: #cbd5e1;
                border: 1px solid #7c3aed44;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #231942;
                color: white;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_create = QPushButton("⚡ Create Page Now")
        self.btn_create.setCursor(Qt.PointingHandCursor)
        self.btn_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #06b6d4);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #22d3ee);
            }
            QPushButton:disabled {
                background: #334155;
                color: #64748b;
            }
        """)
        self.btn_create.clicked.connect(self._start_creation)

        h_btn.addWidget(self.btn_cancel)
        h_btn.addWidget(self.btn_create)
        layout.addLayout(h_btn)

        root_layout.addWidget(main_card)

    def _on_profile_selected(self, index: int):
        if hasattr(self, "combo_profiles"):
            p_data = self.combo_profiles.itemData(index)
            if p_data:
                self.profile_data = p_data
                self._resolve_user_data_dir(p_data)
                if self.rb_random.isChecked():
                    self.txt_page_name.setText(generate_random_page_name(p_data))

    def _toggle_name_mode(self):
        if self.rb_random.isChecked():
            self.txt_page_name.setText(generate_random_page_name(self.profile_data))
            self.txt_page_name.setStyleSheet("""
                QLineEdit {
                    background: #13122c;
                    color: #38bdf8;
                    border: 1px solid #7c3aed66;
                    border-radius: 8px;
                    padding: 7px 10px;
                    font-size: 12px;
                    font-weight: 700;
                }
            """)
        else:
            self.txt_page_name.setStyleSheet("""
                QLineEdit {
                    background: #13122c;
                    color: #f1f5f9;
                    border: 1.5px solid #a855f7;
                    border-radius: 8px;
                    padding: 7px 10px;
                    font-size: 12px;
                    font-weight: 700;
                }
            """)
            self.txt_page_name.setFocus()
            self.txt_page_name.selectAll()

    def _start_creation(self):
        if not self.user_data_dir or not os.path.exists(self.user_data_dir):
            self.lbl_status.setText("🔴 Error: Profile directory not found on disk!")
            self.lbl_status.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700; border: none;")
            return

        target_name = self.txt_page_name.text().strip()
        if not target_name:
            target_name = generate_random_page_name(self.profile_data)
            self.txt_page_name.setText(target_name)

        cat_id = self.combo_category.currentData()
        cat_name = self.combo_category.currentText()

        self.btn_create.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.lbl_status.setText(f"⏳ Creating '{target_name}' in Facebook backend...")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700; border: none;")

        self.worker = QuickCreationWorker(
            user_data_dir=self.user_data_dir,
            page_name=target_name,
            cat_id=cat_id,
            cat_name=cat_name,
            headless=False,
            profile_data=self.profile_data
        )
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, ok: bool, page_id: str, page_link: str, name: str, cat: str):
        self.prog_bar.setVisible(False)
        self.btn_create.setEnabled(True)

        if ok:
            self.lbl_status.setText(f"🟢 Success! '{name}' created (ID: {page_id})")
            self.lbl_status.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 700; border: none;")
            self.btn_create.setText("✨ Create Another Page")
            if self.rb_random.isChecked():
                self.txt_page_name.setText(generate_random_page_name(self.profile_data))
        else:
            self.lbl_status.setText(f"🔴 Failed: {page_id}")
            self.lbl_status.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700; border: none;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


def launch_ui(profile_mgr=None, parent=None, **kwargs) -> bool:
    """Invoked dynamically when user clicks 'Run Bot' in srkBrowser."""
    dlg = QuickPageCreatorModal(profile_mgr=profile_mgr, parent=parent, **kwargs)
    return dlg.exec() == QDialog.DialogCode.Accepted


def main(profile_mgr=None, parent=None, **kwargs) -> bool:
    """Main entrypoint for srkBrowser."""
    return launch_ui(profile_mgr=profile_mgr, parent=parent, **kwargs)


# Export only the exact symbols to prevent QMessageBox subclass detection in dir(mod)
__all__ = ["QuickPageCreatorModal", "launch_ui", "main"]
