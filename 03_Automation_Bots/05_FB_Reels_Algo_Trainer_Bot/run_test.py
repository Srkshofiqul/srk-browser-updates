import os
import sys
from pathlib import Path

# Add project roots to path
current_dir = Path(__file__).resolve().parent
app_root = current_dir.parent.parent
for cand in [app_root / "_internal" / "core", app_root / "01_Main_Software" / "core", app_root / "core"]:
    if cand.exists() and str(cand) not in sys.path:
        sys.path.insert(0, str(cand))
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication
from fb_reels_algo_trainer_ui import FbReelsAlgoTrainerDialog

def main():
    app = QApplication.instance()
    is_standalone = False
    if not app:
        app = QApplication(sys.argv)
        is_standalone = True
    
    profile_mgr = None
    try:
        from profile_manager import ProfileManager
        profile_mgr = ProfileManager()
    except Exception:
        class DummyPM:
            profiles = []
            def get_all_profiles(self): return []
            def get_groups(self): return ["Default", "Social", "Personal"]
        profile_mgr = DummyPM()

    dialog = FbReelsAlgoTrainerDialog(
        profile_mgr=profile_mgr,
        parent=None
    )
    dialog.show()
    if is_standalone:
        sys.exit(app.exec())
    return dialog


if __name__ == "__main__":
    main()
