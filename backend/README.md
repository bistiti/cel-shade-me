# Backend de colorisation de figurines (local, Mac)

Petite API HTTP qui enveloppe les scripts deja valides du projet
(`scripts/recolor_vallejo.py` et `scripts/paint_controlnet.py`) pour qu'un
telephone (ou tout client) puisse envoyer une photo et recevoir la figurine
recolorisee aux couleurs Vallejo Mecha exactes, plus un rendu peint ControlNet.

Tout tourne sur ce Mac (MPS). Aucun service en ligne. Le modele SD1.5 +
ControlNet-canny est charge une seule fois, au premier `/paint` ou `/process`,
puis garde chaud.

## Lancer

```bash
cd ~/figurine_paint/backend
./run_backend.sh            # ecoute sur 0.0.0.0:8000
```

Il affiche l'URL LAN a ouvrir depuis le telephone (meme Wi-Fi), par ex :
`http://10.1.70.88:8000/app/`. Si l'IP du Mac change, relis-la avec
`ipconfig getifaddr en0`.

Dependances (deja installees dans le python du projet) : `starlette`, `uvicorn`,
`python-multipart` (voir `requirements.txt`). torch/diffusers/numpy/pillow/opencv
viennent du python Hermes du projet.

## Deux clients

1. **Client web mobile (pret, teste)** : `http://<ip-du-mac>:8000/app/`
   Ouvre l'appareil photo, envoie la photo, affiche couleur exacte + rendu peint.
   Zero installation. C'est le chemin le plus rapide pour utiliser ca sur telephone.
2. **App Android native** : dossier `../android/` (source, a compiler dans
   Android Studio ; voir son README).

## Endpoints

- `GET /` : redirige vers `/app/`.
- `GET /health` : etat, device MPS, taille palette.
- `GET /palette` : les 80 refs Vallejo Mecha `{code, hex, rgb, name}`.
- `POST /recolor` (multipart) : `file` + soit `map` (grammaire CLI, repetable),
  soit `code` (ciblage auto par teinte dominante). Renvoie `image/png`,
  metriques dans l'en-tete `X-Report`.
- `POST /paint` (multipart) : `file` + `prompt` et parametres ControlNet
  (`steps`, `size`, `strength`, `cn_scale`, `canny_low/high`, `guidance`, `seed`).
  Renvoie `image/png`.
- `POST /process` (multipart) : `file` + `code` [+ `do_paint`, `steps`, `size`,
  `roi`, `width`, `min_sat`, `prompt`]. Enchaine recolor (auto) puis paint.
  Renvoie du JSON avec les URLs `/files/<id>/...` et les metriques.
- `GET /files/<id>/...` : sorties statiques (sous `output/app/`).

## Les contraintes du projet, cote backend

- Couleurs Vallejo exactes : `data/vallejo_mecha_palette.json` (refs deja
  verifiees) est la seule source. Pas de couleur devinee.
- Recoloration = translation Lab (ombrage preserve). `/recolor` et l'etape 1
  de `/process` reutilisent `recolor_vallejo.recolor_region` tel quel.
- Pose/sculpt verrouilles : `/paint` reutilise `paint_controlnet.build_pipe`
  (ControlNet-canny conditionne sur la photo).
- Socle epargne : parametre `roi` (defaut haut 72%), comme le ROI de la CLI.
- Validation : chaque reponse donne la couverture, l'ecart Lab (deltaE) mesure
  sur la sortie, et pour le paint le `mean_luma`/`is_black`.

## Tester

```bash
./smoketest.sh                      # contre un serveur deja lance
# ou, cible precise :
./smoketest.sh http://127.0.0.1:8000 ../output/palettes_v2/02_crapaud.png
```

## Garder le backend allume

Pour un usage regulier, lance-le dans un `tmux`/`screen`, ou fais-en un
LaunchAgent. Pour l'atteindre hors du LAN, un tunnel type Tailscale ou
Cloudflare Tunnel evite d'ouvrir un port.
