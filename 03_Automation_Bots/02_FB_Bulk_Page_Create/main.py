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
from fb_page_creator_ui import MasterBotStudioDialog

def main(profile_mgr=None, parent=None, **kwargs):
    app = QApplication.instance()
    is_standalone = False
    if not app:
        app = QApplication(sys.argv)
        is_standalone = True

    dialog = launch_ui(profile_mgr=profile_mgr, parent=parent, **kwargs)
    if is_standalone and not getattr(dialog, 'is_duplicate', False):
        sys.exit(app.exec())
    return dialog


def launch_ui(profile_mgr=None, parent=None, **kwargs):
    if profile_mgr is None:
        try:
            from profile_manager import ProfileManager
            profile_mgr = ProfileManager()
        except Exception:
            class DummyPM:
                def get_all_profiles(self): return []
                def get_groups(self): return ["Default", "Social", "Personal"]
            profile_mgr = DummyPM()

    dialog = MasterBotStudioDialog(
        profile_mgr=profile_mgr,
        bot_id="fb_bulk_page_create",
        bot_title="⚡ Facebook Bulk Page Creator Studio",
        parent=parent
    )
    dialog.show()
    return dialog

__all__ = ["MasterBotStudioDialog", "launch_ui", "main"]

if __name__ == "__main__":
    main()

