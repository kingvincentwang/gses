"""產生旁白與主角台詞語音：python tools/make_voice.py <專案>
從遊戲讀出所有要唸的文字（window.__bird.voiceLines()），用 edge_tts 產生 audio/v_<雜湊>.mp3。
文字沒變的語音會沿用，改了文字只重錄那一段；不再使用的語音檔會刪除。需要連網。
聲音：旁白 zh-TW-HsiaoChenNeural（與翻頁繪本相同設定）；主角 zh-TW-YunJheNeural 調高音調，聽起來較年輕。"""
import asyncio, sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
import edge_tts
from playwright.sync_api import sync_playwright
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
out = root / "audio"; out.mkdir(exist_ok=True)
VOICE = {"narrator": dict(voice="zh-TW-HsiaoChenNeural", rate="-8%"),
         "hero": dict(voice="zh-TW-YunJheNeural", rate="+0%", pitch="+30Hz")}
with sync_playwright() as p:
    br = p.chromium.launch(headless=True); pg = br.new_page()
    pg.goto((root / "game.html").as_uri()); pg.wait_for_function("window.__bird&&window.__bird.voiceLines", timeout=90000)
    lines = pg.evaluate("__bird.voiceLines()"); br.close()
seen = {}
for l in lines: seen.setdefault(l["key"], l)
async def run():
    made = 0
    for k, l in seen.items():
        f = out / f"v_{k}.mp3"
        if f.exists() and f.stat().st_size > 0: continue
        await edge_tts.Communicate(l["text"], **VOICE[l["role"]]).save(str(f)); made += 1
    return made
made = asyncio.run(run())
keep = {f"v_{k}.mp3" for k in seen}
for f in out.glob("v_*.mp3"):
    if f.name not in keep: f.unlink()
size = sum(f.stat().st_size for f in out.glob("v_*.mp3"))
print(f"語音 {len(seen)} 段（新產生 {made}），共 {size // 1024} KB")
