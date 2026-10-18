package com.figurinecolor.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.cancel
import org.json.JSONObject
import java.io.File

/**
 * Service de premier plan : surveille un job de rendu cote backend (polling leger)
 * et notifie a la fin. Survit a la mise en arriere-plan de l'app : le rendu lourd
 * tourne de toute facon sur le Mac, ici on ne fait qu'attendre et notifier.
 */
class RenderService : Service() {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val backend = intent?.getStringExtra("backend")
        val job = intent?.getStringExtra("job")
        val folder = intent?.getStringExtra("folder") ?: ""
        val label = intent?.getStringExtra("label") ?: "figurine"
        if (backend.isNullOrEmpty() || job.isNullOrEmpty()) {
            stopSelf(); return START_NOT_STICKY
        }
        ensureChannel()
        startForeground(ONGOING, ongoing())
        scope.launch {
            val st = poll(backend, job)
            finish(backend, job, st, folder, label)
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
        return START_REDELIVER_INTENT
    }

    override fun onDestroy() {
        super.onDestroy()
        runCatching { scope.cancel() }
        runCatching { stopForeground(STOP_FOREGROUND_REMOVE) }
    }

    private fun poll(backend: String, job: String): JSONObject? {
        val api = Api(backend)
        repeat(300) {   // ~300 * 8 s = 40 min max
            val st = runCatching { api.celStatus(job) }.getOrNull()
            when (st?.optString("status")) {
                "done", "error" -> return st
            }
            try { Thread.sleep(8000) } catch (_: InterruptedException) { return null }
        }
        return null
    }

    private fun finish(backend: String, job: String, st: JSONObject?, folder: String, label: String) {
        Settings(this).pending = null
        val status = st?.optString("status") ?: "error"
        if (status == "cancelled") return   // l'utilisateur a arrete : pas de notification
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (st == null || status == "error") {
            val msg = st?.optString("error")?.takeIf { it.isNotEmpty() } ?: "delai depasse ou backend injoignable"
            nm.notify(DONE, doneBuilder("Rendu echoue", msg).build())
            return
        }
        val fin = when {
            !st.isNull("final") -> st.optJSONObject("final")
            !st.isNull("render") -> st.optJSONObject("render")
            else -> null
        }
        val url = fin?.optString("url")
        if (url != null && url.isNotEmpty()) {
            runCatching {
                val bytes = Api(backend).fetch(url)
                val dir = if (folder.isNotEmpty()) File(folder) else filesDir
                dir.mkdirs()
                File(dir, "${label}_peint_${job}.png").writeBytes(bytes)
            }
        }
        val launch = packageManager.getLaunchIntentForPackage(packageName)?.apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        } ?: Intent()
        val pi = PendingIntent.getActivity(
            this, 0, launch,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        nm.notify(DONE, doneBuilder("Rendu termine", "Ta figurine peinte est prete. Appuie pour la voir.")
            .setContentIntent(pi).setAutoCancel(true).build())
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (nm.getNotificationChannel(CH) == null) {
                nm.createNotificationChannel(
                    NotificationChannel(CH, "Rendu figurine", NotificationManager.IMPORTANCE_DEFAULT))
            }
        }
    }

    private fun ongoing(): Notification =
        NotificationCompat.Builder(this, CH)
            .setContentTitle("Rendu en cours")
            .setContentText("Plusieurs minutes. Tu peux quitter l'app, tu seras notifie.")
            .setSmallIcon(android.R.drawable.ic_popup_sync)
            .setOngoing(true)
            .setProgress(0, 0, true)
            .build()

    private fun doneBuilder(title: String, text: String): NotificationCompat.Builder =
        NotificationCompat.Builder(this, CH)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setSmallIcon(android.R.drawable.ic_menu_gallery)

    companion object {
        const val CH = "render"
        const val ONGOING = 1001
        const val DONE = 1002

        fun start(ctx: Context, backend: String, job: String, folder: String, label: String) {
            val i = Intent(ctx, RenderService::class.java)
                .putExtra("backend", backend)
                .putExtra("job", job)
                .putExtra("folder", folder)
                .putExtra("label", label)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i)
            else ctx.startService(i)
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, RenderService::class.java))
        }
    }
}
