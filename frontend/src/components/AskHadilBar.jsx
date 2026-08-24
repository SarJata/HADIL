import React from 'react';
import { 
  Search, Loader2, Sparkles, ShieldCheck, Play, Terminal, AlertCircle, 
  BarChart3, Users, Music, TrendingUp, FileText, Grid
} from 'lucide-react';

export default function AskHadilBar({
  query,
  setQuery,
  onRun,
  loading,
  isSqlMode,
  selectedDbId,
  suggestedQueries = []
}) {
  const isConnected = Boolean(selectedDbId);

  const handlePromptClick = (promptText) => {
    setQuery(promptText);
    setTimeout(() => {
      onRun(promptText);
    }, 100);
  };

  // Helper to get category icons for query pills
  const getPromptIcon = (prompt, idx) => {
    const text = prompt.toLowerCase();
    if (text.includes('top') || text.includes('selling') || text.includes('revenue')) return BarChart3;
    if (text.includes('user') || text.includes('customer') || text.includes('country')) return Users;
    if (text.includes('artist') || text.includes('album') || text.includes('genre') || text.includes('music')) return Music;
    if (text.includes('trend') || text.includes('time') || text.includes('growth')) return TrendingUp;
    if (text.includes('invoice') || text.includes('item') || text.includes('order')) return FileText;
    const icons = [BarChart3, Users, Music, TrendingUp, FileText];
    return icons[idx % icons.length];
  };

  return (
    <div className="w-full max-w-full min-w-0 bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 shadow-2xl text-white space-y-4 overflow-hidden">
      {/* Top Header Label */}
      <div className="flex items-center justify-between px-1 text-xs">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-blue-400 fill-current" />
          <span className="font-extrabold text-blue-400 uppercase tracking-widest text-xs">
            CONVERSATIONAL COMMAND INTERFACE
          </span>
        </div>

        {isSqlMode ? (
          <span className="flex items-center gap-1 text-[10px] bg-emerald-950/80 border border-emerald-800/80 text-emerald-300 font-mono font-bold px-2.5 py-0.5 rounded-md">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            DIRECT SQL MODE
          </span>
        ) : !isConnected ? (
          <span className="flex items-center gap-1 text-[10px] bg-amber-950/80 border border-amber-800/80 text-amber-300 font-bold px-2.5 py-0.5 rounded-md">
            <AlertCircle className="w-3 h-3 text-amber-400" />
            CONNECTION REQUIRED
          </span>
        ) : null}
      </div>

      {/* Main Input Box */}
      <div className="relative flex items-center w-full max-w-full min-w-0">
        <div className="absolute left-4 text-slate-400">
          {isSqlMode ? <Terminal className="w-5 h-5 text-emerald-400" /> : <Search className="w-5 h-5 text-blue-400" />}
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && isConnected && onRun()}
          placeholder={isConnected ? "Ask HADIL anything about your data..." : "Connect a database to execute natural language or SQL queries..."}
          disabled={loading || !isConnected}
          className="w-full bg-[#0F1626] border border-[#1F2A44] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 text-slate-100 placeholder-slate-500 text-sm font-medium pl-12 pr-44 py-4 rounded-xl outline-none transition-all disabled:opacity-50"
        />

        <div className="absolute right-3 flex items-center gap-3">
          <span className="hidden sm:inline-block text-[11px] font-mono text-slate-500 font-medium">
            Ctrl + Enter
          </span>

          <button
            onClick={() => onRun()}
            disabled={loading || !query.trim() || !isConnected}
            className={`px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider flex items-center gap-2 transition-all shadow-md cursor-pointer ${
              isSqlMode 
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/40' 
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-950/40'
            } disabled:opacity-30 disabled:cursor-not-allowed active:scale-95`}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Analyzing...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>EXECUTE</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Suggested Queries Pills */}
      {isConnected && suggestedQueries && suggestedQueries.length > 0 && (
        <div className="w-full max-w-full min-w-0 space-y-2 pt-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block px-1">
            SUGGESTED QUERIES
          </span>
          <div className="flex items-center gap-2.5 overflow-x-auto no-scrollbar py-1">
            {suggestedQueries.slice(0, 6).map((prompt, idx) => {
              const IconComp = getPromptIcon(prompt, idx);
              return (
                <button
                  key={idx}
                  onClick={() => handlePromptClick(prompt)}
                  disabled={loading}
                  title={prompt}
                  className="px-4 py-2.5 rounded-xl bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] hover:border-blue-500/50 text-slate-300 hover:text-white text-xs font-semibold transition-all flex items-center gap-2.5 shrink-0 active:scale-95 cursor-pointer shadow-sm"
                >
                  <IconComp className="w-4 h-4 text-blue-400 shrink-0" />
                  <span className="truncate max-w-[240px]">{prompt}</span>
                </button>
              );
            })}
            <button
              onClick={() => handlePromptClick(suggestedQueries[0])}
              className="px-3.5 py-2.5 rounded-xl bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] text-slate-400 hover:text-white text-xs font-semibold transition-all flex items-center gap-2 shrink-0 cursor-pointer"
            >
              <Grid className="w-4 h-4 text-slate-500" />
              <span>More suggestions</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
