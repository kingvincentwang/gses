"""產生配音（Kokoro 離線 TTS）、配樂與音效，輸出 build/audio.wav 與 build/timeline.json。

用法：KOKORO_DIR=/path/to/kokoro-multi-lang-v1_0 python3 make_audio.py
"""
import json
import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from scipy.signal import lfilter

from story import BEATS, FPS, SR, VOICES, WHISPERS

KDIR = os.environ.get('KOKORO_DIR', 'models/kokoro-multi-lang-v1_0').rstrip('/') + '/'
BUILD = 'build'
rng = np.random.default_rng(7)


def make_tts():
    import sherpa_onnx
    d = KDIR
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=d + 'model.onnx', voices=d + 'voices.bin', tokens=d + 'tokens.txt',
                data_dir=d + 'espeak-ng-data', dict_dir=d + 'dict',
                lexicon=d + 'lexicon-us-en.txt,' + d + 'lexicon-zh.txt'),
            num_threads=8),
        rule_fsts=d + 'phone-zh.fst,' + d + 'date-zh.fst,' + d + 'number-zh.fst')
    return sherpa_onnx.OfflineTts(cfg)


def pitch_shift(x, semitone):
    if not semitone:
        return x
    with tempfile.TemporaryDirectory() as td:
        a, b = os.path.join(td, 'a.wav'), os.path.join(td, 'b.wav')
        sf.write(a, x, SR)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', a, '-af',
                        f'rubberband=pitch={2 ** (semitone / 12):.5f}:formant=preserved', b], check=True)
        y, _ = sf.read(b, dtype='float32')
    return y


def trim(x, th=0.01):
    idx = np.where(np.abs(x) > th)[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - int(0.03 * SR)): idx[-1] + int(0.08 * SR)]


def speak(tts, who, text, scale=1.0):
    v = VOICES[who]
    a = tts.generate(text, sid=v['sid'], speed=v['speed'] * scale)
    x = np.asarray(a.samples, dtype=np.float32)
    x = trim(pitch_shift(x, v['semitone']))
    return x / (np.abs(x).max() + 1e-6) * 0.8 * v['gain']


def envelope(x):
    """每格畫面的嘴巴張合程度 0..1。"""
    hop = SR // FPS
    n = int(np.ceil(len(x) / hop))
    rms = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    ref = np.percentile(rms, 90) + 1e-6
    e = np.clip((rms / ref - 0.12) / 0.88, 0, 1) ** 0.8
    out, cur = np.zeros_like(e), 0.0
    for i, v in enumerate(e):  # 快速張口、稍慢閉口
        cur = v if v > cur else cur * 0.45 + v * 0.55
        out[i] = cur
    return [round(float(v), 3) for v in out]


# ---------- 合成音效 ----------
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def pluck(freq, dur=2.5, bright=0.5):
    """Karplus-Strong 撥弦（古箏感）。"""
    n = int(dur * SR)
    p = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, p)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        k = i % p
        out[i] = buf[k]
        buf[k] = 0.998 * ((1 - bright) * buf[k] + bright * buf[(i + 1) % p])
    return out * np.exp(-t_axis(dur) * 1.2)


def gong(dur=6.0, f0=110.0):
    t = t_axis(dur)
    x = np.zeros_like(t)
    for k, (r, a, d) in enumerate([(1, 1, .5), (1.47, .6, .7), (2.09, .5, .9), (2.56, .35, 1.2), (3.18, .3, 1.5), (4.1, .2, 2)]):
        x += a * np.sin(2 * np.pi * f0 * r * t * (1 + 0.004 * np.exp(-t))) * np.exp(-t * d)
    x += 0.3 * rng.standard_normal(len(t)) * np.exp(-t * 25)
    return (x / np.abs(x).max()).astype(np.float32)


def drum(dur=0.8, f=55):
    t = t_axis(dur)
    x = np.sin(2 * np.pi * f * t * (1 + 1.5 * np.exp(-t * 30))) * np.exp(-t * 7)
    x += 0.2 * rng.standard_normal(len(t)) * np.exp(-t * 40)
    return x.astype(np.float32)


def lowpass(x, a):
    return lfilter([a], [1, a - 1], x).astype(np.float32)


def swoosh(dur=1.2):
    t = t_axis(dur)
    n = rng.standard_normal(len(t)).astype(np.float32)
    env = np.sin(np.pi * t / dur) ** 2
    hi = n - lowpass(n, 0.05)
    return (lowpass(hi, 0.35) * env * 0.8).astype(np.float32)


