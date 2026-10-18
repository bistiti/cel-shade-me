#!/usr/bin/env bash
# Rendu FLUX.1 Kontext, 3 paliers de quantification.
#   bash render_kontext.sh q8|q6|q4 SRC.jpg "INSTRUCTION" OUT.png [seed]
# q8=haute/lent (1024/26) ; q6=moyen (1024/22) ; q4=rapide (768/14). Alias: high/medium/low, full/fast.
# Prerequis : serveur ComfyUI deja lance (cf. COLOR.md).
set -e
MODE="${1:-full}"; SRC="$2"; PROMPT="$3"; OUT="$4"; SEED="${5:-42}"
case "$MODE" in
  q8|high|full)  QUANT=Q8_0;   STEPS=26; SIZE=1024 ;;
  q6|medium)     QUANT=Q6_K;   STEPS=22; SIZE=1024 ;;
  q4|low|fast)   QUANT=Q4_K_M; STEPS=14; SIZE=768 ;;
  *) echo "mode inconnu: $MODE (attendu: q8|q6|q4)"; exit 2 ;;
esac
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:8188/object_info/UnetLoaderGGUF; then
  echo "[render] ComfyUI non joignable sur :8188 — demarre-le d'abord (voir COLOR.md)"; exit 3
fi
echo "[render] mode=$MODE quant=$QUANT size=$SIZE steps=$STEPS seed=$SEED"
cd /Users/macia/figurine_paint
exec python scripts/flux_kontext_test.py "$SRC" "$PROMPT" "$OUT" "$SEED" "$STEPS" "$SIZE" "$QUANT"
