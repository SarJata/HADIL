import React, { useState } from 'react';
import { 
  X, RefreshCw, BarChart2, Table as TableIcon, LineChart as LineChartIcon, PieChart as PieChartIcon,
  Sparkles, CheckCircle2, Database, Clock, Download
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const COLORS = ['#10b981', '#059669', '#34d399', '#6ee7b7', '#14b8a6', '#0d9488'];

export default function ExpandedWidgetModal({ widget, onClose, onRefresh }) {
  const [activeViz, setActiveViz] = useState(widget.type || 'table');
  const [refreshing, setRefreshing] = useState(false);

  if (!widget) return null;

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await onRefresh(widget.id);
    } finally {
      setTimeout(() => setRefreshing(false), 500);
    }
  };

  const renderExpandedChart = () => {
    const data = widget.executionData;
    if (!data || data.length === 0) {
      return <div className="p-12 text-center text-slate-400">No records to visualize</div>;
    }
    const keys = Object.keys(data[0]);
    const metadata = widget.metadata || { numeric_columns: [], categorical_columns: [], time_columns: [] };
    const { numeric_columns, categorical_columns, time_columns } = metadata;

    let xKey = keys[0];
    let yKey = keys.find(k => typeof data[0][k] === 'number') || keys[1] || keys[0];

    if (activeViz === 'line') {
      xKey = time_columns?.[0] || categorical_columns?.[0] || keys[0];
      yKey = numeric_columns?.[0] || keys[1] || keys[0];
      return (
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', color: '#fff', borderRadius: '12px', border: 'none' }} />
            <Line type="monotone" dataKey={yKey} stroke="#10b981" strokeWidth={3} dot={{ r: 5, fill: '#10b981' }} />
          </LineChart>
        </ResponsiveContainer>
      );
    }

    if (activeViz === 'pie') {
      xKey = categorical_columns?.[0] || time_columns?.[0] || keys[0];
      yKey = numeric_columns?.[0] || keys[1] || keys[0];
      return (
        <ResponsiveContainer width="100%" height={420}>
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={80} outerRadius={140} paddingAngle={5} dataKey={yKey} nameKey={xKey}>
              {data.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', color: '#fff', borderRadius: '12px', border: 'none' }} />
            <Legend wrapperStyle={{ fontSize: '12px' }} />
          </PieChart>
        </ResponsiveContainer>
      );
    }

    if (activeViz === 'bar') {
      xKey = categorical_columns?.[0] || time_columns?.[0] || keys[0];
      yKey = numeric_columns?.[0] || keys[1] || keys[0];
      return (
        <ResponsiveContainer width="100%" height={420}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', color: '#fff', borderRadius: '12px', border: 'none' }} />
            <Bar dataKey={yKey} fill="#10b981" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      );
    }

    // Default Full Table
    return (
      <div className="overflow-x-auto rounded-xl border border-slate-200 max-h-[450px]">
        <table className="w-full text-xs text-left">
          <thead className="bg-slate-100 text-slate-700 font-bold sticky top-0 border-b border-slate-200 uppercase tracking-wider text-[10px]">
            <tr>
              {keys.map(k => (
                <th key={k} className="px-5 py-3.5 text-slate-600">{k}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50 transition-colors">
                {Object.values(row).map((val, cIdx) => (
                  <td key={cIdx} className="px-5 py-3 text-slate-700 font-medium whitespace-nowrap">
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
    <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-emerald-600" />
            <div>
              <h3 className="text-base font-extrabold text-slate-900">{widget.title || "Expanded Intelligence View"}</h3>
              <p className="text-xs text-slate-500 font-medium">"{widget.original_request}"</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Viz switcher */}
            <div className="flex items-center bg-slate-200/70 p-1 rounded-lg">
              <button onClick={() => setActiveViz('table')} className={`px-2.5 py-1 rounded text-xs font-bold ${activeViz === 'table' ? 'bg-white text-emerald-600 shadow-xs' : 'text-slate-600'}`}>Table</button>
              <button onClick={() => setActiveViz('bar')} className={`px-2.5 py-1 rounded text-xs font-bold ${activeViz === 'bar' ? 'bg-white text-emerald-600 shadow-xs' : 'text-slate-600'}`}>Bar</button>
              <button onClick={() => setActiveViz('line')} className={`px-2.5 py-1 rounded text-xs font-bold ${activeViz === 'line' ? 'bg-white text-emerald-600 shadow-xs' : 'text-slate-600'}`}>Line</button>
              <button onClick={() => setActiveViz('pie')} className={`px-2.5 py-1 rounded text-xs font-bold ${activeViz === 'pie' ? 'bg-white text-emerald-600 shadow-xs' : 'text-slate-600'}`}>Pie</button>
            </div>

            <button
              onClick={handleRefresh}
              className={`p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-200 rounded-lg transition-colors ${refreshing ? 'animate-spin text-emerald-600' : ''}`}
              title="Refresh Widget Data"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 custom-scrollbar">
          {widget.interpretedAnswer && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-100 text-emerald-900 text-sm font-semibold flex items-start gap-2.5">
              <Sparkles className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <span>{widget.interpretedAnswer}</span>
            </div>
          )}

          <div className="bg-slate-50/50 p-4 rounded-2xl border border-slate-200">
            {renderExpandedChart()}
          </div>

          {widget.insights && widget.insights.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">AI Generated Insights</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {widget.insights.map((ins, idx) => (
                  <div key={idx} className="p-3 bg-white border border-slate-200 rounded-xl flex items-start gap-2 text-xs text-slate-700 font-medium">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                    <span>{ins}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SQL Payload display */}
          {widget.sql && (
            <div className="p-4 bg-slate-900 rounded-xl text-xs font-mono space-y-1.5">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-emerald-400" /> Grounded SQL Query
              </span>
              <p className="text-emerald-400 leading-relaxed font-mono">{widget.sql}</p>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Refreshed: {widget.last_refreshed || 'Just now'}</span>
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-lg transition-colors"
          >
            Close Workspace
          </button>
        </div>
      </div>
    </div>
  );
}
