package com.figurinecolor.app

import android.content.Context
import android.graphics.Bitmap

/** Variante TAILSCALE : le rendu passe par le backend HTTP, pas de moteur local. */
object Renderer {
    const val embedded = false
    fun live(ctx: Context, bmp: Bitmap, code: String, thick: Int): Bitmap =
        error("apercu live indisponible dans la variante tailscale")
    fun fill(ctx: Context, photo: ByteArray, code: String, thick: Int): ByteArray =
        error("rendu local indisponible dans la variante tailscale")
    fun zones(ctx: Context, photo: ByteArray, zonesJson: String, thick: Int): ByteArray =
        error("rendu local indisponible dans la variante tailscale")
}
