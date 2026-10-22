"""關西小子舞步教學影片產生器〈嗨！我是關西〉

用法：python3 dance/make_video.py
輸出：dance/kuanxi-dance.mp4（1280x720、30fps、120 BPM 配樂）
需要：Pillow、numpy、ffmpeg
"""
import math
import os
import random
import subprocess
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHAR_PATH = os.path.join(HERE, "kuanxi-boy.webp")
FONT_PATH = os.path.join(ROOT, "Iansui-Regular.ttf")
OUT_PATH = os.path.join(HERE, "kuanxi-dance.mp4")
WAV_PATH = os.path.join(HERE, "_music.wav")

W, H = 1280, 720
FPS = 30
BPM = 120
SPB = 60 / BPM  # 每拍秒數
CHAR_H = 440  # 角色高度（像素）
FEET_X, FEET_Y = W // 2, 628

ORANGE = (255, 140, 30)
BLUE = (30, 90, 200)
NAVY = (20, 50, 120)
YELLOW = (255, 225, 40)
WHITE = (255, 255, 255)

# ---------------------------------------------------------------- 時間軸
SEGMENTS = []  # (起始拍, 拍數, 段落, 動作, 口令, 參數)


def add(section, move, beats, caption="", **params):
    start = SEGMENTS[-1][0] + SEGMENTS[-1][1] if SEGMENTS else 0
    SEGMENTS.append((start, beats, section, move, caption, params))


add("", "title", 4)

S = "前奏：登場亮相"
add(S, "back_nod", 4, "背對觀眾・雙手壓帽簷・跟著節拍點頭")
add(S, "reveal", 4, "跳轉面向前方！右手揮手・左手扠腰")
add(S, "wave4", 4, "定格不動・只揮手 4 下・保持笑容")
add(S, "sparkle", 4, "手掌在臉旁抖 3 下「閃閃發光」")

S = "A 段：嗨！打招呼"
for rep in range(2):
    add(S, "step", 2, "右腳往右踏・右手往右上揮", x0=0, x1=-90, flip=False)
    add(S, "step", 2, "左腳往左踏・左手往左上揮", x0=-90, x1=90, flip=True)
    add(S, "hop4", 4, "原地小跳 4 下・雙手輪流揮", x0=90)
    add(S, "head_sway", 4, "雙手扠腰・左右擺頭「你好呀～」")
    if rep == 0:
        add(S, "hip", 4, "屁股 左、右、左、右 扭 4 下")
    else:
        add(S, "hip", 2, "屁股 左、右 扭一扭")
        add(S, "spin", 2, "向右轉身！")

S = "B 段：戴帽帥氣"
for rep in range(2):
    add(S, "cap", 2, "右手摸帽簷・往右轉", d=1)
    add(S, "cap", 2, "左手摸帽簷・往左轉回來", d=-1)
    add(S, "thumbs", 4, "雙手比讚・身體往前彎一下")
    add(S, "windup", 4, "握住球棒・身體往後蓄力")
    add(S, "swing", 2, "一起喊「關西！」大力揮棒！" if rep else "大力揮棒！", shout=bool(rep))
    add(S, "lookfar", 2, "手搭眉毛往遠看「飛好遠～」")

S = "C 段：運動鞋快跑"
add(S, "run", 8, "抬高膝蓋・擺動手臂・原地跑步")
add(S, "heel", 2, "右腳跟往前點地・雙手往前推", d=1)
add(S, "recover", 2, "收回")
add(S, "heel", 2, "左腳跟往前點地・雙手往前推", d=-1)
add(S, "clap2", 2, "收回・拍手 2 下")
add(S, "spinhop", 8, "小跳步轉一圈・雙手在頭上搖擺")
add(S, "jacks", 8, "開合跳 4 次・合腳時拍手")

S = "D 段：一起當朋友"
for rep in range(2):
    add(S, "bigheart", 4, "雙手在頭上比大愛心")
    add(S, "smallheart", 4, "胸前比小愛心・往前送出")
    add(S, "wave_line", 8, "和同學牽手・從左到右做波浪")

S = "結尾：招牌定格"
add(S, "endspin", 4, "原地轉一圈")
add(S, "endjump", 2, "跳！雙腳張開落地")
add(S, "freeze", 2, "揮手・扠腰・歪頭大笑！定格！")

add("", "outro", 6)

TOTAL_BEATS = SEGMENTS[-1][0] + SEGMENTS[-1][1]
DANCE_START = SEGMENTS[1][0]
DANCE_END = SEGMENTS[-1][0]
TOTAL_SEC = TOTAL_BEATS * SPB
N_FRAMES = int(round(TOTAL_SEC * FPS))


def segment_at(beat):
    for seg in SEGMENTS:
        if seg[0] <= beat < seg[0] + seg[1]:
            return seg
    return SEGMENTS[-1]


