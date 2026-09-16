import React, { useState } from 'react';
import { RefreshCw, Sparkles, Loader2, AlertCircle, ArrowRightLeft } from 'lucide-react';
import { updateSummary } from '../services/api';
import SummaryResult from './SummaryResult';

export default function UpdateSummaryTab() {
  const [previousSummary, setPreviousSummary] = useState('');
  const [currentText, setCurrentText] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;

    if (!previousSummary.trim()) {
      setError('Please provide the previous/old summary.');
      return;
    }

    if (!currentText.trim()) {
      setError('Please provide the current document or update text.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await updateSummary({
        previousSummary: previousSummary.trim(),
        currentText: currentText.trim(),
      });

      if (response && response.summary) {
        setResult(response.summary);
      } else {
        setError('Received an empty update summary from the server.');
      }
    } catch (err) {
      setError(err.message || 'An error occurred during update summarization.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setPreviousSummary('');
    setCurrentText('');
    setResult(null);
    setError(null);
  };

  return (
    <div className="tab-content-wrapper">
      <div className="controls-card">
        <div className="section-heading">
          <h2>Update / Delta Summary</h2>
          <p>
            Compare a previous summary with current document contents to identify what has changed, what was added, and what is no longer relevant.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="compare-grid">
            {/* Previous Summary */}
            <div className="form-group">
              <label className="form-label">
                <span className="badge-doc">Previous Summary</span> (Baseline Overview)
              </label>
              <textarea
                className="input-textarea"
                rows={8}
                placeholder="Paste the previous summary or baseline information here..."
                value={previousSummary}
                onChange={(e) => {
                  setPreviousSummary(e.target.value);
                  setError(null);
                }}
                disabled={isLoading}
              />
            </div>

            {/* Current Text / Document */}
            <div className="form-group">
              <label className="form-label">
                <span className="badge-doc badge-doc-b">Current Content</span> (New / Updated Document Text)
              </label>
              <textarea
                className="input-textarea"
                rows={8}
                placeholder="Paste the current document text, notes, or latest release details here..."
                value={currentText}
                onChange={(e) => {
                  setCurrentText(e.target.value);
                  setError(null);
                }}
                disabled={isLoading}
              />
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="alert-banner alert-error">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          {/* Actions */}
          <div className="form-actions" style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
            {(previousSummary || currentText || result) && (
              <button
                type="button"
                className="btn-secondary"
                onClick={handleReset}
                disabled={isLoading}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.2rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'transparent',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontWeight: 500
                }}
              >
                <RefreshCw size={16} />
                Clear
              </button>
            )}

            <button
              type="submit"
              disabled={isLoading || !previousSummary.trim() || !currentText.trim()}
              className="btn-primary"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Comparing & Analyzing Updates...</span>
                </>
              ) : (
                <>
                  <ArrowRightLeft size={18} />
                  <span>Generate Update Summary</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Result Display */}
      {result && (
        <SummaryResult
          summary={result}
          title="Update & Delta Analysis"
          metaInfo="DELTA / CHANGE DETECTION"
        />
      )}
    </div>
  );
}
