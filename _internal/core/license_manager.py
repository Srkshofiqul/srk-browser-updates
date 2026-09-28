"""
Browser Profile Manager - Cryptographic HWID License Manager Module
Python 3.13 / PySide6 Desktop Application
Developer: Srk Shofiqul (srkbrowser.com)
"""

import os
import sys
import json
import base64
import hashlib
import hmac
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

try:
    from config import BASE_DIR
except Exception:
    BASE_DIR = Path(__file__).resolve().parent.parent

APPDATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "BrowserProfileManager"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)
LICENSE_FILE = APPDATA_DIR / "license.dat"
LOCAL_DATA_LICENSE = BASE_DIR / "data" / "license.dat"

SECRET_SALT = "SRK_SHOFIQUL_SECURE_HWID_LICENSE_KEY_2026_SRITZONE"


_CACHED_HWID: Optional[str] = None


def get_hardware_id() -> str:
    """
    Generates a unique, persistent Hardware ID (HWID) based on CPU ID,
    Motherboard Serial, and System Drive UUID. Fast cached.
    Formatted as: SRK-XXXX-XXXX-XXXX
    """
    global _CACHED_HWID
    if _CACHED_HWID:
        return _CACHED_HWID

    # Fast disk cache check (0.0001s)
    hwid_cache_file = APPDATA_DIR / ".hwid_cache_legacy"
    try:
        if hwid_cache_file.exists():
            cached = hwid_cache_file.read_text(encoding="utf-8").strip()
            if cached.startswith("SRK-") and len(cached) >= 14:
                _CACHED_HWID = cached
                return _CACHED_HWID
    except Exception:
        pass

    raw_components = []

    # 1. System Platform Info
    raw_components.append(platform.machine())
    raw_components.append(platform.processor())

    # 2. Windows CPU & Motherboard Serial via CIM / PowerShell
    if os.name == 'nt':
        try:
            cmd = "powershell -NoProfile -Command \"Get-CimInstance -ClassName Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber\""
            mb_serial = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
            if mb_serial:
                raw_components.append(mb_serial)
        except Exception:
            pass

        try:
            cmd_cpu = "powershell -NoProfile -Command \"Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty ProcessorId\""
            cpu_id = subprocess.check_output(cmd_cpu, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
            if cpu_id:
                raw_components.append(cpu_id)
        except Exception:
            pass

    # Fallback to node name if components empty
    if not raw_components:
        raw_components.append(platform.node())

    raw_str = "|".join(raw_components)
    digest = hashlib.sha256(raw_str.encode('utf-8')).hexdigest().upper()

    part1 = digest[0:4]
    part2 = digest[4:8]
    part3 = digest[8:12]
    _CACHED_HWID = f"SRK-{part1}-{part2}-{part3}"

    try:
        hwid_cache_file.write_text(_CACHED_HWID, encoding="utf-8")
    except Exception:
        pass

    return _CACHED_HWID


def generate_srk_license(hwid: str, name: str = "", phone: str = "", plan: str = "days_30", custom_days: int = 0) -> str:
    """
    Generates an authenticated HMAC-SHA256 encrypted license key for SRK Browser.
    Encodes Client Name, Phone Number, Machine HWID, and Duration Plan.
    """
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


def generate_license_key(hwid: str, days_valid: int = 365) -> str:
    """
    Legacy wrapper for compatibility: generates SRK license for given days.
    """
    if days_valid == 1:
        return generate_srk_license(hwid, "Trial User", "", "trial_24h")
    elif days_valid <= 0:
        return generate_srk_license(hwid, "VIP Member", "", "lifetime")
    else:
        return generate_srk_license(hwid, "VIP Member", "", f"days_{days_valid}", custom_days=days_valid)


def verify_license_key(hwid: str, license_key: str) -> Tuple[bool, str, int, Dict[str, Any]]:
    """
    Verifies if a License Key is valid (supports SRK new format, legacy KEY- format, and website tokens).
    Returns (is_valid, message, expiration_timestamp, license_metadata).
    """
    clean_key = license_key.strip()
    if not clean_key:
        return False, "License Key is empty.", 0, {}

    # 1. New Full-Payload Format: SRK-<payload>-<sig>
    if clean_key.startswith("SRK-") and clean_key.count("-") >= 2:
        try:
            parts = clean_key.split("-", 2)
            encoded_payload, signature = parts[1], parts[2]

            pad_len = 4 - (len(encoded_payload) % 4)
            if pad_len != 4:
                encoded_payload += "=" * pad_len

            raw_json = base64.urlsafe_b64decode(encoded_payload.encode('utf-8')).decode('utf-8')
            expected_sig = hmac.new(SECRET_SALT.encode('utf-8'), raw_json.encode('utf-8'), hashlib.sha256).hexdigest()[:16].upper()
            if not hmac.compare_digest(signature.upper(), expected_sig):
                return False, "Invalid License Key signature (Tampered Key).", 0, {}

            data = json.loads(raw_json)
            key_hwid = str(data.get("h", "")).upper()
            curr_hwid_clean = hwid.strip().upper()

            # Normalize SRL- vs SRK- prefix in HWID comparison
            norm_key_hwid = key_hwid.replace("SRL-", "").replace("SRK-", "")
            norm_curr_hwid = curr_hwid_clean.replace("SRL-", "").replace("SRK-", "")

            if key_hwid not in ("GLOBAL", "ANY", "MASTER") and norm_key_hwid != norm_curr_hwid:
                return False, f"License Key is registered to another PC ({key_hwid}). Cannot be used on this computer.", 0, data

            exp_timestamp = int(data.get("e", 0))
            now = int(time.time())

            if exp_timestamp > 0 and now > exp_timestamp:
                exp_date_str = datetime.fromtimestamp(exp_timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M')
                return False, f"License Key expired on {exp_date_str} UTC.", exp_timestamp, data

            plan_label = data.get("l", "VIP Access")
            exp_info = "Lifetime Access" if exp_timestamp == 0 else f"Valid until {datetime.fromtimestamp(exp_timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M')}"
            return True, f"Active {plan_label} ({exp_info})", exp_timestamp, data

        except Exception as err:
            return False, f"License parsing error: {err}", 0, {}

    # 2. Legacy Cryptographic Format: KEY-<payload>-<sig>
    if clean_key.startswith("KEY-") and "-" in clean_key[4:]:
        try:
            parts = clean_key[4:].split("-")
            if len(parts) == 2:
                encoded_payload, signature = parts[0], parts[1]
                pad_len = 4 - (len(encoded_payload) % 4)
                if pad_len != 4:
                    encoded_payload += "=" * pad_len

                payload = base64.urlsafe_b64decode(encoded_payload.encode('utf-8')).decode('utf-8')
                key_hwid, exp_str = payload.split(":", 1)
                exp_timestamp = int(exp_str)

                expected_sig = hmac.new(SECRET_SALT.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16].upper()
                if not hmac.compare_digest(signature.upper(), expected_sig):
                    return False, "Invalid signature.", 0, {}

                norm_key = key_hwid.replace("SRL-", "").replace("SRK-", "").upper()
                norm_curr = hwid.replace("SRL-", "").replace("SRK-", "").upper()
                if key_hwid.upper() not in ("GLOBAL", "ANY", "MASTER") and norm_key != norm_curr:
                    return False, "Key does not match this PC HWID.", 0, {}

                if exp_timestamp > 0 and time.time() > exp_timestamp:
                    return False, "License expired.", exp_timestamp, {}

                data = {
                    "h": key_hwid,
                    "n": "VIP Member",
                    "p": "",
                    "l": "Lifetime Access" if exp_timestamp == 0 else "VIP Access",
                    "e": exp_timestamp
                }
                return True, "Active License", exp_timestamp, data
        except Exception as e:
            return False, f"Legacy verification error: {e}", 0, {}

    return False, "Invalid License Key format.", 0, {}


def save_activated_license(license_key: str, client_name: str = "", client_phone: str = "") -> bool:
    """Save activated license key and client info to encrypted local dat and json files."""
    try:
        hwid = get_hardware_id()
        is_ok, msg, exp_t, meta = verify_license_key(hwid, license_key)
        
        name_val = client_name.strip() or meta.get("n", "") or "VIP Member"
        phone_val = client_phone.strip() or meta.get("p", "")
        plan_lbl = meta.get("l", "VIP Access")
        plan_code = meta.get("c", "days_30")

        exp_str = "Lifetime" if exp_t == 0 else datetime.fromtimestamp(exp_t).strftime("%Y-%m-%d %H:%M:%S")

        data = {
            "hwid": hwid,
            "license_key": license_key.strip(),
            "name": name_val,
            "customer_name": name_val,
            "phone": phone_val,
            "plan": plan_code,
            "plan_label": plan_lbl,
            "plan_code": plan_code,
            "exp_timestamp": exp_t,
            "expires_at": exp_str,
            "activated_at": int(time.time())
        }

        # 1. Save DAT format
        encoded = base64.b64encode(json.dumps(data, ensure_ascii=False).encode('utf-8')).decode('utf-8')
        try:
            with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                f.write(encoded)
        except Exception:
            pass

        try:
            LOCAL_DATA_LICENSE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOCAL_DATA_LICENSE, "w", encoding="utf-8") as f:
                f.write(encoded)
        except Exception:
            pass

        # 2. Save JSON format for telegram_license_shield
        try:
            with open(APPDATA_DIR / "license.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        try:
            with open(LOCAL_DATA_LICENSE.parent / "license.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return True
    except Exception:
        return False


def load_activated_license() -> Optional[Dict[str, Any]]:
    """Load activated license from local JSON or DAT files if present."""
    # 1. Check JSON files first (from Telegram Cloud Approval or offline key)
    json_paths = [
        APPDATA_DIR / "license.json",
        LOCAL_DATA_LICENSE.parent / "license.json",
        Path(__file__).resolve().parent.parent.parent / "data" / "license.json"
    ]
    for jp in json_paths:
        try:
            if jp.exists():
                with open(jp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data and isinstance(data, dict):
                    name = data.get("customer_name") or data.get("name") or "VIP Member"
                    phone = data.get("phone", "")
                    plan_lbl = data.get("plan_label") or data.get("plan", "VIP Access").capitalize()
                    plan_code = data.get("plan_code") or data.get("plan", "days_30")
                    exp_t = data.get("exp_timestamp", 0)

                    if exp_t == 0 and data.get("expires_at") and data.get("expires_at") != "Lifetime":
                        try:
                            exp_str = data["expires_at"]
                            if len(exp_str) == 10:
                                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
                            else:
                                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
                            exp_t = int(exp_dt.timestamp())
                        except Exception:
                            pass

                    return {
                        "hwid": data.get("hwid", ""),
                        "license_key": data.get("signature") or data.get("license_key", "ACTIVE-VIP-KEY"),
                        "name": name,
                        "customer_name": name,
                        "phone": phone,
                        "plan": plan_code,
                        "plan_label": plan_lbl,
                        "plan_code": plan_code,
                        "exp_timestamp": exp_t,
                        "expires_at": data.get("expires_at", "Lifetime" if exp_t == 0 else ""),
                        "activated_at": data.get("activated_at", int(time.time()))
                    }
        except Exception:
            pass

    # 2. Check DAT files
    for target_path in [LICENSE_FILE, LOCAL_DATA_LICENSE]:
        try:
            if target_path.exists():
                with open(target_path, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                if raw:
                    decoded = base64.b64decode(raw.encode('utf-8')).decode('utf-8')
                    return json.loads(decoded)
        except Exception:
            pass
    return None


def get_active_license_info() -> Dict[str, Any]:
    """
    Returns rich, dynamic license profile info for UI headers and cards.
    Contains client name, phone number, formatted badge, remaining countdown, etc.
    """
    hwid = get_hardware_id()
    saved = load_activated_license()

    if not saved or (not saved.get("license_key") and not saved.get("plan")):
        return {
            "is_active": False,
            "is_expired": False,
            "name": "Unactivated User",
            "phone": "No Contact Info",
            "plan_badge": "⚠️ Unlicensed",
            "validity_text": "🔑 ক্লিক করে লাইসেন্স অ্যাক্টিভ করুন",
            "nav_badge": "🔑 Activate",
            "remaining_seconds": 0,
            "exp_timestamp": 0,
            "hwid": hwid
        }

    key = saved.get("license_key", "")
    is_ok, msg, exp_t, meta = verify_license_key(hwid, key)

    name_str = saved.get("name") or saved.get("customer_name") or meta.get("n") or "VIP Member"
    phone_str = saved.get("phone") or meta.get("p") or ""
    plan_lbl = saved.get("plan_label") or meta.get("l") or "VIP Access"

    # If key wasn't in generator format but was verified and stored via license.json/dat
    if not is_ok and saved.get("exp_timestamp") is not None:
        exp_t = saved.get("exp_timestamp", 0)
        is_ok = (exp_t == 0 or time.time() <= exp_t)

    # Lifetime license
    if is_ok and (exp_t == 0 or saved.get("expires_at") == "Lifetime"):
        return {
            "is_active": True,
            "is_expired": False,
            "name": name_str,
            "phone": phone_str,
            "plan_badge": "👑 Lifetime VIP Member",
            "validity_text": "⚡ Lifetime Unlimited Access",
            "nav_badge": "👑 Lifetime",
            "remaining_seconds": 999999999,
            "exp_timestamp": 0,
            "hwid": hwid
        }

    now = int(time.time())
    rem_sec = exp_t - now

    if rem_sec <= 0 or not is_ok:
        return {
            "is_active": False,
            "is_expired": True,
            "name": name_str,
            "phone": phone_str,
            "plan_badge": "🔴 License Expired",
            "validity_text": "❌ লাইসেন্সের মেয়াদ শেষ (রিনিউ করুন)",
            "nav_badge": "⚠️ Expired",
            "remaining_seconds": 0,
            "exp_timestamp": exp_t,
            "hwid": hwid
        }

    # Format remaining time
    try:
        exp_date_formatted = datetime.fromtimestamp(exp_t).strftime('%d %b %Y, %I:%M %p')
    except Exception:
        exp_date_formatted = str(exp_t)

    # 24 Hours or under
    if rem_sec < 86400:
        hours = int(rem_sec // 3600)
        mins = int((rem_sec % 3600) // 60)
        val_str = f"⏳ আর {hours} ঘণ্টা {mins} মিনিট বাকি (মেয়াদ শেষ: {exp_date_formatted})"
        nav_str = f"⏱️ {hours}h Trial" if "trial" in plan_lbl.lower() else f"⏱️ {hours}h Left"
        badge_str = "⏱️ 24 Hours Free Trial" if "trial" in plan_lbl.lower() else f"💎 {plan_lbl}"
    else:
        days = int(rem_sec // 86400)
        val_str = f"⏳ আর {days} দিন বাকি (মেয়াদ শেষ: {exp_date_formatted})"
        nav_str = f"👑 {days} Days Left"
        badge_str = f"👑 {plan_lbl}"

    return {
        "is_active": True,
        "is_expired": False,
        "name": name_str,
        "phone": phone_str,
        "plan_badge": badge_str,
        "validity_text": val_str,
        "nav_badge": nav_str,
        "remaining_seconds": rem_sec,
        "exp_timestamp": exp_t,
        "hwid": hwid
    }


def get_license_display_badge() -> str:
    """Convenience helper for top toolbar header."""
    info = get_active_license_info()
    if info["is_active"]:
        return f"{info['nav_badge']} | {info['name']}"
    elif info["is_expired"]:
        return "⚠️ License Expired"
    return "⚠️ License Not Active"
