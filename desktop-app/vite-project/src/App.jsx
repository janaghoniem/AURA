import React, { useState, useCallback, useRef, useEffect } from "react";
import { Loader2 } from "lucide-react";

// Animated Orb Component
function AnimatedOrb({ state, onClick, isDisabled }) {
  return (
    <div className="relative flex items-center justify-center">
      {/* Listening State - Rotating gradient ring */}
      {state === 'listening' && (
        <>
          <div className="absolute w-80 h-80 rounded-full animate-spin-slow">
            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-cyan-400 via-purple-500 to-pink-500 blur-xl opacity-60"></div>
          </div>
          <div className="absolute w-72 h-72 rounded-full animate-spin-reverse">
            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-pink-500 via-purple-500 to-cyan-400 blur-lg opacity-40"></div>
          </div>
        </>
      )}
      
      {/* Processing State - Black hole effect */}
      {state === 'processing' && (
        <>
          <div className="absolute w-96 h-96 rounded-full animate-pulse-slow">
            <div className="absolute inset-0 rounded-full bg-gradient-radial from-transparent via-purple-900/30 to-purple-500/50 blur-2xl"></div>
          </div>
          <div className="absolute w-80 h-80 rounded-full animate-spin-slow">
            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-transparent via-indigo-500/40 to-transparent blur-xl"></div>
          </div>
        </>
      )}
      
      {/* Speaking State - Pulsing waves */}
      {state === 'speaking' && (
        <>
          <div className="absolute w-80 h-80 rounded-full animate-pulse-wave">
            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 blur-xl opacity-50"></div>
          </div>
          <div className="absolute w-72 h-72 rounded-full animate-pulse-wave-delayed">
            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-pink-400 via-purple-400 to-blue-400 blur-lg opacity-40"></div>
          </div>
          <div className="absolute w-64 h-64 rounded-full animate-pulse-wave-delayed-2">
            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 blur-md opacity-30"></div>
          </div>
        </>
      )}
      
      {/* Core Orb */}
      <button
        onClick={onClick}
        disabled={isDisabled}
        className={`relative z-10 w-48 h-48 rounded-full transition-all duration-500 ${
          isDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:scale-105'
        } ${
          state === 'idle' ? 'bg-gradient-to-br from-purple-600 to-indigo-700' :
          state === 'listening' ? 'bg-gradient-to-br from-cyan-500 to-purple-600' :
          state === 'processing' ? 'bg-gradient-to-br from-purple-900 to-black' :
          'bg-gradient-to-br from-blue-500 to-purple-600'
        } shadow-2xl`}
      >
        <div className="absolute inset-2 rounded-full bg-gradient-to-br from-white/10 to-transparent"></div>
      </button>
    </div>
  );
}

// Message Bubble Component
function MessageBubble({ text, isUser }) {
  return (
    <div className={`${isUser ? 'ml-auto' : 'mr-auto'} max-w-md`}>
      <div className={`px-6 py-4 rounded-3xl backdrop-blur-xl ${
        isUser 
          ? 'bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30' 
          : 'bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30'
      }`}>
        <p className="text-white/90 text-sm leading-relaxed">{text}</p>
      </div>
    </div>
  );
}

// Task Item Component
function TaskItem({ task, index }) {
  return (
    <div className="group px-4 py-3 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all duration-300">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-6 h-6 mt-0.5 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-xs text-white font-medium">
          {index + 1}
        </div>
        <div className="flex-1">
          <p className="text-white/80 text-sm leading-relaxed">{task}</p>
        </div>
      </div>
    </div>
  );
}

