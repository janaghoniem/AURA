import React, { useState } from "react";
import { X, User, Brain } from "lucide-react";

const SettingsModal = ({ onClose, onSave, initialName = "Labubu" }) => {
  const [activeSection, setActiveSection] = useState("profile");
  const [profileData, setProfileData] = useState({
    username: initialName,
    email: "user@example.com",
    theme: "dark",
    language: "en",
  });
  const [memoryData, setMemoryData] = useState({
    maxMemories: 1000,
    retentionDays: 90,
    autoCleanup: true,
    compressionEnabled: true,
  });

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
        {/* Close Button */}
        <button className="settings-close-btn" onClick={onClose}>
          <X size={22} />
        </button>

        <div className="settings-container">
          {/* Left Sidebar - Section Selector */}
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

          {/* Right Section - Settings Content */}
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
                <div className="settings-group">
                  <label className="settings-label">
                    Max Memories Stored
                    <input
                      type="number"
                      className="settings-input"
                      value={memoryData.maxMemories}
                      onChange={(e) =>
                        handleMemoryChange("maxMemories", parseInt(e.target.value))
                      }
                    />
                  </label>

                  <label className="settings-label">
                    Retention Period (Days)
                    <input
                      type="number"
                      className="settings-input"
                      value={memoryData.retentionDays}
                      onChange={(e) =>
                        handleMemoryChange("retentionDays", parseInt(e.target.value))
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
                    Enable Auto Cleanup
                  </label>

                  <label className="settings-checkbox">
                    <input
                      type="checkbox"
                      checked={memoryData.compressionEnabled}
                      onChange={(e) =>
                        handleMemoryChange("compressionEnabled", e.target.checked)
                      }
                    />
                    Enable Compression
                  </label>

                  <div className="memory-info">
                    <p>
                      <strong>Current Memory Usage:</strong> 245 MB of 500 MB
                    </p>
                    <div className="memory-bar">
                      <div className="memory-fill" style={{ width: "49%" }}></div>
                    </div>
                  </div>
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
