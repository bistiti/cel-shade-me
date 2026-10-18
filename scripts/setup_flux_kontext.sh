#!/usr/bin/env bash
# Installe ComfyUI + noeud GGUF dans un venv ISOLE (herite du torch/diffusers
# Hermes via --system-site-packages, pour ne rien casser), puis telecharge les
# poids FLUX.1 Kontext ouverts. Idempotent : relancable sans tout refaire.
set -e
export HF_HUB_DISABLE_XET=1   # contourne la panne serveur HF Xet/CAS (force le telechargement classique)
ROOT="$HOME/flux_kontext"
COMFY="$ROOT/ComfyUI"
mkdir -p "$ROOT"
echo "[setup] start $(date)"

BASEPY="$(command -v python)"
echo "[setup] base python = $BASEPY"
"$BASEPY" -c "import torch;print('[setup] torch',torch.__version__,'mps',torch.backends.mps.is_available())"

echo "[setup] 1/5 clone ComfyUI"
[ -d "$COMFY/.git" ] || git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "$COMFY"

echo "[setup] 2/5 venv (herite site-packages Hermes)"
[ -d "$ROOT/venv" ] || "$BASEPY" -m venv --system-site-packages "$ROOT/venv"
# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate"
python -m pip install -q --upgrade pip

echo "[setup] 3/5 deps ComfyUI (garde les versions deja satisfaites: torch, etc.)"
python -m pip install -q -r "$COMFY/requirements.txt"

echo "[setup] 4/5 noeud ComfyUI-GGUF"
GG="$COMFY/custom_nodes/ComfyUI-GGUF"
[ -d "$GG/.git" ] || git clone --depth 1 https://github.com/city96/ComfyUI-GGUF "$GG"
python -m pip install -q gguf

echo "[setup] 5/5 telechargement des modeles (~18 Go)"
mkdir -p "$COMFY/models/unet" "$COMFY/models/clip" "$COMFY/models/vae"
python /Users/macia/figurine_paint/scripts/dl_flux_kontext.py

echo "[setup] DONE $(date)"
echo "[setup] unet:"; ls -la "$COMFY/models/unet" 2>/dev/null | awk '{print $5,$NF}'
echo "[setup] clip:"; ls -la "$COMFY/models/clip" 2>/dev/null | awk '{print $5,$NF}'
echo "[setup] vae:";  ls -la "$COMFY/models/vae" 2>/dev/null | awk '{print $5,$NF}'
