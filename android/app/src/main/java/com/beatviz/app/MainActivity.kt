package com.beatviz.app

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var jsBridge: JsBridge

    inner class JsBridge {
        // Pick an audio file from device storage
        @JavascriptInterface
        fun pickAudio() {
            runOnUiThread {
                val i = Intent(Intent.ACTION_GET_CONTENT).apply {
                    type = "audio/*"
                    addCategory(Intent.CATEGORY_OPENABLE)
                }
                audioPicker.launch(i)
            }
        }

        // Read a picked content:// file as base64
        @JavascriptInterface
        fun readBase64(uri: String): String {
            return try {
                val bytes = contentResolver.openInputStream(Uri.parse(uri))?.use {
                    it.readBytes()
                } ?: return ""
                android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP)
            } catch (e: Exception) { "" }
        }

        // Save a recorded video blob to MediaStore (Downloads)
        @JavascriptInterface
        fun saveBase64File(name: String, mime: String, base64: String): Boolean {
            return try {
                val bytes = android.util.Base64.decode(base64, android.util.Base64.DEFAULT)
                val cr = contentResolver
                val values = android.content.ContentValues().apply {
                    put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, name)
                    put(android.provider.MediaStore.MediaColumns.MIME_TYPE, mime)
                    put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH,
                        android.os.Environment.DIRECTORY_DOWNLOADS + "/BeatViz")
                }
                val uri = cr.insert(
                    android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    ?: return false
                cr.openOutputStream(uri)?.use { it.write(bytes) } ?: return false
                true
            } catch (e: Exception) { false }
        }

        @JavascriptInterface
        fun isAndroid(): Boolean = true
    }

    private val audioPicker = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()) { res ->
        if (res.resultCode == Activity.RESULT_OK) {
            val uri: Uri? = res.data?.data
            if (uri != null) {
                webView.evaluateJavascript(
                    "window.__onAudioPicked && window.__onAudioPicked('$uri')", null)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this)
        setContentView(webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = true
            cacheMode = WebSettings.LOAD_NO_CACHE
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(req: PermissionRequest) {
                runOnUiThread { req.grant(req.resources) }
            }
        }
        webView.webViewClient = WebViewClient()
        jsBridge = JsBridge()
        webView.addJavascriptInterface(jsBridge, "BeatVizAndroid")
        webView.loadUrl("file:///android_asset/www/index.html")
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}
