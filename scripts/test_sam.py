import os, sys, urllib.request, time
import numpy as np, cv2
from PIL import Image

MODELS = "/Users/macia/figurine_paint/models"
os.makedirs(MODELS, exist_ok=True)
os.makedirs("/tmp/seg", exist_ok=True)
ckpt = os.path.join(MODELS, "sam_vit_b_01ec64.pth")
url = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
if not os.path.exists(ckpt):
    print("download SAM ViT-B ...", flush=True)
    t = time.time(); urllib.request.urlretrieve(url, ckpt)
    print("  dl", round(time.time() - t, 1), "s", flush=True)
print("ckpt", os.path.getsize(ckpt) // 1_000_000, "MB", flush=True)

import torch
from segment_anything import sam_model_registry, SamPredictor
dev = "mps" if torch.backends.mps.is_available() else "cpu"
print("device", dev, flush=True)
sam = sam_model_registry["vit_b"](checkpoint=ckpt).to(dev)
pred = SamPredictor(sam)

src = "/Users/macia/figurine_paint/output/controlnet/01_gobelin_cn.png"
arr = np.array(Image.open(src).convert("RGB"))
L = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]).astype(np.uint8)
primer = np.stack([L, L, L], -1)
seeds = {"tete": (0.5, 0.12), "torse": (0.5, 0.42), "bras_g": (0.24, 0.46), "socle": (0.5, 0.94)}


def run(img, tag):
    t = time.time(); pred.set_image(img); emb = round(time.time() - t, 2)
    H, W = img.shape[:2]; tiles = []
    for name, (sx, sy) in seeds.items():
        masks, scores, _ = pred.predict(point_coords=np.array([[sx * W, sy * H]]),
                                        point_labels=np.array([1]), multimask_output=True)
        m = masks[int(np.argmax(scores))]
        cov = round(float(m.mean()) * 100, 1)
        o = img.copy(); o[m] = (0.4 * o[m] + np.array([0, 0, 140])).clip(0, 255).astype(np.uint8)
        cnt, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(o, cnt, -1, (0, 255, 255), 2)
        cv2.circle(o, (int(sx * W), int(sy * H)), 6, (255, 128, 0), -1)
        cv2.putText(o, f"{name} {cov}%", (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        tiles.append(o)
        print(f"{tag} set_image={emb}s {name}: {cov}% score={round(float(scores.max()),3)}", flush=True)
    Image.fromarray(np.concatenate(tiles, 1)).save(f"/tmp/seg/sam_{tag}.png")


run(primer, "primer")
run(arr, "color")
print("done")
