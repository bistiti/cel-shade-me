// Plugins declares au niveau racine, appliques dans :app.
// Versions testees ensemble (AGP 8.5 / Kotlin 2.0). Android Studio peut proposer
// une mise a jour coherente a l'ouverture.
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.20" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.20" apply false
}
