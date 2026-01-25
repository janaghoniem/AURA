package com.example.aura_project

import android.view.accessibility.AccessibilityNodeInfo
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject

/**
 * UITreeParser - Converts AccessibilityNodeInfo tree to Semantic JSON
 * 
 * Converts the raw Android accessibility tree into a compact semantic representation
 * that can be sent to the LLM. This reduces token usage significantly.
 * 
 * Example output:
 * {
 *   "screen_id": "screen_123456",
 *   "app_name": "Gmail",
 *   "elements": [
 *     {"element_id": 1, "type": "button", "text": "Send", "clickable": true},
 *     {"element_id": 2, "type": "textfield", "hint_text": "To:", "focusable": true}
 *   ]
 * }
 */
class UITreeParser(
    private val deviceId: String = "default_device",
    private val screenWidth: Int = 1080,
    private val screenHeight: Int = 2340
) {
    companion object {
        private const val TAG = "UITreeParser"
    }

    /**
     * Parse the entire accessibility tree into a semantic representation
     */
    fun parseAccessibilityTree(rootNode: AccessibilityNodeInfo?): JSONObject {
        if (rootNode == null) {
            Log.e(TAG, "Root node is null, cannot parse tree")
            return JSONObject()
        }

        val result = JSONObject()
        result.put("device_id", deviceId)
        result.put("screen_width", screenWidth)
        result.put("screen_height", screenHeight)
        result.put("timestamp", System.currentTimeMillis() / 1000.0)
        
        // Get app info from root node
        val appPackage = rootNode.packageName?.toString() ?: "unknown"
        val appName = getAppNameFromPackage(appPackage)
        result.put("app_package", appPackage)
        result.put("app_name", appName)
        result.put("screen_name", getActivityName(rootNode) ?: appName)

        // Parse all elements
        val elementsArray = JSONArray()
        val elementMap = mutableMapOf<Int, JSONObject>()
        var elementCounter = 0

        traverseTree(rootNode, elementsArray, elementMap, rootNode, elementCounter)

        // Build parent-child relationships
        buildRelationships(elementsArray, elementMap)

        result.put("elements", elementsArray)
        result.put("screen_id", "screen_${System.currentTimeMillis()}")

        Log.d(TAG, "✅ Parsed tree with ${elementsArray.length()} elements")
        return result
    }

    /**
     * Recursive traversal of accessibility tree
     */
    private fun traverseTree(
        node: AccessibilityNodeInfo,
        elementsArray: JSONArray,
        elementMap: MutableMap<Int, JSONObject>,
        rootNode: AccessibilityNodeInfo,
        startCounter: Int
    ): Int {
        var counter = startCounter

        // Skip invisible/gone elements
        if (node.isVisibleToUser == false) {
            return counter
        }

        // Create element JSON
        val elementJson = JSONObject()
        elementJson.put("element_id", counter)

        // Type (infer from class name)
        val className = node.className?.toString() ?: ""
        val elementType = inferElementType(className, node)
        elementJson.put("type", elementType)

        // Text content
        val text = node.text?.toString()
        if (!text.isNullOrBlank()) {
            elementJson.put("text", text)
        }

        // Content description (accessibility label)
        val description = node.contentDescription?.toString()
        if (!description.isNullOrBlank()) {
            elementJson.put("content_description", description)
        }

        // Hint text (for input fields)
        val hint = node.hintText?.toString()
        if (!hint.isNullOrBlank()) {
            elementJson.put("hint_text", hint)
        }

        // Interactive properties
        elementJson.put("clickable", node.isClickable)
        elementJson.put("focusable", node.isFocusable)
        elementJson.put("scrollable", node.isScrollable)
        elementJson.put("enabled", node.isEnabled)
        elementJson.put("visibility", if (node.isVisibleToUser) "visible" else "gone")

        // Bounds (optional - can be expensive to include)
        val bounds = android.graphics.Rect()
        node.getBoundsInScreen(bounds)
        if (bounds.width() > 0 && bounds.height() > 0) {
            val boundsJson = JSONObject()
            boundsJson.put("left", bounds.left)
            boundsJson.put("top", bounds.top)
            boundsJson.put("right", bounds.right)
            boundsJson.put("bottom", bounds.bottom)
            elementJson.put("bounds", boundsJson)
        }

        // Resource ID
        val resourceId = node.viewIdResourceName
        if (resourceId != null && !resourceId.isEmpty()) {
            elementJson.put("resource_id", resourceId)
        }

        // Class name for debugging
        if (!className.isEmpty()) {
            elementJson.put("class_name", className)
        }

        elementJson.put("parent_id", -1) // Will be set later
        elementJson.put("child_ids", JSONArray())

        elementsArray.put(elementJson)
        elementMap[counter] = elementJson

        counter++

        // Traverse children
        val childCount = node.childCount
        val childStartCounter = counter
        for (i in 0 until childCount) {
            val child = node.getChild(i)
            if (child != null) {
                counter = traverseTree(child, elementsArray, elementMap, rootNode, counter)
                child.recycle()
            }
        }

        // Set parent-child relationships for this node's children
        if (counter > childStartCounter) {
            val parentId = elementsArray.getJSONObject(elementsArray.length() - (counter - childStartCounter) - 1).getInt("element_id")
            for (j in childStartCounter until counter) {
                if (j < elementsArray.length()) {
                    val childJson = elementsArray.getJSONObject(j)
                    childJson.put("parent_id", parentId)
                }
            }
        }

        return counter
    }

    /**
     * Build parent-child relationships after traversal
     */
    private fun buildRelationships(
        elementsArray: JSONArray,
        elementMap: MutableMap<Int, JSONObject>
    ) {
        // Initialize child_ids arrays
        for (i in 0 until elementsArray.length()) {
            val elem = elementsArray.getJSONObject(i)
            elem.put("child_ids", JSONArray())
        }

        // Link children to parents
        for (i in 0 until elementsArray.length()) {
            val elem = elementsArray.getJSONObject(i)
            val parentId = elem.getInt("parent_id")
            if (parentId >= 0 && parentId < elementsArray.length()) {
                val parent = elementsArray.getJSONObject(parentId)
                val childIds = parent.getJSONArray("child_ids")
                childIds.put(elem.getInt("element_id"))
            }
        }
    }

    /**
     * Infer element type from Android class name
     */
    private fun inferElementType(className: String, node: AccessibilityNodeInfo): String {
        return when {
            className.contains("Button") -> "button"
            className.contains("EditText") -> "textfield"
            className.contains("CheckBox") -> "checkbox"
            className.contains("RadioButton") -> "radio"
            className.contains("Switch") -> "switch"
            className.contains("ImageView") -> "image"
            className.contains("ProgressBar") -> "progressbar"
            className.contains("SeekBar") -> "seekbar"
            className.contains("Spinner") -> "spinner"
            className.contains("ListView") || className.contains("RecyclerView") -> "list"
            className.contains("ScrollView") -> "scrollview"
            className.contains("WebView") -> "webview"
            className.contains("TextView") -> "text"
            node.isClickable -> "clickable_element"
            node.isScrollable -> "scrollable_container"
            else -> "container"
        }
    }

    /**
     * Get app name from package name (simplified)
     */
    private fun getAppNameFromPackage(packageName: String): String {
        return when (packageName) {
            "com.google.android.gm" -> "Gmail"
            "com.google.android.gm.lite" -> "Gmail Lite"
            "com.android.chrome" -> "Chrome"
            "org.mozilla.firefox" -> "Firefox"
            "com.google.android.apps.maps" -> "Google Maps"
            "com.whatsapp" -> "WhatsApp"
            "com.instagram.android" -> "Instagram"
            "com.facebook.katana" -> "Facebook"
            "com.twitter.android" -> "Twitter"
            "com.android.messaging" -> "Messages"
            "com.android.contacts" -> "Contacts"
            "com.android.calendar" -> "Calendar"
            "com.spotify.music" -> "Spotify"
            "com.netflix.mediaclient" -> "Netflix"
            "com.google.android.youtube" -> "YouTube"
            else -> packageName.split(".").lastOrNull() ?: "Unknown"
        }
    }

    /**
     * Try to get the activity/screen name from the node
     */
    private fun getActivityName(node: AccessibilityNodeInfo): String? {
        // This would require additional context; for now return null
        // In production, you'd use AccessibilityEvent or other mechanisms
        return null
    }

    /**
     * Convert parsed tree to a compact string representation for LLM
     */
    fun treeToSemanticString(treeJson: JSONObject): String {
        val lines = mutableListOf<String>()
        
        lines.add("Screen: ${treeJson.optString("screen_name", treeJson.optString("app_name"))}")
        lines.add("App: ${treeJson.optString("app_package")}")
        lines.add("")

        val elements = treeJson.optJSONArray("elements") ?: JSONArray()
        for (i in 0 until elements.length()) {
            val elem = elements.getJSONObject(i)
            
            val visibility = elem.optString("visibility", "visible")
            if (visibility != "visible") continue

            val id = elem.getInt("element_id")
            val type = elem.optString("type", "element")
            val text = elem.optString("text", "")
            val hint = elem.optString("hint_text", "")
            val clickable = elem.optBoolean("clickable")
            val focusable = elem.optBoolean("focusable")

            // Format: [id] TYPE "text" | hint
            val display = when {
                text.isNotEmpty() -> "\"$text\""
                hint.isNotEmpty() -> "[hint: $hint]"
                else -> "(empty)"
            }

            val flags = mutableListOf<String>()
            if (clickable) flags.add("CLICKABLE")
            if (focusable) flags.add("FOCUSABLE")

            val flagsStr = if (flags.isNotEmpty()) " [${flags.joinToString(", ")}]" else ""
            lines.add("[$id] ${type.uppercase()} $display$flagsStr")
        }

        return lines.joinToString("\n")
    }
}
