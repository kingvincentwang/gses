"""整場試玩：python tools/playtest.py <專案> <截圖資料夾>。以真實點擊與按鍵玩到證書，含答錯扣血。"""
import sys, time, pathlib
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
root = pathlib.Path(sys.argv[1]).resolve(); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
errs = []
with sync_playwright() as p:
    br = p.chromium.launch(headless=True, args=["--use-angle=d3d11", "--ignore-gpu-blocklist"])
    pg = br.new_page(viewport={"width": 1280, "height": 720})
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append("console " + m.text))
    t0 = time.time()
    pg.goto(root.joinpath("game.html").as_uri())   # file:// 測試
    pg.wait_for_function("document.querySelector('#loading').classList.contains('done')&&window.__bird", timeout=90000)
    print("file:// 載入秒數", round(time.time() - t0, 1))
    pg.wait_for_timeout(800); pg.screenshot(path=out / "01_title.png")
    pg.click("#tStart"); pg.wait_for_selector("#tut:not(.hide)"); pg.click("#tutGo")
    pg.wait_for_selector("#dlg:not(.hide)"); pg.wait_for_timeout(700); pg.screenshot(path=out / "02_hub_dialog.png")
    pg.keyboard.press("Space")
    pg.wait_for_function("__bird.G.mode==='explore'"); pg.wait_for_timeout(900); pg.screenshot(path=out / "03_hub.png")

    def walk_to(tx, tz, limit=14):
        end = time.time() + limit
        while time.time() < end:
            d = pg.evaluate(f"(()=>{{const P=__bird.P;return [{tx}-P.pos.x,{tz}-P.pos.z]}})()")
            if (d[0]**2 + d[1]**2)**.5 < 1.8: break
            pg.evaluate(f"(()=>{{const P=__bird.P;P.yaw=Math.atan2(-({tx}-P.pos.x),-({tz}-P.pos.z));}})()")
            pg.keyboard.down("KeyW"); pg.wait_for_timeout(350); pg.keyboard.up("KeyW")
        pg.wait_for_timeout(200)

    walk_to(0, -7.2); print("走到門口", pg.evaluate("[__bird.P.pos.x,__bird.P.pos.z]"), "提示泡泡", pg.is_visible("#prompt"))
    pg.screenshot(path=out / "04_door_prompt.png"); pg.keyboard.press("KeyE")
    def story(tag):
        pg.wait_for_selector("#dlg:not(.hide)", timeout=15000); pg.wait_for_timeout(1000)
        pg.screenshot(path=out / f"{tag}.png"); print("故事", pg.inner_text("#dlgName"), pg.inner_text("#hudName")); pg.click("#dlg")
    for t in ["05_banquet", "06_cup_snake", "07_swallow", "08_sick", "09_visit"]: story(t)
    pg.wait_for_function("__bird.G.station===6&&__bird.G.mode==='explore'"); pg.wait_for_timeout(900); pg.screenshot(path=out / "10_investigate.png")
    walk_to(0, .1); pg.keyboard.press("KeyE")
    pg.wait_for_selector("#exp:not(.hide)"); pg.wait_for_timeout(1400); pg.screenshot(path=out / "11_exp_cup.png")
    b = pg.locator("#expItems button")
    b.nth(1).click(); pg.wait_for_timeout(1100); pg.screenshot(path=out / "12_exp_wall.png"); pg.wait_for_timeout(1900)
    print("取下畫軸後：", pg.inner_text("#expObs"), "蛇可見", pg.evaluate("__bird.H.snake.visible"))
    hp0 = pg.evaluate("__bird.G.hp"); pg.locator("#expAns button").nth(1).click(); pg.wait_for_timeout(300)
    print("錯答扣血", hp0, "→", pg.evaluate("__bird.G.hp"), "提示：", pg.inner_text("#expHint"))
    b.nth(1).click(); pg.wait_for_timeout(2900)
    b.nth(0).click(); pg.wait_for_timeout(3000); pg.screenshot(path=out / "13_exp_no_snake.png")
    print("取下角弓後：", pg.inner_text("#expObs"), "蛇可見", pg.evaluate("__bird.H.snake.visible"))
    pg.locator("#expAns button").nth(0).click(); story("14_truth")
    pg.wait_for_function("__bird.G.station===7&&__bird.G.mode==='explore'"); pg.wait_for_timeout(600)
    walk_to(0, -.75); pg.keyboard.press("KeyE"); story("15_realize")

    pg.wait_for_selector("#quiz:not(.hide)"); q = pg.evaluate("__bird.ST[7].steps[0]")
    for t in q["items"]: pg.locator("#qBody button.opt", has_text=t).click()
    pg.screenshot(path=out / "16_q_order.png"); pg.click("#qOk"); pg.wait_for_timeout(400)
    def choice(st, i, shot=None):
        no = pg.evaluate(f"__bird.ST[{st}].steps[{i}].no")
        pg.wait_for_function(f"document.querySelector('#qMeta').textContent.includes('第 {no} 題')&&!document.querySelector('#quiz').classList.contains('hide')")
        q = pg.evaluate(f"__bird.ST[{st}].steps[{i}]"); ans = q["options"][q["answer"]]
        pos = pg.locator("#qBody button.opt").all_inner_texts().index(ans); print(f"第{no}題 正解位置", "ABCD"[pos], "pos", q["pos"])
        pg.locator("#qBody button.opt", has_text=ans).click()
        if shot: pg.screenshot(path=out / shot)
        pg.click("#qOk"); pg.wait_for_timeout(350)
    choice(7, 1)
    story("17_return"); story("18_clear")
    pg.wait_for_function("__bird.G.station===10&&__bird.G.mode==='explore'"); pg.wait_for_timeout(900)
    walk_to(4, 2); pg.screenshot(path=out / "19_elder.png"); pg.keyboard.press("KeyE"); story("20_moral")
    choice(10, 0)
    pg.wait_for_function("document.querySelector('#qMeta').textContent.includes('第 4 題')")
    q = pg.evaluate("__bird.ST[10].steps[1]")
    rows = pg.locator("#qBody .row")
    for r in range(rows.count()):
        row = rows.nth(r); z = q["answer"][row.locator("p").inner_text()]; row.locator("button").nth(q["zones"].index(z)).click()
    pg.screenshot(path=out / "21_q_match.png"); pg.click("#qOk"); pg.wait_for_timeout(350)
    choice(10, 2, "22_q_misuse.png")
    pg.wait_for_selector("#cardBox:not(.hide)", timeout=8000); pg.wait_for_timeout(300); pg.screenshot(path=out / "23_card.png"); pg.click("#cardGo")
    pg.wait_for_selector("#end:not(.hide)"); print("結局：", pg.inner_text("#endInfo").replace("\n", " "))
    pg.fill("#endName", "測試學生"); pg.click("#endGo"); pg.wait_for_selector("#cert:not(.hide)"); pg.wait_for_timeout(300); pg.screenshot(path=out / "24_cert.png")
    print("HP", pg.evaluate("__bird.G.hp"), "線索章", pg.evaluate("__bird.G.feathers"), "解鎖", pg.evaluate("__bird.G.unlocked"))
    print("FPS(headless)", pg.evaluate("new Promise(r=>{let n=0,s=performance.now();(function f(){n++;performance.now()-s>2000?r(n/2):requestAnimationFrame(f)})()})"))
    br.close()
print("錯誤", errs or "無")
