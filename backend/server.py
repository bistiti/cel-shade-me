#!/usr/bin/env python
"""
server.py — Backend local de colorisation de figurines (Mac, 100% local).

Enveloppe les scripts VALIDES du projet (scripts/recolor_vallejo.py et
scripts/paint_controlnet.py) derriere une petite API HTTP. Multi-zones +
harmonies de couleur (ramenees a la ref Vallejo Mecha la plus proche).

Modele ControlNet/SD1.5 charge UNE fois (lazy), garde chaud. Aucun service en ligne.

Endpoints :
  GET  /                      redirige vers /app/
  GET  /app/                  client web mobile
  GET  /app/designs.html      maquettes de design
  GET  /health                etat + device
  GET  /palette               80 refs Vallejo Mecha
  GET  /harmony?code=&scheme= harmonies -> refs Vallejo (analogous, complementary,
                              split, triad, tetradic, square, monochromatic)
  POST /recolor   (multipart)  file + map(s) OU code -> image/png
  POST /paint     (multipart)  file + prompt/params  -> image/png
  POST /process   (multipart)  file + code[,code2,code3] -> JSON (multi-zones + paint)
  GET  /files/<...>           sorties (output/app/<id>/...)
"""
import colorsys
import io
import json
import os
import sys
import uuid
import threading
import time
import urllib.request

import numpy as np
from PIL import Image

from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response, RedirectResponse
from starlette.staticfiles import StaticFiles

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SCRIPTS = os.path.join(PROJ, "scripts")
sys.path.insert(0, SCRIPTS)

import recolor_vallejo as rv          # recolor Lab exact (leger)
import paint_controlnet as pc         # repaint ControlNet-canny (MPS)

OUT_DIR = os.path.join(PROJ, "output", "app")
os.makedirs(OUT_DIR, exist_ok=True)
WEB_DIR = os.path.join(HERE, "web")
os.makedirs(WEB_DIR, exist_ok=True)

PALETTE = rv.load_palette()

# Lab de chaque ref palette, precalcule (pour le nearest-Vallejo des harmonies)
_PAL_LAB = {c: rv.rgb_to_lab((np.array(p["rgb"], dtype=np.float32) / 255.0).reshape(1, 1, 3))[0, 0]
            for c, p in PALETTE.items()}

_pipe = None
_pipe_lock = threading.Lock()


def get_pipe(fp16=False):
    global _pipe
    with _pipe_lock:
        if _pipe is None:
            _pipe = pc.build_pipe(use_fp16=fp16)
    return _pipe


# --- helpers formulaire ------------------------------------------------------
def _f(form, key, default=None):
    v = form.get(key)
    return v if v not in (None, "") else default


def _float(form, key, d):
    try:
        return float(_f(form, key, d))
    except (TypeError, ValueError):
        return d


def _int(form, key, d):
    try:
        return int(float(_f(form, key, d)))
    except (TypeError, ValueError):
        return d


def _bool(form, key, d=True):
    v = _f(form, key)
    if v is None:
        return d
    return str(v).lower() in ("1", "true", "yes", "on", "oui")


def _parse_roi(s, default=(0.0, 0.0, 1.0, 0.72)):
    if not s:
        return list(default)
    try:
        vals = [float(x) for x in str(s).split(",")]
        return vals if len(vals) == 4 else list(default)
    except ValueError:
        return list(default)


def _lab_delta(mean_rgb01, target_rgb01):
    lo = rv.rgb_to_lab(mean_rgb01.reshape(1, 1, 3))[0, 0]
    lt = rv.rgb_to_lab(target_rgb01.reshape(1, 1, 3))[0, 0]
    return round(float(np.sqrt(((lo - lt) ** 2).sum())), 1)


# --- teintes dominantes ------------------------------------------------------
def dominant_hue(arr01, min_sat=0.30, min_val=0.15, max_val=0.98, roi=None):
    c = dominant_hues(arr01, 1, min_sat=min_sat, min_val=min_val, max_val=max_val, roi=roi)
    return (c[0][0], c[0][1]) if c else (None, 0)


def dominant_hues(arr01, n, min_sat=0.30, min_val=0.15, max_val=0.98, roi=None, min_sep=25.0):
    """Jusqu'a n pics de teinte (centre deg, nb pixels), bien separes."""
    hsv = rv.rgb_to_hsv(arr01)
    H = hsv[..., 0] * 360.0
    S = hsv[..., 1]
    V = hsv[..., 2]
    m = (S >= min_sat) & (V >= min_val) & (V <= max_val)
    if roi:
        Hh, Ww = S.shape
        x0, y0, x1, y1 = roi
        box = np.zeros_like(S, dtype=bool)
        box[int(y0 * Hh):int(y1 * Hh), int(x0 * Ww):int(x1 * Ww)] = True
        m = m & box
    if int(m.sum()) < 50:
        return []
    hist = np.histogram(H[m], bins=72, range=(0, 360))[0]
    peaks = []
    for idx in np.argsort(hist)[::-1]:
        if hist[idx] == 0:
            break
        center = (idx + 0.5) * 5.0
        if all(abs(((center - c + 180) % 360) - 180) >= min_sep for c, _ in peaks):
            peaks.append((center, int(hist[idx])))
        if len(peaks) >= n:
            break
    return peaks


def auto_map(arr01, code, width=35.0, min_sat=0.30, roi=(0.0, 0.0, 1.0, 0.72)):
    center, n = dominant_hue(arr01, min_sat=min_sat, roi=roi)
    if center is None:
        raise ValueError("Aucune teinte dominante saturee detectee (sujet trop neutre ?).")
    src = {"type": "hue", "center": center, "width": width,
           "min_sat": min_sat, "min_val": 0.12, "roi": list(roi)}
    return {"source": src, "target_code": code, "strength": 1.0, "feather": 2}, center, n


