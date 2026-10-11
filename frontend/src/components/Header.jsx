import React from 'react';
import { Shield, Activity } from 'lucide-react';

export default function Header({ stats }) {
  return (
    <header className="app-header glass-card">
      <div className="brand-section">
        <div className="brand-icon">
          <Shield size={24} />
        </div>
        <div>
          <h1 className="brand-title">GraphRAG-Net</h1>
          <p className="brand-subtitle">Hybrid Graph Learning & Multi-Stage CTI RAG System</p>
        </div>
      </div>

      <div className="status-badge">
        <span className="pulse-dot"></span>
        <span>Groq LLM Engine: {stats?.model_name || 'llama-3.3-70b-versatile'}</span>
      </div>
    </header>
  );
}
