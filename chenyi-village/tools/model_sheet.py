"""把主角各動作截圖拼成一張：python tools/model_sheet.py <專案> → QA/hero_sheet.png"""
import sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
from PIL import Image
root = pathlib.Path(sys.argv[1]).resolve(); qa = root / "QA"; qa.mkdir(exist_ok=True)
shots = [("Idle", 0, "front"), ("Idle", 0, "three"), ("Idle", 0, "back"), ("Walk", .25, "side"), ("Walk", .25, "front"), ("Run", .25, "side"),
         ("Wave", .25, "front"), ("Cheer", .45, "front"), ("Surprise", .3, "front"), ("Sit", 0, "side"), ("Sit", 0, "three"), ("Cheer", .45, "side")]
W, H = 360, 420; sheet = Image.new("RGB", (W * 6, H * 2), "white")
with sync_playwright() as p:
    br = p.chromium.launch(headless=True, args=["--use-angle=d3d11", "--ignore-gpu-blocklist", "--allow-file-access-from-files"])
    pg = br.new_page(viewport={"width": W, "height": H})
    for i, (a, t, v) in enumerate(shots):
        pg.goto((root / "tools" / "model-check.html").as_uri() + f"?anim={a}&t={t}&view={v}")
        pg.wait_for_function("window.done===true", timeout=60000); pg.wait_for_timeout(150)
        f = qa / "_m.png"; pg.screenshot(path=str(f)); sheet.paste(Image.open(f), ((i % 6) * W, (i // 6) * H))
        if i == 0: print(pg.inner_text("#info"))
    br.close()
(qa / "_m.png").unlink(missing_ok=True); sheet.save(qa / "hero_sheet.png"); print("ok")
