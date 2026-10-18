"""Demonstration multi-couleurs : recolore le chevalier en zones APPROXIMATIVES
(placees a l'oeil, pas precises) vers les couleurs Vallejo demandees, en
n'affectant QUE la figurine (fond bleu epargne). Sert a prouver que le pipeline
place bien plusieurs couleurs par region (vs tout-rouge). En vrai, l'utilisateur
peindra les zones au doigt dans l'app pour une precision parfaite."""
import sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, "/Users/macia/figurine_paint/scripts")
import recolor_vallejo as rv

pal = rv.load_palette()
src = "/Users/macia/figurine_paint/samples/knight.png"
img = Image.open(src).convert("RGB")
W, H = img.size
arr = np.array(img, np.float32) / 255.0
u8 = np.array(img)

# --- masque figurine (le fond est bleu uni) : bords connectes = fond ---
import cv2
border = np.concatenate([u8[0, :], u8[-1, :], u8[:, 0], u8[:, -1]]).reshape(-1, 3)
bgc = np.median(border, 0)
dist = np.linalg.norm(u8.astype(np.int16) - bgc, axis=2)
near = (dist < 55).astype(np.uint8)
_, lab = cv2.connectedComponents(near)
bl = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1]); bl.discard(0)
bg = np.isin(lab, list(bl)).astype(np.uint8)
fg = (1 - bg).astype(np.uint8)
fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(np.float32)
print("fg%", round(100 * float(fg.mean()), 1))


def ell(cx, cy, rx, ry):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([(cx - rx) * W, (cy - ry) * H, (cx + rx) * W, (cy + ry) * H], fill=255)
    return (np.array(m, np.float32) / 255.0 > 0.5).astype(np.float32) * fg


def rect(x0, y0, x1, y1):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rectangle([x0 * W, y0 * H, x1 * W, y1 * H], fill=255)
    return (np.array(m, np.float32) / 255.0 > 0.5).astype(np.float32) * fg


zones = [
    ("69.008", ell(0.50, 0.46, 0.34, 0.35)),   # armure ROUGE (corps/jambes)
    ("69.019", ell(0.24, 0.52, 0.17, 0.30)),   # cape BLEUE (cote gauche)
    ("69.037", rect(0.0, 0.87, 1.0, 1.0)),     # socle GRIS (bas)
    ("69.001", ell(0.52, 0.09, 0.07, 0.07)),   # plume BLANCHE (sommet)
]
owner = np.full((H, W), -1, np.int32)
for i, (code, m) in enumerate(zones):
    owner[m > 0.5] = i  # derniere zone gagne
out = arr.copy()
for i, (code, m) in enumerate(zones):
    fm = (owner == i).astype(np.float32)
    if fm.sum() < 10:
        print("zone vide", code); continue
    tgt = rv.get_rgb(code, pal) / 255.0
    out, cover = rv.recolor_region(out, fm, rv.feather_mask(fm, 3), tgt)
    print(code, pal[code].get("name", ""), "cover%", round(float(cover) * 100, 2))
Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save("/tmp/knight_recolored.png")
print("saved /tmp/knight_recolored.png", (W, H))
