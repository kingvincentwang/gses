"""依 build/timeline.json 逐格繪製動畫，並與 build/audio.wav 合成 三人成虎.mp4。

用法：python3 render.py [--preview 秒數,秒數,...]
"""
import json
import math
import subprocess
import sys
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from story import BEATS as STORY_BEATS, FPS, NAMES
from tiger import draw_tiger

W, H = 1280, 720
FONT = '../Iansui-Regular.ttf'
rng = np.random.default_rng(11)

TL = json.load(open('build/timeline.json', encoding='utf-8'))
BEATS = TL['beats']
TOTAL = TL['total']


def font(size):
    return _font(int(size))


@lru_cache(None)
def _font(size):
    return ImageFont.truetype(FONT, size)


def ease(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- 角色與嘴形
class Face:
    """角色立繪 + 嘴形。mode='draw' 畫出嘴巴；mode='scale' 以原圖張開的嘴依音量縮放。"""

    def __init__(self, name, mouth, size, mode, lip=(150, 75, 65)):
        self.img = Image.open(f'sprites/{name}.png').convert('RGBA')
        self.cx, self.cy = mouth
        self.mw, self.mh = size
        self.mode = mode
        self.lip = lip
        if mode == 'scale':
            arr = np.asarray(self.img).copy()
            x0, y0 = int(self.cx - self.mw / 2), int(self.cy - self.mh / 2)
            x1, y1 = int(self.cx + self.mw / 2), int(self.cy + self.mh / 2)
            m = Image.new('L', self.img.size, 0)
            ImageDraw.Draw(m).ellipse([x0 - 5, y0 - 5, x1 + 5, y1 + 5], fill=255)
            self.mouth_crop = self.img.crop((x0 - 3, y0 - 3, x1 + 3, y1 + 3))
            mm = Image.new('L', self.mouth_crop.size, 0)
            ImageDraw.Draw(mm).ellipse([1, 1, mm.width - 2, mm.height - 2], fill=255)
            self.mouth_mask = mm.filter(ImageFilter.GaussianBlur(1.2))
            rgb = cv2.inpaint(np.ascontiguousarray(arr[..., :3]), np.asarray(m), 9, cv2.INPAINT_TELEA)
            rgb = cv2.GaussianBlur(rgb, (0, 0), 1.0) * (np.asarray(m)[..., None] > 0) + rgb * (np.asarray(m)[..., None] == 0)
            arr[..., :3] = rgb.astype(np.uint8)
            self.closed = Image.fromarray(arr, 'RGBA')

    def render(self, o):
        """o: 張嘴程度 0..1。回傳修改後的立繪（原尺寸）。"""
        if self.mode == 'none':
            return self.img
        if self.mode == 'scale':
            im = self.closed.copy()
            if o < 0.08:
                self._closed_line(im)
                return im
            sw = max(4, int(self.mouth_crop.width * (0.55 + 0.45 * o)))
            sh = max(3, int(self.mouth_crop.height * (0.18 + 0.82 * o)))
            mc = self.mouth_crop.resize((sw, sh), Image.LANCZOS)
            mk = ImageChops.multiply(self.mouth_mask.resize((sw, sh)), mc.split()[3])
            top = int(self.cy - self.mouth_crop.height / 2)
            im.paste(mc, (int(self.cx - sw / 2), top + int((self.mouth_crop.height - sh) * 0.3)), mk)
            return im
        im = self.img.copy()
        k = 6
        pw, ph = int(self.mw * 1.6), int(self.mh * 1.6 + 6)
        patch = Image.new('RGBA', (pw * k, ph * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(patch)
        mx = pw * k / 2
        top = 3 * k
        if o < 0.08:
            d.line([(mx - self.mw * 0.45 * k, top + 1.5 * k), (mx, top + 2.2 * k), (mx + self.mw * 0.45 * k, top + 1.5 * k)],
                   fill=self.lip + (255,), width=int(1.6 * k), joint='curve')
        else:
            w = self.mw * (0.75 + 0.25 * o) * k
            h = max(2.5, self.mh * o) * k
            d.ellipse([mx - w / 2, top, mx + w / 2, top + h], fill=(70, 22, 22, 255), outline=self.lip + (255,), width=int(1.2 * k))
            d.ellipse([mx - w * 0.3, top + h * 0.55, mx + w * 0.3, top + h * 1.0], fill=(175, 70, 70, 255))
            d.chord([mx - w * 0.38, top + 0.6 * k, mx + w * 0.38, top + h * 0.5], 180, 360, fill=(250, 245, 235, 255))
        patch = patch.resize((pw, ph), Image.LANCZOS)
        im.alpha_composite(patch, (int(self.cx - pw / 2), int(self.cy - 3)))
        return im

    def _closed_line(self, im):
        k = 6
        pw, ph = int(self.mw * 1.2), 10
        patch = Image.new('RGBA', (pw * k, ph * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(patch)
        d.line([(pw * k * 0.2, 4 * k), (pw * k * 0.5, 5.5 * k), (pw * k * 0.8, 4 * k)], fill=self.lip + (255,), width=int(2 * k), joint='curve')
        patch = patch.resize((pw, ph), Image.LANCZOS)
        im.alpha_composite(patch, (int(self.cx - pw / 2), int(self.cy - 5)))


FACES = {
    'P': Face('pang_big', (184, 178), (16, 14), 'draw', (110, 55, 50)),
    'K': Face('king_throne', (245, 135), (18, 15), 'draw', (130, 60, 55)),
    'A': Face('a_big', (113, 112), (33, 37), 'scale'),
    'B': Face('b_big', (104, 111), (36, 27), 'scale'),
    'C': Face('c_big', (128, 113), (41, 29), 'scale'),
}
SMALL = {k: Image.open(f'sprites/{k}.png').convert('RGBA') for k in
         ('pang_s', 'king_s', 'a_s', 'b_s', 'c_s', 'shadowL', 'shadowR')}


def mouth_open(who, t):
    """依時間查詢說話者的嘴巴張合值。"""
    for b in BEATS:
        if b['who'] == who and b['start'] <= t < b['end']:
            i = int((t - b['start']) * FPS)
            return b['env'][i] if i < len(b['env']) else 0.0
    return 0.0


def ink_style(im):
    """將立繪轉成帶褐色調的水墨灰階。"""
    a = im.split()[3]
    g = ImageOps.grayscale(im)
    g = ImageEnhance.Contrast(g).enhance(1.25)
    rgb = Image.merge('RGB', [g.point(lambda v: v * 1.0), g.point(lambda v: v * 0.96), g.point(lambda v: v * 0.86)])
    out = rgb.convert('RGBA')
    out.putalpha(a)
    return out


@lru_cache(64)
def silhouette(name, color=(12, 10, 14)):
    im = SMALL[name]
    s = Image.new('RGBA', im.size, color + (255,))
    s.putalpha(im.split()[3])
    return s


# ---------------------------------------------------------------- 背景
def noise_img(w, h, div, seed=0):
    r = np.random.default_rng(seed)
    n = (r.random((h // div + 2, w // div + 2)) * 255).astype(np.uint8)
    return np.asarray(Image.fromarray(n).resize((w, h), Image.BICUBIC), np.float32) / 255


def palace_bg(door=False):
    S = 2
    w, h = W * S, H * S
    yy = np.linspace(0, 1, h)[:, None]
    wall = np.stack([70 + 60 * yy, 22 + 28 * yy, 16 + 14 * yy], -1) * np.ones((1, w, 1))
    img = Image.fromarray(wall.astype(np.uint8)).convert('RGBA')
    d = ImageDraw.Draw(img)
    fy = int(h * 0.74)
    cx = w // 2
    if door:  # 遠方明亮的殿門
        glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.rectangle([cx - 150, fy - 520, cx + 150, fy], fill=(255, 236, 190, 255))
        glow2 = glow.filter(ImageFilter.GaussianBlur(60))
        img.alpha_composite(glow2)
        img.alpha_composite(glow)
        d.rectangle([cx - 170, fy - 545, cx + 170, fy - 520], fill=(120, 30, 25))
    else:  # 王座後方的金色屏風
        d.rectangle([cx - 520, fy - 760, cx + 520, fy - 40], fill=(150, 105, 40))
        d.rectangle([cx - 500, fy - 740, cx + 500, fy - 60], fill=(185, 135, 55))
        for i in range(-9, 10):
            x = cx + i * 52
            d.line([(x, fy - 740), (x, fy - 60)], fill=(150, 100, 35), width=6)
        for j in range(14):
            y = fy - 740 + j * 50
            d.line([(cx - 500, y), (cx + 500, y)], fill=(150, 100, 35), width=6)
        d.ellipse([cx - 180, fy - 640, cx + 180, fy - 280], outline=(230, 190, 90), width=14)
    # 紅柱
    for xr in (0.07, 0.25, 0.75, 0.93):
        x = int(w * xr)
        pw = 110 if xr in (0.07, 0.93) else 80
        col = np.linspace(0, 1, pw)
        shade = 0.55 + 0.45 * np.sin(col * math.pi)
        pillar = np.stack([175 * shade, 32 * shade, 26 * shade], -1)[None].repeat(fy, 0)
        img.paste(Image.fromarray(pillar.astype(np.uint8)), (x - pw // 2, 0))
        for y0 in (90, fy - 90):
            d.rectangle([x - pw // 2 - 8, y0, x + pw // 2 + 8, y0 + 40], fill=(210, 160, 60))
            d.rectangle([x - pw // 2 - 8, y0 + 12, x + pw // 2 + 8, y0 + 18], fill=(140, 90, 30))
    # 上方的垂幔與宮燈
    for i in range(0, w, 120):
        d.chord([i - 10, -70, i + 130, 70], 0, 180, fill=(190, 140, 40))
        d.chord([i, -60, i + 120, 50], 0, 180, fill=(160, 30, 28))
    for xr in (0.16, 0.84):
        x = int(w * xr)
        d.line([(x, 0), (x, 160)], fill=(60, 30, 10), width=4)
        lg = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(lg).ellipse([x - 90, 120, x + 90, 330], fill=(255, 170, 70, 120))
        img.alpha_composite(lg.filter(ImageFilter.GaussianBlur(40)))
        d.ellipse([x - 50, 160, x + 50, 300], fill=(220, 50, 35))
        d.rectangle([x - 30, 150, x + 30, 165], fill=(210, 160, 60))
        d.rectangle([x - 30, 295, x + 30, 310], fill=(210, 160, 60))
    # 地板（透視格線）
    fl = np.linspace(0, 1, h - fy)[:, None]
    floor = np.stack([95 + 70 * fl, 60 + 45 * fl, 30 + 20 * fl], -1) * np.ones((1, w, 1))
    img.paste(Image.fromarray(floor.astype(np.uint8)), (0, fy))
    for i in range(-14, 15):
        d.line([(cx + i * 40, fy), (cx + i * 260, h)], fill=(80, 50, 25), width=3)
    for j in range(7):
        y = fy + (h - fy) * (j / 7) ** 1.6
        d.line([(0, y), (w, y)], fill=(80, 50, 25), width=3)
    if not door:  # 王座台階
        for k in range(3):
            d.rectangle([cx - 430 + k * 40, fy - 30 + k * 26, cx + 430 - k * 40, fy - 6 + k * 26], fill=(120 - k * 10, 30, 25))
            d.rectangle([cx - 430 + k * 40, fy - 30 + k * 26, cx + 430 - k * 40, fy - 24 + k * 26], fill=(215, 165, 70))
    # 暗角
    vy, vx = np.mgrid[0:h, 0:w]
    v = 1 - 0.55 * np.clip(np.hypot((vx - w / 2) / (w * 0.6), (vy - h / 2) / (h * 0.7)) - 0.35, 0, 1)
    arr = np.asarray(img.convert('RGB'), np.float32) * v[..., None]
    return Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.5))


def market_bg():
    S = 2
    w, h = W * S, H * S
    paper = np.array([236, 229, 212], np.float32)
    grain = noise_img(w, h, 3, 1) * 0.5 + noise_img(w, h, 40, 2) * 0.5
    arr = paper * (0.93 + 0.1 * grain[..., None])
    img = Image.fromarray(arr.astype(np.uint8)).convert('RGBA')

    def wash(poly, tone, blur, alpha=255):
        lay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(lay).polygon(poly, fill=(tone, tone, int(tone * 0.95), alpha))
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur)))

    # 遠山
    for k, (base, amp, tone) in enumerate([(560, 200, 190), (650, 160, 160)]):
        xs = np.linspace(0, w, 40)
        r = np.random.default_rng(k + 5)
        ys = base - amp * np.abs(np.sin(xs / w * math.pi * (2 + k) + r.random())) - r.random(40) * 40
        wash([(0, h)] + list(zip(xs, ys)) + [(w, h)], tone, 18, 200)
    # 街道兩旁的房舍
    gy = int(h * 0.72)
    r = np.random.default_rng(9)
    x = -60
    while x < w:
        bw = int(r.integers(260, 380))
        top = gy - int(r.integers(330, 430))
        tone = int(r.integers(95, 130))
        wash([(x, gy), (x, top), (x + bw, top), (x + bw, gy)], tone + 60, 2)
        # 飛簷屋頂
        roof = [(x - 50, top + 10)] + [(x - 50 + (bw + 100) * t, top - 70 + 60 * (2 * t - 1) ** 2 - 10) for t in np.linspace(0, 1, 16)] + [(x + bw + 50, top + 10)]
        wash(roof, tone - 50, 2)
        # 門窗
        wash([(x + bw * 0.3, gy), (x + bw * 0.3, gy - 170), (x + bw * 0.7, gy - 170), (x + bw * 0.7, gy)], tone - 20, 3)
        # 招牌旗幟
        if r.random() < 0.7:
            fx = x + bw * 0.12
            wash([(fx, top + 40), (fx + 60, top + 40), (fx + 60, top + 230), (fx + 30, top + 250), (fx, top + 230)], 225, 1)
            ImageDraw.Draw(img).text((fx + 30, top + 140), str(r.choice(list('茶酒布肉麵藥米燈'))), font=font(48), fill=(60, 55, 50), anchor='mm')
        x += bw + int(r.integers(20, 60))
    # 攤販棚子
    d = ImageDraw.Draw(img)
    for sx in (260, 1150, 2050):
        d.polygon([(sx - 170, gy - 230), (sx + 170, gy - 230), (sx + 210, gy - 150), (sx - 210, gy - 150)], fill=(150, 145, 135))
        for k in range(-4, 5, 2):
            d.polygon([(sx + k * 42 - 21, gy - 230), (sx + k * 42 + 21, gy - 230), (sx + k * 50 + 25, gy - 150), (sx + k * 50 - 25, gy - 150)], fill=(205, 200, 190))
        d.rectangle([sx - 190, gy - 150, sx - 178, gy + 20], fill=(80, 75, 70))
        d.rectangle([sx + 178, gy - 150, sx + 190, gy + 20], fill=(80, 75, 70))
        d.rectangle([sx - 200, gy - 40, sx + 200, gy + 10], fill=(120, 110, 100))
    # 地面墨痕
    wash([(0, gy), (w, gy), (w, h), (0, h)], 200, 6, 160)
    for _ in range(40):
        y = r.uniform(gy + 20, h)
        x0 = r.uniform(-200, w)
        d.line([(x0, y), (x0 + r.uniform(100, 500), y + r.uniform(-6, 6))], fill=(150, 145, 135), width=int(r.integers(2, 6)))
    return img.convert('RGB').filter(ImageFilter.GaussianBlur(1.6))


BG = {}


def bg(name):
    if name not in BG:
        BG[name] = {'palace': lambda: palace_bg(False), 'door': lambda: palace_bg(True), 'market': market_bg}[name]()
        if name == 'palace':
            BG['palace_blur'] = BG[name].filter(ImageFilter.GaussianBlur(14))
    return BG[name]


# ---------------------------------------------------------------- 畫面合成
class Frame:
    """以「世界座標」(1280x720) 疊圖，鏡頭 (zoom, cx, cy) 決定最後取景。"""

    def __init__(self, bgname, zoom=1.0, cx=W / 2, cy=H / 2, shake=0.0, t=0.0):
        zoom = max(1.0, zoom)
        if shake:
            cx += shake * math.sin(t * 53) * 6
            cy += shake * math.cos(t * 47) * 5
        vw, vh = W / zoom, H / zoom
        self.zoom = zoom
        self.cx = min(max(cx, vw / 2), W - vw / 2)
        self.cy = min(max(cy, vh / 2), H - vh / 2)
        src = bg(bgname) if bgname else None
        if src is None:
            self.img = Image.new('RGBA', (W, H), (0, 0, 0, 255))
        else:
            sx = src.width / W
            vw, vh = W / zoom, H / zoom
            box = ((self.cx - vw / 2) * sx, (self.cy - vh / 2) * sx, (self.cx + vw / 2) * sx, (self.cy + vh / 2) * sx)
            self.img = src.resize((W, H), Image.BILINEAR, box=box).convert('RGBA')

    def to_screen(self, x, y):
        return (x - self.cx) * self.zoom + W / 2, (y - self.cy) * self.zoom + H / 2

    def put(self, sprite, x, y, scale, anchor=(0.5, 1.0), alpha=1.0, rot=0.0, flip=False):
        """把立繪放在世界座標 (x, y)，anchor 為立繪上的對齊點比例。"""
        s = scale * self.zoom
        im = sprite
        if flip:
            im = ImageOps.mirror(im)
        nw, nh = max(1, int(im.width * s)), max(1, int(im.height * s))
        im = im.resize((nw, nh), Image.LANCZOS if s < 1 else Image.BICUBIC)
        ax, ay = anchor[0] * nw, anchor[1] * nh
        if rot:
            big = Image.new('RGBA', (nw * 2, nh * 2), (0, 0, 0, 0))
            big.paste(im, (int(nw - ax), int(nh - ay)))
            im = big.rotate(rot, Image.BICUBIC, center=(nw, nh))
            ax, ay = nw, nh
        if alpha < 1:
            a = im.split()[3].point(lambda v: int(v * alpha))
            im.putalpha(a)
        sx, sy = self.to_screen(x, y)
        self.img.alpha_composite(im, (int(sx - ax), int(sy - ay))) if 0 <= int(sx - ax) and 0 <= int(sy - ay) else self._paste_clip(im, int(sx - ax), int(sy - ay))

    def _paste_clip(self, im, x, y):
        l, t = max(0, -x), max(0, -y)
        if l >= im.width or t >= im.height:
            return
        im = im.crop((l, t, im.width, im.height))
        if x + l < W and y + t < H:
            self.img.alpha_composite(im.crop((0, 0, min(im.width, W - x - l), min(im.height, H - y - t))), (x + l, y + t))

    def overlay(self, rgba):
        self.img.alpha_composite(rgba)

    def darken(self, amount, color=(0, 0, 0)):
        if amount > 0:
            self.img.alpha_composite(Image.new('RGBA', (W, H), color + (int(255 * min(1, amount)),)))


def vignette(strength):
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip(np.hypot((xx - W / 2) / (W * 0.55), (yy - H / 2) / (H * 0.6)) - 0.3, 0, 1) ** 1.3
    a = np.clip(v * strength * 255, 0, 255).astype(np.uint8)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.putalpha(Image.fromarray(a))
    return out


VIG = {}


def vig(s):
    k = round(s, 2)
    if k not in VIG:
        VIG[k] = vignette(k)
    return VIG[k]


# ---------------------------------------------------------------- 字幕與文字
def subtitle(fr, t):
    for b in BEATS:
        if not b['who'] or b['shot'] in ('s8', 's8m'):
            continue
        if b['start'] - 0.1 <= t < b['end'] + 0.3:
            a = min(1, (t - b['start'] + 0.1) / 0.15, (b['end'] + 0.3 - t) / 0.15)
            draw_sub(fr, NAMES[b['who']], b['text'], a)
            return


def wrap(text, n):
    lines, cur = [], ''
    for ch in text:
        cur += ch
        if len(cur) >= n and ch in '，；。！？、':
            lines.append(cur)
            cur = ''
    if cur:
        lines.append(cur)
    out = []  # 合併過短的行
    for ln in lines:
        if out and len(out[-1]) + len(ln) <= n + 4:
            out[-1] += ln
        else:
            out.append(ln)
    return out


def draw_sub(fr, name, text, a):
    lines = wrap(text, 20)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    f = font(38)
    lh = 50
    y0 = H - 40 - lh * len(lines)
    d.rounded_rectangle([140, y0 - 16, W - 140, H - 26], 18, fill=(10, 8, 6, 150))
    is_name = name != '旁白'
    for i, ln in enumerate(lines):
        txt = (f'{name}：' if is_name and i == 0 else ('　' * (len(name) + 1) if is_name else '')) + ln
        x = W / 2
        d.text((x, y0 + i * lh + lh / 2 - 4), txt, font=f, fill=(255, 248, 225), anchor='mm', stroke_width=2, stroke_fill=(20, 10, 5))
    if is_name:  # 名字上色
        first = f'{name}：' + lines[0]
        tw = d.textlength(first, font=f)
        d.text((W / 2 - tw / 2, y0 + lh / 2 - 4), f'{name}：', font=f, fill=(255, 200, 90), anchor='lm', stroke_width=2, stroke_fill=(20, 10, 5))
    if a < 1:
        lay.putalpha(lay.split()[3].point(lambda v: int(v * a)))
    fr.overlay(lay)


@lru_cache(8)
def title_layer():
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    # 紅色直式題籤（呼應人物設定圖）
    x0, y0 = W / 2 - 300, 70
    d.text((W / 2 + 30, 150), '三 人 成 虎', font=font(120), fill=(25, 15, 10, 255), anchor='mm', stroke_width=3, stroke_fill=(250, 235, 200, 255))
    d.rounded_rectangle([x0 - 80, y0, x0 - 10, y0 + 160], 8, fill=(170, 25, 25, 255))
    for i, ch in enumerate('寓言'):
        d.text((x0 - 45, y0 + 45 + i * 70), ch, font=font(52), fill=(255, 240, 220, 255), anchor='mm')
    return lay


def title_dissolve(fr, lt, start=2.4, dur=1.4):
    lay = title_layer()
    if lt < start:
        a = min(1, lt / 0.8)
        im = lay.copy()
        im.putalpha(im.split()[3].point(lambda v: int(v * a)))
        fr.overlay(im)
        return
    p = (lt - start) / dur
    if p >= 1:
        return
    im = lay.copy()
    im.putalpha(im.split()[3].point(lambda v: int(v * max(0, 1 - p * 1.6))))
    fr.overlay(im.filter(ImageFilter.GaussianBlur(p * 6)))
    pts = title_particles()
    d = ImageDraw.Draw(fr.img)
    for (x, y, vx, vy, s) in pts:
        px, py = x + vx * p * 200, y + vy * p * 200 - p * p * 60
        r = s * (1 - p)
        if r > 0.3:
            d.ellipse([px - r, py - r, px + r, py + r], fill=(20, 15, 10, int(220 * (1 - p))))


@lru_cache(1)
def title_particles():
    a = np.asarray(title_layer().split()[3])
    ys, xs = np.where(a > 200)
    idx = rng.choice(len(xs), 1600, replace=False)
    return [(xs[i], ys[i], rng.normal(0.4, 0.6), rng.normal(-0.3, 0.5), rng.uniform(1.5, 4)) for i in idx]


# ---------------------------------------------------------------- 各鏡頭
def shots():
    """回傳 [(鏡頭代號, 開始, 結束)]：每個鏡頭從它第一句的前置停頓開始，到下一鏡頭開始為止。"""
    starts = []
    for b, (shot, _, _, pre, _) in zip(BEATS, STORY_BEATS):
        if not starts or starts[-1][0] != shot:
            starts.append((shot, 0.0 if not starts else b['start'] - pre))
    return [(s, a, starts[i + 1][1] if i + 1 < len(starts) else TOTAL) for i, (s, a) in enumerate(starts)]


SHOTS = shots()
SHOT_T = {s: (a, e) for s, a, e in SHOTS}


def beat_t(shot, who=None, n=0):
    bs = [b for b in BEATS if b['shot'] == shot and (who is None or b['who'] == who)]
    return bs[n]['start'], bs[n]['end']


def face(who, t):
    return FACES[who].render(mouth_open(who, t))


def ghost_king(fr, t, x, motion):
    im = ink_style(SMALL['king_s'])
    rot = 0
    dy = 0
    if motion == 'shake':
        rot = 5 * math.sin(t * 9)
    elif motion == 'stroke':
        dy = 3 * math.sin(t * 4)
        rot = 2 * math.sin(t * 2)
    elif motion == 'nod':
        dy = 6 * abs(math.sin(t * 5))
    fr.put(im, x, 650 + dy, 1.05, alpha=0.42, rot=rot)


def shot_s1(t, lt, a, e):
    z = lerp(1.0, 1.22, ease(lt / (e - a)))
    fr = Frame('palace', z, 640, lerp(360, 380, ease(lt / (e - a))))
    fr.put(face('K', t), 640, 560, 0.62)
    fr.put(SMALL['pang_s'], 330, 650, 0.95)
    title_dissolve(fr, lt)
    fr.overlay(vig(0.7))
    if lt < 0.8:
        fr.darken(1 - lt / 0.8)
    return fr


def shot_s2p(t, lt, a, e):
    # 過肩鏡頭：前景魏王的肩膀（虛化）、聚焦龐蔥
    z = lerp(1.0, 1.06, lt / (e - a))
    fr = Frame('palace_blur', z, 640, 360)
    bow = 2.5 * math.sin(min(1, lt / 1.2) * math.pi / 2)
    fr.put(face('P', t), 520, 780, 1.45, rot=bow)
    fr.overlay(shoulder_layer())
    fr.overlay(vig(0.6))
    return fr


@lru_cache(1)
def shoulder_layer():
    k = FACES['K'].img.crop((250, 160, 460, 480))
    k = k.resize((int(k.width * 2.6), int(k.height * 2.6)), Image.BICUBIC).filter(ImageFilter.GaussianBlur(10))
    k = ImageEnhance.Brightness(k).enhance(0.55)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    lay.alpha_composite(k, (W - 420, H - 680))
    return lay


def shot_s2k(t, lt, a, e):
    z = lerp(1.0, 1.08, ease(lt / (e - a)))
    fr = Frame('palace', z, 640, 340)
    sway = 1.5 * math.sin(lt * 3)
    fr.put(face('K', t), 640, 760, 1.3, rot=sway, anchor=(0.5, 1.0))
    fr.overlay(vig(0.6))
    return fr


def ink_transition(fr_from, fr_to, p):
    """墨跡暈開的轉場：雜訊遮罩由中心向外擴散。"""
    m = ink_mask()
    th = p * 1.25
    a = np.clip((th - m) / 0.08, 0, 1)
    mask = Image.fromarray((a * 255).astype(np.uint8))
    out = fr_from.img.copy()
    out.paste(fr_to.img, (0, 0), mask)
    edge = np.clip(1 - np.abs(th - m) / 0.05, 0, 1) * (p < 1)
    ed = Image.new('RGBA', (W, H), (15, 12, 10, 0))
    ed.putalpha(Image.fromarray((edge * 230).astype(np.uint8)))
    out.alpha_composite(ed)
    fr_to.img = out
    return fr_to


@lru_cache(1)
def ink_mask():
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot((xx - W / 2) / W, (yy - H / 2) / W) * 1.6
    n = noise_img(W, H, 60, 4) * 0.25 + noise_img(W, H, 14, 5) * 0.1
    return np.clip(r + n, 0, 1.1)


def street(fr, t, who, x, scale, slide=0.0, flee=0.0):
    im = ink_style(face(who, t))
    bob = 0
    if flee:
        bob = -abs(math.sin(t * 14)) * 12
    fr.put(im, x + slide, 690 + bob, scale)


def shot_s3(t, lt, a, e):
    a3, e3 = beat_t('s3', 'A')
    p = ease((t - a3 + 0.2) / 1.3)
    # 由路人甲驚恐的臉部特寫拉遠
    z = lerp(2.3, 1.0, p)
    fr = Frame('market', z, lerp(770, 640, p), lerp(370, 360, p), shake=0.3 if lt > 1.4 else 0, t=t)
    street(fr, t, 'A', 760, 1.05)
    if t > a3 + 0.8:
        ghost_king(fr, t, 1150, 'shake' if t > beat_t('s3', 'K')[0] else 'none')
    if lt < 1.5:
        prev = shot_s2k(t, t - SHOT_T['s2k'][0], *SHOT_T['s2k'])
        fr = ink_transition(prev, fr, lt / 1.5)
    return fr


def shot_s4(t, lt, a, e):
    fr = Frame('market', 1.0, 640, 360, shake=0.6, t=t)
    ab = beat_t('s4', 'B')[0]
    slide = lerp(500, 0, ease((t - ab + 0.6) / 0.5))
    street(fr, t, 'A', 600, 1.0)
    street(fr, t, 'B', 840, 1.0, slide)
    ghost_king(fr, t, 1170, 'stroke')
    return fr


def shot_s5(t, lt, a, e):
    ac = beat_t('s5', 'C')[0]
    slide = lerp(700, 0, ease((t - ac + 0.5) / 0.4))
    fr = Frame('market', lerp(1.04, 1.1, lt / (e - a)), 640, 360, shake=0.9, t=t)
    street(fr, t, 'A', 520, 0.95)
    street(fr, t, 'B', 740, 0.95)
    street(fr, t, 'C', 980, 0.95, slide)
    return fr


TIGER = {}


def tiger(j):
    k = round(j * 10) / 10
    if k not in TIGER:
        TIGER[k] = draw_tiger(k)
    return TIGER[k]


@lru_cache(1)
def tiger_particles():
    a = np.asarray(tiger(0.0).split()[3])
    ys, xs = np.where(a > 150)
    idx = rng.choice(len(xs), 2200, replace=False)
    return [(xs[i], ys[i], rng.uniform(-900, 900), rng.uniform(-500, 500), rng.uniform(3, 9), rng.uniform(0, 0.35)) for i in idx]


def shot_s5t(t, lt, a, e):
    # 仰角：猛虎由墨跡凝聚，壓迫感十足
    roar = max(0, lt - 0.6)
    shake = 2.0 if 0.6 < lt < 3.6 else 0.3
    fr = Frame('market', 1.12, 640, 420, shake=shake, t=t)
    gather = ease(lt / 0.9)
    tx, ty, ts = 330, 760, lerp(0.9, 1.05, ease(lt / 3))   # 虎頭的底部中心（世界座標）
    # 三人與民眾四散奔逃
    run = max(0.0, lt - 0.8)
    for i, name in enumerate(('a_s', 'c_s', 'b_s', 'a_s')):
        im = ink_style(SMALL[name])
        x = 180 + i * 90 + run * (520 + 60 * i)
        if x < 1500:
            fr.put(im, x, 600 + 25 * i - abs(math.sin(t * 13 + i)) * 10, 0.55, alpha=0.75)
    fl = ease((lt - 0.7) / 1.6)
    for who, x0, dx in (('A', 560, 900), ('B', 780, 900), ('C', 1000, 800)):
        street(fr, t, who, x0 + dx * fl, 0.95, flee=fl > 0)
    # 墨點聚合
    if gather < 1:
        d = ImageDraw.Draw(fr.img)
        for (x, y, ox, oy, s, delay) in tiger_particles():
            q = ease((gather - delay) / (1 - delay)) if gather > delay else 0
            wx = tx + (x - 400) * ts + ox * (1 - q)
            wy = ty - (800 - y) * ts + oy * (1 - q)
            sx, sy = fr.to_screen(wx, wy)
            r = s * fr.zoom * (1.3 - 0.5 * q)
            d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(25, 22, 20, 230))
    if gather > 0.6:
        jaw = 0.0 if roar <= 0 else min(1, roar / 0.35) * (0.75 + 0.25 * math.sin(roar * 10)) * (1 - ease((lt - 3.6) / 0.5))
        al = ease((gather - 0.6) / 0.4)
        fr.put(tiger(jaw), tx, ty, ts * (1 + 0.04 * jaw), anchor=(0.5, 1.0), alpha=al)
    fr.overlay(vig(0.5 + 0.3 * min(1, roar)))
    return fr


def shot_s5k(t, lt, a, e):
    # 回到現實：魏王恍然大悟（暖色調）
    nod = 4 * max(0, math.sin((t - beat_t('s5k', 'K')[0]) * 6)) if t > beat_t('s5k', 'K')[1] - 0.8 else 0
    fr = Frame('palace', 1.0, 640, 360)
    fr.put(face('K', t), 640, 1080 + nod, 2.1)
    fr.overlay(vig(0.6))
    if lt < 0.4:
        fr.img = Image.blend(Image.new('RGBA', (W, H), (255, 245, 220, 255)), fr.img, lt / 0.4)
    return fr


def shot_s6(t, lt, a, e):
    second = t >= beat_t('s6', 'P', 1)[0] - 0.05
    z = lerp(1.0, 1.05, (lt % 8) / 8)
    fr = Frame('palace_blur', z, 640, 360)
    if not second:
        fr.put(face('P', t), 640, 1130, 2.0)
    else:
        fr.put(face('P', t), 600, 1350, 2.5)
    fr.overlay(vig(0.55))
    return fr


def shot_s7(t, lt, a, e):
    pat = 6 * abs(math.sin(lt * 5)) if lt < 1.2 else 0
    fr = Frame('palace', 1.0, 640, 360)
    fr.put(face('K', t), 640, 790 - pat, 1.35)
    fr.overlay(vig(0.6))
    return fr


WHISPER_TXT = ['聽說龐蔥在趙國結交權貴……', '龐蔥對大王不忠啊……', '他早就想投靠趙國了……', '大王，可別再信龐蔥了……']


def shot_s7w(t, lt, a, e):
    if lt < 2.8:
        # 快轉：龐蔥背影走向殿門，逐漸變小
        p = lt / 2.8
        fr = Frame('door', 1.0, 640, 360)
        sc = lerp(1.1, 0.22, ease(p))
        fr.put(silhouette('pang_s'), 640 + 10 * math.sin(lt * 9) * (1 - p), lerp(760, 540, ease(p)), sc,
               alpha=1 - ease((p - 0.8) / 0.2))
        # 快轉的掃描線
        d = ImageDraw.Draw(fr.img)
        for k in range(3):
            y = (lt * 900 + k * 260) % H
            d.rectangle([0, y, W, y + 3], fill=(255, 255, 255, 40))
        fr.overlay(vig(0.6))
        if lt > 2.5:
            fr.darken((lt - 2.5) / 0.3)
        return fr
    q = (lt - 2.8) / (e - a - 2.8)
    z = lerp(1.35, 1.0, ease(q))   # 緩慢拉遠
    fr = Frame('palace', z, 640, lerp(330, 360, q), shake=0.4 * max(0, q - 0.7) / 0.3, t=t)
    king = face('K', t)
    anger = ease((q - 0.45) / 0.45)
    if anger > 0:
        king = angry(king, anger)
    fr.put(king, 640, 760, 1.25)
    for i, (sp, x, y, sc, flip) in enumerate([('shadowL', 300, 720, 0.95, False), ('shadowR', 1000, 700, 1.15, False),
                                             ('shadowL', 1060, 760, 0.8, True), ('shadowR', 230, 780, 0.9, True)]):
        rise = ease((q - i * 0.12) / 0.3)
        if rise <= 0:
            continue
        fr.put(SMALL[sp], x + 8 * math.sin(t * 2 + i), y + (1 - rise) * 250 + 6 * math.sin(t * 3 + i), sc, alpha=rise * 0.92, flip=flip)
    fr.darken(0.15 + 0.3 * q, (20, 0, 20))
    fr.overlay(vig(0.6 + 0.5 * q))
    d = ImageDraw.Draw(fr.img)
    for i, txt in enumerate(WHISPER_TXT):
        p0 = 0.08 + i * 0.18
        if q > p0:
            al = min(1, (q - p0) / 0.1) * (0.75 - 0.3 * max(0, q - p0 - 0.4))
            x = [250, 980, 300, 960][i]
            y = [170, 230, 330, 400][i] - (q - p0) * 60
            d.text((x, y), txt, font=font(30), fill=(200, 190, 210, int(255 * max(0, al))), anchor='mm')
    if anger > 0.3:
        kw, kh = FACES['K'].img.size
        hx, hy = fr.to_screen(640 + (318 - kw / 2) * 1.25, 760 - (kh - 100) * 1.25)
        anger_mark(fr.img, hx, hy, 26 * fr.zoom * (0.9 + 0.1 * math.sin(t * 12)), anger)
    return fr


def angry(im, amt):
    """臉部轉紅：在頭部區域疊加紅色。"""
    im = im.copy()
    face_mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(face_mask).ellipse([185, 40, 310, 190], fill=int(110 * amt))
    face_mask = ImageChops.multiply(face_mask.filter(ImageFilter.GaussianBlur(12)), im.split()[3])
    red = Image.new('RGBA', im.size, (210, 20, 10, 255))
    im.paste(red, (0, 0), face_mask)
    return im


def anger_mark(img, x, y, r, a):
    d = ImageDraw.Draw(img)
    col = (230, 30, 30, int(255 * min(1, a)))
    for k in range(4):
        ang = k * math.pi / 2 + math.pi / 4
        cx, cy = x + math.cos(ang) * r * 0.7, y + math.sin(ang) * r * 0.7
        d.arc([cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5], math.degrees(ang) + 90, math.degrees(ang) + 270, fill=col, width=max(2, int(r * 0.22)))


@lru_cache(1)
def dust():
    return [(rng.uniform(560, 720), rng.uniform(220, 640), rng.normal(0, 40), rng.uniform(80, 220)) for _ in range(500)]


def shot_s8(t, lt, a, e):
    fr = Frame(None)
    s8a, s8e = beat_t('s8', 'N')
    # 一束光照在龐蔥的剪影上，之後剪影消散
    beam = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    bi = min(1, lt / 0.8)
    bd.polygon([(590, -10), (690, -10), (840, 640), (440, 640)], fill=(255, 240, 200, int(70 * bi)))
    bd.ellipse([420, 600, 860, 680], fill=(255, 240, 200, int(110 * bi)))
    fr.overlay(beam.filter(ImageFilter.GaussianBlur(25)))
    dis = ease((lt - 2.2) / 1.6)
    if dis < 1:
        sil = silhouette('pang_s', (25, 20, 25))
        if dis > 0:
            sil = sil.copy()
            sil.putalpha(sil.split()[3].point(lambda v: int(v * (1 - dis))))
        fr.put(sil, 640, 640, 1.25)
        if dis > 0:
            d = ImageDraw.Draw(fr.img)
            for x0, y0, vx, vy in dust():
                px, py = x0 + vx * dis, y0 - vy * dis
                d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(60, 50, 60, int(200 * (1 - dis))))
    # 字幕逐字浮現（與旁白同步）
    text = BEATS[[b['shot'] for b in BEATS].index('s8')]['text']
    n = int(len(text) * min(1, max(0, (t - s8a) / (s8e - s8a) * 1.1)))
    if n:
        lines = wrap(text, 14)
        d = ImageDraw.Draw(fr.img)
        shown = 0
        for i, ln in enumerate(lines):
            part = ln[:max(0, n - shown)]
            shown += len(ln)
            d.text((W / 2 - d.textlength(ln, font=font(44)) / 2, 300 + i * 66), part, font=font(44), fill=(250, 250, 245), anchor='lm')
    return fr


def shot_s8m(t, lt, a, e):
    fr = Frame(None)
    p = ease(lt / 1.2)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.text((W / 2, 290), '謠言止於智者', font=font(96), fill=(250, 245, 230, 255), anchor='mm')
    am, em = beat_t('s8m', 'N')
    p2 = ease((t - am - 1.2) / 0.8)
    if p2 > 0:
        d.text((W / 2, 440), '三人成虎　切勿盲從', font=font(70), fill=(255, 200, 100, int(255 * p2)), anchor='mm')
    lay = lay.filter(ImageFilter.GaussianBlur((1 - p) * 8))
    lay.putalpha(lay.split()[3].point(lambda v: int(v * p)))
    fr.overlay(lay)
    # 紅色印章
    if p2 > 0:
        sd = ImageDraw.Draw(fr.img)
        sd.rounded_rectangle([1010, 540, 1110, 640], 8, fill=(180, 30, 30, int(255 * p2)))
        for i, ch in enumerate('三人成虎'):
            sd.text((1085 - (i // 2) * 50, 565 + (i % 2) * 50), ch, font=font(40), fill=(255, 235, 220, int(255 * p2)), anchor='mm')
    fade = ease((t - (e - 2.0)) / 2.0)
    fr.darken(fade)
    return fr


SHOT_FN = {'s1': shot_s1, 's2p': shot_s2p, 's2k': shot_s2k, 's3': shot_s3, 's4': shot_s4, 's5': shot_s5,
           's5t': shot_s5t, 's5k': shot_s5k, 's6': shot_s6, 's7': shot_s7, 's7w': shot_s7w, 's8': shot_s8, 's8m': shot_s8m}


def render(t):
    for s, a, e in SHOTS:
        if a <= t < e or s == SHOTS[-1][0]:
            fr = SHOT_FN[s](t, t - a, a, e)
            break
    subtitle(fr, t)
    return fr.img.convert('RGB')


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--preview':
        ts = [float(x) for x in sys.argv[2].split(',')]
        ims = [render(t).resize((640, 360)) for t in ts]
        cols = 3
        sheet = Image.new('RGB', (640 * cols, 360 * math.ceil(len(ims) / cols)))
        for i, im in enumerate(ims):
            ImageDraw.Draw(im).text((8, 8), f'{ts[i]:.1f}s', fill='yellow', font=font(24))
            sheet.paste(im, ((i % cols) * 640, (i // cols) * 360))
        sheet.save('build/preview.png')
        return
    n = int(TOTAL * FPS)
    proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                             '-r', str(FPS), '-i', '-', '-i', 'build/audio.wav', '-c:v', 'libx264', '-preset', 'medium',
                             '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
                             '-shortest', '-movflags', '+faststart', '三人成虎.mp4'], stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(render(i / FPS).tobytes())
        if i % 150 == 0:
            print(f'{i}/{n}', flush=True)
    proc.stdin.close()
    proc.wait()


if __name__ == '__main__':
    main()
