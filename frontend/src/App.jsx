import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Database, Search, ShieldCheck, Play, CheckCircle2, XCircle,
  AlertCircle, Loader2, History, Clock, TrendingUp, BarChart2,
  LineChart as LineChartIcon, PieChart as PieChartIcon, Table as TableIcon,
  ChevronDown, ChevronUp, Info, Zap, Sparkles
} from 'lucide-react'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_URL = `${API_BASE}/api`

const AIBadge = ({ label = "AI Generated", className = "" }) => (
  <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-100/40 border border-emerald-200/30 text-[9px] font-black text-emerald-600/80 uppercase tracking-widest ${className}`}>
    <Sparkles className="w-2.5 h-2.5 fill-emerald-400" />
    {label}
  </div>
);

function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [sql, setSql] = useState('')
  const [intent, setIntent] = useState('')
  const [verification, setVerification] = useState(null)
  const [validation, setValidation] = useState(null)
  const [executionData, setExecutionData] = useState(null)
  const [suggestedViz, setSuggestedViz] = useState('table')
  const [selectedViz, setSelectedViz] = useState('')
  const [metadata, setMetadata] = useState(null)
  const [interpretedAnswer, setInterpretedAnswer] = useState('')
  const [executionError, setExecutionError] = useState(null)
  const [successMessage, setSuccessMessage] = useState('')
  const [showDetails, setShowDetails] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [crudData, setCrudData] = useState(null)
  const [showModal, setShowModal] = useState(false)
  const [formData, setFormData] = useState({})
  const [recentQueries, setRecentQueries] = useState([])
  const [frequentQueries, setFrequentQueries] = useState([])
  const [viewMode, setViewMode] = useState('table')
  const [databases, setDatabases] = useState([])
  const [selectedDbId, setSelectedDbId] = useState('')
  const [currentDbName, setCurrentDbName] = useState('')
  const [insights, setInsights] = useState([])
  const [prediction, setPrediction] = useState(null)
  const [predictLoading, setPredictLoading] = useState(false)
  const [dbError, setDbError] = useState(null)
  const [isSqlMode, setIsSqlMode] = useState(false)
  const [dbInsights, setDbInsights] = useState({ summary: '', suggested_queries: [] })
  const [insightsLoading, setInsightsLoading] = useState(false)
  const [followupSuggestions, setFollowupSuggestions] = useState([])

  useEffect(() => {
    fetchDatabases()
    fetchHistory()
  }, [])

  useEffect(() => {
    if (selectedDbId) {
      fetchDbInsights()
    }
  }, [selectedDbId])

  const fetchDatabases = async () => {
    try {
      const [listRes, currentRes] = await Promise.all([
        axios.get(`${API_URL}/databases`),
        axios.get(`${API_URL}/current-database`)
      ])
      setDatabases(listRes.data)
      setSelectedDbId(currentRes.data.id)
      setCurrentDbName(currentRes.data.name)
      setDbError(null)
    } catch (err) {
      console.error("Failed to fetch databases", err)
      setDatabases([])
      setSelectedDbId('')
      setDbError("Unable to connect to server. Please check if the backend is running.")
    }
  }

  const handleDbChange = async (dbId) => {
    try {
      setLoading(true)
      const res = await axios.post(`${API_URL}/select-database`, { db_id: dbId })
      if (res.data.success) {
        setSelectedDbId(dbId)
        // Refresh name and history
        const currentRes = await axios.get(`${API_URL}/current-database`)
        setCurrentDbName(currentRes.data.name)
        fetchHistory()
        // Clear results
        setExecutionData(null)
        setSql('')
        setValidation(null)
        setVerification(null)
      }
    } catch (err) {
      alert("Failed to switch database: " + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchHistory = async () => {
    try {
      const [recent, frequent] = await Promise.all([
        axios.get(`${API_URL}/queries/recent`),
        axios.get(`${API_URL}/queries/frequent`)
      ])
      setRecentQueries(recent.data)
      setFrequentQueries(frequent.data)
    } catch (err) {
      console.error("Failed to fetch history", err)
    }
  }

  const fetchDbInsights = async () => {
    setInsightsLoading(true)
    try {
      const res = await axios.get(`${API_URL}/database-insights`)
      setDbInsights(res.data)
    } catch (err) {
      console.error("Failed to fetch database insights", err)
      setDbInsights({ summary: '', suggested_queries: [] })
    } finally {
      setInsightsLoading(false)
    }
  }

  const reuseQuery = async (queryId) => {
    setLoading(true)
    setExecutionError(null)
    setExecutionData(null)
    setSuccessMessage('')
    try {
      const res = await axios.post(`${API_URL}/queries/reuse`, { query_id: queryId })
      if (res.data.success) {
        setExecutionData(res.data.data)
        setSuggestedViz(res.data.suggested_visualization || 'table')
        setMetadata(res.data.metadata)
        setSelectedViz('')
        setSql(res.data.sql || '')
        setQuery(res.data.natural_query || '')
        setInsights([])
        setPrediction(null)
        setFollowupSuggestions(res.data.followup_suggestions || [])
        fetchInsights(res.data.data)
        setCurrentStep(5)
        setShowDetails(false)
      } else {
        setExecutionError(res.data.error)
        setShowDetails(true)
      }
    } catch (err) {
      setExecutionError(err.response?.data?.detail || err.message)
      setShowDetails(true)
    } finally {
      setLoading(false)
      fetchHistory()
    }
  }

  const fetchInsights = async (data) => {
    try {
      const res = await axios.post(`${API_URL}/generate-insights`, {
        data,
        query: query,
        sql: sql
      })
      setInsights(res.data.insights)
    } catch (err) {
      console.error("Failed to fetch insights", err)
    }
  }

  const handlePredict = async () => {
    if (!executionData) return;
    setPredictLoading(true)
    setPrediction(null)
    try {
      const res = await axios.post(`${API_URL}/predict-trend`, {
        data: executionData,
        query: query,
        sql: sql
      })
      setPrediction(res.data)
    } catch (err) {
      console.error("Prediction failed", err)
    } finally {
      setPredictLoading(false)
    }
  }

  const runPipeline = async () => {
    if (!query) return;
    setLoading(true)
    setSql('')
    setIntent('')
    setVerification(null)
    setValidation(null)
    setExecutionData(null)
    setInterpretedAnswer('')
    setExecutionError(null)
    setSuccessMessage('')
    setCrudData(null)
    setInsights([])
    setPrediction(null)
    setFollowupSuggestions([])
    setIsSqlMode(false)
    try {
      setCurrentStep(0)

      // Mode Detection
      const modeRes = await axios.post(`${API_URL}/detect-mode`, { query })
      const sqlMode = modeRes.data.mode === 'SQL'
      setIsSqlMode(sqlMode)

      let finalSql = ''

      if (sqlMode) {
        // Direct SQL Pipeline: Skip generation and verification
        finalSql = query
        setSql(finalSql)
        setIntent('Direct SQL Execution')
        setCurrentStep(3) // Jump to Validation
      } else {
        // Natural Language Pipeline
        const intentRes = await axios.post(`${API_URL}/generate-form`, { query })
        if (intentRes.data.operation === 'ERROR') {
          setExecutionError(intentRes.data.error)
          setLoading(false)
          setShowDetails(true)
          return
        }
        if (intentRes.data.operation !== 'READ') {
          setCrudData(intentRes.data)
          setFormData(intentRes.data.form.prefill || {})
          setShowModal(true)
          setLoading(false)
          return
        }
        setCurrentStep(1)
        const genRes = await axios.post(`${API_URL}/generate-sql`, { query })
        if (genRes.data.is_ambiguous) {
          setExecutionError(genRes.data.message)
          setLoading(false)
          setShowDetails(true)
          return
        }
        finalSql = genRes.data.sql
        setSql(finalSql)
        setIntent(genRes.data.intent)
        setCurrentStep(2)
        const verRes = await axios.post(`${API_URL}/verify-sql`, { query, sql: finalSql })
        setVerification(verRes.data)
        if (!verRes.data.is_valid) {
          setLoading(false)
          setShowDetails(true)
          return
        }
        setCurrentStep(3)
      }

      const valRes = await axios.post(`${API_URL}/validate-sql?is_direct_sql=${sqlMode}`, { sql: finalSql })
      setValidation(valRes.data)
      if (!valRes.data.is_safe) {
        setLoading(false)
        setShowDetails(true)
        return
      }

      setCurrentStep(4)
      const execRes = await axios.post(`${API_URL}/execute-query`, {
        sql: finalSql,
        natural_query: sqlMode ? null : query,
        is_direct_sql: sqlMode
      })
      if (execRes.data.success) {
        setExecutionData(execRes.data.data)
        setInterpretedAnswer(execRes.data.interpreted_answer || '')
        setSuggestedViz(execRes.data.suggested_visualization || 'table')
        setMetadata(execRes.data.metadata)
        setSelectedViz('')
        setFollowupSuggestions(execRes.data.followup_suggestions || [])
        fetchInsights(execRes.data.data)
        fetchHistory()
      } else {
        setExecutionError(execRes.data.error)
        setShowDetails(true)
      }
    } catch (err) {
      setExecutionError(err.response?.data?.detail || err.message)
      setShowDetails(true)
    } finally {
      setLoading(false)
      setCurrentStep(5)
    }
  }

  const handleCRUDSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await axios.post(`${API_URL}/execute-form`, {
        operation: crudData.operation,
        table: crudData.table,
        fields: formData,
        where: crudData.form.where
      })
      if (res.data.success) {
        setSuccessMessage(res.data.message)
        setShowModal(false)
        setQuery('')
      } else {
        alert("Error: " + res.data.error)
      }
    } catch (err) {
      alert("Execution failed: " + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const renderChart = (data) => {
    const type = selectedViz || suggestedViz || 'table'
    if (type === 'table' || !data || data.length === 0) return null;
    const keys = Object.keys(data[0])
    const { numeric_columns, categorical_columns, time_columns } = metadata || {
      numeric_columns: [], categorical_columns: [], time_columns: []
    }
    let xKey = keys[0]
    let yKey = keys.find(k => typeof data[0][k] === 'number') || keys[1]
    if (type === 'line') {
      xKey = time_columns[0] || categorical_columns[0] || keys[0]
      yKey = numeric_columns[0] || keys[1]
    } else if (type === 'bar' || type === 'pie') {
      xKey = categorical_columns[0] || time_columns[0] || keys[0]
      yKey = numeric_columns[0] || keys[1]
    }
    const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
    if (type === 'bar') {
      return (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
          <Tooltip contentStyle={{ backgroundColor: '#fff', borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
          <Legend />
          <Bar dataKey={yKey} fill="#6366f1" radius={[4, 4, 0, 0]} />
        </BarChart>
      )
    }
    if (type === 'line') {
      return (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
          <Tooltip contentStyle={{ backgroundColor: '#fff', borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
          <Legend />
          <Line type="monotone" dataKey={yKey} stroke="#6366f1" strokeWidth={3} dot={{ r: 4, fill: '#6366f1', strokeWidth: 2, stroke: '#fff' }} />
        </LineChart>
      )
    }
    if (type === 'pie') {
      return (
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey={yKey} nameKey={xKey}>
            {data.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={{ backgroundColor: '#fff', borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
          <Legend />
        </PieChart>
      )
    }
    return null
  }

  return (
    <div className="min-h-screen bg-[#f8faf9] flex font-sans text-slate-800">
      {/* Sidebar - Glassmorphism */}
      <div className="w-80 bg-white/40 backdrop-blur-3xl border-r border-slate-200/50 flex flex-col h-screen sticky top-0 overflow-y-auto">
        <div className="p-8">
          <h1
            onClick={() => window.location.reload()}
            className="text-2xl font-black text-emerald-900 tracking-tight flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity"
          >
            <div className="w-10 h-10 bg-emerald-200 rounded-2xl flex items-center justify-center shadow-sm shadow-emerald-100 animate-float">
              <Zap className="w-6 h-6 text-emerald-600 fill-emerald-600" />
            </div>
            HADIL
          </h1>
          <div className="mt-10">
            <label className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em] block mb-3 px-1">
              Data Source
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                <Database className="w-4 h-4 text-emerald-400 group-hover:text-emerald-600 transition-colors" />
              </div>
              <select
                value={selectedDbId}
                onChange={(e) => handleDbChange(e.target.value)}
                className={`w-full bg-white/60 border ${dbError ? 'border-red-300' : 'border-emerald-100/50'} text-slate-700 text-sm font-bold pl-12 pr-10 py-4 rounded-2xl appearance-none cursor-pointer hover:border-emerald-300 hover:bg-white transition-all focus:outline-none focus:ring-4 focus:ring-emerald-500/5 shadow-sm`}
              >
                {databases.length === 0 && !dbError && <option value="">Detecting sources...</option>}
                {dbError && <option value="">Connection Offline</option>}
                {databases.map(db => (
                  <option key={db.id} value={db.id}>{db.name}</option>
                ))}
              </select>
              <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none">
                <ChevronDown className="w-4 h-4 text-emerald-400" />
              </div>
            </div>
            {dbError && (
              <div className="mt-4 p-4 bg-red-50/50 backdrop-blur-sm border border-red-100 rounded-2xl">
                <p className="text-[10px] text-red-600 font-black uppercase tracking-wider flex items-center gap-2 mb-2">
                  <AlertCircle className="w-3.5 h-3.5" /> Engine Offline
                </p>
                <p className="text-[11px] text-red-500 leading-relaxed mb-3">
                  {dbError}
                </p>
                <button
                  onClick={fetchDatabases}
                  className="text-[11px] text-emerald-600 font-black uppercase tracking-widest hover:text-emerald-700 flex items-center gap-1.5"
                >
                  <Zap className="w-3 h-3" /> Reconnect
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="p-6 space-y-10">
          <section className="space-y-4">
            <h3 className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em] flex items-center gap-2 px-2">
              <Clock className="w-3.5 h-3.5" /> Recent Queries
            </h3>
            <div className="space-y-2">
              {recentQueries.map((q) => (
                <button key={q.id} onClick={() => reuseQuery(q.id)} className="w-full text-left p-4 rounded-2xl hover:bg-white/60 hover:shadow-sm border border-transparent hover:border-emerald-100 transition-all group">
                  <p className="text-[13px] font-medium text-slate-600 line-clamp-2 group-hover:text-emerald-700">{q.natural_query}</p>
                </button>
              ))}
            </div>
          </section>
          <section className="space-y-4">
            <h3 className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em] flex items-center gap-2 px-2">
              <TrendingUp className="w-3.5 h-3.5" /> Frequent Access
            </h3>
            <div className="space-y-2">
              {frequentQueries.map((q) => (
                <button key={q.id} onClick={() => reuseQuery(q.id)} className="w-full text-left p-4 rounded-2xl hover:bg-white/60 hover:shadow-sm border border-transparent hover:border-emerald-100 transition-all group">
                  <div className="flex justify-between items-start gap-3">
                    <p className="text-[13px] font-medium text-slate-600 line-clamp-2 group-hover:text-emerald-700">{q.natural_query}</p>
                    <span className="text-[10px] bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-black shrink-0">{q.usage_count}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>

      <div className="flex-1 p-12 overflow-y-auto">
        <div className="max-w-5xl mx-auto space-y-12">
          <header className="space-y-3">
            <h2 className="text-4xl font-black text-slate-900 tracking-tight leading-tight">HADIL Insight Engine</h2>
            <p className="text-lg text-slate-500 font-medium">Safe, AI-powered analytics with semantic precision.</p>
          </header>

          {dbInsights.summary && !executionData && !loading && (
            <div className="animate-in fade-in slide-in-from-top-4 duration-700">
              <div className="bg-emerald-50/50 backdrop-blur-sm border border-emerald-100/50 rounded-[32px] p-8 flex items-start gap-6">
                <div className="w-12 h-12 bg-white rounded-2xl flex items-center justify-center shadow-sm shrink-0 border border-emerald-100">
                  <Info className="w-6 h-6 text-emerald-500" />
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h4 className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em]">Database Summary</h4>
                    <AIBadge label="AI Analysis" />
                  </div>
                  <p className="text-slate-600 font-medium leading-relaxed italic text-lg">"{dbInsights.summary}"</p>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-8">
            <div className="glass-card rounded-[32px] p-2 flex gap-3 items-center transition-all focus-within:ring-4 focus-within:ring-emerald-500/10 focus-within:bg-white focus-within:border-emerald-200">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask a business question..."
                className="flex-1 px-8 py-5 bg-transparent focus:outline-none text-xl text-slate-800 placeholder-slate-300 font-medium"
                onKeyDown={(e) => e.key === 'Enter' && runPipeline()}
              />
              <button
                onClick={runPipeline}
                disabled={loading || !query || !selectedDbId}
                className={`${isSqlMode ? 'bg-slate-900' : 'pastel-green-button'} disabled:opacity-30 flex items-center gap-3`}
              >
                {loading ? <Loader2 className="w-6 h-6 animate-spin" /> : (isSqlMode ? <Database className="w-6 h-6" /> : <Search className="w-6 h-6" />)}
                <span className="text-lg tracking-tight">{loading ? 'Processing...' : (isSqlMode ? 'Run SQL' : 'Analyze')}</span>
              </button>
            </div>

            {!executionData && !loading && dbInsights.suggested_queries.length > 0 && (
              <div className="space-y-6 animate-in fade-in duration-1000 delay-300">
                <div className="flex items-center justify-between px-2">
                  <div className="flex items-center gap-3">
                    <Zap className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em]">Suggested Explorations</h3>
                  </div>
                  <AIBadge label="AI Suggestions" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dbInsights.suggested_queries.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => { setQuery(q); setTimeout(() => runPipeline(), 100); }}
                      className="group text-left p-6 bg-white border border-slate-100 rounded-[28px] hover:border-emerald-300 hover:shadow-xl hover:shadow-emerald-500/5 transition-all duration-300"
                    >
                      <p className="text-[15px] font-semibold text-slate-600 group-hover:text-emerald-700 leading-snug">{q}</p>
                      <div className="mt-4 flex items-center gap-2 text-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity">
                        <span className="text-[10px] font-black uppercase tracking-widest">Ask this</span>
                        <Play className="w-3 h-3 fill-emerald-400" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {isSqlMode && (
              <p className="text-[11px] text-emerald-600 font-black uppercase tracking-[0.2em] px-8 flex items-center gap-2 animate-pulse">
                <ShieldCheck className="w-4 h-4" /> SQL SAFETY MODE ACTIVE
              </p>
            )}
            {!selectedDbId && (
              <p className="text-xs text-red-500 font-bold px-8 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> Please select a data source to begin analysis.
              </p>
            )}

            {(executionData || executionError || successMessage || loading) && (
              <div className="glass-card rounded-[40px] overflow-hidden">
                <div className="px-10 py-6 border-b border-emerald-50/50 flex justify-between items-center bg-white/40">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${loading ? 'bg-emerald-400 animate-pulse' : (executionError ? 'bg-red-400' : 'bg-emerald-500')}`} />
                    <span className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em]">{loading ? 'Synthesizing...' : 'Intelligent Response'}</span>
                  </div>
                  {executionData && executionData.length > 0 && (
                    <div className="flex bg-emerald-50 p-1 rounded-2xl border border-emerald-100/30">
                      <button onClick={() => setViewMode('table')} className={`px-4 py-2 rounded-xl text-xs font-black uppercase tracking-tighter flex items-center gap-2 transition-all ${viewMode === 'table' ? 'bg-white text-emerald-600 shadow-sm' : 'text-emerald-400'}`}><TableIcon className="w-4 h-4" /> Data</button>
                      <button onClick={() => setViewMode('chart')} className={`px-4 py-2 rounded-xl text-xs font-black uppercase tracking-tighter flex items-center gap-2 transition-all ${viewMode === 'chart' ? 'bg-white text-emerald-600 shadow-sm' : 'text-emerald-400'}`}><BarChart2 className="w-4 h-4" /> Viz</button>
                    </div>
                  )}
                </div>
                <div className="p-10">
                  {loading ? (
                    <div className="py-20 flex flex-col items-center justify-center space-y-6">
                      <div className="relative">
                        <div className="absolute inset-0 bg-emerald-200 blur-2xl opacity-20 rounded-full animate-pulse" />
                        <Loader2 className="w-16 h-16 text-emerald-500 animate-spin relative z-10" />
                      </div>
                      <p className="text-emerald-900/60 font-black uppercase tracking-[0.3em] text-[10px]">Verifying Safety Pipeline</p>
                    </div>
                  ) : executionError ? (
                    <div className="p-8 rounded-3xl bg-red-50/50 border border-red-100 text-red-700 flex items-start gap-5">
                      <AlertCircle className="w-8 h-8 shrink-0 text-red-400" />
                      <div><p className="font-black uppercase tracking-widest text-[11px] mb-1">System Error</p><p className="text-lg font-medium leading-relaxed">{executionError}</p></div>
                    </div>
                  ) : successMessage ? (
                    <div className="p-8 rounded-3xl bg-emerald-50/50 border border-emerald-100 text-emerald-700 flex items-start gap-5">
                      <CheckCircle2 className="w-8 h-8 shrink-0 text-emerald-500" /><p className="text-lg font-medium">{successMessage}</p>
                    </div>
                  ) : executionData && executionData.length > 0 ? (
                    <div className="space-y-10">
                      {interpretedAnswer && (
                        <div className="p-8 bg-[#a7f3d0] rounded-[32px] text-emerald-900 shadow-xl shadow-emerald-500/10 border border-emerald-200/50 animate-in zoom-in-95 duration-500 relative overflow-hidden">
                          <div className="absolute top-4 right-6">
                            <AIBadge label="AI Interpretation" className="bg-white/40 border-emerald-400/20" />
                          </div>
                          <p className="text-2xl font-black leading-tight tracking-tight italic">{interpretedAnswer}</p>
                        </div>
                      )}
                      <div className="flex justify-between items-center">
                        <h3 className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em] flex items-center gap-2 px-2">
                          <BarChart2 className="w-4 h-4" /> Interactive Dataset
                        </h3>
                        <button
                          onClick={handlePredict}
                          disabled={predictLoading || executionData.length < 3}
                          className="text-xs bg-[#fdf2f8] text-pink-700 px-4 py-2 rounded-xl font-black uppercase tracking-tighter hover:bg-[#fce7f3] transition-all flex items-center gap-2 disabled:opacity-30"
                        >
                          {predictLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TrendingUp className="w-3.5 h-3.5" />}
                          Generate Forecast
                        </button>
                      </div>

                      {prediction && (
                        <div className="p-8 bg-white/60 rounded-[32px] border border-emerald-100/50 animate-in slide-in-from-top-4 duration-500">
                          <div className="flex justify-between items-start mb-6">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-emerald-100 rounded-xl text-emerald-600"><Zap className="w-5 h-5 fill-emerald-600" /></div>
                              <h4 className="font-black text-slate-800 uppercase tracking-widest text-xs">AI Forecasting</h4>
                              <AIBadge label="AI Prediction" />
                            </div>
                            <div className="flex gap-2">
                              <span className={`text-[10px] uppercase tracking-[0.1em] font-black px-3 py-1.5 rounded-full ${prediction.confidence?.startsWith('High') ? 'bg-emerald-100 text-emerald-700' :
                                  prediction.confidence?.startsWith('Medium') ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600'
                                }`}>
                                Confidence: {prediction.confidence}
                              </span>
                              <span className="text-[10px] uppercase tracking-[0.1em] font-black px-3 py-1.5 bg-slate-100 text-slate-500 rounded-full">
                                {prediction.method}
                              </span>
                            </div>
                          </div>

                          {prediction.error ? (
                            <p className="text-sm text-red-500 font-medium">{prediction.error}</p>
                          ) : (
                            <div className="space-y-6">
                              <p className="text-xl text-slate-700 leading-relaxed font-medium italic border-l-4 border-emerald-200 pl-6">
                                {prediction.message}
                              </p>

                              {prediction.why && (
                                <div className="pt-6 border-t border-emerald-100/30">
                                  <p className="text-[10px] text-emerald-800/30 font-black uppercase tracking-[0.2em] mb-2">Algorithm Rationale</p>
                                  <p className="text-xs text-slate-500 leading-relaxed font-medium">{prediction.why}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {viewMode === 'table' ? (
                        <div className="overflow-x-auto rounded-3xl border border-emerald-100/50 bg-white/50">
                          <table className="w-full text-sm text-left">
                            <thead className="bg-emerald-50/50 text-emerald-800/60 border-b border-emerald-100/50">
                              <tr>{Object.keys(executionData[0]).map(key => <th key={key} className="px-8 py-5 font-black uppercase tracking-[0.1em] text-[11px]">{key}</th>)}</tr>
                            </thead>
                            <tbody className="divide-y divide-emerald-100/20">
                              {executionData.map((row, i) => <tr key={i} className="hover:bg-emerald-50/30 transition-colors">{Object.values(row).map((val, j) => <td key={j} className="px-8 py-5 text-slate-600 font-medium">{String(val)}</td>)}</tr>)}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="space-y-6">
                          <div className="flex justify-end">
                            <select value={selectedViz || suggestedViz} onChange={(e) => setSelectedViz(e.target.value)} className="bg-white border border-emerald-100 text-emerald-700 text-[11px] font-black uppercase tracking-widest px-4 py-2 rounded-xl outline-none focus:ring-4 focus:ring-emerald-500/10 transition-all">
                              <option value="bar">Bar Chart</option><option value="line">Line Chart</option><option value="pie">Pie Chart</option><option value="table">Table View</option>
                            </select>
                          </div>
                          <div className="h-[450px] w-full bg-white/40 rounded-3xl p-8 border border-white/50">
                            <ResponsiveContainer width="100%" height="100%">{renderChart(executionData)}</ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {insights.length > 0 && (
                        <div className="pt-10 border-t border-emerald-100/30 space-y-6">
                          <div className="flex items-center justify-between px-2">
                            <h3 className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em] flex items-center gap-2">
                              <Zap className="w-4 h-4 text-emerald-400" /> Key Intelligence
                            </h3>
                            <AIBadge label="AI Generated Insights" />
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {insights.map((insight, idx) => (
                              <div key={idx} className="flex items-start gap-4 p-5 bg-white/50 rounded-[24px] border border-emerald-100/30 hover:border-emerald-300 transition-all hover:shadow-sm">
                                <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                                <p className="text-[13px] text-slate-600 font-medium leading-relaxed">{insight}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {followupSuggestions.length > 0 && (
                        <div className="pt-10 border-t border-emerald-100/30 space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
                          <div className="flex items-center justify-between px-2">
                            <div className="flex items-center gap-3">
                              <Sparkles className="w-4 h-4 text-emerald-400" />
                              <h3 className="text-[11px] font-black text-emerald-800/40 uppercase tracking-[0.2em]">Continue Exploring</h3>
                            </div>
                            <AIBadge label="AI Suggested Follow-ups" />
                          </div>
                          <div className="flex flex-wrap gap-3">
                            {followupSuggestions.map((suggestion, idx) => (
                              <button
                                key={idx}
                                onClick={() => { setQuery(suggestion); setTimeout(() => runPipeline(), 100); }}
                                className="px-6 py-3 bg-white border border-emerald-100 rounded-2xl text-sm font-semibold text-emerald-700 hover:bg-emerald-50 hover:border-emerald-300 hover:shadow-md transition-all active:scale-95 flex items-center gap-2 group"
                              >
                                {suggestion}
                                <Play className="w-2.5 h-2.5 fill-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : executionData && <div className="py-20 text-center text-slate-400 italic bg-white/40 rounded-[32px] border-2 border-dashed border-emerald-100/50 flex flex-col items-center gap-4">
                    <div className="p-4 bg-white rounded-full"><Search className="w-10 h-10 text-slate-200" /></div>
                    <p className="font-medium text-lg">No records found for this query context.</p>
                  </div>}
                </div>
              </div>
            )}
          </div>

          {(sql || verification || validation) && (
            <div className="space-y-6 pt-10">
              <button onClick={() => setShowDetails(!showDetails)} className="flex items-center gap-3 text-emerald-800/40 hover:text-emerald-600 font-black text-[11px] uppercase tracking-[0.3em] transition-all mx-auto bg-emerald-50/50 px-6 py-2 rounded-full border border-emerald-100/50">
                {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                {showDetails ? 'Hide Technical' : 'Inspection Panel'}
              </button>
              {showDetails && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 animate-in slide-in-from-bottom-8 duration-500">
                  <div className="glass-card rounded-[32px] p-8 space-y-6">
                    <h3 className="text-[11px] font-black flex items-center gap-2 text-emerald-800/40 uppercase tracking-[0.2em]"><Database className="w-4 h-4" /> SQL Expression</h3>
                    <div className="bg-slate-900 rounded-[24px] p-6 overflow-x-auto shadow-inner shadow-black/20"><code className="text-emerald-400 font-mono text-sm leading-relaxed">{sql || '-- No SQL Payload'}</code></div>
                    {intent && <div className="text-[11px] bg-emerald-50 text-emerald-800/60 px-4 py-3 rounded-2xl inline-flex items-center gap-3 border border-emerald-100/50"><strong>METADATA:</strong> {intent}</div>}
                  </div>
                  <div className="glass-card rounded-[32px] p-8 space-y-8">
                    <div className="space-y-4">
                      <h3 className="text-[11px] font-black flex items-center gap-2 text-emerald-800/40 uppercase tracking-[0.2em]"><ShieldCheck className="w-4 h-4" /> Pipeline Integrity</h3>
                      {verification && <div className={`p-5 rounded-2xl border ${verification.is_valid ? 'bg-emerald-50/50 border-emerald-100' : 'bg-red-50/50 border-red-100'}`}>
                        <div className="flex items-start gap-4">
                          {verification.is_valid ? <CheckCircle2 className="w-6 h-6 text-emerald-500" /> : <XCircle className="w-6 h-6 text-red-500" />}
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <p className="text-xs font-black uppercase tracking-widest">{verification.is_valid ? 'Intent Verified' : 'Intent Mismatch'}</p>
                              <AIBadge label="AI Explanation" />
                            </div>
                            <p className="text-[11px] leading-relaxed opacity-70">{verification.explanation}</p>
                          </div>
                        </div>
                      </div>}
                    </div>
                    <div className="space-y-3">
                      <h3 className="text-sm font-bold flex items-center gap-2 text-slate-400 uppercase tracking-widest"><AlertCircle className="w-4 h-4" /> Safety</h3>
                      {validation && <div className={`p-4 rounded-2xl border ${validation.is_safe ? 'bg-emerald-50 border-emerald-100' : 'bg-red-50 border-red-100'}`}>
                        <div className="flex items-start gap-3">
                          {validation.is_safe ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <XCircle className="w-5 h-5 text-red-600" />}
                          <p className="text-xs font-bold">{validation.is_safe ? 'Safe' : 'Violated'}</p>
                        </div>
                      </div>}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {showModal && crudData && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-[40px] w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-500">
            <div className="bg-emerald-200 p-10 text-emerald-900 shadow-xl shadow-emerald-500/10">
              <h2 className="text-3xl font-black flex items-center gap-4 tracking-tight leading-none"><ShieldCheck className="w-10 h-10" /> Secure {crudData.operation}</h2>
              <p className="text-emerald-800/60 mt-4 font-medium uppercase tracking-widest text-[11px]">Final Authorization Required</p>
            </div>
            <form onSubmit={handleCRUDSubmit} className="p-10 space-y-8">
              <div className="space-y-6 max-h-[50vh] overflow-y-auto pr-4 custom-scrollbar">
                {crudData.form.fields.map(field => (
                  <div key={field.name} className="space-y-2">
                    <label className="text-[11px] font-black text-emerald-800/40 uppercase tracking-widest ml-1">{field.name}</label>
                    <input type="text" value={formData[field.name] || ''} onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })} className="w-full px-6 py-4 bg-emerald-50/30 border border-emerald-100/50 rounded-2xl outline-none focus:ring-4 focus:ring-emerald-500/10 transition-all text-slate-700 font-medium" />
                  </div>
                ))}
              </div>
              <div className="pt-6 flex gap-4">
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 px-8 py-4 border border-emerald-100 text-emerald-800/60 rounded-[24px] hover:bg-emerald-50 transition-all font-black uppercase tracking-widest text-xs">Cancel</button>
                <button type="submit" className="flex-1 px-8 py-4 bg-emerald-300 text-emerald-900 rounded-[24px] font-black uppercase tracking-widest text-xs hover:bg-emerald-400 transition-all shadow-lg shadow-emerald-200">Execute Transaction</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
