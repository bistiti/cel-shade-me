package com.figurinecolor.app

import android.graphics.Bitmap
import org.opencv.android.OpenCVLoader
import org.opencv.android.Utils
import org.opencv.core.Core
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.core.Point
import org.opencv.core.Rect
import org.opencv.core.Scalar
import org.opencv.core.TermCriteria
import org.opencv.imgproc.Imgproc
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/** Un trait peint au doigt. pts = points normalises [x,y] dans [0,1]; r = rayon normalise. */
data class Stroke(val pts: List<FloatArray>, val r: Float, val erase: Boolean)

/** Une zone a colorier : couleur Vallejo (RGB 0-255) + traits. */
data class ZoneSpec(val base: IntArray, val strokes: List<Stroke>)

/**
 * Moteur cel-shading DETERMINISTE, 100% sur l'appareil (OpenCV). Port fidele du backend
 * server.py (_figure_mask / _rasterize / _posterize_cel / _make_tones). Aucun reseau,
 * aucun modele IA. Instantane.
 */
object CelEngine {
    @Volatile private var inited = false
    private fun ensureInit() {
        if (!inited) { OpenCVLoader.initLocal(); inited = true }
    }

    // ---- API publique -------------------------------------------------------

    /** Mode sans-peinture : toute la figurine en une couleur Vallejo. */
    fun fill(bmp: Bitmap, base: IntArray, ink: Boolean = true, thick: Int = 2): Bitmap {
        ensureInit()
        val rgb = toRgb(bmp)
        val h = rgb.rows(); val w = rgb.cols()
        val fg = figureMask(rgb)
        val frac = Core.countNonZero(fg).toDouble() / (h * w)
        val mask = if (frac > 0.02 && frac < 0.97) fg else Mat(h, w, CvType.CV_8U, Scalar(255.0))
        val out = posterizeCel(rgb, listOf(mask), listOf(base), ink, thick, false)
        return toBitmap(out)
    }

    /** Peindre au doigt : chaque zone = un code Vallejo + des traits (derniere zone gagne). */
    fun zones(bmp: Bitmap, zones: List<ZoneSpec>, ink: Boolean = true, thick: Int = 2): Bitmap {
        ensureInit()
        val rgb = toRgb(bmp)
        val h = rgb.rows(); val w = rgb.cols(); val n = h * w
        val fg = figureMask(rgb)
        val frac = Core.countNonZero(fg).toDouble() / n
        val clip = frac > 0.02 && frac < 0.97
        val fgB = ByteArray(n); fg.get(0, 0, fgB)
        val owner = IntArray(n) { -1 }
        for ((i, z) in zones.withIndex()) {
            val m = rasterize(h, w, z.strokes)
            val mb = ByteArray(n); m.get(0, 0, mb)
            for (p in 0 until n) {
                var on = mb[p].toInt() != 0
                if (clip && fgB[p].toInt() == 0) on = false
                if (on) owner[p] = i
            }
        }
        val masks = ArrayList<Mat>(); val bases = ArrayList<IntArray>()
        for ((i, z) in zones.withIndex()) {
            val bb = ByteArray(n) { if (owner[it] == i) 255.toByte() else 0 }
            val mm = Mat(h, w, CvType.CV_8U); mm.put(0, 0, bb)
            masks.add(mm); bases.add(z.base)
        }
        val out = posterizeCel(rgb, masks, bases, ink, thick, false)
        return toBitmap(out)
    }

    /** Variante pour l'apercu live : retire le FOND UNI (appris sur le pourtour) puis cel.
     *  Rend directement un Bitmap. A appeler sur des images reduites. */
    fun fillLive(bmp: Bitmap, base: IntArray, thick: Int = 2): Bitmap {
        ensureInit()
        val rgb = toRgb(bmp)
        val h = rgb.rows(); val w = rgb.cols()
        val fg = liveMask(rgb)
        val frac = Core.countNonZero(fg).toDouble() / (h * w)
        val mask = if (frac > 0.005) fg else Mat(h, w, CvType.CV_8U, Scalar(255.0))
        val out = posterizeCel(rgb, listOf(mask), listOf(base), true, thick, false)
        return toBitmap(out)
    }

