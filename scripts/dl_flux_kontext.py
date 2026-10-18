"""Telecharge les poids OUVERTS pour FLUX.1 Kontext [dev] dans l'arbo ComfyUI.
Tout est non-gated (QuantStack GGUF, comfyanonymous text encoders, VAE de
FLUX.1-schnell Apache-2.0). Aucun compte/token HF requis."""
import os
from huggingface_hub import hf_hub_download, list_repo_files

COMFY = os.path.expanduser("~/flux_kontext/ComfyUI")


def grab(repo, fname, subdir):
    dst = os.path.join(COMFY, "models", subdir)
    os.makedirs(dst, exist_ok=True)
    out = os.path.join(dst, os.path.basename(fname))
    if os.path.exists(out) and os.path.getsize(out) > 1_000_000:
        print("  deja la:", out, round(os.path.getsize(out) / 1e9, 2), "GB", flush=True)
        return out
    print("  download", repo, fname, "...", flush=True)
    hf_hub_download(repo_id=repo, filename=fname, local_dir=dst)
    print("  ok:", out, round(os.path.getsize(out) / 1e9, 2), "GB", flush=True)
    return out


# 1) transformer Kontext quantifie Q8 (meilleure qualite qui tient en 32 Go)
files = list_repo_files("QuantStack/FLUX.1-Kontext-dev-GGUF")
q8 = sorted(f for f in files if f.endswith(".gguf") and "Q8_0" in f)
print("GGUF candidates:", q8, flush=True)
grab("QuantStack/FLUX.1-Kontext-dev-GGUF", q8[0], "unet")

# 2) encodeurs de texte (T5-XXL fp8 pour economiser la RAM + CLIP-L)
grab("comfyanonymous/flux_text_encoders", "t5xxl_fp8_e4m3fn.safetensors", "clip")
grab("comfyanonymous/flux_text_encoders", "clip_l.safetensors", "clip")

# 3) VAE (ae) depuis FLUX.1-schnell (Apache-2.0, non-gated, meme VAE que Kontext)
grab("black-forest-labs/FLUX.1-schnell", "ae.safetensors", "vae")

print("DOWNLOADS DONE", flush=True)
