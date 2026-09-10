import React, { useState } from 'react';
import { 
  Database, Bell, Settings, ChevronDown, 
  AlertCircle, User, RefreshCw, Command, Search, Plus, Power
} from 'lucide-react';

export default function TopHeader({
  databases = [],
  selectedDbId = '',
  currentDbName = '',
  dbError = null,
  user = null,
  role = null,
  onDbChange,
  onReconnect,
  onOpenSettings,
  onOpenConnectModal,
  onLogout,
  onNavigateOverview,
  onCloseServer
}) {

  const [showNotifications, setShowNotifications] = useState(false);

  const mockNotifications = [
    { id: 1, title: 'AI Schema Grounding Active', message: selectedDbId ? `Grounding active on ${currentDbName || selectedDbId}` : 'Awaiting database connection', time: '1m ago' },
    { id: 2, title: 'SQL Safety Guardrails', message: 'Read-only SELECT validation enforced', time: '5m ago' }
  ];

  const isConnected = Boolean(selectedDbId && !dbError);

  const getRoleBadgeStyle = (r) => {
    switch (r) {
      case 'ADMIN':
        return 'bg-purple-950/80 border-purple-800 text-purple-300';
      case 'EDITOR':
        return 'bg-emerald-950/80 border-emerald-800 text-emerald-300';
      case 'VIEWER':
        return 'bg-slate-900 border-slate-700 text-slate-300';
      default:
        return 'bg-amber-950/80 border-amber-800 text-amber-300';
    }
  };

  const handleSelectChange = (e) => {
    const val = e.target.value;
    if (val === '__connect_new__') {
      onOpenConnectModal();
    } else if (val) {
      onDbChange(val);
    }
  };

  return (
    <header className="h-16 bg-[#0F1626] border-b border-[#1F2A44] text-white flex items-center justify-between px-6 sticky top-0 z-40 shadow-xl">
      {/* Left Branding & Grounding Context */}
      <div className="flex items-center gap-4">
        <div 
          onClick={() => onNavigateOverview && onNavigateOverview()}
          className="flex items-center gap-3 cursor-pointer group select-none hover:opacity-95 transition-all"
          title="Return to Database Overview"
        >
          <div className="w-10 h-10 bg-transparent flex items-center justify-center group-hover:scale-105 transition-all drop-shadow-[0_2px_8px_rgba(16,185,129,0.3)]">
            <img 
              src="/hadil-logo.png" 
              alt="HADIL Database Intelligence Logo" 
              width="40"
              height="40"
              loading="eager"
              decoding="async"
              className="w-full h-full object-contain filter brightness-110" 
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-serif-brand tracking-normal text-white group-hover:text-emerald-300 transition-colors leading-none">HADIL</h1>
              <span className="text-[10px] bg-slate-800 border border-slate-700 text-slate-300 font-mono font-medium px-2 py-0.5 rounded uppercase">
                Database Intelligence
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium">Domain-Agnostic AI Data Workspace</p>
          </div>
        </div>
      </div>

      {/* Center Data Source Switcher & Global Search Hint */}
      <div className="flex items-center gap-3">
        <div className="relative flex items-center">
          <div className="absolute left-3 text-emerald-400">
            <Database className="w-4 h-4" />
          </div>
          <select
            value={selectedDbId}
            onChange={handleSelectChange}
            className="bg-[#131A2B] hover:bg-[#1A2340] text-slate-100 text-xs font-semibold pl-9 pr-8 py-1.5 rounded-md border border-[#1F2A44] focus:outline-none focus:border-emerald-500 cursor-pointer transition-colors"
          >
            <option value="" disabled={isConnected}>-- Select Database --</option>
            {databases.map(db => (
              <option key={db.id} value={db.id}>
                {db.name} {selectedDbId === db.id ? '✓' : ''}
              </option>
            ))}
            <option value="__connect_new__" className="text-emerald-400 font-bold">
              + Connect another database...
            </option>
          </select>
          <div className="absolute right-2.5 text-slate-400 pointer-events-none">
            <ChevronDown className="w-3.5 h-3.5" />
          </div>
        </div>

        {/* Dedicated Connect Database Button */}
        <button
          onClick={onOpenConnectModal}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold rounded-md border border-emerald-600 transition-colors cursor-pointer shrink-0"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Connect DB</span>
        </button>

        {dbError ? (
          <button
            onClick={onReconnect}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-rose-950/80 border border-rose-800 text-rose-300 text-xs font-semibold rounded-md hover:bg-rose-900 transition-colors"
          >
            <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>Offline - Retry</span>
          </button>
        ) : isConnected ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-700 text-emerald-400 text-xs font-mono font-medium rounded-md">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>CONNECTED</span>
          </div>
        ) : null}

        {/* Global Keyboard Shortcut Pill */}
        <div className="hidden md:flex items-center gap-1.5 bg-[#131A2B] border border-[#1F2A44] px-2.5 py-1 rounded-md text-xs text-slate-400 font-medium">
          <Search className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-[11px] font-mono text-slate-400">Ctrl + K</span>
        </div>
      </div>

      {/* Right User & Utility Controls */}
      <div className="flex items-center gap-3">
        {/* Notifications Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-1.5 text-slate-400 hover:text-white hover:bg-[#131A2B] rounded-md border border-transparent hover:border-[#1F2A44] transition-all cursor-pointer"
            title="System Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-0.5 right-0.5 w-3.5 h-3.5 bg-rose-600 text-white text-[9px] font-bold rounded-full flex items-center justify-center border border-[#0F1626]">
              2
            </span>
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-[#131A2B] border border-[#1F2A44] rounded-lg shadow-xl z-50 p-4 text-xs space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#1F2A44]">
                <h4 className="font-bold text-slate-200">System Notifications</h4>
                <span className="text-[10px] text-blue-400 font-mono font-bold uppercase">2 Active</span>
              </div>
              <div className="space-y-2">
                {mockNotifications.map(n => (
                  <div key={n.id} className="p-2.5 rounded-md bg-[#0F1626] border border-[#1F2A44]">
                    <div className="flex items-center justify-between font-semibold text-slate-200">
                      <span>{n.title}</span>
                      <span className="text-[10px] text-slate-500 font-mono">{n.time}</span>
                    </div>
                    <p className="text-slate-400 text-[11px] mt-1">{n.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Settings button */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-[#131A2B] rounded-md border border-transparent hover:border-[#1F2A44] transition-all cursor-pointer"
          title="System Settings"
        >
          <Settings className="w-4 h-4" />
        </button>

        {/* Authenticated User Profile & Scoped Role */}
        <div className="flex items-center gap-3 pl-3 border-l border-[#1F2A44]">
          <div className="w-7 h-7 rounded-md bg-emerald-800 border border-emerald-600 flex items-center justify-center font-bold text-xs text-white uppercase font-mono">
            {user?.username ? user.username.substring(0, 2) : 'US'}
          </div>
          <div className="hidden lg:block text-left">
            <div className="flex items-center gap-1.5">
              <p className="text-xs font-semibold text-slate-100 leading-tight">
                {user?.username || 'Authenticated User'}
              </p>
              <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border ${getRoleBadgeStyle(role)}`}>
                {role || 'NO ROLE'}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono mt-0.5">
              {selectedDbId ? `${selectedDbId}` : 'No Active DB'}
            </p>
          </div>

          {/* SuAdmin Only - Close HADIL Application Button */}
          {role === 'MASTER_ADMIN' && onCloseServer && (
            <button
              onClick={onCloseServer}
              className="px-2.5 py-1 bg-rose-950/80 hover:bg-rose-900 border border-rose-700 text-rose-200 rounded-md text-[11px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
              title="Close HADIL Application"
            >
              <Power className="w-3.5 h-3.5 text-rose-400" />
              <span>Close HADIL</span>
            </button>
          )}

          <button
            onClick={onLogout}
            className="px-2.5 py-1 bg-[#131A2B] hover:bg-rose-950/60 text-slate-300 hover:text-rose-300 border border-[#1F2A44] hover:border-rose-800 rounded-md text-[11px] font-semibold transition-colors cursor-pointer"
            title="Sign Out"
          >
            Sign Out
          </button>
        </div>
      </div>
    </header>
  );
}


