import os
import sys
from logging import INFO

from utils.logging_utils import configure_logging, get_logger


def configure_qt_environment():
    """Prepare the local Qt runtime so the packaged app can find its DLLs."""
    try:
        import PySide6

        pyside_dir = os.path.dirname(PySide6.__file__)
        qt_bin_dir = os.path.join(pyside_dir, "Qt", "bin")

        if hasattr(os, "add_dll_directory") and os.path.isdir(qt_bin_dir):
            os.add_dll_directory(qt_bin_dir)
    except Exception:
        pass

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")


def main():
    """Launch the desktop assistant and show the setup wizard when needed."""
    configure_logging(INFO)
    logger = get_logger(__name__)
    configure_qt_environment()

    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    from config.settings import APP_NAME
    from config.user_settings import load_model_catalog, load_user_settings, save_user_settings, user_settings_exist
    from gui.app import DesktopAssistantApp
    from gui.setup_dialog import SetupDialog
    from gui.styles import APP_STYLE

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    try:
        logger.info("Loading model catalog and persisted user settings.")
        catalog = load_model_catalog()
        settings = load_user_settings(catalog)

        if not user_settings_exist() or not settings.first_run_complete:
            logger.info("Opening first-run setup wizard.")
            dialog = SetupDialog(catalog, settings, first_run=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                logger.info("Setup wizard was canceled by the user.")
                return 0
            settings = dialog.result_settings()
            save_user_settings(settings)

        window = DesktopAssistantApp(settings, catalog)
        window.show()
        logger.info("Desktop AI Assistant window created successfully.")
        return app.exec()
    except Exception as exc:
        logger.exception("Desktop AI Assistant failed to start.")
        QMessageBox.critical(None, "Startup Error", f"Desktop AI Assistant could not start.\n\n{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
