import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import SearchBar from './components/SearchBar';
import GraphVisualizer from './components/GraphVisualizer';
import EvidencePanel from './components/EvidencePanel';
import ReasoningReport from './components/ReasoningReport';
import StatsFooter from './components/StatsFooter';
import './App.css';

export default function App() {
  const [stats, setStats] = useState(null);
  const [samples, setSamples] = useState([]);
  const [query, setQuery] = useState('APT29 credential access and phishing techniques');
  const [selfTest, setSelfTest] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

  // Fetch initial stats & sample queries
  useEffect(() => {
    fetch('/api/stats')
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((err) => console.error('Error fetching stats:', err));

    fetch('/api/samples')
      .then((res) => res.json())
      .then((data) => setSamples(data.samples || []))
      .catch((err) => console.error('Error fetching samples:', err));
  }, []);

  const handleSearch = (searchQuery) => {
    setLoading(true);
    setSelectedNode(null);

    fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: searchQuery,
        top_k: 8,
        self_test: selfTest
      })
    })
      .then((res) => {
        if (!res.ok) throw new Error('API search failed');
        return res.json();
      })
      .then((data) => {
        setResult(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Search error:', err);
        setLoading(false);
      });
  };

  return (
    <div className="app-container">
      <Header stats={stats} />

      <SearchBar
        query={query}
        setQuery={setQuery}
        onSearch={handleSearch}
        loading={loading}
        samples={samples}
        selfTest={selfTest}
        setSelfTest={setSelfTest}
      />

      <main className="dashboard-grid">
        <GraphVisualizer
          graphData={result?.graph_data || { nodes: [], edges: [] }}
          onSelectNode={(node) => setSelectedNode(node)}
        />

        <EvidencePanel
          evidenceBundle={result?.evidence_bundle}
          onSelectEntity={(ent) => setSelectedNode(ent)}
        />

        <ReasoningReport result={result} loading={loading} />
      </main>

      <StatsFooter stats={stats} />
    </div>
  );
}
