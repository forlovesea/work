"""Generate a deterministic document fixture (no personal data)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    target = Path(__file__).parent / "samples"
    target.mkdir(exist_ok=True)
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    font = ImageFont.truetype(str(font_path), 36) if font_path.exists() else ImageFont.load_default()
    draw.text((90, 80), "Photo to Word", font=font, fill="black")
    draw.text((90, 160), "사진에서 문서로 변환합니다.", font=font, fill="black")
    draw.rectangle((90, 320, 490, 540), outline="#245A81", width=5)
    draw.ellipse((660, 320, 1040, 540), outline="#A04820", width=5)
    for x in range(90, 650):
        draw.line((x, 750, x, 1050), fill=(int((x-90)/560*230), 110, 170))
    draw.text((90, 1170), "Editable text and shapes", font=font, fill="black")
    image.save(target / "sample.png")
    print(target / "sample.png")


if __name__ == "__main__":
    main()
