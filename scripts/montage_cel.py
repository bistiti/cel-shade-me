from PIL import Image, ImageDraw
import numpy as np

paths = [("Resine nue", "/Users/macia/figurine_paint/samples/fig1.jpg"),
         ("Kontext doux", "/tmp/fig1_kontext.png"),
         ("Kontext CEL-SHADING", "/tmp/fig1_cel.png")]
H = 680
tiles = []
for label, p in paths:
    im = Image.open(p).convert("RGB")
    w = int(im.width * H / im.height)
    im = im.resize((w, H))
    tile = Image.new("RGB", (w, H + 30), (18, 18, 18))
    tile.paste(im, (0, 30))
    ImageDraw.Draw(tile).text((8, 9), label, fill=(255, 255, 255))
    tiles.append(tile)
W = sum(t.width for t in tiles) + 16 * (len(tiles) - 1)
out = Image.new("RGB", (W, H + 30), (18, 18, 18))
x = 0
for t in tiles:
    out.paste(t, (x, 0)); x += t.width + 16
out.save("/tmp/fig1_cel_compare.png")

a = np.array(Image.open("/tmp/fig1_cel.png").convert("RGB"))
print("cel dims", Image.open("/tmp/fig1_cel.png").size,
      "meanRGB", a.reshape(-1, 3).mean(0).round(1).tolist(),
      "std", round(float(a.std()), 1))
print("montage -> /tmp/fig1_cel_compare.png")
