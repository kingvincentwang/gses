"""產生《望梅止渴》動畫的旁白、角色配音、音效與配樂，並輸出時間軸與嘴形資料。
需要：sherpa-onnx、opencc-python-reimplemented、numpy、soundfile、ffmpeg
用法：python3 build_audio.py <vits-melo-tts-zh_en 模型目錄>
"""
import json, os, subprocess, sys, tempfile
import numpy as np, soundfile as sf, opencc, sherpa_onnx

SR = 44100
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'assets')
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'vits-melo-tts-zh_en'
rng = np.random.default_rng(7)
t2s = opencc.OpenCC('t2s')

# ---------- 語音 ----------
d = MODEL.rstrip('/') + '/'
tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
    model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=d + 'model.onnx', lexicon=d + 'lexicon.txt',
                                                    tokens=d + 'tokens.txt', dict_dir=d + 'dict'),
        num_threads=4),
    rule_fsts=f'{d}date.fst,{d}phone.fst,{d}number.fst'))

def ffmpeg_filter(x, sr, af):
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, 'a.wav'), os.path.join(tmp, 'b.wav')
        sf.write(a, x, sr)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a, '-af', af, '-ar', str(SR), '-ac', '1', b], check=True)
        y, _ = sf.read(b)
    return y.astype(np.float32)

def say(text, speed=1.0, pitch=1.0, extra=''):
    a = tts.generate(t2s.convert(text), sid=0, speed=speed)
    x = np.array(a.samples, dtype=np.float32)
    af = f'asetrate={int(a.sample_rate * pitch)},aresample={SR},atempo={1 / pitch:.4f}'
    if extra:
        af += ',' + extra
    y = ffmpeg_filter(x, a.sample_rate, af)
    # 去掉頭尾靜音
    idx = np.where(np.abs(y) > 0.01)[0]
    y = y[max(0, idx[0] - 800): idx[-1] + 2000]
    return y / (np.abs(y).max() + 1e-9) * 0.85

def envelope(y):
    """每格 (1/30 秒) 的嘴巴張開程度 0~1。"""
    hop = SR // FPS
    n = int(np.ceil(len(y) / hop))
    e = np.array([np.sqrt(np.mean(y[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    e = np.clip((e / (np.percentile(e, 95) + 1e-9)), 0, 1)
    e[e < 0.12] = 0
    out = np.zeros_like(e); v = 0
    for i, x in enumerate(e):  # 開口快、閉口慢
        v = x if x > v else v * 0.55 + x * 0.45
        out[i] = v
    return [round(float(x), 2) for x in out]

# ---------- 合成音效 ----------
def t_(dur): return np.arange(int(dur * SR)) / SR
def adsr(n, a=0.01, r=0.1):
    e = np.ones(n); A = int(a * SR); R = int(r * SR)
    if A: e[:A] = np.linspace(0, 1, A)
    if R: e[-R:] *= np.linspace(1, 0, R)
    return e
def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode='same')
def noise(dur): return rng.standard_normal(int(dur * SR)).astype(np.float32)

def cicada(dur):
    t = t_(dur); x = noise(dur) - lowpass(noise(dur), 3)
    x = np.sin(2 * np.pi * 5200 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 42 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t))
    return (x + 0.15 * (noise(dur) - lowpass(noise(dur), 4))) * 0.06 * adsr(len(t), 0.5, 0.5)

def heat_hum(dur):
    t = t_(dur)
    return (np.sin(2 * np.pi * 70 * t) + 0.5 * np.sin(2 * np.pi * 105 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t)) * 0.05 * adsr(len(t), 0.8, 0.8)

def wind(dur, amp=0.25):
    n = noise(dur); x = lowpass(n, 40) - lowpass(n, 200)
    t = t_(dur)
    return x / np.abs(x).max() * amp * (0.5 + 0.5 * np.sin(2 * np.pi * 0.6 * t + 1)) * adsr(len(t), 0.4, 0.6)

def ding(f=1760, dur=1.2, amp=0.35):
    t = t_(dur)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t)) * np.exp(-t * 4) * amp

def drip():
    t = t_(0.35); f = 900 + 1400 * t / 0.35
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * 0.4

def clunk():  # 空水壺
    t = t_(0.5)
    return (np.sin(2 * np.pi * 180 * t) + 0.6 * np.sin(2 * np.pi * 410 * t)) * np.exp(-t * 12) * 0.4

def footstep(amp=0.3):
    t = t_(0.18)
    return lowpass(noise(0.18), 12) * np.exp(-t * 30) * amp * 3

def gulp(amp=0.7):
    t = t_(0.45); f = 260 - 180 * (t / 0.45)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.45) ** 0.5
    return x * amp

