# -*- coding: utf-8 -*-
"""
srkBrowser FB 1-Click Auto Re-login (FBRL) Standalone Entry Point
"""
import os
import sys
from pathlib import Path

curr_dir = Path(__file__).resolve().parent
app_root = curr_dir.parent.parent / "01_Main_Software"
if str(curr_dir) not in sys.path:
    sys.path.insert(0, str(curr_dir))
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))
if str(app_root / "core") not in sys.path:
    sys.path.insert(0, str(app_root / "core"))

from fb_relogin_engine import execute_relogin, launch_ui, main

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication(sys.argv)

    sample_prof = {}
    try:
        from core.profile_manager import ProfileManager
        pm = ProfileManager()
        profs = pm.get_all_profiles()
        if profs:
            sample_prof = profs[0]
    except Exception as e:
        print(f"ProfileManager notice: {e}")

    if sample_prof:
        ok, msg = execute_relogin(sample_prof)
        if ok:
            QMessageBox.information(None, "FBRL Success", msg)
        else:
            QMessageBox.warning(None, "FBRL Notice", msg)
    else:
        print("No profiles available for test run.")
