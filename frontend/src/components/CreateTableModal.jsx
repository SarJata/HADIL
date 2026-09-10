import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, Table as TableIcon, AlertCircle, Loader2, Link2 } from 'lucide-react';
import api from '../api';

const SUPPORTED_DATA_TYPES = [
  'INTEGER',
  'BIGINT',
  'FLOAT',
  'DOUBLE',
  'DECIMAL',
  'BOOLEAN',
  'VARCHAR',
  'TEXT',
  'DATE',
  'DATETIME'
];

export default function CreateTableModal({ isOpen, onClose, onCreateTable, currentDbName, initialTableName = '', activeDbId = '' }) {
  const [tableName, setTableName] = useState(initialTableName);
  const [columns, setColumns] = useState([
    { id: 1, name: 'id', type: 'INTEGER', length: '', primaryKey: true },
    { id: 2, name: 'name', type: 'VARCHAR', length: '255', primaryKey: false }
  ]);
  const [foreignKeys, setForeignKeys] = useState([]);
  const [dbTables, setDbTables] = useState({}); // { tableName: [col1, col2] }
  const [loading, setLoading] = useState(false);
  const [fetchingSchema, setFetchingSchema] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setTableName(initialTableName || '');
      fetchDatabaseSchemaDetails();
    }
  }, [isOpen, initialTableName, activeDbId]);

  const fetchDatabaseSchemaDetails = async () => {
    try {
      setFetchingSchema(true);
      const res = await api.get('/schema/table-details');
      if (res.data && res.data.tables) {
        setDbTables(res.data.tables);
      }
    } catch (err) {
      console.error("Failed to fetch active database table details:", err);
    } finally {
      setFetchingSchema(false);
    }
  };

  if (!isOpen) return null;

  const handleAddColumn = () => {
    setColumns(prev => [
      ...prev,
      { id: Date.now(), name: '', type: 'VARCHAR', length: '255', primaryKey: false }
    ]);
  };

  const handleRemoveColumn = (id) => {
    if (columns.length <= 1) {
      setError("Table must have at least one column.");
      return;
    }
    const targetCol = columns.find(c => c.id === id);
    if (targetCol && targetCol.name) {
      // Remove any FK associated with this local column name
      setForeignKeys(prev => prev.filter(fk => fk.column !== targetCol.name));
    }
    setColumns(prev => prev.filter(c => c.id !== id));
  };

  const handleColumnChange = (id, field, value) => {
    setColumns(prev => prev.map(col => {
      if (col.id !== id) {
        if (field === 'primaryKey' && value === true) {
          return { ...col, primaryKey: false };
        }
        return col;
      }
      if (field === 'primaryKey' && value === true) {
        return { ...col, primaryKey: true };
      }
      return { ...col, [field]: value };
    }));
  };

  const handleAddForeignKey = () => {
    const defaultLocalCol = columns[0]?.name || '';
    const availableTables = Object.keys(dbTables);
    const defaultRefTable = availableTables[0] || '';
    const defaultRefCol = dbTables[defaultRefTable]?.[0] || '';

    setForeignKeys(prev => [
      ...prev,
      {
        id: Date.now(),
        column: defaultLocalCol,
        refTable: defaultRefTable,
        refColumn: defaultRefCol,
        onDelete: 'NO ACTION',
        onUpdate: 'NO ACTION'
      }
    ]);
  };

  const handleRemoveForeignKey = (id) => {
    setForeignKeys(prev => prev.filter(fk => fk.id !== id));
  };

  const handleFKChange = (id, field, value) => {
    setForeignKeys(prev => prev.map(fk => {
      if (fk.id !== id) return fk;
      const updated = { ...fk, [field]: value };
      if (field === 'refTable') {
        // Automatically select the first column of the newly selected ref table
        const colsForTable = dbTables[value] || [];
        updated.refColumn = colsForTable[0] || '';
      }
      return updated;
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const cleanTableName = tableName.trim();
    if (!cleanTableName) {
      setError("Table name is required.");
      return;
    }

    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(cleanTableName)) {
      setError("Invalid table name. Use alphanumeric characters and underscores only.");
      return;
    }

    if (columns.length === 0) {
      setError("At least one column is required.");
      return;
    }

    const seenNames = new Set();
    const formattedColumns = [];

    for (let i = 0; i < columns.length; i++) {
      const c = columns[i];
      const colName = c.name.trim();
      if (!colName) {
        setError(`Column #${i + 1} name cannot be empty.`);
        return;
      }

      if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(colName)) {
        setError(`Invalid column name '${colName}'. Use alphanumeric characters and underscores only.`);
        return;
      }

      if (seenNames.has(colName.toLowerCase())) {
        setError(`Duplicate column name '${colName}' detected.`);
        return;
      }
      seenNames.add(colName.toLowerCase());

      const payloadCol = {
        name: colName,
        type: c.type,
        primary_key: Boolean(c.primaryKey)
      };

      if (c.type === 'VARCHAR') {
        const lenVal = parseInt(c.length, 10);
        if (isNaN(lenVal) || lenVal <= 0) {
          setError(`VARCHAR column '${colName}' requires a valid positive length.`);
          return;
        }
        payloadCol.length = lenVal;
      }

      formattedColumns.push(payloadCol);
    }

    // Format & Validate Foreign Keys
    const formattedFKs = [];
    const seenFKPairs = new Set();

    for (let i = 0; i < foreignKeys.length; i++) {
      const fk = foreignKeys[i];
      if (!fk.column) {
        setError(`Foreign key #${i + 1} must select a local column.`);
        return;
      }
      if (!fk.refTable) {
        setError(`Foreign key #${i + 1} must select a referenced table.`);
        return;
      }
      if (!fk.refColumn) {
        setError(`Foreign key #${i + 1} must select a referenced column.`);
        return;
      }

      const pairKey = `${fk.column.toLowerCase()}->${fk.refTable.toLowerCase()}.${fk.refColumn.toLowerCase()}`;
      if (seenFKPairs.has(pairKey)) {
        setError(`Duplicate foreign key constraint: '${fk.column}' -> '${fk.refTable}.${fk.refColumn}'.`);
        return;
      }
      seenFKPairs.add(pairKey);

      formattedFKs.push({
        column: fk.column,
        ref_table: fk.refTable,
        ref_column: fk.refColumn,
        on_delete: fk.onDelete || 'NO ACTION',
        on_update: fk.onUpdate || 'NO ACTION'
      });
    }

    try {
      setLoading(true);
      await onCreateTable({
        table_name: cleanTableName,
        columns: formattedColumns,
        foreign_keys: formattedFKs
      });
      // Reset form on success
      setTableName('');
      setColumns([
        { id: 1, name: 'id', type: 'INTEGER', length: '', primaryKey: true },
        { id: 2, name: 'name', type: 'VARCHAR', length: '255', primaryKey: false }
      ]);
      setForeignKeys([]);
      onClose();
    } catch (err) {
      setError(err.message || "Failed to create table.");
    } finally {
      setLoading(false);
    }
  };

  const validLocalColNames = columns.map(c => c.name.trim()).filter(Boolean);
  const cleanTableName = tableName.trim();

  // Exclude current table from activeDbTableNames if present, as it is rendered as `${cleanTableName} (This Table)`
  const activeDbTableNames = Object.keys(dbTables).filter(
    tn => !cleanTableName || tn.toLowerCase() !== cleanTableName.toLowerCase()
  );

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#0F1626] border border-[#1F2A44] rounded-lg shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1F2A44] bg-[#131A2B]">
          <div className="flex items-center gap-2.5">
            <TableIcon className="w-5 h-5 text-emerald-400" />
            <div>
              <h3 className="text-base font-serif-brand font-bold text-white tracking-wide">Create New Table</h3>
              <p className="text-[11px] text-slate-400">Target Database: <span className="text-slate-200 font-mono">{currentDbName || 'Active DB'}</span></p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-md hover:bg-[#1F2A44] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-5">
          {error && (
            <div className="p-3 bg-rose-950/80 border border-rose-800 text-rose-300 rounded-md text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Table Name Field */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Table Name
            </label>
            <input
              type="text"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              placeholder="e.g. employees"
              className="w-full px-3 py-2 bg-[#131A2B] border border-[#1F2A44] rounded-md text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              required
            />
          </div>

          {/* Columns Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-[#1F2A44]">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Columns Definition
              </label>
              <span className="text-[11px] font-mono text-slate-400">{columns.length} columns</span>
            </div>

            <div className="space-y-2.5">
              {columns.map((col, index) => (
                <div key={col.id} className="flex items-end gap-2 bg-[#131A2B] p-3 rounded-md border border-[#1F2A44]">
                  {/* Column Name */}
                  <div className="flex-1 space-y-1">
                    <label className="text-[10px] font-mono text-slate-400">Column Name</label>
                    <input
                      type="text"
                      value={col.name}
                      onChange={(e) => handleColumnChange(col.id, 'name', e.target.value)}
                      placeholder="e.g. column_name"
                      className="w-full px-2.5 py-1.5 bg-[#0F1626] border border-[#1F2A44] rounded text-xs font-mono text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                      required
                    />
                  </div>

                  {/* Data Type */}
                  <div className="w-32 space-y-1">
                    <label className="text-[10px] font-mono text-slate-400">Data Type</label>
                    <select
                      value={col.type}
                      onChange={(e) => handleColumnChange(col.id, 'type', e.target.value)}
                      className="w-full px-2 py-1.5 bg-[#0F1626] border border-[#1F2A44] rounded text-xs font-mono text-white focus:outline-none focus:border-emerald-500 cursor-pointer"
                    >
                      {SUPPORTED_DATA_TYPES.map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>

                  {/* VARCHAR Length Field */}
                  {col.type === 'VARCHAR' && (
                    <div className="w-20 space-y-1">
                      <label className="text-[10px] font-mono text-slate-400">Length</label>
                      <input
                        type="number"
                        min="1"
                        max="65535"
                        value={col.length}
                        onChange={(e) => handleColumnChange(col.id, 'length', e.target.value)}
                        placeholder="255"
                        className="w-full px-2 py-1.5 bg-[#0F1626] border border-[#1F2A44] rounded text-xs font-mono text-white focus:outline-none focus:border-emerald-500"
                        required
                      />
                    </div>
                  )}

                  {/* Primary Key Checkbox */}
                  <div className="flex flex-col items-center justify-center space-y-1.5 px-2 pb-1">
                    <label className="text-[10px] font-mono text-slate-400">PK</label>
                    <input
                      type="checkbox"
                      checked={col.primaryKey}
                      onChange={(e) => handleColumnChange(col.id, 'primaryKey', e.target.checked)}
                      className="w-4 h-4 rounded border-[#1F2A44] bg-[#0F1626] text-emerald-500 focus:ring-0 cursor-pointer"
                      title="Primary Key"
                    />
                  </div>

                  {/* Remove Column Button */}
                  <button
                    type="button"
                    onClick={() => handleRemoveColumn(col.id)}
                    className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded transition-colors mb-0.5 cursor-pointer"
                    title="Remove column"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={handleAddColumn}
              className="w-full py-2 bg-[#131A2B] hover:bg-[#1A2340] text-emerald-400 hover:text-emerald-300 text-xs font-semibold rounded-md border border-[#1F2A44] border-dashed flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>+ Add Column</span>
            </button>
          </div>

          {/* RELATIONSHIPS (FOREIGN KEYS) SECTION */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between pb-1 border-b border-[#1F2A44]">
              <div className="flex items-center gap-2">
                <Link2 className="w-3.5 h-3.5 text-teal-400" />
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Relationships (Foreign Keys)
                </label>
              </div>
              <span className="text-[11px] font-mono text-teal-400">{foreignKeys.length} constraints</span>
            </div>

            {foreignKeys.length === 0 ? (
              <div className="p-3 bg-[#131A2B]/60 border border-dashed border-[#1F2A44] rounded-md text-center text-xs text-slate-400 font-mono">
                {activeDbTableNames.length === 0 
                  ? "No other existing tables in this database to reference. (Create your first table first or define a self-reference)"
                  : "No foreign keys defined (Optional for standalone tables)"
                }
              </div>
            ) : (
              <div className="space-y-2.5">
                {foreignKeys.map((fk, index) => {
                  let refCols = dbTables[fk.refTable];
                  if (!refCols && fk.refTable) {
                    const matchedKey = Object.keys(dbTables).find(k => k.toLowerCase() === fk.refTable.toLowerCase());
                    if (matchedKey) refCols = dbTables[matchedKey];
                  }
                  refCols = refCols || [];
                  return (
                    <div key={fk.id} className="p-3 bg-[#131A2B] rounded-md border border-[#1F2A44] space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono font-bold text-teal-400 uppercase tracking-wider">
                          Foreign Key #{index + 1}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveForeignKey(fk.id)}
                          className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded transition-colors cursor-pointer"
                          title="Remove Foreign Key"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
                        {/* Local FK Column Select */}
                        <div className="space-y-1">
                          <label className="text-[10px] text-slate-400">Local Column</label>
                          <select
                            value={fk.column}
                            onChange={(e) => handleFKChange(fk.id, 'column', e.target.value)}
                            className="w-full px-2 py-1.5 bg-[#0F1626] border border-[#1F2A44] rounded text-xs text-white focus:outline-none focus:border-teal-500 cursor-pointer"
                          >
                            <option value="" disabled>-- Select Column --</option>
                            {validLocalColNames.map(cn => (
                              <option key={cn} value={cn}>{cn}</option>
                            ))}
                          </select>
                        </div>

                        {/* Referenced Table Dropdown */}
                        <div className="space-y-1">
                          <label className="text-[10px] text-slate-400">References Table</label>
                          <select
                            value={fk.refTable}
                            onChange={(e) => handleFKChange(fk.id, 'refTable', e.target.value)}
                            className="w-full px-2 py-1.5 bg-[#0F1626] border border-[#1F2A44] rounded text-xs text-white focus:outline-none focus:border-teal-500 cursor-pointer"
                          >
                            <option value="" disabled>-- Select Table --</option>
                            {tableName.trim() && (
                              <option value={tableName.trim()}>{tableName.trim()} (This Table)</option>
                            )}
                            {activeDbTableNames.map(tn => (
                              <option key={tn} value={tn}>{tn}</option>
                            ))}
                          </select>
                        </div>

                        {/* Referenced Column Dropdown */}
                        <div className="space-y-1">
                          <label className="text-[10px] text-slate-400">References Column</label>
                          <select
                            value={fk.refColumn}
                            onChange={(e) => handleFKChange(fk.id, 'refColumn', e.target.value)}
                            className="w-full px-2 py-1.5 bg-[#0F1626] border border-[#1F2A44] rounded text-xs text-white focus:outline-none focus:border-teal-500 cursor-pointer"
                          >
                            <option value="" disabled>-- Select Column --</option>
                            {(fk.refTable && fk.refTable.toLowerCase() === tableName.trim().toLowerCase()
                              ? validLocalColNames
                              : refCols
                            ).map(rc => (
                              <option key={rc} value={rc}>{rc}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <button
              type="button"
              onClick={handleAddForeignKey}
              className="w-full py-2 bg-[#131A2B] hover:bg-[#1A2340] text-teal-400 hover:text-teal-300 text-xs font-semibold rounded-md border border-[#1F2A44] border-dashed flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
              title="Add Foreign Key constraint"
            >
              <Plus className="w-4 h-4" />
              <span>+ Add Foreign Key</span>
            </button>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#1F2A44]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-[#131A2B] hover:bg-[#1A2340] text-slate-300 text-xs font-semibold rounded-md border border-[#1F2A44] transition-colors cursor-pointer"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold rounded-md border border-emerald-600 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Creating Table...</span>
                </>
              ) : (
                <span>Create Table</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
