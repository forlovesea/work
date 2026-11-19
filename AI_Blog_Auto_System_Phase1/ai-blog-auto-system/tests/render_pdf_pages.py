"""Optional QA helper: render a Word-exported PDF onto white PNG pages."""
import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    app = QApplication([])
    document = QPdfDocument()
    if document.load(str(args.pdf)) != QPdfDocument.Error.None_:
        raise SystemExit("PDF load failed")
    args.output.mkdir(parents=True, exist_ok=True)
    for index in range(document.pageCount()):
        size = document.pagePointSize(index)
        raster = document.render(index, QSize(1240, round(1240 * size.height() / size.width())))
        canvas = QImage(raster.size(), QImage.Format.Format_RGB32)
        canvas.fill(Qt.GlobalColor.white)
        painter = QPainter(canvas)
        painter.drawImage(0, 0, raster)
        painter.end()
        if not canvas.save(str(args.output / f"page-{index+1}.png")):
            raise SystemExit("PNG save failed")
    print(f"Rendered {document.pageCount()} pages")


if __name__ == "__main__":
    main()
