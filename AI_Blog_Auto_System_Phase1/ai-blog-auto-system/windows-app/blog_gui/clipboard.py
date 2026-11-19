"""Unicode text, UTF-8 HTML and registered Windows HTML Format publication."""
import ctypes
import io
import os
import time
from ctypes import wintypes

from PIL import Image
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from .exports import cf_html
from .services import ServiceError

CF_HTML_MIME = 'application/x-qt-windows-mime;value="HTML Format"'


def mime_data(publication):
    mime = QMimeData()
    mime.setText(publication.text())
    mime.setHtml(publication.html())
    mime.setData(CF_HTML_MIME, cf_html(publication.fragment()))
    if publication.assets:
        mime.setImageData(QImage.fromData(publication.assets[0].data))
        mime.setData("image/png", publication.assets[0].data)
    return mime


def windows_api():
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.RegisterClipboardFormatW.argtypes, user.RegisterClipboardFormatW.restype = [wintypes.LPCWSTR], wintypes.UINT
    user.OpenClipboard.argtypes, user.OpenClipboard.restype = [wintypes.HWND], wintypes.BOOL
    user.EmptyClipboard.restype = user.CloseClipboard.restype = wintypes.BOOL
    user.GetDesktopWindow.restype = wintypes.HWND
    user.SetClipboardData.argtypes, user.SetClipboardData.restype = [wintypes.UINT, wintypes.HANDLE], wintypes.HANDLE
    user.GetClipboardData.argtypes, user.GetClipboardData.restype = [wintypes.UINT], wintypes.HANDLE
    kernel.GlobalAlloc.argtypes, kernel.GlobalAlloc.restype = [wintypes.UINT, ctypes.c_size_t], wintypes.HGLOBAL
    kernel.GlobalLock.argtypes, kernel.GlobalLock.restype = [wintypes.HGLOBAL], ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.argtypes, kernel.GlobalFree.restype = [wintypes.HGLOBAL], wintypes.HGLOBAL
    kernel.GlobalSize.argtypes, kernel.GlobalSize.restype = [wintypes.HGLOBAL], ctypes.c_size_t
    return user, kernel


def copy_windows(publication, owner=0):
    user, kernel = windows_api()
    formats = [(13, (publication.text() + "\0").encode("utf-16-le"))]
    for name, data in [("HTML Format", cf_html(publication.fragment())),
                       ("text/html", publication.html().encode("utf-8")),
                       ("text/plain", publication.text().encode("utf-8"))]:
        fmt = user.RegisterClipboardFormatW(name)
        if not fmt:
            raise ServiceError("Windows 클립보드 형식을 등록할 수 없습니다.")
        formats.append((fmt, data + b"\0"))
    if publication.assets:
        png = publication.assets[0].data
        formats.append((user.RegisterClipboardFormatW("PNG"), png))
        buffer = io.BytesIO()
        Image.open(io.BytesIO(png)).convert("RGB").save(buffer, "BMP")
        formats.append((8, buffer.getvalue()[14:]))  # CF_DIB omits BITMAPFILEHEADER.
    allocations = []
    opened = False
    try:
        # Allocate before replacing clipboard contents. Windows owns successful transfers.
        for fmt, data in formats:
            handle = kernel.GlobalAlloc(0x0002, len(data))
            if not handle:
                raise ServiceError("클립보드 메모리를 할당할 수 없습니다.")
            allocations.append([fmt, handle])
            pointer = kernel.GlobalLock(handle)
            if not pointer:
                raise ServiceError("클립보드 메모리를 잠글 수 없습니다.")
            ctypes.memmove(pointer, data, len(data))
            kernel.GlobalUnlock(handle)
        for _ in range(10):
            if user.OpenClipboard(owner or user.GetDesktopWindow()):
                opened = True
                break
            time.sleep(0.02)
        if not opened or not user.EmptyClipboard():
            raise ServiceError("다른 앱이 클립보드를 사용 중입니다. 다시 시도하세요.")
        for item in allocations:
            if not user.SetClipboardData(item[0], item[1]):
                raise ServiceError("클립보드 형식 저장에 실패했습니다. 다시 복사하세요.")
            item[1] = None
    finally:
        if opened:
            user.CloseClipboard()
        for _, handle in allocations:
            if handle:
                kernel.GlobalFree(handle)


def copy_publication(publication, owner=0):
    if os.name == "nt" and QApplication.platformName() != "offscreen":
        copy_windows(publication, owner)
    else:
        QApplication.clipboard().setMimeData(mime_data(publication))
