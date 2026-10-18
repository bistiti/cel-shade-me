# COLOR.md — Recette : coloriser une figurine (Vallejo Mecha Color, 100% local)

Projet `~/figurine_paint`. Recette de référence, consolidée le 2026-10-09.
Pour l'utiliser depuis un nouveau fil : charger le skill `figurine-color-preview`,
lire ce fichier, appliquer le pipeline SANS rien réécrire.

## Sources de vérité de la palette
- `data/vallejo_mecha_palette.json` — 80 réfs, `hex`/`rgb` extraits pixel par
  pixel du nuancier, + `name`, équivalence Vallejo Model Color, Mr. Color,
  `category`. **Source de vérité des couleurs.**
- `data/CC337-Mecha_Color.pdf` — notice/nuancier officiel Vallejo (lire page 1).
- `data/mecha_color_chart.webp` — nuancier visuel officiel.

Gamme officielle CC337 (vérifiée, 80 produits) :
- 42 teintes Mecha Color `69.001`–`69.042`
- 4 fluorescents `69.054`–`69.057`
- 11 métalliques `69.058`–`69.068`
- 5 primers `70.640`–`70.644` (White, Grey, Black, Ivory, Sand)
- 11 Weathering (`69.505/507/515/518/521/522/813/814/817/818/821`)
- 7 auxiliaires : vernis Gloss `69.701` / Mat `69.702` / Satiné `69.703`,
  Airbrush Thinner, Flow Improver, Decal Softener `73.212`, Chipping Medium `73.214`

## Finition (corrigée via CC337)
Les 42 Mecha Color de base ont un acabado **SATINÉ**, pas mat. Séché, le film est
souple, durable, uniforme, et "reproduit l'aspect du plastique injecté en
préservant les détails". Donc dans toute instruction de rendu : **"satin acrylic
finish"**, jamais "matte". Pour unifier a posteriori : vernis 69.701/702/703
selon l'effet voulu.

## Conditions (non négociables)
- Couleurs = Vallejo Mecha Color (`69.0xx`), EXACTES, extraites du nuancier,
  jamais devinées. Peindre la couleur de la PASTILLE (le nom peut contredire la
  teinte réelle).
- Hex fourni sans code → réf Mecha la plus proche en distance Lab (deltaE),
  annoncée AVANT de peindre.
- 100% local sur ce Mac. (Historique : les tout premiers rendus du projet
  venaient de l'outil EN LIGNE Higgsfield/Seedream — modèle fermé, non
  téléchargeable. Remplacé par FLUX.1 Kontext en local, cf. plus bas.)
- Interpréteur = `python` (bundle Hermes 3.14.7 : torch 2.14.1 MPS, diffusers,
  cv2, numpy). JAMAIS `python3`.

## Style de peinture cible : CEL-SHADING
Règles issues des planches de référence fournies par l'utilisateur (2026-10-09) :
- Aplats de couleur **saturés**, finition satinée. PAS de dégradés, pas de fondu
  aérographe.
- **2 à 3 tons DURS par couleur** : base + une ombre plus foncée + une haute
  lumière plus claire, transitions à **bord net**.
- **Noir franc** dans TOUS les creux, coutures et lignes de séparation ; +
  **contour noir marqué** sur la silhouette et les grandes formes.
- Hautes lumières à **bord net** (pas de halo doux).
- Par matériau : métal = teinte froide (gris/bleu) + reflets spéculaires nets sur
  les arêtes ; peau/tissu = satin, chaud, ombre dure ; plastique/caoutchouc =
  aplats lisses peu réfléchissants.
- Verrouiller sculpt / pose / silhouette / proportions (ne pas changer la forme).

## Pipeline (2 couches, dans l'ordre)

### 1. Couche couleur EXACTE (vérité mesurée) — `recolor_vallejo.py`
Recolore une zone vers un code Vallejo par translation Lab : l'ombrage
(shadows/highlights) est préservé tout seul, on ne définit que la couleur de BASE
par zone. Le `deltaE` mesuré est la preuve objective de l'exactitude ; sert aussi
à choisir le pot réel.
```bash
cd /Users/macia/figurine_paint
python scripts/recolor_vallejo.py \
  --input SOURCE.png --output output/recolor_local/TAG_CODE.png \
  --map 'hue:CENTER:WIDTH:CODE[:STRENGTH][:satX][:valX][:roiX0,Y0,X1,Y1][:exX0,Y0,X1,Y1]'
```
Grammaire `--map` (répétable) : `hue:CENTRE:DEMI-LARGEUR:CODE` cible une teinte ;
`satX`/`valX` = seuils d'entrée dans le masque ; `roiX0,Y0,X1,Y1` limite la zone
en fractions 0-1 (ex `roi0,0,1,0.72` épargne le socle) ; `exX0,Y0,X1,Y1` exclut ;
`rgb:R,G,B:TOL:CODE` variante RGB ; `--list` / `--swatch`.

### 2. Finition peinte (rendu cel-shading) — FLUX.1 Kontext [dev], local
Remplace l'ancien SD1.5 + ControlNet-canny : sur une résine unie, SD1.5 avait
trop peu d'arêtes Canny à verrouiller et **inventait** une autre figurine. FLUX.1
Kontext est un modèle d'ÉDITION en contexte (il repeint l'image fournie selon une
instruction en gardant le sculpt). Validé sur fig1 : pose + sculpt préservés,
finition peinte propre.

