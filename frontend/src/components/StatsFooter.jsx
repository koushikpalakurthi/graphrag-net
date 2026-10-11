import React from 'react';
import { Database, GitCommit, Box, Cpu } from 'lucide-react';

export default function StatsFooter({ stats }) {
  return (
    <footer className="stats-footer glass-card">
      <div className="stats-group">
        <div className="stat-item">
          <Database size={15} style={{ color: 'var(--accent-cyan)' }} />
          <span>Graph Nodes:</span>
          <span className="stat-val">{stats?.nodes_count?.toLocaleString() || '6,012'}</span>
        </div>
        <div className="stat-item">
          <GitCommit size={15} style={{ color: 'var(--accent-indigo)' }} />
          <span>Graph Edges:</span>
          <span className="stat-val">{stats?.edges_count?.toLocaleString() || '27,351'}</span>
        </div>
        <div className="stat-item">
          <Box size={15} style={{ color: 'var(--accent-emerald)' }} />
          <span>GNN Vector Embeddings:</span>
          <span className="stat-val">{stats?.gnn_embeddings_count?.toLocaleString() || '5,904'}</span>
        </div>
      </div>

      <div className="stat-item">
        <Cpu size={15} style={{ color: 'var(--accent-purple)' }} />
        <span>GraphRAG-Net Architecture v1.0.0</span>
      </div>
    </footer>
  );
}
