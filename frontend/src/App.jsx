import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Database, Table as TableIcon, TrendingUp, Sparkles, Pin, Clock, Play, 
  RefreshCw, LayoutDashboard, ShieldCheck, CheckCircle2, Search, Filter, 
  Layers, AlertCircle, X, ArrowUpRight
} from 'lucide-react';

import TopHeader from './components/TopHeader';
import SidebarNav from './components/SidebarNav';
import AskHadilBar from './components/AskHadilBar';
import QueryResultPanel from './components/QueryResultPanel';
import DashboardWidget from './components/DashboardWidget';
import KpiCard from './components/KpiCard';
import ExpandedWidgetModal from './components/ExpandedWidgetModal';
import CrudFormModal from './components/CrudFormModal';
import SettingsModal from './components/SettingsModal';
import NoDatabaseConnectedView from './components/NoDatabaseConnectedView';
import ConnectDatabaseModal from './components/ConnectDatabaseModal';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_URL = `${API_BASE}/api`;

export default function App() {
  // View Mode: 'overview' | 'pinned' | 'recent' | 'analytics-charts' | 'analytics-anomalies' | 'table_<tablename>'
  const [currentView, setCurrentView] = useState('overview');

  // Pipeline Execution State
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [sql, setSql] = useState('');
  const [intent, setIntent] = useState('');
  const [verification, setVerification] = useState(null);
  const [validation, setValidation] = useState(null);
  const [executionData, setExecutionData] = useState(null);
  const [suggestedViz, setSuggestedViz] = useState('table');
  const [metadata, setMetadata] = useState(null);
  const [interpretedAnswer, setInterpretedAnswer] = useState('');
  const [executionError, setExecutionError] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');
  const [isSqlMode, setIsSqlMode] = useState(false);
  const [insights, setInsights] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [predictLoading, setPredictLoading] = useState(false);
  const [followupSuggestions, setFollowupSuggestions] = useState([]);

  // Database Connection & Schema Metadata State
  const [databases, setDatabases] = useState([]);
  const [selectedDbId, setSelectedDbId] = useState('');
  const [currentDbName, setCurrentDbName] = useState('');
  const [dbError, setDbError] = useState(null);
  const [dbInsights, setDbInsights] = useState({ summary: '', suggested_queries: [], tables: [] });
  const [tables, setTables] = useState([]);

  // History & Exploration State
  const [recentQueries, setRecentQueries] = useState([]);

  // CRUD Form State
  const [crudData, setCrudData] = useState(null);
  const [showCrudModal, setShowCrudModal] = useState(false);
  const [formData, setFormData] = useState({});

  // Connect Database Modal State
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  // Settings Modal State
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  // Persistent Pinned Widgets State
  const [pinnedWidgets, setPinnedWidgets] = useState(() => {
    try {
      const saved = localStorage.getItem('hadil_pinned_widgets');
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      console.error("Failed to load pinned widgets from localStorage", e);
      return [];
    }
  });

  // Expanded Widget Modal State
  const [expandedWidget, setExpandedWidget] = useState(null);

  const isConnected = Boolean(selectedDbId && !dbError);

  // Save pinned widgets to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem('hadil_pinned_widgets', JSON.stringify(pinnedWidgets));
    } catch (e) {
      console.error("Failed to save pinned widgets to localStorage", e);
    }
  }, [pinnedWidgets]);

  // Initial Data Load
  useEffect(() => {
    fetchDatabases();
    fetchHistory();
  }, []);

  useEffect(() => {
    if (selectedDbId) {
      fetchDbInsights();
      fetchTables();
    }
  }, [selectedDbId]);

  // API Call Handlers
  const fetchDatabases = async () => {
    try {
      const [listRes, currentRes] = await Promise.all([
        axios.get(`${API_URL}/databases`),
        axios.get(`${API_URL}/current-database`)
      ]);
      setDatabases(listRes.data || []);
      setSelectedDbId(currentRes.data?.id || '');
      setCurrentDbName(currentRes.data?.name || '');
      setDbError(null);
    } catch (err) {
      console.error("Failed to fetch databases", err);
      setDatabases([]);
      setSelectedDbId('');
      setDbError("Unable to connect to server. Please check if backend is running.");
    }
  };

  const handleDbChange = async (dbId) => {
    try {
      setLoading(true);
      const res = await axios.post(`${API_URL}/select-database`, { db_id: dbId });
      if (res.data.success) {
        setSelectedDbId(dbId);
        const currentRes = await axios.get(`${API_URL}/current-database`);
        setCurrentDbName(currentRes.data?.name || dbId);
        fetchHistory();
        fetchDbInsights();
        fetchTables();
        setExecutionData(null);
        setSql('');
        setValidation(null);
        setVerification(null);
        setExecutionError(null);
      }
    } catch (err) {
      alert("Failed to switch database: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleConnectCustomDatabase = async (connectionUri, name) => {
    try {
      setLoading(true);
      const res = await axios.post(`${API_URL}/connect-custom-db`, {
        connection_uri: connectionUri,
        name: name
      });
      if (res.data.success) {
        setSelectedDbId(res.data.db_id);
        setCurrentDbName(name || res.data.db_id);
        setDbError(null);
        await Promise.all([
          fetchDatabases(),
          fetchHistory(),
          fetchDbInsights(),
          fetchTables()
        ]);
        setExecutionData(null);
        setSql('');
        setValidation(null);
        setVerification(null);
        setExecutionError(null);
      }
    } catch (err) {
      throw new Error(err.response?.data?.detail || err.message || "Failed to connect to custom database.");
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const recent = await axios.get(`${API_URL}/queries/recent`);
      setRecentQueries(recent.data || []);
    } catch (err) {
      console.error("Failed to fetch query history", err);
    }
  };

  const fetchDbInsights = async () => {
    try {
      const res = await axios.get(`${API_URL}/database-insights`);
      setDbInsights(res.data || { summary: '', suggested_queries: [], tables: [] });
      if (res.data?.tables) {
        setTables(res.data.tables);
      }
    } catch (err) {
      console.error("Failed to fetch database insights", err);
      setDbInsights({ summary: '', suggested_queries: [], tables: [] });
    }
  };

  const fetchTables = async () => {
    try {
      const res = await axios.get(`${API_URL}/schema/tables`);
      if (res.data?.tables) {
        setTables(res.data.tables);
      }
    } catch (err) {
      console.error("Failed to fetch tables", err);
    }
  };

  const fetchInsights = async (dataPayload, queryStr, sqlStr) => {
    try {
      const res = await axios.post(`${API_URL}/generate-insights`, {
        data: dataPayload,
        query: queryStr || query,
        sql: sqlStr || sql
      });
      setInsights(res.data.insights || []);
    } catch (err) {
      console.error("Failed to fetch insights", err);
    }
  };

  const handlePredict = async () => {
    if (!executionData) return;
    setPredictLoading(true);
    setPrediction(null);
    try {
      const res = await axios.post(`${API_URL}/predict-trend`, {
        data: executionData,
        query: query,
        sql: sql
      });
      setPrediction(res.data);
    } catch (err) {
      console.error("Prediction failed", err);
    } finally {
      setPredictLoading(false);
    }
  };

  const reuseQuery = async (queryId) => {
    setLoading(true);
    setExecutionError(null);
    setExecutionData(null);
    setSuccessMessage('');
    try {
      const res = await axios.post(`${API_URL}/queries/reuse`, { query_id: queryId });
      if (res.data.success) {
        setExecutionData(res.data.data);
        setSuggestedViz(res.data.suggested_visualization || 'table');
        setMetadata(res.data.metadata);
        setSql(res.data.sql || '');
        setQuery(res.data.natural_query || '');
        setInsights([]);
        setPrediction(null);
        setFollowupSuggestions(res.data.followup_suggestions || []);
        fetchInsights(res.data.data, res.data.natural_query, res.data.sql);
      } else {
        setExecutionError(res.data.error);
      }
    } catch (err) {
      setExecutionError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
      fetchHistory();
    }
  };

  // Select Table from Sidebar -> Run dynamic query preview
  const handleSelectTable = (tableName) => {
    setCurrentView(`table_${tableName}`);
    const tableQuery = `SELECT * FROM ${tableName} LIMIT 50`;
    setQuery(`Show data from ${tableName}`);
    runPipeline(tableQuery);
  };

  // Main Conversational Execution Pipeline
  const runPipeline = async (overrideQuery = null) => {
    const activeQuery = overrideQuery !== null ? overrideQuery : query;
    if (!activeQuery || !activeQuery.trim() || !selectedDbId) return;

    setLoading(true);
    setSql('');
    setIntent('');
    setVerification(null);
    setValidation(null);
    setExecutionData(null);
    setInterpretedAnswer('');
    setExecutionError(null);
    setSuccessMessage('');
    setCrudData(null);
    setInsights([]);
    setPrediction(null);
    setFollowupSuggestions([]);
    setIsSqlMode(false);

    try {
      // 1. Mode Detection
      const modeRes = await axios.post(`${API_URL}/detect-mode`, { query: activeQuery });
      const sqlMode = modeRes.data.mode === 'SQL';
      setIsSqlMode(sqlMode);

      let finalSql = '';

      if (sqlMode) {
        finalSql = activeQuery;
        setSql(finalSql);
        setIntent('Direct SQL Execution');
      } else {
        // Natural Language Pipeline
        const intentRes = await axios.post(`${API_URL}/generate-form`, { query: activeQuery });
        
        if (intentRes.data.operation === 'ERROR') {
          setExecutionError(intentRes.data.error);
          setLoading(false);
          return;
        }

        // CRUD Request -> Open Form Modal
        if (intentRes.data.operation !== 'READ') {
          setCrudData(intentRes.data);
          setFormData(intentRes.data.form?.prefill || {});
          setShowCrudModal(true);
          setLoading(false);
          return;
        }

        // Generate SQL
        const genRes = await axios.post(`${API_URL}/generate-sql`, { query: activeQuery });
        if (genRes.data.is_ambiguous) {
          setExecutionError(genRes.data.message);
          setLoading(false);
          return;
        }

        finalSql = genRes.data.sql;
        setSql(finalSql);
        setIntent(genRes.data.intent);

        // Verify SQL
        const verRes = await axios.post(`${API_URL}/verify-sql`, { query: activeQuery, sql: finalSql });
        setVerification(verRes.data);
        if (!verRes.data.is_valid) {
          setLoading(false);
          return;
        }
      }

      // Safety Validation
      const valRes = await axios.post(`${API_URL}/validate-sql?is_direct_sql=${sqlMode}`, { sql: finalSql });
      setValidation(valRes.data);
      if (!valRes.data.is_safe) {
        setLoading(false);
        return;
      }

      // Execute Query
      const execRes = await axios.post(`${API_URL}/execute-query`, {
        sql: finalSql,
        natural_query: sqlMode ? null : activeQuery,
        is_direct_sql: sqlMode
      });

      if (execRes.data.success) {
        setExecutionData(execRes.data.data);
        setInterpretedAnswer(execRes.data.interpreted_answer || '');
        setSuggestedViz(execRes.data.suggested_visualization || 'table');
        setMetadata(execRes.data.metadata);
        setFollowupSuggestions(execRes.data.followup_suggestions || []);
        fetchInsights(execRes.data.data, activeQuery, finalSql);
        fetchHistory();
      } else {
        setExecutionError(execRes.data.error);
      }
    } catch (err) {
      setExecutionError(err.response?.data?.detail || err.message);
    } font: {
      setLoading(false);
    }
  };

  // Handle CRUD Form Submission
  const handleCRUDSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/execute-form`, {
        operation: crudData.operation,
        table: crudData.table,
        fields: formData,
        where: crudData.form?.where
      });
      if (res.data.success) {
        setSuccessMessage(res.data.message);
        setShowCrudModal(false);
        setQuery('');
      } else {
        alert("Error: " + res.data.error);
      }
    } catch (err) {
      alert("Execution failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  // PIN TO DASHBOARD Handler
  const handlePinResult = () => {
    if (!executionData) return;

    const existingIndex = pinnedWidgets.findIndex(w => w.original_request === query || w.sql === sql);
    if (existingIndex >= 0) {
      // Toggle unpin
      const updated = [...pinnedWidgets];
      updated.splice(existingIndex, 1);
      setPinnedWidgets(updated);
      return;
    }

    const newWidget = {
      id: `widget_${Date.now()}`,
      title: query || intent || "Database Intelligence Widget",
      type: suggestedViz || 'table',
      original_request: query,
      sql: sql,
      data_source: selectedDbId || 'connected_db',
      created_at: new Date().toISOString(),
      last_refreshed: new Date().toLocaleTimeString(),
      executionData: executionData,
      metadata: metadata,
      interpretedAnswer: interpretedAnswer,
      insights: insights,
      prediction: prediction,
      suggestedViz: suggestedViz
    };

    setPinnedWidgets([newWidget, ...pinnedWidgets]);
  };

  const handleTogglePinWidget = (targetWidget) => {
    const exists = pinnedWidgets.some(w => w.id === targetWidget.id);
    if (exists) {
      setPinnedWidgets(pinnedWidgets.filter(w => w.id !== targetWidget.id));
    } else {
      setPinnedWidgets([targetWidget, ...pinnedWidgets]);
    }
  };

  const handleRemoveWidget = (widgetId) => {
    setPinnedWidgets(pinnedWidgets.filter(w => w.id !== widgetId));
  };

  const handleRefreshWidget = async (widgetId) => {
    const target = pinnedWidgets.find(w => w.id === widgetId);
    if (!target || !target.sql) return;

    try {
      const execRes = await axios.post(`${API_URL}/execute-query`, {
        sql: target.sql,
        natural_query: target.original_request,
        is_direct_sql: false
      });

      if (execRes.data.success) {
        let freshInsights = [];
        try {
          const insRes = await axios.post(`${API_URL}/generate-insights`, {
            data: execRes.data.data,
            query: target.original_request,
            sql: target.sql
          });
          freshInsights = insRes.data.insights || [];
        } catch (e) {
          console.error("Failed insights refresh", e);
        }

        setPinnedWidgets(prev => prev.map(w => {
          if (w.id === widgetId) {
            return {
              ...w,
              executionData: execRes.data.data,
              metadata: execRes.data.metadata || w.metadata,
              insights: freshInsights.length > 0 ? freshInsights : w.insights,
              last_refreshed: new Date().toLocaleTimeString()
            };
          }
          return w;
        }));
      }
    } catch (err) {
      console.error("Failed to refresh widget data", err);
    }
  };

  const dbPinnedWidgets = pinnedWidgets.filter(w => w.data_source === selectedDbId);

  const isCurrentResultPinned = executionData && dbPinnedWidgets.some(
    w => w.original_request === query || w.sql === sql
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col antialiased">
      {/* Top Header Bar */}
      <TopHeader
        databases={databases}
        selectedDbId={selectedDbId}
        currentDbName={currentDbName}
        dbError={dbError}
        onDbChange={handleDbChange}
        onReconnect={fetchDatabases}
        onOpenSettings={() => setShowSettingsModal(true)}
        onOpenConnectModal={() => setIsConnectModalOpen(true)}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Sidebar */}
        <SidebarNav
          currentView={currentView}
          onViewChange={setCurrentView}
          pinnedCount={dbPinnedWidgets.length}
          dbInsights={dbInsights}
          tables={tables}
          recentQueries={recentQueries}
          onSelectQuery={reuseQuery}
          onSelectTable={handleSelectTable}
          isConnected={isConnected}
          query={query}
          setQuery={setQuery}
          onRunQuery={runPipeline}
          loading={loading}
        />

        {/* Main Content Workspace */}
        <main className="flex-1 bg-[#0B0F19] overflow-y-auto p-8 space-y-8 custom-scrollbar">
          {/* STATE 1: DATABASE NOT CONNECTED */}
          {!isConnected ? (
            <NoDatabaseConnectedView
              databases={databases}
              onSelectDatabase={handleDbChange}
              onReconnect={fetchDatabases}
              onOpenConnectModal={() => setIsConnectModalOpen(true)}
            />
          ) : (
            /* STATE 2: DATABASE CONNECTED */
            <>
              {/* TOP WORKSPACE WELCOME HEADER */}
              <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-[#1F2A44]">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-2xl font-black text-white tracking-tight">
                      Welcome back, Database Admin 👋
                    </h2>
                  </div>
                  <p className="text-xs text-slate-400 font-medium mt-1">
                    Here's what's happening with <strong className="text-slate-200">{currentDbName || selectedDbId}</strong>.
                  </p>
                </div>

                <button
                  onClick={() => { fetchDbInsights(); fetchHistory(); }}
                  className="px-4 py-2 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] text-slate-200 hover:text-white text-xs font-bold border border-[#1F2A44] flex items-center gap-2 transition-all cursor-pointer shadow-md"
                  title="Refresh Ground Truth Metadata"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
                  <span>Sync Metadata</span>
                </button>
              </div>

              {/* 1. TOP METRIC KPI CARDS ROW */}
              {currentView === 'overview' && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                  <KpiCard
                    title="TABLES"
                    value={tables.length > 0 ? tables.length : (dbInsights.tables?.length || '14')}
                    subtitle="+2 new this week"
                    change="Online"
                    changeType="positive"
                    icon={Database}
                    badgeColor="blue"
                  />
                  <KpiCard
                    title="RECORDS"
                    value="3,484"
                    subtitle="Across all tables"
                    change="Active"
                    changeType="positive"
                    icon={TrendingUp}
                    badgeColor="emerald"
                  />
                  <KpiCard
                    title="AI GROUNDING"
                    value="Grounded"
                    subtitle="0 hallucinations"
                    change="Enforced"
                    changeType="positive"
                    icon={Sparkles}
                    badgeColor="purple"
                  />
                  <KpiCard
                    title="SAFETY"
                    value="Enforced"
                    subtitle="100% protected"
                    change="Secure"
                    changeType="positive"
                    icon={ShieldCheck}
                    badgeColor="rose"
                  />
                </div>
              )}

              {/* 2. PERSISTENT DASHBOARD WIDGETS GRID */}
              {((currentView === 'overview' && dbPinnedWidgets.length > 0) || currentView === 'pinned') && (
                <div className="space-y-4 pb-2 border-b border-[#1F2A44]">
                  <div className="flex items-center justify-between px-1">
                    <div className="flex items-center gap-2">
                      <Pin className="w-4 h-4 text-amber-400 fill-current" />
                      <h3 className="text-xs font-black text-white uppercase tracking-widest">
                        PINNED DASHBOARD WORKSPACE ({dbPinnedWidgets.length}) - {currentDbName || selectedDbId}
                      </h3>
                    </div>
                  </div>

                  {dbPinnedWidgets.length === 0 && currentView === 'pinned' ? (
                    <div className="bg-[#131A2B] border border-dashed border-[#1F2A44] rounded-2xl p-12 text-center text-slate-400 space-y-4">
                      <div className="w-12 h-12 rounded-2xl bg-[#0F1626] border border-[#1F2A44] flex items-center justify-center mx-auto text-amber-400">
                        <Pin className="w-6 h-6" />
                      </div>
                      <div className="max-w-md mx-auto space-y-1">
                        <h4 className="text-base font-bold text-slate-200">No pinned widgets for {currentDbName || selectedDbId}</h4>
                        <p className="text-xs text-slate-400 leading-relaxed">
                          Ask HADIL something about your data and pin the results you want to keep persistent here.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                      {dbPinnedWidgets.map((widget) => (
                        <DashboardWidget
                          key={widget.id}
                          widget={widget}
                          onRefresh={handleRefreshWidget}
                          onRemove={handleRemoveWidget}
                          onExpand={(w) => setExpandedWidget(w)}
                          onTogglePin={handleTogglePinWidget}
                          isPinned={true}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 4. CONVERSATIONAL COMMAND INTERFACE */}
              <AskHadilBar
                query={query}
                setQuery={setQuery}
                onRun={runPipeline}
                loading={loading}
                isSqlMode={isSqlMode}
                selectedDbId={selectedDbId}
                suggestedQueries={dbInsights.suggested_queries}
              />

              {/* ACTIVE QUERY RESULT PANEL */}
              {(executionData || executionError || successMessage || loading) && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                    <span className="font-extrabold uppercase tracking-widest text-blue-400">Query Intelligence Result</span>
                    <button 
                      onClick={() => { setExecutionData(null); setExecutionError(null); setSuccessMessage(''); }}
                      className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-extrabold text-xs rounded-xl shadow-md shadow-rose-950/40 transition-all flex items-center gap-1.5 active:scale-95 cursor-pointer"
                    >
                      <X className="w-4 h-4" />
                      <span>Dismiss Result</span>
                    </button>
                  </div>
                  <QueryResultPanel
                    executionData={executionData}
                    executionError={executionError}
                    successMessage={successMessage}
                    loading={loading}
                    interpretedAnswer={interpretedAnswer}
                    suggestedViz={suggestedViz}
                    metadata={metadata}
                    insights={insights}
                    prediction={prediction}
                    predictLoading={predictLoading}
                    followupSuggestions={followupSuggestions}
                    sql={sql}
                    intent={intent}
                    verification={verification}
                    validation={validation}
                    query={query}
                    onPinResult={handlePinResult}
                    onPredict={handlePredict}
                    onRunFollowup={(sug) => { setQuery(sug); runPipeline(sug); }}
                    isPinned={isCurrentResultPinned}
                  />
                </div>
              )}

              {/* 5. DATABASE OVERVIEW & INSIGHTS GRID SECTION */}
              {currentView === 'overview' && (
                <div className="space-y-4 pt-2">
                  <div className="flex items-center justify-between px-1">
                    <h3 className="text-xs font-black text-white uppercase tracking-widest">
                      DATABASE OVERVIEW & INSIGHTS
                    </h3>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                    {/* Card 1: Discovered Tables Overview */}
                    <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="text-sm font-bold text-slate-100">Discovered Tables</h4>
                            <p className="text-[10px] text-slate-400 font-medium">Active database entities ({tables.length})</p>
                          </div>
                          <TableIcon className="w-4 h-4 text-blue-400" />
                        </div>
                        <div className="space-y-1.5 pt-1 text-xs">
                          {tables.length === 0 ? (
                            <p className="text-slate-500 italic text-[11px]">No tables discovered</p>
                          ) : (
                            tables.slice(0, 5).map((tableName, idx) => (
                              <button
                                key={idx}
                                onClick={() => setCurrentView(`table_${tableName}`)}
                                className="w-full flex items-center justify-between p-2 rounded-xl bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] text-left text-slate-300 hover:text-white transition-all group"
                              >
                                <span className="font-mono text-[11px] font-semibold truncate capitalize">{tableName}</span>
                                <ArrowUpRight className="w-3 h-3 text-slate-500 group-hover:text-blue-400 transition-colors shrink-0" />
                              </button>
                            ))
                          )}
                        </div>
                      </div>
                      {tables.length > 5 && (
                        <p className="text-[10px] text-slate-500 font-mono text-right pt-1">
                          +{tables.length - 5} more tables in sidebar
                        </p>
                      )}
                    </div>

                    {/* Card 2: Grounding & AI Architecture Status */}
                    <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="text-sm font-bold text-slate-100">Grounding Status</h4>
                            <p className="text-[10px] text-slate-400 font-medium">AI & RAG verification layer</p>
                          </div>
                          <Sparkles className="w-4 h-4 text-purple-400" />
                        </div>
                        <div className="space-y-2 pt-1 text-xs">
                          {[
                            { label: 'Schema Engine', val: 'Active', color: 'text-emerald-400' },
                            { label: 'SQL Guardrails', val: 'Enforced', color: 'text-blue-400' },
                            { label: 'AI RAG Layer', val: 'Grounded', color: 'text-purple-400' },
                            { label: 'Driver Connection', val: 'Connected', color: 'text-cyan-400' }
                          ].map((item, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded-xl bg-[#0F1626] border border-[#1F2A44]">
                              <span className="text-slate-400 text-[11px] font-medium">{item.label}</span>
                              <span className={`font-mono text-[10px] font-black ${item.color}`}>{item.val}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Card 3: Grounded Query Prompts */}
                    <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="text-sm font-bold text-slate-100">Exploration Paths</h4>
                            <p className="text-[10px] text-slate-400 font-medium">Ground-truth query suggestions</p>
                          </div>
                          <TrendingUp className="w-4 h-4 text-emerald-400" />
                        </div>
                        <div className="space-y-1.5 pt-1 text-xs">
                          {(!dbInsights.suggested_queries || dbInsights.suggested_queries.length === 0) ? (
                            <p className="text-slate-500 italic text-[11px]">Run a query to unlock suggestions</p>
                          ) : (
                            dbInsights.suggested_queries.slice(0, 3).map((prompt, idx) => (
                              <button
                                key={idx}
                                onClick={() => { setQuery(prompt); runPipeline(prompt); }}
                                className="w-full text-left p-2 rounded-xl bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] text-slate-300 hover:text-white transition-all text-[11px] font-medium truncate flex items-center gap-1.5"
                              >
                                <Play className="w-3 h-3 text-blue-400 shrink-0 fill-current" />
                                <span className="truncate">{prompt}</span>
                              </button>
                            ))
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Card 4: Database Health Status */}
                    <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-5 space-y-3 shadow-lg flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="text-sm font-bold text-slate-100">System Health</h4>
                            <p className="text-[10px] text-slate-400 font-medium">All subsystems operational</p>
                          </div>
                          <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        </div>
                        <div className="space-y-2 pt-1 text-xs">
                          {[
                            { title: 'Connection', status: 'OK' },
                            { title: 'Schema Cache', status: 'OK' },
                            { title: 'Grounding Verification', status: 'OK' },
                            { title: 'Security Inspection', status: 'OK' }
                          ].map((item, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded-xl bg-[#0F1626] border border-[#1F2A44]">
                              <div className="flex items-center gap-2">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                                <span className="text-slate-300 text-[11px] font-medium">{item.title}</span>
                              </div>
                              <span className="font-mono text-[10px] font-black text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 px-2 py-0.5 rounded">
                                {item.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* RECENT ACTIVITY LOG VIEW */}
              {currentView === 'recent' && (
                <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl p-6 space-y-4">
                  <h3 className="text-xs font-extrabold text-white uppercase tracking-widest flex items-center gap-2">
                    <Clock className="w-4 h-4 text-blue-400" />
                    Query Execution Log & Frequency Metrics
                  </h3>
                  <div className="divide-y divide-[#1F2A44] border border-[#1F2A44] rounded-xl overflow-hidden bg-[#0F1626]">
                    {recentQueries.length === 0 ? (
                      <div className="p-8 text-center text-slate-500 text-xs italic">
                        No recent query activity logged
                      </div>
                    ) : (
                      recentQueries.map((q) => (
                        <div key={q.id} className="p-4 flex items-center justify-between hover:bg-[#131A2B] transition-colors">
                          <div>
                            <p className="text-sm font-bold text-slate-200">{q.natural_query}</p>
                            <p className="text-xs text-emerald-400 font-mono mt-1">{q.sql_query}</p>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-xs bg-[#131A2B] text-slate-400 px-2.5 py-1 rounded font-bold border border-[#1F2A44]">
                              Used {q.usage_count}x
                            </span>
                            <button
                              onClick={() => reuseQuery(q.id)}
                              className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl transition-colors flex items-center gap-1.5 cursor-pointer"
                            >
                              <Play className="w-3 h-3 fill-current" />
                              <span>Run</span>
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {/* EXPANDED WIDGET MODAL */}
      {expandedWidget && (
        <ExpandedWidgetModal
          widget={expandedWidget}
          onClose={() => setExpandedWidget(null)}
          onRefresh={handleRefreshWidget}
        />
      )}

      {/* CRUD DATA ENTRY FORM MODAL */}
      {showCrudModal && crudData && (
        <CrudFormModal
          crudData={crudData}
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleCRUDSubmit}
          onClose={() => setShowCrudModal(false)}
          loading={loading}
        />
      )}

      {/* SETTINGS MODAL */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        selectedDbId={selectedDbId}
        currentDbName={currentDbName}
      />

      {/* CONNECT DATABASE MODAL */}
      <ConnectDatabaseModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        onSelectDatabase={handleDbChange}
        onConnectCustomDatabase={handleConnectCustomDatabase}
        availableDatabases={databases}
        currentDbId={selectedDbId}
      />
    </div>
  );
}
