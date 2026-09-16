import React, { useState } from 'react';
import FileUpload from './FileUpload';
import SummaryResult from './SummaryResult';
import { compareDocuments } from '../services/api';
import { GitCompare, Loader2, AlertCircle } from 'lucide-react';

export default function CompareTab() {
  const [fileA, setFileA] = useState(null);
  const [fileB, setFileB] = useState(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [comparison, setComparison] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (!fileA || !fileB) {
      setError('Please upload both Document A and Document B to compare.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setComparison(null);

    try {
      const response = await compareDocuments({
        fileA,
        fileB,
      });

      if (response && response.summary) {
        setComparison(response.summary);
      } else {
        setError('Received an empty comparison from the server.');
      }
    } catch (err) {
      setError(err.message || 'Failed to compare documents.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper">
      <div className="controls-card">
        <form onSubmit={handleSubmit}>
          <div className="compare-grid">
            <div className="form-group">
              <label className="form-label">
                <span className="badge-doc">Document A</span> Primary Source
              </label>
              <FileUpload
                file={fileA}
                onFileSelect={(f) => {
                  setFileA(f);
                  setError(null);
                }}
                onFileRemove={() => {
                  setFileA(null);
                  setError(null);
                  setComparison(null);
                }}
                onError={(msg) => setError(msg)}
                disabled={isLoading}
                accept=".txt,.pdf,.docx"
                helperText="Upload first document"
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <span className="badge-doc badge-doc-b">Document B</span> Comparison Target
              </label>
              <FileUpload
                file={fileB}
                onFileSelect={(f) => {
                  setFileB(f);
                  setError(null);
                }}
                onFileRemove={() => {
                  setFileB(null);
                  setError(null);
                  setComparison(null);
                }}
                onError={(msg) => setError(msg)}
                disabled={isLoading}
                accept=".txt,.pdf,.docx"
                helperText="Upload second document"
              />
            </div>
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
              disabled={isLoading || !fileA || !fileB}
              className="btn-primary"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Analyzing Differences & Similarities...</span>
                </>
              ) : (
                <>
                  <GitCompare size={18} />
                  <span>Compare Both Documents</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {comparison && (
        <SummaryResult
          summary={comparison}
          title={`Comparison: ${fileA?.name} vs ${fileB?.name}`}
          metaInfo="DOCUMENT COMPARISON"
        />
      )}
    </div>
  );
}
