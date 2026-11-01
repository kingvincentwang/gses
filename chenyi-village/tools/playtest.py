"""整場試玩：python tools/playtest.py <專案> <截圖資料夾>
依遊戲狀態自動操作：第一段用真實按鍵走路，其餘把角色放到目標旁再按 E。三個實驗各答錯一次。"""
import sys, time, pathlib
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
root = pathlib.Path(sys.argv[1]).resolve(); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
errs, seen = [], set()
with sync_playwright() as p:
    br = p.chromium.launch(headless=True, args=["--use-angle=d3d11", "--ignore-gpu-blocklist"])
    pg = br.new_page(viewport={"width": 1280, "height": 720})
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append("console " + m.text))
    pg.goto(root.joinpath("game.html").as_uri())
    pg.wait_for_function("document.querySelector('#loading').classList.contains('done')&&window.__bird", timeout=90000)
    pg.wait_for_timeout(800); pg.screenshot(path=out / "00_title.png")
    pg.click("#tStart"); pg.wait_for_selector("#tut:not(.hide)"); pg.click("#tutGo")
    def st(): return pg.evaluate("__bird.G.station")
    def mode(): return pg.evaluate("__bird.G.mode")
    def shot(tag):
        n = f"{st():02d}_{tag}"
        if n not in seen:
            seen.add(n); pg.wait_for_timeout(950); pg.screenshot(path=out / f"{n}.png")
    def answer():
        no = int(pg.inner_text("#qMeta").split()[1]) if False else None
        s = st(); shown = pg.inner_text("#qText")
        q = pg.evaluate("(t)=>{for(const s of __bird.ST)for(const q of s.steps||[])if(t.endsWith(q.q)||q.q===t)return q}", shown)
        shot(f"q{q['no']}")
        ty = q["type"]
        if ty == "choice": pg.locator("#qBody button.opt", has_text=q["options"][q["answer"]]).click()
        elif ty == "tf": pg.locator("#qBody button.opt").nth(0 if q["answer"] else 1).click()
        elif ty == "fill": pg.locator("#qBody button.opt", has_text=q["answer"]).click()
        elif ty == "order":
            for t in q["items"]: pg.locator("#qBody button.opt", has_text=t).click()
        elif ty == "match":
            rows = pg.locator("#qBody .row")
            for r in range(rows.count()):
                row = rows.nth(r); z = q["answer"][row.locator("p").inner_text()]; row.locator("button").nth(q["zones"].index(z)).click()
        pg.click("#qOk"); pg.wait_for_timeout(250); print(f"第{q['no']}題 {ty} {q['level']} OK")
    def press_item(i, wait):
        pg.wait_for_function(f"!document.querySelectorAll('#expItems button')[{i}].disabled")
        pg.locator("#expItems button").nth(i).click(); pg.wait_for_timeout(wait)
    def exp():
        s = st(); shot("exp_start")
        if s == 6:
            press_item(1, 3200); print(" 取下畫軸：", pg.inner_text("#expObs")); pg.locator("#expAns button").nth(1).click(); pg.wait_for_timeout(200)
            print(" 錯答 HP", pg.evaluate("__bird.G.hp")); press_item(1, 3200); press_item(0, 3200); pg.screenshot(path=out / "06_exp_after.png"); print(" 取下角弓：", pg.inner_text("#expObs"), pg.evaluate("__bird.H.snake.visible"))
            pg.locator("#expAns button").nth(0).click()
        elif s == 14:
            for d in range(3): press_item(0, 3100); print(" ", pg.inner_text("#expObs"))
            pg.screenshot(path=out / "14_exp_day3.png"); pg.locator("#expAns button").nth(0).click(); pg.wait_for_timeout(200); print(" 錯答 HP", pg.evaluate("__bird.G.hp"), pg.inner_text("#expHint"))
            pg.locator("#expAns button").nth(1).click()
        elif s == 19:
            press_item(1, 1800); print(" ", pg.inner_text("#expObs")); press_item(0, 2800); print(" ", pg.inner_text("#expObs"), "船X", pg.evaluate("__bird.RV.boat.position.x"))
            pg.screenshot(path=out / "19_exp_moved.png"); press_item(1, 1800); pg.screenshot(path=out / "19_exp_mark.png"); print(" ", pg.inner_text("#expObs")); press_item(2, 1800); pg.screenshot(path=out / "19_exp_bottom.png"); print(" ", pg.inner_text("#expObs"))
            pg.locator("#expAns button").nth(0).click(); pg.wait_for_timeout(200); print(" 錯答 HP", pg.evaluate("__bird.G.hp"), pg.inner_text("#expHint")); pg.locator("#expAns button").nth(1).click()
    first_walk = True; end = time.time() + 280; order = []
    while time.time() < end:
        if pg.is_visible("#cert"): break
        if pg.is_visible("#end"):
            print("結局：", pg.inner_text("#endInfo").replace("\n", " ")); pg.fill("#endName", "測試學生"); pg.click("#endGo"); pg.wait_for_selector("#cert:not(.hide)"); continue
        if pg.is_visible("#cardBox"):
            print("成語卡", pg.inner_text("#cName")); pg.wait_for_timeout(300); pg.screenshot(path=out / f"card_{pg.inner_text('#cName')}.png"); pg.click("#cardGo"); pg.wait_for_timeout(300); continue
        m = mode()
        if m == "dialog":
            shot("dlg"); s = st(); print("站", s, pg.inner_text("#hudName"))
            pg.keyboard.press("Space") if s == 0 else pg.click("#dlg"); pg.wait_for_timeout(150)
        elif m == "explore":
            s = st(); shot("explore"); ts = pg.evaluate("__bird.ST[%d].hub" % s)
            if ts:  # 依序走訪：第一次中間，再左、右，最後村長
                pos = pg.evaluate("""()=>{const P=__bird.P;const c=__bird.G.cards;const I=__bird.IDIOMS;if(c.length>=3)return [4,3.5];const k=Object.keys(I).find(x=>!c.includes(x));const d=I[k].door();return [d.x,d.z]}""")
            else:
                t = pg.evaluate("(()=>{const t=__bird.ST[%d].target();return [t.x,t.z]})()" % s); pos = [t[0], t[1] + 1.6]
            if first_walk:
                first_walk = False; end2 = time.time() + 14
                while time.time() < end2:
                    d = pg.evaluate(f"Math.hypot({pos[0]}-__bird.P.pos.x,{pos[1]}-__bird.P.pos.z)")
                    if d < 1.8: break
                    pg.evaluate(f"(()=>{{const P=__bird.P;P.yaw=Math.atan2(-({pos[0]}-P.pos.x),-({pos[1]}-P.pos.z));}})()")
                    pg.keyboard.down("KeyW"); pg.wait_for_timeout(350); pg.keyboard.up("KeyW")
                print("真實走路到門口，距離", round(d, 2))
            else:
                pg.evaluate(f"__bird.P.pos.set({pos[0]},0,{pos[1]})")
            pg.wait_for_timeout(350); shot("prompt"); pg.keyboard.press("KeyE"); pg.wait_for_timeout(300)
        elif m == "exp" and pg.is_visible("#exp"): exp()
        elif m == "quiz" and pg.is_visible("#quiz"): answer()
        else: pg.wait_for_timeout(200)
    pg.wait_for_timeout(300); pg.screenshot(path=out / "99_cert.png")
    print("HP", pg.evaluate("__bird.G.hp"), "線索章", pg.evaluate("__bird.G.feathers"), "成語卡", pg.evaluate("__bird.G.cards"), "解鎖", pg.evaluate("__bird.G.unlocked"), "有證書", pg.is_visible("#cert"))
    br.close()
print("錯誤", errs or "無")
