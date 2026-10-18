#!/usr/bin/env python3
"""
recolor_vallejo.py — Recoloration locale directe d'une figurine vers des
couleurs Vallejo Mecha Color EXACTES, en préservant l'ombrage peint.

MÉTHODE (espace CIELab) :
  On sélectionne une région (par teinte HSV et/ou zone spatiale), puis on
  TRANSLATE la moyenne Lab de cette région vers la couleur Vallejo cible.
  Chaque pixel conserve sa variation locale (ombres, lumières, speckles) :
  seul le CENTRE colorimétrique devient exactement la couleur Vallejo.
  → Ton cible fidèle + aspect peint conservé. Instantané, 100% local, sans GPU.

Dépendances : numpy, Pillow. Aucun réseau, aucun modèle.

USAGE CLI :
  python recolor_vallejo.py --list
  python recolor_vallejo.py --swatch 69.008
  python recolor_vallejo.py --input in.png --output out.png \
      --map 'hue:5:14:69.008:1.0:sat0.45:val0.12'          # teinte rouge
  # ROI spatiale (fractions 0-1 : x0,y0,x1,y1) pour limiter/exclure une zone :
      --map 'hue:5:14:69.008:1.0:sat0.45:roi0,0,1,0.72'     # haut de l'image

USAGE MODULE :
  from recolor_vallejo import recolor_image
  recolor_image("in.png","out.png",[
    {"source":{"type":"hue","center":5,"width":14,"min_sat":0.45,"min_val":0.12,
               "roi":[0,0,1,0.72]},
     "target_code":"69.008","strength":1.0,"feather":2}])
"""
import argparse
import json
import os
import numpy as np
from PIL import Image, ImageFilter

PALETTE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "vallejo_mecha_palette.json")


# ----------------------------- Palette -----------------------------
def load_palette(path=PALETTE_PATH):
    with open(path) as f:
        return json.load(f)


def get_rgb(code, palette=None):
    palette = palette or load_palette()
    if code not in palette:
        raise KeyError(f"Code Vallejo inconnu: {code}")
    return np.array(palette[code]["rgb"], dtype=np.float32)


# -------------------- HSV (pour le masque uniquement) --------------
def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.max(rgb, axis=-1); mn = np.min(rgb, axis=-1)
    diff = mx - mn
    safe = np.where(diff > 1e-6, diff, 1.0)       # évite division par 0
    h = np.zeros_like(mx)
    rm = (mx == r) & (diff > 1e-6); h[rm] = (60 * ((g - b) / safe)[rm]) % 360
    gm = (mx == g) & (diff > 1e-6); h[gm] = (60 * ((b - r) / safe)[gm] + 120) % 360
    bm = (mx == b) & (diff > 1e-6); h[bm] = (60 * ((r - g) / safe)[bm] + 240) % 360
    s = np.where(mx > 1e-6, diff / np.where(mx > 1e-6, mx, 1.0), 0.0)
    return np.stack([h / 360.0, s, mx], axis=-1)


# ----------------------------- CIELab ------------------------------
_M_RGB2XYZ = np.array([[0.4124, 0.3576, 0.1805],
                       [0.2126, 0.7152, 0.0722],
                       [0.0193, 0.1192, 0.9505]], dtype=np.float32)
_M_XYZ2RGB = np.linalg.inv(_M_RGB2XYZ).astype(np.float32)
_WHITE = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)


def _srgb_to_linear(c):
    return np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)


def _linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c > 0.0031308, 1.055 * (c ** (1 / 2.4)) - 0.055, 12.92 * c)


