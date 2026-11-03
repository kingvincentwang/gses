"""把 models/*.glb 打包成 models/models.js（base64），讓 game.html 雙擊開啟時也能載入模型。
用法：python tools/pack_models.py <專案>"""
import base64, json, sys, pathlib
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
d = root / "models"
data = {g.stem: "data:model/gltf-binary;base64," + base64.b64encode(g.read_bytes()).decode() for g in sorted(d.glob("*.glb"))}
(d / "models.js").write_text("window.BIRD_MODELS=" + json.dumps(data) + ";\n", encoding="utf-8")
print("packed", list(data), round((d / "models.js").stat().st_size / 1024), "KB")
