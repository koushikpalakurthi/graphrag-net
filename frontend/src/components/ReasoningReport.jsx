import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Cpu, FileText, CheckCircle, ShieldAlert, BarChart3, Info } from 'lucide-react';

export default function ReasoningReport({ result, loading }) {
  if (loading) {
    return (
      <div className="glass-card panel-container" style={{ padding: '4rem 2rem', gridColumn: '1 / -1' }}>
        <div className="empty-state">
          <div className="loading-spinner" style={{ width: 42, height: 42, borderWidth: 3 }} />
          <h3 style={{ color: 'var(--text-primary)', marginTop: '1rem' }}>Executing Stage 5 & 6 RAG Reasoning & Confidence Calibration</h3>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            Retrieving hybrid embeddings $\rightarrow$ Ranking graph triplets $\rightarrow$ Prompting Groq LLM $\rightarrow$ Computing Platt-Calibrated P(correct)...
          </p>
        </div>
      </div>
    );
  }

  if (!result || !result.reasoning_output) {
    return (
      <div className="glass-card panel-container" style={{ gridColumn: '1 / -1' }}>
        <div className="panel-header">
          <div className="panel-title">
            <FileText size={20} style={{ color: 'var(--accent-cyan)' }} />
            <span>AI CTI Attack Chain & Mitigation Report</span>
          </div>
        </div>
        <div className="empty-state">
          <FileText size={36} className="empty-icon" />
          <p>Submit an analyst query to generate attack chain reconstruction, mitigations, and calibrated confidence sub-scores</p>
        </div>
      </div>
    );
  }

  const s6 = result.stage6_output;
  const isTrained = s6?.calibration_status === 'trained_model';
  const labelColor = s6?.confidence_label === 'High' ? 'var(--accent-emerald)' : (s6?.confidence_label === 'Medium' ? 'var(--accent-amber)' : 'var(--accent-rose)');

  return (
    <div className="glass-card animate-fade-in" style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Top Header */}
      <div className="panel-header">
        <div className="panel-title">
          <Cpu size={20} style={{ color: 'var(--accent-cyan)' }} />
          <span>Stage 5 & 6 CTI Reasoning & Confidence Assessment</span>
          <span style={{ fontSize: '0.78rem', background: 'rgba(56,189,248,0.1)', color: 'var(--accent-cyan)', padding: '0.2rem 0.6rem', borderRadius: 12 }}>
            Model: {result.model}
          </span>
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <CheckCircle size={14} style={{ color: 'var(--accent-emerald)' }} /> Grounded in Knowledge Graph Evidence
        </div>
      </div>

      {/* Stage 6 Confidence Scoring Banner */}
      {s6 && (
        <div style={{
          margin: '0 1.5rem',
          padding: '1.25rem',
          background: 'rgba(15, 23, 42, 0.75)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div style={{
                fontSize: '1.8rem',
                fontWeight: 700,
                color: labelColor,
                fontFamily: 'var(--font-mono)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <BarChart3 size={24} />
                <span>{(s6.overall_confidence * 100).toFixed(0)}%</span>
              </div>
              <div>
                <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>P(Correctness): {s6.confidence_label} Confidence</span>
                  <span style={{
                    fontSize: '0.7rem',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '10px',
                    background: isTrained ? 'rgba(52, 211, 153, 0.15)' : 'rgba(251, 191, 36, 0.15)',
                    color: isTrained ? 'var(--accent-emerald)' : 'var(--accent-amber)',
                    border: `1px solid ${isTrained ? 'rgba(52, 211, 153, 0.3)' : 'rgba(251, 191, 36, 0.3)'}`
                  }}>
                    {isTrained ? 'Platt-Calibrated' : 'Unvalidated Heuristic'}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {s6.notes}
                </div>
              </div>
            </div>

            {/* Sub-scores breakdown */}
            <div style={{ display: 'flex', gap: '1.5rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Retrieval</span>
                <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                  {(s6.sub_scores.retrieval_strength * 100).toFixed(0)}%
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Agreement</span>
                <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--accent-indigo)', fontFamily: 'var(--font-mono)' }}>
                  {(s6.sub_scores.cross_channel_agreement * 100).toFixed(0)}%
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Consistency</span>
                <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
                  {(s6.sub_scores.llm_consistency * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Report Body */}
      <div className="report-content">
        <ReactMarkdown>{result.reasoning_output}</ReactMarkdown>
      </div>
    </div>
  );
}