def rgb_to_lab(rgb01):
    lin = _srgb_to_linear(rgb01)
    xyz = lin @ _M_RGB2XYZ.T
    xyz = xyz / _WHITE
    d = 6 / 29
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def lab_to_rgb(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    d = 6 / 29
    def inv(t): return np.where(t > d, t ** 3, 3 * d * d * (t - 4 / 29))
    xyz = np.stack([inv(fx), inv(fy), inv(fz)], axis=-1) * _WHITE
    lin = xyz @ _M_XYZ2RGB.T
    return np.clip(_linear_to_srgb(lin), 0, 1)


# ----------------------------- Masques -----------------------------
def _apply_roi(mask, roi, exclude=False):
    if not roi:
        return mask
    H, W = mask.shape
    x0, y0, x1, y1 = roi
    box = np.zeros_like(mask)
    box[int(y0*H):int(y1*H), int(x0*W):int(x1*W)] = 1.0
    return mask * (1 - box) if exclude else mask * box


def build_mask(arr01, source):
    hsv = rgb_to_hsv(arr01)
    H = hsv[..., 0] * 360.0; S = hsv[..., 1]; V = hsv[..., 2]
    if source["type"] == "hue":
        c = source["center"] % 360; w = source["width"]
        dh = np.abs(((H - c + 180) % 360) - 180)
        m = ((dh <= w) &
             (S >= source.get("min_sat", 0.25)) &
             (S <= source.get("max_sat", 1.01)) &
             (V >= source.get("min_val", 0.12)) &
             (V <= source.get("max_val", 1.01))).astype(np.float32)
    elif source["type"] == "rgb":
        tgt = np.array(source["rgb"], dtype=np.float32) / 255.0
        dist = np.sqrt(((arr01 - tgt) ** 2).sum(axis=-1)) * 255.0
        m = (dist <= source.get("tol", 50)).astype(np.float32)
    else:
        raise ValueError(f"source.type inconnu: {source['type']}")
    m = _apply_roi(m, source.get("roi"), exclude=False)
    m = _apply_roi(m, source.get("exclude_roi"), exclude=True)
    return m


def feather_mask(mask, radius):
    if radius and radius > 0:
        im = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        im = im.filter(ImageFilter.GaussianBlur(radius))
        return np.array(im, dtype=np.float32) / 255.0
    return mask


# --------------------------- Recoloration --------------------------
def recolor_region(arr01, mask_hard, mask_soft, target_rgb01, strength=1.0,
                   keep_chroma=0.0):
    """
    Translate la moyenne Lab de la région (mask_hard) vers la cible, et
    applique le décalage pondéré par mask_soft (bords adoucis).
    keep_chroma 0..1 : 0 = couleur cible pure ; >0 garde un peu du a,b d'origine.
    """
    lab = rgb_to_lab(arr01)
    t_lab = rgb_to_lab(target_rgb01.reshape(1, 1, 3))[0, 0]
    sel = mask_hard > 0.5
    if sel.sum() < 10:
        return arr01, 0.0
    mean_lab = lab[sel].mean(axis=0)
    delta = (t_lab - mean_lab) * strength
    # On garde optionnellement une part de la chroma d'origine (a,b)
    delta[1] *= (1 - keep_chroma)
    delta[2] *= (1 - keep_chroma)
    out = lab + mask_soft[..., None] * delta
    return lab_to_rgb(out), float(sel.mean())


def recolor_image(input_path, output_path, mappings, palette=None):
    palette = palette or load_palette()
    img = Image.open(input_path).convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0
    report = []
    for mp in mappings:
        tgt = get_rgb(mp["target_code"], palette) / 255.0
        hard = build_mask(arr, mp["source"])
        soft = feather_mask(hard, mp.get("feather", 2))
        arr, cover = recolor_region(
            arr, hard, soft, tgt,
            strength=mp.get("strength", 1.0),
            keep_chroma=mp.get("keep_chroma", 0.0),
        )
        report.append({
            "target_code": mp["target_code"],
            "target_hex": palette[mp["target_code"]]["hex"],
            "coverage_pct": round(cover * 100, 2),
        })
    out = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    out.save(output_path)
    return {"output": output_path, "applied": report}


# ------------------------------- CLI -------------------------------
def _parse_map(s):
    """
    'hue:CENTER:WIDTH:CODE[:STRENGTH][:satX][:valX][:roiX0,Y0,X1,Y1][:exX0,Y0,X1,Y1]'
    'rgb:R,G,B:TOL:CODE[:STRENGTH][:roi...][:ex...]'
    """
    parts = s.split(":")
    kind = parts[0]
    src = {"type": kind}
    if kind == "hue":
        src.update(center=float(parts[1]), width=float(parts[2]),
                   min_sat=0.25, min_val=0.12)
        code = parts[3]; rest = parts[4:]
    elif kind == "rgb":
        src.update(rgb=[int(x) for x in parts[1].split(",")], tol=float(parts[2]))
        code = parts[3]; rest = parts[4:]
    else:
        raise ValueError(f"map type inconnu: {kind}")
    strength = 1.0
    for tok in rest:
        if tok.startswith("sat"): src["min_sat"] = float(tok[3:])
        elif tok.startswith("val"): src["min_val"] = float(tok[3:])
        elif tok.startswith("roi"): src["roi"] = [float(x) for x in tok[3:].split(",")]
        elif tok.startswith("ex"): src["exclude_roi"] = [float(x) for x in tok[2:].split(",")]
        else:
            try: strength = float(tok)
            except ValueError: pass
    return {"source": src, "target_code": code, "strength": strength, "feather": 2}


def main():
    ap = argparse.ArgumentParser(description="Recoloration Vallejo locale (Lab)")
    ap.add_argument("--input"); ap.add_argument("--output")
    ap.add_argument("--map", action="append", default=[], dest="maps")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--swatch")
    args = ap.parse_args()
    palette = load_palette()
    if args.list:
        for code in sorted(palette):
            p = palette[code]
            print(f"{code}  {p['hex']}  rgb{tuple(p['rgb'])}  {p['name']}")
        return
    if args.swatch:
        p = palette[args.swatch]
        print(f"{args.swatch}: {p['hex']} rgb{tuple(p['rgb'])} {p['name']}")
        return
    if not (args.input and args.output and args.maps):
        ap.error("--input, --output et au moins un --map requis")
    rep = recolor_image(args.input, args.output, [_parse_map(m) for m in args.maps], palette)
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
