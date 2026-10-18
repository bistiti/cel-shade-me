import numpy as np, cv2
from PIL import Image

rec = np.array(Image.open('output/app/914907dd30d3/recolor.png').convert('RGB'))
fin = np.array(Image.open('output/app/914907dd30d3/final.png').convert('RGB'))
H, W = fin.shape[:2]
if rec.shape[:2] != (H, W):
    rec = cv2.resize(rec, (W, H), interpolation=cv2.INTER_AREA)
RED = np.array([165, 31, 28])
rec_red = np.linalg.norm(rec.astype(int) - RED, axis=2) < 90      # figure+socle peints dans le recolor
rec_bg = ~rec_red                                                 # fond+poches (deja prouve propre)
fin_red = np.linalg.norm(fin.astype(int) - RED, axis=2) < 90
leak = rec_bg & fin_red                                           # fond du recolor devenu rouge dans le final
print("fond (recolor, hors figure/socle):", int(rec_bg.sum()))
print("  devenu ROUGE dans le final:", int(leak.sum()),
      "=", round(100 * leak.sum() / max(1, rec_bg.sum()), 2), "% (0 = render preserve le fond)")
# pour info, les traits noirs
dark = np.linalg.norm(fin.astype(int), axis=2) < 70
print("traits noirs (final):", round(100 * float(dark.mean()), 1), "%")