# ---------------------------------------------------------------- 小工具
def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def bump(u):
    return math.sin(math.pi * u) if 0 < u < 1 else 0.0


def landing_squash(lb, amount=0.12, width=0.14):
    f = lb % 1.0
    d = min(f, 1 - f)
    return amount * max(0.0, 1 - d / width)


_FONTS = {}


def font(size):
    if size not in _FONTS:
        _FONTS[size] = ImageFont.truetype(FONT_PATH, size)
    return _FONTS[size]


def heart_poly(cx, cy, size, n=40):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 32, cy - y * size / 32))
    return pts


def star_poly(cx, cy, r_out, r_in, n=8, rot=0.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ---------------------------------------------------------------- 素材（每個 worker 載入一次）
ASSETS = {}


def load_assets():
    if ASSETS:
        return
    src = Image.open(CHAR_PATH).convert("RGBA")
    src = src.crop(src.getbbox())
    scale = CHAR_H / src.height
    char = src.resize((int(src.width * scale), CHAR_H), Image.LANCZOS)
    ASSETS["char"] = char
    ASSETS["char_flip"] = char.transpose(Image.FLIP_LEFT_RIGHT)
    sil = Image.new("RGBA", char.size, (25, 35, 70, 255))
    sil.putalpha(char.getchannel("A"))
    ASSETS["sil"] = sil
    small = char.resize((int(char.width * 0.5), int(char.height * 0.5)), Image.LANCZOS)
    ASSETS["small"] = small

    # 背景
    bg = Image.new("RGBA", (W, H))
    top, bot = np.array([150, 215, 255]), np.array([255, 244, 214])
    grad = np.linspace(0, 1, H)[:, None]
    arr = (top * (1 - grad) + bot * grad).astype(np.uint8)
    arr = np.repeat(arr[:, None, :], W, axis=1)
    bg = Image.fromarray(arr, "RGB").convert("RGBA")
    d = ImageDraw.Draw(bg)
    rnd = random.Random(7)
    for _ in range(14):  # 柔和圓點
        x, y, r = rnd.randint(0, W), rnd.randint(80, 480), rnd.randint(30, 90)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 35))
    bg = bg.filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(bg)
    d.rectangle((0, 560, W, H), fill=(110, 170, 240))  # 舞台地板
    for i in range(0, W, 80):
        d.line((W / 2 + (i - W / 2) * 0.4, 560, i, H), fill=(95, 155, 230), width=3)
    d.rectangle((0, 556, W, 566), fill=(255, 160, 60))
    ASSETS["bg"] = bg

    # 影子
    sh = Image.new("RGBA", (360, 90), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((30, 20, 330, 70), fill=(20, 40, 90, 120))
    ASSETS["shadow"] = sh.filter(ImageFilter.GaussianBlur(10))


# ---------------------------------------------------------------- 動作
def pose(move, lb, L, p):
    """回傳角色姿勢：x 位移、y 抬高、角度、縮放、旋轉相位、剪影、特效清單"""
    o = dict(x=0.0, y=0.0, ang=0.0, sx=1.0, sy=1.0, spin=0.0, flip=False, sil=False,
             fx=[], hide=False)
    fx = o["fx"]
    if move == "title":
        o["y"] = 10 * abs(math.sin(math.pi * lb))
        o["ang"] = 3 * math.sin(math.pi * lb)
        o["x"] = 300
        fx.append(("title",))
    elif move == "back_nod":
        o["sil"] = True
        o["flip"] = True
        o["ang"] = 3 * math.sin(2 * math.pi * lb)
        o["y"] = 6 * abs(math.sin(math.pi * lb))
        fx.append(("question", lb))
    elif move == "reveal":
        k = ease(lb / 0.7)
        o["spin"] = 180 + 180 * k
        o["sil"] = o["spin"] < 270
        o["y"] = 70 * bump(lb / 0.7)
        if lb >= 0.7:
            o["ang"] = 5 * math.sin(2 * math.pi * (lb - 0.7))
            fx.append(("flash", lb - 0.7))
            fx.append(("sparkle", 1.0))
    elif move == "wave4":
        o["ang"] = 5 * math.sin(2 * math.pi * lb)
        fx.append(("sparkle", 0.9 + 0.2 * abs(math.sin(math.pi * lb))))
        fx.append(("countbig", int(lb) + 1))
    elif move == "sparkle":
        o["ang"] = 2 * math.sin(2 * math.pi * lb)
        pulse = 1 + 0.5 * abs(math.sin(math.pi * lb * 1.5))
        fx.append(("sparkle", 1.3 * pulse))
        fx.append(("stars", lb))
    elif move == "step":
        t = ease(lb / L)
        o["x"] = p["x0"] + (p["x1"] - p["x0"]) * t
        o["y"] = 25 * abs(math.sin(math.pi * lb))
        o["flip"] = p["flip"]
        o["ang"] = (8 if not p["flip"] else -8) * math.sin(math.pi * lb / L)
        fx.append(("sparkle", 0.9))
    elif move == "hop4":
        o["x"] = p["x0"] * (1 - ease(lb))
        o["y"] = 35 * abs(math.sin(math.pi * lb))
        s = landing_squash(lb)
        o["sy"], o["sx"] = 1 - s, 1 + s * 0.6
        o["flip"] = int(lb) % 2 == 1
        fx.append(("sparkle", 0.8))
    elif move == "head_sway":
        o["ang"] = 8 * math.sin(math.pi * lb)
        fx.append(("bubble", "你好呀～"))
    elif move == "hip":
        o["ang"] = 9 * math.sin(math.pi * lb)
        o["x"] = 18 * math.sin(math.pi * lb)
        fx.append(("wiggle", lb))
    elif move in ("spin", "endspin"):
        o["spin"] = 360 * ease(lb / L)
        o["y"] = 20 * bump(lb / L)
        fx.append(("spinlines", lb / L))
    elif move == "cap":
        d = p["d"]
        o["ang"] = 10 * d * math.sin(math.pi * lb / 2)
        fx.append(("cap_arrow", d, lb / L))
    elif move == "thumbs":
        bow = math.sin(math.pi * min(lb, 3.5) / 3.5)
        o["sy"] = 1 - 0.12 * bow
        o["sx"] = 1 + 0.04 * bow
        o["ang"] = 2 * math.sin(2 * math.pi * lb)
        fx.append(("bubble", "讚！"))
    elif move == "windup":
        t = ease(lb / L)
        o["ang"] = 14 * t + 1.5 * math.sin(4 * math.pi * lb) * t
        o["x"] = 25 * t
        fx.append(("power", t))
    elif move == "swing":
        if lb < 0.25:
            o["ang"] = 14 - 36 * ease(lb / 0.25)
        else:
            o["ang"] = -22 + 17 * ease((lb - 0.25) / 1.0)
        o["x"] = 25 * (1 - ease(lb / 0.25))
        fx.append(("swoosh", lb))
        fx.append(("ball", lb))
        if p.get("shout"):
            fx.append(("shout", lb))
    elif move == "lookfar":
        o["ang"] = -5 + 1.5 * math.sin(2 * math.pi * lb)
        fx.append(("ball", lb + 2))
        fx.append(("bubble", "飛好遠～"))
    elif move == "run":
        o["y"] = 18 * abs(math.sin(2 * math.pi * lb))
        o["ang"] = 4 * math.sin(2 * math.pi * lb)
        fx.append(("speed", lb))
    elif move == "heel":
        d = p["d"]
        t = math.sin(math.pi * min(lb, 1.0) / 1.0 * 0.5) if lb < 1 else 1.0
        o["ang"] = 7 * d * t
        o["x"] = -20 * d * t
        o["flip"] = d < 0
        fx.append(("push", d, t))
    elif move == "recover":
        o["y"] = 8 * abs(math.sin(math.pi * lb))
    elif move == "clap2":
        o["y"] = 10 * abs(math.sin(math.pi * lb))
        for k in range(2):
            if 0 <= lb - k < 0.6:
                fx.append(("clap", lb - k, k))
    elif move == "spinhop":
        o["spin"] = 360 * lb / L
        o["y"] = 25 * abs(math.sin(math.pi * lb))
        s = landing_squash(lb, 0.08)
        o["sy"], o["sx"] = 1 - s, 1 + s * 0.5
        fx.append(("notes", lb))
    elif move == "jacks":
        f = lb % 2
        o["y"] = 40 * abs(math.sin(math.pi * lb))
        open_amt = bump(f / 2)
        o["sx"] = 1 + 0.16 * open_amt
        o["sy"] = 1 - 0.06 * open_amt
        if 1.85 <= f or f < 0.45:
            fx.append(("clap", (f - 1.85) % 2, int(lb // 2)))
    elif move == "bigheart":
        o["ang"] = 4 * math.sin(math.pi * lb)
        fx.append(("bigheart", lb))
    elif move == "smallheart":
        o["y"] = 8 * abs(math.sin(math.pi * lb))
        fx.append(("hearts", lb))
    elif move == "wave_line":
        o["hide"] = True
        fx.append(("wave_line", lb))
    elif move == "endjump":
        if lb < 1.2:
            o["y"] = 130 * bump(lb / 1.2)
            o["sy"], o["sx"] = 1 + 0.08 * bump(lb / 1.2), 1 - 0.05 * bump(lb / 1.2)
        else:
            s = 0.14 * max(0, 1 - (lb - 1.2) / 0.4)
            o["sy"], o["sx"] = 1 - s, 1 + s * 0.7
        fx.append(("sparkle", 0.8))
    elif move == "freeze":
        o["ang"] = -6 * ease(lb / 0.3)
        fx.append(("sparkle", 1.4))
        fx.append(("confetti", lb))
        fx.append(("burst", lb))
    elif move == "outro":
        o["y"] = 10 * abs(math.sin(math.pi * lb))
        o["ang"] = 3 * math.sin(math.pi * lb)
        o["x"] = -300
        fx.append(("confetti", lb + 2))
        fx.append(("outro",))
    return o


# ---------------------------------------------------------------- 繪圖
def render_char(frame, o, base_x, base_y, img_key="char", scale=1.0, shadow_k=1.0):
    spin = o["spin"] % 360
    cosv = math.cos(math.radians(spin))
    flip = o["flip"] ^ (cosv < 0)
    if o["sil"]:
        img = ASSETS["sil"]
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
    elif img_key == "small":
        img = ASSETS["small"]
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
    else:
        img = ASSETS["char_flip" if flip else "char"]
    sx = o["sx"] * max(0.04, abs(cosv)) * scale
    sy = o["sy"] * scale
    w = max(2, int(img.width * sx))
    h = max(2, int(img.height * sy))
    img = img.resize((w, h), Image.BILINEAR)
    cw, ch = 1000, 760
    fx, fy = cw // 2, 680
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(img, (fx - w // 2, fy - h), img)
    if abs(o["ang"]) > 0.05:
        canvas = canvas.rotate(o["ang"], resample=Image.BICUBIC, center=(fx, fy))
    x = int(base_x + o["x"])
    y = int(base_y - o["y"])
    # 影子
    sh = ASSETS["shadow"]
    k = max(0.45, 1 - o["y"] / 220) * shadow_k * max(0.5, sx / scale)
    shr = sh.resize((max(2, int(sh.width * k)), max(2, int(sh.height * k))), Image.BILINEAR)
    frame.alpha_composite(shr, (int(base_x + o["x"] - shr.width / 2), int(base_y - shr.height / 2)))
    frame.paste(canvas, (x - fx, y - fy), canvas)
    return x, y, w, h, flip


def draw_sparkle(d, cx, cy, s, flip):
    # 仿角色圖上的黃色閃光線條
    sign = 1 if flip else -1
    for ang, ln in ((-60, 46), (-25, 50), (10, 40)):
        a = math.radians(ang)
        dx, dy = math.cos(a) * sign, math.sin(a)
        x0, y0 = cx + dx * 26 * s, cy + dy * 26 * s
        x1, y1 = cx + dx * (26 + ln) * s, cy + dy * (26 + ln) * s
        d.line((x0, y0, x1, y1), fill=YELLOW + (255,), width=max(3, int(13 * s)))
        r = 6.5 * s
        d.ellipse((x0 - r, y0 - r, x0 + r, y0 + r), fill=YELLOW + (255,))
        d.ellipse((x1 - r, y1 - r, x1 + r, y1 + r), fill=YELLOW + (255,))


def text_center(d, xy, text, size, fill, stroke=0, stroke_fill=WHITE):
    f = font(size)
    d.text(xy, text, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)


def bubble(d, x, y, text):
    f = font(34)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    tw, th = r - l, b - t
    box = (x - tw / 2 - 22, y - th / 2 - 16, x + tw / 2 + 22, y + th / 2 + 16)
    d.rounded_rectangle(box, radius=24, fill=(255, 255, 255, 240), outline=ORANGE + (255,), width=4)
    d.polygon([(x - 18, box[3] - 2), (x + 4, box[3] - 2), (x - 26, box[3] + 22)],
              fill=(255, 255, 255, 240))
    d.text((x, y), text, font=f, fill=NAVY, anchor="mm")


CONFETTI = [(random.Random(i).uniform(0, W), random.Random(i * 7).uniform(0, H),
             random.Random(i * 13).uniform(120, 260), random.Random(i * 17).choice(
                 [ORANGE, BLUE, YELLOW, (255, 90, 120), (80, 200, 120)]),
             random.Random(i * 19).uniform(0, 6.28)) for i in range(90)]


def draw_fx(d, frame, o, cx, cy, flip, t_sec, beat):
    hand_x = cx + (0.27 if flip else -0.27) * CHAR_H * 0.88 * o["sx"]
    hand_y = cy - 0.55 * CHAR_H * o["sy"]
    head_y = cy - CHAR_H * o["sy"]
    for e in o["fx"]:
        kind = e[0]
        if kind == "sparkle":
            draw_sparkle(d, hand_x, hand_y, e[1], flip)
        elif kind == "question":
            a = int(255 * min(1, e[1] / 1.0))
            text_center(d, (cx + 150, head_y + 40), "？", 80, (255, 140, 30, a), 4)
        elif kind == "flash":
            a = int(200 * max(0, 1 - e[1] / 0.6))
            if a > 0:
                d.rectangle((0, 0, W, H), fill=(255, 255, 255, a))
            r = 120 + e[1] * 260
            a2 = int(220 * max(0, 1 - e[1] / 1.2))
            if a2 > 0:
                d.polygon(star_poly(cx, cy - CHAR_H / 2, r * 1.4, r * 0.9, 12, e[1]),
                          outline=YELLOW + (a2,), width=8)
        elif kind == "countbig":
            text_center(d, (cx + 260, cy - 300), str(e[1]), 120, ORANGE + (255,), 8)
        elif kind == "stars":
            for i in range(6):
                a = i * math.pi / 3 + e[1] * 1.5
                r = 120 + 25 * math.sin(e[1] * 4 + i)
                x, y = hand_x + r * math.cos(a), hand_y + r * math.sin(a)
                d.polygon(star_poly(x, y, 16, 6, 5, e[1] * 3), fill=YELLOW + (230,))
        elif kind == "bubble":
            bubble(d, cx + (180 if not flip else -180), head_y + 10, e[1])
        elif kind == "wiggle":
            side = 1 if math.sin(math.pi * e[1]) > 0 else -1
            for i in range(3):
                x = cx - side * (150 + i * 22)
                d.arc((x - 30, cy - 260 - i * 18, x + 30, cy - 140 + i * 18),
                      90 - 60 if side < 0 else 90 + 0, 270 + 60 if side < 0 else 270,
                      fill=(255, 255, 255, 200), width=6)
        elif kind == "spinlines":
            for i in range(4):
                a = e[1] * 6.28 * 2 + i * 1.57
                x0 = cx + 230 * math.cos(a)
                y0 = cy - 230 + 60 * math.sin(a)
                d.ellipse((x0 - 10, y0 - 10, x0 + 10, y0 + 10), fill=(255, 255, 255, 220))
            d.arc((cx - 240, cy - 300, cx + 240, cy - 160), 0, 180, fill=(255, 255, 255, 180), width=6)
        elif kind == "cap_arrow":
            dd, t = e[1], e[2]
            ccx, ccy = cx, head_y + 30
            start = 200 if dd > 0 else -20
            sweep = 140 * ease(t)
            a0, a1 = (start, start + sweep) if dd > 0 else (start - sweep, start)
            d.arc((ccx - 170, ccy - 90, ccx + 170, ccy + 70), a0, a1, fill=ORANGE + (255,), width=10)
            tip = math.radians(a1 if dd > 0 else a0)
            tx, ty = ccx + 170 * math.cos(tip), ccy - 10 + 80 * math.sin(tip)
            d.ellipse((tx - 14, ty - 14, tx + 14, ty + 14), fill=ORANGE + (255,))
        elif kind == "power":
            for i in range(int(e[1] * 6) + 1):
                y = cy - 200 - i * 40
                d.line((cx - 230, y, cx - 270, y - 20), fill=(255, 90, 60, 220), width=8)
        elif kind == "swoosh":
            lb = e[1]
            if lb < 1.0:
                a = int(240 * (1 - lb))
                sweep = 200 * ease(lb / 0.3)
                d.arc((cx - 300, cy - 420, cx + 300, cy - 60), 160, 160 + sweep,
                      fill=(255, 255, 255, a), width=18)
                d.arc((cx - 270, cy - 390, cx + 270, cy - 90), 165, 165 + sweep * 0.9,
                      fill=(255, 230, 120, a), width=8)
        elif kind == "ball":
            u = (e[1] - 0.25) / 3.5
            if 0 <= u <= 1:
                bx = cx + 220 + 380 * u
                by = cy - 260 - 330 * math.sin(math.pi * 0.5 * u) - 40 * u
                r = 26 * (1 - 0.85 * u)
                d.ellipse((bx - r, by - r, bx + r, by + r), fill=WHITE + (255,), outline=(200, 40, 40, 255),
                          width=max(1, int(r / 7)))
                d.arc((bx - r * 1.6, by - r, bx - r * 0.4, by + r), -60, 60, fill=(220, 40, 40, 255),
                      width=max(1, int(r / 8)))
                d.arc((bx + r * 0.4, by - r, bx + r * 1.6, by + r), 120, 240, fill=(220, 40, 40, 255),
                      width=max(1, int(r / 8)))
                if u > 0.85:
                    s = (u - 0.85) / 0.15
                    d.polygon(star_poly(bx, by, 10 + 30 * s, 4 + 10 * s, 4, s), fill=YELLOW + (255,))
            elif u > 1:
                bx, by = cx + 560, cy - 560
                d.polygon(star_poly(bx, by, 40, 14, 4, 0.3), fill=YELLOW + (255,))
        elif kind == "shout":
            lb = e[1]
            if lb > 0.15:
                s = min(1.0, (lb - 0.15) / 0.25)
                size = int(60 + 70 * s)
                d.polygon(star_poly(cx - 300, cy - 420, 150 * s, 100 * s, 12), fill=YELLOW + (240,))
                text_center(d, (cx - 300, cy - 420), "關西！", size, (220, 60, 20, 255), 6)
        elif kind == "speed":
            for i in range(6):
                y = cy - 60 - i * 60
                off = ((e[1] * 300 + i * 70) % 160)
                for side in (-1, 1):
                    x0 = cx + side * (200 + off)
                    d.line((x0, y, x0 + side * 70, y), fill=(255, 255, 255, 200), width=5)
            for i in range(3):
                ph = (e[1] * 2 + i / 3) % 1
                r = 10 + 30 * ph
                a = int(180 * (1 - ph))
                for side in (-1, 1):
                    x = cx + side * (70 + 60 * ph)
                    d.ellipse((x - r, cy - r / 2, x + r, cy + r / 2), fill=(240, 240, 240, a))
        elif kind == "push":
            dd, t = e[1], e[2]
            x = cx + (-1 if dd > 0 else 1) * (210 + 40 * t)
            for i in range(3):
                y = cy - 300 + i * 40
                dirx = -1 if dd > 0 else 1
                d.polygon([(x + dirx * i * 0, y), (x + dirx * 40, y + 15), (x, y + 30)],
                          fill=ORANGE + (int(255 * t),))
        elif kind == "clap":
            lt = e[1]
            if 0 <= lt < 0.6:
                s = 0.6 + lt
                a = int(255 * (1 - lt / 0.6))
                x = cx + (220 if e[2] % 2 == 0 else -220)
                y = cy - 330
                d.polygon(star_poly(x, y, 80 * s, 50 * s, 10), fill=YELLOW + (a,))
                text_center(d, (x, y), "啪！", int(50 * s), (220, 60, 20, a), 4)
        elif kind == "notes":
            for i in range(4):
                ph = (e[1] * 0.5 + i / 4) % 1
                x = cx + (i - 1.5) * 110 + 20 * math.sin(e[1] * 3 + i)
                y = head_y - 10 - 140 * ph
                a = int(255 * (1 - ph))
                col = (BLUE if i % 2 else ORANGE) + (a,)
                d.ellipse((x - 16, y - 11, x + 16, y + 11), fill=col)
                d.line((x + 13, y, x + 13, y - 52), fill=col, width=6)
                d.line((x + 13, y - 52, x + 34, y - 40), fill=col, width=6)
        elif kind == "bigheart":
            s = 140 * (1 + 0.15 * abs(math.sin(math.pi * e[1])))
            d.polygon(heart_poly(cx, head_y - 30, s), fill=(255, 80, 120, 235))
            d.polygon(heart_poly(cx - s * 0.18, head_y - 30 - s * 0.2, s * 0.25), fill=(255, 190, 210, 255))
        elif kind == "hearts":
            for k in range(4):
                ph = e[1] - k
                if 0 <= ph < 2:
                    t = ph / 2
                    x = cx + (k % 2 * 2 - 1) * 260 * t
                    y = cy - 200 - 120 * t
                    s = 30 + 110 * t
                    a = int(255 * (1 - t))
                    d.polygon(heart_poly(x, y, s), fill=(255, 80, 120, a))
        elif kind == "wave_line":
            pass  # 另外處理
        elif kind == "confetti":
            for (x0, y0, sp, col, ph) in CONFETTI:
                y = (y0 + sp * t_sec) % (H + 40) - 20
                x = x0 + 20 * math.sin(t_sec * 2 + ph)
                a = ph + t_sec * 3
                w2, h2 = 9 * abs(math.cos(a)) + 2, 6
                d.polygon([(x - w2, y - h2), (x + w2, y - h2), (x + w2, y + h2), (x - w2, y + h2)],
                          fill=col + (255,))
        elif kind == "burst":
            s = min(1.0, e[1] / 0.3)
            text_center(d, (cx, 160), "嗨！我是關西！", int(40 + 40 * s), ORANGE + (255,), 8, NAVY)
        elif kind == "title":
            d.rounded_rectangle((90, 170, 700, 470), radius=40, fill=(255, 255, 255, 230),
                                outline=ORANGE + (255,), width=8)
            text_center(d, (395, 240), "關西小子舞步", 54, NAVY)
            text_center(d, (395, 330), "〈嗨！我是關西〉", 64, ORANGE + (255,), 4, NAVY)
            text_center(d, (395, 420), "準備好了嗎？跟著一起跳！", 34, BLUE)
        elif kind == "outro":
            d.rounded_rectangle((640, 190, 1200, 470), radius=40, fill=(255, 255, 255, 230),
                                outline=ORANGE + (255,), width=8)
            text_center(d, (920, 270), "跳完囉！", 70, ORANGE + (255,), 4, NAVY)
            text_center(d, (920, 360), "你跳得超棒的！", 46, NAVY)
            text_center(d, (920, 425), "下課也一起動一動吧", 32, BLUE)


def draw_hud(d, beat, seg):
    start, L, section, move, caption, _ = seg
    if not section:
        return
    # 段落標題
    f = font(34)
    l, t, r, b = d.textbbox((0, 0), section, font=f)
    d.rounded_rectangle((24, 20, 24 + r - l + 44, 82), radius=31, fill=ORANGE + (245,))
    d.text((46, 51), section, font=f, fill=WHITE, anchor="lm")
    # 八拍計數
    n = int(beat - DANCE_START) % 8
    frac = (beat - DANCE_START) % 1
    for i in range(8):
        x = 820 + i * 56
        y = 51
        if i == n:
            r = 26 + 6 * max(0, 1 - frac / 0.3)
            d.ellipse((x - r, y - r, x + r, y + r), fill=ORANGE + (255,), outline=WHITE, width=4)
            d.text((x, y), str(i + 1), font=font(34), fill=WHITE, anchor="mm")
        else:
            r = 20
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 220), outline=BLUE + (255,), width=3)
            d.text((x, y), str(i + 1), font=font(24), fill=BLUE, anchor="mm")
    # 口令
    if caption:
        f = font(40)
        l, t, r, b = d.textbbox((0, 0), caption, font=f)
        tw = r - l
        x0 = W / 2 - tw / 2 - 36
        d.rounded_rectangle((x0, 648, W - x0, 708), radius=28, fill=(255, 255, 255, 235),
                            outline=BLUE + (255,), width=4)
        d.text((W / 2, 678), caption, font=f, fill=NAVY, anchor="mm")
        # 本動作進度條
        prog = min(1.0, (beat - start) / L)
        d.rounded_rectangle((x0 + 20, 702, x0 + 20 + (W - 2 * x0 - 40) * prog, 708), radius=3,
                            fill=ORANGE + (255,))


def render_frame(i):
    load_assets()
    t_sec = i / FPS
    beat = t_sec / SPB
    seg = segment_at(beat)
    start, L, section, move, caption, params = seg
    lb = beat - start
    o = pose(move, lb, L, params)
    frame = ASSETS["bg"].copy()
    d0 = ImageDraw.Draw(frame)
    # 舞台光圈隨節拍跳動
    pulse = max(0, 1 - (beat % 1) / 0.4)
    gx = FEET_X + o["x"]
    r = 200 + 20 * pulse
    d0.ellipse((gx - r, FEET_Y - 40, gx + r, FEET_Y + 40), fill=(255, 245, 180) if pulse > 0.5 else (230, 240, 255))

    cx, cy, flip = FEET_X + o["x"], FEET_Y - o["y"], o["flip"]
    if move == "wave_line":
        for k in range(5):
            x = 180 + k * 230
            u = (lb % 4) * 1.4 - k * 0.55
            sub = dict(x=0.0, y=90 * bump(u), ang=-6 * bump(u), sx=1.0, sy=1.0, spin=0.0,
                       flip=False, sil=False, fx=[])
            render_char(frame, sub, x, FEET_Y - 20, "small", 1.0, 0.5)
            if bump(u) > 0.6:
                dd = ImageDraw.Draw(frame)
                draw_sparkle(dd, x - 60, FEET_Y - 20 - sub["y"] - 130, 0.5, False)
    elif not o["hide"]:
        cx, cy, w, h, flip = render_char(frame, o, FEET_X, FEET_Y)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    draw_fx(d, frame, o, cx, cy, flip, t_sec, beat)
    draw_hud(d, beat, seg)
    frame.alpha_composite(ov)
    return frame.convert("RGB").tobytes()


# ---------------------------------------------------------------- 配樂
SR = 44100


def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def make_music():
    n_total = int((TOTAL_SEC + 1.5) * SR)
    out = np.zeros(n_total)
    rng = np.random.default_rng(3)

    def put(sig, t, gain=1.0):
        s = int(t * SR)
        e = min(n_total, s + len(sig))
        if s < n_total:
            out[s:e] += sig[: e - s] * gain

    # 和弦：C G Am F（每小節 4 拍）
    chords = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]
    pent = [60, 62, 64, 67, 69, 72, 74, 76]
    melody_a = [4, 3, 2, 3, 4, 4, 4, -1, 3, 3, 3, -1, 4, 6, 6, -1]
    melody_b = [5, 4, 3, 4, 5, 6, 7, 6, 5, 4, 3, 1, 2, 3, 4, -1]

    def kick():
        n = int(0.25 * SR)
        tt = np.arange(n) / SR
        f = 50 + 90 * np.exp(-tt * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.09)

    def snare():
        n = int(0.18 * SR)
        nz = rng.standard_normal(n)
        nz = nz - np.concatenate([[0], nz[:-1]]) * 0.6
        return nz * env_exp(n, 0.05) * 0.5 + np.sin(2 * np.pi * 190 * np.arange(n) / SR) * env_exp(n, 0.03) * 0.4

    def hat():
        n = int(0.06 * SR)
        nz = rng.standard_normal(n)
        nz = np.diff(np.concatenate([[0], nz]))
        return nz * env_exp(n, 0.012) * 0.25

    def pluck(midi, dur, tau=0.18):
        n = int(dur * SR)
        tt = np.arange(n) / SR
        f = note_freq(midi)
        sig = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt) + 0.1 * np.sin(6 * np.pi * f * tt)
        a = np.minimum(1, tt / 0.005)
        return sig * a * env_exp(n, tau)

    def pad(midis, dur):
        n = int(dur * SR)
        tt = np.arange(n) / SR
        sig = sum(np.sin(2 * np.pi * note_freq(m) * tt) + 0.2 * np.sin(2 * np.pi * note_freq(m) * 2.003 * tt)
                  for m in midis)
        a = np.minimum(1, tt / 0.3) * np.minimum(1, (dur - tt) / 0.3)
        return sig * a / len(midis)

    end_beat = DANCE_END
    for bar in range(int(math.ceil(TOTAL_BEATS / 4))):
        b0 = bar * 4
        t0 = b0 * SPB
        root, tri = chords[bar % 4]
        if b0 >= TOTAL_BEATS:
            break
        if b0 < end_beat:
            put(pad(tri, 4 * SPB), t0, 0.10)
        if DANCE_START <= b0 < end_beat:
            for k in range(4):
                tb = t0 + k * SPB
                put(kick(), tb, 0.9)
                if k % 2 == 1:
                    put(snare(), tb, 0.55)
                put(hat(), tb + SPB / 2, 1.0)
                put(hat(), tb, 0.5)
            for k in range(8):  # 貝斯八分音符
                m = root - 12 if k % 2 == 0 else root
                put(pluck(m, SPB, 0.12), t0 + k * SPB / 2, 0.35)
            mel = melody_a if (bar // 2) % 2 == 0 else melody_b
            half = (bar % 2) * 8
            for k in range(8):  # 主旋律
                idx = mel[half + k]
                if idx >= 0:
                    put(pluck(pent[idx] + 12, SPB, 0.22), t0 + k * SPB / 2, 0.16)
        elif b0 < DANCE_START:  # 片頭
            for k in range(4):
                put(hat(), t0 + k * SPB, 0.8)
                put(pluck(pent[[0, 2, 4, 5][k]] + 12, SPB, 0.3), t0 + k * SPB, 0.18)

    # 音效
    for start, L, section, move, caption, params in SEGMENTS:
        t0 = start * SPB
        if move == "reveal":
            put(pluck(84, 0.6, 0.25), t0 + 0.7 * SPB, 0.3)
            put(pluck(91, 0.6, 0.25), t0 + 0.8 * SPB, 0.25)
        if move == "swing":
            n = int(0.35 * SR)
            nz = rng.standard_normal(n) * np.sin(np.linspace(0, np.pi, n)) * 0.35
            put(nz, t0, 1.0)
            put(pluck(96, 0.3, 0.05), t0 + 0.25 * SPB, 0.4)
        if move == "clap2":
            for k in range(2):
                put(snare(), t0 + k * SPB, 0.6)
        if move == "jacks":
            for k in range(4):
                put(snare(), t0 + (2 * k + 1.9) * SPB, 0.45)
        if move == "freeze":
            n = int(1.2 * SR)
            nz = np.diff(np.concatenate([[0], rng.standard_normal(n)])) * env_exp(n, 0.4) * 0.3
            put(nz, t0, 1.0)
        if move == "outro":
            put(pad([48, 60, 64, 67, 72], L * SPB), t0, 0.2)
            for k, m in enumerate([72, 76, 79, 84]):
                put(pluck(m, 1.5, 0.5), t0 + k * 0.12, 0.2)

    out = out[: int(TOTAL_SEC * SR)]
    fade = int(1.0 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / (np.max(np.abs(out)) + 1e-9) * 0.85
    pcm = (out * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(WAV_PATH, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo.tobytes())


def main():
    print(f"總長 {TOTAL_SEC:.1f} 秒、{N_FRAMES} 格")
    make_music()
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", WAV_PATH,
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT_PATH]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, data in enumerate(pool.imap(render_frame, range(N_FRAMES), chunksize=8)):
            proc.stdin.write(data)
            if k % 300 == 0:
                print(f"  {k}/{N_FRAMES}")
    proc.stdin.close()
    proc.wait()
    os.remove(WAV_PATH)
    print("完成：", OUT_PATH)


if __name__ == "__main__":
    main()
