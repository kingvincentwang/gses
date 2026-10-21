"""程式繪製的水墨猛虎頭（正面咆哮），jaw 0..1 控制張嘴幅度。"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 4  # 超取樣倍率


def _p(pts, ox=0, oy=0):
    return [((x + ox) * S, (y + oy) * S) for x, y in pts]


def _stroke(d, pts, w0, w1, fill):
    """沿折線畫出由粗變細的筆觸。"""
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        x2, y2 = pts[min(i + 1, n - 1)]
        x1, y1 = pts[max(i - 1, 0)]
        dx, dy = x2 - x1, y2 - y1
        l = math.hypot(dx, dy) or 1
        w = w0 + (w1 - w0) * i / (n - 1)
        nx, ny = -dy / l * w / 2, dx / l * w / 2
        left.append((x + nx, y + ny))
        right.append((x - nx, y - ny))
    d.polygon(_p(left + right[::-1]), fill=fill)


def _curve(a, b, c, n=12):
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * b[0] + t * t * c[0],
             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * b[1] + t * t * c[1]) for t in np.linspace(0, 1, n)]


def draw_tiger(jaw=1.0, seed=3):
    W = H = 800
    ink = Image.new('L', (W * S, H * S), 0)       # 墨色濃度
    d = ImageDraw.Draw(ink)
    cx = 400
    # 耳朵
    for sgn in (-1, 1):
        d.polygon(_p([(cx + sgn * 150, 210), (cx + sgn * 265, 95), (cx + sgn * 290, 250)]), fill=150)
        d.polygon(_p([(cx + sgn * 170, 205), (cx + sgn * 255, 130), (cx + sgn * 268, 235)]), fill=235)
    # 頭部輪廓（臉頰帶毛刺）
    pts = []
    for k in range(64):
        a = 2 * math.pi * k / 64
        r = 1.0 + (0.09 if k % 2 == 0 and abs(math.cos(a)) > 0.45 else 0)
        pts.append((cx + 300 * r * math.cos(a) * (1.05 if math.sin(a) > 0 else 1), 400 + 255 * r * math.sin(a)))
    d.polygon(_p(pts), fill=110)
    # 下巴（隨張嘴下移）
    jy = 120 * jaw
    d.ellipse(_p([(cx - 170, 430 + jy * 0.5), (cx + 170, 640 + jy)]), fill=110)
    d.rectangle(_p([(cx - 165, 480), (cx + 165, 540 + jy)]), fill=110)
    # 額頭的「王」字
    for y in (225, 262, 300):
        _stroke(d, [(cx - 55, y), (cx, y - 4), (cx + 55, y)], 16, 8, 255)
    _stroke(d, [(cx, 222), (cx + 2, 262), (cx, 302)], 16, 10, 255)
    # 斑紋
    for sgn in (-1, 1):
        for i, (y, l) in enumerate([(300, 120), (360, 140), (420, 130), (480, 100)]):
            x0 = cx + sgn * 300
            _stroke(d, _curve((x0, y), (x0 - sgn * l * 0.6, y - 25), (x0 - sgn * l, y + 10)), 30, 4, 245)
        for y in (150, 175):
            _stroke(d, _curve((cx + sgn * 120, y + 20), (cx + sgn * 80, y), (cx + sgn * 50, y + 25)), 14, 4, 245)
    # 眉骨與怒目
    for sgn in (-1, 1):
        _stroke(d, _curve((cx + sgn * 40, 330), (cx + sgn * 110, 290), (cx + sgn * 200, 300)), 26, 10, 255)
    # 口鼻部
    for sgn in (-1, 1):
        d.ellipse(_p([(cx + sgn * 75 - 85, 440), (cx + sgn * 75 + 85, 545)]), fill=35)
    d.polygon(_p([(cx - 48, 415), (cx + 48, 415), (cx + 12, 460), (cx - 12, 460)]), fill=255)
    _stroke(d, [(cx, 460), (cx, 485)], 10, 6, 255)
    for sgn in (-1, 1):
        for j in range(3):
            for k in range(3):
                d.ellipse(_p([(cx + sgn * (50 + 25 * k) - 4, 470 + 18 * j - 4), (cx + sgn * (50 + 25 * k) + 4, 470 + 18 * j + 4)]), fill=230)
    # 張開的大嘴
    mouth = Image.new('L', ink.size, 0)
    md = ImageDraw.Draw(mouth)
    if jaw > 0.05:
        md.ellipse(_p([(cx - 120, 500), (cx + 120, 520 + 130 * jaw)]), fill=255)
    ink = ink.filter(ImageFilter.GaussianBlur(2 * S))

    # 毛筆飛白：以雜訊擾動墨色
    rng = np.random.default_rng(seed)
    a = np.asarray(ink, np.float32) / 255
    noise = np.zeros(a.shape, np.float32)
    for div, amp in ((64, 0.5), (24, 0.3), (8, 0.2)):
        n = (rng.random((H // div + 1, W // div + 1)) * 255).astype(np.uint8)
        noise += amp * np.asarray(Image.fromarray(n).resize(ink.size, Image.BICUBIC), np.float32) / 255
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]] / a.shape[0]
    edge = np.clip(np.hypot(xx - 0.5, (yy - 0.5) * 1.1) * 1.6, 0, 1)   # 外圈墨色較濃
    a = np.clip(a * (0.6 + 0.6 * noise + 0.5 * edge * (a > 0.3)), 0, 1)
    alpha = np.clip(np.asarray(ink, np.float32) / 255 * 12, 0, 1)   # 有墨處完全不透明
    tone = 30 + (1 - a) * 150    # 濃墨暗、淡墨亮
    rgb = np.stack([tone, tone * 0.98, tone * 0.94], -1)
    img = Image.fromarray(np.concatenate([rgb, alpha[..., None] * 255], -1).astype(np.uint8), 'RGBA')

    # 嘴內、獠牙、舌頭
    if jaw > 0.05:
        inner = Image.new('RGBA', ink.size, (25, 8, 8, 255))
        tongue = ImageDraw.Draw(inner)
        tongue.ellipse(_p([(cx - 70, 470 + 120 * jaw), (cx + 70, 540 + 130 * jaw)]), fill=(120, 30, 30, 255))
        img.paste(inner, (0, 0), mouth.filter(ImageFilter.GaussianBlur(S)))
        td = ImageDraw.Draw(img)
        for sgn in (-1, 1):
            td.polygon(_p([(cx + sgn * 82, 506), (cx + sgn * 52, 504), (cx + sgn * 68, 506 + 70 * jaw)]), fill=(245, 240, 225, 255))
            td.polygon(_p([(cx + sgn * 80, 512 + 128 * jaw), (cx + sgn * 54, 514 + 128 * jaw), (cx + sgn * 66, 512 + 78 * jaw)]), fill=(245, 240, 225, 255))
    # 發光的眼睛
    glow = Image.new('RGBA', ink.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for sgn in (-1, 1):
        ex = cx + sgn * 115
        gd.ellipse(_p([(ex - 60, 300), (ex + 60, 380)]), fill=(255, 150, 20, 160))
    glow = glow.filter(ImageFilter.GaussianBlur(18 * S))
    img = Image.alpha_composite(img, glow)
    ed = ImageDraw.Draw(img)
    for sgn in (-1, 1):
        ex = cx + sgn * 115
        ed.polygon(_p([(ex - sgn * 55, 352), (ex, 318), (ex + sgn * 55, 330), (ex + sgn * 10, 372)]), fill=(255, 190, 40, 255))
        ed.ellipse(_p([(ex - 7, 322), (ex + 7, 366)]), fill=(10, 5, 0, 255))
    return img.resize((W, H), Image.LANCZOS)


if __name__ == '__main__':
    bg = Image.new('RGBA', (1600, 800), (232, 226, 210, 255))
    bg.alpha_composite(draw_tiger(0.0), (0, 0))
    bg.alpha_composite(draw_tiger(1.0), (800, 0))
    bg.convert('RGB').save('build/tiger_preview.png')
