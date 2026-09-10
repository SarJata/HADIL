import React, { useState, useEffect } from 'react';
import { 
  Database, Server, CheckCircle2, XCircle, Loader2, Sparkles, X, 
  HardDrive, Key, Globe, ArrowRight, ShieldCheck, Upload, FolderPlus, FileCode
} from 'lucide-react';
import api, { DEFAULT_DESKTOP_CAPABILITIES } from '../api';

const DB_TEMPLATES = {
  postgresql: {
    label: 'PostgreSQL',
    placeholder: 'postgresql+psycopg2://user:password@localhost:5432/dbname',
    defaultUri: 'postgresql+psycopg2://postgres:postgres@localhost:5432/enterprise_db'
  },
  mysql: {
    label: 'MySQL / MariaDB',
    placeholder: 'mysql+pymysql://user:password@localhost:3306/dbname',
    defaultUri: 'mysql+pymysql://root:password@localhost:3306/sales_db'
  },
  sqlite: {
    label: 'SQLite File URI',
    placeholder: 'sqlite:///C:/path/to/database.db',
    defaultUri: 'sqlite:///./databases/sales.db'
  },
  mssql: {
    label: 'Microsoft SQL Server',
    placeholder: 'mssql+pyodbc://user:password@localhost:1433/dbname?driver=ODBC+Driver+17+for+SQL+Server',
    defaultUri: 'mssql+pyodbc://sa:password@localhost:1433/production_db'
  },
  oracle: {
    label: 'Oracle Database',
    placeholder: 'oracle+cx_oracle://user:password@localhost:1521/xe',
    defaultUri: 'oracle+cx_oracle://system:password@localhost:1521/xe'
  }
};

