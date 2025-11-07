import React, { useState, useCallback, useRef } from "react";
import { Mic, MicOff, Send, Loader2 } from "lucide-react";

// SpeechInput Component with recording functionality
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
          console.log(`📊 Audio chunk received: ${event.data.size} bytes`);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        console.log(`✅ Recording stopped. Total size: ${audioBlob.size} bytes`);
        setAudioBlob(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      console.log("✅ Recording started successfully");
    } catch (error) {
      console.error("❌ Error accessing microphone:", error);
      alert("Could not access microphone. Please check permissions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      console.log("🛑 Stopping recording...");
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleSubmitAudio = async () => {
    if (!audioBlob) return;
    
    console.log("📤 Preparing to submit audio for transcription...");
    try {
      // Convert blob to base64
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = async () => {
        const base64Audio = reader.result.split(',')[1];
        console.log(`✅ Audio converted to base64: ${base64Audio.length} characters`);
        onTranscript(base64Audio);
        setAudioBlob(null);
      };
    } catch (error) {
      console.error("❌ Error processing audio:", error);
    }
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex gap-3">
        <button
          onClick={isRecording ? stopRecording : startRecording}
          disabled={isLoading}
          className={`p-4 rounded-full transition-all duration-300 shadow-lg ${
            isRecording
              ? 'bg-red-500 hover:bg-red-600 animate-pulse'
              : 'bg-indigo-500 hover:bg-indigo-600'
          } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {isRecording ? (
            <MicOff className="w-6 h-6 text-white" />
          ) : (
            <Mic className="w-6 h-6 text-white" />
          )}
        </button>
        
        {audioBlob && !isRecording && (
          <button
            onClick={handleSubmitAudio}
            disabled={isLoading}
            className="p-4 rounded-full bg-green-500 hover:bg-green-600 transition-all duration-300 shadow-lg"
          >
            <Send className="w-6 h-6 text-white" />
          </button>
        )}
      </div>
      
      <p className="text-sm text-gray-400">
        {isRecording ? 'Recording... Click to stop' : audioBlob ? 'Click send to transcribe' : 'Click to start recording'}
      </p>
    </div>
  );
}

// Main App Component
function App() {
  const [agentResponse, setAgentResponse] = useState("Tap the mic or type your command.");
  const [userInput, setUserInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState("test-123");

  const [clarificationRequired, setClarificationRequired] = useState(false);
  const [clarificationQuestion, setClarificationQuestion] = useState("");
  const [clarificationResponseToId, setClarificationResponseToId] = useState(null);

  // Function to transcribe audio and process it through the agent pipeline
  const transcribeAudio = async (base64Audio) => {
    try {
      setIsLoading(true);
      setAgentResponse("🎤 Transcribing audio...");
      console.log("🔄 Sending audio to /transcribe endpoint...");

      // Step 1: Transcribe the audio
      const transcribeResponse = await fetch('http://localhost:8000/transcribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          audio_data: base64Audio,
          session_id: sessionId,
        }),
      });

      console.log(`📥 Transcription response status: ${transcribeResponse.status}`);
      const transcribeData = await transcribeResponse.json();

      if (transcribeResponse.ok) {
        const transcribedText = transcribeData.transcript || transcribeData.text;
        console.log(`✅ Transcription successful: "${transcribedText}"`);
        setUserInput(transcribedText);
        setAgentResponse(`📝 Transcribed: "${transcribedText}"\n\n🔄 Processing through agent pipeline...`);
        
        // Step 2: Send transcribed text through the same /process pipeline
        console.log("📤 Sending transcribed text to /process endpoint...");
        await processText(transcribedText);
      } else {
        const errorMsg = `Transcription error: ${transcribeData.detail || 'Unknown error'}`;
        console.error(`❌ ${errorMsg}`);
        setAgentResponse(errorMsg);
        setIsLoading(false);
      }
    } catch (error) {
      console.error("❌ Transcription network error:", error);
      setAgentResponse("Network error: Could not transcribe audio.");
      setIsLoading(false);
    }
  };

  // Function to process text through the agent pipeline
  const processText = async (text) => {
    const inputToSend = text.trim();
    if (!inputToSend) {
      console.log("⚠️ Empty input, skipping processing");
      setIsLoading(false);
      return;
    }

    console.log("📤 Processing text through agent pipeline:", inputToSend);
    console.log(`Session ID: ${sessionId}`);
    console.log(`Is clarification: ${!!clarificationResponseToId}`);

    try {
      const response = await fetch('http://localhost:8000/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          input: inputToSend,
          is_clarification: !!clarificationResponseToId,
        }),
      });
      
      console.log(`📥 Process response status: ${response.status}`);
      
      if (response.status === 202) {
        setAgentResponse("❓ Clarification required...");
      } else {
        setAgentResponse("⏳ Processing response...");
      }
      
      const data = await response.json();
      console.log("📦 Process response data:", data);

      if (response.ok) {
        // Handle successful response
        if (data.status === "clarification_needed") {
          console.log("❓ Clarification needed:", data.question);
          setClarificationRequired(true);
          setClarificationQuestion(data.question);
          setClarificationResponseToId(data.response_id);
          setAgentResponse(`❓ ${data.question}`);
        } else if (data.status === "completed") {
          console.log("✅ Task completed:", data.result);
          const resultText = typeof data.result === 'string' 
            ? data.result 
            : JSON.stringify(data.result, null, 2);
          setAgentResponse(`✅ Task completed!\n\n${resultText}`);
          setClarificationRequired(false);
          setClarificationResponseToId(null);
        } else {
          const responseText = data.text || data.payload?.text || JSON.stringify(data);
          console.log("📄 Response text:", responseText);
          setAgentResponse(responseText || "✅ Task submitted successfully. Awaiting status update.");
          setClarificationRequired(false);
          setClarificationResponseToId(null);
        }
      } else {
        // Handle error responses
        const errorMessage = data.detail || data.error || 'Internal Server Error';
        console.error(`❌ Error from server: ${errorMessage}`);
        setAgentResponse(`❌ Error: ${errorMessage}`);
      }
    } catch (error) {
      console.error("❌ Network error during processing:", error);
      setAgentResponse("❌ Network error: Could not connect to the YUSR backend.");
    } finally {
      setIsLoading(false);
      setUserInput("");
    }
  };

  // Function to handle sending text input
  const handleSend = useCallback(async (text) => {
    if (isLoading) {
      console.log("⚠️ Already processing, ignoring new request");
      return;
    }
    
    const inputToSend = text || userInput;
    if (!inputToSend.trim()) {
      console.log("⚠️ Empty input, cannot send");
      return;
    }

    console.log("🚀 User clicked send with input:", inputToSend);
    setIsLoading(true);
    setAgentResponse(`📤 Sending: "${inputToSend}"...`);
    
    await processText(inputToSend);
  }, [isLoading, userInput, sessionId, clarificationResponseToId]);

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      console.log("⌨️ Enter key pressed");
      handleSend(userInput);
    }
  };

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900">
      <div className="relative z-10 flex items-center justify-center min-h-screen text-white p-6">
        <div className="flex flex-col items-center max-w-4xl w-full">
          
          {/* Header */}
          <div className="text-center mb-10">
            <h1 className="text-6xl md:text-7xl font-extrabold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-pink-400 via-indigo-400 to-sky-400">
              YUSR
            </h1>
            <p className="text-lg text-gray-300">Your Unified Smart Reasoner</p>
            
            {/* Agent Response Box */}
            <div className="mt-6 p-6 rounded-2xl max-w-2xl mx-auto bg-white/10 backdrop-blur-md shadow-2xl border border-white/20">
              <p className="text-white font-medium text-left whitespace-pre-wrap">
                {isLoading && <Loader2 className="inline w-5 h-5 mr-2 animate-spin" />}
                {agentResponse}
              </p>
              {clarificationRequired && (
                <div className="mt-3 p-3 bg-yellow-500/20 rounded-lg border border-yellow-500/50">
                  <p className="text-sm text-yellow-200">⚠️ Clarification needed - please respond</p>
                </div>
              )}
            </div>
          </div>

          {/* Speech Input */}
          <div className="w-full max-w-2xl mb-8">
            <div className="backdrop-blur-md bg-white/10 rounded-2xl p-8 shadow-2xl border border-white/20">
              <SpeechInput 
                onTranscript={transcribeAudio} 
                isLoading={isLoading}
              />
            </div>
          </div>

          {/* Text Input */}
          <div className="w-full max-w-2xl">
            <div className="flex w-full space-x-3">
              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={isLoading ? "Processing..." : "Or type your command here..."}
                disabled={isLoading}
                className="flex-grow p-4 rounded-xl border border-gray-600/50 bg-gray-800/50 backdrop-blur-sm text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 shadow-lg transition duration-200"
              />
              <button
                onClick={() => handleSend(userInput)}
                disabled={isLoading || !userInput.trim()}
                className={`px-6 py-4 rounded-xl font-bold transition duration-300 shadow-lg min-w-[100px] flex items-center justify-center ${
                  isLoading || !userInput.trim()
                    ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                    : 'bg-indigo-500 hover:bg-indigo-400 active:bg-indigo-600 text-white'
                }`}
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  'Send'
                )}
              </button>
            </div>
            <p className="mt-3 text-sm text-gray-500 text-center">Session ID: {sessionId}</p>
          </div>

          {/* Footer */}
          <footer className="mt-12 text-gray-500 text-sm">
            Speak naturally — YUSR listens and acts.
          </footer>
        </div>
      </div>
    </div>
  );
}

export default App;