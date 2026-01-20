package com.example.aura_project

import android.content.Intent
import android.provider.Settings
import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import org.json.JSONObject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity: FlutterActivity() {
    private val CHANNEL = "com.example.automation/service"
    private val TAG = "AutomationApp"
    private val BACKEND_URL = "http://10.0.2.2:8000"
    private val SESSION_ID = UUID.randomUUID().toString()
    private val NETWORK_TIMEOUT = 30000  // 30 seconds

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "isServiceEnabled" -> {
                    val isEnabled = AutomationService.isServiceEnabled(this)
                    Log.d(TAG, "isServiceEnabled: $isEnabled")
                    result.success(isEnabled)
                }
                "openAccessibilitySettings" -> {
                    Log.d(TAG, "Opening accessibility settings")
                    val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                    startActivity(intent)
                    result.success(null)
                }
                "sendTextToBackend" -> {
                    val text = call.argument<String>("text") ?: ""
                    Log.d(TAG, "📱 sendTextToBackend called with text: '$text'")
                    
                    if (text.isEmpty()) {
                        Log.w(TAG, "⚠️  Text field is empty")
                        result.error("EMPTY_TEXT", "Text field is empty", null)
                        return@setMethodCallHandler
                    }
                    
                    // Use IO dispatcher for network operations, NOT Main!
                    CoroutineScope(Dispatchers.IO).launch {
                        try {
                            Log.d(TAG, "🔄 About to call sendTextToCoordinator on IO thread...")
                            val response = sendTextToCoordinator(text)
                            Log.d(TAG, "✅ Backend response received: $response")
                            
                            // Switch back to Main dispatcher to update UI
                            runOnUiThread {
                                result.success(response)
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "❌ ========== CATCH BLOCK HIT ==========")
                            Log.e(TAG, "Exception class: ${e::class.simpleName}")
                            Log.e(TAG, "Exception message: '${e.message}'")
                            Log.e(TAG, "Exception toString: '${e.toString()}'")
                            Log.e(TAG, "Exception cause: ${e.cause}")
                            Log.e(TAG, "Stack trace:\n${Log.getStackTraceString(e)}")
                            
                            val errorMsg = e.message ?: e.toString() ?: "Unknown error occurred"
                            Log.e(TAG, "Final error message: '$errorMsg'")
                            Log.e(TAG, "❌ ========== END CATCH BLOCK ==========")
                            
                            // Switch back to Main dispatcher to report error
                            runOnUiThread {
                                result.error("BACKEND_ERROR", errorMsg, null)
                            }
                        }
                    }
                }
                "startAutomation" -> {
                    Log.d(TAG, "startAutomation called")
                    val isEnabled = AutomationService.isServiceEnabled(this)
                    Log.d(TAG, "Service enabled: $isEnabled")
                    Log.d(TAG, "Service instance: ${AutomationService.instance}")
                    
                    if (isEnabled) {
                        if (AutomationService.instance != null) {
                            Log.d(TAG, "Calling performAutomation")
                            AutomationService.instance?.performAutomation()
                            result.success("Automation started")
                        } else {
                            Log.e(TAG, "Service instance is null")
                            result.error("SERVICE_NOT_RUNNING", "Accessibility service is enabled but not running. Please restart the app or re-enable the service.", null)
                        }
                    } else {
                        Log.e(TAG, "Service not enabled")
                        result.error("SERVICE_DISABLED", "Accessibility service not enabled", null)
                    }
                }
                else -> result.notImplemented()
            }
        }
    }
    
    /**
     * Send text to backend coordinator agent
     * Calls POST /process endpoint
     */
    private fun sendTextToCoordinator(text: String): Map<String, Any> {
        Log.d(TAG, "🚀 ========== sendTextToCoordinator started ==========")
        Log.d(TAG, "Backend URL: $BACKEND_URL")
        Log.d(TAG, "Session ID: $SESSION_ID")
        Log.d(TAG, "User input: '$text'")
        Log.d(TAG, "Network timeout: $NETWORK_TIMEOUT ms")
        
        try {
            val url = URL("$BACKEND_URL/process")
            Log.d(TAG, "📍 Full URL: ${url.toExternalForm()}")
            Log.d(TAG, "🔗 Creating connection...")
            
            val connection = url.openConnection() as HttpURLConnection
            Log.d(TAG, "✅ Connection object created")
            
            try {
                Log.d(TAG, "⚙️  Configuring connection...")
                connection.requestMethod = "POST"
                Log.d(TAG, "  - Request method set to POST")
                
                connection.setRequestProperty("Content-Type", "application/json")
                Log.d(TAG, "  - Content-Type set to application/json")
                
                connection.connectTimeout = NETWORK_TIMEOUT
                Log.d(TAG, "  - Connect timeout: $NETWORK_TIMEOUT ms")
                
                connection.readTimeout = NETWORK_TIMEOUT
                Log.d(TAG, "  - Read timeout: $NETWORK_TIMEOUT ms")
                
                Log.d(TAG, "✅ Connection configured successfully")
                
                // Build request payload
                Log.d(TAG, "📝 Building request payload...")
                val requestPayload = JSONObject().apply {
                    put("input", text)
                    put("session_id", SESSION_ID)
                    put("is_clarification", false)
                }
                
                Log.d(TAG, "📤 Request payload: ${requestPayload.toString()}")
                
                // Write request body
                Log.d(TAG, "✏️  Writing request body...")
                connection.outputStream.use { os ->
                    val payload = requestPayload.toString().toByteArray(Charsets.UTF_8)
                    os.write(payload)
                    os.flush()
                    Log.d(TAG, "✅ Request body written (${payload.size} bytes)")
                }
                
                // Get response
                Log.d(TAG, "⏳ Calling getResponseCode()...")
                val responseCode = connection.responseCode
                Log.d(TAG, "📥 Response code: $responseCode")
                
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    Log.d(TAG, "✅ Got HTTP 200 - reading response...")
                    val response = connection.inputStream.bufferedReader().use { it.readText() }
                    Log.d(TAG, "✅ Response received (${response.length} bytes)")
                    Log.d(TAG, "📋 Response body: $response")
                    
                    Log.d(TAG, "🔍 Parsing response JSON...")
                    val responseJson = JSONObject(response)
                    val message = responseJson.optString("text", responseJson.optString("question", "Response received"))
                    Log.d(TAG, "🎯 Extracted message: '$message'")
                    Log.d(TAG, "✅ ========== Request successful ==========")
                    
                    return mapOf(
                        "status" to "success",
                        "response" to response,
                        "message" to message
                    )
                } else {
                    Log.e(TAG, "❌ Got HTTP error: $responseCode")
                    val errorResponse = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "Unknown error"
                    Log.e(TAG, "Error response: $errorResponse")
                    Log.e(TAG, "❌ ========== Request failed ==========")
                    
                    return mapOf(
                        "status" to "error",
                        "error" to "HTTP $responseCode: $errorResponse"
                    )
                }
            } finally {
                Log.d(TAG, "🔌 Disconnecting...")
                connection.disconnect()
                Log.d(TAG, "✅ Connection disconnected")
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ ========== EXCEPTION IN sendTextToCoordinator ==========")
            Log.e(TAG, "Exception class: ${e::class.simpleName}")
            Log.e(TAG, "Exception message: '${e.message}'")
            Log.e(TAG, "Exception toString: '${e.toString()}'")
            Log.e(TAG, "Exception cause: ${e.cause}")
            
            val sw = java.io.StringWriter()
            val pw = java.io.PrintWriter(sw)
            e.printStackTrace(pw)
            Log.e(TAG, "Stack trace:\n$sw")
            
            Log.e(TAG, "❌ ========== END EXCEPTION ==========")
            throw e
        }
    }
}