    /** Masque figurine pour le live. Apprend la/les couleur(s) du FOND UNI sur le POURTOUR
     *  de l'image (= fond quand la figurine est cadree au centre), puis ne retire comme fond
     *  QUE les pixels proches-du-fond ET RELIES AU BORD. Un reflet clair a l'interieur de la
     *  figurine (proche du blanc du fond) n'est pas relie au bord -> il est GARDE (remplissage
     *  des trous). Corrige le masque en 'ilots' sur un sujet clair/brillant. Exige un fond uni
     *  DISTINCT de la couleur de la figurine. */
    private fun liveMask(rgb: Mat, tol: Float = 46f): Mat {
        val h = rgb.rows(); val w = rgb.cols(); val n = h * w
        val b = ByteArray(n * 3); rgb.get(0, 0, b)
        val my = maxOf(3, h / 12); val mx = maxOf(3, w / 12)
        val stride = maxOf(1, (h + w) / 500)
        val sl = ArrayList<Float>(6000)
        var y = 0
        while (y < h) {
            var x = 0
            while (x < w) {
                if (y < my || y >= h - my || x < mx || x >= w - mx) {
                    val p = (y * w + x) * 3
                    sl.add((b[p].toInt() and 255).toFloat())
                    sl.add((b[p + 1].toInt() and 255).toFloat())
                    sl.add((b[p + 2].toInt() and 255).toFloat())
                }
                x += stride
            }
            y += stride
        }
        val cnt = sl.size / 3
        val fgB = ByteArray(n) { 255.toByte() }
        if (cnt >= 12) {
            val samples = Mat(cnt, 3, CvType.CV_32F)
            samples.put(0, 0, sl.toFloatArray())
            val k = minOf(3, cnt)
            val labelsK = Mat(); val centers = Mat()
            Core.kmeans(samples, k, labelsK,
                TermCriteria(TermCriteria.EPS + TermCriteria.MAX_ITER, 8, 1.0),
                2, Core.KMEANS_PP_CENTERS, centers)
            val cf = FloatArray(k * 3); centers.get(0, 0, cf)
            val tol2 = tol * tol
            // 1) pixels proches-du-fond (par couleur)
            val bgColorB = ByteArray(n)
            for (p in 0 until n) {
                val r = (b[p * 3].toInt() and 255).toFloat()
                val g = (b[p * 3 + 1].toInt() and 255).toFloat()
                val bl = (b[p * 3 + 2].toInt() and 255).toFloat()
                var dmin = Float.MAX_VALUE
                for (c in 0 until k) {
                    val dr = r - cf[c * 3]; val dg = g - cf[c * 3 + 1]; val db = bl - cf[c * 3 + 2]
                    val d = dr * dr + dg * dg + db * db
                    if (d < dmin) dmin = d
                }
                if (dmin < tol2) bgColorB[p] = 255.toByte()
            }
            // 2) composantes connexes : ne garder comme fond que celles reliees au BORD
            val bgColor = Mat(h, w, CvType.CV_8U); bgColor.put(0, 0, bgColorB)
            val lbl = Mat()
            Imgproc.connectedComponents(bgColor, lbl, 8, CvType.CV_32S)
            val lab = IntArray(n); lbl.get(0, 0, lab)
            val borderLabels = HashSet<Int>()
            for (x in 0 until w) { borderLabels.add(lab[x]); borderLabels.add(lab[(h - 1) * w + x]) }
            for (yy in 0 until h) { borderLabels.add(lab[yy * w]); borderLabels.add(lab[yy * w + w - 1]) }
            // 3) figure = tout sauf le fond-couleur relie au bord (trous interieurs gardes)
            for (p in 0 until n) {
                if (bgColorB[p].toInt() != 0 && borderLabels.contains(lab[p])) fgB[p] = 0
            }
        }
        val fg = Mat(h, w, CvType.CV_8U); fg.put(0, 0, fgB)
        Imgproc.morphologyEx(fg, fg, Imgproc.MORPH_OPEN, Mat.ones(3, 3, CvType.CV_8U))
        Imgproc.morphologyEx(fg, fg, Imgproc.MORPH_CLOSE, Mat.ones(9, 9, CvType.CV_8U))
        return fg
    }

    // ---- conversions --------------------------------------------------------

    private fun toRgb(bmp: Bitmap): Mat {
        val rgba = Mat(); Utils.bitmapToMat(bmp, rgba)
        val rgb = Mat(); Imgproc.cvtColor(rgba, rgb, Imgproc.COLOR_RGBA2RGB)
        return rgb
    }

