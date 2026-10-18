"""Cel-shading DETERMINISTE : posterise le rendu en N tons durs par couleur.
Prend la DIRECTION d'ombrage du rendu Kontext (sa luminance) mais la quantifie en
bandes dures (ombre / base / highlight), snappees sur des tons derives de la couleur
Vallejo. Donne un vrai look cel partout, pas seulement sur les details serres."""
import cv2, numpy as np, colorsys


def make_tones(base, n=3):
    r, g, b = [x / 255 for x in base]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if n == 3:
        sv = [(s, v * 0.5), (s, v), (max(0, s * 0.68), min(1, v * 1.5 + 0.12))]
    else:  # 4 bandes
        sv = [(s, v * 0.4), (s, v * 0.72), (s, v), (max(0, s * 0.68), min(1, v * 1.5 + 0.12))]
    out = []
    for ss, vv in sv:
        rr, gg, bb = colorsys.hsv_to_rgb(h, ss, vv)
        out.append([int(rr * 255), int(gg * 255), int(bb * 255)])
    return out


def figure_mask_dark(u8, dark_thr=30):
    """masque figure : floodFill du fond depuis les 4 coins (fond sombre/uni), PUIS
    retrait des POCHES de fond noir ENFERMEES par la figurine (entre les jambes, sous
    un bras) : tout pixel quasi-noir (3 canaux < dark_thr) est classe fond, meme
    encercle, car l'ombre reelle de la resine reste coloree (tan) et depasse ce seuil."""
    h, w = u8.shape[:2]
    img = np.ascontiguousarray(u8[:, :, ::-1])
    outer = np.zeros((h, w), np.uint8)
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        m = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(img, m, (sx, sy), 0, loDiff=(8,) * 3, upDiff=(8,) * 3,
                      flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY)
        outer |= m[1:-1, 1:-1]
    conn = (outer == 0)
    dark = (u8[:, :, 0] < dark_thr) & (u8[:, :, 1] < dark_thr) & (u8[:, :, 2] < dark_thr)
    fig = (conn & ~dark).astype(np.uint8)
    fig = cv2.morphologyEx(fig, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return fig


def posterize_cel(ren, base, fig=None, n=3, ink_low=25, ink_high=80, ink_thick=2):
    h, w = ren.shape[:2]
    if fig is None:
        fig = figure_mask_dark(ren)
    fig = (fig > 0)
    # luminance lissee (bilateral) pour des bandes propres sans bruit
    sm = cv2.bilateralFilter(ren, 7, 45, 45)
    gray = cv2.cvtColor(sm, cv2.COLOR_RGB2GRAY).astype(np.float32)
    Lf = gray[fig]
    if n == 3:
        ts = np.percentile(Lf, [42, 80])
    else:
        ts = np.percentile(Lf, [30, 58, 82])
    tones = make_tones(base, n)
    band = np.digitize(gray, ts)
    out = ren.copy()
    for i in range(n):
        m = fig & (band == i)
        out[m] = tones[i]
    # encrage : traits noirs dans les reliefs (Canny sur le rendu, DANS la figure)
    edges = cv2.Canny(cv2.cvtColor(ren, cv2.COLOR_RGB2GRAY), ink_low, ink_high) > 0
    inside = cv2.erode(fig.astype(np.uint8), np.ones((3, 3), np.uint8), 2) > 0
    ring = cv2.morphologyEx(fig.astype(np.uint8), cv2.MORPH_GRADIENT,
                            np.ones((2 * ink_thick + 3,) * 2, np.uint8)) > 0
    lines = (edges & inside & ~ring).astype(np.uint8)
    lines = cv2.dilate(lines * 255, np.ones((ink_thick, ink_thick), np.uint8)) > 0
    out[lines] = (8, 8, 8)
    return out, tones


if __name__ == "__main__":
    import sys
    from PIL import Image
    src = sys.argv[1] if len(sys.argv) > 1 else "output/app/fe63a555dc1b/render.png"
    base = [165, 31, 28]  # Vallejo 69.008
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    ren = np.array(Image.open(src).convert("RGB"))
    out, tones = posterize_cel(ren, base, n=n)
    Image.fromarray(out).save("/tmp/cel_hard.png")
    print("tons:", tones)
    # mesure : l'image doit maintenant avoir des tons DISCRETS (peu de valeurs)
    hsv = cv2.cvtColor(out, cv2.COLOR_RGB2HSV)
    red = (((hsv[..., 0] <= 12) | (hsv[..., 0] >= 165)) & (hsv[..., 1] > 60))
    vals = out[red].reshape(-1, 3)
    uniq = np.unique(vals, axis=0)
    print("couleurs rouges distinctes dans la figure:", len(uniq), "(cel = peu)")
    print("-> /tmp/cel_hard.png")
