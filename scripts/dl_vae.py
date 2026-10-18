"""Recupere le VAE FLUX (ae.safetensors) depuis un miroir Comfy-Org non-gated,
le place dans ComfyUI/models/vae, et VERIFIE sa structure (famille FLUX = 16
canaux latents, soit un encoder.conv_out a 32 sorties = mean+logvar)."""
import os, json, struct, shutil
os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import hf_hub_download

COMFY = os.path.expanduser("~/flux_kontext/ComfyUI")
dst = os.path.join(COMFY, "models", "vae")
os.makedirs(dst, exist_ok=True)
out = os.path.join(dst, "ae.safetensors")

if not (os.path.exists(out) and os.path.getsize(out) > 1_000_000):
    p = hf_hub_download("Comfy-Org/z_image_turbo", "split_files/vae/ae.safetensors", local_dir="/tmp/vae_dl")
    shutil.copy(p, out)
print("fichier:", out, round(os.path.getsize(out) / 1e6, 1), "MB")

with open(out, "rb") as f:
    n = struct.unpack("<Q", f.read(8))[0]
    hdr = json.loads(f.read(n))
keys = [k for k in hdr if k != "__metadata__"]
print("nb tenseurs:", len(keys))
enc_dec = [k for k in keys if k.startswith(("encoder.", "decoder."))]
print("cles encoder/decoder:", len(enc_dec))
for k in keys:
    if k.endswith(("conv_in.weight", "conv_out.weight")) and ("encoder" in k or "decoder" in k):
        print(" ", k, hdr[k]["shape"], hdr[k]["dtype"])
# verdict
latent_ok = any(k.endswith("encoder.conv_out.weight") and hdr[k]["shape"][0] in (32,) for k in keys)
print("STRUCTURE FLUX (16 latents / conv_out=32):", "OUI" if latent_ok else "A VERIFIER")
