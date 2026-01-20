package com.example.aura_project

import android.content.Intent
import android.provider.Settings
import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity: FlutterActivity() {
    private val CHANNEL = "com.example.automation/service"
    private val TAG = "AutomationApp"

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
}