    private fun toBitmap(rgb: Mat): Bitmap {
        val rgba = Mat(); Imgproc.cvtColor(rgb, rgba, Imgproc.COLOR_RGB2RGBA)
        val bmp = Bitmap.createBitmap(rgb.cols(), rgb.rows(), Bitmap.Config.ARGB_8888)
        Utils.matToBitmap(rgba, bmp)
        return bmp
    }

    // ---- masque figurine (port de _figure_mask) -----------------------------

    fun figureMask(rgb: Mat, fast: Boolean = false): Mat {
        val h = rgb.rows(); val w = rgb.cols(); val n = h * w
        val outer = Mat.zeros(h, w, CvType.CV_8U)
        val seeds = arrayOf(
            Point(0.0, 0.0), Point((w - 1).toDouble(), 0.0),
            Point(0.0, (h - 1).toDouble()), Point((w - 1).toDouble(), (h - 1).toDouble())
        )
        for (s in seeds) {
            val mask = Mat.zeros(h + 2, w + 2, CvType.CV_8U)
            Imgproc.floodFill(
                rgb, mask, s, Scalar(0.0), Rect(),
                Scalar(8.0, 8.0, 8.0), Scalar(8.0, 8.0, 8.0),
                4 or (255 shl 8) or Imgproc.FLOODFILL_MASK_ONLY
            )
            val inner = mask.submat(1, h + 1, 1, w + 1)
            Core.bitwise_or(outer, inner, outer)
        }
        val rgbB = ByteArray(n * 3); rgb.get(0, 0, rgbB)
        val outB = ByteArray(n); outer.get(0, 0, outB)
        var colbg: BooleanArray? = null
        val bgIdx = ArrayList<Int>()
        for (p in 0 until n) if (outB[p].toInt() != 0) bgIdx.add(p)
        if (!fast && bgIdx.size >= 200) {
            val sampleIdx = if (bgIdx.size > 5000)
                (0 until 5000).map { bgIdx[it * bgIdx.size / 5000] } else bgIdx
            val ns = sampleIdx.size
            val samples = Mat(ns, 3, CvType.CV_32F)
            val sf = FloatArray(ns * 3)
            for (k in 0 until ns) {
                val p = sampleIdx[k]
                sf[k * 3] = (rgbB[p * 3].toInt() and 255).toFloat()
                sf[k * 3 + 1] = (rgbB[p * 3 + 1].toInt() and 255).toFloat()
                sf[k * 3 + 2] = (rgbB[p * 3 + 2].toInt() and 255).toFloat()
            }
            samples.put(0, 0, sf)
            val labels = Mat(); val centersMat = Mat()
            val crit = TermCriteria(TermCriteria.EPS + TermCriteria.MAX_ITER, 10, 1.0)
            Core.kmeans(samples, 5, labels, crit, 3, Core.KMEANS_PP_CENTERS, centersMat)
            val cf = FloatArray(15); centersMat.get(0, 0, cf)
            val cand = BooleanArray(n)
            var candInZero = 0; var outerZero = 0
            for (p in 0 until n) {
                val r = (rgbB[p * 3].toInt() and 255).toFloat()
                val g = (rgbB[p * 3 + 1].toInt() and 255).toFloat()
                val b = (rgbB[p * 3 + 2].toInt() and 255).toFloat()
                var dmin = Float.MAX_VALUE
                for (c in 0 until 5) {
                    val dr = r - cf[c * 3]; val dg = g - cf[c * 3 + 1]; val db = b - cf[c * 3 + 2]
                    val d = dr * dr + dg * dg + db * db
                    if (d < dmin) dmin = d
                }
                val isCand = dmin < 1600f   // 40^2
                cand[p] = isCand
                if (outB[p].toInt() == 0) { outerZero++; if (isCand) candInZero++ }
            }
            if (outerZero > 0 && candInZero.toDouble() / outerZero < 0.25) colbg = cand
        }
        val fgB = ByteArray(n) {
            val bg = outB[it].toInt() != 0 || (colbg?.get(it) == true)
            if (bg) 0 else 255.toByte()
        }
        val fg = Mat(h, w, CvType.CV_8U); fg.put(0, 0, fgB)
        Imgproc.morphologyEx(fg, fg, Imgproc.MORPH_OPEN, Mat.ones(3, 3, CvType.CV_8U))
        return fg
    }

