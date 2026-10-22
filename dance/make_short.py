"""關西小子直式短片：把 DeeVid AI 生成的跳舞片段去黑底、放上舞台

用法：python3 dance/make_short.py
輸入：dance/deevid-clip.mp4（黑底角色跳舞片段）
輸出：dance/kuanxi-short.mp4（1080x1920、24fps、配樂）
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from make_video import (BLUE, NAVY, ORANGE, WHITE, YELLOW, font, heart_poly, star_poly,
                        text_center)

HERE = os.path.dirname(os.path.abspath(__file__))
CLIP_PATH = os.path.join(HERE, "deevid-clip.mp4")
OUT_PATH = os.path.join(HERE, "kuanxi-short.mp4")
WAV_PATH = os.path.join(HERE, "_short.wav")
PHOTO_PATH = os.path.join(HERE, "bg-photo.jpg")  # 有這張照片就當背景，沒有就用畫的舞台
PHOTO_FOCUS_X = 0.38  # 直式裁切時保留照片的水平位置（0 左 ~ 1 右）

W, H = 1080, 1920
FPS = 24
BPM = 120
SPB = 60 / BPM
CHAR_W = 1100  # 片段縮放後寬度
CLIP_TOP = 240  # 片段上緣（藏在標題框後面，遮住原片切到的帽頂）
FLOOR_Y = CLIP_TOP + int(CHAR_W * 864 / 768) - 40  # 角色腳底位置
SKIP = 2  # 原片前兩格破圖
INTRO = 1.5  # 片頭秒數
OUTRO = 3.0  # 片尾定格秒數

# 片段中動作的時間點（秒），用來切換字幕
MOVES = [(0.0, "揮揮手 打招呼"), (1.2, "左右搖擺 跟著節拍"), (3.2, "張開雙手 好開心"),
         (3.9, "雙手扠腰 帥氣定格")]


# ---------------------------------------------------------------- 讀取與去背
def load_clip():
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", CLIP_PATH],
                           capture_output=True, text=True, check=True).stdout.strip()
    cw, ch = map(int, probe.split(","))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", CLIP_PATH, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (cw * ch * 3)
    arr = np.frombuffer(raw, np.uint8).reshape(n, ch, cw, 3)
    scale = CHAR_W / cw
    size = (CHAR_W, int(ch * scale))
    frames = []
    for f in arr[SKIP:]:
        frames.append(key_black(Image.fromarray(f)).resize(size, Image.LANCZOS))
    return frames


def key_black(img, thresh=10):
    """從畫面邊緣往內填滿黑底；先做中值濾波壓掉壓縮雜點，避免把角色的黑髮也去掉"""
    m = Image.fromarray(np.asarray(img).max(axis=2).astype(np.uint8), "L").filter(ImageFilter.MedianFilter(5))
    w, h = m.size
    seeds = [(x, y) for x in range(0, w, 24) for y in (0, h - 1)] + \
            [(x, y) for y in range(0, h, 24) for x in (0, w - 1)]
    for seed in seeds:
        v = m.getpixel(seed)
        if v != 255 and v <= thresh:
            ImageDraw.floodfill(m, seed, 255, thresh=thresh)
    bg = (np.asarray(m) == 255) & (np.asarray(img).max(axis=2) < 200)
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8), "L")
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.5))
    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out


# ---------------------------------------------------------------- 背景
def make_photo_bg():
    """照片等比放大填滿直式畫面，依 PHOTO_FOCUS_X 裁切；略微柔焦讓角色更突出"""
    ph = Image.open(PHOTO_PATH).convert("RGB")
    k = max(W / ph.width, H / ph.height)
    ph = ph.resize((int(ph.width * k + 0.5), int(ph.height * k + 0.5)), Image.LANCZOS)
    x0 = int(min(max(ph.width * PHOTO_FOCUS_X - W / 2, 0), ph.width - W))
    y0 = (ph.height - H) // 2
    bg = ph.crop((x0, y0, x0 + W, y0 + H)).filter(ImageFilter.GaussianBlur(2)).convert("RGBA")
    # 上下加淡淡的白色漸層，讓標題與字幕更清楚
    g = np.zeros((H, 1), np.float32)
    g[:420, 0] = np.linspace(0.45, 0, 420)
    g[H - 380:, 0] = np.linspace(0, 0.5, 380)
    a = (np.repeat(g, W, axis=1) * 255).astype(np.uint8)
    veil = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    veil.putalpha(Image.fromarray(a, "L"))
    bg.alpha_composite(veil)
    return bg


def make_bg():
    if os.path.exists(PHOTO_PATH):
        return make_photo_bg()
    top, bot = np.array([150, 215, 255]), np.array([255, 244, 214])
    g = np.linspace(0, 1, H)[:, None]
    arr = (top * (1 - g) + bot * g).astype(np.uint8)
    bg = Image.fromarray(np.repeat(arr[:, None, :], W, axis=1), "RGB").convert("RGBA")
    d = ImageDraw.Draw(bg)
    rnd = random.Random(5)
    for _ in range(12):
        x, y, r = rnd.randint(0, W), rnd.randint(350, 1300), rnd.randint(40, 110)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 35))
    bg = bg.filter(ImageFilter.GaussianBlur(8))
    d = ImageDraw.Draw(bg)
    d.rectangle((0, 1440, W, H), fill=(110, 170, 240))
    for i in range(-400, W + 400, 90):
        d.line((W / 2 + (i - W / 2) * 0.35, 1440, i, H), fill=(95, 155, 230), width=4)
    d.rectangle((0, 1434, W, 1446), fill=(255, 160, 60))
    return bg


CONFETTI = [(random.Random(i).uniform(0, W), random.Random(i * 7).uniform(0, H),
             random.Random(i * 13).uniform(150, 320),
             random.Random(i * 17).choice([ORANGE, BLUE, YELLOW, (255, 90, 120), (80, 200, 120)]),
             random.Random(i * 19).uniform(0, 6.28)) for i in range(110)]


def draw_confetti(d, t):
    for x0, y0, sp, col, ph in CONFETTI:
        y = (y0 + sp * t) % (H + 40) - 20
        x = x0 + 25 * math.sin(t * 2 + ph)
        w2 = 12 * abs(math.cos(ph + t * 3)) + 3
        d.rectangle((x - w2, y - 8, x + w2, y + 8), fill=col + (255,))


# ---------------------------------------------------------------- 畫面
def timeline(n_src):
    """片頭定格 → 正放 → 倒放 → 正放 → 片尾定格（倒放讓接點自然）"""
    seq = []
    seq += [("intro", 0)] * int(INTRO * FPS)
    fwd = list(range(n_src))
    for k, order in enumerate([fwd, fwd[::-1][1:], fwd[1:]]):
        seq += [("dance", i) for i in order]
    seq += [("outro", n_src - 1)] * int(OUTRO * FPS)
    return seq


def render(bg, clip, kind, src_i, t, t_kind):
    frame = bg.copy()
    d0 = ImageDraw.Draw(frame)
    beat = t / SPB
    pulse = max(0, 1 - (beat % 1) / 0.4) if kind == "dance" else 0
    if not os.path.exists(PHOTO_PATH):
        r = 380 + 30 * pulse
        d0.ellipse((W / 2 - r, FLOOR_Y - 70, W / 2 + r, FLOOR_Y + 60),
                   fill=(255, 245, 180) if pulse > 0.5 else (235, 242, 255))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((W / 2 - 260, FLOOR_Y - 40, W / 2 + 260, FLOOR_Y + 30), fill=(20, 40, 90, 110))
    frame.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))

    ch = clip[src_i]
    scale = 1.0
    if kind == "intro":  # 彈跳登場
        u = min(1.0, t_kind / 0.6)
        scale = 0.3 + 0.7 * u + 0.08 * math.sin(math.pi * u)
    if scale != 1.0:
        ch = ch.resize((int(ch.width * scale), int(ch.height * scale)), Image.BILINEAR)
    if scale == 1.0:
        frame.alpha_composite(ch, (int(W / 2 - ch.width / 2), CLIP_TOP)) if ch.width <= W else frame.paste(ch, (int(W / 2 - ch.width / 2), CLIP_TOP), ch)
    else:
        frame.paste(ch, (int(W / 2 - ch.width / 2), int(CLIP_TOP + (1 - scale) * clip[src_i].height)), ch)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    # 標題
    bob = 6 * math.sin(t * 4)
    d.rounded_rectangle((90, 70 + bob, W - 90, 330 + bob), radius=50, fill=(255, 255, 255, 235),
                        outline=ORANGE + (255,), width=10)
    text_center(d, (W / 2, 150 + bob), "關西小子 動起來！", 78, NAVY)
    text_center(d, (W / 2, 255 + bob), "〈嗨！我是關西〉", 70, ORANGE + (255,), 5, NAVY)
    # 星星點綴
    for k in range(6):
        a = t * 1.2 + k * math.pi / 3
        x, y = W / 2 + 470 * math.cos(a), 760 + 330 * math.sin(a)
        d.polygon(star_poly(x, y, 22, 9, 5, t * 2 + k), fill=YELLOW + (220,))

    if kind == "dance":
        # 依片段時間點換字幕（倒放時用相同時間點）
        clip_t = (src_i + SKIP) / FPS
        cap = MOVES[0][1]
        for st, txt in MOVES:
            if clip_t >= st:
                cap = txt
        f = font(64)
        l, tp, rr, b = d.textbbox((0, 0), cap, font=f)
        x0 = W / 2 - (rr - l) / 2 - 50
        d.rounded_rectangle((x0, 1640, W - x0, 1750), radius=55, fill=(255, 255, 255, 240),
                            outline=BLUE + (255,), width=6)
        d.text((W / 2, 1695), cap, font=f, fill=NAVY, anchor="mm")
        # 八拍燈
        n = int(beat) % 8
        for i in range(8):
            x, y = W / 2 + (i - 3.5) * 105, 1830
            rad = 40 if i == n else 30
            if i == n:
                d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=ORANGE + (255,), outline=WHITE, width=5)
                d.text((x, y), str(i + 1), font=font(48), fill=WHITE, anchor="mm")
            else:
                d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=(255, 255, 255, 225),
                          outline=BLUE + (255,), width=4)
                d.text((x, y), str(i + 1), font=font(34), fill=BLUE, anchor="mm")
    elif kind == "intro":
        a = int(255 * min(1, t_kind / 0.5))
        text_center(d, (W / 2, 1720), "準備好了嗎？", 80, ORANGE + (a,), 6, NAVY)
    else:
        draw_confetti(d, t_kind)
        s = min(1.0, t_kind / 0.35)
        d.polygon(heart_poly(W / 2 + 330, 560, 150 * s), fill=(255, 80, 120, 235))
        text_center(d, (W / 2, 1680), "一起動起來！", int(60 + 40 * s), ORANGE + (255,), 8, NAVY)
        text_center(d, (W / 2, 1810), "下課也來跳一跳", 54, NAVY)
    d.text((W - 24, H - 18), "角色動畫：DeeVid AI 生成", font=font(26), fill=(255, 255, 255, 230), anchor="rd",
           stroke_width=2, stroke_fill=(40, 60, 100, 200))
    frame.alpha_composite(ov)
    return frame.convert("RGB").tobytes()


# ---------------------------------------------------------------- 配樂
SR = 44100


def make_music(total):
    n_total = int(total * SR)
    out = np.zeros(n_total)
    rng = np.random.default_rng(1)

    def put(sig, t, g=1.0):
        s = int(t * SR)
        e = min(n_total, s + len(sig))
        if s < n_total:
            out[s:e] += sig[: e - s] * g

    def env(n, tau):
        return np.exp(-np.arange(n) / (tau * SR))

    def tone(midi, dur, tau):
        n = int(dur * SR)
        tt = np.arange(n) / SR
        f = 440 * 2 ** ((midi - 69) / 12)
        return (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.minimum(1, tt / 0.005) * env(n, tau)

    def kick():
        n = int(0.25 * SR)
        tt = np.arange(n) / SR
        return np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-tt * 30)) / SR) * env(n, 0.09)

    def noise(dur, tau, hp=False):
        n = int(dur * SR)
        z = rng.standard_normal(n)
        if hp:
            z = np.diff(np.concatenate([[0], z]))
        return z * env(n, tau)

    chords = [(48, 60), (43, 59), (45, 60), (41, 60)]
    mel = [64, 67, 69, 67, 72, 69, 67, -1, 64, 62, 64, 67, 69, 67, 64, -1]
    dance_end = total - OUTRO
    for bar in range(int(total / (4 * SPB)) + 1):
        t0 = bar * 4 * SPB
        root, _ = chords[bar % 4]
        for k in range(4):
            tb = t0 + k * SPB
            if INTRO - 0.01 <= tb < dance_end:
                put(kick(), tb, 0.9)
                if k % 2:
                    put(noise(0.18, 0.05), tb, 0.3)
                put(noise(0.06, 0.012, True), tb + SPB / 2, 0.25)
            elif tb < INTRO:
                put(noise(0.06, 0.012, True), tb, 0.3)
        for k in range(8):
            tb = t0 + k * SPB / 2
            if INTRO <= tb < dance_end:
                put(tone(root - 12 if k % 2 == 0 else root, SPB, 0.12), tb, 0.35)
                m = mel[(bar % 2) * 8 + k]
                if m > 0:
                    put(tone(m + 12, SPB, 0.22), tb, 0.15)
    for k, m in enumerate([72, 76, 79, 84]):
        put(tone(m, 2.0, 0.6), dance_end + k * 0.12, 0.2)
    put(noise(1.5, 0.45, True), dance_end, 0.25)
    fade = int(0.8 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / (np.abs(out).max() + 1e-9) * 0.85
    pcm = (out * 32767).astype(np.int16)
    with wave.open(WAV_PATH, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())


def main():
    clip = load_clip()
    seq = timeline(len(clip))
    total = len(seq) / FPS
    print(f"來源 {len(clip)} 格，輸出 {len(seq)} 格（{total:.1f} 秒）")
    make_music(total)
    bg = make_bg()
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", WAV_PATH,
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT_PATH]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    kind_start = {}
    for i, (kind, src_i) in enumerate(seq):
        kind_start.setdefault(kind, i)
        t = i / FPS
        proc.stdin.write(render(bg, clip, kind, src_i, t, (i - kind_start[kind]) / FPS))
    proc.stdin.close()
    proc.wait()
    os.remove(WAV_PATH)
    print("完成：", OUT_PATH)


if __name__ == "__main__":
    main()
