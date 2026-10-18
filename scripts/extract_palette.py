#!/usr/bin/env python3
"""
Extrait les couleurs exactes (hex RGB) de la planche Vallejo Mecha Color
et les mappe aux codes officiels. Vérifie contre des ancres connues.
"""
import json
import os
import numpy as np
from PIL import Image

SRC = "/Users/macia/.hermes/cache/images/img_ec70523c494e.jpeg"
OUT = "/Users/macia/figurine_paint/data/vallejo_mecha_palette.json"

CODES = [
    ["69.001","69.002","69.003","69.004","69.005","69.006","69.007","69.008","69.009","69.010"],
    ["69.011","69.012","69.013","69.014","69.015","69.016","69.017","69.018","69.019","69.020"],
    ["69.021","69.022","69.023","69.024","69.025","69.026","69.027","69.028","69.029","69.030"],
    ["69.031","69.032","69.033","69.034","69.035","69.036","69.037","69.038","69.039","69.040"],
    ["69.041","69.042","69.054","69.055","69.056","69.057","69.058","69.059","69.060","69.061"],
    ["69.062","69.063","69.064","69.065","69.066","69.067","69.068","69.505","69.507","69.515"],
    ["69.518","69.521","69.522","69.813","69.814","69.817","69.818","69.821","70.640","70.641"],
    ["70.642","70.643","70.644","69.701","69.702","69.703","71.261","71.262","73.212","73.214"],
]

# Noms usuels (Vallejo Mecha Color officiels) pour les codes clés du projet
NAMES = {
    "69.001":"White","69.002":"Light Grey","69.008":"Red","69.011":"Dark Red",
    "69.017":"Sky Blue","69.041":"Dark Grey","69.042":"Black","69.054":"Fluo Yellow",
    "69.055":"Fluo Orange","69.056":"Fluo Magenta","69.057":"Fluo Green",
    "69.058":"Silver","69.059":"Gold","69.060":"Bronze","69.817":"Dark Flesh/Red",
}

img = Image.open(SRC).convert("RGB")
W, H = img.size
arr = np.array(img, dtype=np.uint8)

not_white = ~((arr[:,:,0] > 235) & (arr[:,:,1] > 235) & (arr[:,:,2] > 235))
row_density = not_white.sum(axis=1)
active = row_density > 0.15 * W

bands = []
start = None
for y in range(H):
    if active[y] and start is None:
        start = y
    elif not active[y] and start is not None:
        bands.append((start, y-1)); start = None
if start is not None:
    bands.append((start, H-1))

# Bandes de pastilles = les plus hautes (h>18)
swatch_bands = [(a,b) for (a,b) in bands if (b-a) > 18]
assert len(swatch_bands) == 8, f"Attendu 8 lignes, trouvé {len(swatch_bands)}"

def detect_columns(y0, y1):
    """Projette sur X dans la bande [y0,y1] pour trouver 10 centres de colonnes."""
    band = not_white[y0:y1+1, :]
    col_density = band.sum(axis=0)
    active_c = col_density > 0.25 * (y1-y0+1)
    cols = []
    s = None
    for x in range(W):
        if active_c[x] and s is None:
            s = x
        elif not active_c[x] and s is not None:
            cols.append((s, x-1)); s = None
    if s is not None:
        cols.append((s, W-1))
    # Garder les segments assez larges
    cols = [(a,b) for (a,b) in cols if (b-a) > 20]
    return cols

def sample_swatch(y0, y1, x0, x1):
    """Couleur médiane de la zone centrale de la pastille (évite bords/ombres)."""
    cy0 = y0 + int((y1-y0)*0.25); cy1 = y0 + int((y1-y0)*0.75)
    cx0 = x0 + int((x1-x0)*0.30); cx1 = x0 + int((x1-x0)*0.70)
    patch = arr[cy0:cy1+1, cx0:cx1+1, :].reshape(-1,3)
    # Médiane (robuste au dégradé métallique)
    med = np.median(patch, axis=0).astype(int)
    return int(med[0]), int(med[1]), int(med[2])

palette = {}
for ri, (y0, y1) in enumerate(swatch_bands):
    cols = detect_columns(y0, y1)
    if len(cols) != 10:
        # Repli: grille régulière sur la largeur utile
        xs = np.linspace(40, W-40, 11)
        cols = [(int(xs[i]), int(xs[i+1])) for i in range(10)]
    for ci, (x0, x1) in enumerate(cols[:10]):
        code = CODES[ri][ci]
        r,g,b = sample_swatch(y0, y1, x0, x1)
        palette[code] = {
            "hex": f"#{r:02x}{g:02x}{b:02x}",
            "rgb": [r,g,b],
            "name": NAMES.get(code, ""),
            "row": ri, "col": ci,
        }

# --- VÉRIFICATION des ancres connues ---
def close(code, target, tol=45):
    rgb = np.array(palette[code]["rgb"])
    d = np.abs(rgb - np.array(target)).max()
    return d <= tol, d

checks = {
    "69.001": (245,245,245),  # blanc
    "69.042": (25,25,25),     # noir
    "69.008": (200,40,35),    # rouge
    "69.057": (30,160,60),    # vert fluo
    "69.054": (220,220,30),   # jaune fluo
}
print("=== VÉRIFICATION ANCRES ===")
all_ok = True
for code, tgt in checks.items():
    ok, d = close(code, tgt)
    status = "OK " if ok else "!! "
    if not ok: all_ok = False
    print(f"{status}{code}: {palette[code]['hex']} rgb={palette[code]['rgb']} (ecart max={d})")

print(f"\nTotal pastilles: {len(palette)}")
print("Ancres toutes correctes:", all_ok)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(palette, f, indent=2, ensure_ascii=False)
print(f"\nÉcrit: {OUT}")
