import React from 'react';
import { Layers, CheckCircle2, Zap, Database } from 'lucide-react';

export default function EvidencePanel({ evidenceBundle, onSelectEntity }) {
  const entities = evidenceBundle?.ranked_entities || [];

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
            const isHybrid = ent.provenance === 'HYBRID_BOTH';
            const isGnn = ent.provenance === 'GNN_STRUCTURAL';
            const provClass = isHybrid ? 'prov-hybrid' : (isGnn ? 'prov-gnn' : 'prov-text');
            const provLabel = isHybrid ? 'Both (Boosted 1.5x)' : (isGnn ? 'GNN Vector' : 'Text BM25');

            return (
              <div
                key={idx}
                className="evidence-card"
                onClick={() => onSelectEntity && onSelectEntity(ent)}
                style={{ cursor: 'pointer' }}
              >
                <div className="card-top">
                  <div className="entity-name">
                    <span>{ent.name}</span>
                    {ent.attack_id && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        [{ent.attack_id}]
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className={`prov-pill ${provClass}`}>{provLabel}</span>
                    <span className="score-badge">{ent.composite_score}</span>
                  </div>
                </div>

                <p className="card-desc">
                  {ent.description ? (ent.description.length > 140 ? ent.description.substring(0, 140) + '...' : ent.description) : 'No description snippet available.'}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