    // ---- rasterisation des traits (port de _rasterize) ----------------------

    private fun rasterize(h: Int, w: Int, strokes: List<Stroke>): Mat {
        val m = Mat.zeros(h, w, CvType.CV_8U)
        val s = min(h, w)
        for (st in strokes) {
            if (st.pts.isEmpty()) continue
            val r = max(1.0, st.r.toDouble() * s)
            val v = if (st.erase) Scalar(0.0) else Scalar(255.0)
            val pix = st.pts.map { Point(it[0].toDouble() * w, it[1].toDouble() * h) }
            if (pix.size >= 2) {
                for (i in 0 until pix.size - 1)
                    Imgproc.line(m, pix[i], pix[i + 1], v, max(1, (r * 2).toInt()))
            }
            for (pt in pix) Imgproc.circle(m, pt, max(1, r.toInt()), v, -1)
        }
        return m
    }

    // ---- posterisation cel (port de _posterize_cel) -------------------------

    private fun posterizeCel(
        orig: Mat, zoneMasks: List<Mat>, bases: List<IntArray>,
        ink: Boolean, thick: Int, exterior: Boolean,
        inkLow: Double = 55.0, inkHigh: Double = 140.0, darkThr: Int = 30
    ): Mat {
        val h = orig.rows(); val w = orig.cols(); val n = h * w
        val sm = Mat(); Imgproc.bilateralFilter(orig, sm, 7, 45.0, 45.0)
        val grayM = Mat(); Imgproc.cvtColor(sm, grayM, Imgproc.COLOR_RGB2GRAY)
        val grayB = ByteArray(n); grayM.get(0, 0, grayB)
        val grayF = FloatArray(n) { (grayB[it].toInt() and 255).toFloat() }
        val origB = ByteArray(n * 3); orig.get(0, 0, origB)
        val dark = BooleanArray(n) {
            (origB[it * 3].toInt() and 255) < darkThr &&
                (origB[it * 3 + 1].toInt() and 255) < darkThr &&
                (origB[it * 3 + 2].toInt() and 255) < darkThr
        }
        val outB = origB.copyOf()
        val allfig = BooleanArray(n)
        for ((zi, zmMat) in zoneMasks.withIndex()) {
            val zmB = ByteArray(n); zmMat.get(0, 0, zmB)
            val zm = BooleanArray(n) { zmB[it].toInt() != 0 && !dark[it] }
            var cnt = 0
            for (p in 0 until n) if (zm[p]) cnt++
            if (cnt < 10) continue
            val vals = FloatArray(cnt); var k = 0
            for (p in 0 until n) if (zm[p]) vals[k++] = grayF[p]
            vals.sort()
            val t0 = percentile(vals, 42.0); val t1 = percentile(vals, 80.0)
            val tones = makeTones(bases[zi], 3)
            for (p in 0 until n) if (zm[p]) {
                val x = grayF[p]
                val band = if (x < t0) 0 else if (x < t1) 1 else 2
                val t = tones[band]
                outB[p * 3] = t[0].toByte(); outB[p * 3 + 1] = t[1].toByte(); outB[p * 3 + 2] = t[2].toByte()
                allfig[p] = true
            }
        }
        var anyFig = false
        for (p in 0 until n) if (allfig[p]) { anyFig = true; break }
        if (ink && anyFig) {
            val go = Mat(); Imgproc.cvtColor(orig, go, Imgproc.COLOR_RGB2GRAY)
            val edges = Mat(); Imgproc.Canny(go, edges, inkLow, inkHigh)
            val edgesB = ByteArray(n); edges.get(0, 0, edgesB)
            val afB = ByteArray(n) { if (allfig[it]) 255.toByte() else 0 }
            val afMat = Mat(h, w, CvType.CV_8U); afMat.put(0, 0, afB)
            val inside = Mat()
            Imgproc.erode(afMat, inside, Mat.ones(3, 3, CvType.CV_8U), Point(-1.0, -1.0), 2)
            val insideB = ByteArray(n); inside.get(0, 0, insideB)
            val lines = BooleanArray(n) { edgesB[it].toInt() != 0 && insideB[it].toInt() != 0 }
            if (!exterior) {
                val ring = Mat()
                Imgproc.morphologyEx(afMat, ring, Imgproc.MORPH_GRADIENT,
                    Mat.ones(2 * thick + 3, 2 * thick + 3, CvType.CV_8U))
                val ringB = ByteArray(n); ring.get(0, 0, ringB)
                for (p in 0 until n) if (ringB[p].toInt() != 0) lines[p] = false
            } else {
                val sil = Mat()
                Imgproc.morphologyEx(afMat, sil, Imgproc.MORPH_GRADIENT, Mat.ones(3, 3, CvType.CV_8U))
                val silB = ByteArray(n); sil.get(0, 0, silB)
                for (p in 0 until n) if (silB[p].toInt() != 0) lines[p] = true
            }
            val lnB = ByteArray(n) { if (lines[it]) 255.toByte() else 0 }
            val lnMat = Mat(h, w, CvType.CV_8U); lnMat.put(0, 0, lnB)
            val ln2 = Mat(); Imgproc.dilate(lnMat, ln2, Mat.ones(thick, thick, CvType.CV_8U))
            val ln2B = ByteArray(n); ln2.get(0, 0, ln2B)
            for (p in 0 until n) if (ln2B[p].toInt() != 0) {
                outB[p * 3] = 8; outB[p * 3 + 1] = 8; outB[p * 3 + 2] = 8
            }
        }
        val out = Mat(h, w, CvType.CV_8UC3); out.put(0, 0, outB)
        return out
    }

