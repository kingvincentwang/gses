#!/bin/bash
# 產生 laomashitu.mp4：離線語音 → 逐格錄製動畫與配樂 → 混音 → 合成影片
# 需要：pip install sherpa-onnx opencc-python-reimplemented soundfile numpy；node + playwright；ffmpeg
# 語音模型：https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2
set -e
MODEL=${1:?用法: make_video.sh <kokoro-multi-lang-v1_0 目錄> [工作目錄]}
WORK=${2:-$(mktemp -d)}
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(dirname "$(dirname "$HERE")")
mkdir -p "$WORK/vo" "$WORK/frames"
python3 "$HERE/tts.py" "$MODEL" "$WORK/vo" "$HERE/lines.json"
(cd "$ROOT" && exec python3 -m http.server 8765 >/dev/null 2>&1) & SRV=$!; sleep 1
node "$HERE/render.js" "$WORK"; kill $SRV
python3 "$HERE/mix.py" "$WORK"
ffmpeg -y -loglevel error -framerate 30 -i "$WORK/frames/%05d.jpg" -i "$WORK/mix.wav" -c:v libx264 -preset slow -crf 20 \
  -pix_fmt yuv420p -c:a aac -b:a 160k -shortest -movflags +faststart "$HERE/../laomashitu.mp4"
echo "完成：$HERE/../laomashitu.mp4"
