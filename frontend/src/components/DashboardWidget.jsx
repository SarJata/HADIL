import React, { useState } from 'react';
import { 
  BarChart2, LineChart as LineChartIcon, PieChart as PieChartIcon, Table as TableIcon,
  RefreshCw, Maximize2, Trash2, Pin, TrendingUp, AlertTriangle, CheckCircle2,
  Sparkles, Database, Clock, ChevronRight
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'];

export default function DashboardWidget({ 
  widget, 
  onRefresh, 
  onRemove, 
  onExpand, 
  onTogglePin,
  isPinned = true,
  onMoveUp,
  onMoveDown
}) {
  const [activeViz, setActiveViz] = useState(widget.type || widget.suggestedViz || 'table');
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await onRefresh(widget.id);
    } finally {
      setTimeout(() => setRefreshing(false), 500);
    }
  };

  const renderChart = (data) => {
    if (!data || data.length === 0) {
      return (
        <div className="h-48 flex items-center justify-center text-slate-400 italic text-sm">
          No records found
        </div>
      );
    }

    const keys = Object.keys(data[0]);
    const metadata = widget.metadata || { numeric_columns: [], categorical_columns: [], time_columns: [] };
    const { numeric_columns, categorical_columns, time_columns } = metadata;

    let xKey = keys[0];
    let yKey = keys.find(k => typeof data[0][k] === 'number') || keys[1] || keys[0];

    if (activeViz === 'line') {
      xKey = time_columns?.[0] || categorical_columns?.[0] || keys[0];
      yKey = numeric_columns?.[0] || keys[1] || keys[0];
    } else if (activeViz === 'bar' || activeViz === 'pie') {
      xKey = categorical_columns?.[0] || time_columns?.[0] || keys[0];
      yKey = numeric_columns?.[0] || keys[1] || keys[0];
    }

    if (activeViz === 'bar') {
      return (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', color: '#fff', borderRadius: '8px', border: 'none', fontSize: '12px' }} />
            <Bar dataKey={yKey} fill="#3b82f6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      );
    }

    if (activeViz === 'line') {
      return (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', color: '#fff', borderRadius: '8px', border: 'none', fontSize: '12px' }} />
            <Line type="monotone" dataKey={yKey} stroke="#2563eb" strokeWidth={2.5} dot={{ r: 4, fill: '#2563eb' }} />
          </LineChart>
        </ResponsiveContainer>
      );
    }

    if (activeViz === 'pie') {
      return (
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={4} dataKey={yKey} nameKey={xKey}>
              {data.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', color: '#fff', borderRadius: '8px', border: 'none', fontSize: '12px' }} />
            <Legend wrapperStyle={{ fontSize: '11px' }} />
          </PieChart>
        </ResponsiveContainer>
      );
    }

    // Default Table View
    return (
      <div className="overflow-x-auto max-h-64 rounded-xl border border-slate-200">
        <table className="w-full text-xs text-left">
          <thead className="bg-slate-100/80 text-slate-700 font-semibold sticky top-0 border-b border-slate-200">
            <tr>
              {keys.map(k => (
                <th key={k} className="px-4 py-2.5 font-bold uppercase tracking-wider text-[10px] text-slate-600">{k}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                {Object.values(row).map((val, cIdx) => (
                  <td key={cIdx} className="px-4 py-2.5 text-slate-700 font-medium whitespace-nowrap">
                    {val !== null && val !== undefined ? String(val) : '-'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="bg-[#131A2B] rounded-lg border border-[#1F2A44] flex flex-col justify-between overflow-hidden group">
      {/* Widget Header */}
      <div className="p-3 border-b border-[#1F2A44] flex items-center justify-between bg-[#0F1626]">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
          <div className="truncate">
            <h4 className="text-xs font-bold text-slate-100 truncate" title={widget.title}>
              {widget.title || "Analytics Widget"}
            </h4>
            <p className="text-[10px] text-slate-400 font-mono truncate flex items-center gap-1.5 mt-0.5">
              <span>{widget.original_request || widget.sql}</span>
            </p>
          </div>
        </div>

        {/* Header Action Controls */}
        <div className="flex items-center gap-1 shrink-0">
          {/* Viz switcher */}
          <div className="flex items-center bg-[#131A2B] p-0.5 rounded border border-[#1F2A44] mr-1">
            <button 
              onClick={() => setActiveViz('table')} 
              className={`p-1 rounded text-slate-400 hover:text-slate-100 transition-colors ${activeViz === 'table' ? 'bg-[#0F1626] text-emerald-400 font-bold' : ''}`}
              title="Table View"
            >
              <TableIcon className="w-3 h-3" />
            </button>
            <button 
              onClick={() => setActiveViz('bar')} 
              className={`p-1 rounded text-slate-400 hover:text-slate-100 transition-colors ${activeViz === 'bar' ? 'bg-[#0F1626] text-emerald-400 font-bold' : ''}`}
              title="Bar Chart"
            >
              <BarChart2 className="w-3 h-3" />
            </button>
            <button 
              onClick={() => setActiveViz('line')} 
              className={`p-1 rounded text-slate-400 hover:text-slate-100 transition-colors ${activeViz === 'line' ? 'bg-[#0F1626] text-emerald-400 font-bold' : ''}`}
              title="Line Chart"
            >
              <LineChartIcon className="w-3 h-3" />
            </button>
            <button 
              onClick={() => setActiveViz('pie')} 
              className={`p-1 rounded text-slate-400 hover:text-slate-100 transition-colors ${activeViz === 'pie' ? 'bg-[#0F1626] text-emerald-400 font-bold' : ''}`}
              title="Pie Chart"
            >
              <PieChartIcon className="w-3 h-3" />
            </button>
          </div>

          <button 
            onClick={handleRefresh}
            className={`p-1 text-slate-400 hover:text-slate-100 hover:bg-[#1A2340] rounded transition-colors ${refreshing ? 'animate-spin text-emerald-400' : ''}`}
            title="Refresh Widget Data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button 
            onClick={() => onTogglePin && onTogglePin(widget)}
            className={`p-1 rounded transition-colors ${isPinned ? 'text-amber-400 bg-amber-950/60 border border-amber-800' : 'text-slate-400 hover:text-slate-100 hover:bg-[#1A2340]'}`}
            title={isPinned ? "Unpin Widget" : "Pin to Dashboard"}
          >
            <Pin className="w-3.5 h-3.5 fill-current" />
          </button>

          <button 
            onClick={() => onExpand && onExpand(widget)}
            className="p-1 text-slate-400 hover:text-slate-100 hover:bg-[#1A2340] rounded transition-colors"
            title="Expand Full Screen"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>

          <button 
            onClick={() => onRemove && onRemove(widget.id)}
            className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950/60 rounded transition-colors"
            title="Remove Widget"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Widget Body Content */}
      <div className="p-3 flex-1">
        {/* Interpretation Badge if available */}
        {widget.interpretedAnswer && (
          <div className="mb-2.5 p-2 rounded bg-[#0F1626] border border-emerald-800/60 text-emerald-300 text-xs font-medium leading-relaxed flex items-start gap-2">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <span>{widget.interpretedAnswer}</span>
          </div>
        )}

        {renderChart(widget.executionData)}

        {/* AI Insights List if available */}
        {widget.insights && widget.insights.length > 0 && (
          <div className="mt-2.5 pt-2.5 border-t border-[#1F2A44] space-y-1">
            {widget.insights.slice(0, 2).map((ins, idx) => (
              <div key={idx} className="flex items-start gap-1.5 text-[11px] text-slate-300">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span className="line-clamp-2">{ins}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Widget Footer */}
      <div className="px-3 py-1.5 bg-[#0F1626] border-t border-[#1F2A44] flex items-center justify-between text-[10px] text-slate-400">
        <span className="flex items-center gap-1 font-mono">
          <Clock className="w-3 h-3 text-slate-500" />
          <span>Refreshed: {widget.last_refreshed || 'Just now'}</span>
        </span>
        <span className="font-mono bg-[#131A2B] text-slate-300 px-1.5 py-0.5 rounded border border-[#1F2A44] uppercase font-semibold">
          {widget.executionData ? `${widget.executionData.length} Rows` : '0 Rows'}
        </span>
      </div>
    </div>
  );
}

