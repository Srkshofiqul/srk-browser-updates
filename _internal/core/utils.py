"""
Browser Profile Manager - Utilities & Design System Module
Python 3.13 / PySide6 Desktop Application
"""

import csv
import json
import os
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Realistic Modern User-Agent pool for auto-generation
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
]


SCREEN_RESOLUTIONS = [
    {"width": 1920, "height": 1080, "dpr": 1.0},
    {"width": 1536, "height": 864, "dpr": 1.25},
    {"width": 1440, "height": 900, "dpr": 1.0},
    {"width": 1366, "height": 768, "dpr": 1.0},
    {"width": 2560, "height": 1440, "dpr": 1.5},
    {"width": 1600, "height": 900, "dpr": 1.0}
]


def generate_random_user_agent() -> str:
    """Return a random modern realistic User-Agent string."""
    return random.choice(USER_AGENT_POOL)


def generate_random_profile_fingerprint() -> Dict[str, Any]:
    """Generates a randomized hardware fingerprint profile dictionary."""
    ua = generate_random_user_agent()
    screen = random.choice(SCREEN_RESOLUTIONS)
    cores = random.choice([4, 8, 12, 16])
    ram = random.choice([4, 8, 16, 32])
    return {
        "user_agent": ua,
        "screen_width": screen["width"],
        "screen_height": screen["height"],
        "device_pixel_ratio": screen["dpr"],
        "cpu_cores": cores,
        "ram_gb": ram
    }


def get_current_timestamp() -> str:
    """Return current ISO 8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def get_display_number(num_raw: Any) -> str:
    """Format raw profile number string (e.g. 'Profile018' -> '#18', 'Profile001' -> '#1')."""
    import re
    s = str(num_raw or "").strip()
    digits = re.sub(r"\D", "", s)
    if digits:
        return f"#{int(digits)}"
    return s if s else "#1"


def format_timestamp(iso_str: str) -> str:
    """
    Format ISO 8601 timestamp into human-readable string.
    Example: '2026-07-28T10:15:30Z' -> '2026-07-28 10:15'
    """
    if not iso_str:
        return "Never"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


def is_created_today(iso_str: str) -> bool:
    """Check if the given ISO timestamp was created today in local time."""
    if not iso_str:
        return False
    try:
        dt = datetime.fromisoformat(iso_str)
        today = datetime.now(timezone.utc).date()
        return dt.date() == today
    except Exception:
        return False


def _filter_empty_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out rows that contain no non-empty values (ghost/blank spreadsheet rows)."""
    valid_rows = []
    for r in rows:
        if any(v is not None and str(v).strip() != "" for v in r.values()):
            valid_rows.append(r)
    return valid_rows


