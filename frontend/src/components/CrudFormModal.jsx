import React from 'react';
import { ShieldCheck, X, Check, Loader2, Clock } from 'lucide-react';

const getInputType = (fieldType) => {
  const t = (fieldType || '').toUpperCase();
  if (t.includes('DATETIME') || t.includes('TIMESTAMP')) {
    return 'datetime-local';
  }
  if (t.includes('DATE')) {
    return 'date';
  }
  if (t.includes('TIME')) {
    return 'time';
  }
  return 'text';
};

const formatValueForInput = (inputType, rawValue) => {
  if (rawValue === null || rawValue === undefined || rawValue === '') {
    return '';
  }
  const str = String(rawValue).trim();
  if (inputType === 'datetime-local') {
    return str.replace(' ', 'T');
  }
  if (inputType === 'date') {
    return str.split('T')[0].split(' ')[0];
  }
  if (inputType === 'time') {
    const parts = str.split(' ');
    if (parts.length > 1) return parts[1];
    if (str.includes('T')) return str.split('T')[1];
    return str;
  }
  return str;
};

const formatValueForState = (inputType, inputVal) => {
  if (inputVal === null || inputVal === undefined || inputVal === '') {
    return '';
  }
  if (inputType === 'datetime-local') {
    return inputVal.replace('T', ' ');
  }
  return inputVal;
};

const getCurrentValueForType = (inputType) => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');

  if (inputType === 'date') {
    return `${year}-${month}-${day}`;
  }
  if (inputType === 'time') {
    return `${hours}:${minutes}:${seconds}`;
  }
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
};

export default function CrudFormModal({
  crudData,
  formData,
  setFormData,
  onSubmit,
  onClose,
  loading
}) {
  if (!crudData || !crudData.form) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-200 text-slate-900">
        {/* Header */}
        <div className="px-6 py-5 bg-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-extrabold capitalize">
                Secure {crudData.operation?.toLowerCase()} Operation
              </h3>
              <p className="text-xs text-slate-400 font-medium">
                Target Table: <span className="font-mono text-emerald-400 font-bold">{crudData.table}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={onSubmit} className="p-6 space-y-5">
          <div className="space-y-4 max-h-[55vh] overflow-y-auto pr-2 custom-scrollbar">
            {crudData.form.fields?.map((field) => {
              const inputType = getInputType(field.type);
              const isDateOrTime = inputType !== 'text';
              const displayVal = formatValueForInput(inputType, formData[field.name]);

              return (
                <div key={field.name} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                      {field.name} {field.type && <span className="text-[10px] text-slate-400 font-normal">({field.type})</span>}
                    </label>
                    {isDateOrTime && (
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, [field.name]: getCurrentValueForType(inputType) })}
                        className="text-[11px] font-bold text-emerald-600 hover:text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-2 py-0.5 rounded-md flex items-center gap-1 transition-colors"
                      >
                        <Clock className="w-3 h-3 text-emerald-600" />
                        <span>Set Current</span>
                      </button>
                    )}
                  </div>
                  <div className="relative">
                    <input
                      type={inputType}
                      value={displayVal}
                      onChange={(e) => {
                        const val = formatValueForState(inputType, e.target.value);
                        setFormData({ ...formData, [field.name]: val });
                      }}
                      placeholder={`Enter ${field.name}`}
                      className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm text-slate-900 font-medium outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Authorization Notice */}
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 font-medium flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Final Authorization Required for Database Write Transaction</span>
          </div>

          {/* Action Buttons */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 border border-slate-300 text-slate-700 font-bold text-xs rounded-xl hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl transition-all flex items-center gap-2 shadow-md shadow-emerald-900/20 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Executing...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Execute Transaction</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
