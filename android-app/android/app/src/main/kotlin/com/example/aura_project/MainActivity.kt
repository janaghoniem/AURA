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
import android.speech.tts.TextToSpeech
import java.util.Locale

class MainActivity: FlutterActivity(), TextToSpeech.OnInitListener {
    private val CHANNEL = "com.example.automation/service"
    private val TAG = "AutomationApp"
    private val BACKEND_URL = "http://10.0.2.2:8000"
    private val SESSION_ID = UUID.randomUUID().toString()
    private val NETWORK_TIMEOUT = 30000  // 30 seconds
    
    // Audio recording variables
    private var mediaRecorder: MediaRecorder? = null
    private var audioFilePath: String? = null
    private var isRecording = false
    private var recordingStartTime: Long = 0  // Track recording duration
    private val PERMISSION_REQUEST_CODE = 200
    private val MIN_RECORDING_DURATION_MS = 1000  // Minimum 1 second
    
    // Text-to-Speech variables
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    
    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            Log.d(TAG, "🔊 TextToSpeech initialized successfully")
            tts?.language = Locale.getDefault()
            ttsReady = true
        } else {
            Log.e(TAG, "❌ TextToSpeech initialization failed")
            ttsReady = false
        }
    }
    
    override fun onDestroy() {
        if (tts != null) {
            tts?.stop()
            tts?.shutdown()
            Log.d(TAG, "🔊 TextToSpeech shutdown")
        }
        super.onDestroy()
    }
    
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        
        // Initialize TextToSpeech
        tts = TextToSpeech(this, this)
        Log.d(TAG, "🔊 TextToSpeech initialization started")
        
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
                            
                            // Extract message and speak it
                            if (response is Map<*, *>) {
                                val message = response["message"] as? String ?: ""
                                if (message.isNotEmpty()) {
                                    Log.d(TAG, "🔊 Attempting to speak response: '$message'")
                                    runOnUiThread {
                                        speakText(message)
                                    }
                                }
                            }
                            
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
                "toggleRecording" -> {
                    Log.d(TAG, "🎤 toggleRecording called, isRecording: $isRecording")
                    
                    if (!isRecording) {
                        // Start recording
                        startAudioRecording(result)
                    } else {
                        // Stop recording and transcribe
                        stopAudioRecording(result)
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
    
    /**
     * Start audio recording - FIXED with proper MediaRecorder settings
     */
    private fun startAudioRecording(result: MethodChannel.Result) {
        Log.d(TAG, "🎙️  ========== Starting audio recording ==========")
        
        // Check permissions
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "⚠️  Microphone permission not granted, requesting...")
            ActivityCompat.requestPermissions(
                this,
                arrayOf(android.Manifest.permission.RECORD_AUDIO),
                PERMISSION_REQUEST_CODE
            )
            result.error("PERMISSION_DENIED", "Microphone permission not granted", null)
            return
        }
        
        try {
            // Create file for audio - USE .m4a EXTENSION
            val audioFile = File(cacheDir, "recording_${System.currentTimeMillis()}.m4a")
            audioFilePath = audioFile.absolutePath
            Log.d(TAG, "📁 Audio file path: $audioFilePath")
            
            // Initialize MediaRecorder
            mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(this)
            } else {
                @Suppress("DEPRECATION")
                MediaRecorder()
            }
            
            // CRITICAL: Proper configuration for M4A/AAC
            mediaRecorder?.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)  // M4A container
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)      // AAC codec
                setAudioSamplingRate(16000)      // 16kHz is standard for speech
                setAudioEncodingBitRate(128000)  // 128 kbps - good quality
                setAudioChannels(1)              // Mono audio
                setOutputFile(audioFilePath)
                Log.d(TAG, "⚙️  MediaRecorder configured:")
                Log.d(TAG, "  - Format: MPEG_4 (M4A)")
                Log.d(TAG, "  - Encoder: AAC")
                Log.d(TAG, "  - Sample Rate: 16000 Hz")
                Log.d(TAG, "  - Bit Rate: 128000 bps")
                Log.d(TAG, "  - Channels: Mono")
            }
            
            Log.d(TAG, "📝 Preparing MediaRecorder...")
            mediaRecorder?.prepare()
            
            Log.d(TAG, "▶️  Starting recording...")
            mediaRecorder?.start()
            recordingStartTime = System.currentTimeMillis()  // Track start time
            isRecording = true
            
            Log.d(TAG, "✅ Recording started successfully!")
            result.success(mapOf("status" to "recording", "message" to "Recording started..."))
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error starting recording: ${e.message}", e)
            Log.e(TAG, "Stack trace:\n${Log.getStackTraceString(e)}")
            result.error("RECORDING_ERROR", e.message, null)
            isRecording = false
            
            // Clean up on error
            try {
                mediaRecorder?.release()
                mediaRecorder = null
            } catch (cleanupError: Exception) {
                Log.e(TAG, "Error during cleanup: ${cleanupError.message}")
            }
        }
    }
    
    /**
     * Stop audio recording and send to backend for transcription
     * FIXED: Better error handling and file validation
     */
    private fun stopAudioRecording(result: MethodChannel.Result) {
        Log.d(TAG, "🛑 ========== Stopping audio recording ==========")
        
        if (!isRecording || mediaRecorder == null) {
            Log.w(TAG, "⚠️  Not recording")
            result.error("NOT_RECORDING", "Not currently recording", null)
            return
        }
        
        try {
            Log.d(TAG, "⏹️  Stopping MediaRecorder...")
            
            // Check recording duration
            val recordingDuration = System.currentTimeMillis() - recordingStartTime
            Log.d(TAG, "⏱️  Recording duration: ${recordingDuration}ms")
            
            if (recordingDuration < MIN_RECORDING_DURATION_MS) {
                Log.w(TAG, "⚠️  Recording too short! Must be at least ${MIN_RECORDING_DURATION_MS}ms")
                mediaRecorder?.stop()
                mediaRecorder?.release()
                mediaRecorder = null
                isRecording = false
                
                result.error("RECORDING_TOO_SHORT", "Recording must be at least 1 second long", null)
                return
            }
            
            mediaRecorder?.stop()
            
            Log.d(TAG, "🔓 Releasing MediaRecorder...")
            mediaRecorder?.release()
            mediaRecorder = null
            isRecording = false
            
            Log.d(TAG, "✅ Recording stopped")
            Log.d(TAG, "📁 Audio file: $audioFilePath")
            
            // Validate audio file
            val audioFile = File(audioFilePath!!)
            
            if (!audioFile.exists()) {
                Log.e(TAG, "❌ Audio file does not exist!")
                result.error("FILE_ERROR", "Audio file not found", null)
                return
            }
            
            val fileSize = audioFile.length()
            Log.d(TAG, "📊 Audio file size: $fileSize bytes")
            
            if (fileSize == 0L) {
                Log.e(TAG, "❌ Audio file is empty!")
                result.error("FILE_ERROR", "Audio file is empty", null)
                return
            }
            
            if (fileSize < 1000) {
                Log.w(TAG, "⚠️  Audio file is very small ($fileSize bytes) - might be too short")
            }
            
            // Read the complete M4A file (including headers)
            Log.d(TAG, "📖 Reading audio file bytes...")
            val audioBytes = audioFile.readBytes()
            
            // Verify M4A file signature
            if (audioBytes.size >= 8) {
                val signature = String(audioBytes.sliceArray(4..7))
                Log.d(TAG, "🔍 File signature: $signature")
                
                if (signature != "ftyp") {
                    Log.w(TAG, "⚠️  Unexpected file signature. Expected 'ftyp', got '$signature'")
                    Log.w(TAG, "⚠️  First 16 bytes: ${audioBytes.take(16).joinToString(" ") { "%02x".format(it) }}")
                } else {
                    Log.d(TAG, "✅ Valid M4A file signature detected")
                }
            }
            
            // Encode to base64
            Log.d(TAG, "🔐 Encoding to base64...")
            val base64Audio = Base64.getEncoder().encodeToString(audioBytes)
            
            Log.d(TAG, "📊 Audio file size: ${audioBytes.size} bytes")
            Log.d(TAG, "📊 Base64 encoded size: ${base64Audio.length} characters")
            Log.d(TAG, "📊 File format: M4A/AAC")
            
            // Send to transcription endpoint
            Log.d(TAG, "📤 Sending audio to /transcribe endpoint...")
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val transcript = transcribeAudio(base64Audio)
                    Log.d(TAG, "✅ Transcription received: '$transcript'")
                    
                    // Clean up audio file
                    try {
                        audioFile.delete()
                        Log.d(TAG, "🗑️ Deleted audio file")
                    } catch (e: Exception) {
                        Log.w(TAG, "⚠️ Could not delete audio file: ${e.message}")
                    }
                    
                    runOnUiThread {
                        result.success(mapOf(
                            "status" to "success",
                            "transcript" to transcript
                        ))
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Transcription error: ${e.message}", e)
                    Log.e(TAG, "Stack trace:\n${Log.getStackTraceString(e)}")
                    runOnUiThread {
                        result.error("TRANSCRIPTION_ERROR", e.message, null)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error stopping recording: ${e.message}", e)
            Log.e(TAG, "Stack trace:\n${Log.getStackTraceString(e)}")
            result.error("RECORDING_ERROR", e.message, null)
            isRecording = false
            
            // Try to release resources
            try {
                mediaRecorder?.release()
                mediaRecorder = null
            } catch (cleanupError: Exception) {
                Log.e(TAG, "Error during cleanup: ${cleanupError.message}")
            }
        }
    }
    
    /**
     * Send audio to backend for transcription
     */
    private fun transcribeAudio(base64Audio: String): String {
        Log.d(TAG, "🔄 transcribeAudio started")
        Log.d(TAG, "Audio data size: ${base64Audio.length} characters")
        
        val url = URL("$BACKEND_URL/transcribe")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.connectTimeout = NETWORK_TIMEOUT
            connection.readTimeout = NETWORK_TIMEOUT
            
            // Build request
            val requestPayload = JSONObject().apply {
                put("audio_data", base64Audio)
                put("session_id", SESSION_ID)
            }
            
            Log.d(TAG, "📤 Sending transcribe request...")
            connection.outputStream.use { os ->
                os.write(requestPayload.toString().toByteArray(Charsets.UTF_8))
            }
            
            // Get response
            val responseCode = connection.responseCode
            Log.d(TAG, "📥 Response code: $responseCode")
            
            if (responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                Log.d(TAG, "✅ Response: $response")
                
                val responseJson = JSONObject(response)
                val transcript = responseJson.optString("transcript", "")
                Log.d(TAG, "🎯 Transcript: '$transcript'")
                
                return transcript
            } else {
                val errorResponse = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "Unknown error"
                Log.e(TAG, "❌ Error response: $errorResponse")
                throw Exception("HTTP $responseCode: $errorResponse")
            }
        } finally {
            connection.disconnect()
        }
    }
    
    /**
     * Convert text to speech and play it
     */
    private fun speakText(text: String) {
        if (!ttsReady) {
            Log.w(TAG, "⚠️  TextToSpeech not ready yet, skipping speech")
            return
        }
        
        if (text.isEmpty()) {
            Log.w(TAG, "⚠️  Text is empty, not speaking")
            return
        }
        
        Log.d(TAG, "🔊 ========== Speaking text ==========")
        Log.d(TAG, "📝 Text to speak: '$text'")
        Log.d(TAG, "🎧 Using locale: ${tts?.language}")
        
        try {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, null)
            Log.d(TAG, "✅ Text queued for speech synthesis")
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error during TTS: ${e.message}")
            Log.e(TAG, "Stack trace:\n${Log.getStackTraceString(e)}")
        }
    }
}