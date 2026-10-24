# 望梅止渴｜國風幽默動畫

依分鏡腳本（11 鏡、約 1 分 34 秒）製作的動畫，角色取自角色設定圖（曹操、士兵群），含旁白、角色配音、音效與配樂；角色說話時嘴巴會依配音音量開合。

- `index.html`：網頁播放器（Canvas 即時繪製，可拖曳進度、跳到任一分鏡）
- `wangmei.mp4`：輸出的影片檔（1280×720、30fps）
- `assets/`：去背角色圖、配樂 `soundtrack.mp3`、時間軸與嘴形資料 `timeline.js`、字型子集
- `tools/`：重新產生素材的程式
  - `crop_sprites.py <角色設定圖>`：裁切角色並去背
  - `build_audio.py <vits-melo-tts-zh_en 模型目錄>`：離線 TTS（sherpa-onnx）產生旁白與配音、合成音效配樂、計算嘴形
  - `render_video.js <輸出.mp4>`：以 Playwright 逐格擷取並用 ffmpeg 合成影片
