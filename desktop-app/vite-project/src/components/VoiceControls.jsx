import React, { useState } from "react";
import { Mic, Settings, X, Send } from "lucide-react";

const VoiceControls = ({
  isRecording,
  orbState,
  onMicClick,
  onCancel,
  chatMode,
  setChatMode,
  onSendText,          // ⬅️ NEW PROP
}) => {
  const [text, setText] = useState("");

  if (chatMode) {
    const handleSend = () => {
      if (!text.trim()) return;
      onSendText(text);     // ⬅️ DIRECTLY SEND TO AGENT
      setText("");
    };

    return (
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
    );
  }

  return (
    <div className="voice-controls">
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

      <button className="control-btn">
        <Settings size={20} />
      </button>
    </div>
  );
};

export default VoiceControls;
