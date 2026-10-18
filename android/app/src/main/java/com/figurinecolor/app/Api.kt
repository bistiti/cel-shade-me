package com.figurinecolor.app

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class VColor(val code: String, val hex: String, val name: String)
data class HColor(val role: String, val code: String, val hex: String, val name: String, val deltaE: Double)
data class Zone(val role: String, val code: String, val hex: String, val coverage: Double, val deltaE: Double?)
data class ProcResult(val recolorUrl: String, val paintUrl: String?, val zones: List<Zone>)

/** Client HTTP du backend local. Appels bloquants -> a lancer sur Dispatchers.IO. */
class Api(private val base: String) {

    private val client = OkHttpClient.Builder()
        .callTimeout(1800, TimeUnit.SECONDS)
        .readTimeout(1800, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .connectTimeout(20, TimeUnit.SECONDS)
        .build()

    fun palette(): List<VColor> {
        client.newCall(Request.Builder().url("$base/palette").build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            if (!r.isSuccessful) error("HTTP ${r.code}")
            val arr = JSONObject(b).getJSONArray("colors")
            return (0 until arr.length()).map {
                val o = arr.getJSONObject(it)
                VColor(o.getString("code"), o.getString("hex"), o.optString("name"))
            }
        }
    }

    fun harmony(code: String, scheme: String): List<HColor> {
        val url = "$base/harmony?code=$code&scheme=$scheme"
        client.newCall(Request.Builder().url(url).build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            val o = JSONObject(b)
            if (!r.isSuccessful) error(o.optString("error", "HTTP ${r.code}"))
            val arr = o.getJSONArray("colors")
            return (0 until arr.length()).map {
                val c = arr.getJSONObject(it)
                HColor(c.optString("role"), c.getString("code"), c.getString("hex"),
                    c.optString("name"), c.optDouble("delta_e", 0.0))
            }
        }
    }

    fun process(bytes: ByteArray, codes: List<String>, doPaint: Boolean, steps: Int, size: Int): ProcResult {
        val part = bytes.toRequestBody("image/*".toMediaType())
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", "photo.jpg", part)
            .addFormDataPart("codes", codes.joinToString(","))
            .addFormDataPart("do_paint", doPaint.toString())
            .addFormDataPart("steps", steps.toString())
            .addFormDataPart("size", size.toString())
            .build()
        client.newCall(Request.Builder().url("$base/process").post(form).build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            val o = JSONObject(b)
            if (!r.isSuccessful) error(o.optString("error", "HTTP ${r.code}"))
            val rec = o.getJSONObject("recolor")
            val za = rec.optJSONArray("zones")
            val zones = if (za == null) emptyList() else (0 until za.length()).map {
                val z = za.getJSONObject(it)
                Zone(z.optString("role"), z.optString("target_code"), z.optString("target_hex"),
                    z.optDouble("coverage_pct", 0.0),
                    if (z.isNull("delta_e")) null else z.optDouble("delta_e"))
            }
            val paint = if (o.isNull("paint")) null else o.getJSONObject("paint")
            return ProcResult(base + rec.getString("url"),
                paint?.let { base + it.getString("url") }, zones)
        }
    }

    /** Affectation au doigt : points = (x,y normalises 0..1, code Vallejo). */
    fun processPoints(bytes: ByteArray, points: List<Triple<Float, Float, String>>,
                      doPaint: Boolean, steps: Int, size: Int): ProcResult {
        val arr = org.json.JSONArray()
        points.forEach { (x, y, code) ->
            arr.put(org.json.JSONObject().put("x", x.toDouble()).put("y", y.toDouble()).put("code", code))
        }
        val part = bytes.toRequestBody("image/*".toMediaType())
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", "photo.jpg", part)
            .addFormDataPart("points", arr.toString())
            .addFormDataPart("do_paint", doPaint.toString())
            .addFormDataPart("steps", steps.toString())
            .addFormDataPart("size", size.toString())
            .build()
        client.newCall(Request.Builder().url("$base/process_points").post(form).build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            val o = JSONObject(b)
            if (!r.isSuccessful) error(o.optString("error", "HTTP ${r.code}"))
            val rec = o.getJSONObject("recolor")
            val za = rec.optJSONArray("zones")
            val zones = if (za == null) emptyList() else (0 until za.length()).map {
                val z = za.getJSONObject(it)
                Zone(z.optString("role"), z.optString("target_code"), z.optString("target_hex"),
                    z.optDouble("coverage_pct", 0.0),
                    if (z.isNull("delta_e")) null else z.optDouble("delta_e"))
            }
            val paint = if (o.isNull("paint")) null else o.getJSONObject("paint")
            return ProcResult(base + rec.getString("url"), paint?.let { base + it.getString("url") }, zones)
        }
    }

    /** Recoloration EXACTE par zones peintes au doigt (figurine mono-couleur, zero IA).
     *  zonesJson = [{code, role, strokes:[{pts:[[x,y]], r, mode}]}]. */
    fun recolorStrokes(bytes: ByteArray, zonesJson: String, finish: Boolean): ProcResult {
        val part = bytes.toRequestBody("image/*".toMediaType())
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", "photo.jpg", part)
            .addFormDataPart("zones", zonesJson)
            .addFormDataPart("finish", finish.toString())
            .build()
        client.newCall(Request.Builder().url("$base/recolor_strokes").post(form).build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            val o = JSONObject(b)
            if (!r.isSuccessful) error(o.optString("error", "HTTP ${r.code}"))
            val rec = o.getJSONObject("recolor")
            val za = rec.optJSONArray("zones")
            val zones = if (za == null) emptyList() else (0 until za.length()).map {
                val z = za.getJSONObject(it)
                Zone(z.optString("role"), z.optString("target_code"), z.optString("target_hex"),
                    z.optDouble("coverage_pct", 0.0),
                    if (z.isNull("delta_e")) null else z.optDouble("delta_e"))
            }
            val paint = if (o.isNull("paint")) null else o.getJSONObject("paint")
            return ProcResult(base + rec.getString("url"), paint?.let { base + it.getString("url") }, zones)
        }
    }

    /** Flux cel-shading complet: zones -> recolor Vallejo exact -> finition qui PRESERVE
     *  les couleurs -> encrage noir. mode = q4|q6|q8. URL finale dans paintUrl. */
    fun celZones(bytes: ByteArray, zonesJson: String, mode: String, thick: Int): ProcResult {
        val part = bytes.toRequestBody("image/*".toMediaType())
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", "photo.jpg", part)
            .addFormDataPart("zones", zonesJson)
            .addFormDataPart("mode", mode)
            .addFormDataPart("thick", thick.toString())
            .build()
        client.newCall(Request.Builder().url("$base/cel_zones").post(form).build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            val o = JSONObject(b)
            if (!r.isSuccessful) error(o.optString("error", "HTTP ${r.code}"))
            val rec = o.getJSONObject("recolor")
            val za = rec.optJSONArray("zones")
            val zones = if (za == null) emptyList() else (0 until za.length()).map {
                val z = za.getJSONObject(it)
                Zone(z.optString("role"), z.optString("target_code"), z.optString("target_hex"),
                    z.optDouble("coverage_pct", 0.0),
                    if (z.isNull("delta_e")) null else z.optDouble("delta_e"))
            }
            val fin = when {
                !o.isNull("final") -> o.getJSONObject("final")
                !o.isNull("render") -> o.getJSONObject("render")
                else -> null
            }
            return ProcResult(base + rec.getString("url"), fin?.let { base + it.getString("url") }, zones)
        }
    }

    /** Demarre un job de rendu (recolor immediat + rendu serveur en arriere-plan).
     *  Rend le JSON brut: {id, status, recolor:{url,zones}, clip, clipped_px}. */
    fun celZonesStart(bytes: ByteArray, zonesJson: String, mode: String, thick: Int): JSONObject {
        val part = bytes.toRequestBody("image/*".toMediaType())
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", "photo.jpg", part)
            .addFormDataPart("zones", zonesJson)
            .addFormDataPart("mode", mode)
            .addFormDataPart("thick", thick.toString())
            .build()
        client.newCall(Request.Builder().url("$base/cel_zones").post(form).build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            val o = JSONObject(b)
            if (!r.isSuccessful) error(o.optString("error", "HTTP ${r.code}"))
            return o
        }
    }

    /** Mode sans-peinture : toute la figurine en UNE couleur via le moteur cel (async). */
    fun celFillStart(bytes: ByteArray, code: String, mode: String, thick: Int): JSONObject {
        val part = bytes.toRequestBody("image/*".toMediaType())
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", "photo.jpg", part)
            .addFormDataPart("code", code)
            .addFormDataPart("mode", mode)
            .addFormDataPart("thick", thick.toString())
            .build()
        client.newCall(Request.Builder().url("$base/cel_fill").post(form).build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            val o = JSONObject(b)
            if (!r.isSuccessful) error(o.optString("error", "HTTP ${r.code}"))
            return o
        }
    }

    /** Statut d'un job: {status: pending|done|error, final:{url}, render:{url}, error}. */
    fun celStatus(job: String): JSONObject {
        client.newCall(Request.Builder().url("$base/cel_status/$job").get().build()).execute().use { r ->
            val b = r.body?.string() ?: error("reponse vide")
            return JSONObject(b)
        }
    }

    /** Telecharge un fichier servi par le backend (chemin /files/... ou URL absolue). */
    fun fetch(path: String): ByteArray {
        val url = if (path.startsWith("http")) path else "$base$path"
        client.newCall(Request.Builder().url(url).get().build()).execute().use { r ->
            if (!r.isSuccessful) error("HTTP ${r.code}")
            return r.body?.bytes() ?: error("corps vide")
        }
    }

    /** Annule un job de rendu cote serveur (interrompt ComfyUI, libere le Mac). */
    fun celCancel(job: String): JSONObject {
        client.newCall(Request.Builder().url("$base/cel_cancel/$job").post("".toRequestBody()).build())
            .execute().use { r ->
                val b = r.body?.string() ?: "{}"
                return JSONObject(b)
            }
    }
}
