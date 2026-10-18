"""Telecharge les quantifications Q4_K_M (rapide) puis Q6_K (moyen) de FLUX.1
Kontext, en plus du Q8_0 deja present. Poids non-gated (QuantStack), Xet off."""
import os
os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import hf_hub_download, list_repo_files

COMFY = os.path.expanduser("~/flux_kontext/ComfyUI")
dst = os.path.join(COMFY, "models", "unet")
os.makedirs(dst, exist_ok=True)
files = list_repo_files("QuantStack/FLUX.1-Kontext-dev-GGUF")
for tag in ["Q4_K_M", "Q6_K"]:
    cand = [f for f in files if f.endswith("-" + tag + ".gguf")]
    if not cand:
        print("INTROUVABLE:", tag, "| gguf dispo:", [f for f in files if f.endswith('.gguf')]); continue
    fn = cand[0]
    out = os.path.join(dst, os.path.basename(fn))
    if os.path.exists(out) and os.path.getsize(out) > 1_000_000:
        print("deja la:", out, round(os.path.getsize(out) / 1e9, 2), "GB", flush=True); continue
    print("download", fn, "...", flush=True)
    hf_hub_download("QuantStack/FLUX.1-Kontext-dev-GGUF", fn, local_dir=dst)
    print("ok:", out, round(os.path.getsize(out) / 1e9, 2), "GB", flush=True)
print("QUANTS DONE", flush=True)
