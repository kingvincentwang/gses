#!/usr/bin/env python3
"""讀取 audio/ 內的旁白音檔，產生 clips.js（長度＋嘴型音量包絡）、qr.svg、bgm.wav。

用法：python3 build.py
"""
import json
import os
import subprocess
import wave

import numpy as np
import qrcode
import qrcode.image.svg

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "audio")
FORM_URL = "https://forms.gle/TeuMPAQrugKdW4s57"
ENV_HZ = 20
SR = 22050


def decode(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def clips():
    out = {}
    for name in sorted(os.listdir(AUDIO)):
        if not name.endswith((".mp3", ".wav")):
            continue
        cid = os.path.splitext(name)[0]
        pcm = decode(os.path.join(AUDIO, name))
        hop = SR // ENV_HZ
        n = len(pcm) // hop
        rms = np.sqrt(np.mean(pcm[: n * hop].reshape(n, hop) ** 2, axis=1))
        peak = np.percentile(rms, 95) or 1
        env = np.clip(rms / peak, 0, 1)
        out[cid] = {"file": "audio/" + name, "dur": round(len(pcm) / SR, 3),
                    "env": [round(float(v), 2) for v in env]}
    with open(os.path.join(HERE, "clips.js"), "w", encoding="utf-8") as f:
        f.write("// 由 build.py 自動產生，請勿手動修改\n")
        f.write(f"window.CLIP_ENV_HZ={ENV_HZ};\nwindow.CLIPS=")
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    return out


def qr():
    img = qrcode.make(FORM_URL, image_factory=qrcode.image.svg.SvgPathImage, border=1)
    img.save(os.path.join(HERE, "qr.svg"))


def bgm(seconds=48):
    """輕快的八音盒風格背景音樂（C-G-Am-F 循環），可無縫重複播放。"""
    sr = 44100
    bpm = 112
    beat = 60 / bpm
    t_total = int(seconds / (beat * 16)) * beat * 16
    out = np.zeros(int(sr * t_total) + sr)
    freq = lambda m: 440 * 2 ** ((m - 69) / 12)

    def note(start, midi, length, vol, bright=3):
        n = int(length * sr)
        t = np.arange(n) / sr
        f = freq(midi)
        tone = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.6 for k in range(1, bright + 1))
        env = np.exp(-t * 4.5) * np.minimum(1, t * 200)
        s = int(start * sr)
        out[s:s + n] += tone * env * vol

    chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
    melody = [72, 76, 79, 76, 74, 71, 74, 79, 72, 76, 81, 79, 77, 76, 74, 72]
    bar = beat * 4
    for b in range(int(t_total / bar)):
        ch = chords[b % 4]
        t0 = b * bar
        note(t0, ch[0] - 12, bar, 0.22, 2)
        for i in range(8):
            note(t0 + i * beat / 2, ch[[0, 1, 2, 1][i % 4]], beat, 0.10)
        for i in range(4):
            m = melody[(b % 4) * 4 + i]
            note(t0 + i * beat, m, beat * 1.5, 0.08, 4)
    fade = int(0.02 * sr)
    out = out[: int(sr * t_total)]
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / np.max(np.abs(out)) * 0.6
    with wave.open(os.path.join(HERE, "bgm.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(HERE, "bgm.wav"),
                    "-b:a", "96k", os.path.join(HERE, "bgm.mp3")], check=True)
    os.remove(os.path.join(HERE, "bgm.wav"))


if __name__ == "__main__":
    c = clips()
    print(f"{len(c)} 個音檔：", ", ".join(f"{k}={v['dur']}s" for k, v in c.items()))
    qr()
    bgm()
    print("已產生 clips.js、qr.svg、bgm.mp3")
