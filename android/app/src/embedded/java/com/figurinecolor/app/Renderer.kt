package com.figurinecolor.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import org.json.JSONArray
import java.io.ByteArrayOutputStream

/** Variante EMBEDDED : rendu cel 100% local (OpenCV / CelEngine), aucun reseau. */
object Renderer {
    const val embedded = true

    fun fill(ctx: Context, photo: ByteArray, code: String, thick: Int): ByteArray {
        val bmp = BitmapFactory.decodeByteArray(photo, 0, photo.size)
            ?: error("image illisible")
        val out = CelEngine.fill(bmp, LocalData.rgbFor(ctx, code), true, thick)
        return toPng(out)
    }

    fun zones(ctx: Context, photo: ByteArray, zonesJson: String, thick: Int): ByteArray {
        val bmp = BitmapFactory.decodeByteArray(photo, 0, photo.size)
            ?: error("image illisible")
        val arr = JSONArray(zonesJson)
        val zones = ArrayList<ZoneSpec>()
        for (i in 0 until arr.length()) {
            val z = arr.getJSONObject(i)
            val code = z.getString("code")
            val strokesArr = z.optJSONArray("strokes") ?: JSONArray()
            val strokes = ArrayList<Stroke>()
            for (j in 0 until strokesArr.length()) {
                val st = strokesArr.getJSONObject(j)
                val ptsArr = st.getJSONArray("pts")
                val pts = ArrayList<FloatArray>()
                for (k in 0 until ptsArr.length()) {
                    val pt = ptsArr.getJSONArray(k)
                    pts.add(floatArrayOf(pt.getDouble(0).toFloat(), pt.getDouble(1).toFloat()))
                }
                val r = st.optDouble("r", 0.04).toFloat()
                val erase = st.optString("mode") == "erase"
                strokes.add(Stroke(pts, r, erase))
            }
            zones.add(ZoneSpec(LocalData.rgbFor(ctx, code), strokes))
        }
        val out = CelEngine.zones(bmp, zones, true, thick)
        return toPng(out)
    }

    fun live(ctx: Context, bmp: Bitmap, code: String, thick: Int): Bitmap =
        CelEngine.fillLive(bmp, LocalData.rgbFor(ctx, code), thick)

    private fun toPng(bmp: Bitmap): ByteArray {
        val bos = ByteArrayOutputStream()
        bmp.compress(Bitmap.CompressFormat.PNG, 100, bos)
        return bos.toByteArray()
    }
}
