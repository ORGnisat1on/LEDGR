import React, { useState, useRef, useMemo, useCallback, useEffect } from 'react';
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
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  useEffect(() => {
    setExpandedNodes(new Set());
    setHoveredNodeId(null);
  }, [trace]);

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // ViewBox dimensions (matches the SVG viewBox)
  const VIEWBOX_WIDTH = 960;
  const VIEWBOX_HEIGHT = 460;
  // Padding around the graph when fitting (in viewBox units)
  const FIT_PADDING = 60;
  // Zoom limits — extended downward to accommodate large graphs (500 nodes)
  const ZOOM_MIN = 0.08;
  const ZOOM_MAX = 2.2;

  // Minimap settings: rendered only for graphs with > MINIMAP_NODE_THRESHOLD nodes
  const MINIMAP_NODE_THRESHOLD = 30;
  const MINIMAP_WIDTH = 160;
  const MINIMAP_HEIGHT = 80;

  // Edge stroke-width encoding — LOG-scaled by BTC amount, never linear (real
  // amounts span orders of magnitude). Tuned so a 0.001 BTC hop (~1.5px) and a
  // 5 BTC hop (~3.7px) are both visibly distinct without either dominating;
  // the largest demo-case amount (13.5 BTC) lands at ~4.7px. Live-pipeline
  // structural edges carry amountBtc: 0 → uniform base width (honest: no
  // fabricated amount variation).
  const EDGE_WIDTH_BASE = 1.5;
  const EDGE_WIDTH_LOG_FACTOR = 1.2;

  // Nodes/edges on an all-'none'-verdict path are visually receded (kept
  // visible, not hidden) — lower opacity, full structure intact.
  const RECESSED_OPACITY = 0.45;

  // Source encoding: dashed border = live-lookup trace (real-chain fetch, not
  // in the Elliptic training dataset — lower confidence tier); solid border =
  // elliptic-indexed (default; demo/mock traces carry no source and render
  // indexed-style).
  const isLiveLookupTrace = trace.source === 'live-lookup';

  const HUB_DEGREE_THRESHOLD = 15;

  const nodeDegrees = useMemo(() => {
    const degrees = new Map<string, number>();
    trace.nodes.forEach(n => degrees.set(n.id, 0));
    trace.edges.forEach(e => {
      degrees.set(e.from, (degrees.get(e.from) || 0) + 1);
      degrees.set(e.to, (degrees.get(e.to) || 0) + 1);
    });
    return degrees;
  }, [trace.nodes, trace.edges]);

  const hubs = useMemo(() => {
    return new Set(
      Array.from(nodeDegrees.entries())
        .filter(([_, deg]) => deg >= HUB_DEGREE_THRESHOLD)
        .map(([id]) => id)
    );
  }, [nodeDegrees]);

  const collapsedLeaves = useMemo(() => {
    const leaves = new Set<string>();
    trace.nodes.forEach(n => {
      const degree = nodeDegrees.get(n.id) || 0;
      if (degree === 1 && !hubs.has(n.id)) {
        const edge = trace.edges.find(e => e.from === n.id || e.to === n.id);
        if (edge) {
          const neighborId = edge.from === n.id ? edge.to : edge.from;
          if (hubs.has(neighborId)) {
            leaves.add(n.id);
          }
        }
      }
    });
    return leaves;
  }, [trace.nodes, trace.edges, nodeDegrees, hubs]);

  // Filter nodes according to hopFilter, verdictFilter, and expand/collapse state
  const structureVisibleIds = useMemo(() => {
    const visible = new Set<string>();
    
    trace.nodes.forEach(n => {
      if (n.hop <= 1 && n.hop <= hopFilter && !collapsedLeaves.has(n.id)) {
        visible.add(n.id);
      }
    });

    let added = true;
    while (added) {
      added = false;
      for (const edge of trace.edges) {
        if (visible.has(edge.from) && expandedNodes.has(edge.from)) {
          const toNode = trace.nodes.find(n => n.id === edge.to);
          if (toNode && !visible.has(toNode.id) && toNode.hop <= hopFilter && !collapsedLeaves.has(toNode.id)) {
            visible.add(toNode.id);
            added = true;
          }
        }
      }
    }
    return visible;
  }, [trace.nodes, trace.edges, expandedNodes, hopFilter, collapsedLeaves]);

  const stubs = useMemo(() => {
    const stubList: any[] = [];
    trace.nodes.forEach(n => {
      if (structureVisibleIds.has(n.id) && !expandedNodes.has(n.id)) {
        let hiddenCount = 0;
        trace.edges.forEach(e => {
          if (e.from === n.id) {
            const child = trace.nodes.find(c => c.id === e.to);
            if (child && child.hop <= hopFilter && !collapsedLeaves.has(child.id) && !structureVisibleIds.has(child.id)) {
              hiddenCount++;
            }
          }
        });
        
        if (hiddenCount > 0) {
          stubList.push({
            id: `stub-${n.id}`,
            parentId: n.id,
            hop: n.hop + 1,
            count: hiddenCount,
            label: `+${hiddenCount} more`,
            isStub: true,
            verdict: 'none'
          });
        }
      }
    });
    return stubList;
  }, [trace.nodes, trace.edges, structureVisibleIds, expandedNodes, hopFilter, collapsedLeaves]);

  const filteredNodes = useMemo(() => {
    const nodes: any[] = trace.nodes.filter(node => {
      if (!structureVisibleIds.has(node.id)) return false;
      if (verdictFilter === 'confirmed' && node.verdict !== 'confirmed') return false;
      if (verdictFilter === 'watch' && node.verdict !== 'watch') return false;
      return true;
    });

    stubs.forEach(stub => {
      if (nodes.find(n => n.id === stub.parentId)) {
        nodes.push(stub);
      }
    });

    return nodes;
  }, [trace.nodes, structureVisibleIds, stubs, verdictFilter]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map(n => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    const edges: any[] = trace.edges.filter(edge => {
      return filteredNodeIds.has(edge.from) && filteredNodeIds.has(edge.to);
    });

    filteredNodes.forEach(node => {
      if ('isStub' in node) {
        edges.push({
          id: `edge-${node.parentId}-${node.id}`,
          from: node.parentId,
          to: node.id,
          amountBtc: 0,
          hop: node.hop,
          isPeelChain: false,
          isFanOut: false,
          isMixerHop: false,
          isStubEdge: true
        } as any);
      }
    });

    return edges;
  }, [trace.edges, filteredNodeIds, filteredNodes]);

  const activeNodeId = hoveredNodeId || selectedNode?.id;

  const highlightedEdgeIds = useMemo(() => {
    if (!activeNodeId) return null;
    const ids = new Set<string>();
    
    // Backward traversal
    const queueB = [activeNodeId];
    const visitedB = new Set<string>();
    while (queueB.length > 0) {
      const curr = queueB.shift()!;
      if (visitedB.has(curr)) continue;
      visitedB.add(curr);
      for (const e of filteredEdges) {
        if (e.to === curr) {
          ids.add(e.id);
          queueB.push(e.from);
        }
      }
    }

    // Forward traversal
    const queueF = [activeNodeId];
    const visitedF = new Set<string>();
    while (queueF.length > 0) {
      const curr = queueF.shift()!;
      if (visitedF.has(curr)) continue;
      visitedF.add(curr);
      for (const e of filteredEdges) {
        if (e.from === curr) {
          ids.add(e.id);
          queueF.push(e.to);
        }
      }
    }
    return ids;
  }, [activeNodeId, filteredEdges]);

  // Verdict lookup for edges
  const nodeVerdictById = useMemo(
    () => new Map(filteredNodes.map(n => [n.id, n.verdict || 'none'])),
    [filteredNodes]
  );

  // Stats strip: nodes hidden by the verdict dropdown only
  const verdictHiddenCount = useMemo(() => {
    if (verdictFilter === 'all') return 0;
    return trace.nodes.filter(n => n.hop <= hopFilter && n.verdict !== verdictFilter).length;
  }, [trace.nodes, hopFilter, verdictFilter]);

  // Layout node positions dynamically if needed or use defined x,y
  const nodePositions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();

    // Group nodes by hop
    const byHop: Record<number, WalletNode[]> = {};
    filteredNodes.forEach(node => {
      if (!byHop[node.hop]) byHop[node.hop] = [];
      byHop[node.hop].push(node);
    });

    Object.entries(byHop).forEach(([hopStr, nodeList]) => {
      const hop = Number(hopStr);
      const count = nodeList.length;
      const verticalSpacing = 90;

      nodeList.forEach((node, index) => {
        // Formal left-to-right layout based on hop
        const x = 100 + hop * 200;
        const y = 220 + (index - (count - 1) / 2) * verticalSpacing;
        map.set(node.id, { x, y });
      });
    });

    // DEBUG: Log node positions
    console.log('[nodePositions] filteredNodes:', filteredNodes.map(n => ({ id: n.id, hop: n.hop, x: n.x, y: n.y })));
    console.log('[nodePositions] byHop:', Object.fromEntries(Object.entries(byHop).map(([k, v]) => [k, v.map(n => n.id)])));
    console.log('[nodePositions] map:', Array.from(map.entries()));

    return map;
  }, [filteredNodes]);

  // Compute the bounding box of all rendered nodes from nodePositions
  const computeGraphBounds = useMemo(() => {
    if (nodePositions.size === 0) {
      return { minX: 0, maxX: VIEWBOX_WIDTH, minY: 0, maxY: VIEWBOX_HEIGHT };
    }
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodePositions.forEach(({ x, y }) => {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    });
    // Account for node radius (max 24 for root) + label box (extends ~65px left, 130px wide, ~40px below)
    const NODE_RADIUS_MAX = 24;
    const LABEL_HALF_WIDTH = 65;
    const LABEL_BOTTOM = 24 + 12 + 28; // radius + gap + label box height
    minX -= NODE_RADIUS_MAX + LABEL_HALF_WIDTH;
    maxX += NODE_RADIUS_MAX + LABEL_HALF_WIDTH;
    minY -= NODE_RADIUS_MAX;
    maxY += LABEL_BOTTOM;

    // DEBUG: Log node positions and bounds
    console.log('[computeGraphBounds] nodePositions size:', nodePositions.size);
    const positions = Array.from(nodePositions.values());
    console.log('[computeGraphBounds] all positions:', positions);
    console.log('[computeGraphBounds] raw bounds:', { minX: minX + NODE_RADIUS_MAX + LABEL_HALF_WIDTH, maxX: maxX - NODE_RADIUS_MAX - LABEL_HALF_WIDTH, minY: minY + NODE_RADIUS_MAX, maxY: maxY - LABEL_BOTTOM });
    console.log('[computeGraphBounds] final bounds:', { minX, maxX, minY, maxY });

    return { minX, maxX, minY, maxY };
  }, [nodePositions]);

  // Fit the graph to the viewport: calculate zoom/pan to show all nodes with padding
  const fitToView = useCallback(() => {
    const { minX, maxX, minY, maxY } = computeGraphBounds;
    const graphWidth = maxX - minX;
    const graphHeight = maxY - minY;

    if (graphWidth <= 0 || graphHeight <= 0) {
      setZoom(1);
      setPan({ x: 0, y: 0 });
      return;
    }

    // Available space in viewBox units (with padding)
    const availWidth = VIEWBOX_WIDTH - 2 * FIT_PADDING;
    const availHeight = VIEWBOX_HEIGHT - 2 * FIT_PADDING;

    // Scale to fit both dimensions, preserving aspect ratio
    const scaleX = availWidth / graphWidth;
    const scaleY = availHeight / graphHeight;
    let newZoom = Math.min(scaleX, scaleY);

    // Clamp to allowed zoom range
    newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, newZoom));

    // Center the graph in the viewport
    // With transformOrigin='center center', the pan must be calculated as:
    // pan = (viewCenter - graphCenter) * zoom
    // This positions the graph center at the container center when scaled.
    const graphCenterX = (minX + maxX) / 2;
    const graphCenterY = (minY + maxY) / 2;
    const viewCenterX = VIEWBOX_WIDTH / 2;
    const viewCenterY = VIEWBOX_HEIGHT / 2;

    const newPan = {
      x: (viewCenterX - graphCenterX) * newZoom,
      y: (viewCenterY - graphCenterY) * newZoom,
    };

    // DEBUG: Log the computed values
    console.log('[fitToView] bounds:', { minX, maxX, minY, maxY, graphWidth, graphHeight });
    console.log('[fitToView] scales:', { scaleX, scaleY, newZoom, ZOOM_MIN, ZOOM_MAX });
    console.log('[fitToView] centers:', { graphCenterX, graphCenterY, viewCenterX, viewCenterY });
    console.log('[fitToView] pan:', newPan);

    setZoom(newZoom);
    setPan(newPan);
  }, [computeGraphBounds]);

  // Minimap viewBox and coordinate mapping based on hierarchical layout bounds
  const minimapBounds = useMemo(() => {
    if (filteredNodes.length <= MINIMAP_NODE_THRESHOLD) return null;
    const { minX, maxX, minY, maxY } = computeGraphBounds;
    const padding = 50;
    const rawW = Math.max(maxX - minX + 2 * padding, 100);
    const rawH = Math.max(maxY - minY + 2 * padding, 50);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const targetAspect = MINIMAP_WIDTH / MINIMAP_HEIGHT;
    let w = rawW;
    let h = rawH;

    if (rawW / rawH > targetAspect) {
      h = rawW / targetAspect;
    } else {
      w = rawH * targetAspect;
    }

    return {
      x: centerX - w / 2,
      y: centerY - h / 2,
      w,
      h,
    };
  }, [filteredNodes.length, computeGraphBounds]);

  // Viewport position in graph coordinates for the minimap indicator
  const viewportRect = useMemo(() => {
    if (!minimapBounds) return null;
    const vpW = VIEWBOX_WIDTH / zoom;
    const vpH = VIEWBOX_HEIGHT / zoom;
    const vpX = (VIEWBOX_WIDTH / 2) - ((VIEWBOX_WIDTH / 2) + pan.x) / zoom;
    const vpY = (VIEWBOX_HEIGHT / 2) - ((VIEWBOX_HEIGHT / 2) + pan.y) / zoom;
    return { x: vpX, y: vpY, width: vpW, height: vpH };
  }, [minimapBounds, zoom, pan]);

  const handleMinimapClick = (e: React.MouseEvent<SVGSVGElement>) => {
    e.stopPropagation();
    if (!minimapBounds) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    // Map screen click to graph coordinates
    const targetGraphX = minimapBounds.x + (clickX / rect.width) * minimapBounds.w;
    const targetGraphY = minimapBounds.y + (clickY / rect.height) * minimapBounds.h;

    // Center target point in main view
    const viewCenterX = VIEWBOX_WIDTH / 2;
    const viewCenterY = VIEWBOX_HEIGHT / 2;
    setPan({
      x: (viewCenterX - targetGraphX) * zoom,
      y: (viewCenterY - targetGraphY) * zoom,
    });
  };

  // Auto-fit on initial load and when filtered nodes change significantly
  useEffect(() => {
    // Small delay to ensure SVG is rendered and refs are ready
    const timer = setTimeout(fitToView, 0);
    return () => clearTimeout(timer);
  }, [fitToView, filteredNodes.length]);

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
    fitToView();
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
          {/* Always-visible stats strip — rendered vs total, verdict-hidden count,
              and the R9 live-fetch truncation indicator when the trace response
              actually carries `capped` (absent on indexed/demo traces: nothing is
              truncated there, so nothing is displayed or invented). */}
          <span className="flex items-center gap-2 text-[11px] font-mono text-zinc-500">
            <span title={`Rendered: ${filteredNodes.filter(n => !('isStub' in n)).length} · Total in trace: ${trace.nodes.length}`}>
              rendered {filteredNodes.filter(n => !('isStub' in n)).length}/{trace.nodes.length}
            </span>
            <span aria-label="Nodes hidden by the verdict filter">
              verdict-hidden {verdictHiddenCount}
            </span>
            {trace.fetchCapped === true && (
              <span
                className="text-amber-400 font-semibold"
                title="Live lookup hit its bounded fetch caps (LIVE_MAX_COUNTERPARTY_FETCHES / LIVE_MAX_TXS_PER_ADDRESS) — this subgraph is a bounded window of the chain, not the full history."
              >
                ⚠ live fetch capped
              </span>
            )}
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
              onClick={() => setZoom(z => Math.min(z + 0.15, ZOOM_MAX))}
              className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoom(z => Math.max(z - 0.15, ZOOM_MIN))}
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

            // Log-scaled stroke width by BTC amount (see EDGE_WIDTH_* constants).
            const amountEdgeWidth = EDGE_WIDTH_BASE + Math.log(edge.amountBtc + 1) * EDGE_WIDTH_LOG_FACTOR;
            const edgeWidth = isSelected ? amountEdgeWidth + 1.5 : amountEdgeWidth;

            // Path highlighting opacity
            const isHighlighted = highlightedEdgeIds ? highlightedEdgeIds.has(edge.id) : false;
            const edgeOpacity = highlightedEdgeIds ? (isHighlighted ? 1 : 0.2) : 0.35;

            const midX = (start.x + end.x) / 2;
            const midY = (start.y + end.y) / 2;

            if (edge.isStubEdge) {
              return (
                <g key={edge.id} className="transition-all" opacity={edgeOpacity}>
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#52525b"
                    strokeWidth={EDGE_WIDTH_BASE}
                    markerEnd="url(#arrow)"
                  />
                </g>
              );
            }

            return (
              <g key={edge.id} className="transition-all" opacity={edgeOpacity}>
                {/* Background thicker hit path */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={edgeWidth}
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

            const isHighlightedNode = activeNodeId 
              ? (node.id === activeNodeId || filteredEdges.some(e => (e.from === node.id || e.to === node.id) && highlightedEdgeIds?.has(e.id)))
              : false;
            const nodeOpacity = activeNodeId ? (isHighlightedNode ? 1 : 0.3) : 1;

            if ('isStub' in node) {
              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setExpandedNodes(prev => new Set(prev).add(node.parentId));
                  }}
                  className="cursor-pointer group"
                  opacity={nodeOpacity}
                >
                  <circle
                    r={16}
                    fill="#16161c"
                    stroke="#52525b"
                    strokeWidth="1.5"
                    strokeDasharray="3 2"
                    className="transition-transform group-hover:scale-110"
                  />
                  <text
                    textAnchor="middle"
                    dy="3"
                    fontSize="10"
                    fontWeight="bold"
                    fill="#a1a1aa"
                  >
                    +{node.count}
                  </text>
                </g>
              );
            }

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

            // Verdict color consistency: root/mixer/exchange bodies keep their
            // legend type-colors as the FILL, but a confirmed/watch verdict
            // always overrides the STROKE — no node type bypasses the verdict
            // encoding (the verdict badge carries the same color on every node).
            if (isConfirmed) {
              nodeStroke = '#fb7185';
            } else if (isWatch) {
              nodeStroke = '#fbbf24';
            }

            const radius = isRoot ? 24 : isExchange ? 22 : 18;
            
            const isHub = hubs.has(node.id);
            const degree = nodeDegrees.get(node.id) || 0;

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => {
                  onSelectNode(node);
                  setExpandedNodes(prev => {
                    const next = new Set(prev);
                    if (next.has(node.id)) next.delete(node.id);
                    else next.add(node.id);
                    return next;
                  });
                }}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                className="cursor-pointer group"
                filter={isSelected ? 'url(#glow-selected)' : isConfirmed ? 'url(#glow-confirmed)' : undefined}
                opacity={nodeOpacity}
              >
                {isHub ? (
                  <>
                    <rect
                      x="-40"
                      y="-18"
                      width="80"
                      height="36"
                      rx="8"
                      fill={nodeFill}
                      stroke={isSelected ? '#818cf8' : nodeStroke}
                      strokeWidth={isSelected ? 3 : 2}
                      strokeDasharray={isLiveLookupTrace ? '5 3' : undefined}
                      className="transition-transform group-hover:scale-105"
                    />
                    <text
                      textAnchor="middle"
                      dy="4"
                      fontSize="11"
                      fontWeight="bold"
                      fill={nodeStroke}
                    >
                      HUB
                    </text>
                    <g transform="translate(40, -18)">
                      <circle r="10" fill="#3f3f46" stroke={nodeStroke} strokeWidth="1" />
                      <text textAnchor="middle" dy="3" fontSize="8" fill="#fff" fontWeight="bold">
                        {degree}
                      </text>
                    </g>
                  </>
                ) : (
                  <>
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

                    {/* Base Node Circle — dashed border on live-lookup traces,
                        solid on elliptic-indexed (see isLiveLookupTrace) */}
                    <circle
                      r={radius}
                      fill={nodeFill}
                      stroke={isSelected ? '#818cf8' : nodeStroke}
                      strokeWidth={isSelected ? 3 : 2}
                      strokeDasharray={isLiveLookupTrace ? '5 3' : undefined}
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
                  </>
                )}

                {/* Label Box below Node */}
                <g transform={`translate(0, ${isHub ? 30 : radius + 12})`}>
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

        {/* Overview Minimap (>30 nodes) */}
        {minimapBounds && viewportRect && (
          <div
            className="absolute bottom-3 right-3 z-10 bg-[#121217]/95 backdrop-blur-md p-2 rounded-xl border border-zinc-800/80 shadow-xl shadow-black/50 flex flex-col gap-1.5 select-none"
            onMouseDown={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 px-0.5 text-[10px] font-mono text-zinc-400">
              <span className="flex items-center gap-1 font-semibold text-zinc-300">
                <Eye className="w-3 h-3 text-indigo-400" />
                Minimap
              </span>
              <span className="text-[9px] text-zinc-500">
                {filteredNodes.length} nodes
              </span>
            </div>
            <div className="relative rounded-lg overflow-hidden border border-zinc-800/60 bg-[#08080c]">
              <svg
                width={MINIMAP_WIDTH}
                height={MINIMAP_HEIGHT}
                viewBox={`${minimapBounds.x} ${minimapBounds.y} ${minimapBounds.w} ${minimapBounds.h}`}
                className="cursor-pointer block"
                onClick={handleMinimapClick}
                title="Click to center viewport"
              >
                {/* Minimap simplified edges */}
                {filteredEdges.map(edge => {
                  const start = nodePositions.get(edge.from);
                  const end = nodePositions.get(edge.to);
                  if (!start || !end) return null;
                  return (
                    <line
                      key={`mini-e-${edge.id}`}
                      x1={start.x}
                      y1={start.y}
                      x2={end.x}
                      y2={end.y}
                      stroke="#27272a"
                      strokeWidth={minimapBounds.w * 0.0035}
                      strokeOpacity="0.65"
                    />
                  );
                })}

                {/* Minimap simplified nodes */}
                {filteredNodes.map(node => {
                  const pos = nodePositions.get(node.id);
                  if (!pos) return null;
                  const isConfirmed = node.verdict === 'confirmed';
                  const isWatch = node.verdict === 'watch';
                  const isRoot = node.type === 'suspect_root';
                  const isMixer = node.type === 'mixer_service';
                  const isExchange = node.type === 'exchange_deposit' || node.type === 'exchange_hot_wallet';
                  const isSelected = selectedNode?.id === node.id;

                  let fill = '#34d399';
                  if (isConfirmed || isRoot) fill = '#f43f5e';
                  else if (isMixer) fill = '#c084fc';
                  else if (isExchange) fill = '#60a5fa';
                  else if (isWatch) fill = '#fbbf24';

                  const baseRadius = Math.max(3.5, minimapBounds.w * 0.012);
                  const r = isRoot || isSelected ? baseRadius * 1.4 : baseRadius;

                  return (
                    <circle
                      key={`mini-n-${node.id}`}
                      cx={pos.x}
                      cy={pos.y}
                      r={r}
                      fill={isSelected ? '#818cf8' : fill}
                      stroke={isSelected ? '#ffffff' : '#0e0e12'}
                      strokeWidth={Math.max(0.6, minimapBounds.w * 0.002)}
                    />
                  );
                })}

                {/* Viewport Indicator Rectangle */}
                <rect
                  x={viewportRect.x}
                  y={viewportRect.y}
                  width={viewportRect.width}
                  height={viewportRect.height}
                  fill="rgba(99, 102, 241, 0.18)"
                  stroke="#818cf8"
                  strokeWidth={Math.max(1.2, minimapBounds.w * 0.005)}
                  rx={Math.max(1, minimapBounds.w * 0.004)}
                  pointerEvents="none"
                />
              </svg>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