# --- harmonies ---------------------------------------------------------------
HARMONY_OFFSETS = {
    "custom": [],
    "analogous": [-30, 30],
    "complementary": [180],
    "split": [150, 210],
    "triad": [120, 240],
    "tetradic": [60, 180, 240],
    "square": [90, 180, 270],
    "monochromatic": None,   # cas special (varie la valeur)
}
_ROLE_NAMES = ["secondaire", "accessoire", "detail", "detail2"]


def nearest_vallejo(rgb01, exclude=None):
    exclude = exclude or set()
    lt = rv.rgb_to_lab(np.array(rgb01, dtype=np.float32).reshape(1, 1, 3))[0, 0]
    best, bd = None, 1e9
    for code, plab in _PAL_LAB.items():
        if code in exclude:
            continue
        d = float(np.sqrt(((plab - lt) ** 2).sum()))
        if d < bd:
            bd, best = d, code
    return best, round(bd, 1)


def compute_harmony(code, scheme):
    scheme = (scheme or "analogous").lower()
    base = np.array(PALETTE[code]["rgb"], dtype=np.float32) / 255.0
    h, s, v = colorsys.rgb_to_hsv(float(base[0]), float(base[1]), float(base[2]))
    out = [{"role": "principale", "code": code, "hex": PALETTE[code]["hex"],
            "name": PALETTE[code].get("name", ""), "delta_e": 0.0}]
    derived = []
    if scheme == "monochromatic":
        for dv in (-0.35, -0.15, 0.2):
            nv = min(max(v + dv, 0.08), 1.0)
            derived.append((colorsys.hsv_to_rgb(h, max(s * 0.9, 0.2), nv), round(h * 360, 1)))
    else:
        for off in HARMONY_OFFSETS.get(scheme) or []:
            nh = ((h * 360 + off) % 360) / 360.0
            derived.append((colorsys.hsv_to_rgb(nh, s, v), round(nh * 360, 1)))
    used = {code}   # ne jamais re-proposer la principale ni un doublon
    for i, (rgb, hue) in enumerate(derived):
        nc, de = nearest_vallejo(rgb, exclude=used)
        if nc is None:
            continue
        used.add(nc)
        out.append({"role": _ROLE_NAMES[i] if i < len(_ROLE_NAMES) else f"zone{i + 2}",
                    "code": nc, "hex": PALETTE[nc]["hex"], "name": PALETTE[nc].get("name", ""),
                    "delta_e": de, "target_hue": hue})
    return out


# --- recolor / paint ---------------------------------------------------------
def do_recolor(img, mappings):
    """Multi-zones : masques calcules sur l'ORIGINAL et rendus DISJOINTS (un pixel
    = une seule zone) pour qu'une passe ne recolore pas les pixels d'une autre.
    Mesure deltaE par zone sur la sortie finale."""
    arr0 = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    hards, targets = [], []
    union = np.zeros(arr0.shape[:2], dtype=bool)
    for mp in mappings:
        if mp["target_code"] not in PALETTE:
            raise KeyError(mp["target_code"])
        h = (rv.build_mask(arr0, mp["source"]) > 0.5) & (~union)
        union |= h
        hards.append(h)
        targets.append(rv.get_rgb(mp["target_code"], PALETTE) / 255.0)
    arr = arr0.copy()
    report = []
    for mp, hard, tgt in zip(mappings, hards, targets):
        hardf = hard.astype(np.float32)
        soft = rv.feather_mask(hardf, mp.get("feather", 2))
        arr, cover = rv.recolor_region(arr, hardf, soft, tgt,
                                       strength=mp.get("strength", 1.0),
                                       keep_chroma=mp.get("keep_chroma", 0.0))
        report.append({"target_code": mp["target_code"],
                       "target_hex": PALETTE[mp["target_code"]]["hex"],
                       "role": mp.get("role", ""),
                       "coverage_pct": round(cover * 100, 2)})
    for i, (hard, tgt) in enumerate(zip(hards, targets)):
        report[i]["delta_e"] = _lab_delta(arr[hard].mean(axis=0), tgt) if hard.sum() >= 10 else None
    out = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    return out, report


def do_paint(img, prompt, steps=26, size=704, strength=0.55, cn_scale=0.9,
             canny_low=100, canny_high=200, guidance=7.0, seed=42):
    import torch
    pipe = get_pipe()
    init = pc.fit_size(img.convert("RGB"), size)
    control = pc.canny_image(init, canny_low, canny_high)
    gen = torch.Generator(device="mps").manual_seed(seed)
    res = pipe(prompt=prompt, negative_prompt=pc.NEG, image=init, control_image=control,
               strength=strength, controlnet_conditioning_scale=cn_scale,
               num_inference_steps=steps, guidance_scale=guidance, generator=gen)
    out = res.images[0]
    a = np.array(out)
    return out, {"size": list(out.size), "steps": steps, "strength": strength,
                 "cn_scale": cn_scale, "mean_luma": round(float(a.mean()), 2),
                 "is_black": bool(a.mean() < 3)}


def default_prompt(code):
    name = PALETTE.get(code, {}).get("name", "").lower()
    return (f"professional studio macro photograph of a real hand-painted resin tabletop "
            f"miniature on a round base, {name} matte acrylic skin with subtle brush texture "
            f"and black markings, Vallejo cel-shading box-art technique, soft studio light, "
            f"shallow depth of field, neutral gradient background, keep the exact same pose, "
            f"sculpt and composition as the source")


def _png_response(img, report):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"X-Report": json.dumps(report, ensure_ascii=True)})


# --- FLUX.1 Kontext (local via ComfyUI) + encrage cel-shading ----------------
COMFY_SRV = os.environ.get("COMFY_SRV", "http://127.0.0.1:8188")
COMFY_DIR = os.path.expanduser("~/flux_kontext/ComfyUI")
_QUANT = {"q4": "Q4_K_M", "q6": "Q6_K", "q8": "Q8_0"}
_MODE = {"q4": (14, 768), "q6": (22, 1024), "q8": (26, 1024)}


def _comfy(path, payload=None, timeout=1800):
    url = COMFY_SRV + path
    if payload is not None:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    return urllib.request.urlopen(req, timeout=timeout).read()


