# 將配樂 music.wav 與各句旁白 vo/line*.wav 依 log.json 的時間點混音成 mix.wav（說話時配樂自動壓低）
import sys, json, numpy as np, soundfile as sf
D = sys.argv[1]
log = json.load(open(f'{D}/log.json')); m, sr = sf.read(f'{D}/music.wav'); m = m.astype(np.float32)
v = np.zeros_like(m); duck = np.ones_like(m)
for i, t in enumerate(log['lines']):
    x, r = sf.read(f'{D}/vo/line{i}.wav'); n = int(len(x) * sr / r)
    y = np.interp(np.arange(n) * r / sr, np.arange(len(x)), x)
    s = int(t * sr); e = min(len(v), s + n); v[s:e] += y[:e - s] * 0.95
    duck[max(0, s - 2000):e + 4000] = 0.55
duck = np.convolve(duck, np.ones(4410) / 4410, 'same')
mix = m * duck * 0.9 + v; mix /= max(1, np.abs(mix).max() / 0.97)
sf.write(f'{D}/mix.wav', mix, sr)
