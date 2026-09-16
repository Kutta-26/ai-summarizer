import React, { useState } from 'react';
import FileUpload from './FileUpload';
import SummaryResult from './SummaryResult';
import { summarizeMultipleDocuments } from '../services/api';
import { Files, Sparkles, Loader2, AlertCircle } from 'lucide-react';

export default function MultiSummarizer() {
  const [files, setFiles] = useState([]);
  const [length, setLength] = useState('medium');
  const [format, setFormat] = useState('paragraph');
  const [executive, setExecutive] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);

  const handleFilesSelect = (newFiles) => {
    setFiles((prev) => [...prev, ...newFiles]);
    setError(null);
  };

  const handleFileRemove = (indexToRemove) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
    if (files.length <= 1) {
      setSummary(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (files.length === 0) {
      setError('Please upload at least two documents for multi-document summarization.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSummary(null);

    try {
      const response = await summarizeMultipleDocuments({
        files,
        length,
        format,
        executive,
      });

      if (response && response.summary) {
        setSummary(response.summary);
      } else {
        setError('Received an empty summary from the server.');
      }
    } catch (err) {
      setError(err.message || 'Failed to generate multi-document summary.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper">
      <div className="controls-card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Upload Multiple Documents</label>
            <FileUpload
              files={files}
              onFileSelect={handleFilesSelect}
              onFileRemove={handleFileRemove}
              onError={(msg) => setError(msg)}
              disabled={isLoading}
              multiple={true}
              accept=".txt,.pdf,.docx"
              helperText="Upload multiple TXT, PDF, or DOCX files to summarize into a unified synthesis"
            />
          </div>

          <div className="options-grid">
            <div className="form-group">
              <label className="form-label">Summary Length</label>
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

          <div className="form-group checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={executive}
                onChange={(e) => setExecutive(e.target.checked)}
                disabled={isLoading}
              />
              <span className="checkbox-custom"></span>
              <span className="checkbox-text">
                <strong>Executive Summary</strong> &mdash; Create an executive briefing across all documents
              </span>
            </label>
          </div>

          {error && (
            <div className="alert-banner alert-error">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-actions">
            <button
              type="submit"
              disabled={isLoading || files.length === 0}
              className="btn-primary"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Synthesizing {files.length} Documents...</span>
                </>
              ) : (
                <>
                  <Files size={18} />
                  <span>Summarize {files.length > 0 ? `${files.length} Documents` : 'Documents'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {summary && (
        <SummaryResult
          summary={summary}
          title={`Multi-Document Synthesis (${files.length} documents)`}
          metaInfo={`SYNTHESIS • ${length.toUpperCase()} • ${format.toUpperCase()}`}
        />
      )}
    </div>
  );
}
