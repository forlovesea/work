# Third-party components

PhotoToWord uses Python, Tcl/Tk, Pillow, NumPy, OpenCV, pytesseract, python-docx,
lxml, openpyxl, python-pptx, and PyInstaller. Their licenses apply to their
respective components. Installed package license files are included under
`licenses` in the release package.

The portable Windows release includes Tesseract OCR and its runtime DLLs from
the official Windows distribution. Upstream notices are retained in
`tools/Tesseract-OCR/doc`. Tesseract and the official language models are
distributed under Apache License 2.0. The runtime DLLs retain their respective
upstream licenses; Tesseract's license does not replace their licenses.

- Tesseract source and Windows release: https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3
- Windows build and dependency sources: https://github.com/UB-Mannheim/tesseract
- MSYS2 package sources for Windows dependencies: https://github.com/msys2/MINGW-packages
- Korean/English model sources: https://github.com/tesseract-ocr/tessdata_best
- Tcl/Tk: https://www.tcl.tk/software/tcltk/license.html
- Python: https://docs.python.org/3/license.html

No system fonts are redistributed. The application uses fonts installed on the user's computer.
