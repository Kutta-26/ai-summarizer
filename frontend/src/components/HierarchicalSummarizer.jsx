import React, { useState } from 'react';
import FileUpload from './FileUpload';
import SummaryResult from './SummaryResult';
import { summarizeHierarchical } from '../services/api';
import { Layers, Sparkles, Loader2, AlertCircle, ListChecks } from 'lucide-react';

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
            metaInfo={`MAP-REDUCE • ${hierarchicalResult.total_sections} SECTIONS SYNTHESIZED • ${length.toUpperCase()} • ${format.toUpperCase()}`}
          />

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
                        backgroundColor: 'var(--bg-surface-elevated, #1a2234)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-color)',
                      }}
                    >
                      <strong style={{ color: 'var(--accent-blue)', display: 'block', marginBottom: '0.5rem' }}>
                        Section #{sec.section_index}
                      </strong>
                      <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.5', color: 'var(--text-secondary)' }}>
                        {sec.summary}
                      </p>
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
