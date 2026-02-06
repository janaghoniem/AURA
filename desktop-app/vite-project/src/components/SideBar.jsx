// SideBar.jsx
import { Settings, Menu, X, SquarePen } from "lucide-react";

const SideBar = ({ collapsed, onToggle, onSettingsClick, onNewChat, chats = [], onSwitchChat, currentSessionId }) => {
  return (
    <>
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`} role="navigation" aria-label="Main sidebar">
        
        {/* TOP ZONE */}
        <div className="sidebar-top">
          {!collapsed && <span className="logo">AURA</span>}
          <button className="toggle-btn" onClick={onToggle} aria-label="Toggle sidebar" aria-expanded={!collapsed}>
            {collapsed ? <Menu size={22} /> : <X size={22} />}
          </button>
        </div>

        {/* MIDDLE ZONE */}
        <div className="sidebar-middle">
          <button className="new-chat-btn" onClick={onNewChat} aria-label="Start a new chat">
            <SquarePen size={18} />
            {!collapsed && <span>New chat</span>}
          </button>

          {/* CHAT HISTORY */}
          {!collapsed && chats.length > 0 && (
            <div className="chat-history">
              <div className="chat-history-label">Recent chats</div>
              <ul className="chat-list">
                {chats.slice(0, 10).map((chat) => (
                  <li
                    key={chat.session_id}
                    className={`chat-item ${currentSessionId === chat.session_id ? "active" : ""}`}
                    onClick={() => onSwitchChat && onSwitchChat(chat.session_id, chat.title)}
                    title={chat.title}
                  >
                    <span className="chat-title">{chat.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* BOTTOM ZONE */}
        <button className="sidebar-bottom" onClick={onSettingsClick} aria-label="Open settings">
          <Settings size={18} />
          {!collapsed && <span>Settings</span>}
        </button>
      </aside>

      {collapsed && <div className="sidebar-overlay" onClick={onToggle} role="button" aria-label="Open sidebar overlay"></div>}
    </>
  );
};

export default SideBar;
