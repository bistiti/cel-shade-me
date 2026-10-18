#!/usr/bin/env bash
# Backend de colorisation de figurines — 100% local sur ce Mac (MPS).
cd "$(dirname "$0")"
export PORT="${PORT:-8000}"
LAN=$(ipconfig getifaddr en0 2>/dev/null || echo "127.0.0.1")
echo "Backend sur http://0.0.0.0:$PORT   (depuis le telephone en LAN: http://$LAN:$PORT)"
echo "Le modele ControlNet se charge au 1er /paint ou /process (quelques secondes)."
# Resolution robuste de l'interpreteur (launchd a un PATH minimal : `python` absent).
PYBIN="${PYBIN:-$(command -v python 2>/dev/null)}"
if [ ! -x "$PYBIN" ]; then
  PYBIN=$(ls -1 "$HOME"/.hermes/tools/python-3.14.7*/bin/python 2>/dev/null | head -n1)
fi
echo "python: $PYBIN"
exec "$PYBIN" server.py
