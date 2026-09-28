"""
SRK Browser - Master License Key Generator Tool
Official Seller & Administrator Tool
Developer: Muhammad Shofiqul (srkbrowser.com)
"""

import sys
import os
import json
import base64
import hashlib
import hmac
import time
from datetime import datetime, timezone
from pathlib import Path

SECRET_SALT = "SRK_SHOFIQUL_SECURE_HWID_LICENSE_KEY_2026_SRITZONE"

def generate_srk_key(hwid: str, name: str = "", phone: str = "", plan: str = "days_30", custom_days: int = 0) -> str:
    now = int(time.time())
    hwid_clean = hwid.strip().upper() or "GLOBAL"

    plan_clean = str(plan).lower()
    if plan_clean in ("trial_24h", "24h", "trial"):
        exp = now + 86400  # 24 Hours
        plan_label = "24 Hours Free Trial"
        plan_code = "trial_24h"
    elif plan_clean in ("days_7", "7d", "7"):
        exp = now + (7 * 86400)
        plan_label = "7 Days VIP Access"
        plan_code = "days_7"
    elif plan_clean in ("days_14", "14d", "14"):
        exp = now + (14 * 86400)
        plan_label = "14 Days VIP Access"
        plan_code = "days_14"
    elif plan_clean in ("days_21", "21d", "21"):
        exp = now + (21 * 86400)
        plan_label = "21 Days VIP Access"
        plan_code = "days_21"
    elif plan_clean in ("days_30", "30d", "30", "1m"):
        exp = now + (30 * 86400)
        plan_label = "30 Days VIP Access"
        plan_code = "days_30"
    elif plan_clean in ("lifetime", "life", "0", "unlimited"):
        exp = 0  # Lifetime
        plan_label = "Lifetime VIP Access"
        plan_code = "lifetime"
    elif custom_days > 0:
        exp = now + (custom_days * 86400)
        plan_label = f"{custom_days} Days VIP Access"
        plan_code = f"days_{custom_days}"
    else:
        exp = now + (30 * 86400)
        plan_label = "30 Days VIP Access"
        plan_code = "days_30"

    payload_dict = {
        "h": hwid_clean,
        "n": name.strip() or "VIP Member",
        "p": phone.strip() or "",
        "l": plan_label,
        "c": plan_code,
        "e": exp,
        "i": now
    }

    raw_json = json.dumps(payload_dict, separators=(',', ':'))
    signature = hmac.new(SECRET_SALT.encode('utf-8'), raw_json.encode('utf-8'), hashlib.sha256).hexdigest()[:16].upper()
    encoded_payload = base64.urlsafe_b64encode(raw_json.encode('utf-8')).decode('utf-8').rstrip('=')

    return f"SRK-{encoded_payload}-{signature}"


