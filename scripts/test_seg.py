import os, sys
import cv2
import numpy as np
from PIL import Image
sys.path.insert(0, "/Users/macia/figurine_paint/scripts")
import segment_region as sr

os.makedirs("/tmp/seg", exist_ok=True)
src = "/Users/macia/figurine_paint/output/controlnet/01_gobelin_cn.png"
arr = np.array(Image.open(src).convert("RGB"), np.float32) / 255.0

# proxy "resine unie" : on garde seulement la luminance (ombrage), albedo gris
L = np.clip(sr.luminance(arr), 0, 1)
primer = np.stack([L, L, L], -1)
Image.fromarray((primer * 255).astype(np.uint8)).save("/tmp/seg/primer.png")

seeds = {"tete": (0.5, 0.12), "torse": (0.5, 0.42), "bras_g": (0.24, 0.46), "socle": (0.5, 0.94)}


def overlay(base, region, sx, sy, label):
    o = (base.copy() * 255).astype(np.uint8)
    m = (region > 0.5)
    o[m] = (0.4 * o[m] + np.array([0, 0, 140])).clip(0, 255).astype(np.uint8)
    cnt, _ = cv2.findContours((region > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(o, cnt, -1, (0, 255, 255), 2)
    H, W = base.shape[:2]
    cv2.circle(o, (int(sx * W), int(sy * H)), 6, (255, 128, 0), -1)
    cv2.putText(o, label, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return o


for sens in [0.5, 0.75]:
    tiles = []
    for name, (sx, sy) in seeds.items():
        reg = sr.region_from_seed(primer, sx, sy, sensitivity=sens)
        cov = round(float((reg > 0.5).mean()) * 100, 1)
        tiles.append(overlay(primer, reg, sx, sy, f"{name} {cov}%"))
        print(f"sens={sens:<4} {name:<7}: {cov}%")
    Image.fromarray(np.concatenate(tiles, axis=1)).save(f"/tmp/seg/primer_sens{int(sens*100)}.png")
print("OK ->", os.listdir("/tmp/seg"))
