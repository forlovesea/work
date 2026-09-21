"""Optional, non-destructive preparation of document images for OCR."""
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps


@dataclass(frozen=True)
class CorrectionOptions:
    deskew: bool = True
    shadow: bool = False
    contrast: float = 1.0
    grayscale: bool = False
    binary: bool = False


def correct_image(source: Image.Image, options: CorrectionOptions) -> Image.Image:
    image = source.convert("RGB")
    if options.shadow:
        rgb = np.array(image)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        size = max(15, min(101, (min(gray.shape) // 20) | 1))
        background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
        background = cv2.GaussianBlur(background, (0, 0), max(1, size / 6))
        gain = 255.0 / np.maximum(background.astype(np.float32), 1)
        image = Image.fromarray(np.clip(rgb.astype(np.float32) * gain[:, :, None], 0, 255).astype(np.uint8))
    if options.grayscale or options.binary:
        image = ImageOps.grayscale(image).convert("RGB")
    image = ImageEnhance.Contrast(image).enhance(options.contrast)
    if options.deskew:
        sample = ImageOps.grayscale(image)
        sample.thumbnail((1200, 1200))
        gray = np.array(sample)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, threshold=40,
                                minLineLength=max(30, sample.width // 10), maxLineGap=15)
        angles = []
        if lines is not None:
            for x1, y1, x2, y2 in lines[:, 0]:
                angle = np.degrees(np.arctan2(float(y2-y1), float(x2-x1)))
                if abs(angle) <= 10:
                    angles.append(angle)
        if len(angles) >= 3:
            angle = float(np.median(angles))
            if abs(angle) >= 0.2:
                image = image.rotate(angle, resample=Image.Resampling.BICUBIC,
                                     expand=True, fillcolor="white")
    if options.binary:
        gray = np.array(ImageOps.grayscale(image))
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 11)
        image = Image.fromarray(gray).convert("RGB")
    return image