// Main App Component
function App() {
  const [orbState, setOrbState] = useState('idle'); // idle, listening, processing, speaking
  const [userMessage, setUserMessage] = useState("Tap the orb to speak");
  const [assistantMessage, setAssistantMessage] = useState("I'm ready to help you");
  const [tasks, setTasks] = useState([
    "Open calculator",
    "Check the weather",
    "Set a reminder"
  ]);
  
  const [sessionId] = useState("test-123");
  const [clarificationResponseToId, setClarificationResponseToId] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(new Audio());

  // Handle orb click
  const handleOrbClick = async () => {
    if (orbState === 'processing' || orbState === 'speaking') return;
    
    if (orbState === 'idle' || orbState === 'listening') {
      if (!isRecording) {
        // Start recording
        startRecording();
      } else {
        // Stop recording and process
        stopRecording();
      }
    }
  };

  // Start audio recording
  const startRecording = async () => {
    try {
      console.log("Starting recording...");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        console.log(`Recording stopped. Size: ${audioBlob.size} bytes`);
        setAudioBlob(audioBlob);
        stream.getTracks().forEach(track => track.stop());
        
        // Automatically process the audio
        processAudio(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setOrbState('listening');
      setUserMessage("Listening...");
    } catch (error) {
      console.error("Error accessing microphone:", error);
      setAssistantMessage("Could not access microphone");
    }
  };

  // Stop audio recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      console.log("Stopping recording...");
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // Process audio
  const processAudio = async (blob) => {
    try {
      setOrbState('processing');
      setUserMessage("Processing...");
      console.log("Transcribing audio...");

      // Convert to base64
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      reader.onloadend = async () => {
        const base64Audio = reader.result.split(',')[1];
        
        // Transcribe
        const transcribeResponse = await fetch('http://localhost:8000/transcribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audio_data: base64Audio, session_id: sessionId }),
        });

        const transcribeData = await transcribeResponse.json();

        if (transcribeResponse.ok) {
          const transcript = transcribeData.transcript;
          console.log(`Transcribed: "${transcript}"`);
          setUserMessage(transcript);
          
          // Process through agent
          await processText(transcript);
        } else {
          setAssistantMessage(`Transcription failed: ${transcribeData.detail}`);
          setOrbState('idle');
        }
      };
    } catch (error) {
      console.error("Transcription error:", error);
      setAssistantMessage("Network error during transcription");
      setOrbState('idle');
    }
  };

  // Process text through agent pipeline
  const processText = async (text) => {
    try {
      console.log("Processing:", text);
      console.log("Is clarification response:", !!clarificationResponseToId);

      const response = await fetch('http://localhost:8000/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          input: text,
          is_clarification: !!clarificationResponseToId,
          clarification_id: clarificationResponseToId || null,
        }),
      });

      console.log("Response status:", response.status);
      const data = await response.json();
      console.log("Full response data:", JSON.stringify(data, null, 2));

      if (response.ok) {
        if (data.status === "clarification_needed") {
          console.log("Clarification needed:", data.question);
          setClarificationResponseToId(data.response_id);
          setAssistantMessage(data.question);
          
          // Speak and play TTS
          await speakResponse(data.question);
          
        } else if (data.status === "completed") {
          console.log("Task completed:", data);
          
          let responseText = "";
          if (data.text) {
            responseText = data.text;
          } else if (data.result) {
            responseText = typeof data.result === 'string' 
              ? data.result 
              : (data.result.response || data.result.result || JSON.stringify(data.result, null, 2));
          } else {
            responseText = "Task completed successfully";
          }
          
          console.log("Extracted response text:", responseText);
          setAssistantMessage(responseText);
          setClarificationResponseToId(null);
          
          // Speak and play TTS
          await speakResponse(responseText);
          
        } else {
          console.log("Other response type:", data.status);
          const responseText = data.text || data.response || data.payload?.text || JSON.stringify(data);
          console.log("Response text:", responseText);
          
          setAssistantMessage(responseText);
          setClarificationResponseToId(null);
          
          // Speak and play TTS
          await speakResponse(responseText);
        }
      } else {
        console.error("Error response from server");
        const errorMsg = data.detail || data.error || 'Server error';
        setAssistantMessage(`Error: ${errorMsg}`);
        setClarificationResponseToId(null);
        setOrbState('idle');
      }
    } catch (error) {
      console.error("Process error:", error);
      setAssistantMessage("Network error: Could not connect to backend");
      setClarificationResponseToId(null);
      setOrbState('idle');
    }
  };

  // Speak response with TTS
  const speakResponse = async (text) => {
    try {
      setOrbState('speaking');
      console.log("Generating TTS for:", text);

      const response = await fetch('http://localhost:8000/text-to-speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_name: "Gacrux" }),
      });

      const data = await response.json();

      if (response.ok) {
        console.log("TTS received, playing audio...");
        
        const audioBlob = await fetch(`data:audio/wav;base64,${data.audio_data}`).then(r => r.blob());
        const audioUrl = URL.createObjectURL(audioBlob);
        
        audioRef.current.src = audioUrl;
        audioRef.current.onended = () => {
          URL.revokeObjectURL(audioUrl);
          setOrbState('idle');
          console.log("Audio playback finished");
        };
        
        await audioRef.current.play();
      } else {
        console.error("TTS failed:", data.detail);
        setOrbState('idle');
      }
    } catch (error) {
      console.error("TTS error:", error);
      setOrbState('idle');
    }
  };

  return (
    <div className="min-h-screen bg-black text-white p-6 overflow-hidden">
      <style>{`
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes spin-reverse {
          from { transform: rotate(360deg); }
          to { transform: rotate(0deg); }
        }
        @keyframes pulse-slow {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.05); }
        }
        @keyframes pulse-wave {
          0%, 100% { opacity: 0; transform: scale(0.8); }
          50% { opacity: 0.5; transform: scale(1.2); }
        }
        @keyframes pulse-wave-delayed {
          0%, 100% { opacity: 0; transform: scale(0.85); }
          50% { opacity: 0.4; transform: scale(1.15); }
        }
        @keyframes pulse-wave-delayed-2 {
          0%, 100% { opacity: 0; transform: scale(0.9); }
          50% { opacity: 0.3; transform: scale(1.1); }
        }
        .animate-spin-slow { animation: spin-slow 8s linear infinite; }
        .animate-spin-reverse { animation: spin-reverse 6s linear infinite; }
        .animate-pulse-slow { animation: pulse-slow 3s ease-in-out infinite; }
        .animate-pulse-wave { animation: pulse-wave 2s ease-in-out infinite; }
        .animate-pulse-wave-delayed { animation: pulse-wave-delayed 2s ease-in-out infinite 0.3s; }
        .animate-pulse-wave-delayed-2 { animation: pulse-wave-delayed-2 2s ease-in-out infinite 0.6s; }
        .bg-gradient-radial { background: radial-gradient(circle, var(--tw-gradient-stops)); }
      `}</style>

      <div className="max-w-[1800px] mx-auto h-screen flex gap-6">
        {/* Main Interface - 80% */}
        <div className="flex-[8] bg-gradient-to-br from-gray-900/50 to-gray-800/50 rounded-3xl backdrop-blur-xl border border-white/10 p-8 flex flex-col">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-5xl font-light tracking-wider mb-2">YUSR</h1>
            <p className="text-white/50 text-sm tracking-wide">Your Personal Assistant</p>
          </div>

          {/* Orb Container */}
          <div className="flex-1 flex items-center justify-center">
            <AnimatedOrb 
              state={orbState} 
              onClick={handleOrbClick}
              isDisabled={orbState === 'processing' || orbState === 'speaking'}
            />
          </div>

          {/* Message Bubbles */}
          <div className="space-y-4 min-h-[200px]">
            <MessageBubble text={userMessage} isUser={true} />
            <MessageBubble text={assistantMessage} isUser={false} />
          </div>
        </div>

        {/* Tasks Panel - 20% */}
        <div className="flex-[2] bg-gradient-to-br from-gray-900/50 to-gray-800/50 rounded-3xl backdrop-blur-xl border border-white/10 p-6 flex flex-col">
          <h2 className="text-xl font-light tracking-wide mb-6 text-white/80">Tasks</h2>
          
          <div className="flex-1 space-y-3 overflow-y-auto">
            {tasks.map((task, index) => (
              <TaskItem key={index} task={task} index={index} />
            ))}
          </div>

          <div className="mt-6 pt-4 border-t border-white/10">
            <p className="text-xs text-white/40 text-center">Session: {sessionId}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;