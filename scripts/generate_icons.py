"""Genere les icones de lanceur Android a partir de android/icon_src.png :
pinceau centre sur fond blanc carre, aux 5 densites, ic_launcher + round."""
import os
from PIL import Image

SRC = "/Users/macia/figurine_paint/android/icon_src.png"
RES = "/Users/macia/figurine_paint/android/app/src/main/res"
im = Image.open(SRC).convert("RGBA")
w, h = im.size
side = int(max(w, h) * 1.06)
canvas = Image.new("RGBA", (side, side), (255, 255, 255, 255))
canvas.alpha_composite(im, ((side - w) // 2, (side - h) // 2))
canvas = canvas.convert("RGB")

dens = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
for d, px in dens.items():
    out = os.path.join(RES, f"mipmap-{d}")
    os.makedirs(out, exist_ok=True)
    ic = canvas.resize((px, px), Image.LANCZOS)
    ic.save(os.path.join(out, "ic_launcher.png"))
    ic.save(os.path.join(out, "ic_launcher_round.png"))
    print("wrote", out, f"{px}px")
print("done")
