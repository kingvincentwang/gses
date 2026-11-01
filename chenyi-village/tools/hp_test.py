"""體力歸零測試：python tools/hp_test.py <專案>。在實驗關連續答錯，確認重玩且線索章不重複。"""
import sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
root = pathlib.Path(sys.argv[1]).resolve()
with sync_playwright() as p:
    br = p.chromium.launch(headless=True, args=["--use-angle=d3d11", "--ignore-gpu-blocklist"])
    pg = br.new_page(viewport={"width": 1280, "height": 720})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(root.joinpath("game.html").as_uri())
    pg.wait_for_function("document.querySelector('#loading').classList.contains('done')&&window.__bird")
    pg.evaluate("localStorage.setItem('chengyu-village-tut','1')")
    pg.click("#tStart"); pg.wait_for_selector("#dlg:not(.hide)"); pg.click("#dlg")
    pg.evaluate("__bird.enterStation(6)"); pg.wait_for_function("__bird.G.mode==='explore'")
    pg.evaluate("__bird.P.pos.set(0,0,1)"); pg.wait_for_timeout(100); pg.evaluate("__bird.interact()")
    pg.wait_for_selector("#exp:not(.hide)")
    pg.locator("#expItems button").nth(1).click(); pg.wait_for_timeout(3000)
    for i in range(5):
        pg.locator("#expAns button").nth(1).click(); pg.wait_for_timeout(150)
        print("第", i + 1, "次答錯 HP", pg.evaluate("__bird.G.hp"), "模式", pg.evaluate("__bird.G.mode"))
    pg.wait_for_function("__bird.G.mode==='explore'")
    print("重玩站別", pg.evaluate("__bird.G.station"), "HP", pg.evaluate("__bird.G.hp"), "實驗面板隱藏", pg.is_hidden("#exp"), "物件復原", pg.evaluate("__bird.H.scroll.visible"))
    pg.evaluate("__bird.P.pos.set(0,0,1)"); pg.wait_for_timeout(100); pg.evaluate("__bird.interact()"); pg.wait_for_selector("#exp:not(.hide)"); pg.wait_for_timeout(1500)
    pg.screenshot(path=str(root / "QA" / "hp_restart.png"))
    print("重玩可再進實驗", pg.is_visible("#expItems"), "錯誤", errs or "無")
    br.close()
