#!/usr/bin/env python3
"""
paint_controlnet.py — Repaint d'une figurine en style peint, en VERROUILLANT
la pose / la silhouette / le sculpt via ControlNet (Canny) sur SD 1.5, MPS,
100% local.

Pipeline : StableDiffusionControlNetImg2ImgPipeline.
  - image (init)      : l'image a repeindre (idealement DEJA recolorisee aux
                        couleurs Vallejo exactes par recolor_vallejo.py).
  - control_image     : carte de contours Canny extraite d'une image de
                        structure (par defaut = l'init), qui FORCE le modele a
                        garder exactement les contours/le sculpt d'origine.

float32 sur MPS par defaut (fp16 sur MPS peut sortir une image noire via le VAE).

USAGE :
  python paint_controlnet.py \
    --input  output/recolor_local/01_gobelin_69008_v2.png \
    --output output/controlnet/01_gobelin_cn.png \
    --prompt "hand-painted resin tabletop miniature, Vallejo matte acrylic, studio macro photo, shallow depth of field, clean cel-shading box-art, neutral gradient background" \
    --strength 0.55 --cn-scale 0.9 --canny-low 100 --canny-high 200 \
    --steps 26 --guidance 7.0 --size 704 --seed 42
"""
import argparse
import json
import os
import numpy as np
import cv2
import torch
from diffusers import (StableDiffusionControlNetImg2ImgPipeline, ControlNetModel,
                       DPMSolverMultistepScheduler)
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "..", ".cache")
SD_MARKER = os.path.join(CACHE, "MODEL_READY.txt")
CN_MARKER = os.path.join(CACHE, "CONTROLNET_READY_control_v11p_sd15_canny.txt")
HF_CACHE = os.path.join(CACHE, "hf_models")

NEG = ("lowres, blurry, deformed, extra limbs, bad anatomy, watermark, text, "
       "oversaturated, plastic toy, flat lighting, melted, mutated")


def _read_marker(path):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    repo = lines[0]
    local = lines[1]
    variant = None
    for l in lines[2:]:
        if l.startswith("variant="):
            variant = l.split("=", 1)[1]
    return repo, local, variant


def build_pipe(use_fp16=False):
    dtype = torch.float16 if use_fp16 else torch.float32
    sd_repo, _, _ = _read_marker(SD_MARKER)
    _, cn_dir, cn_variant = _read_marker(CN_MARKER)

    cn_kwargs = {"torch_dtype": dtype}
    if cn_variant == "fp16":
        cn_kwargs["variant"] = "fp16"
    controlnet = ControlNetModel.from_pretrained(cn_dir, **cn_kwargs)

    pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
        sd_repo, controlnet=controlnet, cache_dir=HF_CACHE,
        variant="fp16", torch_dtype=dtype,
        safety_checker=None, local_files_only=True,
    )
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    pipe = pipe.to("mps")
    pipe.enable_attention_slicing()
    return pipe


def fit_size(img, target):
    w, h = img.size
    scale = target / max(w, h)
    nw = int(round(w * scale / 8) * 8)
    nh = int(round(h * scale / 8) * 8)
    return img.resize((nw, nh), Image.LANCZOS)


def canny_image(pil_img, low, high):
    a = np.array(pil_img.convert("RGB"))
    edges = cv2.Canny(a, low, high)
    edges = np.stack([edges] * 3, axis=-1)
    return Image.fromarray(edges)


def main():
    ap = argparse.ArgumentParser(description="Repaint figurine ControlNet-canny (MPS)")
    ap.add_argument("--input", required=True)
    ap.add_argument("--control", help="image source des contours (defaut: --input)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default=NEG)
    ap.add_argument("--strength", type=float, default=0.55)
    ap.add_argument("--cn-scale", type=float, default=0.9, dest="cn_scale")
    ap.add_argument("--canny-low", type=int, default=100, dest="canny_low")
    ap.add_argument("--canny-high", type=int, default=200, dest="canny_high")
    ap.add_argument("--steps", type=int, default=26)
    ap.add_argument("--guidance", type=float, default=7.0)
    ap.add_argument("--size", type=int, default=704)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save-canny", dest="save_canny")
    ap.add_argument("--fp16", action="store_true")
    args = ap.parse_args()

    print(f"PyTorch {torch.__version__}, MPS={torch.backends.mps.is_available()}", flush=True)
    pipe = build_pipe(use_fp16=args.fp16)
    print("Pipeline ControlNet chargé.", flush=True)

    init = fit_size(Image.open(args.input).convert("RGB"), args.size)
    ctrl_src = Image.open(args.control).convert("RGB") if args.control else init
    ctrl_src = ctrl_src.resize(init.size, Image.LANCZOS)
    control = canny_image(ctrl_src, args.canny_low, args.canny_high)
    if args.save_canny:
        control.save(args.save_canny)

    gen = torch.Generator(device="mps").manual_seed(args.seed)
    result = pipe(
        prompt=args.prompt, negative_prompt=args.negative,
        image=init, control_image=control,
        strength=args.strength, controlnet_conditioning_scale=args.cn_scale,
        num_inference_steps=args.steps, guidance_scale=args.guidance,
        generator=gen,
    )
    out = result.images[0]
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out.save(args.output)

    a = np.array(out)
    print(json.dumps({
        "output": args.output, "size": out.size,
        "strength": args.strength, "cn_scale": args.cn_scale,
        "mean_luma": round(float(a.mean()), 2),
        "is_black": bool(a.mean() < 3),
    }, indent=2))


if __name__ == "__main__":
    main()