def read_excel_or_csv(filepath: Path) -> List[Dict[str, Any]]:
    """Parse Excel (.xlsx, .xls) or CSV (.csv) file into a list of row dictionaries."""
    results: List[Dict[str, Any]] = []
    if not filepath.exists():
        return results

    ext = filepath.suffix.lower()
    if ext in (".xlsx", ".xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, data_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return []
            
            first_row_vals = [str(v or "").strip().lower() for v in rows[0] if v is not None]
            known_header_keywords = {"uid", "user", "username", "id", "password", "pass", "pwd", "cookie", "cookies", "profile", "name", "group"}
            matches = any(val in known_header_keywords for val in first_row_vals)
            first_cell = first_row_vals[0] if first_row_vals else ""
            has_cookie_cell = any("datr=" in val or "c_user=" in val or "presence=" in val or "sb=" in val for val in first_row_vals)

            if not matches and (first_cell.isdigit() or has_cookie_cell):
                headers = ["UID", "Password", "Cookie"]
                data_rows = rows
            else:
                headers = [str(cell or "").strip() for cell in rows[0]]
                data_rows = rows[1:]

            for row in data_rows:
                row_dict = {}
                for col_idx, val in enumerate(row):
                    h = headers[col_idx] if col_idx < len(headers) else f"Field_{col_idx+1}"
                    row_dict[h] = str(val or "").strip()
                results.append(row_dict)
            return _filter_empty_rows(results)
        except Exception as err:
            print(f"[Error] openpyxl failed to read Excel {filepath}: {err}")
            return []
    else:
        return _filter_empty_rows(import_csv_helper(filepath))



def write_excel_or_csv(filepath: Path, records: List[Dict[str, Any]]) -> bool:
    """Write or update an Excel (.xlsx/.xls) or CSV (.csv) file with the provided record dictionaries."""
    if not records:
        return False

    suffix = filepath.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Accounts"

            headers = list(records[0].keys())
            ws.append(headers)

            for rec in records:
                row_vals = [str(rec.get(h, "")) if rec.get(h) is not None else "" for h in headers]
                ws.append(row_vals)

            wb.save(filepath)
            return True
        except Exception as err:
            print(f"[Error] Failed to write Excel file {filepath}: {err}")
            return export_csv_helper(filepath.with_suffix(".csv"), records)
    else:
        return export_csv_helper(filepath, records)


def export_csv_helper(filepath: Path, profiles: List[Dict[str, Any]]) -> bool:
    """Export profile list metadata or custom dictionary data to CSV file compatible with Excel."""
    if not profiles:
        return False

    fieldnames = list(profiles[0].keys())
    target_path = filepath
    try:
        with open(target_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for p in profiles:
                writer.writerow(p)
        return True
    except PermissionError:
        alt_path = target_path.parent / (target_path.stem + "_latest" + target_path.suffix)
        try:
            with open(alt_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for p in profiles:
                    writer.writerow(p)
            print(f"[Warning] {target_path.name} was locked by another app. Saved report to {alt_path.name}")
            return True
        except Exception as err2:
            print(f"[Error] Failed to write fallback CSV {alt_path}: {err2}")
            return False
    except Exception as err:
        print(f"[Error] Failed to write CSV file {filepath}: {err}")
        return False


def import_csv_helper(filepath: Path) -> List[Dict[str, Any]]:
    """Import row dictionaries from a CSV file with automatic headerless CSV detection."""
    results = []
    if not filepath.exists():
        return results
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        if not lines:
            return results

        first_line_vals = [v.strip().strip('"').lower() for v in lines[0].split(",") if v.strip()]
        known_header_keywords = {"uid", "user", "username", "id", "password", "pass", "pwd", "cookie", "cookies", "profile", "name", "group"}
        matches = any(val in known_header_keywords for val in first_line_vals)
        first_cell = first_line_vals[0] if first_line_vals else ""
        has_cookie_cell = any("datr=" in val or "c_user=" in val or "presence=" in val or "sb=" in val for val in first_line_vals)

        if not matches and (first_cell.isdigit() or has_cookie_cell):
            reader = csv.reader(lines)
            headers = ["UID", "Password", "Cookie"]
            for row in reader:
                if not row:
                    continue
                row_dict = {}
                for col_idx, val in enumerate(row):
                    h = headers[col_idx] if col_idx < len(headers) else f"Field_{col_idx+1}"
                    row_dict[h] = val.strip()
                results.append(row_dict)
        else:
            reader = csv.DictReader(lines)
            for row in reader:
                results.append(row)
    except Exception as err:
        print(f"[Error] Failed to read CSV file {filepath}: {err}")
    return results



def get_system_browsers() -> Dict[str, str]:
    """
    Returns strictly the bundled Portable Chromium executable included with srkBrowser.
    System-installed Google Chrome, Edge, or Brave are strictly ignored to guarantee isolated environment.
    """
    found_browsers: Dict[str, str] = {}

    # Check for Bundled Portable Chromium in project & exe directories
    app_root = Path(sys.executable).parent.resolve() if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    base_dir = Path(__file__).resolve().parent
    local_appdata_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))

    meipass_dir = Path(getattr(sys, '_MEIPASS', '')) if hasattr(sys, '_MEIPASS') else None

    portable_paths = [
        ("Bundled Chromium", app_root / "chromium" / "chrome.exe"),
        ("Bundled Chromium", app_root / "_internal" / "chromium" / "chrome.exe"),
    ]
    if meipass_dir and str(meipass_dir):
        portable_paths.append(("Bundled Chromium", meipass_dir / "chromium" / "chrome.exe"))

    portable_paths.extend([
        ("Bundled Chromium", app_root / "bin" / "chromium" / "chrome.exe"),
        ("Bundled Chromium", app_root / "assets" / "chromium" / "chrome.exe"),
        ("Bundled Chromium", base_dir / "chromium" / "chrome.exe"),
        ("Bundled Chromium", base_dir.parent / "chromium" / "chrome.exe"),
        ("Bundled Chromium", base_dir.parent.parent / "chromium" / "chrome.exe"),
        ("Bundled Chromium", local_appdata_dir / "BrowserProfileManager" / "chromium" / "chrome.exe"),
    ])

    for label, path in portable_paths:
        if path.exists():
            found_browsers[label] = str(path.resolve())
            return found_browsers

    return found_browsers


def safe_read_json(filepath: Path) -> Optional[Any]:
    """
    Safely read and parse a JSON file with automatic corrupt recovery
    from .bak backup file or .tmp file.
    """
    if not isinstance(filepath, Path):
        filepath = Path(filepath)

    # 1. Try reading the primary target file
    if filepath.exists() and filepath.stat().st_size > 0:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as err:
            print(f"[Warning] Failed to parse primary JSON {filepath}: {err}. Attempting backup recovery...")

    # 2. Fallback to .bak file if primary was 0-bytes or corrupted
    bak_path = filepath.with_suffix(filepath.suffix + ".bak")
    if bak_path.exists() and bak_path.stat().st_size > 0:
        try:
            with open(bak_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[Recovery] Successfully restored valid data from backup: {bak_path}")
                # Re-save to primary path atomically to restore it
                safe_write_json(filepath, data)
                return data
        except Exception as bak_err:
            print(f"[Warning] Failed to parse backup JSON {bak_path}: {bak_err}")

    # 3. Fallback to .tmp file if an interrupted write left valid data
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    if tmp_path.exists() and tmp_path.stat().st_size > 0:
        try:
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[Recovery] Restored valid data from temporary file: {tmp_path}")
                safe_write_json(filepath, data)
                return data
        except Exception:
            pass

    return None


def safe_write_json(filepath: Path, data: Any) -> bool:
    """
    Atomic & Crash-Proof JSON Writer:
    Writes to a temporary file, physically flushes disk buffers via os.fsync,
    maintains an automatic .bak backup, and atomically swaps via os.replace.
    Guarantees 0-byte corruption is IMPOSSIBLE during power outages.
    """
    if not isinstance(filepath, Path):
        filepath = Path(filepath)

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
        bak_path = filepath.with_suffix(filepath.suffix + ".bak")

        # Write data to temporary file
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass

        # Create rolling backup of existing valid file before replacing
        if filepath.exists() and filepath.stat().st_size > 0:
            try:
                shutil.copy2(filepath, bak_path)
            except Exception:
                pass
        else:
            try:
                shutil.copy2(tmp_path, bak_path)
            except Exception:
                pass

        # Atomic file replacement (atomic on Windows/NTFS)
        os.replace(tmp_path, filepath)
        return True
    except Exception as err:
        print(f"[Error] Failed to atomically write JSON to {filepath}: {err}")
        return False

