import { useState, useEffect } from 'react';
import { 
  Activity, Database, FileText, Server, ShieldAlert, Zap, 
  RefreshCw, CheckCircle2, AlertTriangle, XCircle, Wrench,
  ArrowRight
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAdmin } from '../context/AdminContext';
import { apiFetch } from '../utils/api';

interface HealthData {
  database_status: string;
  table_health: Array<{ table: string; status: string; issue: string }>;
  document_health: {
    ready: number;
    processing: number;
    failed: number;
    stuck: number;
    total: number;
  };
  performance_metrics: {
    avg_crud_latency_ms: number;
    avg_retrieval_time_ms: number;
    slow_query_count: number;
  };
  integrity_checks: {
    status: string;
    issues: string[];
  };
  recent_audit: Array<{
    action: string;
    entity: string;
    status: string;
    timestamp: string;
  }>;
  configuration_diagnostics: {
    warnings: Array<{
      id: string;
      type: string;
      severity: string;
      message: string;
      suggested_fix?: {
        action: string;
        description: string;
      };
    }>;
    available_tables: string[];
  };
}

export default function SystemHealthPage() {
  const { clientId } = useAdmin();
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [isFixing, setIsFixing] = useState(false);

  const fetchHealth = async () => {
    try {
      let url = `/api/system/health`;
      if (clientId) url += `?client_id=${clientId}`;
      
      const response = await apiFetch(url);
      if (!response.ok) throw new Error('Failed to fetch system health');
      const data = await response.json();
      setHealth(data);
      setError(null);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 60000); // 60 seconds auto-refresh
    return () => clearInterval(interval);
  }, []);

  const handleFixNow = async () => {
    setIsFixing(true);
    try {
      // Call dummy repair service (ensure backend has this or it'll 404 gracefully in catch)
      await apiFetch(`/api/system/repair`, { method: 'POST' });
      // Wait a sec then refresh
      setTimeout(fetchHealth, 1500);
    } catch (err) {
      console.error("Repair failed:", err);
    } finally {
      setTimeout(() => setIsFixing(false), 1500);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'HEALTHY':
      case 'CONNECTED':
        return 'text-green-500 bg-green-500/10 border-green-500/20';
      case 'WARNING':
        return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
      case 'ERROR':
      case 'DISCONNECTED':
        return 'text-red-500 bg-red-500/10 border-red-500/20';
      default:
        return 'text-gray-500 bg-gray-500/10 border-gray-500/20';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'HEALTHY':
      case 'CONNECTED':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case 'WARNING':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'ERROR':
      case 'DISCONNECTED':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Activity className="w-5 h-5 text-gray-500" />;
    }
  };

  const overallStatus = health?.integrity_checks.status || 'UNKNOWN';
  const issueCount = health?.table_health.length || 0;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center mb-8">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <Activity className="w-6 h-6 text-blue-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600">
              System Health Monitoring
            </h1>
            <p className="text-sm text-gray-500">Real-time infrastructure and pipeline diagnostics</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-sm text-gray-500 bg-white px-4 py-2 rounded-lg border border-gray-200 shadow-sm">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-500' : ''}`} />
          Last updated: {lastRefreshed.toLocaleTimeString()}
        </div>
      </div>

      {loading && !health ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      ) : error ? (
        <div className="bg-red-500/10 border border-red-500/20 text-red-500 p-6 rounded-xl flex items-center gap-4">
          <ShieldAlert className="w-8 h-8" />
          <div>
            <h3 className="font-bold text-lg">Failed to load system health</h3>
            <p>{error}</p>
          </div>
        </div>
      ) : health ? (
        <>
          {/* Summary Banner */}
          <div className={`p-6 rounded-xl border flex items-center justify-between shadow-lg ${getStatusColor(overallStatus)}`}>
            <div className="flex items-center gap-4">
              {getStatusIcon(overallStatus)}
              <div>
                <h2 className="text-xl font-bold">
                  System Status: {overallStatus.charAt(0) + overallStatus.slice(1).toLowerCase()}
                </h2>
                {overallStatus !== 'HEALTHY' && (
                  <p className="opacity-80">
                    Warning — {issueCount + (health?.configuration_diagnostics?.warnings?.length || 0)} issue(s) detected.
                  </p>
                )}
              </div>
            </div>
            {overallStatus !== 'HEALTHY' && (
              <button 
                onClick={handleFixNow}
                disabled={isFixing}
                className="flex items-center gap-2 px-6 py-2.5 bg-white border border-gray-200 hover:bg-gray-50 text-gray-800 font-medium rounded-lg transition-all shadow-sm"
              >
                {isFixing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Wrench className="w-4 h-4" />}
                {isFixing ? 'Repairing...' : 'Fix Now'}
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6">
            {/* Database Status */}
            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-blue-500/10 text-blue-500 rounded-lg">
                  <Database className="w-6 h-6" />
                </div>
                {getStatusIcon(health.database_status)}
              </div>
              <h3 className="text-gray-500 font-medium mb-1">Database Connection</h3>
              <p className="text-2xl font-bold text-gray-800">{health.database_status}</p>
            </div>

            {/* Document Health */}
            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-purple-500/10 text-purple-500 rounded-lg">
                  <FileText className="w-6 h-6" />
                </div>
                <div className={`px-2 py-1 rounded text-xs font-bold ${health.document_health.stuck > 0 ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                  {health.document_health.stuck > 0 ? 'STUCK DETECTED' : 'HEALTHY'}
                </div>
              </div>
              <h3 className="text-gray-500 font-medium mb-4">Document Pipeline</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500 uppercase">Ready</p>
                  <p className="text-xl font-bold text-green-400">{health.document_health.ready}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Failed</p>
                  <p className="text-xl font-bold text-red-400">{health.document_health.failed}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Processing</p>
                  <p className="text-xl font-bold text-blue-400">{health.document_health.processing}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Stuck (&gt;10m)</p>
                  <p className={`text-xl font-bold ${health.document_health.stuck > 0 ? 'text-red-500' : 'text-gray-800'}`}>
                    {health.document_health.stuck}
                  </p>
                </div>
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-orange-500/10 text-orange-500 rounded-lg">
                  <Zap className="w-6 h-6" />
                </div>
                <div className={`px-2 py-1 rounded text-xs font-bold ${health.performance_metrics.avg_retrieval_time_ms > 2000 ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                  {health.performance_metrics.avg_retrieval_time_ms > 2000 ? 'SLOW' : 'FAST'}
                </div>
              </div>
              <h3 className="text-gray-500 font-medium mb-4">Performance</h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">CRUD Latency</span>
                  <span className="font-mono">{health.performance_metrics.avg_crud_latency_ms} ms</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Retrieval Time</span>
                  <span className={`font-mono ${health.performance_metrics.avg_retrieval_time_ms > 2000 ? 'text-red-400' : ''}`}>
                    {health.performance_metrics.avg_retrieval_time_ms} ms
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Slow Queries</span>
                  <span className="font-mono">{health.performance_metrics.slow_query_count}</span>
                </div>
              </div>
            </div>

            {/* Integrity Checks Overview */}
            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-teal-500/10 text-teal-500 rounded-lg">
                  <Server className="w-6 h-6" />
                </div>
                {getStatusIcon(health.integrity_checks.status)}
              </div>
              <h3 className="text-gray-500 font-medium mb-4">Integrity Checks</h3>
              {health.integrity_checks.issues.length === 0 ? (
                <div className="flex items-center gap-2 text-green-400 bg-green-400/10 p-3 rounded-lg">
                  <CheckCircle2 className="w-5 h-5" />
                  <span className="text-sm font-medium">All checks passed</span>
                </div>
              ) : (
                <div className="space-y-2 h-24 overflow-y-auto pr-2 custom-scrollbar">
                  {health.integrity_checks.issues.map((issue, idx) => (
                    <div key={idx} className="text-xs p-2 bg-red-500/10 text-red-400 rounded border border-red-500/20 truncate" title={issue}>
                      {issue}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          {/* System Audit Preview / Link */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
              <div className="p-6 border-b border-gray-200 flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-blue-500" />
                  <h3 className="font-bold text-lg">Recent System Audit</h3>
                </div>
                <Link 
                  to="/admin/audit" 
                  className="text-sm font-bold text-blue-600 hover:text-blue-700 flex items-center gap-1 group"
                >
                  View Full Audit Trail
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Link>
              </div>
              <div className="flex-1 overflow-y-auto">
                {health.recent_audit.length === 0 ? (
                  <div className="p-8 text-center text-gray-500 bg-gray-50/30 h-full flex flex-col items-center justify-center">
                    <Activity className="w-12 h-12 mb-4 opacity-10" />
                    <p className="text-sm max-w-sm">
                      No recent activities found for this client. 
                      Activities will appear here as they occur.
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {health.recent_audit.map((log, idx) => (
                      <div key={idx} className="p-4 hover:bg-gray-50 transition-colors flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${log.status === 'SUCCESS' ? 'bg-green-500' : 'bg-red-500'}`} />
                          <div>
                            <p className="text-sm font-bold text-gray-800">{log.action}</p>
                            <p className="text-xs text-gray-500">{log.entity}</p>
                          </div>
                        </div>
                        <div className="text-right text-[10px] text-gray-400 font-mono">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="bg-gradient-to-br from-indigo-600 to-blue-700 rounded-xl p-6 text-white shadow-lg flex flex-col justify-between relative overflow-hidden">
               <div className="relative z-10">
                 <h3 className="font-bold text-lg mb-2">Automated Diagnostics</h3>
                 <p className="text-indigo-100 text-sm leading-relaxed mb-4">
                   Run deep-scan diagnostics to identify hidden semantic conflicts or orphaned data paths.
                 </p>
               </div>
               <Link 
                 to="/admin/health" 
                 className="relative z-10 w-full py-3 bg-white/20 hover:bg-white/30 backdrop-blur-md rounded-lg text-center font-bold text-sm transition-all border border-white/10"
               >
                 Launch Diagnostic Tool
               </Link>
               <Zap className="absolute -bottom-6 -right-6 w-32 h-32 text-white/10 -rotate-12" />
            </div>
          </div>

          {/* Configuration Diagnostics Section */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-amber-500" />
                <h3 className="font-bold text-lg">Configuration Diagnostics</h3>
              </div>
              <span className="bg-amber-100 border border-amber-200 text-amber-600 text-xs px-2 py-1 rounded">
                {health.configuration_diagnostics.warnings.length} issues found
              </span>
            </div>
            
            {health.configuration_diagnostics.warnings.length === 0 ? (
              <div className="p-12 text-center text-gray-500 bg-gray-50/20">
                <CheckCircle2 className="w-12 h-12 mb-4 mx-auto text-green-500 opacity-50" />
                <p className="font-medium text-gray-800">Your configuration is healthy!</p>
                <p className="text-sm">Navigation items and semantic metadata are correctly mapped.</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {health.configuration_diagnostics.warnings.map((warning, idx) => (
                  <div key={idx} className="p-4 hover:bg-amber-50/30 transition-colors">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex gap-3">
                        <div className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                          warning.severity === 'error' ? 'bg-red-500' : 'bg-amber-500'
                        }`} />
                        <div>
                          <p className="text-sm font-medium text-gray-900">{warning.message}</p>
                          <p className="text-xs text-gray-500 mt-1 capitalize">Source: {warning.type.replace(/_/g, ' ')}</p>
                        </div>
                      </div>
                      {warning.suggested_fix && (
                        <button className="flex-shrink-0 text-[10px] font-bold uppercase tracking-wider text-amber-600 border border-amber-200 px-2 py-1 rounded hover:bg-amber-100 transition-all">
                          Quick Fix: {warning.suggested_fix.description}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Tables Detailed Breakdown */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center">
              <h3 className="font-bold text-lg">Table Health Details</h3>
              <span className="bg-gray-100 border border-gray-200 text-gray-600 text-xs px-2 py-1 rounded">
                Showing {health.table_health.length} flagged tables
              </span>
            </div>
            {health.table_health.length === 0 ? (
              <div className="p-12 text-center text-gray-500 flex flex-col items-center">
                <ShieldAlert className="w-12 h-12 mb-4 opacity-50" />
                <p>No table integrity issues detected.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600 text-sm">
                      <th className="p-4 font-medium border-b border-gray-200">Table Name</th>
                      <th className="p-4 font-medium border-b border-gray-200">Status</th>
                      <th className="p-4 font-medium border-b border-gray-200">Issue Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {health.table_health.map((t, idx) => (
                      <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                        <td className="p-4 font-mono text-sm text-gray-700">{t.table}</td>
                        <td className="p-4">
                          <span className={`px-2 py-1 text-[10px] uppercase font-bold tracking-wider rounded border ${
                            t.status === 'ERROR' ? 'text-red-400 bg-red-400/10 border-red-400/20' : 
                            'text-yellow-400 bg-yellow-400/10 border-yellow-400/20'
                          }`}>
                            {t.status}
                          </span>
                        </td>
                        <td className="p-4 text-sm text-gray-600">{t.issue}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
