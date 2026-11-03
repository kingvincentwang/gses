"""產生主角貼圖：python tools/make_hero_textures.py <專案>
輸出 models/src/logo.png（帽徽，取自 images/hero_source.webp）與 models/src/chest.png（胸前「關西」字）。"""
import sys, pathlib
from PIL import Image, ImageDraw, ImageFont
root = pathlib.Path(sys.argv[1]).resolve()
out = root / "models" / "src"; out.mkdir(parents=True, exist_ok=True)
src = Image.open(root / "images" / "hero_source.webp").convert("RGB")
w, h = src.size
logo = src.crop((int(.51 * w), int(.045 * h), int(.635 * w), int(.15 * h))).resize((128, 128))
logo.save(out / "logo.png")
chest = Image.new("RGB", (256, 128), (109, 180, 239))
d = ImageDraw.Draw(chest)
font = ImageFont.truetype(r"C:\Windows\Fonts\msjhbd.ttc", 92)
d.text((128, 64), "關西", font=font, fill=(31, 63, 208), anchor="mm")
chest.save(out / "chest.png")
print("ok", logo.size, chest.size)
