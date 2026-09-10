import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

export default function KpiCard({
  title,
  value,
  subtitle,
  change,
  changeType = 'neutral',
  icon: Icon,
  badgeColor = 'emerald'
}) {
  const iconStyles = {
    blue: 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30',
    emerald: 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30',
    amber: 'bg-amber-600/20 text-amber-400 border-amber-500/30',
    purple: 'bg-purple-600/20 text-purple-400 border-purple-500/30',
    rose: 'bg-rose-600/20 text-rose-400 border-rose-500/30'
  };

  return (
    <div className="bg-[#131A2B] p-4 rounded-lg border border-[#1F2A44] flex flex-col justify-between space-y-2">
      <div className="flex items-start justify-between">
        <div className="space-y-0.5">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wide text-slate-400 block">
            {title}
          </span>
          <h3 className="text-xl font-bold text-white font-mono tracking-tight">
            {value}
          </h3>
        </div>
        {Icon && (
          <div className={`w-8 h-8 rounded flex items-center justify-center border shrink-0 ${iconStyles[badgeColor] || iconStyles.emerald}`}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="pt-2 border-t border-[#1F2A44] flex items-center justify-between text-xs">
        <span className="text-slate-400 text-[11px] font-medium">{subtitle}</span>

        {change && (
          <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded font-mono font-bold text-[10px] border ${
            changeType === 'positive' ? 'bg-slate-900 text-emerald-300 border-emerald-800' :
            changeType === 'negative' ? 'bg-slate-900 text-rose-300 border-rose-800' :
            'bg-slate-900 text-slate-300 border-slate-700'
          }`}>
            {changeType === 'positive' && <ArrowUpRight className="w-3 h-3" />}
            {changeType === 'negative' && <ArrowDownRight className="w-3 h-3" />}
            {changeType === 'neutral' && <Minus className="w-3 h-3" />}
            {change}
          </span>
        )}
      </div>
    </div>
  );
}

