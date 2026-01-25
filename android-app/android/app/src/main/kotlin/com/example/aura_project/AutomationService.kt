package com.example.aura_project

import android.accessibilityservice.AccessibilityService
import android.content.ClipboardManager
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.*

/**
 * Core Accessibility Service for YUSR Mobile Automation
 * 
 * Capabilities:
 * - Captures the SYSTEM's currently active app UI (not just Flutter app)
 * - Parses accessibility tree into JSON
 * - Sends UI tree to backend every 2 seconds
 * - Executes real accessibility actions (click, type, scroll, etc.)
 * - Supports global actions (HOME, BACK, RECENTS)
 */

// Extension function to get unique ID for node
private fun AccessibilityNodeInfo.uniqueId(): String {
    return "${this.viewIdResourceName}_${this.hashCode()}"
}
class AutomationService : AccessibilityService() {

    companion object {
        var instance: AutomationService? = null
        private const val TAG = "AutomationService"
        private const val BACKEND_URL = "http://localhost:8000"
        private const val DEVICE_ID = "android_device_1"
        private const val UI_SEND_INTERVAL_MS = 2000L
        
        fun isServiceEnabled(context: Context): Boolean {
            val enabledServices = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            )
            return enabledServices?.contains(context.packageName) == true
        }
    }

    private var uiBroadcastJob: Job? = null
    private var lastUiHash: String = ""
    private var elementCounter = 1

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.d(TAG, "✅ AutomationService connected")
        
        // Start UI tree broadcasting
        startUIBroadcasting()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        
        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                Log.d(TAG, "🔄 Window changed: ${event.packageName}")
                // UI changed, next broadcast will capture it
            }
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED -> {
                Log.d(TAG, "🔄 Content changed: ${event.packageName}")
                // Content updated
            }
        }
    }

    override fun onInterrupt() {
        Log.d(TAG, "⚠️ Service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "🛑 Service destroyed")
        stopUIBroadcasting()
        instance = null
    }

    /**
     * Start broadcasting UI tree to backend
     */
    private fun startUIBroadcasting() {
        if (uiBroadcastJob != null) return
        
        Log.d(TAG, "📡 Starting UI tree broadcast...")
        
        uiBroadcastJob = CoroutineScope(Dispatchers.IO).launch {
            while (isActive) {
                try {
                    val rootNode = rootInActiveWindow
                    if (rootNode != null) {
                        captureAndSendUITree(rootNode)
                    }
                    delay(UI_SEND_INTERVAL_MS)
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Error in broadcast: ${e.message}")
                    delay(5000)
                }
            }
        }
    }

    /**
     * Stop UI tree broadcasting
     */
    private fun stopUIBroadcasting() {
        Log.d(TAG, "🛑 Stopping UI broadcast...")
        uiBroadcastJob?.cancel()
        uiBroadcastJob = null
    }

    /**
     * Capture system UI tree and send to backend
     */
    private suspend fun captureAndSendUITree(rootNode: AccessibilityNodeInfo) {
        try {
            elementCounter = 1
            val uiJson = captureAccessibilityTree(rootNode)
            val uiHash = uiJson.toString().hashCode().toString()
            
            // Only send if UI changed (reduce spam)
            if (uiHash == lastUiHash) return
            lastUiHash = uiHash
            
            Log.d(TAG, "📤 Sending UI tree...")
            Log.d(TAG, "   App: ${uiJson.optString("app_name")}")
            Log.d(TAG, "   Screen: ${uiJson.optString("screen_name")}")
            Log.d(TAG, "   Elements: ${uiJson.optJSONArray("elements")?.length() ?: 0}")
            
            sendToBackend(uiJson)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error capturing UI: ${e.message}", e)
        }
    }

    /**
     * Recursively capture accessibility tree into JSON
     */
    private fun captureAccessibilityTree(node: AccessibilityNodeInfo?): JSONObject {
        if (node == null) {
            return JSONObject().apply {
                put("screen_id", "screen_${System.currentTimeMillis()}")
                put("device_id", DEVICE_ID)
                put("app_name", "Unknown")
                put("screen_name", "Unknown")
                put("elements", JSONArray())
                put("timestamp", System.currentTimeMillis())
                put("screen_width", 1080)
                put("screen_height", 2340)
            }
        }
        
        val elements = JSONArray()
        val visitedIds = mutableSetOf<String>()
        
        // Get app package name
        val appName = node.packageName?.toString() ?: "unknown"
        val appLabel = getAppLabel(appName)
        
        // Traverse tree
        traverseAndCollect(node, elements, visitedIds)
        
        return JSONObject().apply {
            put("screen_id", "screen_${System.currentTimeMillis()}")
            put("device_id", DEVICE_ID)
            put("app_name", appLabel)
            put("app_package", appName)
            put("screen_name", getCurrentActivityName())
            put("elements", elements)
            put("timestamp", System.currentTimeMillis())
            put("screen_width", 1080)
            put("screen_height", 2340)
        }
    }

    /**
     * Recursively traverse accessibility tree
     */
    private fun traverseAndCollect(
        node: AccessibilityNodeInfo,
        elements: JSONArray,
        visitedIds: MutableSet<String>
    ) {
        // Avoid infinite loops
        val nodeId = node.uniqueId()
        if (nodeId in visitedIds) return
        visitedIds.add(nodeId)
        
        // Only include visible, interactive elements
        if (node.isVisibleToUser && (node.isClickable || node.isEditable || node.isScrollable)) {
            val element = JSONObject().apply {
                put("element_id", elementCounter++)
                put("text", node.text?.toString() ?: "")
                put("resource_id", node.viewIdResourceName ?: "")
                put("class", node.className?.toString() ?: "")
                put("content_description", node.contentDescription?.toString() ?: "")
                put("clickable", node.isClickable)
                put("editable", node.isEditable)
                put("scrollable", node.isScrollable)
                put("focused", node.isFocused)
                put("password", node.isPassword)
            }
            elements.put(element)
        }
        
        // Recurse to children
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            traverseAndCollect(child, elements, visitedIds)
        }
    }

    /**
     * Send UI tree to backend
     */
    private suspend fun sendToBackend(uiJson: JSONObject) {
        withContext(Dispatchers.IO) {
            try {
                val url = URL("$BACKEND_URL/device/$DEVICE_ID/ui-tree")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Accept", "application/json")
                connection.doOutput = true
                connection.connectTimeout = 5000
                connection.readTimeout = 5000
                
                val outputStream = connection.outputStream
                outputStream.write(uiJson.toString().toByteArray(Charsets.UTF_8))
                outputStream.close()
                
                val responseCode = connection.responseCode
                if (responseCode != HttpURLConnection.HTTP_OK && responseCode != HttpURLConnection.HTTP_CREATED) {
                    Log.w(TAG, "⚠️ Server returned: $responseCode")
                }
                connection.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "❌ Failed to send UI tree: ${e.message}")
            }
        }
    }

    /**
     * Get human-readable app label
     */
    private fun getAppLabel(packageName: String): String {
        return when {
            packageName.contains("gmail") -> "Gmail"
            packageName.contains("whatsapp") -> "WhatsApp"
            packageName.contains("messenger") -> "Messenger"
            packageName.contains("aura_project") -> "Aura App"
            packageName.contains("android.launcher") -> "Launcher"
            else -> packageName.split(".").last()
        }
    }

    /**
     * Get current activity name
     */
    private fun getCurrentActivityName(): String {
        val rootNode = rootInActiveWindow ?: return "Unknown"
        return rootNode.text?.toString() ?: rootNode.contentDescription?.toString() ?: "Unknown Screen"
    }

    /**
     * Execute an action (called by backend)
     */
    fun executeAction(
        actionType: String,
        elementId: Int?,
        text: String?,
        direction: String?,
        globalAction: String?
    ): Boolean {
        return try {
            when (actionType) {
                "click" -> performClickById(elementId)
                "type" -> performTypeText(elementId, text ?: "")
                "scroll" -> performScroll(direction ?: "down")
                "global_action" -> performGlobalAction(globalAction ?: "")
                "navigate_home" -> navigateToHome()
                "navigate_back" -> navigateBack()
                "wait" -> { Thread.sleep((text?.toLongOrNull() ?: 1000)); true }
                else -> false
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error executing action: ${e.message}", e)
            false
        }
    }

    /**
     * Click element by ID
     */
    private fun performClickById(elementId: Int?): Boolean {
        if (elementId == null) return false
        
        val rootNode = rootInActiveWindow ?: return false
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        collectNodesByIndex(rootNode, nodes)
        
        if (elementId - 1 < nodes.size) {
            val node = nodes[elementId - 1]
            if (node.isClickable) {
                Log.d(TAG, "👆 Clicking element $elementId")
                return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            }
        }
        
        return false
    }

    /**
     * Type text into element
     */
    private fun performTypeText(elementId: Int?, text: String): Boolean {
        if (elementId == null) return false
        
        val rootNode = rootInActiveWindow ?: return false
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        collectNodesByIndex(rootNode, nodes)
        
        if (elementId - 1 < nodes.size) {
            val node = nodes[elementId - 1]
            if (node.isEditable) {
                Log.d(TAG, "⌨️ Typing into element $elementId: '$text'")
                
                // Use clipboard method for reliability
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("text", text)
                clipboard.setPrimaryClip(clip)
                
                node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
                Thread.sleep(200)
                return node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
            }
        }
        
        return false
    }

    /**
     * Scroll in direction
     */
    private fun performScroll(direction: String): Boolean {
        val rootNode = rootInActiveWindow ?: return false
        
        Log.d(TAG, "📜 Scrolling $direction")
        
        val forwardDirection = when (direction.lowercase()) {
            "down", "right" -> true
            else -> false
        }
        
        return rootNode.performAction(
            if (forwardDirection) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        )
    }

    /**
     * Navigate to home screen using multiple methods
     */
    private fun navigateToHome(): Boolean {
        Log.d(TAG, "🏠 Navigating to home screen...")
        
        try {
            // Method 1: Use Android Intent to launch home screen
            val intent = Intent(Intent.ACTION_MAIN)
            intent.addCategory(Intent.CATEGORY_HOME)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
            startActivity(intent)
            
            // Method 2: Use system global action as backup
            Thread.sleep(500)
            performGlobalAction(GLOBAL_ACTION_HOME)
            
            Log.d(TAG, "✅ Successfully navigated to home screen")
            return true
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error navigating to home: ${e.message}")
            return false
        }
    }

    /**
     * Navigate back using system back action
     */
    private fun navigateBack(): Boolean {
        Log.d(TAG, "⬅️ Navigating back...")
        
        try {
            // Use system back action
            return performGlobalAction(GLOBAL_ACTION_BACK)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error navigating back: ${e.message}")
            return false
        }
    }

    /**
     * Perform system action
     */
    private fun performGlobalAction(action: String): Boolean {
        Log.d(TAG, "🏠 Global action: $action")
        
        return when (action.uppercase()) {
            "HOME" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "BACK" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "RECENTS" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            "POWER" -> performGlobalAction(GLOBAL_ACTION_LOCK_SCREEN)
            else -> false
        }
    }

    /**
     * Collect nodes by index for easy access
     */
    private fun collectNodesByIndex(node: AccessibilityNodeInfo?, list: MutableList<AccessibilityNodeInfo>) {
        if (node == null) return
        if (node.isVisibleToUser && (node.isClickable || node.isEditable)) {
            list.add(node)
        }
        for (i in 0 until node.childCount) {
            collectNodesByIndex(node.getChild(i), list)
        }
    }
}
