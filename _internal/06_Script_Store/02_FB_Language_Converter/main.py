import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Setup path
curr_dir = Path(__file__).resolve().parent
app_root = curr_dir.parent.parent / "01_Main_Software"
sys.path.insert(0, str(curr_dir))
sys.path.insert(0, str(app_root))
sys.path.insert(0, str(app_root / "core"))

from fb_lang_convert_modal import FbLanguageConverterModal

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)

    # Find a sample profile for testing
    user_data_dir = ""
    sample_prof = {"name": "Profile 228", "number": "228"}
    try:
        from core.profile_manager import ProfileManager
        pm = ProfileManager()
        profs = pm.get_all_profiles()
        if profs:
            sample_prof = profs[0]
            pid = sample_prof.get("id")
            user_data_dir = str(pm.get_profile_folder(pid))
    except Exception as e:
        print(f"ProfileManager notice: {e}")

    modal = FbLanguageConverterModal(profile_data=sample_prof, user_data_dir=user_data_dir)
    modal.show()
    sys.exit(app.exec())
