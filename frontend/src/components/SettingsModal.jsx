import React from 'react';
import { X, Settings, ShieldCheck, Database, Zap, Sparkles } from 'lucide-react';

export default function SettingsModal({ isOpen, onClose, selectedDbId, currentDbName }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200 text-slate-900">
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <Settings className="w-4 h-4 text-white" />
            </div>
            <div>
              <h3 className="text-base font-extrabold">HADIL Intelligence Configuration</h3>
              <p className="text-xs text-slate-400 font-medium">Enterprise Engine Parameters</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 text-xs text-slate-700">
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
            <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-blue-600" /> Active Data Connection
            </h4>
            <div className="grid grid-cols-2 gap-2 text-slate-600 font-medium">
              <div>
                <span className="text-slate-400">Database Name:</span>
                <p className="font-bold text-slate-900">{currentDbName || 'Default Sales DB'}</p>
              </div>
              <div>
                <span className="text-slate-400">Connection ID:</span>
                <p className="font-bold text-slate-900 font-mono">{selectedDbId || 'sales_db'}</p>
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
            <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> AI Safety & Governance
            </h4>
            <ul className="space-y-1.5 text-slate-600 font-medium">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>Strict SELECT-only guardrail for natural language queries</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>Dialect AST safety validator & parameter sanitization</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>Explicit CRUD form authorization modal for mutations</span>
              </li>
            </ul>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
            <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-purple-600" /> Grounded AI Models
            </h4>
            <p className="text-slate-600 leading-relaxed font-medium">
              HADIL uses schema-grounded NL-to-SQL generation with deterministic intent verification. Grounding prevents hallucinations by strictly constraining queries against active table schemas.
            </p>
          </div>
        </div>

        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button onClick={onClose} className="px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-lg transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