def _kontext_render(src_path, prompt, out_path, seed, steps, size, quant, denoise=1.0, should_stop=None):
    sw, sh = Image.open(src_path).size
    sc = size / max(sw, sh)
    tw = max(16, int(round(sw * sc / 16)) * 16)
    th = max(16, int(round(sh * sc / 16)) * 16)
    name = "src_" + uuid.uuid4().hex[:8] + ".png"
    os.makedirs(os.path.join(COMFY_DIR, "input"), exist_ok=True)
    Image.open(src_path).convert("RGB").save(os.path.join(COMFY_DIR, "input", name))
    unet = f"flux1-kontext-dev-{quant}.gguf"
    wf = {
        "unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": unet}},
        "clip": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "load": {"class_type": "LoadImage", "inputs": {"image": name}},
        "scale": {"class_type": "ImageScale", "inputs": {"image": ["load", 0], "upscale_method": "lanczos", "width": tw, "height": th, "crop": "disabled"}},
        "enc": {"class_type": "VAEEncode", "inputs": {"pixels": ["scale", 0], "vae": ["vae", 0]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "ref": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos", 0], "latent": ["enc", 0]}},
        "guid": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["ref", 0], "guidance": 2.5}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["clip", 0]}},
        "ks": {"class_type": "KSampler", "inputs": {"model": ["unet", 0], "positive": ["guid", 0], "negative": ["neg", 0], "latent_image": ["enc", 0], "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": denoise}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": "cel"}},
    }
    r = json.loads(_comfy("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex}))
    if r.get("node_errors"):
        raise RuntimeError("node_errors " + json.dumps(r["node_errors"])[:400])
    pid = r["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < 2400:
        if should_stop is not None and should_stop():
            raise RuntimeError("rendu annule")
        h = json.loads(_comfy("/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {})
            if h[pid].get("outputs"):
                for _, o in h[pid]["outputs"].items():
                    for im in o.get("images", []):
                        q = (f"/view?filename={im['filename']}"
                             f"&subfolder={im.get('subfolder', '')}&type={im.get('type', 'output')}")
                        with open(out_path, "wb") as f:
                            f.write(_comfy(q, timeout=120))
                        return {"size": [tw, th], "steps": steps, "quant": quant,
                                "secs": round(time.time() - t0, 1)}
            if st.get("status_str") == "error":
                raise RuntimeError("exec " + json.dumps(st.get("messages", []))[:400])
        time.sleep(3)
    raise RuntimeError("timeout rendu Kontext")


def _ink(inp, outp, thick=2, exterior=False, low=25, high=80):
    import cv2
    img = np.array(Image.open(inp).convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    try:
        fg = (_figure_mask(img) > 0.5).astype(np.uint8)
    except Exception:
        fg = np.ones(img.shape[:2], np.uint8)
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
    Image.fromarray(res).save(outp)
    return {"thick": thick, "exterior": bool(exterior), "line_px": int((lines > 0).sum())}


# --- endpoints ---------------------------------------------------------------
async def root(request):
    return RedirectResponse(url="/app/")


async def health(request):
    import torch
    return JSONResponse({"status": "ok", "python": sys.version.split()[0],
                         "torch": torch.__version__,
                         "mps": bool(torch.backends.mps.is_available()),
                         "pipe_loaded": _pipe is not None, "palette_size": len(PALETTE)})


async def palette(request):
    colors = [{"code": c, "hex": PALETTE[c]["hex"], "rgb": PALETTE[c]["rgb"],
               "name": PALETTE[c].get("name", "")} for c in sorted(PALETTE)]
    return JSONResponse({"count": len(colors), "colors": colors})


async def harmony_ep(request):
    code = request.query_params.get("code")
    scheme = request.query_params.get("scheme", "analogous")
    if not code or code not in PALETTE:
        return JSONResponse({"error": "param 'code' (Vallejo valide) requis"}, status_code=400)
    return JSONResponse({"code": code, "scheme": scheme,
                         "colors": compute_harmony(code, scheme),
                         "schemes": list(HARMONY_OFFSETS.keys())})


async def recolor_ep(request):
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    data = await form["file"].read()
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)
    maps = form.getlist("map")
    try:
        if maps:
            mappings = [rv._parse_map(m) for m in maps]
        else:
            code = _f(form, "code")
            if not code:
                return JSONResponse({"error": "fournir 'map' ou 'code'"}, status_code=400)
            arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
            mp, _, _ = auto_map(arr, code, width=_float(form, "width", 35.0),
                                min_sat=_float(form, "min_sat", 0.30),
                                roi=_parse_roi(_f(form, "roi")))
            mappings = [mp]
        out, report = do_recolor(img, mappings)
    except KeyError as e:
        return JSONResponse({"error": f"code Vallejo inconnu: {e}"}, status_code=400)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return _png_response(out, report)


async def paint_ep(request):
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    data = await form["file"].read()
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)
    prompt = _f(form, "prompt") or default_prompt(_f(form, "code", ""))
    out, meta = do_paint(img, prompt,
                         steps=_int(form, "steps", 26), size=_int(form, "size", 704),
                         strength=_float(form, "strength", 0.55),
                         cn_scale=_float(form, "cn_scale", 0.9),
                         canny_low=_int(form, "canny_low", 100),
                         canny_high=_int(form, "canny_high", 200),
                         guidance=_float(form, "guidance", 7.0), seed=_int(form, "seed", 42))
    return _png_response(out, meta)


async def process_ep(request):
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    if _f(form, "codes"):
        codes = [c.strip() for c in _f(form, "codes").split(",") if c.strip()]
    else:
        codes = [v for v in (_f(form, k) for k in ("code", "code2", "code3", "code4")) if v]
    if not codes:
        return JSONResponse({"error": "au moins 'code' (Vallejo) requis"}, status_code=400)
    for c in codes:
        if c not in PALETTE:
            return JSONResponse({"error": f"code Vallejo inconnu: {c}"}, status_code=400)
    data = await form["file"].read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)

    job = uuid.uuid4().hex[:12]
    jobdir = os.path.join(OUT_DIR, job)
    os.makedirs(jobdir, exist_ok=True)

    arr = np.array(img, dtype=np.float32) / 255.0
    roi = _parse_roi(_f(form, "roi"))
    width = _float(form, "width", 35.0)
    min_sat = _float(form, "min_sat", 0.30)
    clusters = dominant_hues(arr, len(codes), min_sat=min_sat, roi=roi)
    if not clusters:
        return JSONResponse({"error": "aucune teinte saturee detectee"}, status_code=400)
    mappings = []
    for i, code in enumerate(codes):
        center = clusters[min(i, len(clusters) - 1)][0]
        mappings.append({"source": {"type": "hue", "center": center, "width": width,
                                    "min_sat": min_sat, "min_val": 0.12, "roi": list(roi)},
                         "target_code": code,
                         "role": "principale" if i == 0 else _ROLE_NAMES[i - 1],
                         "strength": 1.0, "feather": 2})
    recolor_img, report = do_recolor(img, mappings)
    recolor_img.save(os.path.join(jobdir, "recolor.png"))
    out = {"id": job, "recolor": {"url": f"/files/{job}/recolor.png", "zones": report},
           "paint": None}
    if report:   # compat client web : champs plats de la zone principale
        out["recolor"].update({k: report[0].get(k) for k in
                               ("target_code", "target_hex", "coverage_pct", "delta_e")})
        out["recolor"]["hue_center"] = round(clusters[0][0], 1)

    if _bool(form, "do_paint", True):
        prompt = _f(form, "prompt") or default_prompt(codes[0])
        paint_img, meta = do_paint(recolor_img, prompt,
                                   steps=_int(form, "steps", 26), size=_int(form, "size", 704),
                                   strength=_float(form, "strength", 0.55),
                                   cn_scale=_float(form, "cn_scale", 0.9),
                                   guidance=_float(form, "guidance", 7.0),
                                   seed=_int(form, "seed", 42))
        paint_img.save(os.path.join(jobdir, "paint.png"))
        out["paint"] = {"url": f"/files/{job}/paint.png", "prompt": prompt, **meta}
    return JSONResponse(out)


async def process_points_ep(request):
    """Affectation au doigt : 'points' = JSON [{x,y,code[,tol]}] en coords
    normalisees 0..1. Pour chaque point on echantillonne la couleur source sous
    le doigt et on recolore cette couleur vers le code Vallejo choisi (masques
    DISJOINTS via do_recolor)."""
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    raw = _f(form, "points")
    if not raw:
        return JSONResponse({"error": "champ 'points' (JSON) requis"}, status_code=400)
    try:
        points = json.loads(raw)
    except Exception:
        return JSONResponse({"error": "'points' JSON invalide"}, status_code=400)
    if not points:
        return JSONResponse({"error": "au moins un point requis"}, status_code=400)
    data = await form["file"].read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)
    arr = np.array(img, dtype=np.float32) / 255.0
    H, W = arr.shape[:2]
    tol = _float(form, "tol", 45.0)
    mappings = []
    for i, p in enumerate(points):
        code = p.get("code")
        if code not in PALETTE:
            return JSONResponse({"error": f"code Vallejo inconnu: {code}"}, status_code=400)
        x = min(max(float(p.get("x", 0.5)), 0.0), 1.0)
        y = min(max(float(p.get("y", 0.5)), 0.0), 1.0)
        px, py = int(x * (W - 1)), int(y * (H - 1))
        y0, y1 = max(0, py - 3), min(H, py + 4)
        x0, x1 = max(0, px - 3), min(W, px + 4)
        rgb = (arr[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0) * 255.0).round().astype(int).tolist()
        mappings.append({"source": {"type": "rgb", "rgb": rgb, "tol": float(p.get("tol", tol))},
                         "target_code": code,
                         "role": "principale" if i == 0 else _ROLE_NAMES[min(i - 1, len(_ROLE_NAMES) - 1)],
                         "strength": 1.0, "feather": 2})
    recolor_img, report = do_recolor(img, mappings)
    job = uuid.uuid4().hex[:12]
    jobdir = os.path.join(OUT_DIR, job)
    os.makedirs(jobdir, exist_ok=True)
    recolor_img.save(os.path.join(jobdir, "recolor.png"))
    out = {"id": job, "recolor": {"url": f"/files/{job}/recolor.png", "zones": report}, "paint": None}
    if report:
        out["recolor"].update({k: report[0].get(k) for k in
                               ("target_code", "target_hex", "coverage_pct", "delta_e")})
    if _bool(form, "do_paint", True):
        prompt = _f(form, "prompt") or default_prompt(mappings[0]["target_code"])
        paint_img, meta = do_paint(recolor_img, prompt,
                                   steps=_int(form, "steps", 26), size=_int(form, "size", 704),
                                   strength=_float(form, "strength", 0.55), cn_scale=_float(form, "cn_scale", 0.9),
                                   guidance=_float(form, "guidance", 7.0), seed=_int(form, "seed", 42))
        paint_img.save(os.path.join(jobdir, "paint.png"))
        out["paint"] = {"url": f"/files/{job}/paint.png", "prompt": prompt, **meta}
    return JSONResponse(out)


def _rasterize(H, W, strokes):
    """Trace au doigt -> masque binaire. strokes: [{pts:[[x,y]norm], r:rayon_norm,
    mode:'add'|'erase'}] appliques dans l'ordre (erase soustrait)."""
    from PIL import ImageDraw
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    s = min(H, W)
    for st in strokes or []:
        pts = [(float(x) * W, float(y) * H) for x, y in st.get("pts", [])]
        if not pts:
            continue
        r = max(1.0, float(st.get("r", 0.04)) * s)
        val = 0 if st.get("mode") == "erase" else 255
        if len(pts) >= 2:
            d.line(pts, fill=val, width=int(r * 2), joint="curve")
        for (x, y) in pts:  # bouts ronds
            d.ellipse([x - r, y - r, x + r, y + r], fill=val)
    return (np.array(im, dtype=np.float32) / 255.0 > 0.5).astype(np.float32)


async def recolor_strokes_ep(request):
    """Recoloration EXACTE par zones peintes au doigt (figurine mono-couleur).
    Pas de couleur source, pas d'IA : chaque zone = un trace + un code Vallejo.
    En cas de recouvrement, la DERNIERE zone l'emporte."""
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    raw = _f(form, "zones")
    if not raw:
        return JSONResponse({"error": "champ 'zones' (JSON) requis"}, status_code=400)
    try:
        zones = json.loads(raw)
    except Exception:
        return JSONResponse({"error": "'zones' JSON invalide"}, status_code=400)
    if not zones:
        return JSONResponse({"error": "au moins une zone requise"}, status_code=400)
    for z in zones:
        if z.get("code") not in PALETTE:
            return JSONResponse({"error": f"code Vallejo inconnu: {z.get('code')}"}, status_code=400)
    data = await form["file"].read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)
    arr = np.array(img, dtype=np.float32) / 255.0
    H, W = arr.shape[:2]
    owner = np.full((H, W), -1, dtype=np.int32)
    for i, z in enumerate(zones):
        m = _rasterize(H, W, z.get("strokes", []))
        owner[m > 0.5] = i  # derniere zone gagne
    out = arr.copy()
    report = []
    for i, z in enumerate(zones):
        code = z["code"]
        tgt = rv.get_rgb(code, PALETTE) / 255.0
        fm = (owner == i).astype(np.float32)
        if fm.sum() < 10:
            report.append({"role": z.get("role", f"zone{i+1}"), "target_code": code,
                           "target_hex": PALETTE[code]["hex"], "coverage_pct": 0.0, "delta_e": None})
            continue
        out, cover = rv.recolor_region(out, fm, rv.feather_mask(fm, 2), tgt)
        de = _lab_delta(out[fm > 0.5].mean(axis=0), tgt)
        report.append({"role": z.get("role", f"zone{i+1}"), "target_code": code,
                       "target_hex": PALETTE[code]["hex"],
                       "coverage_pct": round(float(cover) * 100, 2), "delta_e": round(float(de), 2)})
    job = uuid.uuid4().hex[:12]
    jobdir = os.path.join(OUT_DIR, job)
    os.makedirs(jobdir, exist_ok=True)
    recolor_img = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    recolor_img.save(os.path.join(jobdir, "recolor.png"))
    result = {"id": job, "recolor": {"url": f"/files/{job}/recolor.png", "zones": report}, "paint": None}
    if _bool(form, "finish", False):
        names = [PALETTE[z["code"]].get("name", "") for z in zones if PALETTE.get(z["code"])]
        main = names[0] if names else "colored"
        accents = ", ".join(n for n in names[1:] if n)
        subj = _f(form, "subject") or "fantasy creature"
        prompt = _f(form, "prompt") or (
            f"hand-painted resin tabletop miniature, {subj}, {main} matte acrylic skin"
            + (f" with {accents} details" if accents else "")
            + ", black lining in the recesses, bold edge highlights, Vallejo cel-shading box-art, "
            "studio macro photography, shallow depth of field, neutral gradient background. "
            "Keep the exact same pose, sculpt, proportions and composition as the source.")
        paint_img, meta = do_paint(recolor_img, prompt,
                                   steps=_int(form, "steps", 26), size=_int(form, "size", 704),
                                   strength=_float(form, "strength", 0.55), cn_scale=_float(form, "cn_scale", 0.9),
                                   guidance=_float(form, "guidance", 7.0), seed=_int(form, "seed", 42))
        paint_img.save(os.path.join(jobdir, "paint.png"))
        result["paint"] = {"url": f"/files/{job}/paint.png", "prompt": prompt, **meta}
    return JSONResponse(result)


async def kontext_cel_ep(request):
    """Rendu cel-shading 100% local : FLUX.1 Kontext (ComfyUI) + encrage noir.
    C'est le chemin appele par l'app. file + prompt + mode(q4|q6|q8) + ink params."""
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    prompt = _f(form, "prompt")
    if not prompt:
        return JSONResponse({"error": "champ 'prompt' (instruction) requis"}, status_code=400)
    mode = (_f(form, "mode") or "q8").lower()
    if mode not in _QUANT:
        return JSONResponse({"error": "mode doit etre q4|q6|q8"}, status_code=400)
    data = await form["file"].read()
    job = uuid.uuid4().hex[:12]
    jobdir = os.path.join(OUT_DIR, job)
    os.makedirs(jobdir, exist_ok=True)
    src = os.path.join(jobdir, "src.png")
    try:
        Image.open(io.BytesIO(data)).convert("RGB").save(src)
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)
    dstep, dsize = _MODE[mode]
    steps = _int(form, "steps", dstep)
    size = _int(form, "size", dsize)
    seed = _int(form, "seed", 42)
    denoise = _float(form, "denoise", 1.0)
    raw = os.path.join(jobdir, "render.png")
    try:
        rmeta = _kontext_render(src, prompt, raw, seed, steps, size, _QUANT[mode], denoise)
    except Exception as e:
        return JSONResponse({"error": f"rendu Kontext: {e}"}, status_code=502)
    result = {"id": job, "mode": mode, "prompt": prompt,
              "render": {"url": f"/files/{job}/render.png", **rmeta}}
    if _bool(form, "ink", True):
        final = os.path.join(jobdir, "final.png")
        imeta = _ink(raw, final, thick=_int(form, "thick", 2),
                     exterior=_bool(form, "exterior", False),
                     low=_int(form, "ink_low", 60), high=_int(form, "ink_high", 150))
        result["final"] = {"url": f"/files/{job}/final.png", **imeta}
    return JSONResponse(result)


