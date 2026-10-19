package com.figurinecolor.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme(colorScheme = CraftColors) { AppRoot() } }
    }
}

private fun dlBytes(url: String): ByteArray =
    java.net.URL(url).openStream().use { it.readBytes() }

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun AppRoot() {
    val ctx = LocalContext.current
    val notifPerm = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    LaunchedEffect(Unit) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED) {
            notifPerm.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
    val scope = rememberCoroutineScope()
    val settings = remember { Settings(ctx) }
    val repo = remember { FolderRepo(ctx) }
    LaunchedEffect(Unit) {
        val p = settings.pending
        if (p != null) scope.launch(Dispatchers.IO) {
            runCatching {
                val o = org.json.JSONObject(p)
                val jb = o.optString("job"); val be = o.optString("backend")
                val folder = o.optString("folder"); val label = o.optString("label")
                val st = Api(be).celStatus(jb)
                when (st.optString("status")) {
                    "done" -> {
                        val fin = if (!st.isNull("final")) st.optJSONObject("final") else st.optJSONObject("render")
                        val url = fin?.optString("url")
                        if (!url.isNullOrEmpty() && folder.isNotEmpty()) {
                            val f = java.io.File(folder, "${label}_peint_${jb}.png")
                            if (!f.exists()) f.writeBytes(Api(be).fetch(url))
                        }
                        settings.pending = null
                    }
                    "error", "cancelled" -> settings.pending = null
                    else -> RenderService.start(ctx, be, jb, folder, label)
                }
            }
        }
    }

    var lang by remember { mutableStateOf(settings.lang) }
    fun t(k: String) = I18n.t(lang, k)
    var backend by remember { mutableStateOf(settings.backendUrl) }
    var scheme by remember { mutableStateOf(settings.harmony) }

    var screen by remember { mutableStateOf("folders") }
    var folders by remember { mutableStateOf(repo.folders()) }
    var currentFolder by remember { mutableStateOf<String?>(null) }
    var photos by remember { mutableStateOf<List<File>>(emptyList()) }
    var currentPhoto by remember { mutableStateOf<File?>(null) }
    var photoBytes by remember { mutableStateOf<ByteArray?>(null) }

    var palette by remember { mutableStateOf<List<VColor>>(emptyList()) }
    val paintState = remember { PaintState() }
    var primary by remember { mutableStateOf<String?>(null) }
    var derived by remember { mutableStateOf<List<HColor>>(emptyList()) }
    var paintMode by remember { mutableStateOf(false) }
    var hq by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf<ProcResult?>(null) }
    var busy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("") }

    var showNewFolder by remember { mutableStateOf(false) }
    var newFolderName by remember { mutableStateOf("") }
    var moveTarget by remember { mutableStateOf<File?>(null) }
    var folderToDelete by remember { mutableStateOf<String?>(null) }
    var photoToDelete by remember { mutableStateOf<File?>(null) }
    var npMode by remember { mutableStateOf("q8") }
    var npThick by remember { mutableStateOf(2) }
    var npJob by remember { mutableStateOf<String?>(null) }
    var npMsg by remember { mutableStateOf("") }
    var selMode by remember { mutableStateOf(false) }
    val selFolders = remember { mutableStateListOf<String>() }
    val selPhotos = remember { mutableStateListOf<File>() }
    var confirmBatchDelete by remember { mutableStateOf(false) }
    var batchMove by remember { mutableStateOf(false) }
    var renameFolderT by remember { mutableStateOf<String?>(null) }
    var renamePhotoT by remember { mutableStateOf<File?>(null) }
    var renameText by remember { mutableStateOf("") }

    var pendingCapture by remember { mutableStateOf<File?>(null) }
    val camLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        val f = pendingCapture
        if (ok && f != null && f.exists()) {
            currentPhoto = f
            photoBytes = f.readBytes()
            currentFolder?.let { photos = repo.photos(it) }
            primary = null; derived = emptyList(); result = null
            screen = "colors"
        }
    }
    fun startCamera() {
        val folder = currentFolder ?: return
        val dir = File(repo.base, folder).apply { mkdirs() }
        val f = File(dir, "cap_${System.currentTimeMillis()}.jpg")
        pendingCapture = f
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", f)
        camLauncher.launch(uri)
    }
    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri ->
        val folder = currentFolder
        if (uri != null && folder != null) {
            val bytes = ctx.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            if (bytes != null) {
                val f = repo.saveBytes(folder, bytes, "img")
                currentPhoto = f; photoBytes = bytes
                photos = repo.photos(folder)
                primary = null; derived = emptyList(); result = null
                screen = "colors"
            }
        }
    }

    LaunchedEffect(screen) {
        if ((screen == "colors" || screen == "zones" || screen == "live") && palette.isEmpty()) {
            status = "..."
            runCatching { withContext(Dispatchers.IO) { if (BuildConfig.EMBEDDED) LocalData.palette(ctx) else Api(backend.trim()).palette() } }
                .onSuccess { palette = it; status = "" }
                .onFailure { status = "${t("connect")}: ${it.message}" }
        }
    }
    LaunchedEffect(primary, scheme) {
        val p = primary
        if (p != null && scheme != "custom") {
            runCatching { withContext(Dispatchers.IO) { if (BuildConfig.EMBEDDED) LocalData.harmony(ctx, p, scheme) else Api(backend.trim()).harmony(p, scheme) } }
                .onSuccess { derived = it }
                .onFailure { status = "harmony: ${it.message}" }
        } else if (p != null) {
            derived = listOf(HColor("principale", p, palette.firstOrNull { it.code == p }?.hex ?: "#808080",
                palette.firstOrNull { it.code == p }?.name ?: "", 0.0))
        }
    }
    LaunchedEffect(npJob) {
        val j = npJob ?: return@LaunchedEffect
        while (npJob == j) {
            kotlinx.coroutines.delay(8000)
            val s = runCatching {
                withContext(Dispatchers.IO) { Api(backend.trim()).celStatus(j).optString("status") }
            }.getOrNull()
            when (s) {
                "done" -> { npMsg = t("render_done_check"); npJob = null }
                "error", "cancelled" -> { npMsg = ""; npJob = null }
            }
        }
    }

    Column(Modifier.fillMaxSize()) {
        TopBar(
            title = when (screen) {
                "folders" -> t("app_name")
                "gallery" -> currentFolder ?: t("folders")
                "colors" -> t("choose_primary")
                "zones" -> t("assign_touch")
                "result" -> t("result")
                "settings" -> t("settings")
                "live" -> t("live_title")
                else -> t("app_name")
            },
            onBack = when (screen) {
                "gallery" -> ({ screen = "folders" })
                "colors" -> ({ screen = "gallery" })
                "zones" -> ({ screen = "colors" })
                "result" -> ({ screen = "colors" })
                "settings" -> ({ screen = "folders" })
                "live" -> ({ screen = "gallery" })
                else -> null
            },
            onSettings = if (screen == "folders") ({ screen = "settings" }) else null,
            backLabel = t("back"), settingsLabel = t("settings"),
        )

        if (selMode && (screen == "folders" || screen == "gallery")) {
            val n = if (screen == "gallery") selPhotos.size else selFolders.size
            Row(
                Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant)
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("$n ${t("selected")}", fontSize = 13.sp)
                Spacer(Modifier.size(10.dp))
                if (screen == "gallery" && selPhotos.isNotEmpty()) {
                    TextButton(onClick = {
                        val sel = selPhotos.toList()
                        selMode = false; selFolders.clear(); selPhotos.clear()
                        scope.launch {
                            val ok = withContext(Dispatchers.IO) { sel.count { exportToGallery(ctx, it) } }
                            android.widget.Toast.makeText(ctx, "${t("downloaded")} ($ok)",
                                android.widget.Toast.LENGTH_SHORT).show()
                        }
                    }) { Text(t("download"), fontSize = 12.sp) }
                    TextButton(onClick = { batchMove = true }) { Text(t("move_to"), fontSize = 12.sp) }
                }
                if (n == 1)
                    TextButton(onClick = {
                        renameText = if (screen == "gallery") selPhotos.first().nameWithoutExtension else selFolders.first()
                        if (screen == "gallery") renamePhotoT = selPhotos.first() else renameFolderT = selFolders.first()
                    }) { Text(t("rename"), fontSize = 12.sp) }
                if (n > 0)
                    TextButton(onClick = { confirmBatchDelete = true }) { Text(t("delete"), fontSize = 12.sp) }
                TextButton(onClick = { selMode = false; selFolders.clear(); selPhotos.clear() }) {
                    Text(t("done"), fontSize = 12.sp)
                }
            }
        }

        when (screen) {
            "folders" -> Column(Modifier.fillMaxSize().padding(16.dp).verticalScroll(rememberScrollState())) {
                Button(onClick = { showNewFolder = true }) { Text("+ ${t("new_folder")}") }
                Spacer(Modifier.height(12.dp))
                if (folders.isEmpty()) Text(t("no_folder"), color = MaterialTheme.colorScheme.secondary)
                folders.forEach { fname ->
                    val sel = selFolders.contains(fname)
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 4.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(if (sel) MaterialTheme.colorScheme.primaryContainer
                                        else MaterialTheme.colorScheme.surface)
                            .combinedClickable(
                                onClick = {
                                    if (selMode) {
                                        if (sel) selFolders.remove(fname) else selFolders.add(fname)
                                        if (selFolders.isEmpty()) selMode = false
                                    } else {
                                        currentFolder = fname; photos = repo.photos(fname); screen = "gallery"
                                    }
                                },
                                onLongClick = {
                                    selMode = true; selPhotos.clear()
                                    if (!sel) selFolders.add(fname)
                                },
                            ).padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(fname)
                        Text("${repo.photos(fname).size}", color = MaterialTheme.colorScheme.secondary)
                    }
                }
            }

            "gallery" -> Column(Modifier.fillMaxSize().padding(16.dp)) {
                Row(Modifier.horizontalScroll(rememberScrollState())) {
                    Button(onClick = { startCamera() }) { Text(t("take_photo")) }
                    Spacer(Modifier.size(8.dp))
                    FilledTonalButton(onClick = {
                        importLauncher.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                        )
                    }) { Text("+ ${t("import_photo")}") }
                    if (BuildConfig.EMBEDDED) {
                        Spacer(Modifier.size(8.dp))
                        FilledTonalButton(onClick = { screen = "live" }) { Text(t("live_button")) }
                    }
                }
                Spacer(Modifier.height(12.dp))
                if (photos.isEmpty()) {
                    Text(t("empty_folder"), color = MaterialTheme.colorScheme.secondary)
                } else {
                    LazyVerticalGrid(columns = GridCells.Adaptive(110.dp),
                        modifier = Modifier.weight(1f).fillMaxWidth()) {
                        items(photos) { f ->
                            val sel = selPhotos.contains(f)
                            Box(
                                Modifier.padding(4.dp).aspectRatio(1f)
                                    .clip(RoundedCornerShape(10.dp))
                                    .border(if (sel) 3.dp else 0.dp, MaterialTheme.colorScheme.primary,
                                        RoundedCornerShape(10.dp))
                                    .combinedClickable(
                                        onClick = {
                                            if (selMode) {
                                                if (sel) selPhotos.remove(f) else selPhotos.add(f)
                                                if (selPhotos.isEmpty()) selMode = false
                                            } else {
                                                currentPhoto = f; photoBytes = f.readBytes()
                                                primary = null; derived = emptyList(); result = null; paintState.reset()
                                                screen = "colors"
                                            }
                                        },
                                        onLongClick = {
                                            selMode = true; selFolders.clear()
                                            if (!sel) selPhotos.add(f)
                                        },
                                    )
                            ) {
                                AsyncImage(model = f, contentDescription = null, modifier = Modifier.fillMaxSize())
                                if (sel) Text("\u2713",
                                    modifier = Modifier.align(Alignment.TopEnd).padding(4.dp),
                                    color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }
            }

            "colors" -> Column(Modifier.fillMaxSize().padding(16.dp).verticalScroll(rememberScrollState())) {
                currentPhoto?.let {
                    AsyncImage(model = it, contentDescription = null,
                        modifier = Modifier.fillMaxWidth().height(200.dp).clip(RoundedCornerShape(12.dp)))
                }
                Spacer(Modifier.height(10.dp))
                // Chemin recommande pour figurine NON peinte : peindre les zones au doigt.
                Button(onClick = { screen = "zones" }, modifier = Modifier.fillMaxWidth()) {
                    Text(t("assign_touch"))
                }
                Spacer(Modifier.height(14.dp))
                Text(t("choose_primary"), style = MaterialTheme.typography.titleMedium)
                LazyVerticalGrid(columns = GridCells.Adaptive(64.dp), modifier = Modifier.height(170.dp)) {
                    items(palette) { c ->
                        val col = parseHex(c.hex)
                        Box(
                            Modifier.padding(3.dp).height(44.dp).fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp)).background(col)
                                .border(if (primary == c.code) 3.dp else 0.dp, MaterialTheme.colorScheme.onBackground,
                                    RoundedCornerShape(8.dp))
                                .clickable { primary = c.code },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(c.code.removePrefix("69."), fontSize = 10.sp,
                                color = if (luma(col) > 0.5f) Color.Black else Color.White)
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
                Text(t("fill_hint"), fontSize = 12.sp, color = MaterialTheme.colorScheme.secondary)
                Spacer(Modifier.height(8.dp))
                Text(t("ink_thickness"), fontSize = 12.sp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Chip(t("ink_fine"), npThick == 2) { npThick = 2 }
                    Chip(t("ink_bold"), npThick == 3) { npThick = 3 }
                }
                Spacer(Modifier.height(10.dp))
                if (busy) {
                    Text(t("rendering_long"), fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.height(4.dp))
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                    Spacer(Modifier.height(6.dp))
                } else if (npMsg.isNotEmpty()) {
                    Text(npMsg, fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.height(6.dp))
                }
                if (npJob != null) {
                    OutlinedButton(
                        onClick = {
                            val j = npJob ?: return@OutlinedButton
                            scope.launch {
                                runCatching { withContext(Dispatchers.IO) { Api(backend.trim()).celCancel(j) } }
                                RenderService.stop(ctx)
                                settings.pending = null
                                npJob = null
                                npMsg = t("render_stopped")
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(t("stop")) }
                    Spacer(Modifier.height(6.dp))
                }
                Button(
                    enabled = !busy && photoBytes != null && primary != null && npJob == null,
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        scope.launch {
                            busy = true; status = ""
                            if (BuildConfig.EMBEDDED) {
                                runCatching {
                                    withContext(Dispatchers.IO) {
                                        val out = Renderer.fill(ctx, photoBytes!!, primary!!, npThick)
                                        val dir = currentPhoto!!.parentFile!!
                                        val f = java.io.File(dir, "${currentPhoto!!.nameWithoutExtension}_peint_${System.currentTimeMillis()}.png")
                                        f.writeBytes(out); f
                                    }
                                }.onSuccess {
                                    currentFolder?.let { photos = repo.photos(it) }
                                    android.widget.Toast.makeText(ctx, t("render_done_check"), android.widget.Toast.LENGTH_SHORT).show()
                                    screen = "gallery"
                                }.onFailure { status = "erreur: ${it.message}" }
                            } else {
                                runCatching {
                                    withContext(Dispatchers.IO) {
                                        Api(backend.trim()).celFillStart(photoBytes!!, primary!!, npMode, npThick)
                                    }
                                }.onSuccess { o ->
                                    val jobId = o.optString("id")
                                    val folder = currentPhoto?.parentFile?.absolutePath ?: ""
                                    val label = currentPhoto?.nameWithoutExtension ?: "figurine"
                                    settings.pending = org.json.JSONObject()
                                        .put("job", jobId).put("backend", backend.trim())
                                        .put("folder", folder).put("label", label).toString()
                                    RenderService.start(ctx, backend.trim(), jobId, folder, label)
                                    npJob = jobId; npMsg = t("render_started")
                                }.onFailure { status = "erreur: ${it.message}" }
                            }
                            busy = false
                        }
                    },
                ) { Text(if (busy) t("rendering") else t("colorize")) }
                Spacer(Modifier.height(8.dp))
                if (status.isNotEmpty()) Text(status, color = MaterialTheme.colorScheme.error)
            }

            "zones" -> {
                val p = currentPhoto; val b = photoBytes
                if (p != null && b != null) {
                    PaintScreen(
                        photo = p, bytes = b, palette = palette, backend = backend, state = paintState,
                        settings = settings,
                        t = { k -> t(k) },
                        onResult = { result = it; screen = "result" },
                        onStatus = { status = it },
                        onSaved = { currentFolder?.let { photos = repo.photos(it) }; screen = "gallery" },
                    )
                }
            }

            "live" -> LiveScreen(
                palette = palette,
                t = { k -> t(k) },
                onCapture = { bmp ->
                    val f0 = currentFolder
                    if (f0 != null) {
                        val bos = java.io.ByteArrayOutputStream()
                        bmp.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, bos)
                        repo.saveBytes(f0, bos.toByteArray(), "live")
                        photos = repo.photos(f0)
                    }
                    screen = "gallery"
                },
            )

            "result" -> Column(Modifier.fillMaxSize().padding(16.dp).verticalScroll(rememberScrollState())) {
                val r = result
                if (r != null) {
                    Text(t("exact_color"), style = MaterialTheme.typography.titleMedium)
                    AsyncImage(model = r.recolorUrl, contentDescription = null,
                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)))
                    r.zones.forEach { z ->
                        Text("${z.role} ${z.hex} - ${t("coverage")} ${z.coverage}% - ${t("deltae")} ${z.deltaE ?: "-"}",
                            fontSize = 12.sp, color = MaterialTheme.colorScheme.secondary)
                    }
                    r.paintUrl?.let { url ->
                        Spacer(Modifier.height(10.dp))
                        Text(t("painted_render"), style = MaterialTheme.typography.titleMedium)
                        AsyncImage(model = url, contentDescription = null,
                            modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)))
                    }
                    Spacer(Modifier.height(12.dp))
                    Button(onClick = {
                        scope.launch {
                            val url = r.paintUrl ?: r.recolorUrl
                            val folder = currentFolder ?: return@launch
                            runCatching {
                                val bytes = withContext(Dispatchers.IO) { dlBytes(url) }
                                repo.saveBytes(folder, bytes, "render")
                            }.onSuccess { status = t("save"); photos = repo.photos(currentFolder!!) }
                                .onFailure { status = "erreur: ${it.message}" }
                        }
                    }, modifier = Modifier.fillMaxWidth()) { Text(t("save")) }
                    if (status.isNotEmpty()) Text(status, fontSize = 12.sp)
                }
            }

            "settings" -> Column(Modifier.fillMaxSize().padding(16.dp).verticalScroll(rememberScrollState())) {
                Text(t("language"), style = MaterialTheme.typography.titleMedium)
                Row(Modifier.horizontalScroll(rememberScrollState())) {
                    Lang.entries.forEach { lg ->
                        Chip(lg.label, lang == lg.code) { lang = lg.code; settings.lang = lg.code }
                    }
                }
                Spacer(Modifier.height(16.dp))
                Text(t("backend_url"), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = backend, onValueChange = { backend = it; settings.backendUrl = it },
                    modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(16.dp))
                Text(t("default_harmony"), style = MaterialTheme.typography.titleMedium)
                Row(Modifier.horizontalScroll(rememberScrollState())) {
                    listOf("analogous", "complementary", "split", "triad", "tetradic", "square", "monochromatic", "custom")
                        .forEach { s -> Chip(t("harm_$s"), scheme == s) { scheme = s; settings.harmony = s } }
                }
            }
        }
    }

    if (showNewFolder) {
        AlertDialog(
            onDismissRequest = { showNewFolder = false },
            title = { Text(t("new_folder")) },
            text = {
                OutlinedTextField(value = newFolderName, onValueChange = { newFolderName = it },
                    label = { Text(t("folder_name")) }, singleLine = true)
            },
            confirmButton = {
                TextButton(onClick = {
                    if (repo.createFolder(newFolderName)) { folders = repo.folders() }
                    newFolderName = ""; showNewFolder = false
                }) { Text(t("create")) }
            },
            dismissButton = { TextButton(onClick = { showNewFolder = false }) { Text(t("cancel")) } },
        )
    }

    moveTarget?.let { file ->
        AlertDialog(
            onDismissRequest = { moveTarget = null },
            title = { Text(t("move_to")) },
            text = {
                Column {
                    folders.filter { it != currentFolder }.forEach { tf ->
                        TextButton(onClick = {
                            repo.move(file, tf)
                            currentFolder?.let { photos = repo.photos(it) }
                            folders = repo.folders(); moveTarget = null
                        }) { Text(tf) }
                    }
                    if (folders.filter { it != currentFolder }.isEmpty())
                        Text(t("no_folder"), color = MaterialTheme.colorScheme.secondary)
                }
            },
            confirmButton = { TextButton(onClick = { moveTarget = null }) { Text(t("cancel")) } },
        )
    }

    folderToDelete?.let { fname ->
        AlertDialog(
            onDismissRequest = { folderToDelete = null },
            title = { Text(t("delete_folder")) },
            text = { Text(t("delete_folder_q").replace("%s", fname)) },
            confirmButton = {
                TextButton(onClick = {
                    repo.deleteFolder(fname)
                    folders = repo.folders()
                    if (currentFolder == fname) { currentFolder = null; screen = "folders" }
                    folderToDelete = null
                }) { Text(t("delete")) }
            },
            dismissButton = { TextButton(onClick = { folderToDelete = null }) { Text(t("cancel")) } },
        )
    }

    photoToDelete?.let { file ->
        AlertDialog(
            onDismissRequest = { photoToDelete = null },
            title = { Text(t("delete_photo")) },
            text = { Text(t("delete_photo_q")) },
            confirmButton = {
                TextButton(onClick = {
                    repo.deletePhoto(file)
                    currentFolder?.let { photos = repo.photos(it) }
                    folders = repo.folders()
                    photoToDelete = null
                }) { Text(t("delete")) }
            },
            dismissButton = { TextButton(onClick = { photoToDelete = null }) { Text(t("cancel")) } },
        )
    }

    if (confirmBatchDelete) {
        val n = if (screen == "gallery") selPhotos.size else selFolders.size
        AlertDialog(
            onDismissRequest = { confirmBatchDelete = false },
            title = { Text(t("delete")) },
            text = { Text("${t("delete")} ($n)") },
            confirmButton = {
                TextButton(onClick = {
                    if (screen == "gallery") {
                        selPhotos.toList().forEach { repo.deletePhoto(it) }
                        currentFolder?.let { photos = repo.photos(it) }
                    } else {
                        selFolders.toList().forEach { repo.deleteFolder(it) }
                    }
                    folders = repo.folders()
                    confirmBatchDelete = false; selMode = false; selFolders.clear(); selPhotos.clear()
                }) { Text(t("delete")) }
            },
            dismissButton = { TextButton(onClick = { confirmBatchDelete = false }) { Text(t("cancel")) } },
        )
    }

    if (batchMove) {
        AlertDialog(
            onDismissRequest = { batchMove = false },
            title = { Text(t("move_to")) },
            text = {
                Column {
                    folders.filter { it != currentFolder }.forEach { tf ->
                        TextButton(onClick = {
                            selPhotos.toList().forEach { repo.move(it, tf) }
                            currentFolder?.let { photos = repo.photos(it) }
                            folders = repo.folders()
                            batchMove = false; selMode = false; selPhotos.clear()
                        }) { Text(tf) }
                    }
                    if (folders.filter { it != currentFolder }.isEmpty())
                        Text(t("no_folder"), color = MaterialTheme.colorScheme.secondary)
                }
            },
            confirmButton = { TextButton(onClick = { batchMove = false }) { Text(t("cancel")) } },
        )
    }

    renameFolderT?.let { old ->
        AlertDialog(
            onDismissRequest = { renameFolderT = null },
            title = { Text(t("rename")) },
            text = {
                OutlinedTextField(value = renameText, onValueChange = { renameText = it },
                    label = { Text(t("folder_name")) }, singleLine = true)
            },
            confirmButton = {
                TextButton(onClick = {
                    if (repo.renameFolder(old, renameText)) {
                        if (currentFolder == old) currentFolder = renameText.trim()
                        folders = repo.folders()
                    }
                    renameFolderT = null; selMode = false; selFolders.clear()
                }) { Text(t("rename")) }
            },
            dismissButton = { TextButton(onClick = { renameFolderT = null }) { Text(t("cancel")) } },
        )
    }

    renamePhotoT?.let { file ->
        AlertDialog(
            onDismissRequest = { renamePhotoT = null },
            title = { Text(t("rename")) },
            text = {
                OutlinedTextField(value = renameText, onValueChange = { renameText = it },
                    label = { Text(t("rename")) }, singleLine = true)
            },
            confirmButton = {
                TextButton(onClick = {
                    repo.renamePhoto(file, renameText)
                    currentFolder?.let { photos = repo.photos(it) }
                    renamePhotoT = null; selMode = false; selPhotos.clear()
                }) { Text(t("rename")) }
            },
            dismissButton = { TextButton(onClick = { renamePhotoT = null }) { Text(t("cancel")) } },
        )
    }
}

