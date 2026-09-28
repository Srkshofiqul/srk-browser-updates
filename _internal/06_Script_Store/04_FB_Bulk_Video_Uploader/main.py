import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

curr_dir = Path(__file__).resolve().parent
if str(curr_dir) not in sys.path:
    sys.path.insert(0, str(curr_dir))

from fb_bulk_video_uploader_modal import FbBulkVideoUploaderModal, launch_ui, main

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    modal = FbBulkVideoUploaderModal(profile_data={"number": "540", "name": "Profile 540"})
    modal.show()
    sys.exit(app.exec())
