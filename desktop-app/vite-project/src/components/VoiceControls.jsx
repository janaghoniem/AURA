import React, { useState } from "react";
import { Mic, Settings, X, Send } from "lucide-react";

const VoiceControls = ({
  isRecording,
  orbState,
  onMicClick,
  onCancel,
  chatMode,
  setChatMode,
  onSendText,
  onSettingsClick,
}) => {
  const [text, setText] = useState("");

  if (chatMode) {
    const handleSend = () => {
      if (!text.trim()) return;
      onSendText(text);
      setText("");
    };

    return (
      <div className="chat-input-wrapper">
        <div className="chat-input-container">
          <input
            type="text"
            placeholder="Type your message..."
            className="chat-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSend();
            }}
            autoFocus
          />

          <button className="send-btn" onClick={handleSend}>
            <Send size={18} />
          </button>
                  
          <button
            className="voice-return-btn"
            onClick={() => setChatMode(false)}
            style={{ cursor: "pointer" }}
          >
            <Mic size={18} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`voice-controls ${isRecording ? "recording" : ""}`}>
      <button className="control-btn" onClick={onCancel}>
        <X size={20} />
      </button>

      <button
        className="mic-btn"
        onClick={onMicClick}
        disabled={orbState === "processing" || orbState === "speaking"}
      >
        <Mic size={22} />
      </button>

      <button 
        className="control-btn"
        onClick={onSettingsClick}
      >
        <Settings size={20} />
      </button>
    </div>
  );
};

export default VoiceControls;