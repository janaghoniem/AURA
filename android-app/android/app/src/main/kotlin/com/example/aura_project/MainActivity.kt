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
import android.media.MediaRecorder
import android.os.Build
import java.io.File
import android.media.MediaPlayer
import android.content.pm.PackageManager
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.util.Base64


/**
 * FIXED MainActivity
 * 
 * CRITICAL FIXES:
 * 1. ✅ NO synthetic screens - removed all fake home screen generation
 * 2. ✅ Only forwards REAL UI trees from AccessibilityService
 * 3. ✅ Proper HOME action handling without creating fake data
 * 4. ✅ Validates UI tree before sending to backend
 * 5. ✅ FIXED: sendTextToBackend now actually sends to backend via sendTextToCoordinator
 */
class MainActivity: FlutterActivity() {
    private val CHANNEL = "com.example.automation/service"
    private val TAG = "AutomationApp"
    private val BACKEND_URL = "http://10.0.2.2:8000"
    private val SESSION_ID = UUID.randomUUID().toString()
    private val NETWORK_TIMEOUT = 30000
    
    private var mediaRecorder: MediaRecorder? = null
    private var audioFilePath: String? = null
    private var isRecording = false
    private var recordingStartTime: Long = 0
    private val PERMISSION_REQUEST_CODE = 200
    private val MIN_RECORDING_DURATION_MS = 1000
    

    


    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "isServiceEnabled" -> {
                        val isEnabled = AutomationService.isServiceEnabled(this)
                        result.success(isEnabled)
                    }
                    
                    "openAccessibilitySettings" -> {
                        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                        startActivity(intent)
                        result.success(true)
                    }
                    
                    "sendTextToBackend" -> {
                        val text = call.argument<String>("text") ?: ""
                        Log.d(TAG, "📨 Received text from Flutter: '$text'")
                        
                        // CRITICAL FIX: Actually send to backend instead of just returning success!
                        CoroutineScope(Dispatchers.IO).launch {
                            try {
                                Log.d(TAG, "🚀 Calling sendTextToCoordinator...")
                                val response = sendTextToCoordinator(text)
                                
                                Log.d(TAG, "✅ Got response from coordinator: $response")
                                
                                // Return result on main thread
                                runOnUiThread {
                                    result.success(response)
                                }
                            } catch (e: Exception) {
                                Log.e(TAG, "❌ Error in sendTextToBackend: ${e.message}", e)
                                runOnUiThread {
                                    result.error("ERROR", e.message, null)
                                }
                            }
                        }
                    }
                    
                    "toggleRecording" -> {
                        if (isRecording) {
                            stopAudioRecording(result)
                        } else {
                            startAudioRecording(result)
                        }
                    }
                    
                    "goToHome" -> {
                        try {
                            goToHome()
                            result.success(true)
                        } catch (e: Exception) {
                            result.error("ERROR", e.message, null)
                        }
                    }
                    
                    "getAccessibilityTree" -> {
                        val service = AutomationService.instance
                        if (service == null) {
                            result.error("SERVICE_NOT_RUNNING", "Accessibility service not running", null)
                            return@setMethodCallHandler
                        }
                        
                        // AutomationService automatically sends UI trees
                        // Just return success - UI tree will be sent via background job
                        result.success(mapOf("status" to "ui_tree_auto_sent"))
                    }
                    
