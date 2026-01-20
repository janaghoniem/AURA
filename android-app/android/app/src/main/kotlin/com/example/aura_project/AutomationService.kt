package com.example.aura_project

import android.accessibilityservice.AccessibilityService
import android.content.ClipboardManager
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

class AutomationService : AccessibilityService() {

    companion object {
        var instance: AutomationService? = null
        private const val TAG = "AutomationService"
        
        fun isServiceEnabled(context: Context): Boolean {
            val enabledServices = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            )
            return enabledServices?.contains(context.packageName) == true
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.d(TAG, "AutomationService connected and instance set")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Not used for this specific trigger, but required to override
    }

    override fun onInterrupt() {
        Log.d(TAG, "onInterrupt called")
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "AutomationService destroyed")
        instance = null
    }

    /**
     * Copy text to clipboard and paste it into the focused field
     */
    private fun setTextViaClipboard(text: String, node: AccessibilityNodeInfo): Boolean {
        return try {
            Log.d(TAG, "setTextViaClipboard: Setting text '$text'")
            
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val clip = ClipData.newPlainText("text", text)
            clipboard.setPrimaryClip(clip)
            Log.d(TAG, "Text copied to clipboard")
            Thread.sleep(300)
            
            // Try paste action
            Log.d(TAG, "Attempting paste action")
            val success = node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
            Log.d(TAG, "Paste action result: $success")
            Thread.sleep(500)
            
            success
        } catch (e: Exception) {
            Log.e(TAG, "Clipboard paste failed: ${e.message}", e)
            false
        }
    }

    /**
     * Main entry point to start the automation
     */
    fun performAutomation() {
        Log.d(TAG, "performAutomation called - this method is executing!")
        Log.d(TAG, "Starting Gmail automation")
        
        try {
            // Try multiple possible Gmail package names
            val possiblePackages = listOf(
                "com.google.android.gm",
                "com.google.android.gm.lite",
                "com.gmail.android"
            )
            
            var launchIntent: Intent? = null
            for (packageName in possiblePackages) {
                launchIntent = packageManager.getLaunchIntentForPackage(packageName)
                if (launchIntent != null) {
                    Log.d(TAG, "Found Gmail at: $packageName")
                    break
                }
            }
            
            Log.d(TAG, "Launch intent: $launchIntent")
            
            if (launchIntent != null) {
                launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                startActivity(launchIntent)
                Log.d(TAG, "Gmail app launched")
                
                Handler(Looper.getMainLooper()).postDelayed({
                    Log.d(TAG, "Calling clickComposeButton after delay")
                    clickComposeButton(0)
                }, 3000)
            } else {
                Log.e(TAG, "Could not get launch intent for Gmail - all package names failed")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Exception in performAutomation: ${e.message}", e)
        }
    }

    private fun clickComposeButton(attempt: Int) {
        if (attempt > 5) {
            Log.e(TAG, "Failed to find compose button after 5 attempts")
            return
        }
        
        val rootNode = rootInActiveWindow
        if (rootNode == null) {
            Log.e(TAG, "Root node is null")
            Handler(Looper.getMainLooper()).postDelayed({
                clickComposeButton(attempt + 1)
            }, 1000)
            return
        }
        
        Log.d(TAG, "Attempt $attempt: Looking for compose button")
        
        val composeButton = findNodeByContentDescription(rootNode, "Compose")
            ?: findNodeByText(rootNode, "Compose")
        
        if (composeButton != null && composeButton.isClickable) {
            Log.d(TAG, "Found compose button, clicking")
            composeButton.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            
            Handler(Looper.getMainLooper()).postDelayed({
                fillAllFields(0)
            }, 2500)
        } else {
            Log.d(TAG, "Compose button not found, retrying")
            Handler(Looper.getMainLooper()).postDelayed({
                clickComposeButton(attempt + 1)
            }, 1000)
        }
    }

    private fun fillAllFields(attempt: Int) {
        if (attempt > 10) {
            Log.e(TAG, "Failed to fill fields after 10 attempts")
            return
        }
        
        val rootNode = rootInActiveWindow
        if (rootNode == null) {
            Log.e(TAG, "Root node is null")
            return
        }
        
        // Find ALL EditText fields
        val allEditTexts = mutableListOf<AccessibilityNodeInfo>()
        collectAllEditTexts(rootNode, allEditTexts)
        
        Log.d(TAG, "Attempt $attempt: Found ${allEditTexts.size} EditText fields")
        
        if (allEditTexts.size < 3) {
            // Not all fields loaded yet, retry
            Log.d(TAG, "Not enough fields yet, waiting...")
            Handler(Looper.getMainLooper()).postDelayed({
                fillAllFields(attempt + 1)
            }, 1500)
            return
        }
        
        // Gmail compose has 3 EditText fields in order: To, Subject, Body
        val toField = allEditTexts[0]
        val subjectField = allEditTexts[1]
        val bodyField = allEditTexts[2]
        
        Log.d(TAG, "All fields found, starting to fill")
        Log.d(TAG, "To field: ${toField.text}")
        Log.d(TAG, "Subject field: ${subjectField.text}")
        Log.d(TAG, "Body field: ${bodyField.text}")
        
        Log.d(TAG, "Clicking and focusing To field")
        toField.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        toField.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        Thread.sleep(400)
        
        Handler(Looper.getMainLooper()).postDelayed({
            val toSuccess = setTextViaClipboard("hayaadawy@icloud.com", toField)
            Log.d(TAG, "To field result: $toSuccess")
            
            Handler(Looper.getMainLooper()).postDelayed({
                Log.d(TAG, "Clicking and focusing Subject field")
                subjectField.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                subjectField.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
                Thread.sleep(400)
                
                Handler(Looper.getMainLooper()).postDelayed({
                    val subjectSuccess = setTextViaClipboard("testing out this new method", subjectField)
                    Log.d(TAG, "Subject field result: $subjectSuccess")
                    
                    Handler(Looper.getMainLooper()).postDelayed({
                        Log.d(TAG, "Clicking and focusing Body field")
                        bodyField.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                        bodyField.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
                        Thread.sleep(400)
                        
                        Handler(Looper.getMainLooper()).postDelayed({
                            val bodySuccess = setTextViaClipboard("hello! this is just a test from the agent! thank you", bodyField)
                            Log.d(TAG, "Body field result: $bodySuccess")
                            
                            Handler(Looper.getMainLooper()).postDelayed({
                                sendEmail()
                            }, 1500)
                        }, 600)
                    }, 1200)
                }, 600)
            }, 1200)
        }, 600)
    }

    private fun collectAllEditTexts(node: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        if (node.className?.contains("EditText") == true) {
            list.add(node)
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectAllEditTexts(child, list)
        }
    }

    private fun sendEmail() {
        val rootNode = rootInActiveWindow
        if (rootNode == null) {
            Log.e(TAG, "Root node is null when trying to send")
            return
        }
        
        Log.d(TAG, "Looking for Send button")
        
        val sendButton = findNodeByContentDescription(rootNode, "Send")
            ?: findNodeByText(rootNode, "Send")
        
        if (sendButton != null && sendButton.isClickable) {
            Log.d(TAG, "Found Send button, clicking")
            sendButton.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            Log.d(TAG, "Email sent!")
        } else {
            Log.e(TAG, "Send button not found")
        }
    }

    // --- Helper Search Methods ---

    private fun findNodeByText(node: AccessibilityNodeInfo, text: String): AccessibilityNodeInfo? {
        if (node.text?.toString()?.contains(text, ignoreCase = true) == true) return node
        for (i in 0 until node.childCount) {
            val result = findNodeByText(node.getChild(i) ?: continue, text)
            if (result != null) return result
        }
        return null
    }

    private fun findNodeByContentDescription(node: AccessibilityNodeInfo, desc: String): AccessibilityNodeInfo? {
        if (node.contentDescription?.toString()?.contains(desc, ignoreCase = true) == true) return node
        for (i in 0 until node.childCount) {
            val result = findNodeByContentDescription(node.getChild(i) ?: continue, desc)
            if (result != null) return result
        }
        return null
    }
}