_JOBS: dict = {}


def _figure_mask(u8):
    """Masque binaire de la figurine. Fond detecte de 2 facons combinees : (1) diffusion
    (floodFill) depuis les 4 coins -> fond exterieur meme en degrade / bi-ton ; (2) par
    COULEUR (couleurs de fond apprises par k-means sur ce fond exterieur) -> rattrape les
    POCHES de fond ENFERMEES par la figurine (entre les jambes, au-dessus d'une epaule...).
    Tout le reste = figurine, socle compris. Sert au /cel_fill, au clip et a l'encrage.
    Pas de MORPH_CLOSE : il refermait les poches fines (bug signale)."""
    import cv2
    h, w = u8.shape[:2]
    img = np.ascontiguousarray(u8[:, :, ::-1])   # BGR pour cv2
    outer = np.zeros((h, w), np.uint8)
    for (sx, sy) in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        m2 = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(img, m2, (sx, sy), 0, loDiff=(8, 8, 8), upDiff=(8, 8, 8),
                      flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY)
        outer |= m2[1:-1, 1:-1]
    colbg = np.zeros((h, w), np.uint8)
    bgpix = u8[outer > 0].astype(np.float32)
    if len(bgpix) >= 200:
        idx = np.random.choice(len(bgpix), min(5000, len(bgpix)), replace=False)
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, _, centers = cv2.kmeans(bgpix[idx], 5, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        flat = u8.reshape(-1, 3).astype(np.float32)
        dmin = np.min(np.stack([np.linalg.norm(flat - c, axis=1) for c in centers], 1), 1)
        cand = (dmin.reshape(h, w) < 40)
        # Garde-fou : si ce fond-par-couleur mange >25% de la figure detectee par connexite,
        # c'est que figurine et fond partagent des tons (figurine SOMBRE sur fond NOIR, ou
        # claire sur fond blanc) -> on l'ABANDONNE (sinon on efface la figurine : bug goblin
        # a 3% de couverture) et on ne garde que le fond exterieur. Sinon il ne retire que
        # les poches de fond ENFERMEES (cas knight : entre les jambes, au-dessus de l'epaule).
        conn_fig = (outer == 0)
        if float((cand & conn_fig).sum()) / max(1, int(conn_fig.sum())) < 0.25:
            colbg = cand.astype(np.uint8)
    bg = ((outer | colbg) > 0).astype(np.uint8)
    fg = (1 - bg).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return fg.astype(np.float32)


def _run_cel_render(job, recolor_path, jobdir, prompt, seed, steps, size, quant,
                    denoise, ink, thick, exterior):
    """Rendu Kontext + encrage en arriere-plan (thread). Met a jour _JOBS[job]."""
    stop = lambda: _JOBS.get(job, {}).get("status") == "cancelled"
    try:
        render_path = os.path.join(jobdir, "render.png")
        rmeta = _kontext_render(recolor_path, prompt, render_path, seed, steps, size,
                                quant, denoise, should_stop=stop)
        if stop():
            return
        _JOBS[job]["render"] = {"url": f"/files/{job}/render.png", **rmeta}
        if ink:
            final_path = os.path.join(jobdir, "final.png")
            imeta = _ink(render_path, final_path, thick=thick, exterior=exterior)
            _JOBS[job]["final"] = {"url": f"/files/{job}/final.png", **imeta}
        _JOBS[job]["status"] = "done"
    except Exception as e:
        if stop():
            return
        _JOBS[job]["status"] = "error"
        _JOBS[job]["error"] = str(e)


def _make_tones(base, n=3):
    """A partir d'une couleur Vallejo, derive n tons DURS (ombre / base / highlight)
    en gardant la teinte, via HSV. Marche pour n'importe quelle couleur."""
    import colorsys
    r, g, b = [float(x) / 255 for x in base[:3]]
    h, sat, val = colorsys.rgb_to_hsv(r, g, b)
    if n == 3:
        sv = [(sat, val * 0.5), (sat, val), (max(0.0, sat * 0.68), min(1.0, val * 1.5 + 0.12))]
    else:
        sv = [(sat, val * 0.4), (sat, val * 0.72), (sat, val),
              (max(0.0, sat * 0.68), min(1.0, val * 1.5 + 0.12))]
    tones = []
    for ss, vv in sv:
        rr, gg, bb = colorsys.hsv_to_rgb(h, ss, vv)
        tones.append([int(rr * 255), int(gg * 255), int(bb * 255)])
    return tones


def _posterize_cel(orig_u8, zone_masks, bases, ink=True, thick=2, exterior=False,
                   n=3, ink_low=55, ink_high=140, dark_thr=30):
    """Cel-shading DETERMINISTE (instantane). Ombre la vraie sculpture (luminance de
    l'ORIGINAL, lissee) en n tons DURS par zone, snappes sur la couleur Vallejo de la
    zone. Les pixels quasi-noirs (poches de fond enfermees : entre les jambes, sous un
    bras) restent fond. Encrage cv2 (traits noirs des reliefs) par-dessus."""
    import cv2
    h, w = orig_u8.shape[:2]
    sm = cv2.bilateralFilter(orig_u8, 7, 45, 45)
    gray = cv2.cvtColor(sm, cv2.COLOR_RGB2GRAY).astype(np.float32)
    dark = ((orig_u8[:, :, 0] < dark_thr) & (orig_u8[:, :, 1] < dark_thr) &
            (orig_u8[:, :, 2] < dark_thr))
    out = orig_u8.copy()
    allfig = np.zeros((h, w), dtype=bool)
    for zm, base in zip(zone_masks, bases):
        zm = (np.asarray(zm) > 0) & ~dark
        if int(zm.sum()) < 10:
            continue
        Lf = gray[zm]
        ts = np.percentile(Lf, [42, 80]) if n == 3 else np.percentile(Lf, [30, 58, 82])
        tones = _make_tones(base, n)
        band = np.digitize(gray, ts)
        for i in range(n):
            out[zm & (band == i)] = tones[i]
        allfig |= zm
    if ink and allfig.any():
        go = cv2.cvtColor(orig_u8, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(go, ink_low, ink_high) > 0
        af = allfig.astype(np.uint8)
        inside = cv2.erode(af, np.ones((3, 3), np.uint8), iterations=2) > 0
        lines = edges & inside
        if not exterior:
            ring = cv2.morphologyEx(af, cv2.MORPH_GRADIENT,
                                    np.ones((2 * thick + 3, 2 * thick + 3), np.uint8)) > 0
            lines = lines & ~ring
        else:
            sil = cv2.morphologyEx(af, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
            lines = lines | sil
        lines = cv2.dilate((lines * 255).astype(np.uint8), np.ones((thick, thick), np.uint8)) > 0
        out[lines] = (8, 8, 8)
    return out


def _run_cel_det(job, orig_u8, jobdir, zone_masks, bases, ink, thick, exterior):
    """Rendu cel-shading DETERMINISTE (instantane) en arriere-plan. MaJ _JOBS[job]."""
    stop = lambda: _JOBS.get(job, {}).get("status") == "cancelled"
    try:
        out = _posterize_cel(orig_u8, zone_masks, bases, ink=ink, thick=thick, exterior=exterior)
        if stop():
            return
        render_path = os.path.join(jobdir, "render.png")
        final_path = os.path.join(jobdir, "final.png")
        Image.fromarray(out).save(render_path)
        Image.fromarray(out).save(final_path)
        _JOBS[job]["render"] = {"url": f"/files/{job}/render.png"}
        _JOBS[job]["final"] = {"url": f"/files/{job}/final.png", "engine": "deterministic"}
        _JOBS[job]["status"] = "done"
    except Exception as e:
        if stop():
            return
        _JOBS[job]["status"] = "error"
        _JOBS[job]["error"] = str(e)


async def cel_zones_ep(request):
    """Flux complet de l'app : zones peintes au doigt -> recolor Vallejo EXACT par
    zone -> finition FLUX Kontext qui PRESERVE les couleurs -> encrage cel-shading.
    file + zones(JSON [{code,role,strokes}]) + mode(q4|q6|q8) + thick + denoise."""
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    raw = _f(form, "zones")
    if not raw:
        return JSONResponse({"error": "champ 'zones' (JSON) requis"}, status_code=400)
    try:
        zones = json.loads(raw)
    except Exception:
        return JSONResponse({"error": "'zones' JSON invalide"}, status_code=400)
    if not zones:
        return JSONResponse({"error": "au moins une zone requise"}, status_code=400)
    for z in zones:
        if z.get("code") not in PALETTE:
            return JSONResponse({"error": f"code Vallejo inconnu: {z.get('code')}"}, status_code=400)
    mode = (_f(form, "mode") or "q4").lower()
    if mode not in _QUANT:
        return JSONResponse({"error": "mode doit etre q4|q6|q8"}, status_code=400)
    data = await form["file"].read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)
    arr = np.array(img, dtype=np.float32) / 255.0
    H, W = arr.shape[:2]
    # Masque figurine : les traits qui depassent de la silhouette sont ignores.
    try:
        fg = _figure_mask(np.array(img))
    except Exception:
        fg = np.ones((H, W), dtype=np.float32)
    frac = float(fg.mean())
    use_clip = 0.02 < frac < 0.97   # sinon detection fond douteuse -> pas de decoupe
    owner = np.full((H, W), -1, dtype=np.int32)
    clipped_px = 0
    for i, z in enumerate(zones):
        m = _rasterize(H, W, z.get("strokes", []))
        if use_clip:
            before = int((m > 0.5).sum())
            m = m * fg
            clipped_px += before - int((m > 0.5).sum())
        owner[m > 0.5] = i
    out = arr.copy()
    report = []
    for i, z in enumerate(zones):
        code = z["code"]
        fm = (owner == i).astype(np.float32)
        if fm.sum() < 10:
            report.append({"role": z.get("role", f"zone{i+1}"), "target_code": code,
                           "target_hex": PALETTE[code]["hex"], "coverage_pct": 0.0, "delta_e": None})
            continue
        tgt = rv.get_rgb(code, PALETTE) / 255.0
        out, cover = rv.recolor_region(out, fm, rv.feather_mask(fm, 2), tgt)
        de = _lab_delta(out[fm > 0.5].mean(axis=0), tgt)
        report.append({"role": z.get("role", f"zone{i+1}"), "target_code": code,
                       "target_hex": PALETTE[code]["hex"],
                       "coverage_pct": round(float(cover) * 100, 2), "delta_e": round(float(de), 2)})
    job = uuid.uuid4().hex[:12]
    jobdir = os.path.join(OUT_DIR, job)
    os.makedirs(jobdir, exist_ok=True)
    recolor_img = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    recolor_path = os.path.join(jobdir, "recolor.png")
    recolor_img.save(recolor_path)
    dstep, dsize = _MODE[mode]
    steps = _int(form, "steps", dstep)
    size = _int(form, "size", dsize)
    seed = _int(form, "seed", 42)
    denoise = _float(form, "denoise", 0.55)
    prompt = _f(form, "prompt") or (
        "A real hand-painted resin tabletop miniature, studio macro photograph, satin "
        "acrylic paint with solid opaque colors. Keep the existing colors exactly where they "
        "are. Add clean hard-edged cel-shading, a darker shadow tone and a lighter highlight "
        "tone per area, under even neutral studio light. Keep the exact same sculpt, pose, "
        "proportions, base and background.")
    ink = _bool(form, "ink", True)
    thick = _int(form, "thick", 2)
    exterior = _bool(form, "exterior", False)
    _JOBS[job] = {"id": job, "status": "pending", "mode": mode,
                  "recolor": {"url": f"/files/{job}/recolor.png", "zones": report},
                  "clip": bool(use_clip), "clipped_px": int(clipped_px)}
    orig_u8 = np.array(img)
    zone_masks = [(owner == i) for i in range(len(zones))]
    bases = [rv.get_rgb(z["code"], PALETTE) for z in zones]
    threading.Thread(target=_run_cel_det,
                     args=(job, orig_u8, jobdir, zone_masks, bases, ink, thick, exterior),
                     daemon=True).start()
    return JSONResponse(_JOBS[job])


async def cel_fill_ep(request):
    """Mode sans-peinture : TOUTE la figurine (socle compris, fond epargne s'il est
    detecte) peinte d'une seule couleur Vallejo exacte -> finition cel + encrage. Async."""
    form = await request.form()
    if "file" not in form:
        return JSONResponse({"error": "champ 'file' (image) requis"}, status_code=400)
    code = _f(form, "code")
    if not code or code not in PALETTE:
        return JSONResponse({"error": f"code Vallejo inconnu: {code}"}, status_code=400)
    mode = (_f(form, "mode") or "q4").lower()
    if mode not in _QUANT:
        return JSONResponse({"error": "mode doit etre q4|q6|q8"}, status_code=400)
    data = await form["file"].read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        return JSONResponse({"error": f"image illisible: {e}"}, status_code=400)
    arr = np.array(img, dtype=np.float32) / 255.0
    H, W = arr.shape[:2]
    try:
        fg = _figure_mask(np.array(img))
    except Exception:
        fg = np.ones((H, W), dtype=np.float32)
    frac = float(fg.mean())
    clipped = 0.02 < frac < 0.97   # fond detecte de facon fiable -> on l'epargne
    fm = fg if clipped else np.ones((H, W), dtype=np.float32)
    out = arr.copy()
    tgt = rv.get_rgb(code, PALETTE) / 255.0
    out, cover = rv.recolor_region(out, fm, rv.feather_mask(fm, 2), tgt)
    de = _lab_delta(out[fm > 0.5].mean(axis=0), tgt)
    report = [{"role": "figurine", "target_code": code, "target_hex": PALETTE[code]["hex"],
               "coverage_pct": round(float(cover) * 100, 2), "delta_e": round(float(de), 2)}]
    job = uuid.uuid4().hex[:12]
    jobdir = os.path.join(OUT_DIR, job)
    os.makedirs(jobdir, exist_ok=True)
    recolor_img = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    recolor_path = os.path.join(jobdir, "recolor.png")
    recolor_img.save(recolor_path)
    dstep, dsize = _MODE[mode]
    steps = _int(form, "steps", dstep)
    size = _int(form, "size", dsize)
    seed = _int(form, "seed", 42)
    denoise = _float(form, "denoise", 0.55)
    prompt = _f(form, "prompt") or (
        "A real hand-painted resin tabletop miniature, studio macro photograph, satin "
        "acrylic paint with solid opaque colors. Keep the existing colors exactly where they "
        "are. Add clean hard-edged cel-shading, a darker shadow tone and a lighter highlight "
        "tone per area, under even neutral studio light. Keep the exact same sculpt, pose, "
        "proportions, base and background.")
    ink = _bool(form, "ink", True)
    thick = _int(form, "thick", 2)
    exterior = _bool(form, "exterior", False)
    _JOBS[job] = {"id": job, "status": "pending", "mode": mode,
                  "recolor": {"url": f"/files/{job}/recolor.png", "zones": report},
                  "clip": bool(clipped), "clipped_px": 0}
    orig_u8 = np.array(img)
    zone_masks = [fm > 0.5]
    bases = [rv.get_rgb(code, PALETTE)]
    threading.Thread(target=_run_cel_det,
                     args=(job, orig_u8, jobdir, zone_masks, bases, ink, thick, exterior),
                     daemon=True).start()
    return JSONResponse(_JOBS[job])


async def cel_status_ep(request):
    """Statut d'un job de rendu (polling par l'app / le service de fond)."""
    job = request.path_params.get("job", "")
    j = _JOBS.get(job)
    if j is not None:
        return JSONResponse(j)
    # Fallback disque (backend redemarre) : si render/final existe, le job est fini.
    jobdir = os.path.join(OUT_DIR, job)
    if os.path.isfile(os.path.join(jobdir, "final.png")):
        return JSONResponse({"id": job, "status": "done",
                             "recolor": {"url": f"/files/{job}/recolor.png"},
                             "render": {"url": f"/files/{job}/render.png"},
                             "final": {"url": f"/files/{job}/final.png"}})
    if os.path.isfile(os.path.join(jobdir, "render.png")):
        return JSONResponse({"id": job, "status": "done",
                             "recolor": {"url": f"/files/{job}/recolor.png"},
                             "render": {"url": f"/files/{job}/render.png"}})
    return JSONResponse({"error": "job inconnu"}, status_code=404)


async def cel_cancel_ep(request):
    """Annule un job : marque 'cancelled' + interrompt ComfyUI (libere le Mac)."""
    job = request.path_params.get("job", "")
    j = _JOBS.get(job)
    if j is not None and j.get("status") == "pending":
        j["status"] = "cancelled"
    try:
        _comfy("/interrupt", {})
    except Exception:
        pass
    return JSONResponse({"id": job, "status": "cancelled"})


routes = [
    Route("/", root),
    Route("/health", health),
    Route("/palette", palette),
    Route("/harmony", harmony_ep),
    Route("/recolor", recolor_ep, methods=["POST"]),
    Route("/paint", paint_ep, methods=["POST"]),
    Route("/process", process_ep, methods=["POST"]),
    Route("/process_points", process_points_ep, methods=["POST"]),
    Route("/recolor_strokes", recolor_strokes_ep, methods=["POST"]),
    Route("/kontext_cel", kontext_cel_ep, methods=["POST"]),
    Route("/cel_zones", cel_zones_ep, methods=["POST"]),
    Route("/cel_fill", cel_fill_ep, methods=["POST"]),
    Route("/cel_status/{job}", cel_status_ep),
    Route("/cel_cancel/{job}", cel_cancel_ep, methods=["POST"]),
    Mount("/files", app=StaticFiles(directory=OUT_DIR), name="files"),
    Mount("/app", app=StaticFiles(directory=WEB_DIR, html=True), name="app"),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
