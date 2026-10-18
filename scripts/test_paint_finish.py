import sys, os, io, json, hashlib, time, urllib.request
import numpy as np
from PIL import Image
sys.path.insert(0, "/Users/macia/figurine_paint/scripts")
import recolor_vallejo as rv
import segment_region as sr

PROJ = "/Users/macia/figurine_paint"
refs = ["/Users/macia/.hermes/cache/images/img_d21a25dcdf56.jpeg",
        "/Users/macia/.hermes/cache/images/img_3d0c3d7f9d5c.jpeg"]

# 1) comparer les references aux sorties ControlNet existantes (hash + taille)
def h(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:10]
cn_dir = os.path.join(PROJ, "output", "controlnet")
existing = {f: h(os.path.join(cn_dir, f)) for f in os.listdir(cn_dir) if f.endswith(".png")}
print("refs hash:", [h(r) for r in refs])
print("controlnet hashes:", existing)

# 2) recolor fig1 (schema facon demon jaune) : corps 69.054, bas 69.050, socle 69.030
pal = rv.load_palette()
arr = np.array(Image.open(os.path.join(PROJ, "samples/fig1.jpg")).convert("RGB"), np.float32) / 255
H, W = arr.shape[:2]
fg = sr.foreground_mask(arr)
yy = np.arange(H)[:, None] / H
zones = [(((fg > 0) & (yy < 0.62)).astype(np.float32), "69.054"),
         (((fg > 0) & (yy >= 0.62) & (yy < 0.82)).astype(np.float32), "69.050"),
         (((fg > 0) & (yy >= 0.82)).astype(np.float32), "69.030")]
out = arr.copy()
for m, code in zones:
    if code not in pal:
        print("CODE ABSENT", code); continue
    out, cov = rv.recolor_region(out, m, rv.feather_mask(m, 2), rv.get_rgb(code, pal) / 255)
    print("recolor", code, pal[code]["hex"], "cov", round(cov * 100, 1))
rec_path = "/tmp/fig1_recolor.png"
Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(rec_path)

# 3) finition peinte via le backend chaud (/paint), bons reglages
prompt = ("Professional studio macro photograph of a REAL physical hand-painted 32mm resin "
          "tabletop miniature on a round base, matte acrylic finish with painted shadows and "
          "highlights and subtle brush texture, soft studio lighting, shallow depth of field, "
          "dark neutral backdrop. Keep the EXACT same pose, sculpt, proportions and composition "
          "as the source. Looks like a real painted miniature photographed, not a digital illustration.")
import urllib.request
boundary = "----figb"
def post(url, fields, filep):
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    fb = open(filep, "rb").read()
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"r.png\"\r\nContent-Type: image/png\r\n\r\n".encode())
    body.write(fb); body.write(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(url, data=body.getvalue(),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return urllib.request.urlopen(req, timeout=300).read()

t = time.time()
resp = post("http://127.0.0.1:8000/paint",
            {"prompt": prompt, "steps": "26", "size": "704", "strength": "0.5",
             "cn_scale": "1.0", "guidance": "7.0", "seed": "42"}, rec_path)
print("paint bytes", len(resp), "in", round(time.time() - t, 1), "s")
open("/tmp/fig1_painted.png", "wb").write(resp)
try:
    im = Image.open("/tmp/fig1_painted.png"); print("painted image", im.size, im.mode)
except Exception as e:
    print("PAS une image:", resp[:200])
