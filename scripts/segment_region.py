"""Segmentation par CONTOURS pour figurine mono-couleur (resine / sous-couche).

Un clic (seed) -> la region de la piece situee sous le doigt, delimitee par :
  - les aretes du sculpt (gradient de luminance),
  - les creux sombres entre pieces (chapeau noir / blackhat),
  - la silhouette (figurine vs fond).
Aucune dependance a la COULEUR : marche meme quand tout le modele est d'un seul
ton (ce que la selection par teinte ne peut pas faire). 100% local : cv2 + numpy.
"""
import cv2
import numpy as np


def luminance(arr01):
    return 0.299 * arr01[..., 0] + 0.587 * arr01[..., 1] + 0.114 * arr01[..., 2]


def foreground_mask(arr01):
    """Figurine vs fond : distance a la couleur mediane des 4 coins, puis on
    garde la plus grande composante connexe."""
    H, W = arr01.shape[:2]
    k = max(4, min(H, W) // 20)
    corners = np.concatenate([
        arr01[:k, :k].reshape(-1, 3), arr01[:k, -k:].reshape(-1, 3),
        arr01[-k:, :k].reshape(-1, 3), arr01[-k:, -k:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    dist = np.sqrt(((arr01 - bg) ** 2).sum(-1))
    fg = (dist > 0.12).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    n, lab = cv2.connectedComponents(fg)
    if n > 2:
        sizes = [(lab == i).sum() for i in range(1, n)]
        fg = (lab == 1 + int(np.argmax(sizes))).astype(np.uint8)
    return fg


def barrier(arr01, sensitivity=0.5):
    """Murs infranchissables = aretes (gradient) OU creux sombres (blackhat).
    sensitivity 0..1 : plus haute = plus de murs = regions plus petites."""
    g = (np.clip(luminance(arr01), 0, 1) * 255).astype(np.uint8)
    g = cv2.GaussianBlur(g, (0, 0), 1.2)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    mag /= (mag.max() + 1e-6)
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))).astype(np.float32)
    bh /= (bh.max() + 1e-6)
    thr_g = float(np.interp(sensitivity, [0, 1], [0.22, 0.05]))
    thr_b = float(np.interp(sensitivity, [0, 1], [0.55, 0.18]))
    bar = ((mag >= thr_g) | (bh >= thr_b)).astype(np.uint8)
    bar = cv2.morphologyEx(bar, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    return bar


def region_from_seed(arr01, sx, sy, sensitivity=0.5, use_fg=True, grow=2):
    """Masque (float 0/1) de la piece contenant le point normalise (sx, sy)."""
    H, W = arr01.shape[:2]
    fg = foreground_mask(arr01) if use_fg else np.ones((H, W), np.uint8)
    walk = ((barrier(arr01, sensitivity) == 0).astype(np.uint8)) * fg
    px = min(max(int(round(sx * (W - 1))), 0), W - 1)
    py = min(max(int(round(sy * (H - 1))), 0), H - 1)
    if walk[py, px] == 0:  # seed tombe sur un mur -> plus proche pixel libre
        found = False
        for rr in range(1, 14):
            y0, y1 = max(0, py - rr), min(H, py + rr + 1)
            x0, x1 = max(0, px - rr), min(W, px + rr + 1)
            sub = walk[y0:y1, x0:x1]
            if sub.any():
                ys, xs = np.where(sub > 0)
                py, px = y0 + int(ys[0]), x0 + int(xs[0]); found = True; break
        if not found:
            return np.zeros((H, W), np.float32)
    n, lab = cv2.connectedComponents(walk, connectivity=4)
    region = (lab == lab[py, px]).astype(np.uint8)
    if grow > 0:
        region = cv2.dilate(region, np.ones((3, 3), np.uint8), iterations=grow)
    region = cv2.morphologyEx(region, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    if use_fg:
        region = region * fg
    return region.astype(np.float32)
