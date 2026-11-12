import React, { useState } from 'react';
import { Layers, ChevronDown, ChevronUp, Database, ArrowRight, ShieldCheck, Share2, Info, Network } from 'lucide-react';

export default function EvidencePanel({ evidenceBundle, onSelectEntity }) {
  const entities = evidenceBundle?.ranked_entities || [];
  const triplets = evidenceBundle?.triplets || [];
  
  // Track expanded card node_id (accordion toggle)
  const [expandedId, setExpandedId] = useState(null);

  const toggleExpand = (nodeId, ent) => {
    setExpandedId((prev) => (prev === nodeId ? null : nodeId));
    if (onSelectEntity) {
      onSelectEntity(ent);
    }
  };

  return (
    <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <div className="panel-title">
          <Layers size={20} style={{ color: 'var(--accent-indigo)' }} />
          <span>Stage 4 Fused Evidence Candidates</span>
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          {entities.length} Primary Ranked Nodes
        </span>
      </div>

      <div className="evidence-list">
        {entities.length === 0 ? (
          <div className="empty-state" style={{ padding: '3rem 1rem' }}>
            <Database size={32} className="empty-icon" />
            <p>Run a query to retrieve hybrid evidence candidates</p>
          </div>
        ) : (
          entities.map((ent, idx) => {
            const isExpanded = expandedId === ent.node_id;
            const isHybrid = ent.provenance === 'HYBRID_BOTH';
            const isGnn = ent.provenance === 'GNN_STRUCTURAL';
            const provClass = isHybrid ? 'prov-hybrid' : (isGnn ? 'prov-gnn' : 'prov-text');
            const provLabel = isHybrid ? 'Both (Boosted 1.5x)' : (isGnn ? 'GNN Vector' : 'Text BM25');

            // Find all relation triplets in the subgraph related to this entity
            const nodeTriplets = triplets.filter(
              (trip) =>
                trip.subject_id === ent.node_id ||
                trip.object_id === ent.node_id ||
                trip.subject === ent.name ||
                trip.object === ent.name
            );

            return (
              <div
                key={ent.node_id || idx}
                className={`evidence-card ${isExpanded ? 'is-expanded' : ''}`}
                onClick={() => toggleExpand(ent.node_id, ent)}
                style={{ cursor: 'pointer' }}
              >
                {/* Header Row */}
                <div className="card-top">
                  <div className="entity-name">
                    <span>{ent.name}</span>
                    {ent.attack_id && (
                      <span className="attack-id-chip">
                        [{ent.attack_id}]
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span className={`prov-pill ${provClass}`}>{provLabel}</span>
                    <span className="score-badge">{ent.composite_score}</span>
                    <button
                      type="button"
                      className="dropdown-toggle-btn"
                      aria-label="Toggle details"
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                  </div>
                </div>

                {/* Truncated snippet when collapsed */}
                {!isExpanded && (
                  <p className="card-desc">
                    {ent.description
                      ? ent.description.length > 130
                        ? ent.description.substring(0, 130) + '...'
                        : ent.description
                      : 'Click to expand full entity attributes & connected graph relations.'}
                  </p>
                )}

                {/* Full Information Dropdown Panel */}
                {isExpanded && (
                  <div className="evidence-dropdown animate-fade-in" onClick={(e) => e.stopPropagation()}>
                    {/* Full Description */}
                    <div className="dropdown-section">
                      <div className="dropdown-section-header">
                        <Info size={14} style={{ color: 'var(--accent-cyan)' }} />
                        <span>Full Intelligence Description</span>
                      </div>
                      <p className="evidence-full-desc">
                        {ent.description || 'No extended description available for this entity in the source taxonomies.'}
                      </p>
                    </div>

                    {/* Metadata Attributes Grid */}
                    <div className="dropdown-section">
                      <div className="dropdown-section-header">
                        <ShieldCheck size={14} style={{ color: 'var(--accent-emerald)' }} />
                        <span>Entity Attributes & Calibration Weights</span>
                      </div>
                      <div className="evidence-meta-grid">
                        <div className="meta-box">
                          <span className="meta-box-label">Category / Label</span>
                          <span className="meta-box-val" style={{ color: 'var(--accent-cyan)' }}>
                            {ent.label || 'Entity'}
                          </span>
                        </div>
                        <div className="meta-box">
                          <span className="meta-box-label">External / MITRE ID</span>
                          <span className="meta-box-val">{ent.attack_id || 'N/A'}</span>
                        </div>
                        <div className="meta-box">
                          <span className="meta-box-label">Retrieval Channel</span>
                          <span className="meta-box-val" style={{ fontSize: '0.75rem' }}>
                            {isHybrid
                              ? 'Hybrid (Text BM25 + GNN)'
                              : isGnn
                              ? 'GNN Graph Embedding'
                              : 'Text BM25 / TF-IDF'}
                          </span>
                        </div>
                        <div className="meta-box">
                          <span className="meta-box-label">Composite Score</span>
                          <span className="meta-box-val" style={{ color: 'var(--accent-emerald)' }}>
                            {ent.composite_score}
                          </span>
                        </div>
                        <div className="meta-box">
                          <span className="meta-box-label">Base RRF Score</span>
                          <span className="meta-box-val">{ent.base_rrf_score || 'N/A'}</span>
                        </div>
                        <div className="meta-box">
                          <span className="meta-box-label">Consensus Multiplier</span>
                          <span className="meta-box-val">{ent.consensus_multiplier ? `${ent.consensus_multiplier}x` : '1.0x'}</span>
                        </div>
                        <div className="meta-box">
                          <span className="meta-box-label">Source Reliability</span>
                          <span className="meta-box-val">{ent.source_weight ?? 1.0}</span>
                        </div>
                        <div className="meta-box">
                          <span className="meta-box-label">Graph Node ID</span>
                          <span className="meta-box-val" style={{ fontSize: '0.68rem', wordBreak: 'break-all' }}>
                            {ent.node_id}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Connected Graph Triplets */}
                    <div className="dropdown-section">
                      <div className="dropdown-section-header">
                        <Network size={14} style={{ color: 'var(--accent-indigo)' }} />
                        <span>
                          Connected Sub-Graph Relations ({nodeTriplets.length})
                        </span>
                      </div>
                      {nodeTriplets.length === 0 ? (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                          No immediate 1-hop relation triplets surfaced in the current top-k evidence subgraph.
                        </p>
                      ) : (
                        <div className="triplets-list">
                          {nodeTriplets.slice(0, 8).map((trip, tIdx) => {
                            const isOutgoing =
                              trip.subject === ent.name || trip.subject_id === ent.node_id;
                            return (
                              <div key={tIdx} className="triplet-item">
                                <span className={`triplet-badge ${isOutgoing ? 'badge-out' : 'badge-in'}`}>
                                  {isOutgoing ? 'Outgoing' : 'Incoming'}
                                </span>
                                <span className="triplet-entity">{trip.subject}</span>
                                <span className="triplet-arrow">
                                  ─[:{trip.relation}]─▶
                                </span>
                                <span className="triplet-entity">{trip.object}</span>
                              </div>
                            );
                          })}
                          {nodeTriplets.length > 8 && (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              + {nodeTriplets.length - 8} more connected relations in subgraph
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
