"""Generate the original battery icon at Windows Explorer icon sizes."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent
im = Image.new('RGBA', (256, 256))
d = ImageDraw.Draw(im)
d.rounded_rectangle((94, 12, 162, 44), radius=10, fill='#243e52')
d.rounded_rectangle((48, 32, 208, 244), radius=26, fill='#243e52')
d.rounded_rectangle((61, 45, 195, 231), radius=16, fill='#edf8f4')
d.rounded_rectangle((73, 72, 183, 219), radius=10, fill='#24aa74')
d.polygon([(137, 80), (94, 147), (122, 147), (112, 195), (162, 126), (133, 126)], fill='white')
im.save(root / 'battery.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
im.save(root / 'build' / 'battery-icon-preview.png')
