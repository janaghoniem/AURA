import React, { useState, useEffect } from "react";
import { X, User, Brain, Trash2, RefreshCw } from "lucide-react";

const SettingsModal = ({ onClose, onSave, initialName = "Labubu" }) => {
  const [activeSection, setActiveSection] = useState("profile");
  const [profileData, setProfileData] = useState({
    username: initialName,
    email: "user@example.com",
    theme: "dark",
    language: "en",
  });
  
  // ✅ NEW: Memory stats state
  const [memoryStats, setMemoryStats] = useState({
    total_conversations: 0,
    total_preferences: 0,
    total_checkpoints: 0,
    storage_size_mb: 0,
  });
  
  const [memoryData, setMemoryData] = useState({
    maxConversationDays: 30,
    maxCheckpointDays: 7,
    maxMessagesPerSession: 50,
    autoCleanup: true,
  });
  
  const [loading, setLoading] = useState(false);
  const [cleanupStatus, setCleanupStatus] = useState("");

  // ✅ NEW: Fetch memory stats on mount
  useEffect(() => {
    if (activeSection === "memory") {
      fetchMemoryStats();
    }
  }, [activeSection]);

  const fetchMemoryStats = async () => {
    try {
      setLoading(true);
      const userId = localStorage.getItem("user_id") || "test_user";
      
      const response = await fetch(`http://localhost:8000/api/memory/stats?user_id=${userId}`);
      const data = await response.json();
      
      setMemoryStats(data);
    } catch (error) {
      console.error("Failed to fetch memory stats:", error);
      setCleanupStatus("❌ Failed to load memory statistics");
    } finally {
      setLoading(false);
    }
  };

  const handleCleanup = async () => {
    if (!confirm("⚠️ This will delete old conversations and trim history. Continue?")) {
      return;
    }

    try {
      setLoading(true);
      setCleanupStatus("🧹 Cleaning up memories...");
      
      const userId = localStorage.getItem("user_id") || "test_user";
      
      const response = await fetch(`http://localhost:8000/api/memory/cleanup?user_id=${userId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_conversation_days: memoryData.maxConversationDays,
          max_checkpoint_days: memoryData.maxCheckpointDays,
          max_messages_per_session: memoryData.maxMessagesPerSession,
        }),
      });

      const result = await response.json();
      
      setCleanupStatus(`✅ Cleanup complete! Deleted ${result.conversations_deleted} conversations, ${result.checkpoints_deleted} checkpoints, trimmed ${result.sessions_trimmed} sessions.`);
      
      // Refresh stats
      await fetchMemoryStats();
      
    } catch (error) {
      console.error("Cleanup failed:", error);
      setCleanupStatus("❌ Cleanup failed");
    } finally {
      setLoading(false);
    }
  };

  const handleClearAll = async () => {
    if (!confirm("🚨 WARNING: This will DELETE ALL your memories permanently. Are you ABSOLUTELY sure?")) {
      return;
    }

    try {
      setLoading(true);
      setCleanupStatus("🗑️ Deleting all memories...");
      
      const userId = localStorage.getItem("user_id") || "test_user";
      
      const response = await fetch(`http://localhost:8000/api/memory/clear-all?user_id=${userId}`, {
        method: "DELETE",
      });

      const result = await response.json();
      
      setCleanupStatus(`✅ All memories cleared! Deleted ${result.conversations_deleted} conversations, ${result.preferences_deleted} preferences.`);
      
      // Refresh stats
      await fetchMemoryStats();
      
    } catch (error) {
      console.error("Clear all failed:", error);
      setCleanupStatus("❌ Clear all failed");
    } finally {
      setLoading(false);
    }
  };

  const handleProfileChange = (field, value) => {
    setProfileData({ ...profileData, [field]: value });
  };

  const handleMemoryChange = (field, value) => {
    setMemoryData({ ...memoryData, [field]: value });
  };

  const handleSave = () => {
    console.log("Settings saved:", { profileData, memoryData });
    onSave(profileData);
    onClose();
  };

  return (
    <div className="settings-overlay">
      <div className="settings-modal">
        <button className="settings-close-btn" onClick={onClose}>
          <X size={22} />
        </button>

        <div className="settings-container">
          {/* Left Sidebar */}
          <div className="settings-sidebar">
            <h2 className="settings-title">Settings</h2>
            <nav className="settings-nav">
              <button
                className={`settings-nav-item ${activeSection === "profile" ? "active" : ""}`}
                onClick={() => setActiveSection("profile")}
              >
                <User size={16} />
                <span>Profile</span>
              </button>

              <button
                className={`settings-nav-item ${activeSection === "memory" ? "active" : ""}`}
                onClick={() => setActiveSection("memory")}
              >
                <Brain size={16} />
                <span>Memory</span>
              </button>
            </nav>
          </div>

          {/* Right Content */}
          <div className="settings-content">
            {activeSection === "profile" && (
              <div className="settings-section">
                <h3 className="section-title">Profile Settings</h3>
                <div className="settings-group">
                  <label className="settings-label">
                    Username
                    <input
                      type="text"
                      className="settings-input"
                      value={profileData.username}
                      onChange={(e) => handleProfileChange("username", e.target.value)}
                    />
                  </label>

                  <label className="settings-label">
                    Email
                    <input
                      type="email"
                      className="settings-input"
                      value={profileData.email}
                      onChange={(e) => handleProfileChange("email", e.target.value)}
                    />
                  </label>

                  <label className="settings-label">
                    Theme
                    <select
                      className="settings-select"
                      value={profileData.theme}
                      onChange={(e) => handleProfileChange("theme", e.target.value)}
                    >
                      <option value="dark">Dark</option>
                      <option value="light">Light</option>
                      <option value="auto">Auto</option>
                    </select>
                  </label>

                  <label className="settings-label">
                    Language
                    <select
                      className="settings-select"
                      value={profileData.language}
                      onChange={(e) => handleProfileChange("language", e.target.value)}
                    >
                      <option value="en">English</option>
                      <option value="ar">العربية</option>
                      <option value="es">Español</option>
                    </select>
                  </label>
                </div>
              </div>
            )}

            {activeSection === "memory" && (
              <div className="settings-section">
                <h3 className="section-title">Memory Management</h3>
                
                {/* ✅ NEW: Memory Statistics */}
                <div className="memory-stats-card">
                  <h4 style={{ fontSize: "16px", marginBottom: "12px", color: "rgba(255,255,255,0.9)" }}>
                    Current Usage
                  </h4>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div style={{ background: "rgba(255,255,255,0.05)", padding: "12px", borderRadius: "8px" }}>
                      <div style={{ fontSize: "24px", fontWeight: "bold", color: "#ff4d6d" }}>
                        {memoryStats.total_conversations}
                      </div>
                      <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.6)" }}>
                        Conversations
                      </div>
                    </div>
                    <div style={{ background: "rgba(255,255,255,0.05)", padding: "12px", borderRadius: "8px" }}>
                      <div style={{ fontSize: "24px", fontWeight: "bold", color: "#7a1fa2" }}>
                        {memoryStats.total_preferences}
                      </div>
                      <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.6)" }}>
                        Preferences
                      </div>
                    </div>
                    <div style={{ background: "rgba(255,255,255,0.05)", padding: "12px", borderRadius: "8px" }}>
                      <div style={{ fontSize: "24px", fontWeight: "bold", color: "#38bdf8" }}>
                        {memoryStats.total_checkpoints}
                      </div>
                      <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.6)" }}>
                        Checkpoints
                      </div>
                    </div>
                    <div style={{ background: "rgba(255,255,255,0.05)", padding: "12px", borderRadius: "8px" }}>
                      <div style={{ fontSize: "24px", fontWeight: "bold", color: "#fbbf24" }}>
                        {memoryStats.storage_size_mb} MB
                      </div>
                      <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.6)" }}>
                        Storage Used
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={fetchMemoryStats}
                    disabled={loading}
                    style={{
                      marginTop: "12px",
                      padding: "8px 16px",
                      background: "rgba(255,255,255,0.08)",
                      border: "1px solid rgba(255,255,255,0.2)",
                      borderRadius: "8px",
                      color: "white",
                      cursor: loading ? "not-allowed" : "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      fontSize: "13px"
                    }}
                  >
                    <RefreshCw size={14} />
                    Refresh Stats
                  </button>
                </div>

                {/* Cleanup Configuration */}
                <div className="settings-group" style={{ marginTop: "24px" }}>
                  <label className="settings-label">
                    Delete Conversations Older Than (Days)
                    <input
                      type="number"
                      className="settings-input"
                      value={memoryData.maxConversationDays}
                      onChange={(e) =>
                        handleMemoryChange("maxConversationDays", parseInt(e.target.value))
                      }
                    />
                  </label>

                  <label className="settings-label">
                    Delete Checkpoints Older Than (Days)
                    <input
                      type="number"
                      className="settings-input"
                      value={memoryData.maxCheckpointDays}
                      onChange={(e) =>
                        handleMemoryChange("maxCheckpointDays", parseInt(e.target.value))
                      }
                    />
                  </label>

                  <label className="settings-label">
                    Max Messages Per Session
                    <input
                      type="number"
                      className="settings-input"
                      value={memoryData.maxMessagesPerSession}
                      onChange={(e) =>
                        handleMemoryChange("maxMessagesPerSession", parseInt(e.target.value))
                      }
                    />
                  </label>

                  <label className="settings-checkbox">
                    <input
                      type="checkbox"
                      checked={memoryData.autoCleanup}
                      onChange={(e) =>
                        handleMemoryChange("autoCleanup", e.target.checked)
                      }
                    />
                    Enable Automatic Cleanup (Daily)
                  </label>

                  {/* ✅ NEW: Cleanup Actions */}
                  <div style={{ marginTop: "20px", display: "flex", gap: "12px" }}>
                    <button
                      onClick={handleCleanup}
                      disabled={loading}
                      style={{
                        flex: 1,
                        padding: "12px",
                        background: "linear-gradient(135deg, #ff4d6d, #7a1fa2)",
                        border: "none",
                        borderRadius: "10px",
                        color: "white",
                        cursor: loading ? "not-allowed" : "pointer",
                        fontWeight: "500",
                        opacity: loading ? 0.6 : 1
                      }}
                    >
                      {loading ? "Cleaning..." : "Run Cleanup Now"}
                    </button>
                    
                    <button
                      onClick={handleClearAll}
                      disabled={loading}
                      style={{
                        padding: "12px 20px",
                        background: "rgba(220, 38, 38, 0.2)",
                        border: "1px solid rgba(220, 38, 38, 0.5)",
                        borderRadius: "10px",
                        color: "#ef4444",
                        cursor: loading ? "not-allowed" : "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px"
                      }}
                    >
                      <Trash2 size={16} />
                      Clear All
                    </button>
                  </div>

                  {/* Status Message */}
                  {cleanupStatus && (
                    <div style={{
                      marginTop: "16px",
                      padding: "12px",
                      background: "rgba(255, 255, 255, 0.05)",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: "8px",
                      fontSize: "13px",
                      color: "rgba(255, 255, 255, 0.9)"
                    }}>
                      {cleanupStatus}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="settings-actions">
              <button className="settings-btn-save" onClick={handleSave}>
                Save Changes
              </button>
              <button className="settings-btn-cancel" onClick={onClose}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;