def roar(dur=3.2):
    t = t_axis(dur)
    f = 70 + 30 * np.sin(2 * np.pi * 0.7 * t) + 15 * rng.standard_normal(len(t)).cumsum() / np.sqrt(len(t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    saw = 2 * ((ph / (2 * np.pi)) % 1) - 1
    growl = saw * (0.6 + 0.4 * np.sin(2 * np.pi * 28 * t))
    noise = lowpass(rng.standard_normal(len(t)).astype(np.float32), 0.12)
    env = np.minimum(1, t / 0.25) * np.exp(-np.maximum(0, t - 1.6) * 1.6)
    x = lowpass((growl * 0.7 + noise * 1.4).astype(np.float32), 0.18) * env
    return (x / np.abs(x).max()).astype(np.float32)


def whisperize(x):
    """隨機相位 STFT：保留音色包絡、去掉聲帶振動，聽起來像耳語。"""
    n, hop = 512, 128
    win = np.hanning(n)
    out = np.zeros(len(x) + n)
    for i in range(0, len(x) - n, hop):
        spec = np.fft.rfft(x[i:i + n] * win)
        ph = np.exp(1j * rng.uniform(0, 2 * np.pi, len(spec)))
        out[i:i + n] += np.fft.irfft(np.abs(spec) * ph) * win
    out = out - lowpass(out.astype(np.float32), 0.04)
    return (out / (np.abs(out).max() + 1e-6)).astype(np.float32)


def add(buf, x, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[0]:
        return
    x = x[: buf.shape[0] - i]
    buf[i:i + len(x), 0] += x * gain * (1 - max(0, pan))
    buf[i:i + len(x), 1] += x * gain * (1 + min(0, pan))


def main():
    os.makedirs(BUILD, exist_ok=True)
    tts = make_tts()
    beats, t = [], 0.0
    clips = []
    for shot, who, text, pre, post in BEATS:
        start = t + pre
        if who is None:
            dur, env, x = float(text), [], None
        else:
            x = speak(tts, who, text)
            dur, env = len(x) / SR, envelope(x)
        beats.append(dict(shot=shot, who=who, text=text if who else '', start=round(start, 3),
                          end=round(start + dur, 3), env=env))
        clips.append(x)
        t = start + dur + post
    total = t + 0.5
    print('總長度 %.1f 秒' % total)

    voice = np.zeros((int(total * SR), 2), np.float32)
    for b, x in zip(beats, clips):
        if x is not None:
            add(voice, x, b['start'])

    sfx = np.zeros_like(voice)
    music = np.zeros_like(voice)
    shot_t = {}
    for b in beats:
        shot_t.setdefault(b['shot'], (b['start'], b['end']))
        shot_t[b['shot']] = (shot_t[b['shot']][0], b['end'])

    add(sfx, gong(5, 98), 0.2, 0.35)
    # 配樂：D 小調五聲音階的撥弦
    scale = [146.8, 174.6, 196.0, 220.0, 261.6, 293.7, 349.2, 392.0]
    s3 = shot_t['s3'][0] - 1.4
    s6 = shot_t['s5k'][0]
    s7w0, s7w1 = shot_t['s7w']
    tt = 0.5
    while tt < total - 3:
        calm = tt < s3 or (s6 <= tt < s7w0) or tt > s7w1
        if calm:
            f = scale[rng.integers(0, len(scale))]
            add(music, pluck(f, 2.5, 0.5), tt, 0.22, rng.uniform(-0.4, 0.4))
            if rng.random() < 0.3:
                add(music, pluck(f * 1.5, 2.0), tt + 0.15, 0.12, rng.uniform(-0.4, 0.4))
            tt += rng.choice([0.6, 0.9, 1.2])
        else:
            tt += 0.5
    # 幻想段：漸快的心跳鼓聲與低音持續音
    s5t0 = shot_t['s5t'][0]
    tt, gap = s3 + 0.3, 1.0
    while tt < s5t0:
        add(music, drum(), tt, 0.45)
        add(music, drum(0.5, 60), tt + 0.22, 0.3)
        gap = max(0.45, gap * 0.96)
        tt += gap
    dt = t_axis(s5t0 - s3)
    drone = (np.sin(2 * np.pi * 73.4 * dt) + 0.5 * np.sin(2 * np.pi * 77.8 * dt)) * np.minimum(1, dt / 3) * 0.12
    add(music, drone.astype(np.float32), s3)
    add(sfx, swoosh(1.4), s3 - 1.3, 0.6)                      # 進入水墨幻想
    add(sfx, roar(3.4), s5t0 + 0.6, 0.9)                      # 墨虎咆哮
    add(sfx, drum(1.2, 45), s5t0 + 0.6, 0.8)
    add(sfx, swoosh(1.0), s6 - 0.6, 0.5)                      # 回到現實
    # 竊竊私語段
    dt = t_axis(s7w1 - s7w0 + 1)
    trem = (np.sin(2 * np.pi * 116.5 * dt) + np.sin(2 * np.pi * 123.5 * dt)) * (0.5 + 0.5 * np.sin(2 * np.pi * 5 * dt))
    add(music, (trem * np.minimum(1, dt / 2) * 0.06).astype(np.float32), s7w0)
    wt = s7w0 + 0.3
    for i in range(3):
        for j, (who, text) in enumerate(WHISPERS):
            w = whisperize(speak(tts, who, text, 1.15))
            add(sfx, w, wt + i * 2.2 + j * 0.6, 0.22 + 0.08 * i, [-0.7, 0.6, -0.3, 0.8][j])
    # 結尾銅鑼
    add(sfx, gong(6, 130), beats[-1]['end'] + 0.4, 0.7)

    # 人聲出現時壓低配樂（ducking）
    hop = SR // 50
    act = np.abs(voice[:, 0])
    lvl = np.array([act[i:i + hop].max() for i in range(0, len(act), hop)])
    duck = np.repeat(np.where(lvl > 0.02, 0.45, 1.0), hop)[: len(act)]
    duck = lowpass(duck.astype(np.float32), 0.0005)
    mix = voice + sfx + music * duck[:, None]
    fade = np.ones(len(mix), np.float32)
    fade[-int(2 * SR):] = np.linspace(1, 0, int(2 * SR))
    mix *= fade[:, None]
    mix = mix / (np.abs(mix).max() + 1e-6) * 0.95
    sf.write(os.path.join(BUILD, 'audio.wav'), mix, SR)
    with open(os.path.join(BUILD, 'timeline.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(total=total, beats=beats), f, ensure_ascii=False)


if __name__ == '__main__':
    main()
