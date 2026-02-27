// App.jsx
import React, { useState, useRef, useEffect, useCallback } from "react";
import SpeechRecognition, { useSpeechRecognition } from "react-speech-recognition";
import Sidebar from "./components/SideBar";
import HeaderContent from "./components/HeaderContent";
import VoiceControls from "./components/VoiceControls";
import SettingsModal from "./components/SettingsModal";
import ThinkingIndicator from "./components/ThinkingIndicator";
import screenReader from "./utils/ScreenReader";
import { Mic, Pause, Square, Eye, Maximize2, Minus, X, Maximize, PictureInPicture2, ArrowUpRight } from "lucide-react";

function App() {
  /* ---------- STATE ---------- */
  const [orbState, setOrbState] = useState("idle");
  const [userMessage, setUserMessage] = useState("");
  const [assistantMessage, setAssistantMessage] = useState("");
  // const [sessionId] = useState("test-123");
  // ✅ USER ID - Generated ONCE per browser, persists forever
  const [userId] = useState(() => {
      const stored = localStorage.getItem("userId");
      if (stored) {
          console.log("[Auth] Using existing user ID:", stored);
          return stored;
      }
      
      const newUserId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem("userId", newUserId);
      console.log("[Auth] Created new user ID:", newUserId);
      return newUserId;
  });

  // ✅ SESSION ID - Generated ONCE per chat, persists until "New Chat" clicked
  const [sessionId] = useState(() => {
      const stored = localStorage.getItem("currentSessionId");
      if (stored) {
          console.log("[Session] Using existing session:", stored);
          return stored;
      }
      
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem("currentSessionId", newSessionId);
      console.log("[Session] Created new session:", newSessionId);
      return newSessionId;
  });
  const [clarificationResponseToId, setClarificationResponseToId] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [chatMode, setChatMode] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [deviceType, setDeviceType] = useState("desktop");
  const [ttsVoice, setTtsVoice] = useState(() => localStorage.getItem("ttsVoice") || "Gacrux");
  const [screenSize, setScreenSize] = useState("desktop");
  const [userName, setUserName] = useState("User");
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  // True when server-provided SSE thinking stream is connected
  const [sseConnected, setSseConnected] = useState(false);

  // WebSocket state
  const wsRef = useRef(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsReconnectTimer = useRef(null);

  // Execution mode: normal, transparent, or widget
  const [executionMode, setExecutionMode] = useState("normal");
  const [widgetText, setWidgetText] = useState("");
  const [contextSnapshot, setContextSnapshot] = useState(null);

  // Structured response state
  const [structuredResponse, setStructuredResponse] = useState(null);
  const [offerReadAloud, setOfferReadAloud] = useState(false);

  // Interrupt commands (EN + AR)
  const INTERRUPT_COMMANDS = {
    "aura stop": "stop", "aura pause": "pause", "aura undo": "stop",
    "aura resume": "resume", "aura continue": "resume",
    "أورا وقف": "stop", "أورا توقف": "stop", "أورا إيقاف": "stop",
    "أورا استمر": "resume", "أورا كمل": "resume", "أورا تراجع": "stop",
  };

  // Detected user language — set on first voice interaction, persists for session
  const [userLanguage, setUserLanguage] = useState(() => localStorage.getItem("userLanguage") || null);
  // Whether to vocalize thinking steps
  const [vocalizeSteps, setVocalizeSteps] = useState(true);
  // Ref to track the last spoken step index (avoid re-speaking)
  const lastSpokenStepRef = useRef(-1);
  // Ref for vocalizeStep so WS/SSE closures always get the latest version
  const vocalizeStepRef = useRef(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(new Audio());
  const audioContextRef = useRef(null);

  // Speech recognition (wake-word)
  const { transcript, interimTranscript, finalTranscript, resetTranscript, listening, browserSupportsSpeechRecognition } = useSpeechRecognition();

  // Start wake-word listening — use a language that can hear both EN and AR
  const startWakeWordListening = useCallback(() => {
    if (!browserSupportsSpeechRecognition) return;
    try {
      // Use empty string or a broad locale; Chrome will do best-effort multilingual detection.
      // We cycle between en-US and ar-SA every 30s to catch both, OR use the user's detected lang.
      const lang = userLanguage === 'ar' ? 'ar-SA' : 'en-US';
      SpeechRecognition.startListening({ continuous: true, language: lang, interimResults: true });
      console.log(`[Wake] Listening started (lang=${lang})`);
    } catch (e) {
      console.warn('[Wake] Failed to start listening:', e);
    }
  }, [browserSupportsSpeechRecognition, userLanguage]);

  // Ensure continuous listening starts on mount (if supported)
  useEffect(() => {
    if (!browserSupportsSpeechRecognition) {
      console.warn('[Wake] SpeechRecognition not supported by this browser');
      return;
    }

    startWakeWordListening();

    // Quick sanity-check: if recognition does not start within 1s, log a hint
    setTimeout(() => {
      if (!listening) {
        console.warn('[Wake] SpeechRecognition did not report listening=true. Browser may not allow continuous recognition in this context.');
      }
    }, 1000);

    return () => {
      try { SpeechRecognition.stopListening(); } catch (e) {}
    };
  }, [browserSupportsSpeechRecognition, startWakeWordListening]);

  // Detect wake word AND interrupt commands in speech (always active, even during processing)
  useEffect(() => {
    const combined = `${interimTranscript || ''} ${finalTranscript || ''} ${transcript || ''}`.toLowerCase().trim();
    if (!combined) return;

    // Log every detected phrase for debugging
    console.log(`[Wake-Debug] Heard: "${combined}"`);

    // Check for interrupt commands FIRST (these work during processing/speaking)
    for (const [phrase, command] of Object.entries(INTERRUPT_COMMANDS)) {
      if (combined.includes(phrase)) {
        console.log(`[Wake] Interrupt command detected: "${phrase}" → ${command}`);
        resetTranscript();
        sendInterrupt(command);
        return;
      }
    }

    // Wake word detection — English "aura" OR Arabic "أورا" / "اورا" / "أوره" / "اوره"
    const hasEnglishWake = /\baura\b/.test(combined);
    const hasArabicWake = /أورا|اورا|أوره|اوره|اورة|أورة/.test(combined);

    if (hasEnglishWake || hasArabicWake) {
      const detectedLang = hasArabicWake ? 'ar' : 'en';
      console.log(`[Wake] Wake word detected (${detectedLang}): "${combined}"`);

      // Remember user language on first wake word
      if (!userLanguage) {
        setUserLanguage(detectedLang);
        localStorage.setItem('userLanguage', detectedLang);
        console.log(`[Wake] User language set to: ${detectedLang}`);
      }

      resetTranscript();
      if (!isRecording && orbState !== 'processing' && orbState !== 'speaking') {
        startRecording();
      }
    }
  }, [interimTranscript, finalTranscript, transcript]);

  /* ---------- DEVICE DETECTION & RESPONSIVE LAYOUT ---------- */
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 768) {
        setScreenSize("mobile");
        setIsSidebarCollapsed(true);
      } else {
        setScreenSize("desktop");
      }
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  /* ---------- LOAD USERNAME FROM LOCALSTORAGE ---------- */
  useEffect(() => {
    const savedName = localStorage.getItem("userName");
    if (savedName) {
      setUserName(savedName);
    }
  }, []);

    /* ---------- CONNECT TO WEBSOCKET (primary) + SSE FALLBACK ---------- */
  const connectWebSocket = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected');
      setWsConnected(true);
      if (wsReconnectTimer.current) {
        clearTimeout(wsReconnectTimer.current);
        wsReconnectTimer.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log('[WS] Message:', msg.type);

        switch (msg.type) {
          case 'thinking_step':
            setThinkingSteps(prev => {
              if (prev.includes(msg.step)) return prev;
              return [...prev, msg.step];
            });
            if (vocalizeStepRef.current) vocalizeStepRef.current(msg.step);
            setIsThinking(true);
            break;

          case 'clarification':
            setThinkingSteps([]);
            setIsThinking(false);
            setClarificationResponseToId(msg.response_id);
            setAssistantMessage(msg.question);
            // Use client-side TTS
            setOrbState("speaking");
            screenReader.speak(msg.question, {
              onComplete: () => setOrbState("idle")
            });
            break;

          case 'completion':
          case 'structured_response': {
            setThinkingSteps([]);
            setIsThinking(false);
            setClarificationResponseToId(null);
            
            const responseText = msg.spoken_text || msg.response || msg.text || "Task completed";
            setAssistantMessage(responseText);

            // Handle structured response
            if (msg.structured_response || msg.type === 'structured_response') {
              const sr = msg.structured_response || msg;
              setStructuredResponse(sr);
              setOfferReadAloud(sr.offer_read_aloud === true);
              
              if (sr.full_content && sr.full_content !== responseText) {
                // Store full content for read-aloud
                setStructuredResponse(prev => ({ ...prev, full_content: sr.full_content }));
              }
            }

            // Speak the response with client-side TTS
            setOrbState("speaking");
            screenReader.speak(responseText, {
              onComplete: () => {
                setOrbState("idle");
                // Exit transparent mode when task completes
                setExecutionMode(prev => prev === "transparent" ? "normal" : prev);
              }
            });
            break;
          }

          case 'interrupt_ack':
            console.log('[WS] Interrupt acknowledged:', msg.command);
            if (msg.command === 'stop') {
              screenReader.stop();
              setOrbState("idle");
              setIsThinking(false);
              setThinkingSteps([]);
              setAssistantMessage(`Stopped. ${msg.command === 'stop' ? 'Task cancelled.' : ''}`);
              // Exit widget if auto-triggered
              if (autoWidgetTriggeredRef.current) {
                window.electronAPI?.exitWidgetMode?.();
                autoWidgetTriggeredRef.current = false;
              }
              setExecutionMode("normal");
            } else if (msg.command === 'pause') {
              setAssistantMessage("Paused. Say 'AURA resume' to continue.");
            } else if (msg.command === 'resume') {
              setAssistantMessage("Resuming...");
            }
            break;

          case 'context_snapshot':
            if (msg.snapshot) {
              setContextSnapshot(msg.snapshot);
              console.log('[WS] Context snapshot saved for undo');
            }
            break;

          case 'proactive_prompt':
            setAssistantMessage(msg.spoken_text || msg.text);
            setOrbState("speaking");
            screenReader.speak(msg.spoken_text || msg.text, {
              onComplete: () => setOrbState("idle")
            });
            break;

          case 'error':
            setThinkingSteps([]);
            setIsThinking(false);
            setAssistantMessage(msg.detail || "An error occurred");
            setOrbState("idle");
            break;

          default:
            console.log('[WS] Unknown message type:', msg.type);
        }
      } catch (err) {
        console.warn('[WS] Failed to parse message:', err);
      }
    };

    ws.onclose = () => {
      console.log('[WS] Disconnected');
      setWsConnected(false);
      // Auto-reconnect after 3s
      wsReconnectTimer.current = setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.warn('[WS] Error:', err);
      ws.close();
    };
  }, [sessionId]); // Do NOT include executionMode — it would tear down the WS connection on mode change

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (wsReconnectTimer.current) clearTimeout(wsReconnectTimer.current);
    };
  }, [connectWebSocket]);

  // SSE Fallback - only used when WebSocket is not connected
  useEffect(() => {
    if (wsConnected) return; // Skip SSE when WS is active

    const eventSource = new EventSource(`http://localhost:8000/thinking-stream/${sessionId}`);

    eventSource.onopen = () => {
      console.log('[SSE] Connected to thinking stream');
      setSseConnected(true);
    };

    // Robust SSE handler allowing JSON or plain text steps
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Handle explicit clear events from server
        if (data.action === 'thinking_clear') {
          setThinkingSteps([]);
          setIsThinking(false);
          return;
        }

        if (data.step) {
          setThinkingSteps(prev => [...prev, data.step]);
          setIsThinking(true);
          if (vocalizeStepRef.current) vocalizeStepRef.current(data.step);
        } else if (Array.isArray(data.steps)) {
          setThinkingSteps(data.steps);
          setIsThinking(data.steps.length > 0);
          // Speak only the last step from batch
          if (data.steps.length > 0 && vocalizeStepRef.current) vocalizeStepRef.current(data.steps[data.steps.length - 1]);
        }
      } catch (err) {
        console.warn("[UI] Non-JSON SSE payload:", event.data);
        if (event.data && typeof event.data === 'string' && event.data.trim().length > 0) {
          setThinkingSteps(prev => [...prev, event.data]);
          setIsThinking(true);
          if (vocalizeStepRef.current) vocalizeStepRef.current(event.data);
        }
      }
    };

    eventSource.onerror = (err) => {
      console.warn('[SSE] Thinking stream disconnected or errored:', err);
      setSseConnected(false);
      eventSource.close();
    };

    return () => {
      setSseConnected(false);
      eventSource.close();
    };
  }, [sessionId, wsConnected]);

  /* ---------- VOCALIZE THINKING STEP (local TTS) ---------- */
  const vocalizeStep = useCallback((text) => {
    if (!vocalizeSteps || !text) return;
    try {
      // Cancel previous step utterance so they don't queue up
      window.speechSynthesis.cancel();
      const isArabic = /[\u0600-\u06FF]/.test(text);
      const lang = isArabic ? 'ar' : (userLanguage || 'en');
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang === 'ar' ? 'ar-SA' : 'en-US';
      utterance.rate = 1.2;
      utterance.volume = 0.7;
      const voices = window.speechSynthesis.getVoices();
      const matchVoice = voices.find(v => v.lang.startsWith(lang)) || voices[0];
      if (matchVoice) utterance.voice = matchVoice;
      window.speechSynthesis.speak(utterance);
      console.log(`[TTS-Step] Speaking: "${text}" (${lang})`);
    } catch (e) {
      console.warn('[TTS-Step] Failed:', e);
    }
  }, [vocalizeSteps, userLanguage]);

  // Keep ref in sync so WS/SSE closures always use the latest
  useEffect(() => { vocalizeStepRef.current = vocalizeStep; }, [vocalizeStep]);

  /* ---------- HANDLE THINKING UPDATES ---------- */
  const handleThinkingUpdate = (step) => {
    console.log("[UI] Updating thinking step:", step);
    setThinkingSteps(prev => {
      // Avoid duplicates
      if (prev.includes(step)) return prev;
      return [...prev, step];
    });
    vocalizeStep(step);
    // Ensure thinking indicator is visible
    setIsThinking(true);
  };

  /* ---------- UI ACTIONS ---------- */
  const handleCancel = () => {
    console.log("[UI] Cancel pressed → switching to chat mode");
    setOrbState("idle");
    setUserMessage("");
    setChatMode(true);
  };

  // const handleNewChat = () => {
  //   console.log("[UI] New chat started");
  //   setUserMessage("");
  //   setAssistantMessage("");
  //   setThinkingSteps([]);
  //   setIsThinking(false);
  //   setChatMode(false);
  // };

  const handleNewChat = async () => {
    console.log("[UI] New chat started");
    
    // ✅ Generate NEW session ID (but keep same user ID)
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("currentSessionId", newSessionId);
    console.log("[Session] New session created:", newSessionId);
    
    // Clear UI state
    setUserMessage("");
    setAssistantMessage("");
    setThinkingSteps([]);
    setIsThinking(false);
    setChatMode(false);
    
    // ✅ Notify backend to clear OLD session
    try {
        const response = await fetch("http://localhost:8000/new-chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,  // OLD session to clear
                user_id: userId,        // SAME user
            }),
        });
        
        if (response.ok) {
            console.log("✅ Backend session cleared");
            // ✅ RELOAD PAGE to use new session ID
            window.location.reload();
        }
    } catch (error) {
        console.error("❌ Failed to notify backend:", error);
        // Even if backend fails, still reload to use new session
        window.location.reload();
    }
};

  /* ---------- THINKING STEPS SIMULATION ---------- */
  const startThinkingSequence = async () => {
    // If server is sending real-time thinking updates, do not simulate locally
    if (sseConnected) {
      console.info('[Thinking] Server-side thinking active; skipping local simulation');
      return;
    }

    setThinkingSteps([]);
    setIsThinking(true);
    const steps = ["Searching...", "Analyzing...", "Processing...", "Responding..."];
    
    for (let i = 0; i < steps.length; i++) {
      setThinkingSteps(prev => [...prev, steps[i]]);
      vocalizeStep(steps[i]);
      await new Promise(resolve => setTimeout(resolve, 800));
    }
    
    setIsThinking(false);
  };

  /* ---------- AUDIO RECORDING ---------- */
  const startRecording = async () => {
    try {
      console.log("[Audio] Starting recording...");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);

      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        console.log(`[Audio] Recording stopped. Size: ${blob.size} bytes`);
        stream.getTracks().forEach((t) => t.stop());

        // Stop and clear audio context if used
        if (audioContextRef.current) {
          try { audioContextRef.current.close(); } catch (e) {}
          audioContextRef.current = null;
        }

        processAudio(blob);

        // Resume wake-word listening after processing audio
        try {
          startWakeWordListening();
          console.log('[Wake] Resumed wake-word listening');
        } catch (e) {
          console.warn('[Wake] Failed to resume listening:', e);
        }
      };

      recorder.start();
      setIsRecording(true);
      setOrbState("listening");
      setUserMessage("Listening...");

      // Silence detection using Web Audio API
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const audioCtx = new AudioCtx();
        audioContextRef.current = audioCtx;
        const sourceNode = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 2048;
        sourceNode.connect(analyser);
        const bufferLength = analyser.fftSize;
        const dataArray = new Uint8Array(bufferLength);
        let silentStart = null;

        const checkSilence = () => {
          analyser.getByteTimeDomainData(dataArray);
          let sum = 0;
          for (let i = 0; i < bufferLength; i++) {
            const v = (dataArray[i] - 128) / 128;
            sum += v * v;
          }
          const rms = Math.sqrt(sum / bufferLength);
          if (rms < 0.01) {
            if (silentStart === null) silentStart = Date.now();
            else if (Date.now() - silentStart > 5000) {
              console.log('[Audio] Silence detected >5s, stopping recording');
              if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
                mediaRecorderRef.current.stop();
              }
            }
          } else {
            silentStart = null;
          }
          if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            requestAnimationFrame(checkSilence);
          } else {
            try { audioCtx.close(); } catch (e) {}
          }
        };

        requestAnimationFrame(checkSilence);
      } catch (e) {
        console.warn('[Audio] Silence detection not available:', e);
      }
    } catch (error) {
      console.error("[Audio] Microphone access failed:", error);
      setAssistantMessage("Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      console.log("[Audio] Stopping recording...");
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleMicClick = () => {
    console.log("[UI] Mic clicked. State:", orbState);
    // Allow mic during processing/speaking for interrupt commands
    isRecording ? stopRecording() : startRecording();
  };

  /* ---------- AUDIO → TEXT ---------- */
  const processAudio = async (blob) => {
    try {
      setOrbState("processing");
      setUserMessage("Processing...");
      console.log("[STT] Transcribing audio...");

      const reader = new FileReader();
      reader.readAsDataURL(blob);

      reader.onloadend = async () => {
        const base64 = reader.result.split(",")[1];

        const res = await fetch("http://localhost:8000/transcribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audio_data: base64,
            session_id: sessionId,
            user_id: userId,
          }),
        });

        const data = await res.json();
        console.log("[STT] Response:", data);

        if (!res.ok) {
          throw new Error(data.detail || "Transcription failed");
        }

        console.log(`[STT] Transcript: "${data.transcript}"`);
        setUserMessage(data.transcript);
        await processText(data.transcript);
      };
    } catch (error) {
      console.error("[STT] Error:", error);
      setOrbState("idle");
      setAssistantMessage("Transcription failed");
    }
  };

  /* ---------- DIRECT TEXT (SKIP STT) ---------- */
  const handleTextSubmit = async (text) => {
    try {
      console.log("[UI] Text submitted:", text);

      setOrbState("processing");
      setUserMessage(text);
      setThinkingSteps([]);
      setIsThinking(false);

      // Skip STT completely → go directly to agent
      await processText(text);

    } catch (error) {
      console.error("[UI] Text submit error:", error);
      setOrbState("idle");
      setAssistantMessage("Failed to send message");
    }
  };

  /* ---------- SETTINGS & STOP DETECTION ---------- */
  const handleSettingsClick = () => {
    setShowSettings(!showSettings);
  };

  const handleSettingsSave = (profileData) => {
    console.log("[Settings] Saving profile:", profileData);
    localStorage.setItem("userName", profileData.username);
    setUserName(profileData.username);

    // Persist TTS voice if provided
    if (profileData.voice) {
      localStorage.setItem("ttsVoice", profileData.voice);
      setTtsVoice(profileData.voice);
    }
  };

  /* ---------- INTERRUPT COMMANDS ---------- */
  const sendInterrupt = useCallback((command) => {
    console.log(`[Interrupt] Sending: ${command}`);
    
    // Immediately stop local TTS if speaking
    if (command === 'stop') {
      screenReader.stop();
    } else if (command === 'pause') {
      screenReader.pause();
    } else if (command === 'resume') {
      screenReader.resume();
    }

    // Send to backend via WebSocket
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "interrupt",
        command: command,
        user_id: userId,
      }));
    } else {
      // Fallback: HTTP POST
      fetch("http://localhost:8000/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          user_id: userId,
          input: `AURA ${command}`,
          device_type: deviceType,
        }),
      }).catch(err => console.warn('[Interrupt] HTTP fallback failed:', err));
    }
  }, [sessionId, userId, deviceType]);

  /* ---------- READ ALOUD FULL CONTENT ---------- */
  const handleReadAloud = useCallback(() => {
    if (structuredResponse?.full_content) {
      setOrbState("speaking");
      screenReader.speak(structuredResponse.full_content, {
        onProgress: (current, total) => {
          console.log(`[TTS] Reading sentence ${current}/${total}`);
        },
        onComplete: () => setOrbState("idle")
      });
    }
  }, [structuredResponse]);

  /* ---------- TEXT → AGENT ---------- */
  const processText = async (text) => {
    try {
      console.log("[Agent] Processing input:", text);

      // Check for interrupt commands in text input too
      const lowerText = text.toLowerCase().trim();
      for (const [phrase, command] of Object.entries(INTERRUPT_COMMANDS)) {
        if (lowerText.includes(phrase) || lowerText === command) {
          console.log(`[Agent] Interrupt command in text: "${phrase}" → ${command}`);
          sendInterrupt(command);
          return;
        }
      }

      // Detect "stop" command (legacy)
      if (lowerText === "stop" || lowerText === "aura stop") {
        console.log("[Agent] STOP command detected");
        sendInterrupt("stop");
        handleStopSequence();
        return;
      }

      // Detect settings request
      if (
        lowerText.includes("settings") ||
        lowerText.includes("open settings") ||
        lowerText.includes("show settings")
      ) {
        console.log("[Agent] Settings request detected");
        setShowSettings(true);
        setAssistantMessage("Opening settings for you");
        return;
      }

      console.log("[Agent] Clarification mode:", !!clarificationResponseToId);

      // Enter transparent execution mode during processing
      setExecutionMode("transparent");

      // Send via WebSocket if connected, fallback to HTTP
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        const msgType = clarificationResponseToId ? "clarification_response" : "user_input";
        const payload = {
          type: msgType,
          user_id: userId,
          device_type: deviceType,
        };
        if (clarificationResponseToId) {
          payload.answer = text;
          payload.clarification_id = clarificationResponseToId;
        } else {
          payload.text = text;
        }
        wsRef.current.send(JSON.stringify(payload));
        console.log(`[WS] Sent ${msgType}:`, text);
      } else {
        // HTTP fallback
        console.log("[Agent] Using HTTP fallback (WS not connected)");
        if (!sseConnected) await startThinkingSequence();

        const res = await fetch("http://localhost:8000/process", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            user_id: userId,
            input: text,
            is_clarification: !!clarificationResponseToId,
            clarification_id: clarificationResponseToId || null,
            device_type: deviceType,
          }),
        });

        console.log("[Agent] Status:", res.status);
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Backend error");

        setThinkingSteps([]);
        setIsThinking(false);

        if (data.status === "clarification_needed") {
          setClarificationResponseToId(data.response_id);
          setAssistantMessage(data.question);
          setOrbState("speaking");
          screenReader.speak(data.question, {
            onComplete: () => setOrbState("idle")
          });
        } else {
          const responseText = data.text || data.result?.response || data.result || "Task completed";
          setClarificationResponseToId(null);
          setAssistantMessage(responseText);
          setOrbState("speaking");
          screenReader.speak(responseText, {
            onComplete: () => {
              setOrbState("idle");
              setExecutionMode("normal");
            }
          });
        }
      }
    } catch (error) {
      console.error("[Agent] Error:", error);
      setOrbState("idle");
      setAssistantMessage("Backend error");
      setThinkingSteps([]);
      setIsThinking(false);
      setExecutionMode("normal");
    }
  };

  /* ---------- STOP SEQUENCE ---------- */
  const handleStopSequence = () => {
    console.log("[System] Executing stop sequence");
    screenReader.stop(); // Stop client-side TTS
    stopRecording();
    setOrbState("idle");
    setUserMessage("");
    setAssistantMessage("Stop sequence initiated");
    setIsRecording(false);
    setChatMode(false);
    setShowSettings(false);
    setThinkingSteps([]);
    setIsThinking(false);
    setStructuredResponse(null);
    setOfferReadAloud(false);
    // Exit widget if auto-triggered
    if (autoWidgetTriggeredRef.current) {
      window.electronAPI?.exitWidgetMode?.();
      autoWidgetTriggeredRef.current = false;
    }
    setExecutionMode("normal");
  };

  /* ---------- EXECUTION MODE TOGGLE ---------- */
  const toggleExecutionMode = useCallback(() => {
    setExecutionMode(prev => prev === "normal" ? "transparent" : "normal");
  }, []);

  const enterWidgetMode = useCallback(() => {
    window.electronAPI?.enterWidgetMode?.();
    setExecutionMode("widget");
  }, []);

  const exitWidgetMode = useCallback(() => {
    window.electronAPI?.exitWidgetMode?.();
    setExecutionMode("normal");
  }, []);

  /* ---------- TEXT → SPEECH (Client-side via ScreenReader) ---------- */
  const speakResponse = async (text) => {
    try {
      console.log("[TTS] Speaking via client-side ScreenReader:", text?.substring(0, 50));
      setOrbState("speaking");
      await screenReader.speak(text, {
        onComplete: () => {
          console.log("[TTS] Playback finished");
          setOrbState("idle");
        }
      });
    } catch (error) {
      console.error("[TTS] Error:", error);
      setOrbState("idle");
    }
  };


  /* ---------- AUTO WIDGET / FULLSCREEN TOGGLE ---------- */
  // Track previous orbState to detect transitions
  const prevOrbStateRef = useRef(orbState);
  const autoWidgetTriggeredRef = useRef(false);

  useEffect(() => {
    const prevState = prevOrbStateRef.current;
    prevOrbStateRef.current = orbState;

    const wasIdle = prevState === "idle" || prevState === "listening";
    const isNowExecuting = orbState === "processing";

    // Auto-enter widget when execution starts (only from idle/listening)
    if (wasIdle && isNowExecuting && executionMode === "normal") {
      console.log("[Auto-Widget] Execution started → entering widget mode");
      window.electronAPI?.enterWidgetMode?.();
      setExecutionMode("widget");
      autoWidgetTriggeredRef.current = true;
    }
  }, [orbState, executionMode]);

  // Auto-exit widget when execution finishes (only if we auto-entered)
  useEffect(() => {
    const isNowIdle = orbState === "idle" && !isThinking;
    if (isNowIdle && executionMode === "widget" && autoWidgetTriggeredRef.current) {
      console.log("[Auto-Widget] Execution done → exiting widget mode");
      window.electronAPI?.exitWidgetMode?.();
      setExecutionMode("normal");
      autoWidgetTriggeredRef.current = false;
    }
  }, [orbState, isThinking, executionMode]);

  /* ---------- RENDER ---------- */
  const isExecuting = orbState === "processing" || orbState === "speaking" || isThinking;
  const appClassName = [
    "app-root",
    executionMode === "transparent" && isExecuting ? "transparent-mode" : "",
    executionMode === "widget" ? "widget-mode" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={appClassName}>
      {/* ===== Title bar (custom — frameless window) ===== */}
      {executionMode !== "widget" && (
        <div className="titlebar">
          <div className="titlebar-drag">
            <span className="titlebar-title">AURA</span>
          </div>
          <div className="titlebar-buttons">
            {isExecuting && (
              <button
                className="titlebar-btn titlebar-mode"
                onClick={toggleExecutionMode}
                title={executionMode === "normal" ? "Go transparent" : "Back to normal"}
              >
                {executionMode === "normal" ? <Eye size={14} /> : <Maximize2 size={14} />}
              </button>
            )}
            <button className="titlebar-btn" onClick={enterWidgetMode} title="Minimize to widget">
              <PictureInPicture2 size={14} />
            </button>
            <button className="titlebar-btn" onClick={() => window.electronAPI?.minimizeWindow?.()} title="Minimize">
              <Minus size={14} />
            </button>
            <button className="titlebar-btn" onClick={() => window.electronAPI?.maximizeWindow?.()} title="Maximize">
              <Maximize size={14} />
            </button>
            <button className="titlebar-btn titlebar-close" onClick={() => window.electronAPI?.closeWindow?.()} title="Close">
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* ===== Widget mini-player ===== */}
      {executionMode === "widget" && (
        <div className="widget-player">
          {/* Drag handle */}
          <div className="widget-drag-strip" />

          {/* Left: Orb + Status */}
          <div className="widget-left">
            <div className={`widget-orb orb-${orbState}`}>
              {orbState === "processing" ? "⚡" : orbState === "speaking" ? "🔊" : "●"}
            </div>
            <div className="widget-status-text">
              {isExecuting
                ? (isThinking
                    ? (thinkingSteps.length > 0 ? thinkingSteps[thinkingSteps.length - 1] : "Thinking...")
                    : assistantMessage
                      ? (assistantMessage.length > 40 ? assistantMessage.slice(0, 40) + "…" : assistantMessage)
                      : "Processing...")
                : "AURA"}
            </div>
          </div>

          {/* Center: Input area */}
          <div className="widget-input-area">
            {!isExecuting ? (
              <>
                <input
                  className="widget-text-input"
                  type="text"
                  placeholder="Ask AURA..."
                  value={widgetText}
                  onChange={(e) => setWidgetText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && widgetText.trim()) {
                      handleTextSubmit(widgetText);
                      setWidgetText("");
                    }
                  }}
                />
                <button
                  className="widget-mic-btn"
                  onClick={handleMicClick}
                  title={isRecording ? "Stop recording" : "Voice input"}
                >
                  <Mic size={16} />
                </button>
              </>
            ) : (
              <div className="widget-exec-controls">
                <button
                  className="widget-action-btn widget-pause"
                  onClick={() => sendInterrupt("pause")}
                  title="Pause"
                >
                  <Pause size={14} />
                </button>
                <button
                  className="widget-action-btn widget-stop"
                  onClick={() => sendInterrupt("stop")}
                  title="Stop"
                >
                  <Square size={14} />
                </button>
              </div>
            )}
          </div>

          {/* Right: Window controls */}
          <div className="widget-window-controls">
            <button className="widget-win-btn" onClick={exitWidgetMode} title="Expand">
              <ArrowUpRight size={14} />
            </button>
            <button className="widget-win-btn widget-win-close" onClick={() => window.electronAPI?.closeWindow?.()} title="Close">
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      <Sidebar
        collapsed={isSidebarCollapsed || executionMode === "widget"}
        onToggle={() => {
          console.log("[UI] Sidebar toggled");
          setIsSidebarCollapsed((p) => !p);
        }}
        onSettingsClick={handleSettingsClick}
        onNewChat={handleNewChat}
      />

      <main className={`main-area ${isSidebarCollapsed && screenSize === "mobile" ? "mobile-sidebar-open" : ""}`}>
        <video autoPlay muted loop playsInline>
          <source src="/Background3.mp4" type="video/mp4" />
        </video>
        
        <div className="main-overlay">
          <HeaderContent userName={userName} />

          {/* Thinking Indicator */}
          {isThinking && <ThinkingIndicator steps={thinkingSteps} />}

          {/* Response Display Area */}
          {assistantMessage && !isThinking && (
            <div className="response-container" role="status" aria-live="polite" aria-atomic="true" aria-label="Assistant response">
              <div className="response-message">
                {assistantMessage}
              </div>
              {/* Read Aloud offer */}
              {offerReadAloud && structuredResponse?.full_content && (
                <button 
                  className="read-aloud-btn"
                  onClick={handleReadAloud}
                  title="Read full content aloud"
                >
                  🔊 Read Aloud
                </button>
              )}
            </div>
          )}

          {/* VoiceControls stay at the bottom */}
          <VoiceControls
            isRecording={isRecording}
            orbState={orbState}
            onMicClick={handleMicClick}
            onCancel={handleCancel}
            chatMode={chatMode}
            setChatMode={setChatMode}
            onSendText={handleTextSubmit}
            onSettingsClick={handleSettingsClick}
            isExecuting={isExecuting}
            onInterrupt={sendInterrupt}
          />
        </div>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <SettingsModal 
          onClose={() => setShowSettings(false)} 
          onSave={handleSettingsSave}
          initialName={userName}
          initialVoice={ttsVoice}
        />
      )}
    </div>
  );
}

export default App;