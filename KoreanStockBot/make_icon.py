"""Render the application's original chart icon at multiple Windows sizes."""
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    folder=Path(__file__).resolve().parent/'assets'
    folder.mkdir(exist_ok=True)
    im=Image.new('RGBA',(1024,1024))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((24,24,1000,1000),radius=220,fill='#151E32')
    for y in (340,520,700):
        d.line((170,y,860,y),fill='#293952',width=8)
    for x,top,bottom,color in [(240,540,770,'#5796FF'),(410,440,670,'#FF6571'),
                               (580,365,555,'#5796FF'),(750,230,440,'#FF6571')]:
        d.line((x,top-60,x,bottom+55),fill=color,width=18)
        d.rounded_rectangle((x-43,top,x+43,bottom),radius=12,fill=color)
    d.line([(175,820),(355,725),(535,765),(835,505)],fill='#5EE4C3',width=35,joint='curve')
    d.polygon([(854,479),(743,505),(835,586)],fill='#5EE4C3')
    im=im.resize((256,256),Image.Resampling.LANCZOS)
    im.save(folder/'stock_chart.png')
    im.save(folder/'stock_chart.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__=='__main__':main()
