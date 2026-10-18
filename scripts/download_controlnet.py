#!/usr/bin/env python3
"""
Télécharge un ControlNet SD1.5 (format diffusers) en contournant le serveur
CAS/Xet de HuggingFace. Essaie la variante fp16, retombe sur fp32 sinon.
"""
import os
import sys

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"

from huggingface_hub import snapshot_download

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "..", ".cache", "hf_models")
REPO = sys.argv[1] if len(sys.argv) > 1 else "lllyasviel/control_v11p_sd15_canny"
MARKER = os.path.join(HERE, "..", ".cache",
                      "CONTROLNET_READY_" + REPO.split("/")[-1] + ".txt")


def dl(allow):
    return snapshot_download(
        repo_id=REPO, cache_dir=CACHE_DIR,
        allow_patterns=allow,
        ignore_patterns=["*.ckpt", "*.pt", "*.bin", "*.onnx", "*.pth"],
        max_workers=2,
    )


def has_model(path):
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".safetensors"):
                return True
    return False


def main():
    # 1) tente fp16
    try:
        p = dl(["*.json", "*.fp16.safetensors"])
        if not has_model(p):
            raise RuntimeError("pas de .fp16.safetensors, fallback fp32")
        variant = "fp16"
    except Exception as e:
        print(f"fp16 KO ({str(e)[:120]}), fallback fp32", flush=True)
        p = dl(["*.json", "*.safetensors"])
        variant = "fp32"
    with open(MARKER, "w") as f:
        f.write(f"{REPO}\n{p}\nvariant={variant}\n")
    print(f"SUCCESS {REPO} [{variant}] -> {p}", flush=True)


if __name__ == "__main__":
    main()
