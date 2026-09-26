import React, { useState } from 'react';
import FileUpload from './FileUpload';
import SummaryResult from './SummaryResult';
import { summarizeHierarchical } from '../services/api';
import { Layers, Sparkles, Loader2, AlertCircle, ListChecks, ShieldCheck } from 'lucide-react';

export default function HierarchicalSummarizer({ onError }) {
  const [file, setFile] = useState(null);
  const [length, setLength] = useState('medium');
  const [format, setFormat] = useState('paragraph');
  const [executive, setExecutive] = useState(false);
  const [chunkSize, setChunkSize] = useState(2000);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hierarchicalResult, setHierarchicalResult] = useState(null);
  const [showSections, setShowSections] = useState(false);
  const [showFaithfulnessClaims, setShowFaithfulnessClaims] = useState(false);

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    setError(null);
    setHierarchicalResult(null);
  };

  const handleFileRemove = () => {
    setFile(null);
    setError(null);
    setHierarchicalResult(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (!file) {
      setError('Please select a long document (TXT, PDF, or DOCX) to summarize.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setHierarchicalResult(null);

    try {
      const response = await summarizeHierarchical({
        file,
        length,
        format,
        executive,
        chunkSize: Number(chunkSize),
      });

      if (response && response.final_summary) {
        setHierarchicalResult(response);
      } else {
        setError('Received an empty hierarchical summary from the server.');
      }
    } catch (err) {
      setError(err.message || 'An error occurred during hierarchical summarization.');
      if (onError) onError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper">
      <div className="controls-card">
        <div className="section-heading">
          <h2>Hierarchical Document Summarizer (Map-Reduce)</h2>
          <p>
            Designed for long documents, reports, and books. Text is broken into coherent structural chunks, individually summarized, and reduced into a synthesized master summary.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {/* File Upload Area */}
          <div className="form-group">
            <label className="form-label">Upload Long Document</label>
            <FileUpload
              file={file}
              onFileSelect={handleFileSelect}
              onFileRemove={handleFileRemove}
              onError={(msg) => setError(msg)}
              disabled={isLoading}
              accept=".txt,.pdf,.docx"
              helperText="Upload TXT, PDF, or DOCX document (Up to 10 MB)"
            />
          </div>

          {/* Controls Grid */}
          <div className="options-grid">
            {/* Length Selector */}
            <div className="form-group">
              <label className="form-label">Final Summary Length</label>
              <div className="pill-group">
                {[
                  { id: 'short', label: 'Short' },
                  { id: 'medium', label: 'Medium' },
                  { id: 'long', label: 'Long' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`pill-btn ${length === item.id ? 'pill-active' : ''}`}
                    onClick={() => setLength(item.id)}
                    disabled={isLoading}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Format Selector */}
            <div className="form-group">
              <label className="form-label">Output Format</label>
              <div className="pill-group">
                {[
                  { id: 'paragraph', label: 'Paragraph' },
                  { id: 'bullets', label: 'Bullets' },
                  { id: 'table', label: 'Table' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`pill-btn ${format === item.id ? 'pill-active' : ''}`}
                    onClick={() => setFormat(item.id)}
                    disabled={isLoading}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Chunk Size & Executive Summary Controls */}
          <div className="options-grid" style={{ marginTop: '0.75rem' }}>
            <div className="form-group">
              <label className="form-label">
                Chunk Size ({chunkSize} characters per section)
              </label>
              <input
                type="range"
                min={1000}
                max={8000}
                step={500}
                value={chunkSize}
                onChange={(e) => setChunkSize(Number(e.target.value))}
                disabled={isLoading}
                style={{ width: '100%', accentColor: 'var(--accent-blue)', cursor: 'pointer' }}
              />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Smaller chunk = fine-grained section analysis; Larger chunk = broader thematic units.
              </span>
            </div>

            <div className="form-group checkbox-group" style={{ display: 'flex', alignItems: 'center' }}>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={executive}
                  onChange={(e) => setExecutive(e.target.checked)}
                  disabled={isLoading}
                />
                <span className="checkbox-custom"></span>
                <span className="checkbox-text">
                  <strong>Executive Summary</strong> &mdash; Generate high-level strategic overview
                </span>
              </label>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="alert-banner alert-error">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          {/* Submit Action Button */}
          <div className="form-actions">
            <button
              type="submit"
              disabled={isLoading || !file}
              className="btn-primary"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Processing Sections via Map-Reduce...</span>
                </>
              ) : (
                <>
                  <Layers size={18} />
                  <span>Generate Hierarchical Summary</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Result Section */}
      {hierarchicalResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1.5rem' }}>
          <SummaryResult
            summary={hierarchicalResult.final_summary}
            title={`Hierarchical Summary of ${file ? file.name : 'Document'}`}
            metaInfo={`MAP-REDUCE • ${hierarchicalResult.total_sections} SECTIONS${hierarchicalResult.redundant_sections_count > 0 ? ` (${hierarchicalResult.redundant_sections_count} REDUNDANT REMOVED)` : ''} • ${length.toUpperCase()} • ${format.toUpperCase()}`}
          />

          {/* Faithfulness Verification Card */}
          {hierarchicalResult.faithfulness && (
            <div className="controls-card" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '40px',
                    height: '40px',
                    borderRadius: '10px',
                    backgroundColor: hierarchicalResult.faithfulness.status === 'HIGH' ? 'rgba(34, 197, 94, 0.15)' : hierarchicalResult.faithfulness.status === 'MODERATE' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    color: hierarchicalResult.faithfulness.status === 'HIGH' ? '#4ade80' : hierarchicalResult.faithfulness.status === 'MODERATE' ? '#facc15' : '#f87171'
                  }}>
                    <ShieldCheck size={22} />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <h3 style={{ fontSize: '1.1rem', margin: 0 }}>Source Faithfulness Verification</h3>
                      <span style={{
                        fontSize: '0.75rem',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        backgroundColor: hierarchicalResult.faithfulness.status === 'HIGH' ? 'rgba(34, 197, 94, 0.2)' : hierarchicalResult.faithfulness.status === 'MODERATE' ? 'rgba(234, 179, 8, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                        color: hierarchicalResult.faithfulness.status === 'HIGH' ? '#4ade80' : hierarchicalResult.faithfulness.status === 'MODERATE' ? '#facc15' : '#f87171',
                        fontWeight: 700
                      }}>
                        {hierarchicalResult.faithfulness.status} ({Math.round(hierarchicalResult.faithfulness.faithfulness_score * 100)}%)
                      </span>
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Claims checked: {hierarchicalResult.faithfulness.claims_checked} • Supported: {hierarchicalResult.faithfulness.supported_claims} • Unsupported: {hierarchicalResult.faithfulness.unsupported_claims}
                      {hierarchicalResult.faithfulness.partially_supported_claims > 0 && ` • Partial: ${hierarchicalResult.faithfulness.partially_supported_claims}`}
                    </div>
                  </div>
                </div>

                {hierarchicalResult.faithfulness.claims && hierarchicalResult.faithfulness.claims.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowFaithfulnessClaims(!showFaithfulnessClaims)}
                    className="btn-secondary"
                    style={{
                      padding: '0.4rem 0.9rem',
                      fontSize: '0.85rem',
                      background: 'transparent',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer'
                    }}
                  >
                    {showFaithfulnessClaims ? 'Hide Claims' : 'Inspect Claims'}
                  </button>
                )}
              </div>

              {showFaithfulnessClaims && hierarchicalResult.faithfulness.claims && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                  {hierarchicalResult.faithfulness.claims.map((claim, idx) => {
                    const isSupported = claim.status === 'SUPPORTED';
                    const isUnsupported = claim.status === 'UNSUPPORTED';
                    const isPartial = claim.status === 'PARTIALLY_SUPPORTED';
                    const statusColor = isSupported ? '#4ade80' : isUnsupported ? '#f87171' : isPartial ? '#facc15' : '#94a3b8';
                    const statusBg = isSupported ? 'rgba(34, 197, 94, 0.15)' : isUnsupported ? 'rgba(239, 68, 68, 0.15)' : isPartial ? 'rgba(234, 179, 8, 0.15)' : 'rgba(148, 163, 184, 0.15)';

                    return (
                      <div
                        key={idx}
                        style={{
                          padding: '0.85rem 1rem',
                          backgroundColor: 'var(--bg-surface-elevated, #1a2234)',
                          borderRadius: 'var(--radius-md)',
                          border: `1px solid ${isUnsupported ? 'rgba(239, 68, 68, 0.35)' : 'var(--border-color)'}`,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{
                              fontSize: '0.72rem',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              backgroundColor: statusBg,
                              color: statusColor,
                              fontWeight: 600
                            }}>
                              {claim.status}
                            </span>
                            {claim.claim_type && (
                              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #94a3b8)', textTransform: 'capitalize' }}>
                                ({claim.claim_type.replace('_', ' ')})
                              </span>
                            )}
                          </div>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #94a3b8)' }}>
                            Confidence: {Math.round(claim.confidence * 100)}%
                          </span>
                        </div>

                        <p style={{ margin: 0, fontSize: '0.88rem', lineHeight: '1.4', color: 'var(--text-primary)' }}>
                          {claim.claim}
                        </p>

                        {claim.reason && (
                          <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: isUnsupported ? '#f87171' : 'var(--text-muted, #94a3b8)', fontStyle: 'italic' }}>
                            {claim.reason}
                          </div>
                        )}

                        {claim.evidence && (
                          <div style={{
                            marginTop: '0.5rem',
                            padding: '0.5rem 0.75rem',
                            backgroundColor: 'rgba(0, 0, 0, 0.2)',
                            borderLeft: `3px solid ${statusColor}`,
                            borderRadius: '4px',
                            fontSize: '0.8rem',
                            color: 'var(--text-secondary)'
                          }}>
                            <strong style={{ color: 'var(--text-primary)' }}>Source Evidence:</strong> "{claim.evidence}"
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Section Breakdown Accordion / Toggle */}
          {hierarchicalResult.section_summaries && hierarchicalResult.section_summaries.length > 0 && (
            <div className="controls-card" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ListChecks size={18} color="var(--accent-blue)" />
                  Intermediate Section Summaries ({hierarchicalResult.section_summaries.length})
                </h3>
                <button
                  type="button"
                  onClick={() => setShowSections(!showSections)}
                  className="btn-secondary"
                  style={{
                    padding: '0.4rem 0.9rem',
                    fontSize: '0.85rem',
                    background: 'transparent',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer'
                  }}
                >
                  {showSections ? 'Hide Sections' : 'Inspect Sections'}
                </button>
              </div>

              {showSections && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
                  {hierarchicalResult.section_summaries.map((sec) => (
                    <div
                      key={sec.section_index}
                      style={{
                        padding: '1rem',
                        backgroundColor: sec.is_redundant ? 'rgba(234, 179, 8, 0.04)' : 'var(--bg-surface-elevated, #1a2234)',
                        borderRadius: 'var(--radius-md)',
                        border: sec.is_redundant ? '1px dashed rgba(234, 179, 8, 0.35)' : '1px solid var(--border-color)',
                        opacity: sec.is_redundant ? 0.85 : 1.0,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <strong style={{ color: sec.is_redundant ? '#facc15' : 'var(--accent-blue)', margin: 0 }}>
                            Section #{sec.section_index}
                          </strong>
                          {sec.is_redundant && (
                            <span style={{
                              fontSize: '0.72rem',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              backgroundColor: 'rgba(234, 179, 8, 0.2)',
                              color: '#facc15',
                              fontWeight: 600
                            }}>
                              Redundant ({sec.redundancy_info?.redundancy_type === 'exact_duplicate' ? 'Exact Match' : `${Math.round((sec.redundancy_info?.similarity || 0.85) * 100)}% Match`})
                            </span>
                          )}
                        </div>
                        {sec.importance_score !== undefined && sec.importance_score !== null && (
                          <span style={{
                            fontSize: '0.75rem',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            backgroundColor: sec.importance_score >= 0.7 ? 'rgba(34, 197, 94, 0.2)' : sec.importance_score >= 0.4 ? 'rgba(234, 179, 8, 0.2)' : 'rgba(148, 163, 184, 0.2)',
                            color: sec.importance_score >= 0.7 ? '#4ade80' : sec.importance_score >= 0.4 ? '#facc15' : '#94a3b8',
                            fontWeight: 600
                          }}>
                            Importance: {Math.round(sec.importance_score * 100)}%
                          </span>
                        )}
                      </div>
                      <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.5', color: 'var(--text-secondary)' }}>
                        {sec.summary}
                      </p>
                      {sec.is_redundant && sec.redundancy_info?.reason && (
                        <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#facc15', fontStyle: 'italic' }}>
                          Filtered from synthesis: {sec.redundancy_info.reason}
                        </div>
                      )}
                      {sec.importance_reason && !sec.is_redundant && (
                        <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted, #94a3b8)', fontStyle: 'italic' }}>
                          {sec.importance_reason}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
