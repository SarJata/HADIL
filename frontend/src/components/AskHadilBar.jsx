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
    <div className="w-full max-w-full min-w-0 bg-[#131A2B] border border-[#1F2A44] rounded-lg p-4 text-white space-y-3 overflow-hidden">
      {/* Top Header Label */}
      <div className="flex items-center justify-between px-1 text-xs">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="font-semibold text-slate-300 uppercase tracking-wide text-xs">
            QUERY COMMAND INTERFACE
          </span>
        </div>

        {isSqlMode ? (
          <span className="flex items-center gap-1 text-[10px] bg-slate-900 border border-emerald-800 text-emerald-400 font-mono font-medium px-2 py-0.5 rounded">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            DIRECT SQL MODE
          </span>
        ) : !isConnected ? (
          <span className="flex items-center gap-1 text-[10px] bg-amber-950/80 border border-amber-800 text-amber-300 font-mono font-medium px-2 py-0.5 rounded">
            <AlertCircle className="w-3 h-3 text-amber-400" />
            CONNECTION REQUIRED
          </span>
        ) : null}
      </div>

      {/* Main Input Box */}
      <div className="relative flex items-center w-full max-w-full min-w-0">
        <div className="absolute left-3.5 text-slate-400">
          {isSqlMode ? <Terminal className="w-4 h-4 text-emerald-400" /> : <Search className="w-4 h-4 text-emerald-400" />}
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && isConnected && onRun()}
          placeholder={isConnected ? "Ask HADIL anything about your data..." : "Connect a database to execute natural language or SQL queries..."}
          disabled={loading || !isConnected}
          className="w-full bg-[#0F1626] border border-[#1F2A44] focus:border-emerald-500 text-slate-100 placeholder-slate-500 text-sm font-medium pl-10 pr-40 py-3 rounded-md outline-none transition-colors disabled:opacity-50"
        />

        <div className="absolute right-2.5 flex items-center gap-3">
          <span className="hidden sm:inline-block text-[11px] font-mono text-slate-500">
            Ctrl + Enter
          </span>

          <button
            onClick={() => onRun()}
            disabled={loading || !query.trim() || !isConnected}
            className="px-4 py-1.5 rounded-md text-xs font-semibold bg-emerald-700 hover:bg-emerald-600 border border-emerald-600 text-white flex items-center gap-2 transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          >
            {loading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
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
        <div className="w-full max-w-full min-w-0 space-y-1.5 pt-1">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wide block px-1">
            SUGGESTED QUERIES
          </span>
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
            {suggestedQueries.slice(0, 6).map((prompt, idx) => {
              const IconComp = getPromptIcon(prompt, idx);
              return (
                <button
                  key={idx}
                  onClick={() => handlePromptClick(prompt)}
                  disabled={loading}
                  title={prompt}
                  className="px-3 py-1.5 rounded-md bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] hover:border-emerald-500/50 text-slate-300 hover:text-white text-xs transition-colors flex items-center gap-2 shrink-0 cursor-pointer"
                >
                  <IconComp className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="truncate max-w-[240px]">{prompt}</span>
                </button>
              );
            })}
            <button
              onClick={() => handlePromptClick(suggestedQueries[0])}
              className="px-3 py-1.5 rounded-md bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] text-slate-400 hover:text-white text-xs transition-colors flex items-center gap-1.5 shrink-0 cursor-pointer"
            >
              <Grid className="w-3.5 h-3.5 text-slate-500" />
              <span>More</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

