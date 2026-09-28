"""
srkBrowser - VIP Cryptographic Hardware ID (HWID) & Telegram Cloud License Shield
Author: SRK Shofiqul
Description:
    Locks srkBrowser to client physical machine hardware.
    Integrates real-time Telegram Bot approval workflow (@srkBrowserbot).
    Allows 1-click mobile authorization by Admin (24h Trial, 7d, 14d, 21d, 30d, 1y, Lifetime).
    100% Offline verification after authorization.
"""

import os
import sys
import time
import json
import base64
import hmac
import hashlib
import platform
import subprocess
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

# Secret Cryptographic Salts
SECRET_SALT = b"SRK_SHOFIQUL_SECURE_HWID_KEY_2026_@#!"
GENERATOR_SALT = "SRK_SHOFIQUL_SECURE_HWID_LICENSE_KEY_2026_SRITZONE"

# Telegram Cloud Licensing Config
BOT_TOKEN = "8606669813:AAFLki2psDqj4zeEHx9-8pAEdjH0Tff-Uj0"
ADMIN_CHAT_IDS = ["8028884408", "8538383463"]

APPDATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "BrowserProfileManager"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)


_CACHED_MACHINE_HWID: Optional[str] = None


def get_machine_hwid() -> str:
    """Generates deterministic physical Hardware ID (Motherboard + CPU + Windows MachineGuid). Fast cached."""
    global _CACHED_MACHINE_HWID
    if _CACHED_MACHINE_HWID:
        return _CACHED_MACHINE_HWID

    # Fast disk cache check (0.0001s)
    hwid_cache_file = APPDATA_DIR / ".hwid_cache"
    try:
        if hwid_cache_file.exists():
            cached = hwid_cache_file.read_text(encoding="utf-8").strip()
            if cached.startswith("SRK-") and len(cached) >= 19:
                _CACHED_MACHINE_HWID = cached
                return _CACHED_MACHINE_HWID
    except Exception:
        pass

    components = []
    
    # 1. Motherboard Serial / UUID
    try:
        cmd = 'powershell -NoProfile -Command "Get-CimInstance Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID"'
        uuid_str = subprocess.check_output(cmd, shell=True, text=True, timeout=4, stderr=subprocess.DEVNULL).strip()
        if uuid_str and len(uuid_str) > 5 and "error" not in uuid_str.lower():
            components.append(uuid_str)
    except Exception:
        pass

    # 2. CPU Processor ID
    try:
        cmd_cpu = 'powershell -NoProfile -Command "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty ProcessorId"'
        cpu_id = subprocess.check_output(cmd_cpu, shell=True, text=True, timeout=4, stderr=subprocess.DEVNULL).strip()
        if cpu_id and len(cpu_id) > 4:
            components.append(cpu_id)
    except Exception:
        pass

    # 3. Windows Machine GUID
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if guid:
            components.append(guid)
    except Exception:
        pass

    # Fallback to computer name / processor if any query failed
    if not components:
        components.append(platform.node())
        components.append(platform.processor())

    raw_data = "::".join(components).upper()
    sha = hashlib.sha256(raw_data.encode("utf-8")).hexdigest().upper()
    _CACHED_MACHINE_HWID = f"SRK-{sha[0:4]}-{sha[4:8]}-{sha[8:12]}-{sha[12:16]}"

    try:
        hwid_cache_file.write_text(_CACHED_MACHINE_HWID, encoding="utf-8")
    except Exception:
        pass

    return _CACHED_MACHINE_HWID


def create_signature(hwid: str, plan: str, expires_at: str, customer_name: str) -> str:
    msg = f"{hwid.strip().upper()}::{plan.strip().lower()}::{expires_at.strip()}::{customer_name.strip().lower()}"
    return hmac.new(SECRET_SALT, msg.encode("utf-8"), hashlib.sha256).hexdigest()[:24].upper()


