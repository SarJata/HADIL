import React from 'react';
import { Database, RefreshCw, AlertCircle, ArrowRight, Plus } from 'lucide-react';

export default function NoDatabaseConnectedView({ 
  databases = [], 
  onSelectDatabase, 
  onReconnect,
  onOpenConnectModal 
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-100 min-h-[60vh]">
      <div className="max-w-md mx-auto space-y-6 animate-in fade-in duration-500">
        {/* Logo Badge */}
        <div className="w-16 h-16 rounded-2xl bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 shadow-xl shadow-emerald-900/20">
          <Database className="w-8 h-8" />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-center gap-2">
            <h2 className="text-2xl font-black text-white tracking-tight">HADIL</h2>
            <span className="text-[10px] bg-slate-800 border border-slate-700 text-slate-400 font-bold px-2 py-0.5 rounded uppercase">
              Intelligence Layer
            </span>
          </div>
          <h3 className="text-lg font-bold text-slate-300">No Database Connected</h3>
          <p className="text-xs text-slate-400 leading-relaxed max-w-sm mx-auto">
            Connect a database to begin exploring, querying, and managing your data with AI-mediated grounding.
          </p>
        </div>

        {/* Primary Action Controls */}
        <div className="space-y-4 pt-2">
          <button
            onClick={onOpenConnectModal}
            className="w-full max-w-xs mx-auto px-6 py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs uppercase tracking-wider rounded-2xl transition-all shadow-xl shadow-emerald-900/40 flex items-center justify-center gap-2 cursor-pointer active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>Connect Database</span>
          </button>

          {databases && databases.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-[#1F2A44]">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Or select discovered local database:
              </label>
              <div className="flex flex-col gap-2 max-w-xs mx-auto">
                {databases.map(db => (
                  <button
                    key={db.id}
                    onClick={() => onSelectDatabase(db.id)}
                    className="w-full px-4 py-2.5 bg-[#131A2B] hover:bg-[#1A2340] border border-[#1F2A44] hover:border-slate-600 text-slate-200 font-bold text-xs rounded-xl transition-all flex items-center justify-between group cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <Database className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="font-mono">{db.name}</span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-1 transition-transform" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
