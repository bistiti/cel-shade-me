import sys, os, io, glob, time, json, urllib.request
import numpy as np
from PIL import Image
sys.path.insert(0, "/Users/macia/figurine_paint/scripts")
import recolor_vallejo as rv
import segment_region as sr

PROJ = "/Users/macia/figurine_paint"
pal = rv.load_palette()
B = "----b"


def post(url, fields, filep):
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{B}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    body.write(f"--{B}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"i.png\"\r\nContent-Type: image/png\r\n\r\n".encode())
    body.write(open(filep, "rb").read()); body.write(f"\r\n--{B}--\r\n".encode())
    req = urllib.request.Request(url, data=body.getvalue(),
                                 headers={"Content-Type": f"multipart/form-data; boundary={B}"})
    return urllib.request.urlopen(req, timeout=300).read()


def dl(u, out):
    open(out, "wb").write(urllib.request.urlopen("http://127.0.0.1:8000" + u, timeout=60).read())

# ---- A) reproduire la reference gobelin jaune, recette EXACTE de COLOR.md ----
src = None
for c in glob.glob(os.path.join(PROJ, "output/palettes_v2/*")):
    if "gobelin_souriant" in c or os.path.basename(c).startswith("05"):
        src = c; break
print("05 source:", src)
if src:
    rec = "/tmp/repro_05_recolor.png"
    rv.recolor_image(src, rec, [{"source": {"type": "hue", "center": 40, "width": 40, "min_sat": 0.45,
                                             "min_val": 0.12, "roi": [0, 0, 1, 0.72]},
                                  "target_code": "69.054", "strength": 1.0, "feather": 2}], pal)
    t = time.time()
    out = post("http://127.0.0.1:8000/paint",
               {"prompt": "hand-painted resin tabletop miniature, grinning goblin, fluorescent yellow matte "
                          "acrylic skin with black markings, Vallejo cel-shading box-art, studio macro "
                          "photography, shallow depth of field, neutral gradient background",
                "steps": "26", "size": "704", "strength": "0.55", "cn_scale": "0.9",
                "guidance": "7.0", "seed": "42"}, rec)
    open("/tmp/repro_05.png", "wb").write(out)
    print("repro_05.png", len(out), "bytes", round(time.time() - t, 1), "s")

# ---- B) figurine NUE via le CHEMIN DE L'APP corrige (/recolor_strokes finish) ----
zones = [{"code": "69.054", "role": "corps", "strokes": [
            {"pts": [[0.5, 0.28], [0.5, 0.5], [0.5, 0.72]], "r": 0.15},
            {"pts": [[0.36, 0.46], [0.64, 0.46]], "r": 0.11}]},
         {"code": "69.030", "role": "socle", "strokes": [{"pts": [[0.4, 0.93], [0.6, 0.93]], "r": 0.05}]}]
t = time.time()
resp = post("http://127.0.0.1:8000/recolor_strokes",
            {"zones": json.dumps(zones), "finish": "true"}, os.path.join(PROJ, "samples/fig1.jpg"))
d = json.loads(resp)
print("app job", d.get("id"), "paint:", (d.get("paint") or {}).get("url"), round(time.time() - t, 1), "s")
if d.get("paint"):
    dl(d["paint"]["url"], "/tmp/fig1_app.png")
    print("fig1_app.png saved; prompt used:", d["paint"]["prompt"][:120])
dl(d["recolor"]["url"], "/tmp/fig1_app_recolor.png")
