#!/usr/bin/env python3
"""
Télécharge un modèle Stable Diffusion au format DIFFUSERS en contournant le
serveur CAS/Xet de HuggingFace (bug "CAS Client Error / reconstructions").
Force le chemin HTTP classique via HF_HUB_DISABLE_XET=1 + retries.
Variante fp16 uniquement (optimale pour MPS / Apple Silicon, ~2GB au lieu de ~4GB).
"""
import os
import sys
import time

# CONTOURNEMENT du serveur CAS/Xet en panne : force le téléchargement HTTP classique
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"

from huggingface_hub import snapshot_download

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "..", ".cache", "hf_models")
MARKER = os.path.join(HERE, "..", ".cache", "MODEL_READY.txt")

# Modèles par ordre de préférence
MODELS = [
    "runwayml/stable-diffusion-v1-5",
    "stable-diffusion-v1-5/stable-diffusion-v1-5",
    "Lykon/dreamshaper-8",
]

# Format diffusers, variante fp16 uniquement
ALLOW = [
    "model_index.json",
    "**/config.json",
    "**/*.fp16.safetensors",
    "tokenizer/*",
    "scheduler/*",
    "**/merges.txt",
    "**/vocab.json",
    "**/special_tokens_map.json",
    "**/tokenizer_config.json",
]
IGNORE = ["*.ckpt", "*.onnx", "*.pt", "*.bin", "*non_ema*",
          "safety_checker/*", "v1-5-pruned*", "*.msgpack", "*.h5"]

def try_download(repo_id, attempt):
    print(f"[attempt {attempt}] snapshot_download({repo_id}) fp16 [XET off]", flush=True)
    return snapshot_download(
        repo_id=repo_id,
        cache_dir=CACHE_DIR,
        allow_patterns=ALLOW,
        ignore_patterns=IGNORE,
        max_workers=2,
    )

def main():
    attempt = 0
    while True:
        attempt += 1
        for repo in MODELS:
            try:
                path = try_download(repo, attempt)
                with open(MARKER, "w") as f:
                    f.write(f"{repo}\n{path}\nvariant=fp16\n")
                print(f"SUCCESS: {repo} -> {path}", flush=True)
                return 0
            except Exception as e:
                print(f"  FAIL {repo}: {type(e).__name__}: {str(e)[:200]}", flush=True)
                continue
        wait = min(300, 30 * attempt)
        print(f"  Toutes sources KO (passe {attempt}). Retry dans {wait}s...", flush=True)
        if attempt >= 40:
            print("ABANDON apres 40 passes.", flush=True)
            return 1
        time.sleep(wait)

if __name__ == "__main__":
    sys.exit(main())
