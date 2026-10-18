package com.figurinecolor.app

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.provider.MediaStore
import java.io.File

/** Reglages persistes (SharedPreferences). */
class Settings(ctx: Context) {
    private val sp = ctx.getSharedPreferences("figcolor", Context.MODE_PRIVATE)
    private val DEF_URL = "http://100.93.53.15:8000"  // IP Tailscale du Mac (joignable hors LAN)

    var lang: String
        get() = sp.getString("lang", "fr") ?: "fr"
        set(v) { sp.edit().putString("lang", v).apply() }

    var backendUrl: String
        get() = sp.getString("backend", DEF_URL) ?: DEF_URL
        set(v) { sp.edit().putString("backend", v.trim().trimEnd('/')).apply() }

    var harmony: String
        get() = sp.getString("harmony", "analogous") ?: "analogous"
        set(v) { sp.edit().putString("harmony", v).apply() }

    /** Job de rendu en attente (JSON {job,backend,folder,label}) pour reprise apres fermeture. */
    var pending: String?
        get() = sp.getString("pending", null)
        set(v) { val e = sp.edit(); if (v == null) e.remove("pending") else e.putString("pending", v); e.apply() }
}

/** Dossiers et photos sur le systeme de fichiers de l'app (stockage externe prive). */
class FolderRepo(ctx: Context) {
    val base: File = File(ctx.getExternalFilesDir(null), "figurines").apply { mkdirs() }

    fun folders(): List<String> =
        base.listFiles()?.filter { it.isDirectory }?.map { it.name }?.sorted() ?: emptyList()

    fun createFolder(name: String): Boolean {
        val n = name.trim()
        if (n.isEmpty()) return false
        return File(base, n).mkdirs()
    }

    fun photos(folder: String): List<File> =
        File(base, folder).listFiles()
            ?.filter { it.isFile && it.extension.lowercase() in listOf("jpg", "jpeg", "png") }
            ?.sortedByDescending { it.lastModified() } ?: emptyList()

    fun saveBytes(folder: String, bytes: ByteArray, prefix: String): File {
        val dir = File(base, folder).apply { mkdirs() }
        val f = File(dir, "${prefix}_${System.currentTimeMillis()}.png")
        f.writeBytes(bytes)
        return f
    }

    fun move(file: File, toFolder: String) {
        val dir = File(base, toFolder).apply { mkdirs() }
        file.copyTo(File(dir, file.name), overwrite = true)
        file.delete()
    }

    fun deletePhoto(file: File): Boolean = runCatching { file.delete() }.getOrDefault(false)

    fun deleteFolder(name: String): Boolean =
        runCatching { File(base, name).deleteRecursively() }.getOrDefault(false)

    fun renameFolder(old: String, newName: String): Boolean {
        val safe = newName.trim(); if (safe.isEmpty() || safe == old) return false
        return runCatching { File(base, old).renameTo(File(base, safe)) }.getOrDefault(false)
    }

    fun renamePhoto(file: File, newName: String): Boolean {
        val safe = newName.trim(); if (safe.isEmpty()) return false
        val target = File(file.parentFile, if (safe.contains('.')) safe else "$safe.${file.extension}")
        return runCatching { file.renameTo(target) }.getOrDefault(false)
    }
}

/** Exporte une image de l'app vers la galerie du telephone (Pictures/FigurineColor via MediaStore). */
fun exportToGallery(ctx: Context, file: File): Boolean = runCatching {
    val values = ContentValues().apply {
        put(MediaStore.Images.Media.DISPLAY_NAME, file.name)
        put(MediaStore.Images.Media.MIME_TYPE, "image/png")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/FigurineColor")
    }
    val uri = ctx.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
        ?: return@runCatching false
    ctx.contentResolver.openOutputStream(uri)?.use { out -> file.inputStream().use { it.copyTo(out) } }
    true
}.getOrDefault(false)
