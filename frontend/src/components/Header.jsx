import React from 'react';
import { Shield, Sun, Moon } from 'lucide-react';

export default function Header({ stats, theme, onToggleTheme }) {
  const isLight = theme === 'light';

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

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <button
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          type="button"
          aria-label={`Switch to ${isLight ? 'Dark' : 'Light'} Mode`}
        >
          {isLight ? (
            <>
              <Moon size={16} style={{ color: '#4F46E5' }} />
              <span>Dark Mode</span>
            </>
          ) : (
            <>
              <Sun size={16} style={{ color: '#FBBF24' }} />
              <span>Light Mode</span>
            </>
          )}
        </button>

        <div className="status-badge">
          <span className="pulse-dot"></span>
          <span>Groq LLM Engine: {stats?.model_name || 'openai/gpt-oss-120b'}</span>
        </div>
      </div>
    </header>
  );
}
