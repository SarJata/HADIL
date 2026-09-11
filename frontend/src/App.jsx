import React, { useState, useEffect, useRef } from 'react';
import api, { setAuthCallbacks, fetchDeploymentCapabilities, DEFAULT_DESKTOP_CAPABILITIES } from './api';
import {
  Database, Table as TableIcon, TrendingUp, Sparkles, Pin, Clock, Play,
  RefreshCw, LayoutDashboard, ShieldCheck, CheckCircle2, Search, Filter,
  Layers, AlertCircle, X, ArrowUpRight, Lock, Loader2
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
import LoginScreen from './components/LoginScreen';
import UserManagementView from './components/UserManagementView';
import SetupScreen from './components/SetupScreen';
import PolicyManagementView from './components/PolicyManagementView';
import CreateTableModal from './components/CreateTableModal';
import SuAdminView from './components/SuAdminView';



export default function App() {
  // Authentication & Session State
  const [setupRequired, setSetupRequired] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState(null);
  const [forbiddenToast, setForbiddenToast] = useState(null);

  // View Mode: 'overview' | 'pinned' | 'recent' | 'analytics-charts' | 'analytics-anomalies' | 'user-management' | 'table_<tablename>'
  const [currentView, setCurrentView] = useState('overview');

  // Pipeline Execution State
  const [query, setQuery] = useState('');
  const [executedQuery, setExecutedQuery] = useState('');
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

  // Active Database ID Ref for Race Condition Protection
  const activeDbIdRef = useRef(selectedDbId);
  useEffect(() => {
    activeDbIdRef.current = selectedDbId;
  }, [selectedDbId]);

  // History & Exploration State
  const [recentQueries, setRecentQueries] = useState([]);

  // CRUD Form State
  const [crudData, setCrudData] = useState(null);
  const [showCrudModal, setShowCrudModal] = useState(false);
  const [formData, setFormData] = useState({});

  // Connect Database Modal State
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  // Create Table Modal State
  const [isCreateTableModalOpen, setIsCreateTableModalOpen] = useState(false);
  const [initialCreateTableTableName, setInitialCreateTableTableName] = useState('');

  // Settings Modal State
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [capabilities, setCapabilities] = useState(DEFAULT_DESKTOP_CAPABILITIES);


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

  // Server Shutdown Dialog & State
  const [showShutdownConfirm, setShowShutdownConfirm] = useState(false);
  const [isShuttingDownServer, setIsShuttingDownServer] = useState(false);
  const [serverShutDownComplete, setServerShutDownComplete] = useState(false);

  const isConnected = Boolean(selectedDbId && !dbError);


  // Configure centralized API callbacks & check setup status on startup
  useEffect(() => {
    setAuthCallbacks({
      onUnauthorized: (msg) => {
        setIsAuthenticated(false);
        setUser(null);
        setRole(null);
        setPermissions([]);
        setAuthError(msg || 'Session expired. Please sign in again.');
      },
      onForbidden: (msg) => {
        setForbiddenToast(msg || 'Access Denied: You do not have permission to perform this action.');
      }
    });

    checkSetupStatus();
    fetchDeploymentCapabilities()
      .then((caps) => setCapabilities(caps))
      .catch(() => setCapabilities(DEFAULT_DESKTOP_CAPABILITIES));
  }, []);

  // Check whether first-time administrator setup is required
  const checkSetupStatus = async () => {
    try {
      setAuthLoading(true);
      const res = await api.get('/setup/status');
      if (res.data && res.data.setup_required) {
        setSetupRequired(true);
        setAuthLoading(false);
      } else {
        setSetupRequired(false);
        await validateSession();
      }
    } catch (err) {
      console.error("Setup status check failed:", err);
      setSetupRequired(false);
      await validateSession();
    }
  };

  const handleSetupComplete = (newAdminUsername) => {
    setSetupRequired(false);
    setAuthError(`Admin account '${newAdminUsername}' created successfully! Please sign in.`);
  };

  // Reset view if view is user-management but user is not authorized
  useEffect(() => {
    const canManage = permissions.includes('MANAGE_USERS') || role === 'ADMIN' || role === 'MASTER_ADMIN';
    if (currentView === 'user-management' && !canManage) {
      setCurrentView('overview');
    }
  }, [role, permissions, currentView]);

  // Save pinned widgets to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem('hadil_pinned_widgets', JSON.stringify(pinnedWidgets));
    } catch (e) {
      console.error("Failed to save pinned widgets to localStorage", e);
    }
  }, [pinnedWidgets]);

  useEffect(() => {
    if (isAuthenticated && selectedDbId) {
      fetchDbInsights();
      fetchTables();
    }
  }, [selectedDbId, isAuthenticated]);

  // Validate session against backend /auth/me
  const validateSession = async () => {
    const token = localStorage.getItem('hadil_jwt_token');
    if (!token) {
      setIsAuthenticated(false);
      setAuthLoading(false);
      return;
    }

    try {
      setAuthLoading(true);
      const meRes = await api.get('/auth/me');
      setIsAuthenticated(true);
      setUser({ id: meRes.data.user_id, username: meRes.data.username });
      setRole(meRes.data.role);
      setPermissions(meRes.data.permissions || []);
      setAuthError(null);
      await fetchDatabases();
      await fetchHistory();
    } catch (err) {
      console.error("Session validation failed:", err);
      localStorage.removeItem('hadil_jwt_token');
      setIsAuthenticated(false);
      setUser(null);
      setRole(null);
      setPermissions([]);
    } finally {
      setAuthLoading(false);
    }
  };

  // Login handler
  const handleLogin = async (username, password) => {
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await api.post('/auth/login', { username, password });
      const newToken = res.data.access_token;
      localStorage.setItem('hadil_jwt_token', newToken);

      // Fetch user profile and active database role
      const meRes = await api.get('/auth/me');
      setIsAuthenticated(true);
      setUser({ id: meRes.data.user_id, username: meRes.data.username });
      setRole(meRes.data.role);
      setPermissions(meRes.data.permissions || []);

      await fetchDatabases();
      await fetchHistory();
    } catch (err) {
      if (err.response) {
        const status = err.response.status;
        if (status === 401) {
          setAuthError('Invalid username or password.');
        } else if (status >= 500) {
          setAuthError('Could not verify credentials. Please try again.');
        } else {
          const msg = err.response.data?.detail || 'Authentication failed. Please check your credentials.';
          setAuthError(msg);
        }
      } else {
        // Network error / connection refused / backend unreachable
        setAuthError('Could not verify credentials. Couldn\'t connect to HADIL.');
      }
    } finally {
      setAuthLoading(false);
    }
  };

  // Logout handler
  const handleLogout = () => {
    localStorage.removeItem('hadil_jwt_token');
    setIsAuthenticated(false);
    setUser(null);
    setRole(null);
    setPermissions([]);
    setDatabases([]);
    setSelectedDbId('');
  };

  // SuAdmin Graceful Server Shutdown Handler
  const handleInitiateServerShutdown = async () => {
    try {
      setIsShuttingDownServer(true);
      await api.post('/admin/server/shutdown');
    } catch (err) {
      console.log("Shutdown request sent:", err.message);
    } finally {
      setIsShuttingDownServer(false);
      setShowShutdownConfirm(false);
      setServerShutDownComplete(true);
    }
  };


  // API Call Handlers
  const fetchDatabases = async () => {
    try {
      const [listRes, currentRes] = await Promise.all([
        api.get('/databases'),
        api.get('/current-database')
      ]);
      setDatabases(listRes.data || []);
      setSelectedDbId(currentRes.data?.id || '');
      setCurrentDbName(currentRes.data?.name || '');
      setDbError(null);
    } catch (err) {
      console.error("Failed to fetch databases", err);
      setDatabases([]);
      setSelectedDbId('');
      setDbError("Unable to connect to server. Please check backend.");
    }
  };

  // Active Database ID Ref for Race Condition Protection
  // Database Loading & Invalidation State
  const [isDbLoading, setIsDbLoading] = useState(false);

  const handleDbChange = async (dbId) => {
    try {
      setLoading(true);
      setIsDbLoading(true);
      // 1. Immediately invalidate old database-specific state
      setRole(null);
      setPermissions([]);
      setDbInsights({ summary: 'Loading database metadata...', suggested_queries: [], tables: [], stats: { table_count: 0, record_count: 0, relation_count: 0 } });
      setTables([]);
      setExecutionData(null);
      setSql('');
      setValidation(null);
      setVerification(null);
      setExecutionError(null);

      const res = await api.post('/select-database', { db_id: dbId });
      if (res.data.success) {
        setSelectedDbId(dbId);
        activeDbIdRef.current = dbId;
        const currentRes = await api.get('/current-database');
        setCurrentDbName(currentRes.data?.name || dbId);

        // Retrieve effective role for newly selected database
        const meRes = await api.get('/auth/me');
        setRole(meRes.data.role);
        setPermissions(meRes.data.permissions || []);

        await Promise.all([
          fetchDatabases(),
          fetchHistory(),
          fetchDbInsights(dbId),
          fetchTables(dbId)
        ]);
      }

    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || "Failed to switch database";
      alert("Failed to switch database: " + errMsg);
    } finally {
      setLoading(false);
      setIsDbLoading(false);
    }
  };

  const handleConnectCustomDatabase = async (connectionUri, name) => {
    try {
      setLoading(true);
      setIsDbLoading(true);
      // 1. Immediately invalidate old database-specific state
      setRole(null);
      setPermissions([]);
      setDbInsights({ summary: 'Loading database metadata...', suggested_queries: [], tables: [], stats: { table_count: 0, record_count: 0, relation_count: 0 } });
      setTables([]);
      setExecutionData(null);
      setSql('');
      setValidation(null);
      setVerification(null);
      setExecutionError(null);

      const res = await api.post('/connect-custom-db', {
        connection_uri: connectionUri,
        name: name
      });
      if (res.data.success) {
        const targetDbId = res.data.db_id;
        setSelectedDbId(targetDbId);
        activeDbIdRef.current = targetDbId;
        setCurrentDbName(name || targetDbId);
        setDbError(null);

        // Retrieve effective role for new custom database
        const meRes = await api.get('/auth/me');
        setRole(meRes.data.role);
        setPermissions(meRes.data.permissions || []);

        await Promise.all([
          fetchDatabases(),
          fetchHistory(),
          fetchDbInsights(targetDbId),
          fetchTables(targetDbId)
        ]);
      }
    } catch (err) {
      throw new Error(err.response?.data?.detail || err.message || "Failed to connect to custom database.");
    } finally {
      setLoading(false);
      setIsDbLoading(false);
    }
  };

  const handleCreateTable = async (tablePayload) => {
    try {
      const res = await api.post('/create-table', tablePayload);
      if (res.data?.success) {
        setSuccessMessage(res.data.message);
        await Promise.all([
          fetchDbInsights(selectedDbId),
          fetchTables(selectedDbId)
        ]);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || "Failed to create table.";
      throw new Error(msg);
    }
  };

  const fetchHistory = async () => {
    try {
      const recent = await api.get('/queries/recent');
      setRecentQueries(recent.data || []);
    } catch (err) {
      console.error("Failed to fetch query history", err);
    }
  };

  const fetchDbInsights = async (targetDbId = selectedDbId) => {
    try {
      const res = await api.get('/database-insights');
      // Guard against race conditions: Ignore response if user switched database during fetch
      if (targetDbId && activeDbIdRef.current && targetDbId !== activeDbIdRef.current) {
        return;
      }
      setDbInsights(res.data || { summary: '', suggested_queries: [], tables: [], stats: { table_count: 0, record_count: 0, relation_count: 0 } });
      if (res.data?.tables) {
        setTables(res.data.tables);
      }
    } catch (err) {
      console.error("Failed to fetch database insights", err);
      if (!targetDbId || targetDbId === activeDbIdRef.current) {
        setDbInsights({ summary: 'No database analysis available', suggested_queries: [], tables: [], stats: { table_count: 0, record_count: 0, relation_count: 0 } });
      }
    }
  };

  const fetchTables = async (targetDbId = selectedDbId) => {
    try {
      const res = await api.get('/schema/tables');
      // Guard against race conditions
      if (targetDbId && activeDbIdRef.current && targetDbId !== activeDbIdRef.current) {
        return;
      }
      if (res.data?.tables) {
        setTables(res.data.tables);
      }
    } catch (err) {
      console.error("Failed to fetch tables", err);
      if (!targetDbId || targetDbId === activeDbIdRef.current) {
        setTables([]);
      }
    }
  };

  const fetchInsights = async (dataPayload, queryStr, sqlStr) => {
    try {
      const res = await api.post('/generate-insights', {
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
      const res = await api.post('/predict-trend', {
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
      const res = await api.post('/queries/reuse', { query_id: queryId });
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
      if (err.response?.status === 403) {
        setExecutionError("Access Denied: You do not have permission to execute this operation on this database.");
      } else {
        setExecutionError(err.response?.data?.detail || err.message);
      }
    } finally {
      setLoading(false);
      fetchHistory();
    }
  };

  const handleSelectTable = (tableName) => {
    setCurrentView(`table_${tableName}`);
    const tableQuery = `SELECT * FROM ${tableName} LIMIT 50`;
    setQuery(`Show data from ${tableName}`);
    runPipeline(tableQuery);
  };

  // Conversational Execution Pipeline
  const runPipeline = async (overrideQuery = null) => {
    const activeQuery = (typeof overrideQuery === 'string' && overrideQuery.trim())
      ? overrideQuery.trim()
      : (typeof query === 'string' ? query.trim() : '');

    if (!activeQuery || !selectedDbId) return;

    setExecutedQuery(activeQuery);
    // Clear input box after processing begins (success or failure)
    setQuery('');

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
      const modeRes = await api.post('/detect-mode', { query: activeQuery });
      const sqlMode = modeRes.data.mode === 'SQL';
      setIsSqlMode(sqlMode);

      let finalSql = '';

      if (sqlMode) {
        finalSql = activeQuery;
        setSql(finalSql);
        setIntent('Direct SQL Execution');

        // AI Verification for Raw SQL
        const verRes = await api.post('/verify-sql', { query: activeQuery, sql: finalSql });
        setVerification(verRes.data);
        if (!verRes.data.is_valid) {
          setLoading(false);
          return;
        }
      } else {
        // Natural Language Pipeline -> Detect Intent
        const intentRes = await api.post('/generate-form', { query: activeQuery });

        if (intentRes.data.operation === 'ERROR') {
          setExecutionError(intentRes.data.error);
          setLoading(false);
          return;
        }

        if (intentRes.data.operation === 'CREATE_TABLE') {
          setInitialCreateTableTableName(intentRes.data.target_table_name || '');
          setIsCreateTableModalOpen(true);
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
        const genRes = await api.post('/generate-sql', { query: activeQuery });
        if (genRes.data.is_ambiguous) {
          setExecutionError(genRes.data.message);
          setLoading(false);
          return;
        }

        finalSql = genRes.data.sql;
        setSql(finalSql);
        setIntent(genRes.data.intent);

        // Verify SQL
        const verRes = await api.post('/verify-sql', { query: activeQuery, sql: finalSql });
        setVerification(verRes.data);
        if (!verRes.data.is_valid) {
          setLoading(false);
          return;
        }
      }

      // Safety Validation
      const valRes = await api.post(`/validate-sql?is_direct_sql=${sqlMode}`, { sql: finalSql });
      setValidation(valRes.data);
      if (!valRes.data.is_safe) {
        setLoading(false);
        return;
      }

      // Execute Query
      const execRes = await api.post('/execute-query', {
        sql: finalSql,
        natural_query: sqlMode ? null : activeQuery,
        is_direct_sql: sqlMode,
        is_verified: true
      });

      if (execRes.data.success) {
        setExecutionData(execRes.data.data);
        setInterpretedAnswer(execRes.data.interpreted_answer || '');
        setSuggestedViz(execRes.data.suggested_visualization || 'table');
        setMetadata({
          ...(execRes.data.metadata || {}),
          columns: execRes.data.columns || []
        });
        setFollowupSuggestions(execRes.data.followup_suggestions || []);
        fetchInsights(execRes.data.data, activeQuery, finalSql);
        fetchHistory();
      } else {
        setExecutionError(execRes.data.error);
      }
    } catch (err) {
      if (err.response?.status === 403) {
        setExecutionError("Access Denied: You do not have permission to execute this query on this database.");
      } else {
        setExecutionError(err.response?.data?.detail || err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  // Handle CRUD Form Submission
  const handleCRUDSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post('/execute-form', {
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
        setExecutionError("Error: " + res.data.error);
      }
    } catch (err) {
      if (err.response?.status === 403) {
        alert("Access Denied: You do not have permission to modify records in this database.");
      } else {
        alert("Execution failed: " + (err.response?.data?.detail || err.message));
      }
    } finally {
      setLoading(false);
    }
  };

  // PIN TO DASHBOARD Handler
  const handlePinResult = () => {
    if (!executionData) return;

    const queryText = executedQuery || query;
    const existingIndex = pinnedWidgets.findIndex(w => w.original_request === queryText || w.sql === sql);
    if (existingIndex >= 0) {
      const updated = [...pinnedWidgets];
      updated.splice(existingIndex, 1);
      setPinnedWidgets(updated);
      return;
    }

    const newWidget = {
      id: `widget_${Date.now()}`,
      title: queryText || intent || "Database Intelligence Widget",
      type: suggestedViz || 'table',
      original_request: queryText,
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
      const execRes = await api.post('/execute-query', {
        sql: target.sql,
        natural_query: target.original_request,
        is_direct_sql: false
      });

      if (execRes.data.success) {
        let freshInsights = [];
        try {
          const insRes = await api.post('/generate-insights', {
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
    w => w.original_request === (executedQuery || query) || w.sql === sql
  );

  // If First-Run Setup is Required -> Render Setup Screen
  if (setupRequired === true && !isAuthenticated) {
    return <SetupScreen onSetupComplete={handleSetupComplete} />;
  }

  // If Auth initial validation loading
  if (authLoading && !isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white font-sans">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Validating HADIL Workspace Security Session...
          </p>
        </div>
      </div>
    );
  }

  // If NOT Authenticated -> Render HADIL Login Screen
  if (!isAuthenticated) {
    return <LoginScreen onLogin={handleLogin} loading={authLoading} authError={authError} />;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col antialiased">
      {/* Top Header Bar */}
      <TopHeader
        databases={databases}
        selectedDbId={selectedDbId}
        currentDbName={currentDbName}
        dbError={dbError}
        user={user}
        role={role}
        onDbChange={handleDbChange}
        onReconnect={fetchDatabases}
        onOpenSettings={() => setShowSettingsModal(true)}
        onOpenConnectModal={() => setIsConnectModalOpen(true)}
        onLogout={handleLogout}
        onNavigateOverview={() => setCurrentView('overview')}
        onCloseServer={capabilities.server_shutdown ? () => setShowShutdownConfirm(true) : null}
      />


      {/* Global 403 Forbidden Toast Notification */}
      {forbiddenToast && (
        <div className="bg-rose-950/90 border-b border-rose-800 text-rose-200 px-6 py-3 text-xs font-bold flex items-center justify-between shadow-lg animate-in slide-in-from-top-2 duration-200 z-50">
          <div className="flex items-center gap-3">
            <Lock className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{forbiddenToast}</span>
          </div>
          <button
            onClick={() => setForbiddenToast(null)}
            className="p-1 hover:bg-rose-900 rounded text-rose-300 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Sidebar */}
        <SidebarNav
          currentView={currentView}
          onViewChange={setCurrentView}
          onOpenSettings={() => setShowSettingsModal(true)}
          pinnedCount={dbPinnedWidgets.length}
          dbInsights={dbInsights}
          tables={tables}
          recentQueries={recentQueries}
          onSelectQuery={reuseQuery}
          onSelectTable={handleSelectTable}
          isConnected={isConnected}
          role={role}
          permissions={permissions}
        />

        {/* Main Content Workspace */}
        <main className="flex-1 bg-[#0B0F19] overflow-y-auto p-8 space-y-8 custom-scrollbar">

          {/* VIEW MODE 1: USER MANAGEMENT & SUADMIN */}
          {currentView === 'user-management' && (permissions.includes('MANAGE_USERS') || role === 'ADMIN' || role === 'MASTER_ADMIN') ? (
            <UserManagementView databases={databases} activeDbId={selectedDbId} currentUser={user} currentRole={role} />
          ) : currentView === 'suadmin' && (permissions.includes('MANAGE_USERS') || role === 'ADMIN' || role === 'MASTER_ADMIN') ? (
            <SuAdminView databases={databases} activeDbId={selectedDbId} capabilities={capabilities} />
          ) : currentView === 'policy-documents' ? (
            <PolicyManagementView activeDatabase={databases.find(d => d.id === selectedDbId)} userRole={role} />
          ) : !isConnected ? (

            /* STATE 2: DATABASE NOT CONNECTED */
            <NoDatabaseConnectedView
              databases={databases}
              onSelectDatabase={handleDbChange}
              onReconnect={fetchDatabases}
              onOpenConnectModal={() => setIsConnectModalOpen(true)}
            />
          ) : (
            /* STATE 3: DATABASE CONNECTED WORKSPACE */
            <>
              {/* TOP WORKSPACE WELCOME HEADER */}
              <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-[#1F2A44]">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-2xl font-serif-brand text-white tracking-wide">
                      Welcome back, {user?.username || 'User'} 👋
                    </h2>
                    {role && (
                      <span className={`text-[10px] font-mono font-extrabold px-2 py-0.5 rounded border uppercase ${role === 'ADMIN' ? 'bg-purple-950 text-purple-300 border-purple-800' :
                          role === 'EDITOR' ? 'bg-emerald-950 text-emerald-300 border-emerald-800' :
                            'bg-slate-900 text-slate-300 border-slate-700'
                        }`}>
                        {role} Role
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-slate-400 font-medium mt-1">
                    Here's what's happening with <strong className="text-slate-200">{currentDbName || selectedDbId}</strong>.
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  {(role === 'ADMIN' || role === 'EDITOR') && (
                    <button
                      onClick={() => setIsCreateTableModalOpen(true)}
                      className="px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold border border-emerald-600 flex items-center gap-2 transition-all cursor-pointer shadow-md"
                      title="Create New Database Table"
                    >
                      <TableIcon className="w-3.5 h-3.5" />
                      <span>+ Create Table</span>
                    </button>
                  )}

                  <button
                    onClick={() => { fetchDbInsights(); fetchHistory(); }}
                    className="px-4 py-2 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] text-slate-200 hover:text-white text-xs font-bold border border-[#1F2A44] flex items-center gap-2 transition-all cursor-pointer shadow-md"
                    title="Sync Ground Truth Metadata"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Sync Metadata</span>
                  </button>
                </div>
              </div>


              {/* 1. TOP METRIC KPI CARDS ROW */}
              {currentView === 'overview' && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                  <KpiCard
                    title="TABLES"
                    value={isDbLoading ? 'Loading...' : (dbInsights.stats?.table_count !== undefined ? dbInsights.stats.table_count : tables.length)}
                    subtitle={isDbLoading ? 'Inspecting schema...' : `${tables.length} discovered entities`}
                    change={isDbLoading ? 'Syncing' : 'Online'}
                    changeType={isDbLoading ? 'neutral' : 'positive'}
                    icon={Database}
                    badgeColor="blue"
                  />
                  <KpiCard
                    title="RECORDS"
                    value={isDbLoading ? 'Loading...' : (dbInsights.stats?.record_count !== undefined ? (dbInsights.stats.record_count >= 1000 ? `${(dbInsights.stats.record_count / 1000).toFixed(1)}K` : dbInsights.stats.record_count.toLocaleString()) : '0')}
                    subtitle="Across all tables"
                    change={isDbLoading ? 'Syncing' : 'Active'}
                    changeType={isDbLoading ? 'neutral' : 'positive'}
                    icon={TrendingUp}
                    badgeColor="emerald"
                  />
                  <KpiCard
                    title="ROLE SCOPE"
                    value={role || 'VIEWER'}
                    subtitle={`Scoped to ${selectedDbId}`}
                    change="Enforced"
                    changeType="positive"
                    icon={ShieldCheck}
                    badgeColor={role === 'ADMIN' ? 'purple' : role === 'EDITOR' ? 'blue' : 'rose'}
                  />
                  <KpiCard
                    title="SAFETY"
                    value="Enforced"
                    subtitle="Server-side protected"
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
                      onClick={() => {
                        setExecutionData(null);
                        setExecutionError(null);
                        setSuccessMessage('');
                        if (currentView.startsWith('table_')) {
                          setCurrentView('overview');
                        }
                      }}
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
                    query={executedQuery || query}
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
                                className="w-full flex items-center justify-between p-2 rounded-xl bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] text-left text-slate-300 hover:text-white transition-all group cursor-pointer"
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
                            <h4 className="text-sm font-bold text-slate-100">RBAC Security Status</h4>
                            <p className="text-[10px] text-slate-400 font-medium">Active Database Role & Controls</p>
                          </div>
                          <ShieldCheck className="w-4 h-4 text-purple-400" />
                        </div>
                        <div className="space-y-2 pt-1 text-xs">
                          {[
                            { label: 'Active User', val: user?.username || 'Guest', color: 'text-blue-400' },
                            { label: 'Database Scope', val: selectedDbId || 'None', color: 'text-indigo-400' },
                            { label: 'Effective Role', val: role || 'VIEWER', color: role === 'ADMIN' ? 'text-purple-400' : role === 'EDITOR' ? 'text-blue-400' : 'text-slate-300' },
                            { label: 'Server Boundary', val: 'Protected (401/403)', color: 'text-emerald-400' }
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
                                className="w-full text-left p-2 rounded-xl bg-[#0F1626] hover:bg-[#1A2340] border border-[#1F2A44] text-slate-300 hover:text-white transition-all text-[11px] font-medium truncate flex items-center gap-1.5 cursor-pointer"
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
                            { title: 'JWT Authentication', status: 'OK' },
                            { title: 'RBAC Security Boundary', status: 'ACTIVE' }
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
                              className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl transition-colors flex items-center gap-1.5 cursor-pointer"
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
        userRole={role}
      />

      {/* CONNECT DATABASE MODAL */}
      <ConnectDatabaseModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        onSelectDatabase={handleDbChange}
        onConnectCustomDatabase={handleConnectCustomDatabase}
        availableDatabases={databases}
        currentDbId={selectedDbId}
        userRole={role}
        capabilities={capabilities}
      />


      {/* CREATE TABLE MODAL */}
      <CreateTableModal
        isOpen={isCreateTableModalOpen}
        onClose={() => setIsCreateTableModalOpen(false)}
        onCreateTable={handleCreateTable}
        currentDbName={currentDbName}
        initialTableName={initialCreateTableTableName}
        activeDbId={selectedDbId}
      />
      {/* SERVER SHUTDOWN CONFIRMATION DIALOG */}
      {showShutdownConfirm && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="bg-[#131A2B] border border-rose-800/80 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 border-b border-[#1F2A44] pb-4">
              <div className="w-10 h-10 rounded-xl bg-rose-950/90 border border-rose-700 flex items-center justify-center shrink-0">
                <Power className="w-5 h-5 text-rose-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100">Close HADIL Application?</h3>
                <p className="text-xs text-rose-300 font-medium">Master Administrator Action</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              This will gracefully close the HADIL application and disconnect active sessions.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                disabled={isShuttingDownServer}
                onClick={() => setShowShutdownConfirm(false)}
                className="px-4 py-2 bg-[#1A2340] hover:bg-[#232F52] text-slate-300 text-xs font-semibold rounded-xl border border-[#1F2A44] transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                disabled={isShuttingDownServer}
                onClick={handleInitiateServerShutdown}
                className="px-4 py-2 bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold rounded-xl border border-rose-600 flex items-center gap-2 transition-all shadow-lg cursor-pointer disabled:opacity-50"
              >
                {isShuttingDownServer ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Closing...</span>
                  </>
                ) : (
                  <>
                    <Power className="w-3.5 h-3.5" />
                    <span>Close HADIL</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SHUTTING DOWN / SERVER CLOSED OVERLAY */}
      {serverShutDownComplete && (
        <div className="fixed inset-0 bg-slate-950 flex items-center justify-center z-50 p-6">
          <div className="bg-[#131A2B] border border-[#1F2A44] rounded-2xl max-w-lg w-full p-8 text-center space-y-6 shadow-2xl">
            <div className="w-16 h-16 rounded-2xl bg-emerald-950/80 border border-emerald-700/80 flex items-center justify-center mx-auto">
              <Power className="w-8 h-8 text-emerald-400" />
            </div>

            <div className="space-y-2">
              <h2 className="text-xl font-bold text-slate-100">HADIL Has Been Closed</h2>
              <p className="text-xs text-slate-400 leading-relaxed">
                The application was gracefully closed by a Master Administrator. All active database sessions and service workers have been safely terminated.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#0B0F19] border border-[#1F2A44] text-xs font-mono text-slate-400">
              You may now safely close this browser window or tab.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


