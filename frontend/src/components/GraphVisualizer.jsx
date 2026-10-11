import React, { useEffect, useRef } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { Network as NetworkIcon } from 'lucide-react';

export default function GraphVisualizer({ graphData, onSelectNode }) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !graphData || !graphData.nodes.length) return;

    // Convert nodes to Vis format
    const visNodes = new DataSet(
      graphData.nodes.map((n) => ({
        id: n.id,
        label: n.label.length > 25 ? n.label.substring(0, 22) + '...' : n.label,
        title: `<b>${n.label}</b> (${n.group})<br/>Provenance: ${n.provenance}<br/>Score: ${n.composite_score}`,
        shape: 'dot',
        size: n.provenance === 'HYBRID_BOTH' ? 22 : (n.composite_score > 0 ? 16 : 10),
        color: {
          background: n.color,
          border: n.provenance === 'HYBRID_BOTH' ? '#38BDF8' : '#1E293B',
          highlight: { background: '#38BDF8', border: '#FFFFFF' }
        },
        borderWidth: n.provenance === 'HYBRID_BOTH' ? 3 : 1,
        font: { color: '#F8FAFC', face: 'Inter', size: 12 }
      }))
    );

    // Convert edges to Vis format
    const visEdges = new DataSet(
      graphData.edges.map((e, idx) => ({
        id: idx,
        from: e.from,
        to: e.to,
        label: e.label,
        arrows: 'to',
        color: { color: e.is_core ? 'rgba(56, 189, 248, 0.6)' : 'rgba(148, 163, 184, 0.25)', highlight: '#38BDF8' },
        width: e.is_core ? 2 : 1,
        font: { color: '#94A3B8', size: 10, align: 'top' }
      }))
    );

    const options = {
      physics: {
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -50,
          centralGravity: 0.01,
          springLength: 100,
          springConstant: 0.08
        },
        maxVelocity: 50,
        timestep: 0.5,
        stabilization: { iterations: 150 }
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        zoomView: true
      }
    };

    networkRef.current = new Network(containerRef.current, { nodes: visNodes, edges: visEdges }, options);

    if (onSelectNode) {
      networkRef.current.on('selectNode', (params) => {
        if (params.nodes.length > 0) {
          const selectedId = params.nodes[0];
          const nodeData = graphData.nodes.find((n) => n.id === selectedId);
          onSelectNode(nodeData);
        }
      });
    }

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
      }
    };
  }, [graphData, onSelectNode]);

  return (
    <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <div className="panel-title">
          <NetworkIcon size={20} style={{ color: 'var(--accent-cyan)' }} />
          <span>Interactive Sub-Graph Topology</span>
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          {graphData?.nodes?.length || 0} Nodes | {graphData?.edges?.length || 0} Relations
        </span>
      </div>

      <div className="graph-container">
        <div ref={containerRef} className="graph-canvas" />
        <div className="graph-overlay-info">
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#F87171' }} /> Tactic / Technique
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#34D399' }} /> Mitigation
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#38BDF8' }} /> Software / Vulnerability
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#A78BFA' }} /> Threat Group
          </div>
        </div>
      </div>
    </div>
  );
}
