import React, { useState, useRef } from "react";
import Sidebar from "./components/SideBar";
import HeaderContent from "./components/HeaderContent";
import VoiceControls from "./components/VoiceControls";

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

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(new Audio());

  /* ---------- UI ACTIONS ---------- */
  const handleCancel = () => {
    console.log("[UI] Cancel pressed → switching to chat mode");
    setOrbState("idle");
    setUserMessage("");
    setChatMode(true);
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

      // Skip STT completely → go directly to agent
      await processText(text);

    } catch (error) {
      console.error("[UI] Text submit error:", error);
      setOrbState("idle");
      setAssistantMessage("Failed to send message");
    }
  };

  /* ---------- TEXT → AGENT ---------- */
  const processText = async (text) => {
    try {
      console.log("[Agent] Processing input:", text);
      console.log(
        "[Agent] Clarification mode:",
        !!clarificationResponseToId
      );

      const res = await fetch("http://localhost:8000/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          input: text,
          is_clarification: !!clarificationResponseToId,
          clarification_id: clarificationResponseToId || null,
        }),
      });

      console.log("[Agent] Status:", res.status);
      const data = await res.json();
      console.log("[Agent] Full response:", data);

      if (!res.ok) {
        throw new Error(data.detail || "Backend error");
      }

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
    }
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

      // Convert base64 to blob correctly
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
      />

      <main className="main-area">
        <div className="main-overlay">
          {/* Header stays at the top */}
          <HeaderContent />

          <div className="chat-display-area">
            {userMessage && (
              <div className="message-item user">
                <div className="message-avatar">U</div>
                <div className="message-bubble">
                  {userMessage}
                </div>
              </div>
            )}
            
            {assistantMessage && (
              <div className="message-item assistant">
                <div className="message-avatar" style={{ background: 'transparent', border: '1px solid #7a1fa2' }}>
                  ✨
                </div>
                <div className="message-bubble">
                  {assistantMessage}
                </div>
              </div>
            )}
          </div>

          {/* VoiceControls stay at the bottom */}
          <VoiceControls
            isRecording={isRecording}
            orbState={orbState}
            onMicClick={handleMicClick}
            onCancel={handleCancel}
            chatMode={chatMode}
            setChatMode={setChatMode}
            onSendText={handleTextSubmit}
          />
        </div>
      </main>
    </div>
  );
}

export default App;
