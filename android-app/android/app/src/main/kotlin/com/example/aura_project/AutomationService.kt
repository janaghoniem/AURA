package com.example.aura_project

import android.accessibilityservice.AccessibilityService
import android.content.ClipboardManager
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * CRITICAL FIX: AutomationService with synchronized UI tree and click handling
 * 
 * THE PROBLEM: UI tree element IDs didn't match click positions!
 * Element 7 showed "Gmail" but clicking it opened YouTube instead.
 * 
 * ROOT CAUSE: traverseAndCollect() and collectNodesByIndex() used DIFFERENT
 * traversal orders, causing element_id mismatch.
 * 
 * SOLUTION: Store nodes in a list during UI tree capture, then use that
 * SAME list for clicking. This guarantees element_id consistency.
 */

private fun AccessibilityNodeInfo.uniqueId(): String {
    return "${this.viewIdResourceName}_${this.hashCode()}"
}

class AutomationService : AccessibilityService() {

    companion object {
        var instance: AutomationService? = null
        private const val TAG = "AutomationService"
        private const val BACKEND_URL = "http://10.0.2.2:8000"
        private const val DEVICE_ID = "android_device_1"
        private const val UI_SEND_INTERVAL_MS = 2000L
        private const val ACTION_CHECK_INTERVAL_MS = 500L
        
        fun isServiceEnabled(context: Context): Boolean {
            val enabledServices = android.provider.Settings.Secure.getString(
                context.contentResolver,
                android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            )
            return enabledServices?.contains(context.packageName) == true
        }
    }

    private var uiBroadcastJob: Job? = null
    private var actionExecutorJob: Job? = null
    private var lastUiHash: String = ""
    private var elementCounter = 1
    
    // ✅ CRITICAL FIX: Store captured nodes in the SAME order as UI tree
    private var lastCapturedNodes: MutableList<AccessibilityNodeInfo> = mutableListOf()

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.d(TAG, "✅ AutomationService connected")
        
