import React, { useState } from 'react';
import { 
  Database, Zap, Bell, Settings, ChevronDown, 
  AlertCircle, User, RefreshCw, Command, Search, Plus
} from 'lucide-react';

export default function TopHeader({
  databases = [],
  selectedDbId = '',
  currentDbName = '',
  dbError = null,
  onDbChange,
  onReconnect,
  onOpenSettings,
  onOpenConnectModal
}) {
  const [showNotifications, setShowNotifications] = useState(false);

  const mockNotifications = [
    { id: 1, title: 'AI Schema Grounding Active', message: selectedDbId ? `Grounding active on ${currentDbName || selectedDbId}` : 'Awaiting database connection', time: '1m ago' },
    { id: 2, title: 'SQL Safety Guardrails', message: 'Read-only SELECT validation enforced', time: '5m ago' }
  ];

  const isConnected = Boolean(selectedDbId && !dbError);

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
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-600/30 border border-blue-400/30">
            <Zap className="w-5 h-5 text-white fill-current" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-black tracking-tight text-white leading-none">HADIL</h1>
              <span className="text-[10px] bg-blue-500/15 border border-blue-400/20 text-blue-300 font-bold px-2 py-0.5 rounded-md uppercase tracking-wider">
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
          <div className="absolute left-3 text-blue-400">
            <Database className="w-4 h-4" />
          </div>
          <select
            value={selectedDbId}
            onChange={handleSelectChange}
            className="bg-[#131A2B] hover:bg-[#1A2340] text-slate-100 text-xs font-semibold pl-9 pr-8 py-2 rounded-xl border border-[#1F2A44] focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer transition-colors"
          >
            <option value="" disabled={isConnected}>-- Select Database --</option>
            {databases.map(db => (
              <option key={db.id} value={db.id}>
                {db.name} {selectedDbId === db.id ? '✓' : ''}
              </option>
            ))}
            <option value="__connect_new__" className="text-blue-400 font-bold">
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
          className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-blue-900/30 cursor-pointer shrink-0"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Connect DB</span>
        </button>

        {dbError ? (
          <button
            onClick={onReconnect}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950/80 border border-rose-800/80 text-rose-300 text-xs font-semibold rounded-xl hover:bg-rose-900 transition-colors"
          >
            <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>Offline - Retry</span>
          </button>
        ) : isConnected ? (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-950/80 border border-emerald-800/80 text-emerald-400 text-xs font-semibold rounded-full shadow-inner">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Connected</span>
          </div>
        ) : null}

        {/* Global Keyboard Shortcut Pill */}
        <div className="hidden md:flex items-center gap-1.5 bg-[#131A2B] border border-[#1F2A44] px-2.5 py-1.5 rounded-xl text-xs text-slate-400 font-medium">
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
            className="relative p-2 text-slate-400 hover:text-white hover:bg-[#131A2B] rounded-xl border border-transparent hover:border-[#1F2A44] transition-all cursor-pointer"
            title="System Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-4 h-4 bg-rose-600 text-white text-[9px] font-black rounded-full flex items-center justify-center border-2 border-[#0F1626]">
              2
            </span>
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-[#131A2B] border border-[#1F2A44] rounded-2xl shadow-2xl z-50 p-4 text-xs space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#1F2A44]">
                <h4 className="font-bold text-slate-200">System Notifications</h4>
                <span className="text-[10px] text-blue-400 font-bold uppercase">2 Active</span>
              </div>
              <div className="space-y-2">
                {mockNotifications.map(n => (
                  <div key={n.id} className="p-2.5 rounded-xl bg-[#0F1626] border border-[#1F2A44]">
                    <div className="flex items-center justify-between font-semibold text-slate-200">
                      <span>{n.title}</span>
                      <span className="text-[10px] text-slate-500">{n.time}</span>
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
          className="p-2 text-slate-400 hover:text-white hover:bg-[#131A2B] rounded-xl border border-transparent hover:border-[#1F2A44] transition-all cursor-pointer"
          title="System Settings"
        >
          <Settings className="w-4 h-4" />
        </button>

        {/* User Profile */}
        <div className="flex items-center gap-2.5 pl-3 border-l border-[#1F2A44]">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center font-black text-xs text-white shadow-md border border-blue-400/30">
            DB
          </div>
          <div className="hidden lg:block text-left">
            <p className="text-xs font-bold text-slate-100 leading-tight">Database Admin</p>
            <p className="text-[10px] text-slate-400 font-medium">Grounding Layer</p>
          </div>
        </div>
      </div>
    </header>
  );
}