// ----- Editeur pinceau au doigt (figurine non peinte, recolor exact) -----
data class Sk(val pts: List<Offset>, val r: Float, val erase: Boolean)
data class Zn(val code: String, val hex: String, val strokes: List<Sk>)

private fun DrawScope.drawSk(sk: Sk, color: Color) {
    val w = size.width; val h = size.height
    val sw = (sk.r * 2f * minOf(w, h)).coerceAtLeast(2f)
    val bm = if (sk.erase) BlendMode.Clear else BlendMode.SrcOver
    if (sk.pts.size < 2) {
        val p = sk.pts.firstOrNull() ?: return
        drawCircle(color, sw / 2f, Offset(p.x * w, p.y * h), blendMode = bm)
    } else {
        val path = Path()
        sk.pts.forEachIndexed { i, o ->
            val x = o.x * w; val y = o.y * h
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, color, style = Stroke(sw, cap = StrokeCap.Round, join = StrokeJoin.Round), blendMode = bm)
    }
}

class PaintState {
    var zones by mutableStateOf<List<Zn>>(emptyList())
    var activeStrokes by mutableStateOf<List<Sk>>(emptyList())
    var activeCode by mutableStateOf<String?>(null)
    fun reset() { zones = emptyList(); activeStrokes = emptyList(); activeCode = null }
}

