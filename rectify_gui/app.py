"""Point d'entrée de l'application Rectify Perspective."""

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from rectify_gui.ui_main import MainWindow

# Configurer les logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Lance l'application GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("Rectify Perspective")
    app.setOrganizationName("Rectify")
    app.setApplicationVersion("1.0.0")

    # Style par défaut
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Dossiers par défaut
    project_root = Path(__file__).resolve().parent.parent
    input_dir = project_root / "input"
    output_dir = project_root / "output"
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    window = MainWindow(input_dir=input_dir, output_dir=output_dir)
    window.setWindowTitle("Rectify Perspective - Correction de documents scannés")
    window.resize(1400, 900)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
