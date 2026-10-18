#!/usr/bin/env bash
# Installe la chaine de build Android SANS sudo (espace utilisateur) :
# JDK 17 (Temurin) + Gradle + Android SDK (cmdline-tools, platform 34, build-tools)
# + Android Studio (dmg). Tout est logue. Relançable (idempotent au mieux).
set -u
LOG() { echo "[$(date +%H:%M:%S)] $*"; }
TOOLS="$HOME/android-tools"
SDK="$HOME/Library/Android/sdk"
PROJ_ANDROID="/Users/macia/figurine_paint/android"
GV="8.10.2"
mkdir -p "$TOOLS" "$SDK"
cd "$TOOLS" || exit 1

# --- 1. JDK 17 (Temurin / Adoptium) ---
if [ ! -x "$TOOLS/jdk17/Contents/Home/bin/javac" ] && [ ! -x "$TOOLS/jdk17/bin/javac" ]; then
  LOG "JDK17: telechargement..."
  curl -fL -o jdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse" || { LOG "JDK dl ECHEC"; exit 1; }
  rm -rf jdk17 && mkdir jdk17
  tar -xzf jdk17.tar.gz -C jdk17 --strip-components=1 && rm -f jdk17.tar.gz
  LOG "JDK17: extrait"
else
  LOG "JDK17 deja present"
fi
if [ -d "$TOOLS/jdk17/Contents/Home" ]; then export JAVA_HOME="$TOOLS/jdk17/Contents/Home"; else export JAVA_HOME="$TOOLS/jdk17"; fi
LOG "JAVA_HOME=$JAVA_HOME ; $("$JAVA_HOME/bin/java" -version 2>&1 | head -1)"

# --- 2. Gradle ---
if [ ! -x "$TOOLS/gradle-$GV/bin/gradle" ]; then
  LOG "Gradle $GV: telechargement..."
  curl -fL -o gradle.zip "https://services.gradle.org/distributions/gradle-$GV-bin.zip" || { LOG "gradle dl ECHEC"; exit 1; }
  unzip -q -o gradle.zip && rm -f gradle.zip
  LOG "Gradle extrait"
else
  LOG "Gradle deja present"
fi
export PATH="$TOOLS/gradle-$GV/bin:$PATH"

# --- 3. cmdline-tools ---
SDKM="$SDK/cmdline-tools/latest/bin/sdkmanager"
if [ ! -x "$SDKM" ]; then
  LOG "cmdline-tools: telechargement..."
  curl -fL -o cmdtools.zip "https://dl.google.com/android/repository/commandlinetools-mac_arm64-15859902_latest.zip" || { LOG "cmdtools dl ECHEC"; exit 1; }
  rm -rf cmdtools-tmp && mkdir cmdtools-tmp && unzip -q -o cmdtools.zip -d cmdtools-tmp && rm -f cmdtools.zip
  mkdir -p "$SDK/cmdline-tools/latest"
  cp -R cmdtools-tmp/cmdline-tools/* "$SDK/cmdline-tools/latest/" && rm -rf cmdtools-tmp
  LOG "cmdline-tools installes"
else
  LOG "cmdline-tools deja presents"
fi
export ANDROID_HOME="$SDK"

# --- 4. packages SDK + licences ---
LOG "licences SDK..."
yes | "$SDKM" --sdk_root="$SDK" --licenses >/dev/null 2>&1
LOG "packages SDK (platform-tools, android-34, build-tools 34.0.0)..."
"$SDKM" --sdk_root="$SDK" "platform-tools" "platforms;android-34" "build-tools;34.0.0" >/dev/null 2>&1 && LOG "SDK packages OK" || LOG "SDK packages ECHEC"

# --- 5. env.sh + local.properties ---
cat > "$TOOLS/env.sh" <<ENV
export JAVA_HOME="$JAVA_HOME"
export ANDROID_HOME="$SDK"
export PATH="$TOOLS/gradle-$GV/bin:\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/cmdline-tools/latest/bin:\$JAVA_HOME/bin:\$PATH"
ENV
echo "sdk.dir=$SDK" > "$PROJ_ANDROID/local.properties"
LOG "env.sh + local.properties ecrits"

# --- 6. Android Studio (dmg) ---
STUDIO_URL="https://edgedl.me.gvt1.com/android/studio/install/2026.2.1.8/android-studio-rabbit1-mac_arm.dmg"
STUDIO_SHA="16d4a0f8a52413b51869fc18d5bdcdf9cecd38615cd7bb7cf14d51b99d2fef54"
if [ ! -d "/Applications/Android Studio.app" ] && [ ! -d "$HOME/Applications/Android Studio.app" ]; then
  LOG "Android Studio: telechargement (1.5 Go)..."
  curl -fL -o studio.dmg "$STUDIO_URL" || { LOG "studio dl ECHEC"; exit 1; }
  GOT=$(shasum -a 256 studio.dmg | awk '{print $1}')
  [ "$GOT" = "$STUDIO_SHA" ] && LOG "studio sha256 OK" || LOG "studio sha256 MISMATCH ($GOT)"
  MP=$(hdiutil attach studio.dmg -nobrowse -plist | python -c "import sys,plistlib;p=plistlib.loads(sys.stdin.buffer.read());print(next((e['mount-point'] for e in p['system-entities'] if e.get('mount-point')),''))")
  LOG "dmg monte sur $MP"
  if [ -n "$MP" ] && [ -d "$MP/Android Studio.app" ]; then
    if cp -R "$MP/Android Studio.app" "/Applications/" 2>/dev/null; then
      LOG "Studio installe dans /Applications"
    else
      mkdir -p "$HOME/Applications"
      cp -R "$MP/Android Studio.app" "$HOME/Applications/" && LOG "Studio installe dans ~/Applications (pas d'ecriture /Applications)"
    fi
    xattr -dr com.apple.quarantine "/Applications/Android Studio.app" 2>/dev/null
    hdiutil detach "$MP" -force -quiet 2>/dev/null
    rm -f studio.dmg
  else
    LOG "studio: point de montage introuvable, dmg conserve pour reessai"
  fi
else
  LOG "Android Studio deja installe"
fi

LOG "=== TOOLCHAIN_DONE ==="