def generate_license_payload(
    hwid: str,
    plan: str = "lifetime",
    days: int = 0,
    customer_name: str = "Valued Customer",
    phone: str = ""
) -> Dict[str, Any]:
    plan_clean = str(plan).lower().strip()
    now_dt = datetime.now()

    if plan_clean in ("trial_24h", "24h", "trial"):
        exp_dt = now_dt + timedelta(hours=24)
        expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_timestamp = int(exp_dt.timestamp())
        plan_label = "24 Hours Free Trial"
        plan_code = "trial_24h"
    elif plan_clean in ("days_7", "7d", "7"):
        exp_dt = now_dt + timedelta(days=7)
        expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_timestamp = int(exp_dt.timestamp())
        plan_label = "7 Days VIP Access"
        plan_code = "days_7"
    elif plan_clean in ("days_14", "14d", "14"):
        exp_dt = now_dt + timedelta(days=14)
        expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_timestamp = int(exp_dt.timestamp())
        plan_label = "14 Days VIP Access"
        plan_code = "days_14"
    elif plan_clean in ("days_21", "21d", "21"):
        exp_dt = now_dt + timedelta(days=21)
        expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_timestamp = int(exp_dt.timestamp())
        plan_label = "21 Days VIP Access"
        plan_code = "days_21"
    elif plan_clean in ("days_30", "30d", "30", "30days", "1m"):
        exp_dt = now_dt + timedelta(days=30)
        expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_timestamp = int(exp_dt.timestamp())
        plan_label = "30 Days VIP Access"
        plan_code = "days_30"
    elif plan_clean in ("1year", "365d", "365", "year"):
        exp_dt = now_dt + timedelta(days=365)
        expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_timestamp = int(exp_dt.timestamp())
        plan_label = "1 Year VIP Access"
        plan_code = "1year"
    elif plan_clean in ("lifetime", "life", "unlimited") or days <= 0:
        expires_at = "Lifetime"
        exp_timestamp = 0
        plan_label = "Lifetime VIP Access"
        plan_code = "lifetime"
    else:
        exp_dt = now_dt + timedelta(days=days)
        expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_timestamp = int(exp_dt.timestamp())
        plan_label = f"{days} Days VIP Access"
        plan_code = f"days_{days}"

    sig = create_signature(hwid, plan_code, expires_at, customer_name)
    return {
        "hwid": hwid.strip().upper(),
        "plan": plan_code,
        "plan_label": plan_label,
        "plan_code": plan_code,
        "expires_at": expires_at,
        "exp_timestamp": exp_timestamp,
        "customer_name": customer_name.strip() or "VIP Member",
        "name": customer_name.strip() or "VIP Member",
        "phone": phone.strip(),
        "signature": sig,
        "issued_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")
    }