export default function ConnectDatabaseModal({ 
  isOpen, 
  onClose, 
  onSelectDatabase, 
  onConnectCustomDatabase,
  availableDatabases = [],
  currentDbId = '',
  userRole = '',
  capabilities = DEFAULT_DESKTOP_CAPABILITIES
}) {
  const isSuAdmin = userRole === 'MASTER_ADMIN';
  const allowSqliteImport = Boolean(
    isSuAdmin && (capabilities.sqlite_upload || capabilities.sqlite_file_location)
  );
  const remoteTemplates = Object.fromEntries(
    Object.entries(DB_TEMPLATES).filter(([key]) => key !== 'sqlite' || capabilities.sqlite_local)
  );

  const [activeTab, setActiveTab] = useState(capabilities.sqlite_local ? 'local' : 'remote'); // 'local' | 'import' | 'remote'
  const [selectedLocalDb, setSelectedLocalDb] = useState(currentDbId || '');
  
  // SuAdmin SQLite Import State
  const [importMethod, setImportMethod] = useState('path'); // 'path' | 'upload'
  const [existingFilePath, setExistingFilePath] = useState('');
  const [importDisplayName, setImportDisplayName] = useState('');
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importStatusMsg, setImportStatusMsg] = useState(null);

  // Remote Connection Form State
  const [dbType, setDbType] = useState('postgresql');
  const [connectionUri, setConnectionUri] = useState('');
  const [displayName, setDisplayName] = useState('');
  
  // Status states
  const [testing, setTesting] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (availableDatabases.length > 0 && !selectedLocalDb) {
      setSelectedLocalDb(availableDatabases[0].id);
    }
  }, [availableDatabases, selectedLocalDb]);

  useEffect(() => {
    setConnectionUri(DB_TEMPLATES[dbType]?.defaultUri || '');
    setTestResult(null);
    setErrorMsg(null);
  }, [dbType]);

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    if (!connectionUri.trim()) {
      setErrorMsg('Please enter a valid connection URI.');
      return;
    }
    setTesting(true);
    setTestResult(null);
    setErrorMsg(null);

    try {
      const res = await api.post('/test-connection', { connection_uri: connectionUri.trim() });
      setTestResult(res.data);
    } catch (err) {
      setTestResult({ success: false, message: 'Network error while testing connection.' });
    } finally {
      setTesting(false);
    }
  };

  const handleConnectLocal = async () => {
    if (!selectedLocalDb) return;
    setConnecting(true);
    setErrorMsg(null);
    try {
      await onSelectDatabase(selectedLocalDb);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to connect to selected database.');
    } finally {
      setConnecting(false);
    }
  };

  const handleConnectRemote = async () => {
    if (!connectionUri.trim()) {
      setErrorMsg('Please enter a connection URI.');
      return;
    }
    setConnecting(true);
    setErrorMsg(null);

    try {
      const dbName = displayName.trim() || `${DB_TEMPLATES[dbType]?.label || 'Remote DB'}`;
      await onConnectCustomDatabase(connectionUri.trim(), dbName);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Connection failed.');
    } finally {
      setConnecting(false);
    }
  };

  const handleRegisterExistingPath = async () => {
    if (!existingFilePath.trim()) {
      setImportStatusMsg({ type: 'error', text: 'Please enter a valid SQLite file path.' });
      return;
    }

    setImporting(true);
    setImportStatusMsg(null);

    try {
      const res = await api.post('/admin/databases/register-path', {
        file_path: existingFilePath.trim(),
        display_name: importDisplayName.trim() || undefined
      });

      setImportStatusMsg({ type: 'success', text: res.data.message });
      const regDb = res.data.database;
      if (regDb && regDb.id) {
        await onSelectDatabase(regDb.id);
      }
      setTimeout(() => onClose(), 1200);
    } catch (err) {
      setImportStatusMsg({ 
        type: 'error', 
        text: err.response?.data?.detail || 'Failed to register existing SQLite file path.' 
      });
    } finally {
      setImporting(false);
    }
  };

  const handleUploadDatabaseFile = async () => {
    if (!selectedUploadFile) {
      setImportStatusMsg({ type: 'error', text: 'Please select a SQLite database file (.db, .sqlite, .sqlite3) to upload.' });
      return;
    }

    setImporting(true);
    setImportStatusMsg(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedUploadFile);
      if (importDisplayName.trim()) {
        formData.append('display_name', importDisplayName.trim());
      }

      const res = await api.post('/admin/databases/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setImportStatusMsg({ type: 'success', text: res.data.message });
      const regDb = res.data.database;
      if (regDb && regDb.id) {
        await onSelectDatabase(regDb.id);
      }
      setTimeout(() => onClose(), 1200);
    } catch (err) {
      setImportStatusMsg({ 
        type: 'error', 
        text: err.response?.data?.detail || 'Failed to upload and register SQLite database file.' 
      });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-[#0F1626] border border-[#1F2A44] rounded-3xl w-full max-w-xl shadow-2xl overflow-hidden space-y-0 text-slate-200">
        
        {/* Header */}
        <div className="p-6 bg-[#131A2B] border-b border-[#1F2A44] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Connect Database</h2>
              <p className="text-xs text-slate-400">Choose a database source to explore & analyze</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-[#1F2A44] transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Source Tabs */}
        <div className="flex border-b border-[#1F2A44] bg-[#0B0F19]">
          <button
            onClick={() => { setActiveTab('local'); setErrorMsg(null); setImportStatusMsg(null); }}
            className={`flex-1 py-3 px-3 text-xs font-bold flex items-center justify-center gap-2 border-b-2 transition-all ${
              activeTab === 'local'
                ? 'border-emerald-500 text-emerald-400 bg-[#131A2B]/50'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <HardDrive className="w-4 h-4" />
            <span>Registered Databases</span>
          </button>

          {allowSqliteImport && (
            <button
              onClick={() => { setActiveTab('import'); setErrorMsg(null); setImportStatusMsg(null); }}
              className={`flex-1 py-3 px-3 text-xs font-bold flex items-center justify-center gap-2 border-b-2 transition-all ${
                activeTab === 'import'
                  ? 'border-emerald-500 text-emerald-400 bg-[#131A2B]/50'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <FolderPlus className="w-4 h-4" />
              <span>Import SQLite</span>
            </button>
          )}

          <button
            onClick={() => { setActiveTab('remote'); setErrorMsg(null); setImportStatusMsg(null); }}
            className={`flex-1 py-3 px-3 text-xs font-bold flex items-center justify-center gap-2 border-b-2 transition-all ${
              activeTab === 'remote'
                ? 'border-emerald-500 text-emerald-400 bg-[#131A2B]/50'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe className="w-4 h-4" />
            <span>Remote URI</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5">

          {/* TAB 1: LOCAL SQLITE DATABASES */}
          {activeTab === 'local' && (
            <div className="space-y-4">
              <label className="text-xs font-bold text-slate-300 block uppercase tracking-wider flex items-center justify-between">
                <span>Active Registered Databases</span>
                <span className="text-[10px] text-emerald-400 font-mono font-normal tracking-normal lowercase">hadil runtime storage</span>
              </label>

              {availableDatabases.length === 0 ? (
                <div className="p-4 rounded-xl bg-[#131A2B] border border-[#1F2A44] text-center text-slate-400 text-xs">
                  No registered database entries discovered in HADIL.
                </div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto no-scrollbar">
                  {availableDatabases.map((db) => {
                    const isSelected = selectedLocalDb === db.id;
                    return (
                      <button
                        key={db.id}
                        onClick={() => setSelectedLocalDb(db.id)}
                        className={`w-full flex items-center justify-between p-3.5 rounded-xl border text-xs transition-all text-left ${
                          isSelected
                            ? 'bg-emerald-600/20 border-emerald-500 text-white font-bold'
                            : 'bg-[#131A2B] border-[#1F2A44] text-slate-300 hover:border-slate-600'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <Database className={`w-4 h-4 ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`} />
                          <span className="font-mono">{db.name}</span>
                        </div>
                        {isSelected && (
                          <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
                            Selected
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="pt-3 flex items-center justify-end gap-3 border-t border-[#1F2A44]">
                <button
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-[#131A2B]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConnectLocal}
                  disabled={connecting || !selectedLocalDb}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
                >
                  {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                  <span>Connect Database</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: SUADMIN SQLITE IMPORT */}
          {activeTab === 'import' && allowSqliteImport && (
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-300 block mb-2 uppercase tracking-wider">
                  Add Method
                </label>
                <div className={`grid gap-3 ${capabilities.sqlite_file_location && capabilities.sqlite_upload ? 'grid-cols-2' : 'grid-cols-1'}`}>
                  {capabilities.sqlite_file_location && (
                  <button
                    onClick={() => { setImportMethod('path'); setImportStatusMsg(null); }}
                    className={`p-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                      importMethod === 'path'
                        ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                        : 'bg-[#131A2B] border-[#1F2A44] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <FolderPlus className="w-4 h-4" />
                    <span>Existing File Location</span>
                  </button>
                  )}

                  {capabilities.sqlite_upload && (
                  <button
                    onClick={() => { setImportMethod('upload'); setImportStatusMsg(null); }}
                    className={`p-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                      importMethod === 'upload'
                        ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                        : 'bg-[#131A2B] border-[#1F2A44] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Upload className="w-4 h-4" />
                    <span>Upload Database File</span>
                  </button>
                  )}
                </div>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1 uppercase tracking-wider">
                  Friendly Database Name (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Sales Analytics DB"
                  value={importDisplayName}
                  onChange={(e) => setImportDisplayName(e.target.value)}
                  className="w-full bg-[#131A2B] border border-[#1F2A44] rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                />
              </div>

              {/* Method 1: Existing File Path */}
              {importMethod === 'path' && capabilities.sqlite_file_location && (
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-300 block uppercase tracking-wider">
                    Server File Path
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. C:\data\finance.db or /var/data/sales.sqlite"
                    value={existingFilePath}
                    onChange={(e) => setExistingFilePath(e.target.value)}
                    className="w-full bg-[#131A2B] border border-[#1F2A44] rounded-xl px-3.5 py-2.5 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                  />
                  <p className="text-[10px] text-slate-500">
                    ℹ Path refers to an accessible SQLite file on the filesystem.
                  </p>
                </div>
              )}

              {/* Method 2: File Upload */}
              {importMethod === 'upload' && capabilities.sqlite_upload && (
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-300 block uppercase tracking-wider">
                    Select Local SQLite File (.db, .sqlite, .sqlite3)
                  </label>
                  <div className="p-4 bg-[#131A2B] border border-dashed border-[#1F2A44] rounded-xl text-center space-y-2">
                    <input
                      type="file"
                      id="sqlite-upload-input"
                      accept=".db,.sqlite,.sqlite3"
                      onChange={(e) => setSelectedUploadFile(e.target.files[0] || null)}
                      className="hidden"
                    />
                    <label
                      htmlFor="sqlite-upload-input"
                      className="inline-flex items-center gap-2 px-4 py-2 bg-[#1A2340] border border-[#2A385C] rounded-xl text-xs font-bold text-emerald-400 hover:text-emerald-300 hover:bg-[#222E54] cursor-pointer transition-all"
                    >
                      <Upload className="w-4 h-4" />
                      <span>Choose Database File</span>
                    </label>
                    {selectedUploadFile ? (
                      <p className="text-xs font-mono text-emerald-300">
                        Selected: <span className="font-bold text-white">{selectedUploadFile.name}</span> ({Math.round(selectedUploadFile.size / 1024)} KB)
                      </p>
                    ) : (
                      <p className="text-[11px] text-slate-500">No file selected yet</p>
                    )}
                  </div>
                </div>
              )}

              {/* Status Message */}
              {importStatusMsg && (
                <div className={`p-3 rounded-xl border text-xs flex items-center gap-2.5 ${
                  importStatusMsg.type === 'success'
                    ? 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-800/80 text-rose-300'
                }`}>
                  {importStatusMsg.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  )}
                  <span>{importStatusMsg.text}</span>
                </div>
              )}

              <div className="pt-3 flex items-center justify-end gap-3 border-t border-[#1F2A44]">
                <button
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-[#131A2B]"
                >
                  Cancel
                </button>
                <button
                  onClick={importMethod === 'path' ? handleRegisterExistingPath : handleUploadDatabaseFile}
                  disabled={importing || (importMethod === 'path' ? !existingFilePath.trim() : !selectedUploadFile)}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
                >
                  {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderPlus className="w-4 h-4" />}
                  <span>{importMethod === 'path' ? 'Register File Location' : 'Upload & Register'}</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: REMOTE DATABASE URI */}
          {activeTab === 'remote' && (
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1.5 uppercase tracking-wider">
                  Database Type
                </label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {Object.entries(remoteTemplates).map(([key, item]) => (
                    <button
                      key={key}
                      onClick={() => setDbType(key)}
                      className={`p-2.5 rounded-xl border text-xs font-semibold transition-all text-center ${
                        dbType === key
                          ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                          : 'bg-[#131A2B] border-[#1F2A44] text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1.5 uppercase tracking-wider">
                  Connection Display Name (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Production PostgreSQL DB"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full bg-[#131A2B] border border-[#1F2A44] rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1.5 uppercase tracking-wider">
                  SQLAlchemy Connection URI
                </label>
                <input
                  type="text"
                  placeholder={DB_TEMPLATES[dbType]?.placeholder}
                  value={connectionUri}
                  onChange={(e) => setConnectionUri(e.target.value)}
                  className="w-full bg-[#131A2B] border border-[#1F2A44] rounded-xl px-3.5 py-2.5 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
                />
                <p className="text-[10px] text-slate-500 pt-1">
                  🔒 Passwords are used strictly for session authorization and never logged or exposed.
                </p>
              </div>

              {/* Test Result Message */}
              {testResult && (
                <div className={`p-3 rounded-xl border text-xs flex items-center gap-2.5 ${
                  testResult.success 
                    ? 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-800/80 text-rose-300'
                }`}>
                  {testResult.success ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  )}
                  <span>{testResult.message}</span>
                </div>
              )}

              {/* Error Alert */}
              {errorMsg && (
                <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div className="pt-3 flex items-center justify-between border-t border-[#1F2A44]">
                <button
                  onClick={handleTestConnection}
                  disabled={testing || !connectionUri.trim()}
                  className="px-4 py-2 rounded-xl bg-[#131A2B] hover:bg-[#1A2340] border border-[#1F2A44] text-xs font-semibold text-emerald-400 hover:text-emerald-300 disabled:opacity-50 flex items-center gap-2 transition-all"
                >
                  {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                  <span>Test Connection</span>
                </button>

                <div className="flex items-center gap-3">
                  <button
                    onClick={onClose}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-[#131A2B]"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConnectRemote}
                    disabled={connecting || !connectionUri.trim()}
                    className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
                  >
                    {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                    <span>Connect</span>
                  </button>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