def launch_gui():
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QTextEdit,
        QFrame, QMessageBox
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    win = QMainWindow()
    win.setWindowTitle("🔑 SRK Browser — Master License Key Generator (Admin)")
    win.setFixedSize(620, 720)
    win.setStyleSheet("""
        QMainWindow {
            background-color: #0b0d17;
            color: #f1f5f9;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }
        QLabel {
            color: #cbd5e1;
            font-size: 12px;
            font-weight: 600;
        }
        QLineEdit, QComboBox, QSpinBox, QTextEdit {
            background-color: #131626;
            color: #f8fafc;
            border: 1.5px solid #232742;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            selection-background-color: #6366f1;
        }
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
            border-color: #818cf8;
            background-color: #171b30;
        }
    """)

    central = QWidget()
    win.setCentralWidget(central)
    root = QVBoxLayout(central)
    root.setContentsMargins(24, 20, 24, 20)
    root.setSpacing(14)

    # Header Card
    hdr = QFrame()
    hdr.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1b4b, stop:1 #0f172a);
            border: 1px solid rgba(129, 140, 248, 0.3);
            border-radius: 12px;
            padding: 12px;
        }
    """)
    hdr_lay = QHBoxLayout(hdr)
    hdr_icon = QLabel("👑")
    hdr_icon.setStyleSheet("font-size: 32px; background: transparent;")
    hdr_lay.addWidget(hdr_icon)

    hdr_texts = QVBoxLayout()
    hdr_title = QLabel("SRK Browser — Master Key Generator")
    hdr_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff; background: transparent;")
    hdr_sub = QLabel("Official Seller Tool • Create 24h Trials, 7-30 Days, & Lifetime Keys")
    hdr_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
    hdr_texts.addWidget(hdr_title)
    hdr_texts.addWidget(hdr_sub)
    hdr_lay.addLayout(hdr_texts)
    hdr_lay.addStretch()
    root.addWidget(hdr)

    # 1. HWID
    root.addWidget(QLabel("1. Client Machine Hardware ID (HWID):"))
    txt_hwid = QLineEdit()
    txt_hwid.setPlaceholderText("Paste client HWID (e.g. SRK-C63E-B353-02C2-79CC or GLOBAL)")
    txt_hwid.setStyleSheet("font-family: 'Consolas', monospace; color: #fbbf24; font-weight: bold;")
    root.addWidget(txt_hwid)

    # 2. Client Name
    root.addWidget(QLabel("2. Client Full Name (গ্রাহকের নাম):"))
    txt_name = QLineEdit()
    txt_name.setPlaceholderText("e.g. রফিকুল ইসলাম বা Md. Shofiqul")
    root.addWidget(txt_name)

    # 3. Client Phone
    root.addWidget(QLabel("3. Client Mobile / Telegram (মোবাইল / টেলিগ্রাম):"))
    txt_phone = QLineEdit()
    txt_phone.setPlaceholderText("e.g. 017xxxxxxxx বা @username")
    root.addWidget(txt_phone)

    # 4. Plan Selector
    root.addWidget(QLabel("4. License Duration / Package (লাইসেন্সের মেয়াদ):"))
    cmb_plan = QComboBox()
    cmb_plan.addItems([
        "🟢 24 Hours Free Trial (২৪ ঘণ্টার ফ্রি ট্রায়াল)",
        "🔵 7 Days Access (৭ দিন / ১ সপ্তাহ)",
        "🔵 14 Days Access (১৪ দিন / ২ সপ্তাহ)",
        "🔵 21 Days Access (২১ দিন / ৩ সপ্তাহ)",
        "🔵 30 Days Access (৩০ দিন / ১ মাস)",
        "🟣 Lifetime Access (আজীবন আনলিমিটেড)",
        "🟡 Custom Days (কাস্টম দিন সিলেক্ট করুন)"
    ])
    cmb_plan.setCurrentIndex(4)  # Default: 30 Days
    root.addWidget(cmb_plan)

    spin_custom = QSpinBox()
    spin_custom.setRange(1, 3650)
    spin_custom.setValue(60)
    spin_custom.setPrefix("Custom Days: ")
    spin_custom.setSuffix(" Days")
    spin_custom.hide()
    root.addWidget(spin_custom)

    def on_plan_changed(idx):
        spin_custom.setVisible(idx == 6)

    cmb_plan.currentIndexChanged.connect(on_plan_changed)

    # Generate Button
    btn_gen = QPushButton("⚡ Generate Cryptographic License Key")
    btn_gen.setCursor(Qt.PointingHandCursor)
    btn_gen.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
            color: #ffffff;
            font-size: 13.5px;
            font-weight: 800;
            padding: 10px 16px;
            border-radius: 8px;
            border: 1px solid #6366f1;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
        }
    """)
    root.addWidget(btn_gen)

    # Output Key Section
    root.addWidget(QLabel("Generated License Key (ক্লায়েন্টকে পাঠানোর চাবি):"))
    txt_output = QTextEdit()
    txt_output.setReadOnly(True)
    txt_output.setFixedHeight(75)
    txt_output.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11.5px; color: #34d399; font-weight: bold;")
    root.addWidget(txt_output)

    # Copy Button
    btn_copy = QPushButton("📋 Copy License Message to Send Client")
    btn_copy.setCursor(Qt.PointingHandCursor)
    btn_copy.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f766e, stop:1 #0d9488);
            color: #ffffff;
            font-size: 13px;
            font-weight: 800;
            padding: 9px 14px;
            border-radius: 8px;
            border: 1px solid #14b8a6;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #14b8a6, stop:1 #0f766e);
        }
    """)
    root.addWidget(btn_copy)

    lbl_status = QLabel("")
    lbl_status.setStyleSheet("color: #38bdf8; font-size: 11.5px; font-weight: 700;")
    root.addWidget(lbl_status)

    def do_generate():
        hwid_val = txt_hwid.text().strip()
        if not hwid_val:
            QMessageBox.warning(win, "Missing HWID", "অনুগ্রহ করে ক্লায়েন্টের Machine HWID দিন।")
            return

        name_val = txt_name.text().strip() or "VIP Member"
        phone_val = txt_phone.text().strip()

        idx = cmb_plan.currentIndex()
        plan_map = ["trial_24h", "days_7", "days_14", "days_21", "days_30", "lifetime", "custom"]
        chosen_plan = plan_map[idx]
        custom_d = spin_custom.value() if chosen_plan == "custom" else 0

        key = generate_srk_key(hwid_val, name_val, phone_val, chosen_plan, custom_d)
        txt_output.setText(key)

        now = int(time.time())
        if chosen_plan == "trial_24h":
            exp_text = "২৪ ঘণ্টার ফ্রি ট্রায়াল"
        elif chosen_plan == "lifetime":
            exp_text = "আজীবন আনলিমিটেড অ্যাক্সেস"
        else:
            days_count = custom_d if chosen_plan == "custom" else int(chosen_plan.split("_")[1])
            exp_date = datetime.fromtimestamp(now + (days_count * 86400)).strftime('%d %b %Y, %I:%M %p')
            exp_text = f"{days_count} দিন (মেয়াদ শেষ: {exp_date})"

        lbl_status.setText(f"✅ চাবি তৈরি সফল! ক্লায়েন্ট: {name_val} | মেয়াদ: {exp_text}")

    def do_copy():
        key = txt_output.toPlainText().strip()
        if not key:
            QMessageBox.warning(win, "No Key", "আগে জেনারেট বাটনে চাপ দিয়ে চাবি তৈরি করুন।")
            return

        name_val = txt_name.text().strip() or "Client"
        plan_text = cmb_plan.currentText()

        msg = (
            f"🎉 ধন্যবাদ {name_val}! আপনার srkBrowser লাইসেন্স সক্রিয় করার চাবি নিচে দেওয়া হলো:\n\n"
            f"🔑 License Key:\n{key}\n\n"
            f"📦 Plan: {plan_text}\n"
            f"💡 সফটওয়্যার ওপেন করে কি (Key) বক্সে পেস্ট করে 'Activate' বাটনে চাপ দিন।"
        )
        QApplication.clipboard().setText(msg)
        QMessageBox.information(win, "Copied!", "✅ সম্পূর্ণ মেসেজটি ক্লিপবোর্ডে কপি করা হয়েছে!\n\nএখন এটি ক্লায়েন্টকে টেলিগ্রাম বা হোয়াটসঅ্যাপে পাঠিয়ে দিন।")

    btn_gen.clicked.connect(do_generate)
    btn_copy.clicked.connect(do_copy)

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SRK License Key Generator")
    parser.add_argument("--hwid", help="Client HWID")
    parser.add_argument("--name", default="", help="Client Name")
    parser.add_argument("--phone", default="", help="Client Phone")
    parser.add_argument("--plan", default="days_30", choices=["trial_24h", "days_7", "days_14", "days_21", "days_30", "lifetime"])
    parser.add_argument("--days", type=int, default=0, help="Custom days")
    args, unknown = parser.parse_known_args()

    if args.hwid:
        k = generate_srk_key(args.hwid, args.name, args.phone, args.plan, args.days)
        print("Generated Key:", k)
    else:
        launch_gui()