    private fun percentile(sorted: FloatArray, p: Double): Float {
        if (sorted.isEmpty()) return 0f
        val idx = p / 100.0 * (sorted.size - 1)
        val lo = floor(idx).toInt(); val hi = ceil(idx).toInt()
        if (lo == hi) return sorted[lo]
        val frac = (idx - lo).toFloat()
        return sorted[lo] * (1 - frac) + sorted[hi] * frac
    }

    // ---- tons Vallejo (port de _make_tones) ---------------------------------

    fun makeTones(base: IntArray, n: Int): List<IntArray> {
        val hsv = rgbToHsv(base[0] / 255f, base[1] / 255f, base[2] / 255f)
        val hh = hsv[0]; val s = hsv[1]; val v = hsv[2]
        val sv = if (n == 3) listOf(
            floatArrayOf(s, v * 0.5f),
            floatArrayOf(s, v),
            floatArrayOf(max(0f, s * 0.68f), min(1f, v * 1.5f + 0.12f))
        ) else listOf(
            floatArrayOf(s, v * 0.4f),
            floatArrayOf(s, v * 0.72f),
            floatArrayOf(s, v),
            floatArrayOf(max(0f, s * 0.68f), min(1f, v * 1.5f + 0.12f))
        )
        return sv.map {
            val rgb = hsvToRgb(hh, it[0], it[1])
            intArrayOf((rgb[0] * 255).toInt(), (rgb[1] * 255).toInt(), (rgb[2] * 255).toInt())
        }
    }

    // colorsys.rgb_to_hsv / hsv_to_rgb (h,s,v dans [0,1]) pour coller exactement au backend
    private fun rgbToHsv(r: Float, g: Float, b: Float): FloatArray {
        val mx = max(r, max(g, b)); val mn = min(r, min(g, b)); val v = mx
        if (mn == mx) return floatArrayOf(0f, 0f, v)
        val s = (mx - mn) / mx
        val rc = (mx - r) / (mx - mn); val gc = (mx - g) / (mx - mn); val bc = (mx - b) / (mx - mn)
        var hh = when (mx) {
            r -> bc - gc
            g -> 2f + rc - bc
            else -> 4f + gc - rc
        }
        hh = (hh / 6f) % 1f
        if (hh < 0f) hh += 1f
        return floatArrayOf(hh, s, v)
    }

    private fun hsvToRgb(h: Float, s: Float, v: Float): FloatArray {
        if (s == 0f) return floatArrayOf(v, v, v)
        val i = (h * 6f).toInt()
        val f = h * 6f - i
        val p = v * (1 - s); val q = v * (1 - s * f); val t = v * (1 - s * (1 - f))
        return when (i % 6) {
            0 -> floatArrayOf(v, t, p)
            1 -> floatArrayOf(q, v, p)
            2 -> floatArrayOf(p, v, t)
            3 -> floatArrayOf(p, q, v)
            4 -> floatArrayOf(t, p, v)
            else -> floatArrayOf(v, p, q)
        }
    }
}
