import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from photoword.core import analyze
from photoword.corrections import CorrectionOptions, correct_image


class CorrectionTests(unittest.TestCase):
    def test_disabled_options_preserve_pixels_and_source(self):
        image = Image.new("RGB", (120, 100), (120, 80, 40))
        before = image.tobytes()
        result = correct_image(image, CorrectionOptions(deskew=False))
        self.assertEqual(result.tobytes(), before)
        self.assertEqual(image.tobytes(), before)
        self.assertIsNot(result, image)

    def test_shadow_normalizes_background_without_erasing_dark_text(self):
        pixels = np.tile(np.linspace(100, 220, 300).astype(np.uint8), (200, 1))
        image = Image.fromarray(pixels).convert("RGB")
        ImageDraw.Draw(image).rectangle((80, 80, 160, 84), fill="black")
        result = correct_image(image, CorrectionOptions(deskew=False, shadow=True))
        self.assertLess(np.std(np.array(result)[20, :, 0]), np.std(pixels[20]))
        self.assertEqual(result.getpixel((100, 82)), (0, 0, 0))

    def test_binary_produces_black_and_white(self):
        image = Image.new("RGB", (100, 100), "gray")
        ImageDraw.Draw(image).text((10, 10), "Text 123", fill="black")
        result = correct_image(image, CorrectionOptions(deskew=False, binary=True))
        self.assertEqual(set(np.unique(np.array(result))), {0, 255})

    def test_deskew_levels_tilted_lines(self):
        image = Image.new("RGB", (600, 400), "white")
        draw = ImageDraw.Draw(image)
        for y in range(80, 330, 40):
            draw.line((80, y, 520, y), fill="black", width=3)
        tilted = image.rotate(4, expand=True, fillcolor="white")
        result = correct_image(tilted, CorrectionOptions())
        # Level lines concentrate dark pixels into fewer rows.
        before = np.max(np.sum(np.array(tilted)[:, :, 0] < 80, axis=1))
        after = np.max(np.sum(np.array(result)[:, :, 0] < 80, axis=1))
        self.assertGreater(after, before * 3)

    def test_analysis_uses_selected_pixels_without_resizing(self):
        selected = Image.new("RGB", (2500, 40), (80, 100, 120))
        with patch("photoword.core.check_engine"), patch("photoword.core.extract_text", return_value=[]) as ocr:
            page = analyze(b"unused original bytes", prepared_image=selected)
        self.assertEqual(ocr.call_args.args[0].tobytes(), selected.tobytes())
        self.assertEqual(page.image.size, selected.size)
