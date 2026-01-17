import { Settings, Menu } from "lucide-react";

const SideBar = ({ collapsed, onToggle }) => {
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-top">
        {!collapsed && <span className="logo">AURA</span>}
        <Menu size={22} onClick={onToggle} className="toggle-btn" />
      </div>

      <div className="sidebar-bottom">
        <Settings size={18} />
        {!collapsed && <span>Settings and help</span>}
      </div>
    </aside>
  );
};

export default SideBar;
