#!/usr/bin/env bash
# Finition locale des figurines 02 / 04 / 05 :
#   1) recoloration Lab EXACTE vers le code Vallejo choisi par l'utilisateur
#   2) repaint ControlNet-canny (structure verrouillee), style peint/studio
# Params regles par mesure de teinte + inspection de composition (ROI socle).
# IMPORTANT : interprete = `python` (bundle Hermes 3.14.7 avec torch/diffusers/cv2),
#             surtout PAS `python3` (CommandLineTools, sans paquets).
cd /Users/macia/figurine_paint
PY=python
mkdir -p output/recolor_local output/controlnet

run_fig () {
  local tag="$1" src="$2" mask="$3" code="$4" prompt="$5"
  echo ""
  echo "############ $tag ############"
  if [ ! -f "$src" ]; then echo "$tag SOURCE_MANQUANTE: $src"; return; fi
  echo "---- $tag : recolor Lab -> $code ----"
  $PY scripts/recolor_vallejo.py --input "$src" \
      --output "output/recolor_local/${tag}_${code}.png" --map "$mask" \
      || { echo "$tag RECOLOR_FAILED"; return; }
  echo "---- $tag : ControlNet-canny repaint ----"
  $PY scripts/paint_controlnet.py \
      --input "output/recolor_local/${tag}_${code}.png" \
      --output "output/controlnet/${tag}_cn.png" \
      --save-canny "output/controlnet/${tag}_canny.png" \
      --prompt "$prompt" \
      --strength 0.55 --cn-scale 0.9 --canny-low 100 --canny-high 200 \
      --steps 26 --guidance 7.0 --size 704 --seed 42 \
      || { echo "$tag CONTROLNET_FAILED"; return; }
  echo "$tag OK"
}

run_fig "02_crapaud" "output/palettes_v2/02_crapaud.png" \
  "hue:5:28:69.009:1.0:sat0.35:roi0,0,1,0.68" "69009" \
  "hand-painted resin tabletop miniature, frilled toad creature, deep red matte acrylic skin with black markings, Vallejo cel-shading box-art, studio macro photography, shallow depth of field, neutral gradient background"

run_fig "04_demon" "output/palettes_v2/04_demon_skyblue.png" \
  "hue:193:34:69.017:1.0:sat0.30:roi0,0,1,0.64" "69017" \
  "hand-painted resin tabletop miniature, armored plated demon, sky blue matte acrylic with black armor plates, Vallejo cel-shading box-art, studio macro photography, shallow depth of field, neutral gradient background"

run_fig "05_gobelin_souriant" "output/palettes_v2/05_gobelin_souriant.png" \
  "hue:40:40:69.054:1.0:sat0.45:roi0,0,1,0.72" "69054" \
  "hand-painted resin tabletop miniature, grinning goblin frog warrior, fluorescent yellow matte acrylic skin with black markings and black armor, Vallejo cel-shading box-art, studio macro photography, shallow depth of field, neutral gradient background"

echo ""
echo "ALL_FIGURES_DONE"
ls -la output/controlnet/*_cn.png 2>/dev/null
