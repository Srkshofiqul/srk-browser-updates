import os
import sys
from pathlib import Path

# Add project roots to path
current_dir = Path(__file__).resolve().parent
app_root = current_dir.parent.parent
core_dir = app_root / "01_Main_Software" / "core"
if str(core_dir) not in sys.path and core_dir.exists():
    sys.path.insert(0, str(core_dir))
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication
from fb_bulk_login_ui import MasterBotStudioDialog, launch_ui

def main():
    app = QApplication.instance()
    is_standalone = False
    if not app:
        app = QApplication(sys.argv)
        is_standalone = True

    # Initialize ProfileManager from main software
    profile_mgr = None
    try:
        from profile_manager import ProfileManager
        profile_mgr = ProfileManager()
    except Exception as err:
        print(f"Note on ProfileManager: {err}")
        class DummyPM:
            profiles = []
            def get_all_profiles(self): return []
            def get_groups(self): return ["Default", "Social", "Personal"]
        profile_mgr = DummyPM()

    dialog = MasterBotStudioDialog(
        profile_mgr=profile_mgr,
        bot_id="fb_bulk_login",
        bot_title="Facebook Bulk ID Login Studio"
    )
    if getattr(dialog, 'is_duplicate', False):
        if is_standalone:
            sys.exit(0)
        return dialog
    dialog.show()
    if is_standalone:
        sys.exit(app.exec())
    return dialog

if __name__ == "__main__":
    main()