def whip():
    t = t_(0.25)
    return (noise(0.25) - lowpass(noise(0.25), 3)) * np.exp(-t * 25) * 0.7

def neigh():
    t = t_(1.3)
    f0 = 520 + 250 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 1.5) + 200 * np.exp(-t * 3)
    ph = 2 * np.cumsum(np.pi * f0) / SR
    x = sum(np.sin(k * ph) / k for k in range(1, 7))
    return x * adsr(len(t), 0.05, 0.6) * 0.18

def splash():
    t = t_(0.5); n = noise(0.5)
    return (n - lowpass(n, 6)) * np.exp(-t * 9) * 0.5 + np.sin(2 * np.pi * np.cumsum(400 + 1600 * t) / SR) * np.exp(-t * 10) * 0.2

def bite():
    t = t_(0.15)
    return (noise(0.15) - lowpass(noise(0.15), 2)) * np.exp(-t * 40) * 0.7

def crowd(dur, amp=0.25):  # 歡呼背景
    x = np.zeros(int(dur * SR))
    for _ in range(14):
        f = rng.uniform(180, 420); t = t_(dur)
        ph = 2 * np.pi * np.cumsum(f * (1 + 0.06 * np.sin(2 * np.pi * rng.uniform(3, 7) * t))) / SR
        v = sum(np.sin(k * ph) / k for k in range(1, 5))
        x += v * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(0.5, 2) * t + rng.uniform(0, 6)))
    n = noise(dur); x = x / np.abs(x).max() * 0.6 + (lowpass(n, 3) - lowpass(n, 30)) * 0.4
    return x * amp * adsr(len(x), 0.3, 0.5)

def pluck(f, dur=1.2, amp=0.3, bright=0.5):  # Karplus-Strong 古箏音色
    N = int(SR / f); buf = rng.uniform(-1, 1, N)
    out = np.zeros(int(dur * SR)); b = bright
    for i in range(len(out)):
        out[i] = buf[i % N]
        buf[i % N] = 0.996 * (b * buf[i % N] + (1 - b) * buf[(i + 1) % N])
    return out * amp

def drum(f=70, amp=0.8, dur=0.6):
    t = t_(dur); ff = f * (1 + 1.5 * np.exp(-t * 30))
    return np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t * 6) * amp + lowpass(noise(dur), 3) * np.exp(-t * 40) * amp * 0.3

def pad(freqs, dur, amp=0.08):
    t = t_(dur); x = np.zeros_like(t)
    for f in freqs:
        for det in (-0.6, 0.6):
            x += np.sin(2 * np.pi * (f + det) * t) + 0.3 * np.sin(2 * np.pi * 2 * (f + det) * t)
    return x / len(freqs) * amp * adsr(len(t), 1.2, 1.2)

PENTA = [293.66, 329.63, 369.99, 440.0, 493.88, 587.33, 659.26, 739.99, 880.0]  # D 宮調

# ---------- 劇本 ----------
SCENES = [
    dict(id=1, min=5, lines=[dict(at=0.8, who='narrator', text='三國時期，曹操率領大軍，經過一片荒涼的旱地。')]),
    dict(id=2, min=8, lines=[dict(at=2.4, who='soldierA', text='水……水……再沒有水，我們真的走不動了……')]),
    dict(id=3, min=10, lines=[dict(at=0.8, who='narrator', text='酷暑難耐，士兵們口渴難忍，行軍速度越來越慢。')]),
    dict(id=4, min=8, lines=[dict(at=1.0, who='narrator', text='曹操心知，若找不到水源，大軍隨時可能崩潰。')]),
    dict(id=5, min=5, lines=[dict(at=1.4, who='caocaoThink', text='有了！')]),
    dict(id=6, min=10, lines=[dict(at=1.8, who='caocao', text='將士們！前方的山谷後，有一大片青梅林！果實累累，酸甜多汁，足夠我們解渴！')]),
    dict(id=7, min=8, lines=[dict(at=1.0, who='narrator', text='一聽到「酸甜青梅」四個字……')]),
    dict(id=8, min=10, lines=[dict(at=4.2, who='soldiers', text='咕嚕！酸梅！好酸啊！')]),
    dict(id=9, min=12, lines=[dict(at=1.6, who='soldiers', text='衝啊！去吃青梅！')]),
    dict(id=10, min=10, lines=[dict(at=1.5, who='narrator', text='雖然並沒有真的青梅，但士兵們憑著對酸梅的想像分泌唾液，終於堅持到了水源地。')]),
    dict(id=11, min=4, lines=[dict(at=1.0, who='narrator', text='「望梅止渴」，比喻願望無法實現，只能用空想來安慰自己。')]),
]
# 字幕顯示原文（TTS 為求發音正確，個別字詞改寫）
DISPLAY = {'果實累累': '果實纍纍', '只能用空想來安慰自己': '只能用空想來慰藉自己'}

