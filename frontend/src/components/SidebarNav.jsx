import React, { useState, useEffect, useRef } from 'react';
import { 
  LayoutDashboard, Database, Table as TableIcon, TrendingUp, Pin, History, 
  Clock, Sparkles, ChevronRight, Play, ChevronsLeft, ChevronsRight, Layers, ShieldCheck, Users, Cpu, Settings, FileText
} from 'lucide-react';


export default function SidebarNav({ 
  currentView, 
  onViewChange,
  onOpenSettings,
  pinnedCount = 0,
  dbInsights = {},
  tables = [],
  recentQueries = [],
  onSelectQuery,
  onSelectTable,
  isConnected = false,
  role = null,
  permissions = [],
  capabilities = {},
  authorityType = null
}) {
  const isCloud = capabilities.deployment_mode === 'cloud' || capabilities.organization_signup;
  const isPlatformMaster = role === 'MASTER_ADMIN' || authorityType === 'PLATFORM';
  const isOrgSuAdmin = role === 'SUADMIN' || authorityType === 'ORGANIZATION';
  const canManageUsers = isCloud
    ? (isOrgSuAdmin || role === 'ADMIN')
    : (permissions.includes('MANAGE_USERS') || role === 'ADMIN' || role === 'MASTER_ADMIN' || role === 'SUADMIN');
  const canConfigureProviders = isCloud
    ? (isOrgSuAdmin || isPlatformMaster)
    : (role === 'ADMIN' || role === 'MASTER_ADMIN' || role === 'SUADMIN');
  const dynamicTables = tables && tables.length > 0 ? tables : (dbInsights.tables || []);
  
  // Customisable Sidebar Width State
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('hadil_sidebar_width');
    return saved ? Math.max(220, Math.min(480, parseInt(saved, 10))) : 280;
  });

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [isAnalysisExpanded, setIsAnalysisExpanded] = useState(false);
  const sidebarRef = useRef(null);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing || isCollapsed) return;
      const newWidth = Math.max(220, Math.min(480, e.clientX));
      setSidebarWidth(newWidth);
    };

    const handleMouseUp = () => {
      if (isResizing) {
        setIsResizing(false);
        localStorage.setItem('hadil_sidebar_width', sidebarWidth.toString());
      }
    };

    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    } else {
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    };
  }, [isResizing, isCollapsed, sidebarWidth]);

  const handleDoubleClickReset = () => {
    if (isCollapsed) return;
    setSidebarWidth(280);
    localStorage.setItem('hadil_sidebar_width', '280');
  };

  const actualWidth = isCollapsed ? 64 : sidebarWidth;

  return (
    <aside 
      ref={sidebarRef}
      style={{ width: `${actualWidth}px` }}
      className="relative bg-[#0F1626] border-r border-[#1F2A44] text-slate-300 flex flex-col h-[calc(100vh-4rem)] sticky top-16 select-none shrink-0 overflow-hidden transition-[width] duration-150 min-w-0 max-w-full"
    >
      {/* Resizable Drag Handle on Right Border */}
      {!isCollapsed && (
        <div
          onMouseDown={() => setIsResizing(true)}
          onDoubleClick={handleDoubleClickReset}
          title="Drag to resize sidebar width (Double-click to reset)"
          className={`absolute right-0 top-0 bottom-0 w-2 cursor-col-resize z-30 transition-colors flex items-center justify-center ${
            isResizing ? 'bg-emerald-600' : 'hover:bg-emerald-500/40 bg-transparent'
          }`}
        >
          <div className={`w-0.5 h-8 rounded-full ${isResizing ? 'bg-white' : 'bg-slate-700 hover:bg-emerald-400'}`} />
        </div>
      )}

      {/* Navigation Content with hidden scrollbar */}
      <div className="flex-1 overflow-y-auto p-3 space-y-5 no-scrollbar min-w-0">
        
        {/* COMPACT DB ANALYSIS SIDEBAR CARD (POSITIONS ABOVE MENU) */}
        {!isCollapsed && (
          isConnected ? (
            <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-4 space-y-2.5 shadow-lg min-w-0">
              <div className="flex items-center justify-between gap-1">
                <div className="flex items-center gap-1.5 truncate">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400 fill-current shrink-0" />
                  <span className="font-extrabold text-emerald-400 uppercase tracking-wider text-[10px] truncate">
                    DB ANALYSIS
                  </span>
                </div>
                <span className="text-[9px] font-mono font-bold bg-emerald-950/80 border border-emerald-800/80 text-emerald-400 px-2 py-0.5 rounded-md uppercase tracking-wider shrink-0">
                  GROUNDED
                </span>
              </div>

              {dbInsights.summary ? (
                <div className="space-y-1">
                  <p className={`text-[11px] text-slate-300 italic leading-relaxed font-medium transition-all ${
                    isAnalysisExpanded ? '' : 'line-clamp-3'
                  }`}>
                    "{dbInsights.summary}"
                  </p>
                  {dbInsights.summary.length > 120 && (
                    <button
                      onClick={() => setIsAnalysisExpanded(!isAnalysisExpanded)}
                      className="text-[10px] font-mono font-semibold text-emerald-400 hover:text-emerald-300 hover:underline transition-colors block cursor-pointer"
                    >
                      {isAnalysisExpanded ? "Show less" : "View more"}
                    </button>
                  )}
                </div>
              ) : (
                <p className="text-[11px] text-slate-400 italic leading-relaxed">
                  Database schema inspected and grounded.
                </p>
              )}

              {/* Compact Metadata Row */}
              <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-[#1F2A44]/80 text-[10px] font-mono">
                <span className="bg-[#0F1626] border border-[#1F2A44] px-2 py-0.5 rounded-md text-slate-300 font-semibold">
                  {dbInsights.stats?.table_count ?? dynamicTables.length} Tables
                </span>
                <span className="bg-[#0F1626] border border-[#1F2A44] px-2 py-0.5 rounded-md text-teal-300 font-semibold">
                  {dbInsights.stats?.relation_count ?? 0} Relations
                </span>
                <span className="bg-[#0F1626] border border-[#1F2A44] px-2 py-0.5 rounded-md text-emerald-300 font-semibold">
                  {dbInsights.stats?.record_count !== undefined 
                    ? (dbInsights.stats.record_count >= 1000 
                        ? `${(dbInsights.stats.record_count / 1000).toFixed(1)}K Records` 
                        : `${dbInsights.stats.record_count} Records`)
                    : '0 Records'}
                </span>
              </div>
            </div>
          ) : (
            <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-3.5 space-y-1 shadow-md min-w-0">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px] font-bold uppercase tracking-wider">
                <Database className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                <span>DATABASE</span>
              </div>
              <p className="text-xs font-bold text-amber-400">Not connected</p>
              <p className="text-[10px] text-slate-500">Connect a database to begin.</p>
            </div>
          )
        )}

        {/* MENU SECTION */}
        <div className="space-y-1.5">
          {!isCollapsed && (
            <h3 className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              MENU
            </h3>
          )}
          <button
            onClick={() => onViewChange('overview')}
            title="Overview"
            className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
              currentView === 'overview'
                ? 'bg-gradient-to-r from-emerald-600/30 to-emerald-600/10 border-l-2 border-emerald-500 text-white'
                : 'text-slate-400 hover:bg-[#131A2B] hover:text-slate-100'
            }`}
          >
            <LayoutDashboard className={`w-4 h-4 shrink-0 ${currentView === 'overview' ? 'text-emerald-400' : 'text-slate-400'}`} />
            {!isCollapsed && <span>Overview</span>}
          </button>
        </div>

        {/* DYNAMIC DISCOVERED TABLES SECTION */}
        {isConnected && dynamicTables.length > 0 && (
          <div className="space-y-1">
            {!isCollapsed && (
              <h3 className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                DISCOVERED TABLES
              </h3>
            )}
            {dynamicTables.map((table) => {
              const viewId = `table_${table}`;
              const isActive = currentView === viewId;
              return (
                <button
                  key={table}
                  onClick={() => onSelectTable(table)}
                  title={table}
                  className={`w-full flex items-center justify-between px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-emerald-600/30 to-emerald-600/10 border-l-2 border-emerald-500 text-white font-bold'
                      : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
                  }`}
                >
                  <div className="flex items-center gap-3 truncate">
                    <TableIcon className={`w-4 h-4 shrink-0 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                    {!isCollapsed && <span className="truncate capitalize font-medium text-xs">{table}</span>}
                  </div>
                  {!isCollapsed && isActive && <ChevronRight className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
                </button>
              );
            })}
          </div>
        )}

        {/* INTELLIGENCE SECTION */}
        <div className="space-y-1.5">
          {!isCollapsed && (
            <h3 className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              INTELLIGENCE
            </h3>
          )}
          <div className="space-y-1">
            <button
              onClick={() => onViewChange('analytics-charts')}
              title="Analytics & Trends"
              className={`w-full flex items-center gap-3 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                currentView === 'analytics-charts'
                  ? 'bg-slate-800/80 border-l-2 border-emerald-500 text-white font-bold'
                  : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
              }`}
            >
              <TrendingUp className="w-4 h-4 text-slate-400 shrink-0" />
              {!isCollapsed && <span className="truncate">Analytics & Trends</span>}
            </button>

            <button
              onClick={() => onViewChange('analytics-anomalies')}
              title="Anomalies & ML"
              className={`w-full flex items-center gap-3 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                currentView === 'analytics-anomalies'
                  ? 'bg-slate-800/80 border-l-2 border-emerald-500 text-white font-bold'
                  : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
              }`}
            >
              <Sparkles className="w-4 h-4 text-emerald-400 shrink-0" />
              {!isCollapsed && <span className="truncate">Anomalies & ML</span>}
            </button>
          </div>
        </div>

        {/* WORKSPACE SECTION */}
        <div className="space-y-1.5">
          {!isCollapsed && (
            <h3 className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              WORKSPACE
            </h3>
          )}
          <div className="space-y-1">
            <button
              onClick={() => onViewChange('pinned')}
              title="Pinned Widgets"
              className={`w-full flex items-center justify-between px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                currentView === 'pinned'
                  ? 'bg-slate-800/80 border-l-2 border-emerald-500 text-white font-bold'
                  : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
              }`}
            >
              <div className="flex items-center gap-3 truncate">
                <Pin className="w-4 h-4 text-amber-400 fill-current shrink-0" />
                {!isCollapsed && <span className="truncate">Pinned Widgets</span>}
              </div>
              {pinnedCount > 0 && (
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-800 text-emerald-400 border border-slate-700 shrink-0">
                  {pinnedCount}
                </span>
              )}
            </button>

            <button
              onClick={() => onViewChange('history')}
              title="Query History"
              className={`w-full flex items-center gap-3 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                currentView === 'history'
                  ? 'bg-slate-800/80 border-l-2 border-emerald-500 text-white font-bold'
                  : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
              }`}
            >
              <History className="w-4 h-4 text-slate-400 shrink-0" />
              {!isCollapsed && <span className="truncate">Query History</span>}
            </button>

            {/* POLICY RAG SUBSYSTEM MENU ITEM */}
            <button
              onClick={() => onViewChange('policy-documents')}
              title="Policy Documents (RAG)"
              className={`w-full flex items-center gap-3 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                currentView === 'policy-documents'
                  ? 'bg-slate-800/80 border-l-2 border-emerald-500 text-white font-bold'
                  : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
              }`}
            >
              <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
              {!isCollapsed && <span className="truncate">Policy Documents</span>}
            </button>


            {canConfigureProviders && (
              <button
                onClick={onOpenSettings}
                title="AI Models & Providers"
                className="w-full flex items-center gap-3 px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:bg-[#131A2B] hover:text-white transition-all cursor-pointer"
              >
                <Cpu className="w-4 h-4 text-emerald-400 shrink-0" />
                {!isCollapsed && <span className="truncate">AI Models & Providers</span>}
              </button>
            )}

            {isPlatformMaster && (
              <button
                onClick={() => onViewChange('platform-orgs')}
                title="Pending Organizations"
                className={`w-full flex items-center gap-3 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                  currentView === 'platform-orgs'
                    ? 'bg-gradient-to-r from-amber-600/30 to-amber-600/10 border-l-2 border-amber-500 text-white font-bold'
                    : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
                }`}
              >
                <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0" />
                {!isCollapsed && <span className="truncate">Organizations</span>}
              </button>
            )}

            {canManageUsers && (
              <>
                <button
                  onClick={() => onViewChange('user-management')}
                  title="User Management"
                  className={`w-full flex items-center gap-3 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                    currentView === 'user-management'
                      ? 'bg-gradient-to-r from-teal-600/30 to-teal-600/10 border-l-2 border-teal-500 text-white font-bold'
                      : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
                  }`}
                >
                  <Users className="w-4 h-4 text-teal-400 shrink-0" />
                  {!isCollapsed && <span className="truncate">User Management</span>}
                </button>

                <button
                  onClick={() => onViewChange('suadmin')}
                  title="SuAdmin Administration"
                  className={`w-full flex items-center gap-3 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                    currentView === 'suadmin'
                      ? 'bg-gradient-to-r from-emerald-600/30 to-emerald-600/10 border-l-2 border-emerald-500 text-white font-bold'
                      : 'text-slate-300 hover:bg-[#131A2B] hover:text-slate-100'
                  }`}
                >
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                  {!isCollapsed && <span className="truncate">SuAdmin Tools</span>}
                </button>
              </>
            )}
          </div>
        </div>

        {/* RECENT QUERIES SECTION */}
        {recentQueries.length > 0 && isConnected && !isCollapsed && (
          <div className="pt-2 border-t border-[#1F2A44] space-y-2">
            <div className="flex items-center justify-between px-3">
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                <span>RECENT QUERIES</span>
              </h3>
            </div>
            <div className="space-y-1">
              {recentQueries.slice(0, 4).map((q) => (
                <button
                  key={q.id}
                  onClick={() => onSelectQuery(q.id)}
                  className="w-full flex items-center justify-between px-3.5 py-1.5 rounded-xl hover:bg-[#131A2B] text-xs text-slate-400 hover:text-white transition-all group cursor-pointer text-left"
                  title={q.natural_query}
                >
                  <span className="truncate text-[11px] group-hover:text-emerald-400">
                    {q.natural_query}
                  </span>
                </button>
              ))}
              <button
                onClick={() => onViewChange('recent')}
                className="w-full text-left px-3.5 py-1.5 text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 flex items-center justify-between transition-colors"
              >
                <span>View all queries</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* COLLAPSIBLE SIDEBAR TOGGLE BUTTON AT BOTTOM */}
      <div className="p-3 border-t border-[#1F2A44] bg-[#0F1626]">
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] text-slate-300 hover:text-white text-xs font-semibold transition-all border border-[#1F2A44] cursor-pointer"
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? (
            <ChevronsRight className="w-4 h-4 text-emerald-400" />
          ) : (
            <>
              <ChevronsLeft className="w-4 h-4 text-slate-400" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
