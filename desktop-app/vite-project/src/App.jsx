import React, { useState, useCallback } from "react";
import SplashBurst from "./components/SplashBurst";
import GradientBlobs from "./components/GradientBlobs";
import SpeechInput from "./components/SpeechInput";

function App() {

  const [showSplash, setShowSplash] = useState(false);
  const [agentResponse, setAgentResponse] = useState("Tap the mic or type your command.");
  const [userInput, setUserInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState("test-123"); // Keep session ID constant for testing

  const [clarificationRequired, setClarificationRequired] = useState(false);
  const [clarificationQuestion, setClarificationQuestion] = useState("");
  const [clarificationResponseToId, setClarificationResponseToId] = useState(null);

  // Function to handle sending the message to the backend
  // This is the function that performs the POST request to http://localhost:8000/process 
  const handleSend = useCallback(async (text) => {
      const inputToSend = text.trim();
      if (isLoading || !inputToSend) return;

      console.log("Sending to backend:", inputToSend);
      setIsLoading(true);
      setAgentResponse(`Sending: "${inputToSend}"...`);

      try {
          const response = await fetch('http://localhost:8000/process', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                  session_id: sessionId,
                  input: inputToSend,
              }),
          });
          setAgentResponse(response.status === 202 ? "Clarification required..." : "Processing response...");
          const data = await response.json();

          if (response.ok) {
              // Handle successful response
              const responseText = data.text || data.payload?.text || JSON.stringify(data);
              setAgentResponse(responseText || "Task submitted successfully. Awaiting status update.");
          } else if (response.status === 202) { // Status 202: Clarification
                setClarificationRequired(true);
                setClarificationQuestion(data.question);
                setClarificationResponseToId(data.response_id); // Save the ID to respond to
                setAgentResponse(data.question);
          } else {
              // Handle API error response
              const errorMessage = data.detail || (data.text ? `Error: ${data.text}` : 'Internal Server Error');
              setAgentResponse(`Error: ${errorMessage}`);
          }

      } catch (error) {
          console.error("Fetch Error:", error);
          setAgentResponse("Network error: Could not connect to the YUSR backend.");
      } finally {
          setIsLoading(false);
          setUserInput(""); // Clear input field after sending
      }
  }, [isLoading, sessionId]);

  // Handler for text input (can be used by the SpeechInput component too)
  // const handleTranscript = useCallback((text) => {
  //     // Updated to use handleSend for consistency, mirroring the behavior of the new button
  //     handleSend(text);
  // }, [handleSend]);


  // const handleKeyPress = (e) => {
  //     if (e.key === 'Enter') {
  //         handleSend(userInput);
  //     }
  // };

  return (
    <div className="relative min-h-screen">
      {/* {showSplash && (
        <SplashBurst onComplete={() => setShowSplash(false)} />
      )} */}

      {!showSplash && (
        <>
          <GradientBlobs />
          <div className="relative z-10 flex items-center justify-center min-h-screen text-white p-6">
            <div className="flex flex-col items-center">
              
              {/* Application Text Block */}
              <div className="text-center mb-10">
                <h1 className="text-5xl font-extrabold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-pink-400 to-indigo-400">
                    YUSR
                </h1>
                <p className="text-lg text-gray-300">Your intelligent accessibility assistant.</p>
                <div className="mt-4 p-4 rounded-xl max-w-lg bg-white/10 backdrop-blur-sm shadow-xl">
                    <p className="text-white font-medium">Agent: {agentResponse}</p>
                </div>
              </div>

              {/* Speech Input Component (Placed directly below the text) */}
              <div className="w-full max-w-2xl mb-8 flex flex-col items-center">
                            
                {/* Original Speech Input (Kept for completeness but disabled UI-wise) */}
                {/* NOTE: If you restore the actual SpeechInput component, ensure its onTranscript prop calls handleSend(text) */}
                {/* <SpeechInput onTranscript={handleTranscript} /> */}
                
                {/* Text Chat Input: THE REQUESTED UI */}
                <div className="flex w-full mt-4 space-x-2">
                    <input
                        type="text"
                        value={userInput}
                        onChange={(e) => setUserInput(e.target.value)}
                        // onKeyPress={handleKeyPress}
                        placeholder={isLoading ? "Processing..." : "Type your command here..."}
                        disabled={isLoading}
                        className="flex-grow p-3 rounded-xl border border-gray-700 bg-gray-800 text-white placeholder-gray-500 focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 shadow-lg transition duration-200"
                    />
                    <button
                        onClick={() => handleSend(userInput)}
                        disabled={isLoading || !userInput.trim()}
                        className={`p-3 rounded-xl font-bold transition duration-300 shadow-lg min-w-[100px]
                            ${isLoading || !userInput.trim()
                                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                                : 'bg-indigo-500 hover:bg-indigo-400 active:bg-indigo-600 text-white'
                            }`}>
                        {isLoading ? (
                            <svg className="animate-spin h-5 w-5 text-white mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            'Send'
                        )}
                    </button>
                </div>

                <p className="mt-2 text-sm text-gray-500">Session ID: {sessionId}</p>
            </div>
                
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default App;