VOICE = {
    'narrator':    lambda s: say(s, speed=0.9, pitch=0.97),
    'soldierA':    lambda s: say(s, speed=0.72, pitch=0.86, extra='tremolo=f=6:d=0.35'),
    'caocao':      lambda s: say(s, speed=1.0, pitch=0.78, extra='volume=1.2'),
    'caocaoThink': lambda s: say(s, speed=1.0, pitch=0.78, extra='aecho=0.8:0.7:60|120:0.35|0.2'),
}

def soldiers_voice(s):
    parts = [say(s, speed=1.05, pitch=p) for p in (0.8, 0.88, 0.95)]
    n = max(len(p) for p in parts) + 3000
    x = np.zeros(n)
    for k, p in enumerate(parts):
        o = k * 1100; x[o:o + len(p)] += p * (1.0 if k == 0 else 0.6)
    return x / np.abs(x).max() * 0.85
VOICE['soldiers'] = soldiers_voice

# 先產生語音，決定每一場長度
t0 = 0.0
timeline = []
for sc in SCENES:
    end = sc['min']
    for ln in sc['lines']:
        ln['audio'] = VOICE[ln['who']](ln['text'])
        ln['dur'] = len(ln['audio']) / SR
        end = max(end, ln['at'] + ln['dur'] + 1.0)
    sc['start'] = round(t0, 3); sc['dur'] = round(end, 3); t0 += end
TOTAL = t0 + 0.5
mix = np.zeros(int(TOTAL * SR) + SR)
voice_bus = np.zeros_like(mix)

def put(x, at, gain=1.0, bus=None):
    bus = mix if bus is None else bus
    i = int(at * SR); x = np.asarray(x) * gain
    bus[i:i + len(x)] += x[:len(bus) - i]

S = {sc['id']: sc for sc in SCENES}
def st(i): return S[i]['start']
def du(i): return S[i]['dur']

# 1 烈日：蟬鳴、熱浪
put(cicada(du(1) + du(2) + 1.0), st(1)); put(heat_hum(du(1) + du(2)), st(1))
put(wind(du(1), 0.12), st(1))
# 2 拖步、空壺、滴水
for k in range(6): put(footstep(0.25), st(2) + 0.2 + k * 0.55)
put(clunk(), st(2) + 1.0); put(drip(), st(2) + 1.75); put(ding(2400, 0.8, 0.15), st(2) + 1.8)
# 3 沉重低緩配樂
put(pad([146.83, 174.61, 220.0], du(3) + 0.8, 0.10), st(3))
put(pad([73.42], du(3) + 0.8, 0.08), st(3))
for k, f in enumerate([440.0, 392.0, 349.23, 293.66]):
    put(pluck(f, 2.0, 0.12, 0.3), st(3) + 1.0 + k * 2.2)
# 4 急促風聲，節奏收緊
put(wind(du(4), 0.35), st(4))
for k in range(int(du(4) / 0.5)): put(drum(55, 0.25 + 0.03 * k, 0.3), st(4) + 0.5 + k * 0.5)
# 5 靈光一閃
put(ding(1568, 1.5, 0.4), st(5) + 0.9); put(ding(2093, 1.2, 0.25), st(5) + 1.0)
# 6 馬嘶、揮鞭、戰鼓
put(neigh(), st(6) + 0.2); put(whip(), st(6) + 1.2)
for k in range(int((du(6) - 1.4) / 0.42)):
    put(drum(62 if k % 4 else 50, 0.55 if k % 4 else 0.9, 0.5), st(6) + 1.4 + k * 0.42)
