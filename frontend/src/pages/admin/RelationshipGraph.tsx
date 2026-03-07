/// <reference types="vite/client" />
import React, { useEffect, useCallback, useState, useMemo } from 'react';
import ReactFlow, {
  ConnectionLineType,
  Panel,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  type Node,
  type Edge,
  MarkerType,
  Position,
  addEdge,
  type Connection,
  useReactFlow,
  ReactFlowProvider
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';
import { TableNode } from '../../components/admin/TableNode';
import { apiFetch } from '../../utils/api';
import { AlertCircle, CheckCircle, Info, Loader2, X, Search, Crosshair, RefreshCcw, Command } from 'lucide-react';

interface RelationshipGraphProps {
    apiKey: string | null;
}

const nodeTypes = {
  tableNode: TableNode,
};

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 220; 
const nodeHeight = 200; 

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction });
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });
  dagre.layout(dagreGraph);
  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = (isHorizontal ? Position.Left : Position.Top) as Position;
    node.sourcePosition = (isHorizontal ? Position.Right : Position.Bottom) as Position;
    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    };
    return node;
  });
  return { nodes, edges };
};

const RelationshipGraphInner: React.FC<RelationshipGraphProps> = ({ apiKey }) => {
  const { setCenter, fitView } = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{type: 'success' | 'info', text: string} | null>(null);
  
  // Search state
  const [searchTerm, setSearchTerm] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);

  // Manual Connection Modal State
  const [connModal, setConnModal] = useState<{source: string, target: string} | null>(null);
  const [sourceCol, setSourceCol] = useState('');
  const [targetCol, setTargetCol] = useState('');
  const [schemaData, setSchemaData] = useState<any[]>([]);

  const showMessage = (type: 'success' | 'info', text: string) => {
      setMessage({ type, text });
      setTimeout(() => setMessage(null), 3000);
  };

  const fetchData = useCallback(async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
        const API_BASE = import.meta.env.VITE_API_URL || ""; 
        const constructUrl = (path: string) => `${API_BASE}${path}`.replace(/\/\//g, '/').replace(':/', '://');
        const schemaRes = await apiFetch(constructUrl('/api/v2/semantic/schema'), {
            headers: { "X-API-Key": apiKey }
        });
        const fullSchema = await schemaRes.json();
        setSchemaData(fullSchema);
        const tableColumns: Record<string, string[]> = {};
        fullSchema.forEach((col: any) => {
            if (!tableColumns[col.table_name]) tableColumns[col.table_name] = [];
            tableColumns[col.table_name].push(col.column_name);
        });
        const res = await apiFetch(constructUrl('/api/v2/relationships'), {
            headers: { "X-API-Key": apiKey }
        });
        const data = await res.json(); 
        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];
        const nodeSet = new Set<string>();
        if (Array.isArray(data)) {
            data.forEach((rel: any) => {
                const tables = [rel.parent_table, rel.child_table];
                tables.forEach(t => {
                    if (!nodeSet.has(t)) {
                        newNodes.push({
                            id: t,
                            type: 'tableNode',
                            data: { label: t, columns: tableColumns[t] || ['id'] },
                            position: { x: 0, y: 0 },
                        });
                        nodeSet.add(t);
                    }
                });
                const edgeColor = rel.risk_level === 'safe' ? '#10b981' : 
                                rel.risk_level === 'heuristic' ? '#f59e0b' : 
                                rel.risk_level === 'manual' ? '#3b82f6' : '#ef4444';
                newEdges.push({
                    id: `e${rel.id}`,
                    source: rel.parent_table,
                    target: rel.child_table,
                    type: 'smoothstep',
                    animated: rel.is_enabled,
                    label: `${rel.parent_column} → ${rel.child_column}`,
                    labelStyle: { fontSize: '8px', fill: '#666', fontWeight: 700 },
                    labelBgPadding: [2, 2],
                    labelBgBorderRadius: 4,
                    labelBgStyle: { fill: '#fff', fillOpacity: 0.8 },
                    style: { stroke: edgeColor, opacity: rel.is_enabled ? 1 : 0.2, strokeWidth: 3 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor },
                    data: { id: rel.id, is_enabled: rel.is_enabled }
                });
            });
        }
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(newNodes, newEdges);
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
    } catch (err) {
        console.error("Failed to load graph data", err);
    } finally {
        setLoading(false);
    }
  }, [apiKey, setNodes, setEdges]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Autocomplete suggestions
  const suggestions = useMemo(() => {
      if (!searchTerm || searchTerm.length < 1) return [];
      return nodes
        .filter(n => n.id.toLowerCase().includes(searchTerm.toLowerCase()))
        .slice(0, 5);
  }, [searchTerm, nodes]);

  const goToNode = (nodeId: string) => {
      const node = nodes.find(n => n.id === nodeId);
      if (node) {
          setCenter(node.position.x + nodeWidth / 2, node.position.y + nodeHeight / 2, { zoom: 1.2, duration: 800 });
          setShowSuggestions(false);
          setActiveSuggestionIndex(-1);
          setSearchTerm(node.id);
          showMessage('info', `Located ${node.id}`);
      }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
      if (!showSuggestions || suggestions.length === 0) return;
      if (e.key === 'ArrowDown') {
          e.preventDefault();
          setActiveSuggestionIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev));
      } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          setActiveSuggestionIndex(prev => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === 'Enter') {
          e.preventDefault();
          if (activeSuggestionIndex >= 0) {
              goToNode(suggestions[activeSuggestionIndex].id);
          } else if (suggestions.length > 0) {
              goToNode(suggestions[0].id);
          }
      } else if (e.key === 'Escape') {
          setShowSuggestions(false);
          setActiveSuggestionIndex(-1);
      }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      if (activeSuggestionIndex >= 0) {
          goToNode(suggestions[activeSuggestionIndex].id);
      } else if (suggestions.length > 0) {
          goToNode(suggestions[0].id);
      }
  };

  const onEdgeClick = async (event: React.MouseEvent, edge: Edge) => {
      const relId = edge.data?.id;
      const currentStatus = edge.data?.is_enabled;
      if (!relId || !apiKey) return;
      try {
          const API_BASE = import.meta.env.VITE_API_URL || "";
          const url = `${API_BASE}/api/v2/relationships/${relId}/toggle`.replace(/\/\//g, '/').replace(':/', '://');
          const response = await apiFetch(url, {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
              body: JSON.stringify({ is_enabled: !currentStatus })
          });
          if (response.ok) {
              showMessage('success', `Relationship ${!currentStatus ? 'enabled' : 'disabled'}`);
              fetchData();
          }
      } catch (err) {
          console.error(err);
      }
  };

  const onConnect = useCallback((params: Connection) => {
    setConnModal({ source: params.source || '', target: params.target || '' });
  }, []);

  const handleCreateManualJoin = async () => {
    if (!connModal || !sourceCol || !targetCol || !apiKey) return;
    try {
        const API_BASE = import.meta.env.VITE_API_URL || "";
        const url = `${API_BASE}/api/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://');
        await apiFetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
            body: JSON.stringify({
                parent_table: connModal.source,
                parent_column: sourceCol,
                child_table: connModal.target,
                child_column: targetCol
            })
        });
        setConnModal(null);
        setSourceCol('');
        setTargetCol('');
        showMessage('success', "Manual connection created!");
        fetchData();
    } catch (err) {
        console.error(err);
    }
  };

  const getColsForTable = (table: string) => {
      return schemaData.filter(s => s.table_name === table).map(s => s.column_name);
  };

  return (
    <div style={{ height: '750px', position: 'relative' }}>
      {loading && (
          <div className="absolute inset-0 bg-white/50 backdrop-blur-[1px] z-50 flex items-center justify-center">
              <Loader2 className="animate-spin text-blue-600" size={48} />
          </div>
      )}

      {message && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-2 bg-slate-900 text-white px-4 py-2 rounded-full shadow-2xl animate-in fade-in slide-in-from-top-4">
              {message.type === 'success' ? <CheckCircle className="text-green-400" size={16}/> : <Info className="text-blue-400" size={16}/>}
              <span className="text-xs font-bold">{message.text}</span>
          </div>
      )}

      {/* Manual Connection Modal */}
      {connModal && (
          <div className="absolute inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
              <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                  <div className="bg-blue-600 p-4 text-white flex justify-between items-center">
                      <h3 className="font-bold flex items-center gap-2 text-sm uppercase tracking-wider">
                          <AlertCircle size={16}/> Create Manual Join
                      </h3>
                      <button onClick={() => setConnModal(null)} className="hover:bg-blue-700 p-1 rounded transition">
                          <X size={20}/>
                      </button>
                  </div>
                  <div className="p-6 space-y-6">
                      <div className="grid grid-cols-2 gap-4 text-center">
                          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                               <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Source Table</p>
                               <p className="font-bold text-slate-800 text-sm">{connModal.source}</p>
                               <select className="mt-3 w-full border text-xs p-2 rounded-lg bg-white" value={sourceCol} onChange={e => setSourceCol(e.target.value)}>
                                   <option value="">-- Select Column --</option>
                                   {getColsForTable(connModal.source).map(c => <option key={c} value={c}>{c}</option>)}
                               </select>
                          </div>
                          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
                               <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Target Table</p>
                               <p className="font-bold text-slate-800 text-sm">{connModal.target}</p>
                               <select className="mt-3 w-full border text-xs p-2 rounded-lg bg-white" value={targetCol} onChange={e => setTargetCol(e.target.value)}>
                                   <option value="">-- Select Column --</option>
                                   {getColsForTable(connModal.target).map(c => <option key={c} value={c}>{c}</option>)}
                               </select>
                          </div>
                      </div>
                      <button onClick={handleCreateManualJoin} disabled={!sourceCol || !targetCol} className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 transition disabled:opacity-50 shadow-lg shadow-blue-100">Establish Join</button>
                  </div>
              </div>
          </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onEdgeClick={onEdgeClick}
        onConnect={onConnect}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
      >
        <Background color="#cbd5e1" variant={'dots' as any} />
        <Controls />
        <MiniMap />
        
        {/* Navigation & Search Panel with Autocomplete */}
        <Panel position="top-right" className="m-4 space-y-4 relative">
            <div className="relative">
                <form onSubmit={handleSearchSubmit} className="bg-white/90 backdrop-blur-md p-2 rounded-2xl shadow-2xl border border-white flex items-center gap-2 w-[280px]">
                    <div className="pl-2 text-slate-400"><Search size={18} /></div>
                    <input 
                        placeholder="Type table name..."
                        className="flex-1 bg-transparent border-none outline-none text-sm font-bold text-slate-700"
                        value={searchTerm}
                        onChange={e => {
                            setSearchTerm(e.target.value);
                            setShowSuggestions(true);
                            setActiveSuggestionIndex(-1);
                        }}
                        onFocus={() => setShowSuggestions(true)}
                        onKeyDown={handleKeyDown}
                    />
                    {searchTerm && (
                        <button type="button" onClick={() => {setSearchTerm(''); setShowSuggestions(false); setActiveSuggestionIndex(-1);}} className="p-1 text-slate-300 hover:text-slate-500">
                            <X size={14} />
                        </button>
                    )}
                    <button type="submit" className="bg-blue-600 text-white p-2 rounded-xl hover:bg-blue-700 transition shadow-lg shadow-blue-100">
                        <Crosshair size={16} />
                    </button>
                </form>

                {/* Suggestions Dropdown */}
                {showSuggestions && suggestions.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden z-[100] animate-in slide-in-from-top-2 duration-200">
                        {suggestions.map((s, idx) => (
                            <button 
                                key={s.id}
                                onClick={() => goToNode(s.id)}
                                onMouseEnter={() => setActiveSuggestionIndex(idx)}
                                className={`w-full text-left px-4 py-3 flex items-center gap-3 transition-colors border-b last:border-b-0 border-gray-50 ${
                                    activeSuggestionIndex === idx ? 'bg-blue-600 text-white' : 'hover:bg-blue-50 text-slate-700'
                                }`}
                            >
                                <div className={`p-1.5 rounded-lg transition-colors ${
                                    activeSuggestionIndex === idx ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-400'
                                }`}>
                                    <Command size={14} />
                                </div>
                                <span className="text-sm font-bold">{s.id}</span>
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <div className="bg-white/80 backdrop-blur-md p-4 rounded-2xl shadow-xl border border-white/20 text-[10px] space-y-3 min-w-[140px]">
                <div className="flex justify-between items-center border-b pb-2 mb-2">
                    <div className="font-bold text-slate-800 uppercase tracking-widest">Controls</div>
                    <button onClick={() => fitView({ duration: 800 })} className="text-blue-600 hover:text-blue-800 flex items-center gap-1 font-black uppercase tracking-tighter">
                        <RefreshCcw size={10} /> Reset View
                    </button>
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                    <div className="w-4 h-1 bg-blue-500 rounded-full"></div>
                    <span>Click edge to Toggle</span>
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                    <div className="w-4 h-1 bg-slate-300 rounded-full"></div>
                    <span>Drag nodes to Connect</span>
                </div>
                
                <div className="font-bold text-slate-800 uppercase tracking-widest border-b pb-2 mb-2 pt-2">Join Health</div>
                <div className="flex items-center gap-2"><div className="w-3 h-3 bg-green-500 rounded-full"></div> Safe FK</div>
                <div className="flex items-center gap-2"><div className="w-3 h-3 bg-blue-500 rounded-full"></div> Manual</div>
                <div className="flex items-center gap-2"><div className="w-3 h-3 bg-yellow-500 rounded-full"></div> Heuristic</div>
                <div className="flex items-center gap-2"><div className="w-3 h-3 bg-red-500 rounded-full"></div> Circular</div>
            </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};

const RelationshipGraph: React.FC<RelationshipGraphProps> = (props) => (
    <ReactFlowProvider>
        <RelationshipGraphInner {...props} />
    </ReactFlowProvider>
);

export default RelationshipGraph;