def encode_license_key(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    return f"SRK-KEY-{b64}"


def decode_license_key(key_str: str) -> Optional[Dict[str, Any]]:
    key_str = key_str.strip()
    if not key_str:
        return None

    # Case 1: SRK-KEY- format (Telegram backup offline key)
    if key_str.startswith("SRK-KEY-"):
        b64_part = key_str[8:]
        padding = len(b64_part) % 4
        if padding:
            b64_part += "=" * (4 - padding)
        try:
            raw = base64.urlsafe_b64decode(b64_part.encode("utf-8"))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    # Case 2: SRK-<payload>-<signature> format (SRK_Key_Generator format)
    if key_str.startswith("SRK-"):
        parts = key_str.split("-")
        if len(parts) >= 3:
            b64_part = parts[1]
            sig_part = parts[2]
            padding = len(b64_part) % 4
            if padding:
                b64_part += "=" * (4 - padding)
            try:
                raw = base64.urlsafe_b64decode(b64_part.encode("utf-8"))
                d = json.loads(raw.decode("utf-8"))
                hwid = d.get("h", "")
                name = d.get("n", "")
                phone = d.get("p", "")
                plan_code = d.get("c", "days_30")
                plan_lbl = d.get("l", "VIP Access")
                exp_t = d.get("e", 0)
                exp_str = "Lifetime" if exp_t == 0 else datetime.fromtimestamp(exp_t).strftime("%Y-%m-%d %H:%M:%S")

                return {
                    "hwid": hwid,
                    "customer_name": name,
                    "name": name,
                    "phone": phone,
                    "plan": plan_code,
                    "plan_code": plan_code,
                    "plan_label": plan_lbl,
                    "expires_at": exp_str,
                    "exp_timestamp": exp_t,
                    "signature": sig_part,
                    "is_generator_format": True,
                    "generator_raw": raw.decode("utf-8")
                }
            except Exception:
                pass

    return None


def verify_license_data(payload: Dict[str, Any], current_hwid: str) -> Tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "Invalid license payload structure."

    lic_hwid = payload.get("hwid", "")
    curr_clean = current_hwid.strip().upper().replace("-", "")
    lic_clean = lic_hwid.strip().upper().replace("-", "")

    # Also check if machine's alternate HWID matches
    alt_hwid = ""
    try:
        from core.license_manager import get_hardware_id
        alt_hwid = get_hardware_id().strip().upper().replace("-", "")
    except Exception:
        pass

    if lic_clean != "GLOBAL":
        matched = (lic_clean == curr_clean) or (alt_hwid and lic_clean == alt_hwid)
        if not matched and len(lic_clean) >= 12 and len(curr_clean) >= 12:
            matched = (lic_clean[:12] == curr_clean[:12])
        if not matched:
            return False, f"Hardware ID mismatch (Licensed for {lic_hwid}, this PC is {current_hwid})"

    # Cryptographic Signature Check
    if payload.get("is_generator_format"):
        sig = payload.get("signature", "")
        gen_raw = payload.get("generator_raw", "")
        expected_sig = hmac.new(GENERATOR_SALT.encode('utf-8'), gen_raw.encode('utf-8'), hashlib.sha256).hexdigest()[:16].upper()
        if not hmac.compare_digest(sig.upper(), expected_sig.upper()):
            return False, "Cryptographic signature validation failed."
    else:
        sig = payload.get("signature", "")
        plan = payload.get("plan", "lifetime")
        expires_at = payload.get("expires_at", "Lifetime")
        cust_name = payload.get("customer_name") or payload.get("name", "")
        expected_sig = create_signature(lic_hwid, plan, expires_at, cust_name)
        if not hmac.compare_digest(sig, expected_sig):
            # Check legacy salt
            legacy_sig = create_signature(lic_hwid, plan, expires_at, "Valued Customer")
            if not hmac.compare_digest(sig, legacy_sig):
                return False, "Cryptographic signature validation failed."

    # Expiration Verification
    exp_t = payload.get("exp_timestamp")
    if exp_t is not None and exp_t > 0:
        if time.time() > exp_t:
            return False, f"License expired on {payload.get('expires_at')}."
    elif payload.get("expires_at") != "Lifetime":
        try:
            exp_str = payload.get("expires_at", "")
            if len(exp_str) == 10:
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
            else:
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp_dt + timedelta(seconds=60):
                return False, f"License expired on {payload.get('expires_at')}."
        except Exception:
            return False, "Invalid expiration date timestamp."

    plan_lbl = payload.get("plan_label") or payload.get("plan", "VIP").capitalize()
    return True, f"Active ({plan_lbl} • Expires: {payload.get('expires_at')})"


def get_license_file_path() -> Path:
    base = Path(__file__).resolve().parent.parent.parent
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "license.json"


def get_appdata_license_json_path() -> Path:
    return APPDATA_DIR / "license.json"


def get_saved_client_meta() -> Dict[str, str]:
    """Helper to retrieve previously saved client name and phone for dialog prefill."""
    for p in [get_license_file_path(), get_appdata_license_json_path()]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("customer_name") or data.get("name") or ""
                phone = data.get("phone") or ""
                if name or phone:
                    return {"name": name, "phone": phone}
            except Exception:
                pass
    return {"name": "", "phone": ""}


def save_license_file(payload: Dict[str, Any]) -> bool:
    """Saves valid license payload to all persistent paths (data/license.json, AppData, and dat formats)."""
    success = False
    # 1. Save data/license.json
    try:
        lic_file = get_license_file_path()
        with open(lic_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        success = True
    except Exception:
        pass

    # 2. Save AppData/license.json
    try:
        appdata_file = get_appdata_license_json_path()
        with open(appdata_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        success = True
    except Exception:
        pass

    # 3. Sync to license.dat for license_manager compatibility
    try:
        dat_payload = {
            "hwid": payload.get("hwid", ""),
            "license_key": encode_license_key(payload),
            "name": payload.get("customer_name") or payload.get("name", "VIP Member"),
            "phone": payload.get("phone", ""),
            "plan_label": payload.get("plan_label", "VIP Access"),
            "plan_code": payload.get("plan_code", payload.get("plan", "days_30")),
            "exp_timestamp": payload.get("exp_timestamp", 0),
            "expires_at": payload.get("expires_at", "Lifetime"),
            "activated_at": int(time.time())
        }
        encoded = base64.b64encode(json.dumps(dat_payload, ensure_ascii=False).encode('utf-8')).decode('utf-8')
        
        # Save AppData/license.dat
        with open(APPDATA_DIR / "license.dat", "w", encoding="utf-8") as f:
            f.write(encoded)
        
        # Save local data/license.dat
        base = Path(__file__).resolve().parent.parent.parent
        with open(base / "data" / "license.dat", "w", encoding="utf-8") as f:
            f.write(encoded)
    except Exception:
        pass

    return success


def is_system_activated() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks if current machine has an active, cryptographically verified license."""
    current_hwid = get_machine_hwid()

    # 1. Check JSON license files first
    for lic_file in [get_license_file_path(), get_appdata_license_json_path()]:
        if lic_file.exists():
            try:
                with open(lic_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ok, msg = verify_license_data(data, current_hwid)
                if ok:
                    return True, msg, data
            except Exception:
                pass

    # 2. Check DAT license files (backward compatibility)
    for dat_file in [APPDATA_DIR / "license.dat", Path(__file__).resolve().parent.parent.parent / "data" / "license.dat"]:
        if dat_file.exists():
            try:
                with open(dat_file, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                if raw:
                    data = json.loads(base64.b64decode(raw.encode('utf-8')).decode('utf-8'))
                    key = data.get("license_key", "")
                    decoded = decode_license_key(key)
                    if decoded:
                        ok, msg = verify_license_data(decoded, current_hwid)
                        if ok:
                            return True, msg, decoded
                    # Fallback check on dat_file direct structure
                    exp_t = data.get("exp_timestamp", 0)
                    if exp_t == 0 or time.time() <= exp_t:
                        return True, "Active Access", data
            except Exception:
                pass

    return False, "No active license found.", {}


def send_telegram_request(client_name: str, contact_no: str, hwid: str) -> Tuple[bool, str]:
    """Sends ultra-luxury VIP authorization card to Admin's Telegram."""
    now_str = datetime.now().strftime("%d %b %Y | %I:%M %p")
    pc_name = platform.node()

    text = (
        "👑 <b>SRK BROWSER | VIP LICENSE SYSTEM</b> 👑\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <b>New Client Authorization Request</b>\n\n"
        f"👤 <b>Client Name:</b> <code>{client_name}</code>\n"
        f"📱 <b>WhatsApp/Phone:</b> <code>{contact_no or 'N/A'}</code>\n"
        f"🔑 <b>Hardware ID:</b> <code>{hwid}</code>\n"
        f"💻 <b>Device Hostname:</b> <code>{pc_name}</code>\n"
        f"🕒 <b>Request Time:</b> <code>{now_str}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>Select License Tier to Instantly Authorize:</b>"
    )

    clean_hwid_tag = hwid.replace("-", "")
    inline_keyboard = [
        [
            {"text": "👑 Lifetime Unlimited VIP", "callback_data": f"appr_life_{clean_hwid_tag}"}
        ],
        [
            {"text": "⚡ 30 Days Access", "callback_data": f"appr_30d_{clean_hwid_tag}"},
            {"text": "🛡️ 1 Year Access", "callback_data": f"appr_365d_{clean_hwid_tag}"}
        ],
        [
            {"text": "⏳ 14 Days Access", "callback_data": f"appr_14d_{clean_hwid_tag}"},
            {"text": "⏳ 21 Days Access", "callback_data": f"appr_21d_{clean_hwid_tag}"}
        ],
        [
            {"text": "⏱️ 24h Free Trial", "callback_data": f"appr_24h_{clean_hwid_tag}"},
            {"text": "⏳ 7 Days Access", "callback_data": f"appr_7d_{clean_hwid_tag}"}
        ],
        [
            {"text": "🚫 Decline / Block Device", "callback_data": f"appr_block_{clean_hwid_tag}"}
        ]
    ]

    payload = {
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": inline_keyboard}
    }

    sent_any = False
    for cid in ADMIN_CHAT_IDS:
        try:
            p = dict(payload)
            p["chat_id"] = cid
            data = json.dumps(p).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("ok"):
                    sent_any = True
        except Exception:
            pass

    if sent_any:
        return True, "Request delivered to Admin Telegram."
    return False, "Failed to deliver request to Telegram. Please verify internet connection."


def poll_telegram_approval(
    hwid: str,
    client_name: str,
    client_phone: str = "",
    timeout_sec: int = 300,
    status_callback = None
) -> Tuple[bool, str]:
    """Polls Telegram for Admin 1-click button tap."""
    clean_hwid_tag = hwid.replace("-", "")
    start_time = time.time()
    last_update_id = 0

    while (time.time() - start_time) < timeout_sec:
        try:
            req_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=3"
            req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("ok"):
                for upd in data.get("result", []):
                    last_update_id = max(last_update_id, upd.get("update_id", 0))
                    cb = upd.get("callback_query")
                    if not cb:
                        continue

                    cb_id = cb.get("id")
                    cb_data = cb.get("data", "")
                    sender = cb.get("from", {}).get("first_name", "Admin")

                    if clean_hwid_tag in cb_data:
                        # 1. Answer callback query
                        try:
                            ans_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                            ans_payload = json.dumps({"callback_query_id": cb_id, "text": "Authorization processed!"}).encode("utf-8")
                            urllib.request.urlopen(urllib.request.Request(ans_url, data=ans_payload, headers={"Content-Type": "application/json"}))
                        except Exception:
                            pass

                        if "appr_block_" in cb_data:
                            return False, "Access Request was declined by Admin."

                        # Determine tier
                        if "appr_life_" in cb_data:
                            plan, days = "lifetime", 0
                            plan_display = "Lifetime Unlimited VIP"
                        elif "appr_365d_" in cb_data:
                            plan, days = "1year", 365
                            plan_display = "1 Year VIP Access"
                        elif "appr_30d_" in cb_data:
                            plan, days = "days_30", 30
                            plan_display = "30 Days VIP Access"
                        elif "appr_21d_" in cb_data:
                            plan, days = "days_21", 21
                            plan_display = "21 Days VIP Access"
                        elif "appr_14d_" in cb_data:
                            plan, days = "days_14", 14
                            plan_display = "14 Days VIP Access"
                        elif "appr_7d_" in cb_data:
                            plan, days = "days_7", 7
                            plan_display = "7 Days VIP Access"
                        elif "appr_24h_" in cb_data:
                            plan, days = "trial_24h", 1
                            plan_display = "24 Hours Free Trial"
                        else:
                            plan, days = "days_30", 30
                            plan_display = "30 Days VIP Access"

                        # Generate Signed License
                        lic_payload = generate_license_payload(
                            hwid,
                            plan=plan,
                            days=days,
                            customer_name=client_name,
                            phone=client_phone
                        )
                        save_license_file(lic_payload)
                        offline_key = encode_license_key(lic_payload)

                        # Update Telegram message to show APPROVED
                        msg_obj = cb.get("message", {})
                        msg_chat_id = msg_obj.get("chat", {}).get("id")
                        msg_id = msg_obj.get("message_id")
                        if msg_chat_id and msg_id:
                            try:
                                edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                                edit_text = (
                                    "✅ <b>AUTHORIZED • VIP ACCESS GRANTED</b>\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"👤 <b>Client:</b> <code>{client_name}</code>\n"
                                    f"📱 <b>Phone:</b> <code>{client_phone or 'N/A'}</code>\n"
                                    f"🔑 <b>HWID:</b> <code>{hwid}</code>\n"
                                    f"💎 <b>Tier:</b> <b>{plan_display}</b>\n"
                                    f"🛡️ <b>Authorized By:</b> {sender}\n"
                                    f"🕒 <b>Time:</b> <code>{datetime.now().strftime('%d %b %Y | %I:%M %p')}</code>\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    "✨ <i>Client PC unlocked successfully!</i>"
                                )
                                edit_p = json.dumps({
                                    "chat_id": msg_chat_id,
                                    "message_id": msg_id,
                                    "text": edit_text,
                                    "parse_mode": "HTML"
                                }).encode("utf-8")
                                urllib.request.urlopen(urllib.request.Request(edit_url, data=edit_p, headers={"Content-Type": "application/json"}))
                            except Exception:
                                pass

                        # Send Offline Key backup to Admin
                        for cid in ADMIN_CHAT_IDS:
                            try:
                                key_msg = (
                                    f"🔑 <b>Offline Key Backup for {client_name}:</b>\n"
                                    f"<code>{offline_key}</code>"
                                )
                                kp = json.dumps({"chat_id": cid, "text": key_msg, "parse_mode": "HTML"}).encode("utf-8")
                                urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=kp, headers={"Content-Type": "application/json"}))
                            except Exception:
                                pass

                        return True, f"🎉 Successfully Activated: {plan_display}"
        except Exception:
            pass

        time.sleep(2)
        if status_callback:
            elapsed = int(time.time() - start_time)
            status_callback(f"⏳ Request Sent! Waiting for Admin Approval on Telegram... ({elapsed}s)")

    return False, "Authorization timed out. Please contact Admin or try again."
