// SideBar.jsx
import { Settings, Menu, X, SquarePen } from "lucide-react";

const SideBar = ({ collapsed, onToggle, onSettingsClick, onNewChat }) => {
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
