import React, { useEffect, useState, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  MarkerType,
  ConnectionLineType,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { TableNode } from './TableNode';
import { Plus, X, Search, GitBranch, Info, Zap } from 'lucide-react';

interface JoinDefinition {
  table: string;
  parent: string;
}

interface JoinGraphProps {
  baseTable: string;
  relationships: any; 
  onJoinsChange: (joins: JoinDefinition[]) => void;
  initialJoins?: JoinDefinition[];
}

const nodeTypes = {
  tableNode: TableNode,
};

export const JoinGraph: React.FC<JoinGraphProps> = ({ baseTable, relationships, onJoinsChange, initialJoins = [] }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const handleAddJoin = useCallback((table: string, parent: string) => {
      onJoinsChange([...initialJoins, { table, parent }]);
  }, [initialJoins, onJoinsChange]);

  const handleRemoveJoin = useCallback((table: string) => {
      const toRemove = new Set([table]);
      let size;
      do {
          size = toRemove.size;
          initialJoins.forEach(j => {
              if (toRemove.has(j.parent)) toRemove.add(j.table);
          });
      } while (toRemove.size !== size);
      onJoinsChange(initialJoins.filter(j => !toRemove.has(j.table)));
  }, [initialJoins, onJoinsChange]);

  // 1. Build Graph with Discovery (Active + Ghost Nodes)
  useEffect(() => {
    if (!baseTable) {
        setNodes([]);
        setEdges([]);
        return;
    }

    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];
    const activeTableSet = new Set([baseTable, ...initialJoins.map(j => j.table)]);
    
    // Level tracking for layout
    const levelMap: Record<string, number> = { [baseTable]: 0 };
    const getLevel = (tableName: string): number => levelMap[tableName] || 0;

    // A. Add Base Node
    newNodes.push({
        id: baseTable,
        type: 'tableNode',
        data: { label: baseTable, columns: [] },
        position: { x: 0, y: 0 },
        style: { border: '3px solid #8b5cf6', width: 220 }
    });

    // B. Place Active Joins (Recursive)
    const placeActive = (parent: string, x: number, y: number) => {
        const children = initialJoins.filter(j => j.parent === parent);
        children.forEach((child, idx) => {
            const childX = x + 350;
            const childY = y + (idx * 180) - ((children.length - 1) * 90);
            levelMap[child.table] = getLevel(parent) + 1;

            newNodes.push({
                id: child.table,
                type: 'tableNode',
                data: { label: child.table, columns: [] },
                position: { x: childX, y: childY },
            });

            newEdges.push({
                id: `e-${parent}-${child.table}`,
                source: parent,
                target: child.table,
                type: 'smoothstep',
                animated: true,
                style: { stroke: '#8b5cf6', strokeWidth: 3 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#8b5cf6' }
            });

            placeActive(child.table, childX, childY);
        });
    };
    placeActive(baseTable, 0, 0);

    // C. Discovery: Project "Ghost Nodes" for every active node
    const activeNodesList = [...newNodes]; // Snapshot before adding ghosts
    activeNodesList.forEach(activeNode => {
        const parentTable = activeNode.id;
        const potentialJoins = relationships[parentTable] || {};
        
        Object.keys(potentialJoins).forEach((targetTable, idx) => {
            if (activeTableSet.has(targetTable)) return; // Already in map

            const ghostId = `ghost-${parentTable}-${targetTable}`;
            const ghostX = activeNode.position.x + 300;
            const ghostY = activeNode.position.y + 80 + (idx * 100);

            newNodes.push({
                id: ghostId,
                type: 'tableNode',
                data: { 
                    label: targetTable, 
                    isGhost: true,
                    onGhostClick: (t: string) => handleAddJoin(t, parentTable)
                },
                position: { x: ghostX, y: ghostY },
            });

            newEdges.push({
                id: `edge-${ghostId}`,
                source: parentTable,
                target: ghostId,
                type: 'smoothstep',
                animated: false,
                style: { stroke: '#cbd5e1', strokeWidth: 2, strokeDasharray: '5,5' },
            });
        });
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [baseTable, initialJoins, relationships, setNodes, setEdges, handleAddJoin]);

  return (
    <div className="h-full bg-slate-50 relative rounded-3xl overflow-hidden border-2 border-slate-100 shadow-inner">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
        onNodeContextMenu={(e, node) => {
            e.preventDefault();
            if (node.id !== baseTable && !node.id.startsWith('ghost-')) handleRemoveJoin(node.id);
        }}
        nodesDraggable={true}
        zoomOnScroll={true}
        panOnDrag={true}
      >
        <Background color="#e2e8f0" variant={'dots' as any} />
        <Controls showInteractive={false} className="bg-white rounded-xl shadow-lg border-none m-4" />
        
        <Panel position="top-left" className="m-6">
            <div className="bg-white/90 backdrop-blur-md p-5 rounded-3xl shadow-2xl border border-white flex flex-col gap-4 min-w-[200px]">
                <div>
                    <span className="text-[10px] font-black text-purple-500 uppercase tracking-widest leading-none block mb-1">Architecture Map</span>
                    <h4 className="text-sm font-bold text-slate-800">{initialJoins.length + 1} Tables in Report</h4>
                </div>
                
                <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500">
                        <div className="w-2 h-2 rounded-full bg-purple-500" /> Active Tables
                    </div>
                    <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400">
                        <div className="w-2 h-2 rounded-full border-2 border-dashed border-slate-300" /> Available Joins
                    </div>
                </div>

                <button 
                    onClick={() => onJoinsChange([])}
                    className="w-full bg-slate-100 hover:bg-red-50 text-red-500 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition-colors"
                >
                    Reset Map
                </button>
            </div>
        </Panel>

        <Panel position="bottom-center" className="mb-8">
            <div className="bg-slate-900/80 backdrop-blur-md px-6 py-3 rounded-full text-white text-[10px] font-bold flex items-center gap-6 shadow-2xl border border-white/10">
                <span className="flex items-center gap-2"><Zap size={14} className="text-yellow-400" /> Click Ghost Nodes to add them</span>
                <div className="w-px h-4 bg-white/20" />
                <span className="flex items-center gap-2"><Info size={14} className="text-blue-400" /> Right-click active table to remove</span>
            </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};
