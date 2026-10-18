"""Test FLUX.1 Kontext via l'API ComfyUI (suppose le serveur lance sur 127.0.0.1:8188).
Usage: python flux_kontext_test.py SOURCE.jpg "instruction de repeinture" OUT.png [seed] [steps]
Edite l'image source selon l'instruction en gardant le sculpt (modele d'edition
en contexte). Rend via le GGUF Q8 + T5-XXL fp8 + CLIP-L + VAE telecharges."""
import sys, os, json, time, uuid, shutil, urllib.request
from PIL import Image

COMFY = os.path.expanduser("~/flux_kontext/ComfyUI")
SRV = "http://127.0.0.1:8188"


def api(path, data=None, timeout=600):
    url = SRV + path
    if data is not None:
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    return urllib.request.urlopen(req, timeout=timeout).read()


def wait_server(timeout=180):
    t = time.time()
    while time.time() - t < timeout:
        try:
            api("/object_info", timeout=5); return True
        except Exception:
            time.sleep(2)
    return False


def build_wf(image_name, prompt, seed, steps, tw, th, unet):
    return {
        "unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": unet}},
        "clip": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "load": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "scale": {"class_type": "ImageScale", "inputs": {"image": ["load", 0], "upscale_method": "lanczos", "width": tw, "height": th, "crop": "disabled"}},
        "enc": {"class_type": "VAEEncode", "inputs": {"pixels": ["scale", 0], "vae": ["vae", 0]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "ref": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos", 0], "latent": ["enc", 0]}},
        "guid": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["ref", 0], "guidance": 2.5}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["clip", 0]}},
        "ks": {"class_type": "KSampler", "inputs": {
            "model": ["unet", 0], "positive": ["guid", 0], "negative": ["neg", 0],
            "latent_image": ["enc", 0], "seed": seed, "steps": steps, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": "kontext_test"}},
    }


def main():
    src, prompt, out = sys.argv[1], sys.argv[2], sys.argv[3]
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42
    steps = int(sys.argv[5]) if len(sys.argv) > 5 else 26
    size = int(sys.argv[6]) if len(sys.argv) > 6 else 1024
    quant = sys.argv[7] if len(sys.argv) > 7 else "Q8_0"
    unet = f"flux1-kontext-dev-{quant}.gguf"
    if not wait_server():
        print("ERREUR: serveur ComfyUI injoignable sur", SRV); sys.exit(1)
    info = json.loads(api("/object_info"))
    need = ["UnetLoaderGGUF", "DualCLIPLoader", "VAELoader", "ImageScale",
            "ReferenceLatent", "FluxGuidance", "KSampler", "VAEEncode", "VAEDecode",
            "LoadImage", "CLIPTextEncode", "SaveImage"]
    missing = [n for n in need if n not in info]
    if missing:
        print("NOEUDS MANQUANTS:", missing); sys.exit(2)
    os.makedirs(COMFY + "/input", exist_ok=True)
    img_name = "src_" + uuid.uuid4().hex[:8] + os.path.splitext(src)[1]
    shutil.copy(src, COMFY + "/input/" + img_name)
    sw, sh = Image.open(src).size
    sc = size / max(sw, sh)
    tw = max(16, int(round(sw * sc / 16)) * 16)
    th = max(16, int(round(sh * sc / 16)) * 16)
    print("render", tw, "x", th, "| steps", steps, "| unet", unet, flush=True)
    wf = build_wf(img_name, prompt, seed, steps, tw, th, unet)
    r = json.loads(api("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex}))
    if r.get("node_errors"):
        print("ERREURS DE NOEUDS:", json.dumps(r["node_errors"])[:1500]); sys.exit(3)
    pid = r.get("prompt_id")
    if not pid:
        print("ECHEC submit:", r); sys.exit(3)
    print("job soumis:", pid, "| steps", steps, "seed", seed, flush=True)
    t = time.time()
    while time.time() - t < 1800:
        try:
            h = json.loads(api("/history/" + pid, timeout=10))
        except Exception:
            time.sleep(3); continue
        if pid in h:
            st = h[pid].get("status", {})
            if h[pid].get("outputs"):
                for _, o in h[pid]["outputs"].items():
                    for im in o.get("images", []):
                        q = f"/view?filename={im['filename']}&subfolder={im.get('subfolder','')}&type={im.get('type','output')}"
                        open(out, "wb").write(api(q))
                        print("SAVED", out, round(os.path.getsize(out) / 1e6, 2), "MB in",
                              round(time.time() - t, 1), "s", flush=True)
                        return
            if st.get("status_str") == "error":
                print("ERREUR EXECUTION:", json.dumps(st.get("messages", []))[:1500]); sys.exit(5)
        time.sleep(3)
    print("TIMEOUT rendu"); sys.exit(4)


main()
