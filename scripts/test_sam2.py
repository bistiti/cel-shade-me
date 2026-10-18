import os
import numpy as np, cv2, torch
from PIL import Image
from segment_anything import sam_model_registry, SamPredictor

ckpt = "/Users/macia/figurine_paint/models/sam_vit_b_01ec64.pth"
dev = "mps" if torch.backends.mps.is_available() else "cpu"
sam = sam_model_registry["vit_b"](checkpoint=ckpt).to(dev)
pred = SamPredictor(sam)

arr = np.array(Image.open("/Users/macia/figurine_paint/output/controlnet/01_gobelin_cn.png").convert("RGB"))
L = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]).astype(np.uint8)
primer = np.stack([L, L, L], -1)
pred.set_image(primer)
H, W = primer.shape[:2]

# silhouette (pour mesurer "part vs objet entier")
bg = np.median(np.concatenate([primer[:20, :20].reshape(-1, 3), primer[:20, -20:].reshape(-1, 3)]), 0)
fg = (np.sqrt(((primer.astype(float) - bg) ** 2).sum(-1)) > 30)
fg_area = fg.mean()
print("foreground =", round(fg_area * 100, 1), "% de l'image\n")

seeds = {"casque": (0.5, 0.10), "tete": (0.5, 0.17), "torse": (0.44, 0.50),
         "bras_dr": (0.72, 0.50), "jambe": (0.46, 0.80), "socle": (0.5, 0.95)}


def choose(masks, scores):
    # part-aware : plus petit masque dont la couverture DU FOREGROUND est dans
    # [3%,55%] et score>=0.80 ; sinon le mieux note.
    cands = []
    for m, s in zip(masks, scores):
        fcov = (m & fg).sum() / (fg.sum() + 1e-6)
        cands.append((fcov, float(s), m))
    part = [(fc, s, m) for fc, s, m in cands if 0.03 <= fc <= 0.55 and s >= 0.80]
    if part:
        return min(part, key=lambda c: c[0])  # le plus petit "part-like"
    return max(cands, key=lambda c: c[1])      # fallback : meilleur score


tiles = []
for name, (sx, sy) in seeds.items():
    masks, scores, _ = pred.predict(point_coords=np.array([[sx * W, sy * H]]),
                                    point_labels=np.array([1]), multimask_output=True)
    ladder = [f"{round(float(m.mean())*100,1)}%/s{round(float(s),2)}" for m, s in zip(masks, scores)]
    fc, sc, m = choose(masks, scores)
    print(f"{name:8} 3-masques={ladder}  -> choisi {round(float(m.mean())*100,1)}% (fg {round(fc*100,1)}%)")
    o = primer.copy(); o[m] = (0.4 * o[m] + np.array([0, 0, 150])).clip(0, 255).astype(np.uint8)
    cnt, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(o, cnt, -1, (0, 255, 255), 2)
    cv2.circle(o, (int(sx * W), int(sy * H)), 7, (255, 128, 0), -1)
    cv2.putText(o, name, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    tiles.append(o)
Image.fromarray(np.concatenate(tiles, 1)).save("/tmp/seg/sam_chosen.png")
print("\nsaved /tmp/seg/sam_chosen.png")
