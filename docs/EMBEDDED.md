# Version embarquée (embedded)

Tout tourne sur le téléphone. Pas de Mac, pas de backend, pas de Tailscale, aucun réseau.
L'app charge une photo, tu choisis des couleurs Vallejo, et le rendu cel se fait sur place.

C'est possible parce que le moteur cel est déterministe et léger : du traitement d'image
(OpenCV), pas de modèle IA. Le portage Kotlin reproduit exactement le pipeline du backend.

## Installer

Prends l'APK `embedded` dans les Releases et installe-le. Il porte un nom de paquet
distinct (`com.figurinecolor.app.embedded`), donc il peut cohabiter avec la version
Tailscale sur le même téléphone.

- Taille : ~34 Mo (il embarque la bibliothèque native OpenCV, `libopencv_java4.so`).
- Architecture : arm64-v8a (téléphones récents et émulateur Apple Silicon).

## Utiliser

1. Crée un dossier, puis ajoute une photo (appareil photo ou import).
2. Sans peinture : choisis une couleur Vallejo comme couleur principale, puis Coloriser.
   Toute la figurine (socle compris) est peinte dans cette couleur, avec le cel-shading et
   les traits noirs.
3. Peindre au doigt : peins des zones au doigt, une couleur par zone. La bande d'harmonie
   à droite propose des couleurs assorties, snappées sur la gamme Vallejo.

La palette Vallejo (80 réfs) et les harmonies sont embarquées en asset et calculées en
local, comme le rendu. Le résultat se télécharge vers la galerie du téléphone.

## Aperçu cel en direct

Depuis un dossier, le bouton « Aperçu live » ouvre la caméra et applique le cel en temps
réel sur ce que tu vises, dans la couleur Vallejo de ton choix. À utiliser sur un fond uni.
C'est honnêtement un filtre 2D en direct, pas de l'AR 3D : le rendu se recalcule image par
image, il ne suit pas la figurine en 3D quand tu tournes autour. Le bouton Capturer
enregistre l'image filtrée comme photo du dossier. Tout est calculé sur le téléphone
(OpenCV), sans réseau.

## Différence avec la version Tailscale

Cette version ne fait que le cel déterministe. Le mode réaliste optionnel (FLUX.1 Kontext)
n'existe que dans la version Tailscale, parce qu'il a besoin du GPU du Mac. Ici, pas de
dépendance à une machine : c'est le compromis, et c'est voulu.
