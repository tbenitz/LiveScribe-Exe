from PIL import Image, ImageDraw
from pathlib import Path
im=Image.new("RGBA",(256,256))
d=ImageDraw.Draw(im)
d.rounded_rectangle((0,0,255,255),radius=55,fill="#047a65")
for x,h in [(56,54),(92,98),(128,152),(164,98),(200,54)]:
    d.rounded_rectangle((x-9,128-h//2,x+9,128+h//2),radius=9,fill="white")
Path("build").mkdir(exist_ok=True)
im.save("build/livescribe.ico",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(256,256)])
