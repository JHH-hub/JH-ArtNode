"""生成插件所需图标（PNG），无需设计软件。"""
from PIL import Image, ImageDraw
import os

sizes = [16, 48, 128]
out_dir = os.path.join(os.path.dirname(__file__), "icons")
os.makedirs(out_dir, exist_ok=True)

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 圆形背景
    d.ellipse([0, 0, size-1, size-1], fill=(124, 110, 245, 255))
    # 中心调色盘符号（简单几何）
    r = size * 0.28
    cx = cy = size / 2
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(255,255,255,200))
    d.ellipse([cx-r*0.4, cy-r*0.4, cx+r*0.4, cy+r*0.4], fill=(124,110,245,255))
    img.save(os.path.join(out_dir, f"icon{size}.png"))
    print(f"  icon{size}.png created")

print("图标生成完成")
