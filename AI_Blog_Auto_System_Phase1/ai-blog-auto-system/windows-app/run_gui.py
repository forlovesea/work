"""Launch the Phase 2 desktop application."""
import sys

from PySide6.QtWidgets import QApplication, QDialog

from blog_gui.storage import Store, Vault, data_directory
from blog_gui.window import MainWindow, SetupWizard


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from blog_gui.self_test import run
        return run(sys.argv[2])
    app = QApplication(sys.argv)
    app.setApplicationName("AI Blog Auto System")
    store = Store(data_directory())
    vault = Vault()
    if not store.settings().initialized:
        wizard = SetupWizard(store, vault)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return 0
    window = MainWindow(store, vault)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
