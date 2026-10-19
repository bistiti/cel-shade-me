# Cel-Shade-Me

Prévisualiser une figurine peinte, en local, avec des couleurs Vallejo **exactes**.

On photographie une figurine (brute ou déjà peinte), on choisit des références Vallejo
Mecha Color, et l'application rend un aperçu « figurine peinte » en cel-shading : aplats
francs, deux ou trois tons durs par couleur, traits noirs dans les creux. Tout tourne
sur ta machine. Aucun service en ligne, aucune donnée qui sort.

Deux usages dans l'app :
- **Sans peinture** : toute la figurine (socle compris) prend une seule couleur Vallejo.
- **Peindre au doigt** : on peint des zones au doigt, chacune avec sa couleur, et une
  bande d'harmonie reste affichée à droite pour garder un ensemble cohérent.

## Pourquoi c'est fiable

Les couleurs ne sont jamais devinées. Les 80 références Vallejo Mecha Color sont
extraites pixel par pixel des pastilles réelles (`data/vallejo_mecha_palette.json`). Une
couleur donnée en hex sans référence est ramenée à la référence Mecha la plus proche en
distance Lab, et annoncée avant d'être posée.

Le rendu cel-shading est **déterministe** : pas de modèle d'image génératif, donc pas
d'hallucination (pas d'yeux lumineux inventés, pas d'effets magiques), couleurs exactes,
et un rendu quasi instantané (~0,2 s par image).

## Architecture

- **App Android** (Kotlin + Jetpack Compose) : dossiers, galerie, appareil photo et
  import, éditeur de peinture au doigt, harmonies, i18n FR/ES/EN.
- **Backend local** (Python + Starlette, sur le Mac) : palette, harmonies, recoloration
  Lab exacte, moteur cel-shading. Exposé hors du réseau local via Tailscale.
- **Moteur cel déterministe** (numpy + OpenCV + Pillow) : voir « Étapes » ci-dessous.

Deux distributions prévues :
1. **Tailscale** : l'app parle au backend sur le Mac (via Tailscale hors du LAN).
2. **100 % embarquée** : tout le pipeline cel tourne sur le téléphone (portage
   Kotlin + OpenCV Android), sans machine ni serveur. Possible justement parce que le
   moteur est déterministe et léger.

## Étapes du projet

1. **Palette Vallejo exacte.** Extraction des 80 réfs Mecha Color (RGB pixel-exact) →
   `data/vallejo_mecha_palette.json`. Jamais de couleur inventée.
2. **Recoloration Lab.** Remplacement d'une zone par une réf Vallejo exacte en conservant
   l'ombrage, avec mesure du delta E (`scripts/recolor_vallejo.py`).
3. **Harmonies.** Schémas (analogue, complémentaire, split, triade, tétradique, carré,
   monochrome) ramenés aux réfs Vallejo les plus proches.
4. **Backend HTTP.** `backend/server.py` : `/palette`, `/harmony`, `/recolor`, `/process`,
   plus le flux cel.
5. **Masque figurine.** Séparer la figurine du fond : floodFill depuis les 4 coins (gère
   les fonds en dégradé ou bi-ton), puis détection des couleurs de fond par k-means pour
   récupérer les poches enfermées (entre les jambes, sous un bras), avec un garde-fou qui
   désactive cette détection quand figurine et fond partagent les mêmes tons (figurine
   sombre sur fond noir), et retrait des poches quasi-noires.
6. **Moteur cel.** Première version via FLUX.1 Kontext en local (ComfyUI). Abandonnée :
   trop lente (~17 min/image), elle hallucinait (lueurs, objets inventés) et n'ombrait
   franchement que les petits détails. Remplacée par une **posterisation déterministe** :
   la luminance de la sculpture est quantifiée en 2-3 bandes dures, chaque bande snappée
   sur un ton dérivé de la couleur Vallejo (ombre / base / highlight en HSV), puis encrage
   OpenCV (Canny) dans les reliefs. Instantané, exact, sans hallucination.
7. **Application Android.** Dossiers et galerie, photo in-app ou import, éditeur au doigt
   (6 tailles de pinceau), deux modes (une couleur / zones), bande d'harmonie figée,
   multi-sélection par appui long (déplacer / renommer / supprimer), export vers la
   galerie du téléphone, rendu asynchrone avec notification, FR/ES/EN.
8. **Exposition hors LAN.** Tailscale pour joindre le backend du Mac depuis le téléphone.

## Structure du dépôt

```
android/            app Android (Kotlin/Compose)
backend/server.py   backend local (Starlette) + moteur cel
scripts/            recolor_vallejo.py, cel_posterize.py, outils
data/               palette Vallejo Mecha (80 réfs)
COLOR.md            notes de pipeline et décisions
```

## Statut

Prototype fonctionnel et utilisé. Le moteur cel déterministe est la voie active. Les
deux APK (Tailscale et 100 % embarquée) sont en préparation dans les Releases.

## Installation

- Version Tailscale (app + backend sur le Mac, avec en option le mode réaliste FLUX et
  sa config modèles) : voir `docs/TAILSCALE.md`.
- Version 100 % embarquée (tout sur le téléphone, sans serveur ni réseau) : voir
  `docs/EMBEDDED.md`.
