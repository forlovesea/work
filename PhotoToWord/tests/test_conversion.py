import io
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from lxml import etree
from PIL import Image, ImageDraw

from photoword.core import Element, Page, analyze, extract_text, load_image, visual_elements
from photoword.document import build_docx


class ConversionTests(unittest.TestCase):
    def test_transparency_composites_on_white(self):
        stream = io.BytesIO()
        Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(stream, "PNG")
        self.assertEqual(load_image(stream.getvalue()).getpixel((0, 0)), (255, 255, 255))

    def test_invalid_input(self):
        with self.assertRaises(Exception):
            load_image(b"not an image")

    def test_text_grouping_keeps_separate_blocks(self):
        data = dict(text=["Hello", "world", "next"], conf=[90, 80, 70],
                    left=[10, 60, 10], top=[10, 10, 40], width=[40, 40, 40], height=[20]*3,
                    block_num=[1, 1, 2], par_num=[1]*3, line_num=[1]*3)
        with patch("photoword.core.pytesseract.image_to_data", return_value=data):
            result = extract_text(Image.new("RGB", (200, 200)), "eng", 3)
        self.assertEqual([e.text for e in result], ["Hello world", "next"])
        self.assertEqual(result[0].box, (10, 10, 90, 20))

    def test_basic_shapes_and_photo(self):
        image = Image.new("RGB", (800, 1000), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((50, 50, 250, 200), outline="black", width=4)
        draw.ellipse((350, 50, 600, 210), outline="black", width=4)
        for x in range(50, 300):
            draw.line((x, 400, x, 600), fill=(x % 256, (x*3) % 256, 120))
        kinds = [e.kind for e in visual_elements(image, [])]
        self.assertIn("rect", kinds)
        self.assertIn("oval", kinds)
        self.assertIn("image", kinds)

    def test_word_objects_and_relationships(self):
        page = Page(Image.new("RGB", (800, 1000), "white"), [
            Element("text", (10, 10, 200, 30), "한글 & <Word>"),
            Element("rect", (10, 100, 100, 100)),
            Element("oval", (150, 100, 100, 100)),
            Element("image", (10, 250, 200, 200)),
        ])
        with ZipFile(io.BytesIO(build_docx([page, page]))) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "v": "urn:schemas-microsoft-com:vml"}
            self.assertEqual(root.xpath("//w:t/text()", namespaces=ns), ["한글 & <Word>"]*2)
            self.assertEqual(len(root.xpath("//v:oval", namespaces=ns)), 2)
            self.assertEqual(len(root.xpath("//v:imagedata", namespaces=ns)), 2)
            self.assertTrue(any(name.startswith("word/media/") for name in archive.namelist()))
            self.assertEqual(len(root.xpath('//w:pageBreakBefore[not(@w:val) or @w:val="1"]', namespaces=ns)), 1)

    def test_original_mode_has_no_editable_text(self):
        page = Page(Image.new("RGB", (100, 100), "white"), [Element("text", (1, 1, 50, 20), "hidden")])
        with ZipFile(io.BytesIO(build_docx([page], original=True))) as archive:
            content = archive.read("word/document.xml")
            self.assertNotIn(b"hidden", content)
            self.assertIn(b"imagedata", content)

    def test_full_frame_photo_is_preserved(self):
        image = Image.new("RGB", (200, 200))
        draw = ImageDraw.Draw(image)
        for x in range(200):
            draw.line((x, 0, x, 199), fill=(x, 80, 150))
        elements = visual_elements(image, [])
        self.assertTrue(any(e.kind == "image" and e.box == (0, 0, 200, 200) for e in elements))

    def test_blank_analysis_warns(self):
        data = io.BytesIO()
        Image.new("RGB", (100, 100), "white").save(data, "PNG")
        with patch("photoword.core.check_engine"), patch("photoword.core.extract_text", return_value=[]):
            page = analyze(data.getvalue())
        self.assertTrue(page.warnings)

    def test_empty_document_rejected(self):
        with self.assertRaises(ValueError):
            build_docx([])


if __name__ == "__main__":
    unittest.main()
