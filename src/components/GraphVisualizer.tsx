import React, { useState, useRef, useMemo } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Filter, Layers, Info, ArrowRight, Eye, ShieldAlert } from 'lucide-react';
import { TraceResult, WalletNode, TransactionEdge, RiskVerdict } from '../types';

interface GraphVisualizerProps {
  trace: TraceResult;
  selectedNode: WalletNode | null;
  onSelectNode: (node: WalletNode) => void;
  hopFilter: number;
  onHopFilterChange: (hops: number) => void;
}

export const GraphVisualizer: React.FC<GraphVisualizerProps> = ({
  trace,
  selectedNode,
  onSelectNode,
  hopFilter,
  onHopFilterChange,
}) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [verdictFilter, setVerdictFilter] = useState<'all' | 'confirmed' | 'watch'>('all');
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const containerRef = useRef<HTMLDivElement>(null);

  // Filter nodes according to hopFilter and verdictFilter
  const filteredNodes = useMemo(() => {
    return trace.nodes.filter(node => {
      if (node.hop > hopFilter) return false;
      if (verdictFilter === 'confirmed' && node.verdict !== 'confirmed') return false;
      if (verdictFilter === 'watch' && node.verdict !== 'watch') return false;
      return true;
    });
  }, [trace.nodes, hopFilter, verdictFilter]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map(n => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    return trace.edges.filter(edge => {
      return filteredNodeIds.has(edge.from) && filteredNodeIds.has(edge.to);
    });
  }, [trace.edges, filteredNodeIds]);

  // Layout node positions dynamically if needed or use defined x,y
  const nodePositions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    
    // Group nodes by hop
    const byHop: Record<number, WalletNode[]> = {};
    filteredNodes.forEach(node => {
      if (!byHop[node.hop]) byHop[node.hop] = [];
      byHop[node.hop].push(node);
    });

    const maxHop = Math.max(...filteredNodes.map(n => n.hop), 1);
    const hopWidth = 720 / Math.max(maxHop, 1);

    Object.entries(byHop).forEach(([hopStr, nodeList]) => {
      const hop = Number(hopStr);
      const count = nodeList.length;
      nodeList.forEach((node, index) => {
        // If pre-set in data, respect it or adjust spacing
        const x = node.x ?? 80 + hop * 200;
        const y = node.y ?? 220 + (index - (count - 1) / 2) * 90;
        map.set(node.id, { x, y });
      });
    });

    return map;
  }, [filteredNodes]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === containerRef.current || (e.target as HTMLElement).tagName === 'svg') {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className="bg-[#0e0e12] rounded-2xl border border-zinc-800/80 shadow-lg shadow-black/20 overflow-hidden flex flex-col">
      {/* Graph Toolbar */}
      <div className="px-4 py-2.5 bg-[#121217] border-b border-zinc-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          <span className="font-bold text-white tracking-tight">Fund Flow Graph</span>
          <span className="text-[11px] text-zinc-400 font-mono">
            [{filteredNodes.length} nodes, {filteredEdges.length} hops]
          </span>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Hop Depth Selector */}
          <div className="flex items-center gap-1.5 bg-[#16161d] px-2 py-1 rounded-lg border border-zinc-800">
            <span className="text-zinc-400 font-medium">Depth:</span>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4].map(hops => (
                <button
                  key={hops}
                  onClick={() => onHopFilterChange(hops)}
                  className={`px-2 py-0.5 rounded-md font-mono font-medium transition-colors cursor-pointer ${
                    hopFilter >= hops
                      ? 'bg-indigo-600 text-white font-bold shadow-xs'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {hops}H
                </button>
              ))}
            </div>
          </div>

          {/* Verdict Filter */}
          <div className="flex items-center gap-1.5 bg-[#16161d] px-2 py-1 rounded-lg border border-zinc-800">
            <Filter className="w-3.5 h-3.5 text-zinc-400" />
            <select
              value={verdictFilter}
              onChange={e => setVerdictFilter(e.target.value as any)}
              className="bg-transparent font-medium text-zinc-200 outline-none cursor-pointer"
            >
              <option value="all" className="bg-[#121217] text-zinc-200">All Verdicts</option>
              <option value="confirmed" className="bg-[#121217] text-zinc-200">Confirmed Risk Only</option>
              <option value="watch" className="bg-[#121217] text-zinc-200">Watchlist Only</option>
            </select>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-[#16161d] p-0.5 rounded-lg border border-zinc-800">
            <button
              onClick={() => setZoom(z => Math.min(z + 0.15, 2.2))}
              className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoom(z => Math.max(z - 0.15, 0.5))}
              className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleReset}
              className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Reset View"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* SVG Canvas Area */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className="relative w-full h-[460px] bg-[#070709] overflow-hidden cursor-grab active:cursor-grabbing select-none"
      >
        <svg
          className="w-full h-full"
          viewBox="0 0 960 460"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out'
          }}
        >
          <defs>
            {/* Arrow Marker */}
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#71717a" />
            </marker>

            <marker
              id="arrow-peel"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#f43f5e" />
            </marker>

            <marker
              id="arrow-mixer"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#a855f7" />
            </marker>

            {/* Glowing filters for highlighted nodes */}
            <filter id="glow-confirmed" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#f43f5e" floodOpacity="0.6" />
            </filter>
            <filter id="glow-selected" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="7" floodColor="#6366f1" floodOpacity="0.8" />
            </filter>
          </defs>

          {/* Grid lines for precision look */}
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1c1c24" strokeWidth="0.8" strokeDasharray="2 2" />
          </pattern>
          <rect width="960" height="460" fill="url(#grid)" opacity="0.8" />

          {/* Transaction Edges */}
          {filteredEdges.map(edge => {
            const start = nodePositions.get(edge.from);
            const end = nodePositions.get(edge.to);
            if (!start || !end) return null;

            const isSelected = selectedNode?.id === edge.from || selectedNode?.id === edge.to;
            const isPeel = edge.isPeelChain;
            const isMixer = edge.isMixerHop;

            // Bezier curve calculation
            const dx = end.x - start.x;
            const dy = end.y - start.y;
            const cx1 = start.x + dx * 0.5;
            const cy1 = start.y;
            const cx2 = start.x + dx * 0.5;
            const cy2 = end.y;
            const pathD = `M ${start.x} ${start.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${end.x} ${end.y}`;

            const strokeColor = isMixer ? '#a855f7' : isPeel ? '#f43f5e' : isSelected ? '#6366f1' : '#3f3f46';
            const markerId = isMixer ? 'url(#arrow-mixer)' : isPeel ? 'url(#arrow-peel)' : 'url(#arrow)';

            const midX = (start.x + end.x) / 2;
            const midY = (start.y + end.y) / 2;

            return (
              <g key={edge.id} className="transition-all">
                {/* Background thicker hit path */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={isSelected ? 3.5 : 2}
                  strokeDasharray={edge.isFanOut ? '4 3' : 'none'}
                  markerEnd={markerId}
                  opacity={isSelected ? 1 : 0.85}
                />

                {/* Animated pulse dot along the path to indicate fund flow direction */}
                <circle r="3" fill={strokeColor}>
                  <animateMotion
                    path={pathD}
                    dur={`${Math.max(2.5, 4 - edge.hop * 0.6)}s`}
                    repeatCount="indefinite"
                  />
                </circle>

                {/* Edge Label: BTC Amount */}
                <rect
                  x={midX - 28}
                  y={midY - 10}
                  width="56"
                  height="16"
                  rx="4"
                  fill="#121217"
                  stroke={strokeColor}
                  strokeWidth="0.8"
                  opacity="0.95"
                />
                <text
                  x={midX}
                  y={midY + 2}
                  textAnchor="middle"
                  fontSize="9"
                  fontFamily="monospace"
                  fontWeight="bold"
                  fill="#ededed"
                >
                  {edge.amountBtc} BTC
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {filteredNodes.map(node => {
            const pos = nodePositions.get(node.id);
            if (!pos) return null;

            const isSelected = selectedNode?.id === node.id;
            const isConfirmed = node.verdict === 'confirmed';
            const isWatch = node.verdict === 'watch';
            const isLicit = node.verdict === 'none';
            const isRoot = node.type === 'suspect_root';
            const isExchange = node.type === 'exchange_deposit' || node.type === 'exchange_hot_wallet';
            const isMixer = node.type === 'mixer_service';

            let nodeFill = '#16161c';
            let nodeStroke = '#71717a';

            if (isRoot) {
              nodeFill = '#2a1117';
              nodeStroke = '#f43f5e';
            } else if (isMixer) {
              nodeFill = '#221133';
              nodeStroke = '#c084fc';
            } else if (isExchange) {
              nodeFill = '#111d38';
              nodeStroke = '#60a5fa';
            } else if (isConfirmed) {
              nodeFill = '#281115';
              nodeStroke = '#fb7185';
            } else if (isWatch) {
              nodeFill = '#281b0a';
              nodeStroke = '#fbbf24';
            } else if (isLicit) {
              nodeFill = '#0d2419';
              nodeStroke = '#34d399';
            }

            const radius = isRoot ? 24 : isExchange ? 22 : 18;

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => onSelectNode(node)}
                className="cursor-pointer group"
                filter={isSelected ? 'url(#glow-selected)' : isConfirmed ? 'url(#glow-confirmed)' : undefined}
              >
                {/* Outer ring for root or exchange */}
                {(isRoot || isExchange) && (
                  <circle
                    r={radius + 5}
                    fill="none"
                    stroke={nodeStroke}
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                    className="animate-spin"
                    style={{ animationDuration: '16s' }}
                  />
                )}

                {/* Base Node Circle */}
                <circle
                  r={radius}
                  fill={nodeFill}
                  stroke={isSelected ? '#818cf8' : nodeStroke}
                  strokeWidth={isSelected ? 3 : 2}
                  className="transition-transform group-hover:scale-110"
                />

                {/* Node Glyph or Hop indicator */}
                <text
                  textAnchor="middle"
                  dy="4"
                  fontSize={radius > 20 ? '11' : '10'}
                  fontWeight="bold"
                  fill={nodeStroke}
                >
                  {isRoot ? 'ROOT' : isExchange ? 'VASP' : isMixer ? 'MIX' : `H${node.hop}`}
                </text>

                {/* Verdict Badge Mini-indicator */}
                <circle
                  cx={radius - 2}
                  cy={-radius + 2}
                  r="5"
                  fill={isConfirmed ? '#f43f5e' : isWatch ? '#fbbf24' : '#34d399'}
                  stroke="#0e0e12"
                  strokeWidth="1"
                />

                {/* Label Box below Node */}
                <g transform={`translate(0, ${radius + 12})`}>
                  <rect
                    x="-65"
                    y="0"
                    width="130"
                    height="28"
                    rx="6"
                    fill="#121217"
                    stroke={isSelected ? '#818cf8' : '#27272a'}
                    strokeWidth={isSelected ? 1.5 : 0.8}
                    className="shadow-md"
                  />
                  <text
                    x="0"
                    y="11"
                    textAnchor="middle"
                    fontSize="9.5"
                    fontWeight="bold"
                    fill="#f4f4f5"
                  >
                    {node.label.length > 18 ? node.label.substring(0, 16) + '…' : node.label}
                  </text>
                  <text
                    x="0"
                    y="22"
                    textAnchor="middle"
                    fontSize="8.5"
                    fontFamily="monospace"
                    fill="#a1a1aa"
                  >
                    {node.id.substring(0, 6)}...{node.id.substring(node.id.length - 4)}
                  </text>
                </g>
              </g>
            );
          })}
        </svg>

        {/* Legend Overlay at Bottom */}
        <div className="absolute bottom-3 left-3 bg-[#121217]/90 backdrop-blur-md p-2 rounded-xl border border-zinc-800/80 text-[11px] shadow-lg shadow-black/40 flex flex-wrap items-center gap-3 text-zinc-300">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-xs shadow-rose-500/50"></span>
            <span className="font-medium text-zinc-300">Confirmed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 shadow-xs shadow-amber-400/50"></span>
            <span className="font-medium text-zinc-300">Watchlist</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sky-400 shadow-xs shadow-sky-400/50"></span>
            <span className="font-medium text-zinc-300">VASP</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-400 shadow-xs shadow-purple-400/50"></span>
            <span className="font-medium text-zinc-300">Mixer</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-xs shadow-emerald-400/50"></span>
            <span className="font-medium text-zinc-300">Licit</span>
          </div>
        </div>
      </div>
    </div>
  );
};
