import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Database, Plus, X } from 'lucide-react';

interface TableNodeProps {
  data: {
    label: string;
    columns: string[];
    isGhost?: boolean;
    onGhostClick?: (table: string) => void;
    onRemoveClick?: () => void;
  };
}

export const TableNode = memo(({ data }: TableNodeProps) => {
  if (data.isGhost) {
    return (
      <div 
        onClick={() => data.onGhostClick?.(data.label)}
        className="bg-white/40 backdrop-blur-sm rounded-2xl border-2 border-dashed border-slate-300 p-4 flex items-center gap-3 cursor-pointer hover:border-purple-400 hover:bg-purple-50 transition-all group"
      >
        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400 group-hover:bg-purple-100 group-hover:text-purple-600 transition-colors">
            <Plus size={16} />
        </div>
        <div>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Connect</p>
            <p className="text-sm font-bold text-slate-500 group-hover:text-purple-700">{data.label}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-xl border-2 border-slate-200 min-w-[200px] overflow-hidden group hover:border-blue-400 transition-all">
      <div className="bg-slate-800 p-3 flex items-center justify-between border-b border-slate-700">
        <div className="flex items-center gap-2">
            <Database size={14} className="text-blue-400" />
            <span className="text-white font-bold text-xs tracking-tight uppercase">{data.label}</span>
        </div>
        <div className="flex items-center gap-1.5">
            {data.onRemoveClick && (
                <button 
                    onClick={(e) => {
                        e.stopPropagation();
                        data.onRemoveClick?.();
                    }}
                    className="p-1 hover:bg-red-500/20 rounded-md text-slate-400 hover:text-red-400 transition-colors"
                    title="Remove Table"
                >
                    <X size={12} />
                </button>
            )}
            <div className="w-2 h-2 rounded-full bg-green-500 shadow-sm shadow-green-500/50" />
        </div>
      </div>
      
      <div className="p-2 bg-slate-50/50">
          <p className="text-[9px] font-black text-slate-400 uppercase tracking-tighter">Table Active</p>
      </div>

      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-blue-500 border-2 border-white" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-blue-500 border-2 border-white" />
    </div>
  );
});

TableNode.displayName = 'TableNode';
