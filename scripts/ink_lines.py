"""Ajoute des TRAITS NOIRS nets facon cel-shading (ligne claire) sur un rendu
deja colorise : encre les aretes/creux INTERIEURS ; silhouette exterieure
optionnelle (l'utilisateur n'en veut pas par defaut).
Usage: python ink_lines.py IN.png OUT.png [thick=2] [exterior=0] [low=60] [high=150]"""
import sys, cv2, numpy as np
from PIL import Image

inp, out = sys.argv[1], sys.argv[2]
thick = int(sys.argv[3]) if len(sys.argv) > 3 else 2
exterior = (len(sys.argv) > 4 and sys.argv[4] == "1")
low = int(sys.argv[5]) if len(sys.argv) > 5 else 60
high = int(sys.argv[6]) if len(sys.argv) > 6 else 150

img = np.array(Image.open(inp).convert("RGB"))
gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

# Fond = couleur mediane des bords, pixels proches ET connectes a un bord.
border = np.concatenate([img[0, :], img[-1, :], img[:, 0], img[:, -1]]).reshape(-1, 3)
bgc = np.median(border, 0)
dist = np.linalg.norm(img.astype(np.int16) - bgc, axis=2)
near = (dist < 45).astype(np.uint8)
_, lab = cv2.connectedComponents(near)
bl = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
bl.discard(0)
bg = np.isin(lab, list(bl)).astype(np.uint8)
fg = (1 - bg).astype(np.uint8)
fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

edges = (cv2.Canny(gray, low, high) > 0).astype(np.uint8)
inside = (cv2.erode(fg, np.ones((3, 3), np.uint8), iterations=2) > 0).astype(np.uint8)
lines = edges * inside
if not exterior:
    ring = (cv2.morphologyEx(fg, cv2.MORPH_GRADIENT,
            np.ones((2 * thick + 3, 2 * thick + 3), np.uint8)) > 0).astype(np.uint8)
    lines = lines * (1 - ring)
else:
    sil = (cv2.morphologyEx(fg, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0).astype(np.uint8)
    lines = np.clip(lines + sil, 0, 1)
lines = cv2.dilate((lines * 255).astype(np.uint8), np.ones((thick, thick), np.uint8))
res = img.copy()
res[lines > 0] = (8, 8, 8)
Image.fromarray(res).save(out)
print("saved", out, "| fg%", round(100 * float(fg.mean()), 1), "| line px", int((lines > 0).sum()))