        startUIBroadcasting()
        startActionExecutor()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        
        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                Log.d(TAG, "🔄 Window changed: ${event.packageName}")
            }
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED -> {
                // Don't log content changes - too verbose
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
        stopActionExecutor()
        instance = null
    }

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

    private fun stopUIBroadcasting() {
        Log.d(TAG, "🛑 Stopping UI broadcast...")
        uiBroadcastJob?.cancel()
        uiBroadcastJob = null
    }

    private fun startActionExecutor() {
        if (actionExecutorJob != null) return
        
        Log.d(TAG, "⚡ Starting action executor...")
        
        actionExecutorJob = CoroutineScope(Dispatchers.IO).launch {
            while (isActive) {
                try {
                    val actions = fetchPendingActions()
                    
                    if (actions.isNotEmpty()) {
                        Log.d(TAG, "📥 Got ${actions.size} actions to execute")
                        
                        for (action in actions) {
                            Log.d(TAG, "🎯 Executing action: ${action.optString("action_type")}")
                            executeActionFromJson(action)
                            delay(500)
                        }
                    }
                    
                    delay(ACTION_CHECK_INTERVAL_MS)
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Error in action executor: ${e.message}")
                    delay(2000)
                }
            }
        }
    }

    private fun stopActionExecutor() {
        Log.d(TAG, "🛑 Stopping action executor...")
        actionExecutorJob?.cancel()
        actionExecutorJob = null
    }

    private fun fetchPendingActions(): List<JSONObject> {
        try {
            val url = URL("$BACKEND_URL/device/$DEVICE_ID/pending-actions")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 2000
            connection.readTimeout = 2000
            
            val responseCode = connection.responseCode
            if (responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                val responseJson = JSONObject(response)
                val actionsArray = responseJson.optJSONArray("actions") ?: JSONArray()
                
                val result = mutableListOf<JSONObject>()
                for (i in 0 until actionsArray.length()) {
                    result.add(actionsArray.getJSONObject(i))
                }
                
                connection.disconnect()
                return result
            }
            
            connection.disconnect()
        } catch (e: Exception) {
            // Silent fail - polling will retry
        }
        
        return emptyList()
    }

    private fun executeActionFromJson(actionJson: JSONObject) {
        val actionType = actionJson.optString("action_type", "")
        
        Log.d(TAG, "🎬 executeActionFromJson: type=$actionType")
        
        val success = when (actionType) {
            "click" -> {
                val elementId = actionJson.optInt("element_id", -1)
                performClickById(elementId)
            }
            "type" -> {
                val elementId = actionJson.optInt("element_id", -1)
                val text = actionJson.optString("text", "")
                performTypeText(elementId, text)
            }
            "scroll" -> {
                val direction = actionJson.optString("direction", "down")
                performScroll(direction)
            }
            "global_action" -> {
                val globalAction = actionJson.optString("global_action", "")
                Log.d(TAG, "🔘 GLOBAL ACTION: $globalAction")
                performGlobalAction(globalAction)
            }
            "navigate_home", "goToHome" -> {
                Log.d(TAG, "🏠 NAVIGATE HOME")
                navigateToHome()
            }
            "navigate_back" -> {
                Log.d(TAG, "⬅️ NAVIGATE BACK")
                navigateBack()
            }
            "wait" -> {
                val duration = actionJson.optInt("duration", 1000)
                Thread.sleep(duration.toLong())
                true
            }
            else -> {
                Log.w(TAG, "❓ Unknown action type: $actionType")
                false
            }
        }
        
        Log.d(TAG, if (success) "✅ Action executed: $actionType" else "❌ Action failed: $actionType")
    }

    private suspend fun captureAndSendUITree(rootNode: AccessibilityNodeInfo) {
        try {
            elementCounter = 1
            val uiJson = captureAccessibilityTree(rootNode)
            val uiHash = uiJson.toString().hashCode().toString()
            
            if (uiHash == lastUiHash) return
            lastUiHash = uiHash
            
            val elemCount = uiJson.optJSONArray("elements")?.length() ?: 0
            
            Log.d(TAG, "📤 Sending UI tree...")
            Log.d(TAG, "   App: ${uiJson.optString("app_name")}")
            Log.d(TAG, "   Package: ${uiJson.optString("app_package")}")
            Log.d(TAG, "   Elements: $elemCount")
            
            sendToBackend(uiJson)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error capturing UI: ${e.message}", e)
        }
    }

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
        
        val appPackage = node.packageName?.toString() ?: "unknown"
        val appLabel = getAppLabel(appPackage)
        
        // ✅ CRITICAL FIX: Clear and rebuild node list in sync with UI tree
        lastCapturedNodes.clear()
        elementCounter = 1
        traverseAndCollect(node, elements, visitedIds, lastCapturedNodes)
        
        Log.d(TAG, "✅ Captured ${lastCapturedNodes.size} nodes for clicking")
        
        return JSONObject().apply {
            put("screen_id", "screen_${System.currentTimeMillis()}")
            put("device_id", DEVICE_ID)
            put("app_name", appLabel)
            put("app_package", appPackage)
            put("screen_name", getCurrentActivityName(node))
            put("elements", elements)
            put("timestamp", System.currentTimeMillis())
            put("screen_width", 1080)
            put("screen_height", 2340)
        }
    }

    private fun traverseAndCollect(
        node: AccessibilityNodeInfo,
        elements: JSONArray,
        visitedIds: MutableSet<String>,
        nodeList: MutableList<AccessibilityNodeInfo>  // ✅ NEW: Store nodes here
    ) {
        val nodeId = node.uniqueId()
        if (nodeId in visitedIds) return
        visitedIds.add(nodeId)
        
        if (node.isVisibleToUser) {
            val className = node.className?.toString() ?: ""
            val elementType = inferElementType(className)
            
            // Skip noise elements
            val shouldSkip = className.contains("AccessibilityNodeProvider") ||
                           className.endsWith("$0") ||
                           (className.contains("View") && 
                            node.text.isNullOrEmpty() && 
                            node.contentDescription.isNullOrEmpty() &&
                            !node.isClickable &&
                            !node.isScrollable)
            
            if (!shouldSkip) {
                // ✅ CRITICAL: Add node to list FIRST
                nodeList.add(node)
                
                val currentElementId = elementCounter++
                
                val element = JSONObject().apply {
                    put("element_id", currentElementId)
                    put("text", node.text?.toString() ?: "")
                    put("content_description", node.contentDescription?.toString() ?: "")
                    put("resource_id", node.viewIdResourceName ?: "")
                    put("class", className)
                    put("type", elementType)
                    put("clickable", node.isClickable)
                    put("editable", node.isEditable)
                    put("scrollable", node.isScrollable)
                    put("focusable", node.isFocusable)
                    put("focused", node.isFocused)
                    put("enabled", node.isEnabled)
                    put("password", node.isPassword)
                }
                elements.put(element)
                
                // Log for verification
                if (node.isClickable || node.text?.isNotEmpty() == true) {
                    Log.v(TAG, "[$currentElementId] ${node.text} | ${node.contentDescription}")
                }
            }
        }
        
        // Recursively traverse all children
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            traverseAndCollect(child, elements, visitedIds, nodeList)
        }
    }
    
    private fun inferElementType(className: String): String {
        return when {
            className.contains("Button") || className.contains("ImageButton") -> "button"
            className.contains("EditText") || className.contains("TextInputLayout") -> "textfield"
            className.contains("CheckBox") -> "checkbox"
            className.contains("RadioButton") -> "radio"
            className.contains("Switch") || className.contains("ToggleButton") -> "switch"
            className.contains("ImageView") || className.contains("Image") -> "image"
            className.contains("Icon") -> "icon"
            className.contains("TextV") || className.contains("Text") -> "text"
            className.contains("Spinner") -> "spinner"
            className.contains("SeekBar") -> "slider"
            className.contains("ProgressBar") -> "progress"
            className.contains("ScrollView") || className.contains("RecyclerView") || className.contains("ListView") -> "scroll"
            className.contains("TabLayout") || className.contains("TabBar") -> "tabbar"
            className.contains("BottomNavigationView") -> "bottomnav"
            className.contains("DrawerLayout") -> "drawer"
            className.contains("Toolbar") || className.contains("ActionBar") -> "toolbar"
            else -> "element"
        }
    }

    private suspend fun sendToBackend(uiJson: JSONObject) {
        withContext(Dispatchers.IO) {
            try {
                val url = URL("$BACKEND_URL/device/$DEVICE_ID/ui-tree")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true
                connection.connectTimeout = 5000
                connection.readTimeout = 5000
                
                connection.outputStream.write(uiJson.toString().toByteArray(Charsets.UTF_8))
                connection.outputStream.close()
                
                val responseCode = connection.responseCode
                if (responseCode == HttpURLConnection.HTTP_OK || responseCode == HttpURLConnection.HTTP_CREATED) {
                    Log.d(TAG, "✅ UI tree sent")
                }
                connection.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "❌ Failed to send UI tree: ${e.message}")
            }
        }
    }

    private fun getAppLabel(packageName: String): String {
        return when {
            packageName.contains("gmail") -> "Gmail"
            packageName.contains("chrome") -> "Chrome"
            packageName.contains("youtube") -> "YouTube"
            packageName.contains("messages") || packageName.contains("messaging") -> "Messages"
            packageName.contains("aura_project") || packageName.contains("aura") -> "Aura App"
            packageName.contains("launcher") -> "Android Launcher"
            else -> packageName.split(".").lastOrNull() ?: "Unknown"
        }
    }

    private fun getCurrentActivityName(node: AccessibilityNodeInfo): String {
        node.text?.toString()?.let { if (it.isNotEmpty()) return it }
        node.contentDescription?.toString()?.let { if (it.isNotEmpty()) return it }
        
        val packageName = node.packageName?.toString() ?: ""
        return getAppLabel(packageName) + " Screen"
    }

    // ============================================================================
    // ACTION EXECUTION METHODS - WITH CRITICAL FIX
    // ============================================================================

    private fun performClickById(elementId: Int?): Boolean {
        if (elementId == null || elementId < 1) {
            Log.e(TAG, "❌ Invalid element ID: $elementId")
            return false
        }
        
        Log.d(TAG, "👆 Attempting click on element $elementId")
        Log.d(TAG, "   Available nodes: ${lastCapturedNodes.size}")
        
        // ✅ CRITICAL FIX: Use the SAME list that built the UI tree!
        if (elementId - 1 < lastCapturedNodes.size) {
            val node = lastCapturedNodes[elementId - 1]
            
            val text = node.text?.toString() ?: ""
            val desc = node.contentDescription?.toString() ?: ""
            val className = node.className?.toString() ?: ""
            
            Log.d(TAG, "✅ Found element $elementId:")
            Log.d(TAG, "   Text: '$text'")
            Log.d(TAG, "   Desc: '$desc'")
            Log.d(TAG, "   Class: $className")
            Log.d(TAG, "   Clickable: ${node.isClickable}")
            
            if (node.isClickable) {
                val success = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                Log.d(TAG, "👆 Click result: $success")
                return success
            } else {
                Log.w(TAG, "⚠️ Element $elementId is not clickable, trying anyway...")
                // Try clicking anyway - sometimes Android lies about clickability
                val success = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                Log.d(TAG, "👆 Force click result: $success")
                return success
            }
        } else {
            Log.e(TAG, "❌ Element $elementId out of bounds (max: ${lastCapturedNodes.size})")
            return false
        }
    }

    private fun performTypeText(elementId: Int?, text: String): Boolean {
        if (elementId == null || text.isEmpty()) {
            Log.e(TAG, "❌ Invalid type parameters: elementId=$elementId, text='$text'")
            return false
        }
        
        Log.d(TAG, "⌨️ Typing '$text' into element $elementId")
        
        if (elementId - 1 < lastCapturedNodes.size) {
            val node = lastCapturedNodes[elementId - 1]
            
            Log.d(TAG, "   Found element: ${node.text}")
            Log.d(TAG, "   Editable: ${node.isEditable}, Focusable: ${node.isFocusable}")
            
            if (node.isEditable || node.isFocusable) {
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("text", text)
                clipboard.setPrimaryClip(clip)
                
                node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
                Thread.sleep(200)
                val success = node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
                Log.d(TAG, "⌨️ Type result: $success")
                return success
            } else {
                Log.w(TAG, "⚠️ Element is not editable/focusable")
            }
        } else {
            Log.e(TAG, "❌ Element $elementId out of bounds")
        }
        
        return false
    }

    private fun performScroll(direction: String): Boolean {
        Log.d(TAG, "📜 Scrolling $direction")
        
        val rootNode = rootInActiveWindow ?: return false
        
        val forwardDirection = direction.lowercase() in listOf("down", "right")
        
        return rootNode.performAction(
            if (forwardDirection) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD 
            else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        )
    }

    private fun navigateToHome(): Boolean {
        Log.d(TAG, "🏠 ========== NAVIGATE TO HOME ==========")
        
        try {
            val intent = Intent(Intent.ACTION_MAIN)
            intent.addCategory(Intent.CATEGORY_HOME)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            startActivity(intent)
            
            Log.d(TAG, "✅ Sent HOME intent")
            
            Thread.sleep(300)
            val success = performGlobalAction(GLOBAL_ACTION_HOME)
            
            Log.d(TAG, "✅ HOME global action result: $success")
            Log.d(TAG, "🏠 ========== HOME NAVIGATION COMPLETE ==========")
            
            return true
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error navigating home: ${e.message}", e)
            return false
        }
    }

    private fun navigateBack(): Boolean {
        Log.d(TAG, "⬅️ ========== NAVIGATE BACK ==========")
        
        try {
            val success = performGlobalAction(GLOBAL_ACTION_BACK)
            Log.d(TAG, "✅ BACK result: $success")
            Log.d(TAG, "⬅️ ========== BACK NAVIGATION COMPLETE ==========")
            return success
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error navigating back: ${e.message}")
            return false
        }
    }

    private fun performGlobalAction(action: String): Boolean {
        Log.d(TAG, "🔘 performGlobalAction: $action")
        
        val actionCode = when (action.uppercase()) {
            "HOME" -> GLOBAL_ACTION_HOME
            "BACK" -> GLOBAL_ACTION_BACK
            "RECENTS" -> GLOBAL_ACTION_RECENTS
            "POWER" -> GLOBAL_ACTION_LOCK_SCREEN
            else -> {
                Log.w(TAG, "❓ Unknown global action: $action")
                return false
            }
        }
        
        val success = performGlobalAction(actionCode)
        Log.d(TAG, "🔘 Global action $action result: $success")
        return success
    }
}