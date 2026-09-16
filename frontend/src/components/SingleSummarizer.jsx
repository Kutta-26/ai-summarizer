import React, { useState } from 'react';
import FileUpload from './FileUpload';
import SummaryResult from './SummaryResult';
import { summarizeDocument } from '../services/api';
import { Sparkles, Loader2, AlertCircle } from 'lucide-react';

export default function SingleSummarizer({ onError }) {
  const [file, setFile] = useState(null);
  const [length, setLength] = useState('medium');
  const [format, setFormat] = useState('paragraph');
  const [executive, setExecutive] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    setError(null);
  };

  const handleFileRemove = () => {
    setFile(null);
    setError(null);
    setSummary(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (!file) {
      setError('Please select a document to summarize.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSummary(null);

    try {
      const response = await summarizeDocument({
        file,
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
      setError(err.message || 'An error occurred during summarization.');
      if (onError) onError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper">
      <div className="controls-card">
        <form onSubmit={handleSubmit}>
          {/* File Upload Area */}
          <div className="form-group">
            <label className="form-label">Upload Document</label>
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

          {/* Executive Summary Checkbox */}
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
                <strong>Executive Summary</strong> &mdash; Generate high-level strategic overview
              </span>
            </label>
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
                  <span>Processing with Groq LLM...</span>
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  <span>Generate Summary</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Result Section */}
      {summary && (
        <SummaryResult
          summary={summary}
          title={`Summary of ${file ? file.name : 'Document'}`}
          metaInfo={`${length.toUpperCase()} • ${format.toUpperCase()}${executive ? ' • EXECUTIVE' : ''}`}
        />
      )}
    </div>
  );
}