# 7 夢幻青梅：咬下、爆汁
for k, f in enumerate([PENTA[i] for i in (4, 5, 6, 7, 8, 6)]):
    put(pluck(f, 1.5, 0.1, 0.6), st(7) + 0.2 + k * 0.35)
put(pad([587.33, 739.99, 880.0], du(7), 0.05), st(7))
for k in range(3):
    put(bite(), st(7) + 2.6 + k * 1.6); put(splash(), st(7) + 2.7 + k * 1.6)
# 8 集體嚥口水
for k, at in enumerate([0.6, 1.6, 2.6, 3.3]): put(gulp(0.8 if k < 3 else 1.0), st(8) + at)
put(gulp(1.0), st(8) + 4.2 + S[8]['lines'][0]['dur'] * 0.05)
# 9 歡呼、奔跑、快板音樂
put(crowd(du(9), 0.22), st(9) + 0.8)
for k in range(int((du(9) - 1) / 0.22)): put(footstep(0.25), st(9) + 1.0 + k * 0.22 + rng.uniform(0, 0.05))
seq = [0, 2, 3, 4, 3, 2, 4, 5, 4, 3, 2, 0, 1, 2, 3, 5]
for k in range(int((du(9) - 0.5) / 0.25)):
    put(pluck(PENTA[seq[k % len(seq)]] * (1 if k % 16 < 8 else 1.122), 0.6, 0.12, 0.6), st(9) + 0.5 + k * 0.25)
    if k % 2 == 0: put(drum(70, 0.4, 0.3), st(9) + 0.5 + k * 0.25)
# 10 幽默輕鬆結尾樂
fun = [5, 3, 4, 2, 3, 1, 2, 0, 2, 4, 3, 5, 6, 5, 4, 5]
for k in range(int((du(10) - 0.5) / 0.4)):
    put(pluck(PENTA[fun[k % len(fun)]], 0.8, 0.08, 0.55), st(10) + 0.3 + k * 0.4)
    if k % 4 == 3: put(pluck(PENTA[fun[k % len(fun)]] / 2, 0.8, 0.06, 0.4), st(10) + 0.3 + k * 0.4)
put(neigh() * 0.5, st(10) + du(10) - 2.0)
# 11 古箏刮奏、定音鼓
for k, f in enumerate(PENTA):
    put(pluck(f, 2.5, 0.12, 0.55), st(11) + 0.05 + k * 0.06)
put(drum(48, 1.0, 1.5), st(11) + du(11) - 1.4)
put(pluck(293.66, 3.0, 0.15, 0.5), st(11) + du(11) - 1.4)

# 語音（另外一條音軌，壓低背景）
lines_out = []
for sc in SCENES:
    for ln in sc['lines']:
        at = sc['start'] + ln['at']
        put(ln['audio'], at, 1.0, voice_bus)
        txt = ln['text']
        for a, b in DISPLAY.items(): txt = txt.replace(a, b)
        lines_out.append(dict(scene=sc['id'], who=ln['who'], text=txt, start=round(at, 3),
                              dur=round(ln['dur'], 3), env=envelope(ln['audio'])))

# 旁白出現時讓背景音小一點（ducking）
duck = lowpass((np.abs(voice_bus) > 0.02).astype(float), 8000)
mix = mix * (1 - 0.45 * np.clip(duck * 3, 0, 1)) + voice_bus
mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.6) * 0.9
sf.write(os.path.join(HERE, 'soundtrack.wav'), mix[:int(TOTAL * SR)].astype(np.float32), SR)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(HERE, 'soundtrack.wav'), '-b:a', '128k',
                os.path.join(OUT, 'soundtrack.mp3')], check=True)
os.remove(os.path.join(HERE, 'soundtrack.wav'))
data = dict(total=round(TOTAL, 3), fps=FPS,
            scenes=[dict(id=s['id'], start=s['start'], dur=s['dur']) for s in SCENES], lines=lines_out)
with open(os.path.join(OUT, 'timeline.js'), 'w', encoding='utf-8') as f:
    f.write('window.TIMELINE = ' + json.dumps(data, ensure_ascii=False) + ';\n')
print('total', TOTAL)
for s in SCENES: print(s['id'], s['start'], s['dur'], [round(l['dur'], 2) for l in s['lines']])
