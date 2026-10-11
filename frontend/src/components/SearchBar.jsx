import React from 'react';
import { Search, Sparkles, Cpu } from 'lucide-react';

export default function SearchBar({ query, setQuery, onSearch, loading, samples, selfTest, setSelfTest }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query);
    }
  };

  return (
    <section className="search-section glass-card">
      <form onSubmit={handleSubmit} className="search-bar-wrapper">
        <div className="search-input-container">
          <Search size={20} className="search-input-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Ask analyst query (e.g. 'APT29 credential access and phishing', 'MOVEit Transfer SQL injection')..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <button type="submit" className="btn-primary" disabled={loading || !query.trim()}>
          {loading ? (
            <>
              <div className="loading-spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
              <span>Reasoning...</span>
            </>
          ) : (
            <>
              <Sparkles size={18} />
              <span>Run RAG</span>
            </>
          )}
        </button>
      </form>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="preset-chips">
          <span className="preset-label">Presets:</span>
          {samples.map((s, idx) => (
            <button
              key={idx}
              className="chip-btn"
              onClick={() => {
                setQuery(s.query);
                onSearch(s.query);
              }}
            >
              {s.title}
            </button>
          ))}
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={selfTest}
            onChange={(e) => setSelfTest(e.target.checked)}
            style={{ accentColor: 'var(--accent-cyan)' }}
          />
          <span>Offline Mock Mode</span>
        </label>
      </div>
    </section>
  );
}
