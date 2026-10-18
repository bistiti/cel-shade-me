# App Android Figurine Color (source)

Client natif (Kotlin + Jetpack Compose) pour le backend local `../backend`.
Il prend/choisit une photo de figurine, charge la palette Vallejo depuis le
backend, laisse choisir une couleur, et affiche la recoloration exacte plus
le rendu peint optionnel.

## Statut

Compile avec succes sur ce Mac (chaine installee sans sudo : JDK17 + Gradle
8.10.2 + Android SDK 34). L'APK debug est produit et servi pour installation
directe sur le telephone : `http://<ip-du-mac>:8000/app/figurine-color.apk`.
Compilation = OK ; le comportement a l'execution (UI, appareil photo, chargement
reseau) reste a valider sur un vrai telephone. Android Studio est installe dans
/Applications pour iterer. Toolchain CLI : `source ~/android-tools/env.sh` puis
`cd android && gradle assembleDebug`.

## Compiler

1. Installer Android Studio (il fournit le SDK et Gradle).
2. `File > Open` sur ce dossier `android/`. Laisser la synchro Gradle se faire
   (elle genere le wrapper et telecharge les dependances).
3. Brancher un telephone (debogage USB) ou lancer un emulateur.
4. `Run`.

En ligne de commande (si tu as deja le SDK + `ANDROID_HOME` + Gradle) :
```bash
cd android
gradle wrapper          # genere ./gradlew la premiere fois
./gradlew assembleDebug  # APK dans app/build/outputs/apk/debug/
```

## Configurer l'adresse du backend

Au lancement, le champ "Adresse du backend" est pre-rempli avec
`http://10.1.70.88:8000` (IP LAN du Mac au moment de l'ecriture). Si l'IP du
Mac change, corrige-la dans l'app (ou dans `MainActivity.kt`, variable `base`).
Le telephone et le Mac doivent etre sur le meme Wi-Fi.

Le trafic HTTP clair vers le LAN est autorise via
`res/xml/network_security_config.xml` (Android le bloque par defaut).

## Limites connues / pistes

- Import photo via la galerie (`PickVisualMedia`). Pour la prise de vue directe,
  ajouter `TakePicture` + un `FileProvider`.
- Pas de detourage du socle cote app : le backend applique un ROI par defaut
  (haut 72%). Un pinceau de selection enverrait un `roi` sur mesure.
- Le rendu peint depend du Mac allume avec le backend lance.
