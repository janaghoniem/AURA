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
        className={`relative z-10 w-48 h-48 rounded-full transition-all duration-500 ${isDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:scale-105'
          } ${state === 'idle' ? 'bg-gradient-to-br from-purple-600 to-indigo-700' :
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

// Message Bubble Component with speech bubble tail
function MessageBubble({ text, isUser }) {
  return (
    <div className={`${isUser ? 'ml-auto' : 'mr-auto'} max-w-md relative`}>


      <div className="px-6 py-4 rounded-3xl backdrop-blur-xl bg-white/5 border border-white/10">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] uppercase tracking-widest text-white/40 font-light">
            {isUser ? 'You' : 'YUSR'}
          </span>
        </div>
        <p className="text-white/90 text-sm leading-relaxed">{text}</p>
      </div>
    </div>
  );
}

// Task Item Component with checkbox
function TaskItem({ task, onToggle, completed }) {
  return (
    <div className="group px-4 py-3 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all duration-300">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggle}
          className="flex-shrink-0 w-5 h-5 rounded border-2 border-white/30 hover:border-white/50 transition-colors flex items-center justify-center"
        >
          {completed && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </button>
        <p className={`text-white/80 text-sm leading-relaxed flex-1 ${completed ? 'line-through opacity-50' : ''}`}>
          {task}
        </p>
      </div>
    </div>
  );
}

// Main App Component
function App() {
  const [orbState, setOrbState] = useState('idle');
  const [userMessage, setUserMessage] = useState("Tap the orb to speak");
  const [assistantMessage, setAssistantMessage] = useState("I'm ready to help you");
  const [tasks, setTasks] = useState([
    { text: "Get Started!", completed: false },

  ]);
  const [newTaskInput, setNewTaskInput] = useState("");

  const [sessionId] = useState("test-123");
  const [clarificationResponseToId, setClarificationResponseToId] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(new Audio());

  // Add new task
  const handleAddTask = (e) => {
    e.preventDefault();
    if (newTaskInput.trim()) {
      setTasks([...tasks, { text: newTaskInput.trim(), completed: false }]);
      setNewTaskInput("");
    }
  };

  // Toggle task completion
  const handleToggleTask = (index) => {
    setTasks(tasks.map((task, i) =>
      i === index ? { ...task, completed: !task.completed } : task
    ));
  };

  // Handle orb click
  const handleOrbClick = async () => {
    if (orbState === 'processing' || orbState === 'speaking') return;

    if (orbState === 'idle' || orbState === 'listening') {
      if (!isRecording) {
        startRecording();
      } else {
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

      const reader = new FileReader();
      reader.readAsDataURL(blob);
      reader.onloadend = async () => {
        const base64Audio = reader.result.split(',')[1];

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

          await speakResponse(responseText);

        } else {
          console.log("Other response type:", data.status);
          const responseText = data.text || data.response || data.payload?.text || JSON.stringify(data);
          console.log("Response text:", responseText);

          setAssistantMessage(responseText);
          setClarificationResponseToId(null);

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

  // Speak response with TTS - synced with orb animation
  const speakResponse = async (text) => {
    try {
      console.log("Generating TTS for:", text);

      const response = await fetch('http://localhost:8000/text-to-speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_name: "Gacrux" }),
      });

      const data = await response.json();

      if (response.ok) {
        console.log("TTS received, preparing audio...");

        const audioBlob = await fetch(`data:audio/wav;base64,${data.audio_data}`).then(r => r.blob());
        const audioUrl = URL.createObjectURL(audioBlob);

        audioRef.current.src = audioUrl;

        // Set speaking state ONLY when audio is ready to play
        audioRef.current.oncanplaythrough = async () => {
          console.log("Audio ready, starting playback...");
          setOrbState('speaking');

          try {
            await audioRef.current.play();
            console.log("Audio playing now");
          } catch (playError) {
            console.error("Play error:", playError);
            setOrbState('idle');
          }
        };

        audioRef.current.onended = () => {
          URL.revokeObjectURL(audioUrl);
          setOrbState('idle');
          console.log("Audio playback finished");
        };

        audioRef.current.onerror = (error) => {
          console.error("Audio error:", error);
          URL.revokeObjectURL(audioUrl);
          setOrbState('idle');
        };

        // Load the audio
        audioRef.current.load();

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
    <div className="min-h-screen relative bg-[#05010A] text-white p-6 overflow-hidden">
      <style>{`
        /* Background gradients - left and right */
        .night-gradient-right {
          background: radial-gradient(
            circle at 120% 50%,
            rgba(120, 80, 200, 0.35) 0%,
            rgba(20, 10, 40, 0.1) 40%,
            transparent 100%
          );
        }
        
        .night-gradient-left {
          background: radial-gradient(
            circle at -20% 50%,
            rgba(80, 60, 180, 0.3) 0%,
            rgba(20, 10, 40, 0.08) 40%,
            transparent 100%
          );
        }

        /* Improved star field - scattered all over */
        .stars {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background-image: 
            /* Center stars */
            radial-gradient(1.5px 1.5px at 50% 20%, #fff, transparent),
            radial-gradient(1px 1px at 60% 30%, #eee, transparent),
            radial-gradient(2px 2px at 40% 40%, #fff, transparent),
            radial-gradient(1px 1px at 55% 50%, #eee, transparent),
            radial-gradient(1.5px 1.5px at 45% 60%, #fff, transparent),
            radial-gradient(1px 1px at 50% 70%, #eee, transparent),
            radial-gradient(2px 2px at 60% 80%, #fff, transparent),
            
            /* Left side stars */
            radial-gradient(1.5px 1.5px at 20% 25%, #fff, transparent),
            radial-gradient(1px 1px at 15% 35%, #eee, transparent),
            radial-gradient(2px 2px at 25% 45%, #fff, transparent),
            radial-gradient(1px 1px at 10% 55%, #eee, transparent),
            radial-gradient(1.5px 1.5px at 30% 65%, #fff, transparent),
            radial-gradient(1px 1px at 20% 75%, #eee, transparent),
            radial-gradient(2px 2px at 15% 85%, #fff, transparent),
            
            /* Right side stars */
            radial-gradient(1.5px 1.5px at 80% 15%, #fff, transparent),
            radial-gradient(1px 1px at 85% 25%, #eee, transparent),
            radial-gradient(2px 2px at 75% 35%, #fff, transparent),
            radial-gradient(1px 1px at 90% 45%, #eee, transparent),
            radial-gradient(1.5px 1.5px at 70% 55%, #fff, transparent),
            radial-gradient(1px 1px at 80% 65%, #eee, transparent),
            radial-gradient(2px 2px at 85% 75%, #fff, transparent),
            
            /* Additional scattered stars */
            radial-gradient(1px 1px at 35% 10%, #eee, transparent),
            radial-gradient(1.5px 1.5px at 65% 90%, #fff, transparent),
            radial-gradient(1px 1px at 5% 50%, #eee, transparent),
            radial-gradient(2px 2px at 95% 40%, #fff, transparent),
            radial-gradient(1px 1px at 30% 85%, #eee, transparent),
            radial-gradient(1.5px 1.5px at 70% 5%, #fff, transparent),
            radial-gradient(1px 1px at 90% 95%, #eee, transparent),
            radial-gradient(2px 2px at 10% 15%, #fff, transparent);
          background-repeat: no-repeat;
          opacity: 0.6;
          animation: twinkle 8s infinite ease-in-out alternate;
          pointer-events: none;
        }

        @keyframes twinkle {
          0% { opacity: 0.4; }
          50% { opacity: 0.8; }
          100% { opacity: 0.6; }
        }
        
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
      
      {/* Apply both gradients + star field */}
      <div className="absolute inset-0 night-gradient-right"></div>
      <div className="absolute inset-0 night-gradient-left"></div>
      <div className="stars"></div>

      <div className="max-w-[1800px] mx-auto h-screen flex gap-6">
        {/* Main Interface - 80% */}
        <div className="flex-[8] bg-white/[0.02] rounded-3xl backdrop-blur-xl border border-white/10 p-8 flex flex-col">
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
        <div className="flex-[2] bg-white/[0.02] rounded-3xl backdrop-blur-xl border border-white/10 p-6 flex flex-col">
          <h2 className="text-xl font-light tracking-wide mb-6 text-white/80">Tasks</h2>

          {/* Task Input */}
          <form onSubmit={handleAddTask} className="mb-6">
            <textarea
              value={newTaskInput}
              onChange={(e) => setNewTaskInput(e.target.value)}
              placeholder="Add tasks (one per line)..."
              className="w-full px-4 py-3 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-white/30 text-sm resize-none focus:outline-none focus:border-white/20 transition-colors"
              rows="3"
            />
            <button
              type="submit"
              className="mt-2 w-full px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 text-sm transition-all duration-300"
            >
              Add Task
            </button>
          </form>

          {/* Task List */}
          <div className="flex-1 space-y-3 overflow-y-auto">
            {tasks.map((task, index) => (
              <TaskItem
                key={index}
                task={task.text}
                completed={task.completed}
                onToggle={() => handleToggleTask(index)}
              />
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