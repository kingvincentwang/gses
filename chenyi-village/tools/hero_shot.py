"""主角近拍：python tools/hero_shot.py <專案>。存正面與桌機、手機畫面到 QA/。"""
import sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
root = pathlib.Path(sys.argv[1]).resolve()
with sync_playwright() as p:
    br = p.chromium.launch(headless=True, args=["--use-angle=d3d11", "--ignore-gpu-blocklist"])
    pg = br.new_page(viewport={"width": 1000, "height": 700})
    pg.goto(root.joinpath("game.html").as_uri())
    pg.wait_for_function("document.querySelector('#loading').classList.contains('done')&&window.__bird")
    pg.evaluate("localStorage.setItem('chengyu-village-tut','1')")
    pg.click("#tStart"); pg.wait_for_selector("#dlg:not(.hide)"); pg.click("#dlg"); pg.wait_for_function("__bird.G.mode==='explore'")
    pg.evaluate("(()=>{const B=__bird;B.P.pos.set(0,0,3);B.P.facing=Math.PI;B.P.yaw=Math.PI;B.P.pitch=.12;})()")
    # 鏡頭轉到主角正面（yaw=π 時鏡頭在 -z 方向）
    pg.wait_for_timeout(1300); pg.locator("#c").screenshot(path=str(root / "QA" / "hero_front.png"))
    pg.evaluate("__bird.enterStation(19)"); pg.wait_for_function("__bird.G.mode==='explore'")
    pg.evaluate("__bird.P.pos.set(-3,0,4)"); pg.wait_for_timeout(300); pg.evaluate("__bird.interact()"); pg.wait_for_selector("#exp:not(.hide)")
    pg.locator("#expItems button").nth(0).click(); pg.wait_for_timeout(3200); pg.screenshot(path=str(root / "QA" / "boat_wide.png"))
    pg.locator("#expItems button").nth(2).click(); pg.wait_for_timeout(2300); pg.screenshot(path=str(root / "QA" / "boat_bottom.png"))
    br.close()
print("ok")
