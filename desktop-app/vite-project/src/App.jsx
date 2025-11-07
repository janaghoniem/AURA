import React, { useState, useCallback, useRef, useEffect } from "react";
import { Mic, MicOff, Send, Loader2, Volume2, User, Bot } from "lucide-react";

// SpeechInput Component
function SpeechInput({ onTranscript, isLoading }) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const startRecording = async () => {
    try {
      console.log("🎤 Starting audio recording...");
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
        console.log(`✅ Recording stopped. Size: ${audioBlob.size} bytes`);
        setAudioBlob(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error("❌ Error accessing microphone:", error);
      alert("Could not access microphone. Please check permissions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleSubmitAudio = async () => {
    if (!audioBlob) return;
    
    try {
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = async () => {
        const base64Audio = reader.result.split(',')[1];
        onTranscript(base64Audio);
        setAudioBlob(null);
      };
    } catch (error) {
      console.error("❌ Error processing audio:", error);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={isLoading}
        className={`p-3 rounded-full transition-all duration-300 ${
          isRecording
            ? 'bg-red-500 hover:bg-red-600 animate-pulse'
            : 'bg-indigo-500 hover:bg-indigo-600'
        } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        {isRecording ? (
          <MicOff className="w-5 h-5 text-white" />
        ) : (
          <Mic className="w-5 h-5 text-white" />
        )}
      </button>
      
      {audioBlob && !isRecording && (
        <button
          onClick={handleSubmitAudio}
          disabled={isLoading}
          className="p-3 rounded-full bg-green-500 hover:bg-green-600 transition-all"
        >
          <Send className="w-5 h-5 text-white" />
        </button>
      )}
    </div>
  );
}

// Chat Message Component
function ChatMessage({ message, onPlayAudio }) {
  const isUser = message.role === 'user';
  
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} mb-4`}>
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? 'bg-indigo-500' : 'bg-purple-500'
      }`}>
        {isUser ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
      </div>
      
      <div className={`flex-1 ${isUser ? 'text-right' : 'text-left'}`}>
        <div className={`inline-block max-w-[80%] p-4 rounded-2xl ${
          isUser 
            ? 'bg-indigo-500 text-white' 
            : 'bg-white/10 text-white border border-white/20'
        }`}>
          <p className="whitespace-pre-wrap">{message.text}</p>
          
          {!isUser && message.hasAudio && (
            <button
              onClick={() => onPlayAudio(message.text)}
              className="mt-2 flex items-center gap-2 text-sm opacity-70 hover:opacity-100 transition"
            >
              <Volume2 className="w-4 h-4" />
              Play Audio
            </button>
          )}
        </div>
        
        {message.status && (
          <p className="text-xs text-gray-400 mt-1 px-2">
            {message.status}
          </p>
        )}
      </div>
    </div>
  );
}

// Main App Component
function App() {
  const [messages, setMessages] = useState([
    { id: 1, role: 'assistant', text: 'Welcome! How can I help you today?', hasAudio: false }
  ]);
  const [userInput, setUserInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [sessionId] = useState("test-123");
  const [clarificationResponseToId, setClarificationResponseToId] = useState(null);
  
  const chatContainerRef = useRef(null);
  const audioRef = useRef(new Audio());

  // Auto-scroll to bottom
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  // Function to play TTS audio
  const playAudio = async (text) => {
    if (isPlayingAudio) {
      console.log("⚠️ Audio already playing");
      return;
    }

    try {
      setIsPlayingAudio(true);
      console.log("🔊 Generating TTS for:", text);

      const response = await fetch('http://localhost:8000/text-to-speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_name: "Gacrux" }),
      });

      const data = await response.json();

      if (response.ok) {
        console.log("✅ TTS received, playing audio...");
        
        // Convert base64 to blob
        const audioBlob = await fetch(`data:audio/wav;base64,${data.audio_data}`).then(r => r.blob());
        const audioUrl = URL.createObjectURL(audioBlob);
        
        audioRef.current.src = audioUrl;
        audioRef.current.onended = () => {
          URL.revokeObjectURL(audioUrl);
          setIsPlayingAudio(false);
          console.log("✅ Audio playback finished");
        };
        
        await audioRef.current.play();
      } else {
        console.error("❌ TTS failed:", data.detail);
        setIsPlayingAudio(false);
      }
    } catch (error) {
      console.error("❌ TTS error:", error);
      setIsPlayingAudio(false);
    }
  };

  // Add message to chat
  const addMessage = (role, text, status = null, hasAudio = false) => {
    const newMessage = {
      id: Date.now(),
      role,
      text,
      status,
      hasAudio
    };
    setMessages(prev => [...prev, newMessage]);
    return newMessage;
  };

  // Transcribe audio and send
  const transcribeAudio = async (base64Audio) => {
    try {
      setIsLoading(true);
      console.log("🔄 Transcribing audio...");

      const response = await fetch('http://localhost:8000/transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_data: base64Audio, session_id: sessionId }),
      });

      const data = await response.json();

      if (response.ok) {
        const transcript = data.transcript;
        console.log(`✅ Transcribed: "${transcript}"`);
        
        // Add user message
        addMessage('user', transcript);
        
        // Process through agent pipeline
        await processText(transcript);
      } else {
        addMessage('assistant', `❌ Transcription failed: ${data.detail}`, 'error');
        setIsLoading(false);
      }
    } catch (error) {
      console.error("❌ Transcription error:", error);
      addMessage('assistant', '❌ Network error during transcription', 'error');
      setIsLoading(false);
    }
  };

  // Process text through agent pipeline
  const processText = async (text) => {
    try {
      console.log("📤 Processing:", text);
      console.log("🔑 Clarification ID:", clarificationResponseToId);

      const response = await fetch('http://localhost:8000/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          input: text,
          is_clarification: !!clarificationResponseToId,
        }),
      });

      console.log("📥 Response status:", response.status);
      const data = await response.json();
      console.log("📦 Full response data:", JSON.stringify(data, null, 2));

      if (response.ok) {
        if (data.status === "clarification_needed") {
          // Clarification required
          console.log("❓ Clarification needed:", data.question);
          setClarificationResponseToId(data.response_id);
          addMessage('assistant', data.question, 'clarification needed', true);
          
          // Auto-play TTS
          console.log("🔊 Auto-playing clarification TTS...");
          await playAudio(data.question);
          
        } else if (data.status === "completed") {
          // Task completed
          console.log("✅ Task completed:", data);
          
          // Extract text from response
          let responseText = "";
          if (data.text) {
            responseText = data.text;
          } else if (data.result) {
            responseText = typeof data.result === 'string' 
              ? data.result 
              : (data.result.response || data.result.result || JSON.stringify(data.result, null, 2));
          } else {
            responseText = "Task completed successfully!";
          }
          
          console.log("📝 Extracted response text:", responseText);
          
          addMessage('assistant', responseText, 'completed', true);
          setClarificationResponseToId(null);
          
          // Auto-play TTS
          console.log("🔊 Auto-playing completion TTS...");
          await playAudio(responseText);
          
        } else {
          // Other response
          console.log("📄 Other response type:", data.status);
          const responseText = data.text || data.response || data.payload?.text || JSON.stringify(data);
          console.log("📝 Response text:", responseText);
          
          addMessage('assistant', responseText, null, true);
          setClarificationResponseToId(null);
          
          // Auto-play TTS
          console.log("🔊 Auto-playing response TTS...");
          await playAudio(responseText);
        }
      } else {
        console.error("❌ Error response from server");
        const errorMsg = data.detail || data.error || 'Server error';
        addMessage('assistant', `❌ Error: ${errorMsg}`, 'error');
      }
    } catch (error) {
      console.error("❌ Process error:", error);
      console.error("❌ Error stack:", error.stack);
      addMessage('assistant', '❌ Network error: Could not connect to backend', 'error');
    } finally {
      setIsLoading(false);
      setUserInput("");
    }
  };

  // Handle text send
  const handleSend = useCallback(() => {
    if (isLoading || !userInput.trim()) return;
    
    console.log("🚀 Sending:", userInput);
    setIsLoading(true);
    
    // Add user message
    addMessage('user', userInput);
    
    // Process
    processText(userInput);
  }, [isLoading, userInput]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-4xl h-[90vh] flex flex-col bg-gray-800/50 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/10">
        
        {/* Header */}
        <div className="p-6 border-b border-white/10">
          <h1 className="text-4xl font-extrabold text-center bg-clip-text text-transparent bg-gradient-to-r from-pink-400 via-indigo-400 to-sky-400">
            YUSR
          </h1>
          <p className="text-center text-gray-400 text-sm mt-1">Your Unified Smart Reasoner</p>
        </div>

        {/* Chat Messages */}
        <div 
          ref={chatContainerRef}
          className="flex-1 overflow-y-auto p-6 space-y-4"
        >
          {messages.map(msg => (
            <ChatMessage 
              key={msg.id} 
              message={msg} 
              onPlayAudio={playAudio}
            />
          ))}
          
          {isLoading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="bg-white/10 p-4 rounded-2xl border border-white/20">
                <Loader2 className="w-5 h-5 animate-spin text-white" />
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-6 border-t border-white/10">
          <div className="flex gap-3 items-center">
            <SpeechInput 
              onTranscript={transcribeAudio}
              isLoading={isLoading}
            />
            
            <input
              type="text"
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={isLoading ? "Processing..." : "Type your message..."}
              disabled={isLoading}
              className="flex-1 p-3 rounded-xl bg-gray-700/50 text-white placeholder-gray-400 border border-gray-600/50 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400 outline-none"
            />
            
            <button
              onClick={handleSend}
              disabled={isLoading || !userInput.trim()}
              className={`p-3 rounded-xl transition ${
                isLoading || !userInput.trim()
                  ? 'bg-gray-600 cursor-not-allowed'
                  : 'bg-indigo-500 hover:bg-indigo-600'
              }`}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 text-white animate-spin" />
              ) : (
                <Send className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
          
          <p className="text-xs text-gray-500 text-center mt-3">
            {isPlayingAudio ? '🔊 Playing audio...' : `Session: ${sessionId}`}
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;