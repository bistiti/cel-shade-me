import sys
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, "/Users/macia/figurine_paint/scripts")
import recolor_vallejo as rv
pal = rv.load_palette()


def rasterize(H, W, strokes):
    """strokes: [{pts:[(x,y)norm...], r:rayon_norm, mode:add|erase}]"""
    m = np.zeros((H, W), np.uint8)
    for st in strokes:
        pts = [(int(x * W), int(y * H)) for x, y in st["pts"]]
        r = max(1, int(st["r"] * min(H, W)))
        val = 255 if st.get("mode", "add") == "add" else 0
        for i, pt in enumerate(pts):
            cv2.circle(m, pt, r, val, -1)
            if i > 0:
                cv2.line(m, pts[i - 1], pt, val, r * 2)
    return (m > 127).astype(np.float32)


arr = np.array(Image.open("/Users/macia/figurine_paint/samples/fig1.jpg").convert("RGB"), np.float32) / 255
H, W = arr.shape[:2]
zones = [
    {"code": "69.009", "strokes": [{"pts": [(0.5, 0.30), (0.5, 0.45), (0.5, 0.60), (0.5, 0.72)], "r": 0.07}]},
    {"code": "69.017", "strokes": [{"pts": [(0.40, 0.92), (0.5, 0.93), (0.60, 0.92)], "r": 0.045}]},
]
claimed = np.zeros((H, W), bool)
masks = []
for z in zones:
    m = rasterize(H, W, z["strokes"]); m[claimed] = 0; claimed |= (m > 0.5); masks.append(m)

out = arr.copy()
for z, m in zip(zones, masks):
    tgt = rv.get_rgb(z["code"], pal) / 255
    out, cov = rv.recolor_region(out, m, rv.feather_mask(m, 2), tgt)
    sel = m > 0.5
    de = float(np.sqrt(((rv.rgb_to_lab(out)[sel].mean(0) - rv.rgb_to_lab(tgt.reshape(1, 1, 3))[0, 0]) ** 2).sum()))
    print(f"{z['code']} {pal[z['code']]['hex']} cov={round(cov*100,1)}% deltaE={round(de,2)}")

Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save("/tmp/seg/fig1_strokes.png")
ov = (arr * 255).astype(np.uint8).copy()
for m, col in zip(masks, [(255, 0, 0), (0, 128, 255)]):
    ov[m > 0.5] = (0.5 * ov[m > 0.5] + 0.5 * np.array(col)).astype(np.uint8)
Image.fromarray(ov).save("/tmp/seg/fig1_strokes_mask.png")
print("saved fig1_strokes.png (recolor) + fig1_strokes_mask.png (tracé)")
