import React from "react";

const ThinkingIndicator = ({ steps = [] }) => {
  return (
    <div className="thinking-container">
      <div className="thinking-content">
        <div className="thinking-header">
          <span className="thinking-label">Thinking</span>
          <div className="thinking-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
        
        <div className="thinking-steps">
          {steps.map((step, idx) => (
            <div 
              key={idx} 
              className={`thinking-step ${idx < steps.length - 1 ? "completed" : "active"}`}
            >
              <span className="step-icon">
                {idx < steps.length - 1 ? "✓" : "●"}
              </span>
              <span className="step-text">{step}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ThinkingIndicator;