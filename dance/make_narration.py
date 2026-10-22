"""關西小子短片旁白產生器（離線語音合成）

用法：
  1. 下載 sherpa-onnx 中文語音模型（約 130 MB，不放進版本庫）：
       https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/matcha-icefall-zh-baker.tar.bz2
       https://github.com/k2-fsa/sherpa-onnx/releases/download/vocoder-models/vocos-22khz-univ.onnx
     解壓到同一個資料夾，例如 dance/tts/
  2. pip install sherpa-onnx opencc
  3. python3 dance/make_narration.py [模型資料夾]
輸出：dance/narration.wav、dance/narration.json（每句的開始時間與長度，給 make_short.py 使用）
"""
import json
import os
import sys
import wave

import numpy as np
import opencc
import sherpa_onnx

HERE = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "tts")
WAV_OUT = os.path.join(HERE, "narration.wav")
JSON_OUT = os.path.join(HERE, "narration.json")
SR = 44100
SPEED = 0.85  # 先慢慢念……
PITCH = 1.18  # ……再加快播放，音調變高，聽起來更像小朋友

# (預定開始秒數, 旁白)；畫面時間軸見 make_short.py
SCRIPT = [
    (0.2, "嗨！我是關西小子！"),
    (2.6, "左右搖擺，跟著節拍！"),
    (4.9, "雙手扠腰，好帥氣！"),
    (7.4, "張開雙手，好開心！"),
    (9.4, "再來一次，搖一搖！"),
    (11.8, "大家一起跳！"),
    (13.6, "一二三四，五六七八！"),
    (16.8, "越跳越開心！"),
    (19.4, "最後揮揮手，說再見！"),
    (22.0, "一起動起來！下課也來跳一跳！"),
]


def main():
    model = os.path.join(TTS_DIR, "matcha-icefall-zh-baker")
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            matcha=sherpa_onnx.OfflineTtsMatchaModelConfig(
                acoustic_model=f"{model}/model-steps-3.onnx",
                vocoder=os.path.join(TTS_DIR, "vocos-22khz-univ.onnx"),
                lexicon=f"{model}/lexicon.txt", tokens=f"{model}/tokens.txt", dict_dir=f"{model}/dict"),
            num_threads=4),
        rule_fsts=f"{model}/phone.fst,{model}/date.fst,{model}/number.fst",
        max_num_sentences=1)
    tts = sherpa_onnx.OfflineTts(cfg)
    t2s = opencc.OpenCC("t2s")  # 模型字典是簡體字

    lines, clips, t_end = [], [], 0.0
    for start, text in SCRIPT:
        audio = tts.generate(t2s.convert(text), sid=0, speed=SPEED)
        x = np.asarray(audio.samples, np.float32)
        # 重新取樣到 44.1 kHz，同時乘上 PITCH 讓音調升高
        n_out = int(len(x) * SR / audio.sample_rate / PITCH)
        y = np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x)
        nz = np.where(np.abs(y) > 0.01)[0]  # 修掉前後靜音
        y = y[max(0, nz[0] - 200): nz[-1] + 2000]
        start = max(start, t_end + 0.15)  # 避免句子重疊
        dur = len(y) / SR
        lines.append({"start": round(start, 3), "dur": round(dur, 3), "text": text})
        clips.append((start, y))
        t_end = start + dur
        print(f"{start:5.2f}s +{dur:.2f}s  {text}")

    out = np.zeros(int((t_end + 0.5) * SR), np.float32)
    for start, y in clips:
        s = int(start * SR)
        out[s:s + len(y)] += y
    out = out / (np.abs(out).max() + 1e-9) * 0.9
    with wave.open(WAV_OUT, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((out * 32767).astype(np.int16).tobytes())
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(lines, f, ensure_ascii=False, indent=1)
    print("完成：", WAV_OUT)


if __name__ == "__main__":
    main()
