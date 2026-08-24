import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

export default function KpiCard({
  title,
  value,
  subtitle,
  change,
  changeType = 'neutral',
  icon: Icon,
  badgeColor = 'blue'
}) {
  const iconStyles = {
    blue: 'bg-blue-600/20 text-blue-400 border-blue-500/30',
    emerald: 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30',
    amber: 'bg-amber-600/20 text-amber-400 border-amber-500/30',
    purple: 'bg-purple-600/20 text-purple-400 border-purple-500/30',
    rose: 'bg-rose-600/20 text-rose-400 border-rose-500/30'
  };

  return (
    <div className="bg-[#131A2B] p-5 rounded-2xl border border-[#1F2A44] shadow-lg hover:border-blue-500/40 transition-all duration-200 flex flex-col justify-between space-y-3">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block">
            {title}
          </span>
          <h3 className="text-2xl font-black text-white tracking-tight">
            {value}
          </h3>
        </div>
        {Icon && (
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center border shrink-0 ${iconStyles[badgeColor] || iconStyles.blue}`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      <div className="pt-2 border-t border-[#1F2A44] flex items-center justify-between text-xs">
        <span className="text-slate-400 text-[11px] font-medium">{subtitle}</span>

        {change && (
          <span className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full font-bold text-[10px] border ${
            changeType === 'positive' ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800' :
            changeType === 'negative' ? 'bg-rose-950/80 text-rose-300 border-rose-800' :
            'bg-slate-900 text-slate-300 border-slate-800'
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