@Composable
fun PaintScreen(
    photo: File, bytes: ByteArray, palette: List<VColor>, backend: String, state: PaintState,
    settings: Settings,
    t: (String) -> String, onResult: (ProcResult) -> Unit, onStatus: (String) -> Unit,
    onSaved: (() -> Unit)? = null,
) {
    val scope = rememberCoroutineScope()
    val ctx = LocalContext.current
    val drawing = remember { mutableStateListOf<Offset>() }
    var mode by remember { mutableStateOf("paint") }   // paint | zoom
    var eraser by remember { mutableStateOf(false) }
    var brushR by remember { mutableStateOf(0.02f) }
    var scale by remember { mutableStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    var boxSize by remember { mutableStateOf(IntSize.Zero) }
    var busy by remember { mutableStateOf(false) }
    var qmode by remember { mutableStateOf("q8") }
    var thick by remember { mutableStateOf(2) }
    var launchedMsg by remember { mutableStateOf("") }
    var pendingJobId by remember { mutableStateOf<String?>(null) }
    var pScheme by remember { mutableStateOf(settings.harmony) }
    var pHarmony by remember { mutableStateOf<List<HColor>>(emptyList()) }
    var harmonyBase by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(palette) {
        if (state.activeCode == null) state.activeCode = palette.firstOrNull()?.code
        if (harmonyBase == null) harmonyBase = state.activeCode
    }
    LaunchedEffect(Unit) {
        settings.pending?.let { p ->
            runCatching {
                val o = org.json.JSONObject(p)
                if (o.optString("label") == photo.nameWithoutExtension) {
                    pendingJobId = o.optString("job"); launchedMsg = t("render_started")
                }
            }
        }
    }
    LaunchedEffect(pendingJobId) {
        val j = pendingJobId ?: return@LaunchedEffect
        while (pendingJobId == j) {
            kotlinx.coroutines.delay(8000)
            val s = runCatching {
                withContext(Dispatchers.IO) { Api(backend.trim()).celStatus(j).optString("status") }
            }.getOrNull()
            when (s) {
                "done" -> { launchedMsg = t("render_done_check"); pendingJobId = null }
                "error", "cancelled" -> { launchedMsg = ""; pendingJobId = null }
            }
        }
    }
    LaunchedEffect(harmonyBase, pScheme) {
        val c = harmonyBase
        if (c == null || pScheme == "custom") { pHarmony = emptyList(); return@LaunchedEffect }
        runCatching { withContext(Dispatchers.IO) { if (BuildConfig.EMBEDDED) LocalData.harmony(ctx, c, pScheme) else Api(backend.trim()).harmony(c, pScheme) } }
            .onSuccess { pHarmony = it }
            .onFailure { pHarmony = emptyList() }
    }

    val aspect = remember(photo) {
        val o = android.graphics.BitmapFactory.Options().apply { inJustDecodeBounds = true }
        android.graphics.BitmapFactory.decodeFile(photo.absolutePath, o)
        if (o.outWidth > 0 && o.outHeight > 0) o.outWidth.toFloat() / o.outHeight else 1f
    }
    val activeHex = palette.firstOrNull { it.code == state.activeCode }?.hex ?: "#ffffff"

    fun pickColor(code: String) {
        val ac = state.activeCode
        if (state.activeStrokes.isNotEmpty() && ac != null && code != ac) {
            state.zones = state.zones + Zn(ac, palette.firstOrNull { it.code == ac }?.hex ?: "#808080", state.activeStrokes)
            state.activeStrokes = emptyList()
        }
        state.activeCode = code
    }

    fun buildZonesJson(): String {
        val arr = org.json.JSONArray()
        fun add(code: String, strokes: List<Sk>) {
            if (strokes.isEmpty()) return
            val sarr = org.json.JSONArray()
            strokes.forEach { s ->
                val pa = org.json.JSONArray()
                s.pts.forEach { o -> pa.put(org.json.JSONArray().put(o.x.toDouble()).put(o.y.toDouble())) }
                sarr.put(org.json.JSONObject().put("pts", pa).put("r", s.r.toDouble())
                    .put("mode", if (s.erase) "erase" else "add"))
            }
            arr.put(org.json.JSONObject().put("code", code).put("strokes", sarr))
        }
        state.zones.forEach { add(it.code, it.strokes) }
        state.activeCode?.let { add(it, state.activeStrokes) }
        return arr.toString()
    }

    val canColorize = state.zones.any { it.strokes.isNotEmpty() } || state.activeStrokes.isNotEmpty()

    Column(Modifier.fillMaxSize().padding(10.dp)) {
        Text(t("paint_hint"), fontSize = 11.sp, color = MaterialTheme.colorScheme.secondary)
        Spacer(Modifier.height(6.dp))
        Row(Modifier.fillMaxWidth()) {
        Box(
            Modifier.weight(1f).aspectRatio(aspect)
                .clip(RoundedCornerShape(10.dp)).clipToBounds()
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .onSizeChanged { boxSize = it }
                .pointerInput(mode, boxSize) {
                    if (mode == "paint") {
                        detectDragGestures(
                            onDragStart = { pos ->
                                drawing.clear()
                                val w = boxSize.width.toFloat(); val h = boxSize.height.toFloat()
                                if (w > 0f && h > 0f) drawing.add(Offset(
                                    (((pos.x - offset.x) / scale) / w).coerceIn(0f, 1f),
                                    (((pos.y - offset.y) / scale) / h).coerceIn(0f, 1f)))
                            },
                            onDrag = { change, _ ->
                                val w = boxSize.width.toFloat(); val h = boxSize.height.toFloat()
                                if (w > 0f && h > 0f) drawing.add(Offset(
                                    (((change.position.x - offset.x) / scale) / w).coerceIn(0f, 1f),
                                    (((change.position.y - offset.y) / scale) / h).coerceIn(0f, 1f)))
                            },
                            onDragEnd = {
                                if (drawing.isNotEmpty()) {
                                    state.activeStrokes = state.activeStrokes + Sk(drawing.toList(), brushR, eraser)
                                    drawing.clear()
                                }
                            },
                            onDragCancel = { drawing.clear() },
                        )
                    } else {
                        detectTransformGestures { _, pan, zoom, _ ->
                            val w = boxSize.width.toFloat(); val h = boxSize.height.toFloat()
                            val ns = (scale * zoom).coerceIn(1f, 6f)
                            scale = ns
                            offset = Offset(
                                (offset.x + pan.x).coerceIn(-(ns - 1f) * w, 0f),
                                (offset.y + pan.y).coerceIn(-(ns - 1f) * h, 0f))
                        }
                    }
                }
        ) {
            AsyncImage(
                model = photo, contentDescription = null, contentScale = ContentScale.FillBounds,
                modifier = Modifier.fillMaxSize().graphicsLayer(
                    scaleX = scale, scaleY = scale, translationX = offset.x, translationY = offset.y,
                    transformOrigin = TransformOrigin(0f, 0f)),
            )
            Canvas(
                Modifier.fillMaxSize().graphicsLayer {
                    scaleX = scale; scaleY = scale
                    translationX = offset.x; translationY = offset.y
                    transformOrigin = TransformOrigin(0f, 0f)
                    compositingStrategy = CompositingStrategy.Offscreen
                },
            ) {
                state.zones.forEach { z ->
                    val col = parseHex(z.hex).copy(alpha = 0.5f)
                    z.strokes.forEach { drawSk(it, col) }
                }
                val acol = parseHex(activeHex).copy(alpha = 0.5f)
                state.activeStrokes.forEach { drawSk(it, acol) }
                if (drawing.isNotEmpty()) drawSk(Sk(drawing.toList(), brushR, eraser), acol)
            }
            }
            if (pHarmony.size >= 2) {
                Spacer(Modifier.size(6.dp))
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(t("harmony"), fontSize = 9.sp)
                    pHarmony.forEach { hc ->
                        val hcol = parseHex(hc.hex)
                        Box(
                            Modifier.padding(vertical = 3.dp).size(42.dp).clip(RoundedCornerShape(8.dp))
                                .background(hcol)
                                .border(if (state.activeCode == hc.code) 3.dp else 1.dp,
                                    MaterialTheme.colorScheme.onBackground, RoundedCornerShape(8.dp))
                                .clickable { pickColor(hc.code) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(hc.code.removePrefix("69."), fontSize = 9.sp,
                                color = if (luma(hcol) > 0.5f) Color.Black else Color.White)
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(6.dp))
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Chip(t("mode_paint"), mode == "paint") { mode = "paint" }
                Chip(t("mode_zoom"), mode == "zoom") { mode = "zoom" }
                Spacer(Modifier.size(10.dp))
                if (mode == "paint") Chip(t("eraser"), eraser) { eraser = !eraser }
            }
            Spacer(Modifier.height(4.dp))
            Text(t("brush_size"), fontSize = 12.sp)
            Row(Modifier.horizontalScroll(rememberScrollState()), verticalAlignment = Alignment.CenterVertically) {
                val sizes = listOf(0.01f, 0.02f, 0.03f, 0.04f, 0.05f, 0.08f)
                val labels = listOf("1", "2", "3", "4", "5", "8")
                sizes.forEachIndexed { i, s ->
                    Chip(labels[i], brushR == s) { brushR = s }
                    Spacer(Modifier.size(4.dp))
                }
            }
            Spacer(Modifier.height(4.dp))
            Text(t("harmony"), fontSize = 12.sp)
            Row(Modifier.horizontalScroll(rememberScrollState())) {
                listOf("custom", "analogous", "complementary", "split", "triad", "tetradic", "square", "monochromatic")
                    .forEach { s -> Chip(t("harm_$s"), pScheme == s) { pScheme = s } }
            }
            Text("${t("active_color")}: ${state.activeCode ?: "-"}", fontSize = 12.sp)
            LazyVerticalGrid(columns = GridCells.Adaptive(54.dp), modifier = Modifier.height(96.dp)) {
                items(palette) { c ->
                    val col = parseHex(c.hex)
                    Box(
                        Modifier.padding(2.dp).height(34.dp).fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp)).background(col)
                            .border(if (state.activeCode == c.code) 3.dp else 0.dp, MaterialTheme.colorScheme.onBackground,
                                RoundedCornerShape(6.dp))
                            .clickable { pickColor(c.code); harmonyBase = c.code },
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(c.code.removePrefix("69."), fontSize = 9.sp,
                            color = if (luma(col) > 0.5f) Color.Black else Color.White)
                    }
                }
            }
            if (state.zones.isNotEmpty()) {
                Row(Modifier.horizontalScroll(rememberScrollState()).padding(vertical = 4.dp)) {
                    state.zones.forEach { z ->
                        Box(Modifier.padding(end = 6.dp).size(26.dp).clip(RoundedCornerShape(6.dp))
                            .background(parseHex(z.hex))
                            .border(1.dp, MaterialTheme.colorScheme.onBackground, RoundedCornerShape(6.dp)))
                    }
                }
            }
            Spacer(Modifier.height(4.dp))
            Row {
                OutlinedButton(onClick = {
                    if (state.activeStrokes.isNotEmpty()) state.activeStrokes = state.activeStrokes.dropLast(1)
                }) { Text(t("undo")) }
                Spacer(Modifier.size(8.dp))
                OutlinedButton(onClick = { state.zones = emptyList(); state.activeStrokes = emptyList(); drawing.clear() }) {
                    Text(t("clear_all"))
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(t("ink_thickness"), fontSize = 12.sp)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Chip(t("ink_fine"), thick == 2) { thick = 2 }
                Chip(t("ink_bold"), thick == 3) { thick = 3 }
            }
            Spacer(Modifier.height(8.dp))
        }
        if (busy) {
            Text(t("rendering_long"), fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(4.dp))
            LinearProgressIndicator(Modifier.fillMaxWidth())
            Spacer(Modifier.height(6.dp))
        } else if (launchedMsg.isNotEmpty()) {
            Text(launchedMsg, fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(6.dp))
        }
        if (pendingJobId != null) {
            OutlinedButton(
                onClick = {
                    val j = pendingJobId ?: return@OutlinedButton
                    scope.launch {
                        runCatching { withContext(Dispatchers.IO) { Api(backend.trim()).celCancel(j) } }
                        RenderService.stop(ctx)
                        settings.pending = null
                        pendingJobId = null
                        launchedMsg = t("render_stopped")
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(t("stop")) }
            Spacer(Modifier.height(6.dp))
        }
        Button(
            enabled = !busy && canColorize && pendingJobId == null,
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                val json = buildZonesJson()
                scope.launch {
                    busy = true; onStatus("")
                    if (BuildConfig.EMBEDDED) {
                        runCatching {
                            withContext(Dispatchers.IO) {
                                val out = Renderer.zones(ctx, bytes, json, thick)
                                val dir = photo.parentFile!!
                                val f = java.io.File(dir, "${photo.nameWithoutExtension}_peint_${System.currentTimeMillis()}.png")
                                f.writeBytes(out); f
                            }
                        }.onSuccess { onSaved?.invoke() }
                            .onFailure { onStatus("erreur: ${it.message}") }
                    } else {
                        runCatching {
                            withContext(Dispatchers.IO) { Api(backend.trim()).celZonesStart(bytes, json, qmode, thick) }
                        }.onSuccess { o ->
                            val jobId = o.optString("id")
                            settings.pending = org.json.JSONObject()
                                .put("job", jobId).put("backend", backend.trim())
                                .put("folder", photo.parentFile?.absolutePath ?: "")
                                .put("label", photo.nameWithoutExtension).toString()
                            RenderService.start(ctx, backend.trim(), jobId,
                                photo.parentFile?.absolutePath ?: "", photo.nameWithoutExtension)
                            pendingJobId = jobId
                            launchedMsg = t("render_started")
                        }.onFailure { launchedMsg = ""; onStatus("erreur: ${it.message}") }
                    }
                    busy = false
                }
            },
        ) { Text(if (busy) t("rendering") else t("colorize")) }
    }
}

@Composable
fun TopBar(title: String, onBack: (() -> Unit)?, onSettings: (() -> Unit)?,
           backLabel: String, settingsLabel: String) {
    Row(
        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.primary).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        if (onBack != null) TextButton(onClick = onBack) { Text(backLabel, color = MaterialTheme.colorScheme.onPrimary) }
        else Spacer(Modifier.size(1.dp))
        Text(title, color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.titleLarge)
        if (onSettings != null) TextButton(onClick = onSettings) { Text(settingsLabel, color = MaterialTheme.colorScheme.onPrimary) }
        else Spacer(Modifier.size(1.dp))
    }
}

@Composable
fun Chip(label: String, selected: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.padding(end = 6.dp)
            .clip(RoundedCornerShape(50))
            .background(if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant)
            .clickable { onClick() }
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Text(label, fontSize = 13.sp,
            color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

fun parseHex(hex: String): Color {
    val h = hex.removePrefix("#")
    val r = h.substring(0, 2).toInt(16)
    val g = h.substring(2, 4).toInt(16)
    val b = h.substring(4, 6).toInt(16)
    return Color(r, g, b)
}

fun luma(c: Color): Float = 0.299f * c.red + 0.587f * c.green + 0.114f * c.blue


@Composable
fun LiveScreen(
    palette: List<VColor>,
    t: (String) -> String,
    onCapture: (android.graphics.Bitmap) -> Unit,
) {
    val ctx = LocalContext.current
    val owner = remember(ctx) { ctx.findLifecycleOwner() }
    var granted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted = it }
    LaunchedEffect(Unit) { if (!granted) permLauncher.launch(Manifest.permission.CAMERA) }

    var code by remember { mutableStateOf(palette.firstOrNull()?.code ?: "69.008") }
    val codeState = rememberUpdatedState(code)
    var frame by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
    val exec = remember { java.util.concurrent.Executors.newSingleThreadExecutor() }
    DisposableEffect(Unit) { onDispose { exec.shutdown() } }

    if (granted && owner != null) {
        LaunchedEffect(Unit) {
            val provider = withContext(Dispatchers.IO) {
                androidx.camera.lifecycle.ProcessCameraProvider.getInstance(ctx).get()
            }
            val analysis = androidx.camera.core.ImageAnalysis.Builder()
                .setBackpressureStrategy(androidx.camera.core.ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setTargetResolution(android.util.Size(480, 640))
                .build()
            analysis.setAnalyzer(exec) { img ->
                try {
                    val small = prepFrame(img.toBitmap(), img.imageInfo.rotationDegrees, 480)
                    val out = runCatching { Renderer.live(ctx, small, codeState.value, 2) }.getOrNull()
                    if (out != null) frame = out
                } catch (_: Throwable) {
                } finally { img.close() }
            }
            try {
                provider.unbindAll()
                provider.bindToLifecycle(
                    owner,
                    androidx.camera.core.CameraSelector.DEFAULT_BACK_CAMERA,
                    analysis
                )
            } catch (_: Throwable) {}
        }
    }

    Column(Modifier.fillMaxSize().padding(12.dp)) {
        if (!granted) {
            Text(t("camera_denied"), color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(16.dp))
        } else {
            Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                val f = frame
                if (f != null) Image(
                    bitmap = f.asImageBitmap(), contentDescription = null,
                    modifier = Modifier.fillMaxWidth()
                ) else Text(t("live_starting"))
            }
            Text(t("live_hint"), color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.padding(vertical = 6.dp))
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
                palette.take(40).forEach { c ->
                    val sel = c.code == code
                    Box(
                        Modifier.padding(3.dp).size(36.dp)
                            .background(
                                Color(android.graphics.Color.parseColor(c.hex)),
                                RoundedCornerShape(6.dp)
                            )
                            .border(
                                if (sel) 3.dp else 1.dp,
                                if (sel) MaterialTheme.colorScheme.primary else Color.Gray,
                                RoundedCornerShape(6.dp)
                            )
                            .clickable { code = c.code }
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = { frame?.let { onCapture(it) } },
                enabled = frame != null, modifier = Modifier.fillMaxWidth()
            ) { Text(t("capture")) }
        }
    }
}

private fun prepFrame(src: android.graphics.Bitmap, rot: Int, maxDim: Int): android.graphics.Bitmap {
    val scale = maxDim.toFloat() / maxOf(src.width, src.height)
    val m = android.graphics.Matrix()
    if (scale < 1f) m.postScale(scale, scale)
    if (rot != 0) m.postRotate(rot.toFloat())
    return android.graphics.Bitmap.createBitmap(src, 0, 0, src.width, src.height, m, true)
}

private fun android.content.Context.findLifecycleOwner(): androidx.lifecycle.LifecycleOwner? {
    var c: android.content.Context? = this
    while (c != null) {
        if (c is androidx.lifecycle.LifecycleOwner) return c
        c = (c as? android.content.ContextWrapper)?.baseContext
    }
    return null
}