Setup (poids OUVERTS, non-gated, dans `~/flux_kontext`) :
- `ComfyUI/` + venv isolé (`--system-site-packages`, réutilise le torch Hermes) +
  nœud `ComfyUI-GGUF`.
- `models/unet/flux1-kontext-dev-Q8_0.gguf` (12,7 Go, QuantStack)
- `models/clip/t5xxl_fp8_e4m3fn.safetensors` + `clip_l.safetensors` (comfyanonymous)
- `models/vae/ae.safetensors` (VAE FLUX, 16 latents vérifiés, miroir Comfy-Org)
- Install : `scripts/setup_flux_kontext.sh` (met `HF_HUB_DISABLE_XET=1` car le
  backend Xet/CAS de HF est en panne sur ce Mac).

Démarrage serveur :
```bash
source ~/flux_kontext/venv/bin/activate
cd ~/flux_kontext/ComfyUI
python main.py --listen 127.0.0.1 --port 8188 --lowvram --disable-auto-launch
```
Rendu (attend le serveur, vérifie les nœuds, rend, sauvegarde) :
```bash
# 3 paliers quant (lance ComfyUI avant) :
bash scripts/render_kontext.sh q4 SOURCE.jpg "INSTRUCTION" OUT.png  # rapide (Q4, 768/14)
bash scripts/render_kontext.sh q6 SOURCE.jpg "INSTRUCTION" OUT.png  # moyen  (Q6, 1024/22)
bash scripts/render_kontext.sh q8 SOURCE.jpg "INSTRUCTION" OUT.png  # qualite (Q8, 1024/26)
# direct : python scripts/flux_kontext_test.py SRC "INSTR" OUT.png [seed] [steps] [size] [quant]
```
Instruction type (cel-shading + satin, couleurs nommées depuis la palette) :
> Repaint this miniature in a bold CEL-SHADED comic / toon-shaded style, as a
> hand-painted tabletop figurine in studio macro. FLAT blocks of saturated color,
> NO gradients, NO soft blending. Each color only two or three hard tone steps
> (base + darker shadow + lighter highlight) with SHARP crisp edges. Clean BLACK
> ink in every recess, crevice, seam and separation + bold black outline on the
> silhouette and main shapes. Sharp-edged highlights, satin acrylic finish.
> Colors: <zone principale>=<nom/hex Vallejo>, <accessoires>=<...>, base=<...>.
> Keep the EXACT same sculpt, pose, silhouette and proportions.

Réserves honnêtes :
- Trois paliers qualité/vitesse par QUANTIFICATION (wrapper
  `scripts/render_kontext.sh q8|q6|q4`) : `q8` Q8_0 haute/lent (1024/26),
  `q6` Q6_K moyen (1024/22), `q4` Q4_K_M faible/rapide (768/14).
- Vitesse : ~17 min en full avec `--lowvram`. Avec la RAM libre, lancer ComfyUI
  SANS `--lowvram` (modeles gardes sur le device MPS, moins d'allers-retours)
  accelere nettement ; le mode rapide reduit encore. Quant Q6/Q4 = secours.
- Libérer la RAM avant un rendu : arrêter le backend figurine, vérifier
  `ollama ps` (aucun gros modèle chargé).
- Jugement "look peint" : le modèle vision local `qwen2.5vl:7b` surnote et n'est
  pas fiable → c'est l'UTILISATEUR qui valide visuellement. Les métriques
  (deltaE, IoU) restent la preuve objective pour la couleur et la structure.

## Mapping validé (exemples de référence)
- `02 crapaud`  : SZ Red `69.009` (#922125) — `hue:5:28:69.009:1.0:sat0.35:roi0,0,1,0.68` — deltaE 3 (exact)
- `04 demon`    : Sky Blue `69.017` (#09a9d0) — `hue:193:34:69.017:1.0:sat0.30:roi0,0,1,0.64`
- `05 gobelin`  : Yellow Fluorescent `69.054` (#e0dc14) — `hue:40:40:69.054:1.0:sat0.45:roi0,0,1,0.72`
- Réserve : 04 et 05 à deltaE ~22-24 (clipping de gamut sRGB sur cibles très
  saturées/claires). Teinte juste, saturation un cran sous le swatch.

## App Android (`android/`)
Éditeur pinceau au doigt (figurine non peinte mono-couleur → sélection par
couleur impossible) → zones → recolor exact + finition cel-shading. Backend local
`server.py` (endpoints `/recolor_strokes` avec `finish`, etc.). Défaut app = IP
Tailscale `100.93.53.15:8000`. À brancher : finition via FLUX.1 Kontext (en cours).

## Outils
- `scripts/recolor_vallejo.py`, `segment_region.py`, `flux_kontext_test.py`,
  `setup_flux_kontext.sh`, `dl_flux_kontext.py`, `dl_vae.py`.
- `scripts/extract_palette.py`, `enrich_palette.py`, `make_palette_cards.py`.
- Ancien moteur (superseded) : `paint_controlnet.py` (SD1.5+ControlNet-canny).
- Validation : deltaE Lab (couleur) + IoU contours Canny (structure), en Python inline.

## Config modèle (posée par l'utilisateur pour ce projet)
Réserve : sur le provider "anthropic" de ce Mac, `claude-sonnet-5`/`claude-sonnet-4`
renvoient 404 (seul `claude-opus-4-8` répond). Bascule/restauration :
`bash RESTORE_MODEL_CONFIG.sh`.
