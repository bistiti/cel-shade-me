import sys
import numpy as np
from PIL import Image
sys.path.insert(0, "/Users/macia/figurine_paint/scripts")
import recolor_vallejo as rv
import segment_region as sr

pal = rv.load_palette()
arr = np.array(Image.open("/Users/macia/figurine_paint/samples/fig1.jpg").convert("RGB"), np.float32) / 255
H, W = arr.shape[:2]
fg = sr.foreground_mask(arr)
yy = np.arange(H)[:, None] / H
body = ((fg > 0) & (yy < 0.80)).astype(np.float32)
base = ((fg > 0) & (yy >= 0.80)).astype(np.float32)
out = arr.copy()
for m, code in [(body, "69.009"), (base, "69.030")]:
    tgt = rv.get_rgb(code, pal) / 255
    out, cov = rv.recolor_region(out, m, rv.feather_mask(m, 2), tgt)
    de = float(np.sqrt(((rv.rgb_to_lab(out)[m > 0.5].mean(0) - rv.rgb_to_lab(tgt.reshape(1, 1, 3))[0, 0]) ** 2).sum()))
    print(code, pal[code]["hex"], "cov", round(cov * 100, 1), "deltaE", round(de, 2))
a = (arr * 255).astype(np.uint8)
b = (np.clip(out, 0, 1) * 255).astype(np.uint8)
Image.fromarray(np.concatenate([a, b], 1)).save("/tmp/fig1_demo.png")
print("saved /tmp/fig1_demo.png")
