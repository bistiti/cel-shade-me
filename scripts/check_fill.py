import json, numpy as np, cv2
from PIL import Image

def figure_mask(u8):
    h, w = u8.shape[:2]
    img = np.ascontiguousarray(u8[:, :, ::-1])
    outer = np.zeros((h, w), np.uint8)
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        m = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(img, m, (sx, sy), 0, loDiff=(8,) * 3, upDiff=(8,) * 3,
                      flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY)
        outer |= m[1:-1, 1:-1]
    bgpix = u8[outer > 0].astype(np.float32)
    idx = np.random.choice(len(bgpix), min(5000, len(bgpix)), replace=False)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, _, centers = cv2.kmeans(bgpix[idx], 5, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    flat = u8.reshape(-1, 3).astype(np.float32)
    dmin = np.min(np.stack([np.linalg.norm(flat - c, axis=1) for c in centers], 1), 1)
    colbg = (dmin.reshape(h, w) < 40).astype(np.uint8)
    bg = ((outer | colbg) > 0).astype(np.uint8)
    fg = cv2.morphologyEx((1 - bg).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return fg

job = json.load(open('/tmp/fill_resp.json'))['id']
orig = np.array(Image.open('samples/knight.png').convert('RGB'))
rec = np.array(Image.open(f'output/app/{job}/recolor.png').convert('RGB'))
if rec.shape != orig.shape:
    rec = cv2.resize(rec, (orig.shape[1], orig.shape[0]))
fg = figure_mask(orig)
diff = np.linalg.norm(rec.astype(int) - orig.astype(int), axis=2) > 40
changed_bg = diff & (fg == 0)                       # pixels hors figure qui ont change
far = cv2.erode((fg == 0).astype(np.uint8), np.ones((13, 13), np.uint8))  # fond a >6px de la figure
leak_far = int((changed_bg & (far > 0)).sum())      # vraies fuites (poches/fond), pas l'anneau
print("changed hors-figure:", int(changed_bg.sum()),
      "| dont LOIN du bord (>6px) =", leak_far, "(poches/fond ; ~0 vise)")
vis = orig.copy(); vis[changed_bg] = [0, 255, 0]
Image.fromarray(vis).save('/tmp/leak_vis.png')
print("overlay -> /tmp/leak_vis.png")
