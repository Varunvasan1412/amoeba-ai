/// <reference types="vite/client" />
import React, { useEffect } from 'react';
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
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';
import axios from 'axios';

interface RelationshipGraphProps {
    apiKey: string | null;
}

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 172;
const nodeHeight = 36;

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

    // We are shifting the dagre node position (anchor=center center) to the top left
    // so it matches the React Flow node anchor point (top left).
    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    };

    return node;
  });

  return { nodes, edges };
};

const RelationshipGraph: React.FC<RelationshipGraphProps> = ({ apiKey }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!apiKey) return;

    const fetchData = async () => {
        try {
            const API_BASE = import.meta.env.VITE_API_URL || ""; 
            const res = await axios.get(`${API_BASE}/api/v2/relationships`, {
                headers: { "X-API-Key": apiKey }
            });
            const data = res.data; // AllowedRelationship[]

            const newNodes: Node[] = [];
            const newEdges: Edge[] = [];
            const nodeSet = new Set<string>();

            data.forEach((rel: any) => {
                // Add Nodes
                if (!nodeSet.has(rel.parent_table)) {
                    newNodes.push({
                        id: rel.parent_table,
                        data: { label: rel.parent_table },
                        position: { x: 0, y: 0 },
                        style: { border: '1px solid #777', borderRadius: '8px', padding: '10px', background: 'white', minWidth: '150px', textAlign: 'center' }
                    });
                    nodeSet.add(rel.parent_table);
                }
                if (!nodeSet.has(rel.child_table)) {
                    newNodes.push({
                        id: rel.child_table,
                        data: { label: rel.child_table },
                        position: { x: 0, y: 0 },
                        style: { border: '1px solid #777', borderRadius: '8px', padding: '10px', background: 'white', minWidth: '150px', textAlign: 'center' }

                    });
                    nodeSet.add(rel.child_table);
                }

                // Color Logic based on Risk
                let edgeColor = '#b1b1b7'; // default gray
                if (rel.risk_level === 'safe') edgeColor = '#10b981'; // green
                else if (rel.risk_level === 'heuristic') edgeColor = '#f59e0b'; // yellow
                else if (rel.risk_level === 'circular') edgeColor = '#ef4444'; // red
                else if (rel.risk_level === 'high_cardinality') edgeColor = '#8b5cf6'; // purple

                // Opacity based on enabled status
                const opacity = rel.is_enabled ? 1 : 0.3;
                const strokeWidth = rel.is_enabled ? 2 : 1;
                const animated = rel.is_enabled;

                newEdges.push({
                    id: `e${rel.id}`,
                    source: rel.parent_table,
                    target: rel.child_table,
                    type: 'smoothstep',
                    animated: animated,
                    style: { stroke: edgeColor, opacity: opacity, strokeWidth: strokeWidth },
                    markerEnd: {
                        type: MarkerType.ArrowClosed,
                        color: edgeColor,
                    },
                });
            });

            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                newNodes,
                newEdges,
                'LR' // Left to Right
            );

            setNodes(layoutedNodes);
            setEdges(layoutedEdges);

        } catch (err) {
            console.error("Failed to load graph data", err);
        }
    };

    fetchData();
  }, [apiKey, setNodes, setEdges]);


  return (
    <div style={{ height: '600px', border: '1px solid #eee', borderRadius: '12px', overflow: 'hidden' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
        <Panel position="top-right">
            <div className="bg-white p-2 rounded shadow text-xs">
                <div className="font-bold mb-1">Risk Levels</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-green-500 rounded-full"></div> Safe</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-yellow-500 rounded-full"></div> Heuristic</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-red-500 rounded-full"></div> Circular</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-purple-500 rounded-full"></div> High Card.</div>
            </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};

export default RelationshipGraph;
