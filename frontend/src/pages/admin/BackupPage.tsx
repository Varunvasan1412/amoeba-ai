import { useState, useEffect } from 'react';
import { 
  Archive, Database, Download, History, Clock, 
  RefreshCw, Trash2, ShieldAlert, 
  Save, Wrench, ArrowLeft, CheckCircle2,
  ShieldCheck, ShieldX, Info
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'react-toastify';
import { apiFetch } from '../../utils/api';

interface BackupFile {
  file_name: string;
  created_at: string;
  file_size: number;
  status: string;
  is_validated?: boolean;
  last_tested_at?: string;
  validation_status?: string;
  validation_error?: string;
}

interface BackupSchedule {
  schedule_hour: number;
  schedule_minute: number;
  enabled: boolean;
  last_restore_at?: string;
  last_restore_file?: string;
}

export default function BackupPage() {
  const [backups, setBackups] = useState<BackupFile[]>([]);
  const [schedule, setSchedule] = useState<BackupSchedule>({ schedule_hour: 2, schedule_minute: 0, enabled: true });
  const [isBackingUp, setIsBackingUp] = useState(false);
  const [isValidating, setIsValidating] = useState<string | null>(null);
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);
  const [restoreConfirm, setRestoreConfirm] = useState<string | null>(null);
  const [inspecting, setInspecting] = useState<string | null>(null);
  const [inspectionData, setInspectionData] = useState<any>(null);

  const API_BASE = "/api/system";

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [backupsRes, scheduleRes] = await Promise.all([
        apiFetch(`${API_BASE}/backups`),
        apiFetch(`${API_BASE}/backup/schedule`)
      ]);
      
      if (backupsRes.ok) setBackups(await backupsRes.json());
      if (scheduleRes.ok) setSchedule(await scheduleRes.json());
    } catch (err) {
      toast.error("Failed to fetch backup data");
    } finally {
      // Data loaded
    }
  };

  const handleInspect = async (filename: string) => {
    setInspecting(filename);
    setInspectionData(null);
    try {
      const res = await apiFetch(`${API_BASE}/backup/${filename}/inspect`);
      if (res.ok) {
        setInspectionData(await res.json());
      } else {
        toast.error("Inspection failed");
      }
    } catch (err) {
      toast.error("Network error during inspection");
    }
  };

  const handleBackupNow = async () => {
    setIsBackingUp(true);
    try {
      const res = await apiFetch(`${API_BASE}/backup`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        toast.success("Backup created successfully!");
        fetchData();
      } else {
        toast.error(data.detail || "Backup failed");
      }
    } catch (err) {
      toast.error("Network error during backup");
    } finally {
      setIsBackingUp(false);
    }
  };

  const handleValidate = async (filename: string) => {
    setIsValidating(filename);
    try {
      const res = await apiFetch(`${API_BASE}/backup/${filename}/validate`, { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.success) {
        toast.success("Validation PASSED! Structure is intact.");
        fetchData();
      } else {
        toast.error(`Validation FAILED: ${data.error || "Integrity check failed"}`);
        fetchData();
      }
    } catch (err) {
      toast.error("Network error during validation");
    } finally {
      setIsValidating(null);
    }
  };

  const handleSaveSchedule = async () => {
    setIsSavingSchedule(true);
    try {
      const res = await apiFetch(`${API_BASE}/backup/schedule`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hour: schedule.schedule_hour, minute: schedule.schedule_minute })
      });
      if (res.ok) {
        toast.success("Backup schedule updated!");
      } else {
        const data = await res.json();
        toast.error(data.detail || "Update failed");
      }
    } catch (err) {
      toast.error("Network error during update");
    } finally {
      setIsSavingSchedule(false);
    }
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Delete backup ${filename}?`)) return;
    try {
      const res = await apiFetch(`${API_BASE}/backup/${filename}`, { method: 'DELETE' });
      if (res.ok) {
        toast.success("Backup deleted");
        fetchData();
      }
    } catch (err) {
      toast.error("Deletion failed");
    }
  };

  const handleRestore = async (filename: string) => {
    setRestoreConfirm(null);
    const toastId = toast.loading("Restoring database... system may be briefly unresponsive");
    try {
      const res = await apiFetch(`${API_BASE}/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backup_file_name: filename, confirm: true })
      });
      const data = await res.json();
      if (res.ok) {
        toast.update(toastId, { render: "Restore successful!", type: "success", isLoading: false, autoClose: 3000 });
      } else {
        toast.update(toastId, { render: data.detail || "Restore failed", type: "error", isLoading: false, autoClose: 3000 });
      }
    } catch (err) {
      toast.update(toastId, { render: "Network error during restore", type: "error", isLoading: false, autoClose: 3000 });
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex justify-between items-end mb-4">
        <div>
          <Link to="/admin" className="flex items-center gap-1 text-blue-600 font-bold text-sm mb-2 hover:gap-2 transition-all">
            <ArrowLeft className="w-4 h-4" /> Back to Dashboard
          </Link>
          <div className="flex items-center gap-3">
             <div className="p-2 bg-teal-500/10 rounded-lg">
                <Archive className="w-6 h-6 text-teal-500" />
             </div>
             <div>
                <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 text-left">
                  System Backup & Recovery
                </h1>
                <p className="text-sm text-gray-500">Automated SQL dumps and safety-validated point-in-time recovery</p>
             </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {schedule.last_restore_at && (
             <div className="text-right mr-4 hidden md:block">
               <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">System State</div>
               <div className="text-xs font-bold text-teal-600 flex items-center justify-end gap-1">
                 <CheckCircle2 size={12} /> Restored from {schedule.last_restore_file?.replace('backup_', '').replace('.sql', '')}
               </div>
               <div className="text-[10px] text-gray-400 italic">
                 Last update: {new Date(schedule.last_restore_at).toLocaleString()}
               </div>
             </div>
          )}
          <button 
            onClick={handleBackupNow}
            disabled={isBackingUp}
            className="flex items-center gap-2 px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl transition-all shadow-lg active:scale-95 disabled:opacity-50"
          >
            {isBackingUp ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Download className="w-5 h-5" />}
            {isBackingUp ? 'Creating Backup...' : 'Generate Manual Backup'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Schedule & Info */}
        <div className="space-y-6 lg:col-span-1">
          <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm relative overflow-hidden group">
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-4">
                <Clock className="w-5 h-5 text-indigo-500" />
                <h3 className="font-bold text-gray-800">Automated Schedule</h3>
              </div>
              <p className="text-sm text-gray-500 mb-6 leading-relaxed">
                Configure when the daily database snapshot occurs. 
                System maintenance will keep the <span className="font-bold text-teal-600">last 7 backups</span> automatically.
              </p>

                  <div className="space-y-4">
                    <div className="flex items-center gap-4">
                       <div className="flex-[2]">
                          <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">Hour (12h)</label>
                          <input 
                            type="number" 
                            min="1" max="12"
                            value={schedule.schedule_hour % 12 || 12}
                            onChange={(e) => {
                               const val = parseInt(e.target.value);
                               if (val >= 1 && val <= 12) {
                                  const isPM = schedule.schedule_hour >= 12;
                                  let newHour = val === 12 ? 0 : val;
                                  if (isPM) newHour += 12;
                                  setSchedule({...schedule, schedule_hour: newHour});
                               }
                            }}
                            className="w-full bg-gray-50 border border-gray-200 p-2.5 rounded-lg font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                          />
                       </div>
                       <div className="flex-[2]">
                          <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">Minute</label>
                          <input 
                            type="number" 
                            min="0" max="59"
                            value={schedule.schedule_minute}
                            onChange={(e) => setSchedule({...schedule, schedule_minute: parseInt(e.target.value)})}
                            className="w-full bg-gray-50 border border-gray-200 p-2.5 rounded-lg font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                          />
                       </div>
                       <div className="flex-[1.5]">
                          <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">Period</label>
                          <select 
                            value={schedule.schedule_hour >= 12 ? 'PM' : 'AM'}
                            onChange={(e) => {
                               const isPM = e.target.value === 'PM';
                               const current12h = schedule.schedule_hour % 12 || 12;
                               let newHour = current12h === 12 ? 0 : current12h;
                               if (isPM) newHour += 12;
                               setSchedule({...schedule, schedule_hour: newHour});
                            }}
                            className="w-full bg-gray-50 border border-gray-200 p-2.5 rounded-lg font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                          >
                            <option value="AM">AM</option>
                            <option value="PM">PM</option>
                          </select>
                       </div>
                    </div>

                <button 
                  onClick={handleSaveSchedule}
                  disabled={isSavingSchedule}
                  className="w-full flex items-center justify-center gap-2 py-3 bg-gray-900 text-white font-bold rounded-xl hover:bg-black transition-all active:scale-95 disabled:opacity-50"
                >
                  {isSavingSchedule ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Update Schedule
                </button>
              </div>
            </div>
            <Clock className="absolute -bottom-4 -right-4 w-24 h-24 text-gray-100 group-hover:text-blue-50/50 transition-colors" />
          </div>

          <div className="bg-gradient-to-br from-indigo-50 to-blue-50 p-6 rounded-2xl border border-indigo-100">
            <div className="flex items-center gap-2 mb-3">
               <ShieldAlert className="w-5 h-5 text-indigo-500" />
               <h3 className="font-bold text-indigo-900">Safety Policy</h3>
            </div>
            <ul className="space-y-3 text-sm text-indigo-800/80">
              <li className="flex gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0" />
                Dumps are stored in isolated persistent volumes.
              </li>
              <li className="flex gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0" />
                Restoring will overwrite current database state.
              </li>
              <li className="flex gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0" />
                Retention is strictly capped at last 7 versions.
              </li>
            </ul>
          </div>
        </div>

        {/* Backup History */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col h-full">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center bg-gray-50/30">
               <div className="flex items-center gap-2">
                 <History className="w-5 h-5 text-teal-600" />
                 <h3 className="font-bold text-gray-800">Backup History</h3>
               </div>
               <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">{backups.length} Versions</span>
            </div>

            <div className="flex-1 overflow-x-auto min-h-[400px]">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50 text-gray-500 text-[10px] font-bold uppercase tracking-wider">
                    <th className="p-4 pl-6">Backup Name</th>
                    <th className="p-4">Created At</th>
                    <th className="p-4">Size</th>
                    <th className="p-4">Integrity</th>
                    <th className="p-4 text-right pr-6">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {backups.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="p-12 text-center text-gray-400">
                        <div className="flex flex-col items-center">
                          <Database className="w-12 h-12 mb-4 opacity-10" />
                          <p className="font-medium">No backups available</p>
                          <p className="text-xs">Daily jobs or manual triggers will appear here.</p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    backups.map((bk) => (
                      <tr key={bk.file_name} className="group hover:bg-gray-50/50 transition-colors">
                        <td className="p-4 pl-6">
                          <div className="flex items-center gap-3">
                             <div className="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center text-teal-600">
                                <Database size={14} />
                             </div>
                             <span className="font-mono text-xs font-bold text-gray-700">{bk.file_name}</span>
                          </div>
                        </td>
                        <td className="p-4 text-sm text-gray-500">
                          {new Date(bk.created_at).toLocaleString()}
                        </td>
                        <td className="p-4 text-sm font-bold text-gray-900">
                          {formatSize(bk.file_size)}
                        </td>
                        <td className="p-4">
                           {isValidating === bk.file_name ? (
                             <div className="flex items-center gap-2 text-blue-500 font-bold text-[10px] animate-pulse">
                               <RefreshCw className="w-3 h-3 animate-spin" /> TESTING...
                             </div>
                           ) : (
                             <div className="flex items-center gap-2">
                               {bk.validation_status === 'PASS' && (
                                 <span className="px-2 py-1 bg-green-50 text-green-600 rounded-md text-[10px] font-bold flex items-center gap-1 border border-green-100">
                                   <ShieldCheck size={10} /> VALIDATED
                                 </span>
                               )}
                               {bk.validation_status === 'FAIL' && (
                                 <span className="px-2 py-1 bg-red-50 text-red-600 rounded-md text-[10px] font-bold flex items-center gap-1 border border-red-100" title={bk.validation_error}>
                                   <ShieldX size={10} /> FAILED
                                 </span>
                               )}
                               {bk.validation_status === 'NOT TESTED' && (
                                 <span className="px-2 py-1 bg-yellow-50 text-yellow-600 rounded-md text-[10px] font-bold flex items-center gap-1 border border-yellow-100">
                                   <Info size={10} /> UNTESTED
                                 </span>
                               )}
                             </div>
                           )}
                        </td>
                        <td className="p-4 text-right pr-6">
                           <div className="flex items-center justify-end gap-2">
                             <button 
                               onClick={() => handleInspect(bk.file_name)}
                               className="p-2 hover:bg-gray-100 text-gray-500 rounded-lg transition-all"
                               title="Inspect Content"
                             >
                               <History size={16} />
                             </button>
                             <button 
                               onClick={() => handleValidate(bk.file_name)}
                               disabled={!!isValidating}
                               className="p-2 hover:bg-teal-50 text-teal-600 rounded-lg transition-all"
                               title="Validate Integrity"
                             >
                               <ShieldCheck size={16} />
                             </button>
                             <button 
                               onClick={() => setRestoreConfirm(bk.file_name)}
                               className="p-2 hover:bg-blue-50 text-blue-600 rounded-lg transition-all"
                               title="Restore"
                             >
                               <Wrench size={16} />
                             </button>
                             <button 
                               onClick={() => handleDelete(bk.file_name)}
                               className="p-2 hover:bg-red-50 text-red-400 rounded-lg transition-all"
                               title="Delete"
                             >
                               <Trash2 size={16} />
                             </button>
                           </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Inspection Modal */}
      {inspecting && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
           <div className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[80vh]">
              <div className="p-8 pb-4 flex items-center justify-between border-b border-gray-100">
                 <div className="flex items-center gap-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                       <History className="w-5 h-5 text-gray-600" />
                    </div>
                    <h2 className="text-xl font-bold text-gray-900">Backup Analysis</h2>
                 </div>
                 <button onClick={() => setInspecting(null)} className="p-2 hover:bg-gray-100 rounded-full">
                    <History className="w-5 h-5 rotate-45" /> 
                 </button>
              </div>
              
              <div className="p-8 flex-1 overflow-y-auto">
                 {!inspectionData ? (
                   <div className="flex flex-col items-center justify-center py-12">
                      <RefreshCw className="w-8 h-8 text-blue-500 animate-spin mb-4" />
                      <p className="text-gray-500 font-medium">Parsing SQL Dump...</p>
                   </div>
                 ) : (
                   <div className="space-y-6">
                      <div className="grid grid-cols-2 gap-4">
                         <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-[10px] font-bold text-gray-400 mb-1 uppercase">Database Name</div>
                            <div className="font-bold text-gray-800">public_schema</div>
                         </div>
                         <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-[10px] font-bold text-gray-400 mb-1 uppercase">Total Tables</div>
                            <div className="font-bold text-teal-600">{inspectionData.table_count} Objects</div>
                         </div>
                      </div>

                      <div>
                         <h4 className="text-xs font-bold text-gray-400 uppercase mb-3 tracking-widest">Included Tables</h4>
                         <div className="flex flex-wrap gap-2">
                            {inspectionData.tables.map((t: string) => (
                               <span key={t} className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-mono font-bold text-gray-700 shadow-sm">
                                  {t}
                               </span>
                            ))}
                         </div>
                      </div>
                   </div>
                 )}
              </div>

              <div className="p-6 border-t border-gray-100 bg-gray-50/50 flex justify-end">
                 <button 
                  onClick={() => setInspecting(null)}
                  className="px-6 py-2 bg-gray-900 text-white font-bold rounded-xl hover:bg-black transition-all"
                 >
                   Close Analysis
                 </button>
              </div>
           </div>
        </div>
      )}

      {/* Restore Confirmation Modal */}
      {restoreConfirm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
           <div className="bg-white rounded-3xl shadow-2xl max-w-lg w-full overflow-hidden animate-in zoom-in-95 duration-200">
              <div className="p-8 pb-4 flex flex-col items-center text-center">
                 <div className="w-16 h-16 bg-red-100/50 text-red-600 rounded-2xl flex items-center justify-center mb-6">
                    <ShieldAlert size={32} />
                 </div>
                 <h2 className="text-2xl font-bold text-gray-900 mb-2">Critical Action: Recovery</h2>
                 <p className="text-gray-500 leading-relaxed px-4">
                   You are about to restore the database to version <span className="font-mono font-bold text-red-500">{restoreConfirm}</span>. 
                   All current data will be <span className="font-bold">permanently overwritten</span>.
                 </p>
              </div>
              <div className="p-8 border-t border-gray-100 bg-gray-50/50 flex gap-4">
                 <button 
                  onClick={() => setRestoreConfirm(null)}
                  className="flex-1 py-3 bg-white border border-gray-200 text-gray-700 font-bold rounded-xl hover:bg-white active:scale-95 transition-all"
                 >
                   Cancel
                 </button>
                 <button 
                  onClick={() => handleRestore(restoreConfirm)}
                  className="flex-1 py-3 bg-red-600 text-white font-bold rounded-xl hover:bg-red-700 active:scale-95 transition-all shadow-lg"
                 >
                   Restore Now
                 </button>
              </div>
           </div>
        </div>
      )}
    </div>
  );
}
