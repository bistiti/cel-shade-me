# Version Tailscale

L'app parle à un backend qui tourne sur ton Mac. Tailscale sert juste à joindre ce
backend depuis le téléphone quand tu n'es pas sur le même Wi-Fi. Tout le calcul reste
sur ta machine, rien ne part sur Internet.

Si tu veux une app qui marche sans Mac et sans réseau, prends plutôt la version
embarquée (voir `EMBEDDED.md`). Cette version-ci existe pour une raison : elle peut, en
option, passer par un vrai modèle d'image (FLUX.1 Kontext) pour une finition plus
réaliste que le cel déterministe. C'est le seul endroit du projet où il y a des modèles IA.

## 1. Le backend sur le Mac

Le serveur est dans `backend/` (Starlette + uvicorn). Dépendances : `numpy`,
`opencv-python` (cv2), `Pillow`, `starlette`, `uvicorn`. Le mode réaliste optionnel ajoute
`torch` (voir plus bas). Elles sont listées dans `backend/requirements.txt`.

Lancer :

    cd backend
    bash run_backend.sh

Le script écoute sur le port 8000 (`http://0.0.0.0:8000`) et affiche l'adresse LAN du Mac.
Par défaut le moteur cel est **déterministe** : aucun modèle IA, rendu quasi instantané.

## 2. Tailscale

Pour joindre le Mac hors du Wi-Fi local.

1. Installe Tailscale sur le Mac et sur le téléphone, connecte les deux au même compte
   (même tailnet).
2. Récupère l'adresse Tailscale du Mac (elle commence par `100.`), par exemple avec
   `tailscale ip -4` sur le Mac.
3. Dans l'app, Réglages, mets l'URL du backend : `http://<ip-tailscale-du-mac>:8000`.
   En Wi-Fi local tu peux aussi utiliser l'adresse LAN affichée par `run_backend.sh`.

Le Mac doit rester allumé et le backend lancé pour que l'app rende quoi que ce soit.

## 3. Les deux moteurs de rendu

### Déterministe (par défaut, aucun modèle IA)

Posterisation de la luminance de la sculpture en 2-3 tons durs par couleur, snappés sur la
couleur Vallejo, plus l'encrage des creux. Zéro hallucination, couleurs exactes, ~0,2 s.
N'a besoin que de numpy, OpenCV et Pillow. C'est ce que fait l'app par défaut.

### Réaliste, optionnel (FLUX.1 Kontext, local via ComfyUI)

Pour une finition plus photo-réaliste que les aplats cel. C'est lent et ça peut
réinterpréter la figurine (c'est précisément pourquoi le déterministe est le défaut), mais
la config est documentée ici puisque ce sont les modèles IA du projet.

Pile : un serveur ComfyUI local, appelé par le backend.

- ComfyUI : `~/flux_kontext/ComfyUI`, serveur sur `http://127.0.0.1:8188`
  (surchargeable par la variable d'environnement `COMFY_SRV`).
- Le backend : `COMFY_DIR = ~/flux_kontext/ComfyUI`.

Modèles et leur emplacement dans ComfyUI :

- UNet (GGUF), dans `ComfyUI/models/unet/`, chargé via `UnetLoaderGGUF` :
  - `flux1-kontext-dev-Q4_K_M.gguf`  (mode q4, le plus léger)
  - `flux1-kontext-dev-Q6_K.gguf`    (mode q6)
  - `flux1-kontext-dev-Q8_0.gguf`    (mode q8, le plus net, le plus lourd)
- Encodeurs de texte (CLIP), dans `ComfyUI/models/clip/`, via `DualCLIPLoader` (type flux) :
  - `t5xxl_fp8_e4m3fn.safetensors`
  - `clip_l.safetensors`
- VAE, dans `ComfyUI/models/vae/`, via `VAELoader` :
  - `ae.safetensors`

Le mode (q4/q6/q8) choisit la quantification de l'UNet et fixe les pas et la taille :

- q4 : 14 pas, 768 px
- q6 : 22 pas, 1024 px
- q8 : 26 pas, 1024 px

Matériel : Mac Apple Silicon (le backend utilise torch sur MPS). Sur un M1 Max 32 Go, une
image FLUX Kontext prend de l'ordre de 15 à 20 minutes selon le mode. À réserver aux cas
où tu veux vraiment le rendu réaliste.

Note honnête sur le prompt FLUX : le workflow tourne à cfg 1.0 avec un négatif vide, donc
tout texte est lu comme du positif. Ne liste jamais ce que tu ne veux pas (écrire « pas de
lueur » ajoute de la lueur). Le prompt est formulé 100 % en positif pour cette raison.
