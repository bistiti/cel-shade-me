#!/usr/bin/env python3
"""
paint_sd.py — Pipeline Stable Diffusion LOCAL (img2img) pour "repeindre" une
figurine en style peint, sur Apple Silicon (MPS), 100% hors-ligne.

Utilise le modèle téléchargé localement (voir .cache/MODEL_READY.txt).
Par défaut float32 sur MPS (fiable ; fp16 sur MPS peut sortir des images
noires à cause du VAE). Attention slicing activé pour la mémoire.

USAGE :
  python paint_sd.py --input render.png --output out.png \
      --prompt "hand-painted miniature, Vallejo acrylic, studio macro photo" \
      --strength 0.35 --steps 28 --guidance 7.0 --size 768 --seed 42
"""
import argparse
import json
import os
import sys
import torch
from diffusers import StableDiffusionImg2ImgPipeline, DPMSolverMultistepScheduler
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = os.path.join(HERE, "..", ".cache", "MODEL_READY.txt")

NEG = ("lowres, blurry, deformed, extra limbs, bad anatomy, watermark, text, "
       "oversaturated, plastic toy, cartoon, flat lighting")


def load_model_path():
    with open(MARKER) as f:
        lines = [l.strip() for l in f if l.strip()]
    repo = lines[0]
    path = lines[1]
    return repo, path


def build_pipe(use_fp16=False):
    repo, path = load_model_path()
    dtype = torch.float16 if use_fp16 else torch.float32
    # On charge depuis le cache local (variant fp16 téléchargé), cast en dtype voulu
    pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
        repo,
        cache_dir=os.path.join(HERE, "..", ".cache", "hf_models"),
        variant="fp16",
        torch_dtype=dtype,
        safety_checker=None,
        local_files_only=True,
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


def main():
    ap = argparse.ArgumentParser(description="SD img2img local (MPS)")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default=NEG)
    ap.add_argument("--strength", type=float, default=0.35)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--guidance", type=float, default=7.0)
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fp16", action="store_true")
    args = ap.parse_args()

    print(f"PyTorch {torch.__version__}, MPS={torch.backends.mps.is_available()}", flush=True)
    pipe = build_pipe(use_fp16=args.fp16)
    print("Pipeline chargé.", flush=True)

    init = Image.open(args.input).convert("RGB")
    init = fit_size(init, args.size)
    gen = torch.Generator(device="mps").manual_seed(args.seed)

    result = pipe(
        prompt=args.prompt,
        negative_prompt=args.negative,
        image=init,
        strength=args.strength,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        generator=gen,
    )
    out = result.images[0]
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out.save(args.output)
    # Vérif anti-image-noire (bug MPS fp16)
    import numpy as np
    a = np.array(out)
    print(json.dumps({
        "output": args.output,
        "size": out.size,
        "mean_luma": round(float(a.mean()), 2),
        "is_black": bool(a.mean() < 3),
    }, indent=2))


if __name__ == "__main__":
    main()