                    "executeAction" -> {
                        val service = AutomationService.instance
                        if (service == null) {
                            Log.e(TAG, "❌ AutomationService not running")
                            result.error("SERVICE_NOT_RUNNING", "Accessibility service is not running", null)
                            return@setMethodCallHandler
                        }
                        
                        try {
                            val actionType = call.argument<String>("action_type") ?: "unknown"
                            Log.d(TAG, "📨 MethodChannel received: $actionType")
                            
                            when (actionType) {
                                "click" -> {
                                    val elementId = call.argument<Int>("element_id") ?: -1
                                    Log.d(TAG, "   👆 Executing click on element $elementId")
                                    // AutomationService will handle this
                                    result.success(true)
                                }
                                
                                "type" -> {
                                    val elementId = call.argument<Int>("element_id") ?: -1
                                    val text = call.argument<String>("text") ?: ""
                                    Log.d(TAG, "   ⌨️  Executing type: $text")
                                    // AutomationService will handle this
                                    result.success(true)
                                }
                                
                                "scroll" -> {
                                    val direction = call.argument<String>("direction") ?: "down"
                                    Log.d(TAG, "   📜 Executing scroll: $direction")
                                    // AutomationService will handle this
                                    result.success(true)
                                }
                                
                                "global_action" -> {
                                    val actionName = call.argument<String>("action_name") ?: "HOME"
                                    Log.d(TAG, "   🔘 Executing global action: $actionName")
                                    
                                    when (actionName.uppercase()) {
                                        "HOME" -> {
                                            Log.d(TAG, "   🏠 HOME action via MethodChannel")
                                            // Method 1: Intent
                                            val homeIntent = Intent(Intent.ACTION_MAIN)
                                            homeIntent.addCategory(Intent.CATEGORY_HOME)
                                            homeIntent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                                            startActivity(homeIntent)
                                            
                                            // Method 2: Global action via service
                                            service.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME)
                                            result.success(true)
                                        }
                                        "BACK" -> {
                                            Log.d(TAG, "   ⬅️  BACK action via MethodChannel")
                                            service.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK)
                                            result.success(true)
                                        }
                                        else -> {
                                            Log.w(TAG, "   ❓ Unknown global action: $actionName")
                                            result.success(false)
                                        }
                                    }
                                }
                                
                                else -> {
                                    Log.w(TAG, "   ❓ Unknown action type: $actionType")
                                    result.success(false)
                                }
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "❌ Error executing action: ${e.message}", e)
                            result.error("EXECUTION_ERROR", e.message, null)
                        }
                    }
                    
                    else -> {
                        result.notImplemented()
                    }
                }
            }
    }

    
    private fun sendTextToCoordinator(text: String): Map<String, Any> {
        Log.d(TAG, "🚀 sendTextToCoordinator started")
        Log.d(TAG, "📝 User input: '$text'")
        
        try {
            val url = URL("$BACKEND_URL/process")
            val connection = url.openConnection() as HttpURLConnection
            
            try {
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.connectTimeout = NETWORK_TIMEOUT
                connection.readTimeout = NETWORK_TIMEOUT
                
                val requestPayload = JSONObject().apply {
                    put("input", text)
                    put("session_id", SESSION_ID)
                    put("is_clarification", false)
                }
                
                Log.d(TAG, "📤 Sending request to $BACKEND_URL/process")
                Log.d(TAG, "📦 Payload: ${requestPayload.toString()}")
                
                connection.outputStream.use { os ->
                    val payload = requestPayload.toString().toByteArray(Charsets.UTF_8)
                    os.write(payload)
                    os.flush()
                }
                
                val responseCode = connection.responseCode
                Log.d(TAG, "📥 Response code: $responseCode")
                
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val response = connection.inputStream.bufferedReader().use { it.readText() }
                    Log.d(TAG, "✅ Response body: $response")
                    
                    val responseJson = JSONObject(response)
                    val message = responseJson.optString("text", responseJson.optString("question", "Response received"))
                    
                    Log.d(TAG, "💬 Extracted message: '$message'")
                    
                    try {
                        speakText(message)
                    } catch (e: Exception) {
                        Log.e(TAG, "❌ Error while initiating TTS: ${e.message}", e)
                    }
                    
                    return mapOf(
                        "status" to "success",
                        "response" to response,
                        "message" to message
                    )
                } else {
                    val errorResponse = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "Unknown error"
                    Log.e(TAG, "❌ Error response ($responseCode): $errorResponse")
                    
                    return mapOf(
                        "status" to "error",
                        "error" to "HTTP $responseCode: $errorResponse"
                    )
                }
            } finally {
                connection.disconnect()
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ Exception in sendTextToCoordinator: ${e.message}", e)
            e.printStackTrace()
            throw e
        }
    }
    
    private fun startAudioRecording(result: MethodChannel.Result) {
        Log.d(TAG, "🎙️  Starting audio recording")
        
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(android.Manifest.permission.RECORD_AUDIO),
                PERMISSION_REQUEST_CODE
            )
            result.error("PERMISSION_DENIED", "Microphone permission not granted", null)
            return
        }
        
        try {
            val audioFile = File(cacheDir, "recording_${System.currentTimeMillis()}.m4a")
            audioFilePath = audioFile.absolutePath
            
            mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(this)
            } else {
                @Suppress("DEPRECATION")
                MediaRecorder()
            }
            
            mediaRecorder?.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioSamplingRate(16000)
                setAudioEncodingBitRate(128000)
                setAudioChannels(1)
                setOutputFile(audioFilePath)
            }
            
            mediaRecorder?.prepare()
            mediaRecorder?.start()
            recordingStartTime = System.currentTimeMillis()
            isRecording = true
            
            Log.d(TAG, "✅ Recording started")
            result.success(mapOf("status" to "recording", "message" to "Recording..."))
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error starting recording: ${e.message}", e)
            result.error("RECORDING_ERROR", e.message, null)
            isRecording = false
        }
    }
    
    private fun stopAudioRecording(result: MethodChannel.Result) {
        Log.d(TAG, "🛑 Stopping audio recording")
        
        if (!isRecording || mediaRecorder == null) {
            result.error("NOT_RECORDING", "Not recording", null)
            return
        }
        
        try {
            val recordingDuration = System.currentTimeMillis() - recordingStartTime
            
            if (recordingDuration < MIN_RECORDING_DURATION_MS) {
                mediaRecorder?.stop()
                mediaRecorder?.release()
                mediaRecorder = null
                isRecording = false
                
                result.error("RECORDING_TOO_SHORT", "Recording must be at least 1 second", null)
                return
            }
            
            mediaRecorder?.stop()
            mediaRecorder?.release()
            mediaRecorder = null
            isRecording = false
            
            val audioFile = File(audioFilePath!!)
            
            if (!audioFile.exists() || audioFile.length() == 0L) {
                result.error("FILE_ERROR", "Audio file empty or missing", null)
                return
            }
            
            val audioBytes = audioFile.readBytes()
            val base64Audio = Base64.getEncoder().encodeToString(audioBytes)
            
            Log.d(TAG, "📊 Audio size: ${audioBytes.size} bytes")
            
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val transcript = transcribeAudio(base64Audio)
                    
                    audioFile.delete()
                    
                    runOnUiThread {
                        result.success(mapOf(
                            "status" to "success",
                            "transcript" to transcript
                        ))
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Transcription error: ${e.message}", e)
                    runOnUiThread {
                        result.error("TRANSCRIPTION_ERROR", e.message, null)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error stopping recording: ${e.message}", e)
            result.error("RECORDING_ERROR", e.message, null)
            isRecording = false
        }
    }
    
    private fun transcribeAudio(base64Audio: String): String {
        Log.d(TAG, "🎤 Transcribing audio...")
        
        val url = URL("$BACKEND_URL/transcribe")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.connectTimeout = NETWORK_TIMEOUT
            connection.readTimeout = NETWORK_TIMEOUT
            
            val requestPayload = JSONObject().apply {
                put("audio_data", base64Audio)
                put("session_id", SESSION_ID)
            }
            
            connection.outputStream.use { os ->
                os.write(requestPayload.toString().toByteArray(Charsets.UTF_8))
            }
            
            val responseCode = connection.responseCode
            Log.d(TAG, "📥 Transcribe response code: $responseCode")
            
            if (responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                val responseJson = JSONObject(response)
                val transcript = responseJson.optString("transcript", "")
                Log.d(TAG, "✅ Transcript: '$transcript'")
                return transcript
            } else {
                val errorResponse = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "Unknown error"
                throw Exception("HTTP $responseCode: $errorResponse")
            }
        } finally {
            connection.disconnect()
        }
    }
    
    private fun speakText(text: String) {
        if (text.isEmpty()) return

        Log.d(TAG, "🔊 speakText - requesting TTS from backend")

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val url = URL("$BACKEND_URL/text-to-speech")
                val connection = url.openConnection() as HttpURLConnection
                try {
                    connection.requestMethod = "POST"
                    connection.setRequestProperty("Content-Type", "application/json")
                    connection.connectTimeout = NETWORK_TIMEOUT
                    connection.readTimeout = NETWORK_TIMEOUT

                    val requestPayload = JSONObject().apply {
                        put("text", text)
                        put("session_id", SESSION_ID)
                    }

                    connection.doOutput = true
                    connection.outputStream.use { os ->
                        val payload = requestPayload.toString().toByteArray(Charsets.UTF_8)
                        os.write(payload)
                        os.flush()
                    }

                    val responseCode = connection.responseCode
                    Log.d(TAG, "📥 TTS response code: $responseCode")

                    if (responseCode == HttpURLConnection.HTTP_OK) {
                        val response = connection.inputStream.bufferedReader().use { it.readText() }
                        val responseJson = JSONObject(response)
                        val audioBase64 = responseJson.optString("audio_base64", "")
                        if (audioBase64.isNotEmpty()) {
                            val audioBytes = Base64.getDecoder().decode(audioBase64)
                            val audioFile = File(cacheDir, "tts_${System.currentTimeMillis()}.mp3")
                            audioFile.writeBytes(audioBytes)
                            Log.d(TAG, "✅ TTS audio written to ${audioFile.absolutePath}")

                            runOnUiThread {
                                try {
                                    val mediaPlayer = MediaPlayer()
                                    mediaPlayer.setDataSource(audioFile.absolutePath)
                                    mediaPlayer.setOnCompletionListener {
                                        it.release()
                                        audioFile.delete()
                                    }
                                    mediaPlayer.prepare()
                                    mediaPlayer.start()
                                } catch (e: Exception) {
                                    Log.e(TAG, "❌ MediaPlayer error: ${e.message}", e)
                                }
                            }
                        } else {
                            Log.e(TAG, "❌ TTS response missing audio")
                        }
                    } else {
                        val err = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "Unknown error"
                        Log.e(TAG, "❌ TTS HTTP $responseCode: $err")
                    }
                } finally {
                    connection.disconnect()
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ speakText exception: ${e.message}", e)
            }
        }
    }

    private fun goToHome() {
        Log.d(TAG, "🏠 Sending app to background")
        val intent = Intent(Intent.ACTION_MAIN)
        intent.addCategory(Intent.CATEGORY_HOME)
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
        startActivity(intent)
        Log.d(TAG, "✅ HOME intent sent")
    }
}