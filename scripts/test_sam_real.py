import os
import numpy as np, cv2, torch
from PIL import Image
from segment_anything import sam_model_registry, SamPredictor

ckpt = "/Users/macia/figurine_paint/models/sam_vit_b_01ec64.pth"
dev = "mps" if torch.backends.mps.is_available() else "cpu"
sam = sam_model_registry["vit_b"](checkpoint=ckpt).to(dev)
pred = SamPredictor(sam)
os.makedirs("/tmp/seg/real", exist_ok=True)


def foreground(arr):  # fond noir -> fg = pixels non sombres
    L = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    fg = (L > 28).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab = cv2.connectedComponents(fg)
    if n > 2:
        fg = (lab == 1 + int(np.argmax([(lab == i).sum() for i in range(1, n)]))).astype(np.uint8)
    return fg


def seeds_from_silhouette(fg):
    ys, xs = np.where(fg > 0)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    h = y1 - y0
    s = {}
    for name, fr in [("tete", 0.12), ("torse", 0.35), ("hanches", 0.55), ("jambes", 0.78), ("socle", 0.95)]:
        yy = int(y0 + fr * h)
        band = fg[max(y0, yy - 6):yy + 6]
        col = np.where(band.any(0))[0]
        if col.size:
            s[name] = (float((col.min() + col.max()) / 2) / fg.shape[1], yy / fg.shape[0])
    ymid = int(y0 + 0.45 * h)
    band = fg[max(y0, ymid - 6):ymid + 6]
    col = np.where(band.any(0))[0]
    if col.size:
        s["bras_g"] = (float(col.min() + 4) / fg.shape[1], ymid / fg.shape[0])
        s["bras_d"] = (float(col.max() - 4) / fg.shape[1], ymid / fg.shape[0])
    return s


def choose(masks, scores, fg):
    fga = fg.sum() + 1e-6
    cands = [((m & (fg > 0)).sum() / fga, float(s), m) for m, s in zip(masks, scores)]
    part = [c for c in cands if 0.05 <= c[0] <= 0.55 and c[1] >= 0.80]
    return (min(part, key=lambda c: c[0]) if part else max(cands, key=lambda c: c[1])), cands


for i in range(1, 5):
    p = f"/Users/macia/figurine_paint/samples/fig{i}.jpg"
    arr = np.array(Image.open(p).convert("RGB"))
    fg = foreground(arr)
    pred.set_image(arr)
    H, W = arr.shape[:2]
    seeds = seeds_from_silhouette(fg)
    print(f"\n=== fig{i}  fg={round(fg.mean()*100,1)}%  seeds={list(seeds)} ===")
    tiles = []
    for name, (sx, sy) in seeds.items():
        masks, scores, _ = pred.predict(point_coords=np.array([[sx * W, sy * H]]),
                                        point_labels=np.array([1]), multimask_output=True)
        (fcov, sc, m), cands = choose(masks, scores, fg)
        ladder = " ".join(f"{round(c[0]*100)}%/{round(c[1],2)}" for c in cands)
        print(f"  {name:8} ladder[{ladder}] -> {round(fcov*100,1)}% fg")
        o = arr.copy()
        o[m] = (0.45 * o[m] + np.array([0, 0, 150])).clip(0, 255).astype(np.uint8)
        cnt, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(o, cnt, -1, (0, 255, 255), 3)
        cv2.circle(o, (int(sx * W), int(sy * H)), 10, (255, 128, 0), -1)
        cv2.putText(o, f"{name} {round(fcov*100)}%", (8, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        tiles.append(cv2.resize(o, (360, 360)))
    row = np.concatenate(tiles, 1)
    Image.fromarray(row).save(f"/tmp/seg/real/fig{i}_sam.png")
print("\nsaved montages /tmp/seg/real/fig*_sam.png")
