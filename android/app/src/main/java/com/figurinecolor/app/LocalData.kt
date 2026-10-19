package com.figurinecolor.app

import android.content.Context
import org.json.JSONObject
import kotlin.math.cbrt
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Palette Vallejo Mecha + harmonies, 100% local (lues depuis
 * assets/vallejo_mecha_palette.json). Pur Kotlin, aucun reseau. Port de
 * compute_harmony / nearest_vallejo / rgb_to_lab du backend. Utilise par la
 * variante embedded a la place des endpoints /palette et /harmony.
 */
object LocalData {
    private var rgbOf: LinkedHashMap<String, IntArray>? = null
    private var hexOf: HashMap<String, String>? = null
    private var nameOf: HashMap<String, String>? = null
    private var labOf: LinkedHashMap<String, FloatArray>? = null
    private var order: List<String>? = null

    @Synchronized
    private fun ensure(ctx: Context) {
        if (rgbOf != null) return
        val txt = ctx.assets.open("vallejo_mecha_palette.json").bufferedReader().use { it.readText() }
        val o = JSONObject(txt)
        val rg = LinkedHashMap<String, IntArray>()
        val hx = HashMap<String, String>(); val nm = HashMap<String, String>()
        val lb = LinkedHashMap<String, FloatArray>(); val ord = ArrayList<String>()
        val it = o.keys()
        while (it.hasNext()) {
            val code = it.next(); val e = o.getJSONObject(code)
            val a = e.getJSONArray("rgb")
            val rgb = intArrayOf(a.getInt(0), a.getInt(1), a.getInt(2))
            rg[code] = rgb; hx[code] = e.optString("hex"); nm[code] = e.optString("name")
            lb[code] = rgbToLab(floatArrayOf(rgb[0] / 255f, rgb[1] / 255f, rgb[2] / 255f))
            ord.add(code)
        }
        rgbOf = rg; hexOf = hx; nameOf = nm; labOf = lb; order = ord
    }

    fun palette(ctx: Context): List<VColor> {
        ensure(ctx)
        return order!!.map { VColor(it, hexOf!![it] ?: "", nameOf!![it] ?: "") }
    }

    fun rgbFor(ctx: Context, code: String): IntArray {
        ensure(ctx)
        return rgbOf!![code] ?: error("code inconnu: $code")
    }

    private val OFFSETS = mapOf(
        "custom" to listOf(),
        "analogous" to listOf(-30, 30),
        "complementary" to listOf(180),
        "split" to listOf(150, 210),
        "triad" to listOf(120, 240),
        "tetradic" to listOf(60, 180, 240),
        "square" to listOf(90, 180, 270)
    )
    private val ROLE = listOf("secondaire", "accessoire", "detail", "detail2")

    fun harmony(ctx: Context, code: String, scheme: String): List<HColor> {
        ensure(ctx)
        val base = rgbOf!![code] ?: return emptyList()
        val hsv = rgbToHsv(base[0] / 255f, base[1] / 255f, base[2] / 255f)
        val h = hsv[0]; val s = hsv[1]; val v = hsv[2]
        val out = ArrayList<HColor>()
        out.add(HColor("principale", code, hexOf!![code] ?: "", nameOf!![code] ?: "", 0.0))
        val derived = ArrayList<FloatArray>()
        if (scheme.lowercase() == "monochromatic") {
            for (dv in floatArrayOf(-0.35f, -0.15f, 0.2f)) {
                val nv = min(max(v + dv, 0.08f), 1.0f)
                derived.add(hsvToRgb(h, max(s * 0.9f, 0.2f), nv))
            }
        } else {
            for (off in OFFSETS[scheme.lowercase()] ?: emptyList()) {
                var nh = (h * 360f + off) % 360f
                if (nh < 0f) nh += 360f
                derived.add(hsvToRgb(nh / 360f, s, v))
            }
        }
        val used = HashSet<String>(); used.add(code)
        for ((i, rgb) in derived.withIndex()) {
            val near = nearest(rgb, used) ?: continue
            used.add(near.first)
            out.add(HColor(if (i < ROLE.size) ROLE[i] else "zone${i + 2}",
                near.first, hexOf!![near.first] ?: "", nameOf!![near.first] ?: "", near.second))
        }
        return out
    }

    private fun nearest(rgb01: FloatArray, exclude: Set<String>): Pair<String, Double>? {
        val lt = rgbToLab(rgb01); var best: String? = null; var bd = 1e9
        for ((code, pl) in labOf!!) {
            if (code in exclude) continue
            val dl = (pl[0] - lt[0]); val da = (pl[1] - lt[1]); val db = (pl[2] - lt[2])
            val d = sqrt((dl * dl + da * da + db * db).toDouble())
            if (d < bd) { bd = d; best = code }
        }
        return best?.let { Pair(it, Math.round(bd * 10.0) / 10.0) }
    }

    // --- colorsys (h,s,v dans [0,1]) ---
    private fun rgbToHsv(r: Float, g: Float, b: Float): FloatArray {
        val mx = max(r, max(g, b)); val mn = min(r, min(g, b)); val v = mx
        if (mn == mx) return floatArrayOf(0f, 0f, v)
        val s = (mx - mn) / mx
        val rc = (mx - r) / (mx - mn); val gc = (mx - g) / (mx - mn); val bc = (mx - b) / (mx - mn)
        var hh = when (mx) { r -> bc - gc; g -> 2f + rc - bc; else -> 4f + gc - rc }
        hh = (hh / 6f) % 1f; if (hh < 0f) hh += 1f
        return floatArrayOf(hh, s, v)
    }

    private fun hsvToRgb(h: Float, s: Float, v: Float): FloatArray {
        if (s == 0f) return floatArrayOf(v, v, v)
        val i = (h * 6f).toInt(); val f = h * 6f - i
        val p = v * (1 - s); val q = v * (1 - s * f); val t = v * (1 - s * (1 - f))
        return when (i % 6) {
            0 -> floatArrayOf(v, t, p); 1 -> floatArrayOf(q, v, p); 2 -> floatArrayOf(p, v, t)
            3 -> floatArrayOf(p, q, v); 4 -> floatArrayOf(t, p, v); else -> floatArrayOf(v, p, q)
        }
    }

    // --- CIELab (port de rgb_to_lab) ---
    private fun srgbToLinear(c: Float): Float =
        if (c > 0.04045f) Math.pow(((c + 0.055f) / 1.055f).toDouble(), 2.4).toFloat() else c / 12.92f

    private fun rgbToLab(rgb: FloatArray): FloatArray {
        val r = srgbToLinear(rgb[0]); val g = srgbToLinear(rgb[1]); val b = srgbToLinear(rgb[2])
        val x = (0.4124f * r + 0.3576f * g + 0.1805f * b) / 0.95047f
        val y = (0.2126f * r + 0.7152f * g + 0.0722f * b) / 1.0f
        val z = (0.0193f * r + 0.1192f * g + 0.9505f * b) / 1.08883f
        val d = 6f / 29f; val d3 = d * d * d
        val fx = if (x > d3) cbrt(x.toDouble()).toFloat() else x / (3 * d * d) + 4f / 29f
        val fy = if (y > d3) cbrt(y.toDouble()).toFloat() else y / (3 * d * d) + 4f / 29f
        val fz = if (z > d3) cbrt(z.toDouble()).toFloat() else z / (3 * d * d) + 4f / 29f
        return floatArrayOf(116f * fy - 16f, 500f * (fx - fy), 200f * (fy - fz))
    }
}
