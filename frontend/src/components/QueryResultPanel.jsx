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

const COLORS = ['#10b981', '#059669', '#34d399', '#6ee7b7', '#14b8a6', '#0d9488'];

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
            <Line type="monotone" dataKey={yKey} stroke="#10b981" strokeWidth={3} dot={{ r: 5, fill: '#10b981' }} />
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
          <Bar dataKey={yKey} fill="#10b981" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  };

  return (
    <div className="bg-[#0F1626] border border-[#1F2A44] rounded-lg overflow-hidden text-slate-100">
      {/* Panel Action Header Bar */}
      <div className="px-5 py-3 border-b border-[#1F2A44] bg-[#131A2B] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <div>
            <h3 className="text-xs font-bold text-white flex items-center gap-2">
              <span>QUERY RESULT</span>
              <span className="text-[10px] bg-slate-900 text-slate-400 font-mono px-2 py-0.5 rounded border border-slate-800">
                {executionData.length} records
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 font-mono truncate max-w-md">"{query}"</p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Table / Viz Toggle */}
          <div className="flex bg-[#0F1626] p-0.5 rounded border border-[#1F2A44] text-xs">
            <button
              onClick={() => setViewMode('table')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1.5 ${
                viewMode === 'table' ? 'bg-emerald-700 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <TableIcon className="w-3 h-3" />
              <span>Data Table</span>
            </button>
            <button
              onClick={() => setViewMode('chart')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1.5 ${
                viewMode === 'chart' ? 'bg-emerald-700 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BarChart2 className="w-3 h-3" />
              <span>Visual Chart</span>
            </button>
          </div>

          {/* ML Predict Button */}
          <button
            onClick={onPredict}
            disabled={predictLoading || executionData.length < 2}
            className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-pink-300 text-xs font-medium transition-colors flex items-center gap-1.5 disabled:opacity-40"
          >
            {predictLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <TrendingUp className="w-3 h-3" />}
            <span>Forecast Trend</span>
          </button>

          {/* PIN TO DASHBOARD BUTTON */}
          <button
            onClick={onPinResult}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1.5 border ${
              isPinned
                ? 'bg-amber-950/80 border-amber-800 text-amber-300'
                : 'bg-emerald-700 border-emerald-600 hover:bg-emerald-600 text-white'
            }`}
          >
            {isPinned ? <Check className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5 fill-current" />}
            <span>{isPinned ? 'Pinned' : 'Pin to Dashboard'}</span>
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="p-4 space-y-4">
        {/* AI Answer Interpretation Banner */}
        {interpretedAnswer && (
          <div className="p-3 rounded bg-slate-900 border border-emerald-800/60 text-emerald-200 flex items-start gap-3">
            <Sparkles className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wide text-emerald-400 block mb-0.5">
                AI SEMANTIC SYNTHESIS
              </span>
              <p className="text-xs font-medium leading-relaxed text-slate-200">
                {interpretedAnswer}
              </p>
            </div>
          </div>
        )}

        {/* Forecast / ML Prediction Display */}
        {prediction && (
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-pink-400" />
                <h4 className="text-xs font-mono font-bold uppercase tracking-wide text-slate-200">ML Forecast & Trend Analysis</h4>
              </div>
              <span className="text-[10px] bg-slate-900 border border-slate-700 text-pink-300 font-mono px-2 py-0.5 rounded">
                Confidence: {prediction.confidence || 'High'}
              </span>
            </div>
            <p className="text-xs text-slate-300 font-medium leading-relaxed border-l-2 border-pink-500 pl-3">
              {prediction.message}
            </p>
            {prediction.why && (
              <p className="text-[11px] text-slate-400 font-mono">Methodology: {prediction.why}</p>
            )}
          </div>
        )}

        {/* Data View, Empty State, or Chart View */}
        {executionData.length === 0 ? (
          <div className="bg-[#0F1626] border border-dashed border-[#1F2A44] rounded-xl p-8 text-center space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[#131A2B] border border-[#1F2A44] flex items-center justify-center mx-auto text-emerald-400">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-200">Query Executed Successfully</h4>
              <p className="text-xs text-slate-400 font-mono">0 rows returned</p>
              <p className="text-xs text-slate-400 leading-relaxed max-w-md mx-auto">
                This table exists in the active database, but currently contains no matching records.
              </p>
            </div>
            {metadata && metadata.columns && metadata.columns.length > 0 && (
              <div className="pt-3 border-t border-[#1F2A44] max-w-md mx-auto text-left">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wide block mb-1.5">
                  Available Table Columns ({metadata.columns.length}):
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {metadata.columns.map((col, idx) => (
                    <span key={idx} className="text-[11px] font-mono bg-[#131A2B] text-slate-300 px-2 py-0.5 rounded border border-[#1F2A44]">
                      {col}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : viewMode === 'table' ? (
          <div className="overflow-x-auto rounded border border-[#1F2A44] bg-[#0F1626]">
            <table className="w-full text-xs text-left">
              <thead className="bg-[#131A2B] text-slate-300 border-b border-[#1F2A44] font-mono uppercase text-[10px] tracking-wide">
                <tr>
                  {Object.keys(executionData[0]).map(key => (
                    <th key={key} className="px-4 py-2.5 text-slate-300 font-semibold">{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1F2A44]/60">
                {executionData.map((row, i) => (
                  <tr key={i} className="hover:bg-[#131A2B]/80 transition-colors">
                    {Object.values(row).map((val, j) => (
                      <td key={j} className="px-4 py-2 text-slate-300 font-mono">
                        {val !== null && val !== undefined ? String(val) : '-'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-end gap-2">
              <span className="text-[11px] text-slate-400 font-mono">Chart Type:</span>
              <select
                value={chartType}
                onChange={(e) => setChartType(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-xs text-slate-200 px-2 py-1 rounded outline-none"
              >
                <option value="bar">Bar Chart</option>
                <option value="line">Line Chart</option>
                <option value="pie">Pie Chart</option>
              </select>
            </div>
            <div className="p-4 bg-slate-950 border border-slate-800 rounded">
              {renderChartContent()}
            </div>
          </div>
        )}

        {/* Key Intelligence Insights */}
        {insights && insights.length > 0 && (
          <div className="space-y-2 pt-1">
            <h4 className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
              <span>Automated Intelligence Takeaways</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {insights.map((ins, idx) => (
                <div key={idx} className="p-2.5 bg-slate-950 border border-slate-800 rounded flex items-start gap-2 text-xs text-slate-300 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{ins}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Dynamic Follow-up Suggestions */}
        {followupSuggestions && followupSuggestions.length > 0 && (
          <div className="pt-2 border-t border-[#1F2A44] space-y-1.5">
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wide block">
              Suggested Next Explorations:
            </span>
            <div className="flex flex-wrap gap-2">
              {followupSuggestions.map((sug, idx) => (
                <button
                  key={idx}
                  onClick={() => onRunFollowup(sug)}
                  className="px-2.5 py-1 rounded bg-[#131A2B] hover:bg-[#1A2340] border border-[#1F2A44] text-emerald-400 hover:text-emerald-300 text-xs font-medium transition-colors flex items-center gap-1.5"
                >
                  <span>{sug}</span>
                  <Play className="w-3 h-3 fill-current text-emerald-500" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Technical Inspection Toggle */}
        <div className="pt-2 border-t border-[#1F2A44]">
          <button
            onClick={() => setShowTechnical(!showTechnical)}
            className="text-[11px] font-mono font-semibold text-slate-400 hover:text-slate-200 uppercase tracking-wide flex items-center gap-2 transition-colors py-1"
          >
            {showTechnical ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            <span>{showTechnical ? "Hide SQL Inspection & Verification" : "Show SQL Inspection & Verification"}</span>
          </button>

          {showTechnical && (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
              <div className="p-3 bg-[#0F1626] border border-[#1F2A44] rounded space-y-2">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-emerald-400" /> SQL Expression Payload
                </span>
                <pre className="text-emerald-400 bg-[#080D1A] p-3 rounded border border-slate-800 overflow-x-auto text-[11px] leading-relaxed">
                  {sql || '-- Direct execution query'}
                </pre>
                {intent && (
                  <p className="text-[10px] text-slate-400 font-mono">Intent: <strong>{intent}</strong></p>
                )}
              </div>

              <div className="p-3 bg-[#0F1626] border border-[#1F2A44] rounded space-y-2 font-sans">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Pipeline Integrity Verification
                </span>
                {verification && (
                  <div className={`p-2.5 rounded border text-xs ${verification.is_valid ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' : 'bg-red-950/40 border-red-800 text-red-300'}`}>
                    <p className="font-bold">{verification.is_valid ? 'Verified Intent' : 'Intent Mismatch'}</p>
                    <p className="text-[11px] mt-0.5 opacity-80">{verification.explanation}</p>
                  </div>
                )}
                {validation && (
                  <div className={`p-2.5 rounded border text-xs ${validation.is_safe ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' : 'bg-red-950/40 border-red-800 text-red-300'}`}>
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

