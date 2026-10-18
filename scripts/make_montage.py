import numpy as np
from PIL import Image

def load_h(p, h=620):
    im = Image.open(p).convert("RGB")
    w = int(im.width * h / im.height)
    return np.array(im.resize((w, h)))

orig = load_h("/Users/macia/figurine_paint/samples/fig1.jpg")
reco = load_h("/tmp/fig1_recolor.png")
pnt = load_h("/tmp/fig1_painted.png")
gap = np.full((620, 8, 3), 20, np.uint8)
row = np.concatenate([orig, gap, reco, gap, pnt], axis=1)
Image.fromarray(row).save("/tmp/fig1_compare.png")
print("saved /tmp/fig1_compare.png", row.shape)
