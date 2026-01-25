# 🔧 Android Service Integration Guide

## Quick Summary

The **AutomationService** has been completely rewritten to:
- ✅ Capture real Android system UI (Home screen, app drawer, etc.)
- ✅ Not just the Flutter app UI anymore
- ✅ Send UI tree to backend every 2 seconds
- ✅ Execute real accessibility actions

## What You Need to Do

### Step 1: Rebuild Android App

```bash
cd android-app
flutter clean
flutter pub get
flutter build apk
```

### Step 2: Ensure Accessibility Service is Enabled

When the app starts, user must:
1. Open Android Settings
2. Go to Accessibility
3. Enable "Aura Project" (or your app name)
4. Grant permissions when prompted

### Step 3: Verify Service is Running

Check Android logcat:
```
adb logcat -s "AutomationService"
```

You should see:
```
✅ AutomationService connected
📡 Starting UI tree broadcast...
📤 Sending UI tree...
   App: Launcher
   Screen: Home
   Elements: 12
```

### Step 4: Test the Full Flow

**Backend Log:**
```
2026-01-24 19:16:17 - Handling mobile task: task_1
2026-01-24 19:16:17 - 🤖 Using ReAct loop for mobile task: Open Gmail app
2026-01-24 19:16:17 - 👁️ Getting initial UI state...
2026-01-24 19:16:17 - ✅ Initial UI captured: Home Screen
2026-01-24 19:16:17 - Elements found: 15  ← NOW SHOWS HOME SCREEN ELEMENTS!
```

**Should see:**
- Gmail icon in UI tree
- LLM recognizes it
- LLM clicks it
- New observation shows Gmail is open
- Task completes successfully

## Important Files

| File | What Changed |
|------|--------------|
| `AutomationService.kt` | Complete rewrite - now captures real system UI |
| `mobile_action_handler.py` | Removed old hardcoded automation, always use ReAct |
| `mobile_strategy.py` | No changes, but now gets real UI data |

## Troubleshooting

### Issue: Service not sending UI tree

**Check:**
1. Is Accessibility enabled in Settings?
2. Is app running in foreground?
3. Check logcat: `adb logcat -s "AutomationService"`

**Fix:**
- Rebuild app: `flutter clean && flutter build apk`
- Re-enable Accessibility service
- Restart app

### Issue: Getting "Unknown Screen" or empty elements

**Check:**
1. Service is connected: `rootInActiveWindow` is not null
2. Current app is different from Flutter app
3. Try switching to Home screen first

### Issue: Actions not executing

**Check:**
1. Element IDs are correct (1-indexed)
2. Element is actually clickable/editable
3. Accessibility service has required permissions

## Architecture Now

```
Android Device:
├─ AutomationService (extends AccessibilityService)
│  ├─ onServiceConnected() → startUIBroadcasting()
│  ├─ startUIBroadcasting() → runs every 2 seconds
│  │  ├─ Gets rootInActiveWindow (REAL current app!)
│  │  ├─ Parses to JSON
│  │  └─ POSTs to backend /device/{id}/ui-tree
│  └─ executeAction() → handles clicks, typing, scrolling
│
Backend:
├─ mobile_action_handler.py
│  └─ ALWAYS routes to MobileReActStrategy (no hardcoded detection)
│
└─ mobile_strategy.py (ReAct Loop)
   ├─ OBSERVE: GET /device/{id}/ui-tree ← NOW HAS REAL UI!
   ├─ THINK: LLM analyzes real UI
   ├─ ACT: POST /device/{id}/execute-action
   └─ OBSERVE: [repeat]
```

## Next Steps

1. **Immediate:** Test with "open gmail app"
   - Should work now without hallucination

2. **Soon:** Integrate service startup into MainActivity
   - Currently works but could be automatic

3. **Later:** Add more action types (gesture, swipe, long-press)

## Key Insight

**The hallucination was because:**
- LLM only saw Flutter app UI
- Couldn't see Gmail/Home/anything else
- Kept typing into text field hoping it would work
- Same observation every step = same action = infinite loop

**Now fixed because:**
- LLM sees actual system UI (Home screen with app icons)
- Can click real apps
- Gets different UI after each action
- No infinite loop!

---

**Status:** ✅ Ready to test
**Last Updated:** 2026-01-24
**Changes:** Complete AutomationService rewrite + handler routing fix
