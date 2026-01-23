import React, { useState, useRef, useEffect } from "react";
import Sidebar from "./components/SideBar";
import HeaderContent from "./components/HeaderContent";
import VoiceControls from "./components/VoiceControls";
import SettingsModal from "./components/SettingsModal";
import ThinkingIndicator from "./components/ThinkingIndicator";

function App() {
  /* ---------- STATE ---------- */
  const [orbState, setOrbState] = useState("idle");
  const [userMessage, setUserMessage] = useState("");
  const [assistantMessage, setAssistantMessage] = useState("");
  const [sessionId] = useState("test-123");
  const [clarificationResponseToId, setClarificationResponseToId] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [chatMode, setChatMode] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [deviceType, setDeviceType] = useState("desktop");
  const [userName, setUserName] = useState("Labubu");
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [isThinking, setIsThinking] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(new Audio());

  /* ---------- DEVICE DETECTION & RESPONSIVE LAYOUT ---------- */
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 768) {
        setDeviceType("mobile");
        setIsSidebarCollapsed(true);
      } else {
        setDeviceType("desktop");
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

    /* ---------- CONNECT TO THINKING STREAM ---------- */
  useEffect(() => {
    const eventSource = new EventSource(`http://localhost:8000/thinking-stream/${sessionId}`);
    
    // Inside your useEffect for SSE
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.steps) {
        setThinkingSteps(data.steps); // This now receives ['Step 1', 'Step 2']
      }
    };
    
    eventSource.onerror = () => {
      console.warn("[UI] Thinking stream disconnected");
      eventSource.close();
    };
    
    return () => eventSource.close();
  }, [sessionId]);

  /* ---------- HANDLE THINKING UPDATES ---------- */
  const handleThinkingUpdate = (step) => {
    console.log("[UI] Updating thinking step:", step);
    setThinkingSteps(prev => {
      // Avoid duplicates
      if (prev.includes(step)) return prev;
      return [...prev, step];
    });
    
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

  const handleNewChat = () => {
    console.log("[UI] New chat started");
    setUserMessage("");
    setAssistantMessage("");
    setThinkingSteps([]);
    setIsThinking(false);
    setChatMode(false);
  };

  /* ---------- THINKING STEPS SIMULATION ---------- */
  const startThinkingSequence = async () => {
    setIsThinking(true);
    const steps = ["Searching...", "Analyzing...", "Processing...", "Responding..."];
    
    for (let i = 0; i < steps.length; i++) {
      setThinkingSteps(prev => [...prev, steps[i]]);
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
        processAudio(blob);
      };

      recorder.start();
      setIsRecording(true);
      setOrbState("listening");
      setUserMessage("Listening...");
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
    if (orbState === "processing" || orbState === "speaking") return;
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
  };

  /* ---------- TEXT → AGENT ---------- */
  const processText = async (text) => {
    try {
      console.log("[Agent] Processing input:", text);

      // Detect "stop" command
      if (text.toLowerCase().includes("stop")) {
        console.log("[Agent] STOP command detected - initiating stop sequence");
        handleStopSequence();
        return;
      }

      // Detect settings request
      if (
        text.toLowerCase().includes("settings") ||
        text.toLowerCase().includes("open settings") ||
        text.toLowerCase().includes("show settings")
      ) {
        console.log("[Agent] Settings request detected");
        setShowSettings(true);
        setAssistantMessage("Opening settings for you");
        return;
      }

      console.log("[Agent] Clarification mode:", !!clarificationResponseToId);

      // Start thinking sequence
      await startThinkingSequence();

      const res = await fetch("http://localhost:8000/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          input: text,
          is_clarification: !!clarificationResponseToId,
          clarification_id: clarificationResponseToId || null,
          device_type: deviceType,
        }),
      });

      console.log("[Agent] Status:", res.status);
      const data = await res.json();
      console.log("[Agent] Full response:", data);

      if (!res.ok) {
        throw new Error(data.detail || "Backend error");
      }

      setThinkingSteps([]);
      setIsThinking(false);

      if (data.status === "clarification_needed") {
        console.log("[Agent] Clarification requested:", data.question);
        setClarificationResponseToId(data.response_id);
        setAssistantMessage(data.question);
        await speakResponse(data.question);
      } else {
        const responseText =
          data.text ||
          data.result?.response ||
          data.result ||
          "Task completed";

        console.log("[Agent] Final response:", responseText);
        setClarificationResponseToId(null);
        setAssistantMessage(responseText);
        await speakResponse(responseText);
      }
    } catch (error) {
      console.error("[Agent] Error:", error);
      setOrbState("idle");
      setAssistantMessage("Backend error");
      setThinkingSteps([]);
      setIsThinking(false);
    }
  };

  /* ---------- STOP SEQUENCE ---------- */
  const handleStopSequence = () => {
    console.log("[System] Executing stop sequence");
    stopRecording();
    setOrbState("idle");
    setUserMessage("");
    setAssistantMessage("Stop sequence initiated");
    setIsRecording(false);
    setChatMode(false);
    setShowSettings(false);
    setThinkingSteps([]);
    setIsThinking(false);
  };

  /* ---------- TEXT → SPEECH ---------- */
  const speakResponse = async (text) => {
    try {
      console.log("[TTS] Generating speech for:", text);

      const res = await fetch("http://localhost:8000/text-to-speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          voice_name: "Gacrux",
        }),
      });

      const data = await res.json();
      console.log("[TTS] Response received");

      if (!res.ok) {
        throw new Error(data.detail || "TTS failed");
      }

      const binaryString = atob(data.audio_data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const audioBlob = new Blob([bytes], { type: "audio/wav" });

      const url = URL.createObjectURL(audioBlob);
      console.log("[TTS] Audio blob created, URL:", url);
      
      audioRef.current.src = url;

      audioRef.current.oncanplaythrough = async () => {
        console.log("[TTS] Audio ready, playing...");
        setOrbState("speaking");
        await audioRef.current.play().catch(err => {
          console.error("[TTS] Play error:", err);
        });
      };

      audioRef.current.onended = () => {
        console.log("[TTS] Playback finished");
        URL.revokeObjectURL(url);
        setOrbState("idle");
      };

      audioRef.current.onerror = (err) => {
        console.error("[TTS] Audio error:", err);
        setOrbState("idle");
      };

      audioRef.current.load();
    } catch (error) {
      console.error("[TTS] Error:", error);
      setOrbState("idle");
    }
  };

  /* ---------- RENDER ---------- */
  return (
    <div className="app-root">
      <Sidebar
        collapsed={isSidebarCollapsed}
        onToggle={() => {
          console.log("[UI] Sidebar toggled");
          setIsSidebarCollapsed((p) => !p);
        }}
        onSettingsClick={handleSettingsClick}
        onNewChat={handleNewChat}
      />

      <main className={`main-area ${isSidebarCollapsed && deviceType === "mobile" ? "mobile-sidebar-open" : ""}`}>
        <video autoPlay muted loop playsInline>
          <source src="/Background3.mp4" type="video/mp4" />
        </video>
        
        <div className="main-overlay">
          {/* Header stays at the top */}
          <HeaderContent userName={userName} />

          {/* Thinking Indicator */}
          {isThinking && <ThinkingIndicator steps={thinkingSteps} />}

          {/* Response Display Area - Gemini Style */}
          {assistantMessage && !isThinking && (
            <div className="response-container">
              <div className="response-message">
                {assistantMessage}
              </div>
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
          />
        </div>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <SettingsModal 
          onClose={() => setShowSettings(false)} 
          onSave={handleSettingsSave}
          initialName={userName}
        />
      )}
    </div>
  );
}

export default App;