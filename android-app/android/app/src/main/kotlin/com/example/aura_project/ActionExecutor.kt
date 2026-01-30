package com.example.aura_project

import android.accessibilityservice.AccessibilityService
import android.content.ClipboardManager
import android.content.ClipData
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONObject
import kotlin.math.abs

/**
 * ActionExecutor - Executes atomic UI actions (primitives)
 * 
 * The 5 core primitives:
 * 1. click(element_id) - Click a button/clickable element
 * 2. type(element_id, text) - Type text into a field
 * 3. scroll(direction) - Scroll in a direction (up/down/left/right)
 * 4. wait(duration_ms) - Wait for N milliseconds
 * 5. global_action(action_type) - HOME, BACK, RECENTS, POWER, etc.
 * 
 * Handles:
 * - Finding elements by ID in the accessibility tree
 * - Executing actions with proper error handling
 * - Retrying failed actions (delegated to caller via result)
 * - Returning action results with new UI state
 */
class ActionExecutor(
    private val service: AccessibilityService,
    private val uiTreeParser: UITreeParser
) {
    companion object {
        private const val TAG = "ActionExecutor"
        private const val PASTE_DELAY_MS = 300L
        private const val ACTION_EXECUTE_DELAY_MS = 500L
    }

    /**
     * Main execution entry point
     * Takes a JSON action and executes it
     * Returns the result as a JSON object
     */
    fun executeAction(actionJson: JSONObject): JSONObject {
        val startTime = System.currentTimeMillis()
        val actionId = actionJson.optString("action_id", "unknown")
        val actionType = actionJson.optString("action_type", "unknown")

        Log.d(TAG, "🎯 Executing action: $actionType (ID: $actionId)")

        val result = JSONObject()
        result.put("action_id", actionId)

        try {
            val success = when (actionType) {
                "click" -> handleClick(actionJson)
                "type" -> handleType(actionJson)
                "scroll" -> handleScroll(actionJson)
                "wait" -> handleWait(actionJson)
                "global_action" -> handleGlobalAction(actionJson)
                "long_click" -> handleLongClick(actionJson)
                "double_click" -> handleDoubleClick(actionJson)
                else -> {
                    Log.w(TAG, "Unknown action type: $actionType")
                    false
                }
            }

            result.put("success", success)
            
            // Capture new UI state after action
            Thread.sleep(ACTION_EXECUTE_DELAY_MS)
            val newRootNode = service.rootInActiveWindow
            if (newRootNode != null) {
                val newTree = uiTreeParser.parseAccessibilityTree(newRootNode)
                result.put("new_tree", newTree)
            }

        } catch (e: Exception) {
            Log.e(TAG, "❌ Error executing action $actionType: ${e.message}", e)
            result.put("success", false)
            result.put("error", e.message)
        }

        val executionTime = System.currentTimeMillis() - startTime
        result.put("execution_time_ms", executionTime)
        
        Log.d(TAG, "✅ Action $actionType completed in ${executionTime}ms: ${result.optBoolean("success")}")
        return result
    }

    /**
     * PRIMITIVE 1: Click
     * Finds an element by ID and clicks it
     */
    private fun handleClick(actionJson: JSONObject): Boolean {
        val elementId = actionJson.optInt("element_id", -1)
        if (elementId < 0) {
            Log.e(TAG, "Click: Invalid element ID")
            return false
        }

        Log.d(TAG, "Click: Looking for element $elementId")
        val rootNode = service.rootInActiveWindow ?: return false
        
        val element = findElementById(rootNode, elementId)
        if (element == null) {
            Log.e(TAG, "Click: Element $elementId not found")
            return false
        }

        if (!element.isClickable) {
            Log.e(TAG, "Click: Element $elementId is not clickable")
            return false
        }

        Log.d(TAG, "Click: Performing click on element $elementId")
        return element.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    /**
     * PRIMITIVE 2: Type
     * Finds a text field by ID and types text into it
     * Uses clipboard to handle special characters
     */
    private fun handleType(actionJson: JSONObject): Boolean {
        val elementId = actionJson.optInt("element_id", -1)
        val text = actionJson.optString("text", "")

        if (elementId < 0 || text.isEmpty()) {
            Log.e(TAG, "Type: Invalid element ID or text")
            return false
        }

        Log.d(TAG, "Type: Looking for element $elementId")
        val rootNode = service.rootInActiveWindow ?: return false
        
        val element = findElementById(rootNode, elementId)
        if (element == null) {
            Log.e(TAG, "Type: Element $elementId not found")
            return false
        }

        if (!element.isFocusable) {
            Log.e(TAG, "Type: Element $elementId is not focusable")
            return false
        }

        Log.d(TAG, "Type: Typing '$text' into element $elementId")
        
        // Click to focus
        element.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        element.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        Thread.sleep(300)

        // Copy text to clipboard
        val clipboard = service.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("text", text)
        clipboard.setPrimaryClip(clip)
        
        Thread.sleep(PASTE_DELAY_MS)

        // Paste
        val pasteSuccess = element.performAction(AccessibilityNodeInfo.ACTION_PASTE)
        Thread.sleep(300)

        Log.d(TAG, "Type: Paste action result: $pasteSuccess")
        return pasteSuccess
    }

    /**
     * PRIMITIVE 3: Scroll
     * Scrolls in the specified direction on the current view
     * Note: Left/right scrolling is limited - primarily supports up/down
     */
    private fun handleScroll(actionJson: JSONObject): Boolean {
        val direction = actionJson.optString("direction", "down").lowercase()
        
        Log.d(TAG, "Scroll: Direction=$direction")

        val rootNode = service.rootInActiveWindow
        if (rootNode == null) {
            Log.e(TAG, "Scroll: Root node is null")
            return false
        }

        // Find scrollable container
        val scrollableNode = findFirstScrollableNode(rootNode)
        if (scrollableNode == null) {
            Log.w(TAG, "Scroll: No scrollable element found")
            return false
        }

        val action = when (direction) {
            "up", "left" -> AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
            "down", "right" -> AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
            else -> AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        }

        Log.d(TAG, "Scroll: Performing scroll action on scrollable element")
        return scrollableNode.performAction(action)
    }

    /**
     * PRIMITIVE 4: Wait
     * Simple delay to allow UI to update
     */
    private fun handleWait(actionJson: JSONObject): Boolean {
        val duration = actionJson.optInt("duration", 1000)
        
        Log.d(TAG, "Wait: Waiting ${duration}ms")
        Thread.sleep(duration.toLong())
        Log.d(TAG, "Wait: Done")
        return true
    }

    /**
     * PRIMITIVE 5: Global Action
     * Performs system-level actions: HOME, BACK, RECENTS, POWER, etc.
     */
    private fun handleGlobalAction(actionJson: JSONObject): Boolean {
        val globalActionStr = actionJson.optString("global_action", "BACK").uppercase()

        val action = when (globalActionStr) {
            "HOME" -> AccessibilityService.GLOBAL_ACTION_HOME
            "BACK" -> AccessibilityService.GLOBAL_ACTION_BACK
            "RECENTS" -> AccessibilityService.GLOBAL_ACTION_RECENTS
            "POWER" -> AccessibilityService.GLOBAL_ACTION_POWER_DIALOG
            else -> AccessibilityService.GLOBAL_ACTION_BACK
        }

        Log.d(TAG, "GlobalAction: Performing $globalActionStr")
        return service.performGlobalAction(action)
    }

    /**
     * BONUS: Long Click
     */
    private fun handleLongClick(actionJson: JSONObject): Boolean {
        val elementId = actionJson.optInt("element_id", -1)
        val duration = actionJson.optInt("duration", 1000)

        if (elementId < 0) {
            Log.e(TAG, "LongClick: Invalid element ID")
            return false
        }

        val rootNode = service.rootInActiveWindow ?: return false
        val element = findElementById(rootNode, elementId)
        if (element == null) {
            Log.e(TAG, "LongClick: Element $elementId not found")
            return false
        }

        Log.d(TAG, "LongClick: Performing long click on element $elementId for ${duration}ms")
        element.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        Thread.sleep(duration.toLong())
        return true
    }

    /**
     * BONUS: Double Click
     */
    private fun handleDoubleClick(actionJson: JSONObject): Boolean {
        val elementId = actionJson.optInt("element_id", -1)

        if (elementId < 0) {
            Log.e(TAG, "DoubleClick: Invalid element ID")
            return false
        }

        val rootNode = service.rootInActiveWindow ?: return false
        val element = findElementById(rootNode, elementId)
        if (element == null) {
            Log.e(TAG, "DoubleClick: Element $elementId not found")
            return false
        }

        Log.d(TAG, "DoubleClick: Performing double click on element $elementId")
        element.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        Thread.sleep(100)
        element.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        Thread.sleep(100)
        return true
    }

    // ========================================================================
    // HELPER METHODS
    // ========================================================================

    /**
     * Find element by ID in the tree
     * This assumes the element_id from the semantic tree is the traversal order
     */
    private fun findElementById(rootNode: AccessibilityNodeInfo, targetId: Int): AccessibilityNodeInfo? {
        var currentId = 0
        return findElementByIdRecursive(rootNode, targetId, { currentId++ })
    }

    private fun findElementByIdRecursive(
        node: AccessibilityNodeInfo?,
        targetId: Int,
        idCounter: () -> Int
    ): AccessibilityNodeInfo? {
        if (node == null) return null

        val currentId = idCounter()
        if (currentId == targetId) {
            return node
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i)
            if (child != null) {
                val result = findElementByIdRecursive(child, targetId, idCounter)
                if (result != null) {
                    return result
                }
                child.recycle()
            }
        }

        return null
    }

    /**
     * Find first scrollable element in tree
     */
    private fun findFirstScrollableNode(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (node.isScrollable) {
            return node
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i)
            if (child != null) {
                val result = findFirstScrollableNode(child)
                if (result != null) {
                    return result
                }
                child.recycle()
            }
        }

        return null
    }
}
