import React, { useState } from 'react';
import { 
  BarChart2, Table as TableIcon, LineChart as LineChartIcon, PieChart as PieChartIcon,
  TrendingUp, Pin, Sparkles, CheckCircle2, AlertCircle, ShieldCheck, ChevronDown, 
  ChevronUp, Database, XCircle, Loader2, Play, Check
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export default function QueryResultPanel({
  executionData,
  executionError,
  successMessage,
  loading,
  interpretedAnswer,
  suggestedViz,
  metadata,
  insights,
  prediction,
  predictLoading,
  followupSuggestions,
  sql,
  intent,
  verification,
  validation,
  query,
  onPinResult,
  onPredict,
  onRunFollowup,
  isPinned
}) {
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'chart'
  const [chartType, setChartType] = useState(suggestedViz || 'bar');
  const [showTechnical, setShowTechnical] = useState(false);

  if (loading) {
    return (
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-12 text-center text-white space-y-4">
        <div className="relative flex justify-center">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
        </div>
        <div>
          <h4 className="text-base font-bold text-slate-200">Processing Business Intelligence Query</h4>
          <p className="text-xs text-slate-400 mt-1">Executing SQL generation & strict safety validation pipeline...</p>
        </div>
      </div>
    );
  }

  if (executionError) {
    return (
      <div className="bg-red-950/40 rounded-2xl border border-red-800/60 p-6 text-red-200 flex items-start gap-4">
        <AlertCircle className="w-6 h-6 text-red-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="text-xs font-bold uppercase tracking-wider text-red-400">Query Execution Error</h4>
          <p className="text-sm font-medium leading-relaxed">{executionError}</p>
        </div>
      </div>
    );
  }

  if (successMessage) {
    return (
      <div className="bg-emerald-950/40 rounded-2xl border border-emerald-800/60 p-6 text-emerald-200 flex items-start gap-4">
        <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400">Operation Success</h4>
          <p className="text-sm font-medium leading-relaxed">{successMessage}</p>
        </div>
      </div>
    );
  }

  if (!executionData) return null;

  const renderChartContent = () => {
    if (!executionData || executionData.length === 0) return null;
    const keys = Object.keys(executionData[0]);
    const { numeric_columns, categorical_columns, time_columns } = metadata || { numeric_columns: [], categorical_columns: [], time_columns: [] };

    let xKey = keys[0];
    let yKey = keys.find(k => typeof executionData[0][k] === 'number') || keys[1] || keys[0];

    const type = chartType || suggestedViz || 'bar';

    if (type === 'line') {
      xKey = time_columns?.[0] || categorical_columns?.[0] || keys[0];
      yKey = numeric_columns?.[0] || keys[1] || keys[0];
      return (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={executionData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff', borderRadius: '8px' }} />
            <Line type="monotone" dataKey={yKey} stroke="#3b82f6" strokeWidth={3} dot={{ r: 5, fill: '#3b82f6' }} />
          </LineChart>
        </ResponsiveContainer>
      );
    }

    if (type === 'pie') {
      xKey = categorical_columns?.[0] || time_columns?.[0] || keys[0];
      yKey = numeric_columns?.[0] || keys[1] || keys[0];
      return (
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie data={executionData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={4} dataKey={yKey} nameKey={xKey}>
              {executionData.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff', borderRadius: '8px' }} />
            <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
          </PieChart>
        </ResponsiveContainer>
      );
    }

    // Default Bar Chart
    xKey = categorical_columns?.[0] || time_columns?.[0] || keys[0];
    yKey = numeric_columns?.[0] || keys[1] || keys[0];
    return (
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={executionData}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
          <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff', borderRadius: '8px' }} />
          <Bar dataKey={yKey} fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl text-slate-100">
      {/* Panel Action Header Bar */}
      <div className="px-6 py-4 border-b border-slate-800 bg-slate-950 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>Query Intelligence Result</span>
              <span className="text-[10px] bg-slate-800 text-slate-400 font-mono px-2 py-0.5 rounded border border-slate-700">
                {executionData.length} records
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 font-medium truncate max-w-md">"{query}"</p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Table / Viz Toggle */}
          <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1 rounded-md font-bold transition-all flex items-center gap-1.5 ${
                viewMode === 'table' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <TableIcon className="w-3.5 h-3.5" />
              <span>Data Table</span>
            </button>
            <button
              onClick={() => setViewMode('chart')}
              className={`px-3 py-1 rounded-md font-bold transition-all flex items-center gap-1.5 ${
                viewMode === 'chart' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BarChart2 className="w-3.5 h-3.5" />
              <span>Visual Chart</span>
            </button>
          </div>

          {/* ML Predict Button */}
          <button
            onClick={onPredict}
            disabled={predictLoading || executionData.length < 2}
            className="px-3 py-1.5 rounded-lg bg-pink-950/70 hover:bg-pink-900 border border-pink-800/80 text-pink-300 text-xs font-bold transition-all flex items-center gap-1.5 disabled:opacity-40"
          >
            {predictLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TrendingUp className="w-3.5 h-3.5" />}
            <span>Forecast Trend</span>
          </button>

          {/* PIN TO DASHBOARD BUTTON */}
          <button
            onClick={onPinResult}
            className={`px-4 py-1.5 rounded-lg text-xs font-extrabold transition-all flex items-center gap-1.5 shadow-md ${
              isPinned
                ? 'bg-amber-600 hover:bg-amber-500 text-white'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white'
            }`}
          >
            {isPinned ? <Check className="w-4 h-4" /> : <Pin className="w-4 h-4 fill-current" />}
            <span>{isPinned ? 'Pinned to Dashboard' : 'Pin to Dashboard'}</span>
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="p-6 space-y-6">
        {/* AI Answer Interpretation Banner */}
        {interpretedAnswer && (
          <div className="p-4 rounded-xl bg-blue-950/60 border border-blue-800/60 text-blue-200 flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400 block mb-1">
                AI Semantic Synthesis
              </span>
              <p className="text-sm font-semibold leading-relaxed text-white italic">
                "{interpretedAnswer}"
              </p>
            </div>
          </div>
        )}

        {/* Forecast / ML Prediction Display */}
        {prediction && (
          <div className="p-5 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-pink-400" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">ML Forecast & Trend Analysis</h4>
              </div>
              <span className="text-[10px] bg-pink-900/60 border border-pink-700/60 text-pink-300 font-bold px-2 py-0.5 rounded">
                Confidence: {prediction.confidence || 'High'}
              </span>
            </div>
            <p className="text-sm text-slate-300 font-medium leading-relaxed italic border-l-2 border-pink-500 pl-3">
              {prediction.message}
            </p>
            {prediction.why && (
              <p className="text-[11px] text-slate-400 font-normal">Methodology: {prediction.why}</p>
            )}
          </div>
        )}

        {/* Data View or Chart View */}
        {viewMode === 'table' ? (
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-900 text-slate-300 border-b border-slate-800 font-bold uppercase text-[10px] tracking-wider">
                <tr>
                  {Object.keys(executionData[0]).map(key => (
                    <th key={key} className="px-5 py-3 text-slate-300">{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {executionData.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-900/80 transition-colors">
                    {Object.values(row).map((val, j) => (
                      <td key={j} className="px-5 py-3 text-slate-300 font-medium">
                        {val !== null && val !== undefined ? String(val) : '-'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-end gap-2">
              <span className="text-[11px] text-slate-400 font-semibold">Chart Type:</span>
              <select
                value={chartType}
                onChange={(e) => setChartType(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-xs text-slate-200 font-bold px-3 py-1 rounded-lg outline-none"
              >
                <option value="bar">Bar Chart</option>
                <option value="line">Line Chart</option>
                <option value="pie">Pie Chart</option>
              </select>
            </div>
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl">
              {renderChartContent()}
            </div>
          </div>
        )}

        {/* Key Intelligence Insights */}
        {insights && insights.length > 0 && (
          <div className="space-y-2.5 pt-2">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-blue-400" />
              <span>Automated Intelligence Key Takeaways</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {insights.map((ins, idx) => (
                <div key={idx} className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-start gap-2.5 text-xs text-slate-300 font-medium">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{ins}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Dynamic Follow-up Suggestions */}
        {followupSuggestions && followupSuggestions.length > 0 && (
          <div className="pt-3 border-t border-slate-800/80 space-y-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              Suggested Next Explorations:
            </span>
            <div className="flex flex-wrap gap-2">
              {followupSuggestions.map((sug, idx) => (
                <button
                  key={idx}
                  onClick={() => onRunFollowup(sug)}
                  className="px-3 py-1.5 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-blue-400 hover:text-blue-300 text-xs font-medium transition-all flex items-center gap-1.5 group"
                >
                  <span>{sug}</span>
                  <Play className="w-3 h-3 fill-current text-blue-500 opacity-60 group-hover:opacity-100" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Technical Inspection Toggle */}
        <div className="pt-2 border-t border-slate-800">
          <button
            onClick={() => setShowTechnical(!showTechnical)}
            className="text-[11px] font-bold text-slate-500 hover:text-slate-300 uppercase tracking-wider flex items-center gap-2 transition-colors mx-auto py-1"
          >
            {showTechnical ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            <span>{showTechnical ? "Hide SQL Inspection & Verification" : "Show SQL Inspection & Verification"}</span>
          </button>

          {showTechnical && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-blue-400" /> SQL Expression Payload
                </span>
                <pre className="text-emerald-400 bg-slate-900 p-3 rounded-lg overflow-x-auto text-[11px] leading-relaxed">
                  {sql || '-- Direct execution query'}
                </pre>
                {intent && (
                  <p className="text-[10px] text-slate-400 font-sans">Intent: <strong>{intent}</strong></p>
                )}
              </div>

              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3 font-sans">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Pipeline Integrity Verification
                </span>
                {verification && (
                  <div className={`p-3 rounded-lg border text-xs ${verification.is_valid ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300' : 'bg-red-950/40 border-red-800/60 text-red-300'}`}>
                    <p className="font-bold">{verification.is_valid ? 'Verified Intent' : 'Intent Mismatch'}</p>
                    <p className="text-[11px] mt-1 opacity-80">{verification.explanation}</p>
                  </div>
                )}
                {validation && (
                  <div className={`p-3 rounded-lg border text-xs ${validation.is_safe ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300' : 'bg-red-950/40 border-red-800/60 text-red-300'}`}>
                    <p className="font-bold">{validation.is_safe ? 'Safe SELECT Operation' : 'Violated Safety Guardrail'}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
