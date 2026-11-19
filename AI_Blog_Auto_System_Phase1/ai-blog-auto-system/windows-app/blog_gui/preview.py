import base64

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import QTextBrowser


class HtmlPreview(QTextBrowser):
    """Offline rich-text preview: only generated inline PNG resources may load."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)

    def loadResource(self, resource_type, url):
        value = url.toString()
        if resource_type == QTextDocument.ResourceType.ImageResource and value.startswith("data:image/png;base64,"):
            try:
                return QImage.fromData(base64.b64decode(value.partition(",")[2], validate=True))
            except ValueError:
                return QImage()
        # Do not fetch remote URLs, stylesheets or arbitrary local files.
        return None
