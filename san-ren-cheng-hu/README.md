# 三人成虎｜故事動畫

依分鏡腳本製作的寓言動畫（約 81 秒、1280×720、30fps），角色取自人物設定圖，
含旁白與角色配音，說話時角色嘴形依聲音大小同步開合。

成品：`三人成虎.mp4`

## 分鏡對照

| 幕 | 鏡頭 | 內容 |
|---|---|---|
| 一 | 1 | 魏國大殿全景推進，標題「三人成虎」化為墨點消散，旁白開場 |
| 一 | 2 | 過肩鏡頭聚焦龐蔥提問；反打魏王擺手笑答 |
| 二 | 3 | 墨跡暈開轉入水墨市集，路人甲特寫拉遠；魏王虛影搖頭「不信」 |
| 二 | 4 | 路人乙加入，鏡頭微晃；魏王虛影摸鬍子、半信半疑 |
| 二 | 5 | 路人丙衝入，墨點凝聚成咆哮猛虎（仰角），民眾逃竄；切回魏王「寡人就信了」 |
| 三 | 6 | 暖色大殿，龐蔥平視特寫、背景虛化，說出邯鄲比市集遠 |
| 三 | 7 | 魏王拍胸保證；快轉龐蔥走向殿門；陰影小人包圍耳語，魏王由疑轉怒、鏡頭拉遠 |
| 四 | 8 | 黑幕光束中龐蔥剪影消散，字幕逐字浮現；寓意「謠言止於智者」，銅鑼淡出 |

## 製作方式（皆為離線開源工具）

- **配音**：[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) + Kokoro 多語模型的中文男聲
  （旁白雲揚、龐蔥雲希、魏王雲健，路人以不同音色與音高區分）。
- **嘴形同步**：逐格計算每句台詞的音量包絡（`timeline.json` 的 `env`），
  龐蔥與魏王以繪製的嘴型開合；路人甲乙丙先修補掉原圖張開的嘴，再依音量縮放原本的嘴巴。
- **配樂音效**：程式合成的五聲音階撥弦、心跳鼓、虎嘯、耳語（隨機相位處理）與銅鑼。
- **畫面**：去背後的角色立繪、程式繪製的大殿／水墨市集背景與墨虎，以 Pillow 逐格合成，ffmpeg 編碼。

## 重新產生

```bash
pip install sherpa-onnx soundfile scipy opencv-python-headless pillow numpy
# 下載 Kokoro 模型：https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2
KOKORO_DIR=/path/to/kokoro-multi-lang-v1_0 python3 make_audio.py   # 產生 build/audio.wav、build/timeline.json
python3 render.py                                                   # 產生 三人成虎.mp4
python3 render.py --preview 10,36,66                               # 只輸出指定秒數的預覽圖
```

台詞、配音音色與停頓都在 `story.py` 修改。
