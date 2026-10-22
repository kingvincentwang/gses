"""對嘴：找出 DeeVid 片段裡的嘴巴，依旁白音量把原嘴壓扁或撐開"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def mouth_mask(a):
    r, g, b, al = [a[..., i].astype(int) for i in range(4)]
    return (r > 110) & (r - g > 75) & (g < 125) & (b > g - 30) & (al > 200)

def full_mouth_mask(a):
    """嘴內（深紅）加上與它相連的舌頭（淺粉紅），並把每一欄上下之間補滿"""
    core = mouth_mask(a)
    r, g, b = [a[..., i].astype(int) for i in range(3)]
    tongue = (r > 180) & (r - g > 55) & (b < g + 35) & (a[..., 3] > 200)
    near = np.asarray(Image.fromarray(core.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(15))) > 0
    m = core | (tongue & near)
    mi = Image.fromarray(m.astype(np.uint8) * 255)
    m = np.asarray(mi.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))) > 0  # 補細縫
    out = m.copy()
    for x in np.nonzero(m.any(axis=0))[0]:
        ys = np.nonzero(m[:, x])[0]
        out[ys[0]:ys[-1] + 1, x] = True
    return out


def detect_mouths(frames):
    """每格找出嘴巴外框；以時間中位數平滑，避免跳動"""
    boxes = []
    for f in frames:
        a = np.asarray(f)
        m = mouth_mask(a).astype(np.int32)
        m[int(a.shape[0] * 0.62):] = 0
        m[: int(a.shape[0] * 0.24)] = 0
        if m.sum() < 30:
            boxes.append(None)
            continue
        ii = np.pad(m.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        h, w = 40, 60
        win = ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]
        y, x = np.unravel_index(win.argmax(), win.shape)
        cx, cy = x + w // 2, y + h // 2
        y0, x0 = max(0, cy - 45), max(0, cx - 75)
        ys, xs = np.nonzero(m[y0:cy + 45, x0:cx + 75])
        xs, ys = xs + x0, ys + y0
        boxes.append([np.percentile(xs, 1), np.percentile(ys, 1), np.percentile(xs, 99), np.percentile(ys, 99)])
    arr = np.array([b if b else [np.nan] * 4 for b in boxes], float)
    out = arr.copy()
    for i in range(len(arr)):
        out[i] = np.nanmedian(arr[max(0, i - 2): i + 3], axis=0)
    return out

def draw_mouth(frame, box, o):
    """把原本的嘴擦掉，再把原嘴垂直縮放成開合程度 o（0 閉 ~ 1 原樣全開）貼回去，保留 3D 質感"""
    a = np.asarray(frame).copy()
    x0, y0, x1, y1 = box
    pad = 14
    X0, Y0, X1, Y1 = int(x0 - pad), int(y0 - pad), int(x1 + pad), int(y1 + pad)
    orig = Image.fromarray(a[Y0:Y1, X0:X1].copy())
    sub = a[Y0:Y1, X0:X1].astype(float)
    raw = Image.fromarray((full_mouth_mask(a[Y0:Y1, X0:X1]) * 255).astype(np.uint8))
    mk = np.asarray(raw.filter(ImageFilter.MaxFilter(13))) > 0
    ring = (~mk) & (sub[..., 3] > 200)
    if ring.sum() < 20:
        return frame
    skin = np.median(sub[ring][:, :3], axis=0)
    rows = np.empty_like(sub[..., :3])
    for yy in range(sub.shape[0]):
        rr = ring[yy]
        rows[yy] = np.median(sub[yy, rr, :3], axis=0) if rr.sum() > 4 else skin
    patch = np.asarray(Image.fromarray(np.where(mk[..., None], rows, sub[..., :3]).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(3))).astype(float)
    pa = np.asarray(Image.fromarray(mk.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(3)))[..., None] / 255.0
    sub[..., :3] = sub[..., :3] * (1 - pa) + patch * pa
    a[Y0:Y1, X0:X1] = sub.astype(np.uint8)
    img = Image.fromarray(a)
    # 原嘴（含唇線）做成貼片後垂直縮放
    m2 = raw.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
    piece = orig.copy()
    piece.putalpha(Image.fromarray(np.minimum(np.asarray(m2), np.asarray(orig.getchannel("A")))))
    f = 0.16 + 0.84 * o
    ph = max(3, int(piece.height * f))
    piece = piece.resize((piece.width, ph), Image.LANCZOS)
    oy = int(Y0 + (y1 - y0) * 0.18 * (1 - f))
    img.alpha_composite(piece, (X0, oy))
    return img
