import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Topology from "./pages/Topology";
import Devices from "./pages/Devices";
import DeviceDetail from "./pages/DeviceDetail";
import ChangeManagement from "./pages/ChangeManagement";
import ChangePlanDetail from "./pages/ChangePlanDetail";
import AuditPage from "./pages/AuditPage";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/topology", label: "Topology" },
  { to: "/devices", label: "Devices" },
  { to: "/changes", label: "Change Management" },
  { to: "/audit", label: "Audit" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="sidebar-brand">
          <div className="name">Net Infrastructure Platform</div>
          <div className="tag">discovery &middot; topology &middot; change mgmt</div>
        </div>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/topology" element={<Topology />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="/devices/:deviceId" element={<DeviceDetail />} />
          <Route path="/changes" element={<ChangeManagement />} />
          <Route path="/changes/:planId" element={<ChangePlanDetail />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
