"""招牌與語音檢查：python tools/voice_sign_check.py <專案>
1. 截下五棟房子的招牌（QA/signs.png）
2. 進入幾段對話，確認語音檔真的載入並開始播放、關掉對話會停止、主角台詞用主角的聲音"""
import sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
from PIL import Image
root = pathlib.Path(sys.argv[1]).resolve(); qa = root / "QA"
with sync_playwright() as p:
    br = p.chromium.launch(headless=True, args=["--use-angle=d3d11", "--ignore-gpu-blocklist", "--autoplay-policy=no-user-gesture-required"])
    pg = br.new_page(viewport={"width": 900, "height": 560}); errs, mp3 = [], []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("requestfinished", lambda r: r.url.endswith(".mp3") and mp3.append(r.url.rsplit("/", 1)[1]))
    pg.on("requestfailed", lambda r: errs.append("failed " + r.url))
    pg.goto((root / "game.html").as_uri()); pg.wait_for_function("document.querySelector('#loading').classList.contains('done')&&window.__bird")
    pg.evaluate("localStorage.setItem('chengyu-village-tut','1')"); pg.click("#tStart"); pg.wait_for_selector("#dlg:not(.hide)"); pg.wait_for_timeout(1200)
    st = lambda: pg.evaluate("(()=>{const a=__bird.VO.el;return a?{src:a.src.split('/').pop(),t:+a.currentTime.toFixed(2),paused:a.paused}:null})()")
    print("村長對話：", pg.inner_text("#dlgName"), st())
    pg.click("#dlg"); pg.wait_for_timeout(900); print("主角台詞：", pg.inner_text("#dlgName"), pg.inner_text("#dlgText"), st())
    pg.click("#dlgVoice"); pg.wait_for_timeout(500); print("按重聽：", st())
    pg.click("#dlg"); pg.wait_for_timeout(300); print("關閉後：", st())
    pg.wait_for_function("__bird.G.mode==='explore'")
    shots = []
    NORMAL = {"杯弓蛇影": (0, 1), "守株待兔": (.966, .259), "刻舟求劍": (-.966, .259), "亡羊補牢": (.924, -.383), "畫蛇添足": (-.924, -.383)}
    for name, (nx, nz) in NORMAL.items():
        pg.evaluate("""([n,nx,nz])=>{const B=__bird;const d=Object.values(B.IDIOMS).find(x=>x.name===n).door();
          const x=d.x+nx*4.2,z=d.z+nz*4.2;B.P.pos.set(x,0,z);B.P.yaw=Math.atan2(-(d.x-x),-(d.z-z));B.P.pitch=.16;}""", [name, nx, nz])
        pg.wait_for_timeout(1000); f = qa / f"_sign{len(shots)}.png"; pg.screenshot(path=str(f)); shots.append(f)
    sheet = Image.new("RGB", (900 * 3, 560 * 2), "white")
    for i, f in enumerate(shots): sheet.paste(Image.open(f), ((i % 3) * 900, (i // 3) * 560)); f.unlink()
    sheet.save(qa / "signs.png")
    print("載入的語音檔：", len(mp3), "錯誤：", errs or "無")
    br.close()
