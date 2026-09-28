"""
Browser Profile Manager - Centralized Reports Manager Module
Python 3.13 / PySide6 Desktop Application
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


class ReportManager:
    """Manages bot execution reports saved to Documents/Browser Profile Manager/Reports/."""

    def __init__(self) -> None:
        user_docs = os.path.expanduser("~/Documents")
        self.reports_base_dir = Path(user_docs) / "Browser Profile Manager" / "Reports"
        self.reports_base_dir.mkdir(parents=True, exist_ok=True)

    def get_bot_report_dir(self, bot_name: str) -> Path:
        clean_name = str(bot_name).strip().replace(" ", "_").replace("/", "_")
        target_dir = self.reports_base_dir / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def generate_report_filepath(self, bot_name: str, ext: str = "xlsx") -> Path:
        bot_dir = self.get_bot_report_dir(bot_name)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        clean_ext = ext.lstrip(".")
        return bot_dir / f"{bot_name.replace(' ', '_')}_Report_{timestamp}.{clean_ext}"

    def open_report_file(self, filepath: Union[str, Path]) -> bool:
        """Opens the specified report file directly using default Windows associated app (e.g. Excel / Notepad)."""
        path = Path(filepath)
        if not path.exists():
            return False
        try:
            if os.name == "nt":
                os.startfile(str(path.resolve()))
            else:
                subprocess.Popen(["xdg-open", str(path.resolve())])
            return True
        except Exception:
            return False

    def open_reports_folder(self, bot_name: Optional[str] = None) -> bool:
        """Opens Windows File Explorer directly at the reports directory."""
        if bot_name:
            target = self.get_bot_report_dir(bot_name)
        else:
            target = self.reports_base_dir

        target.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                subprocess.Popen(f'explorer "{str(target.resolve())}"')
            else:
                subprocess.Popen(["xdg-open", str(target.resolve())])
            return True
        except Exception:
            return False
