import React, { useState } from 'react';
import FileUpload from './FileUpload';
import { extractKeyPoints } from '../services/api';
import { ListOrdered, Sparkles, Loader2, AlertCircle, Copy, Check, CheckSquare } from 'lucide-react';

export default function KeyPointsTab() {
  const [file, setFile] = useState(null);
  const [numberOfPoints, setNumberOfPoints] = useState(5);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [keyPoints, setKeyPoints] = useState([]);
  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState(null);

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    setError(null);
  };

  const handleFileRemove = () => {
    setFile(null);
    setError(null);
    setKeyPoints([]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (!file) {
      setError('Please select a document for key points extraction.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setKeyPoints([]);

    try {
      const response = await extractKeyPoints({
        file,
        numberOfPoints: parseInt(numberOfPoints, 10),
      });

      if (response && response.key_points) {
        setKeyPoints(response.key_points);
      } else {
        setError('No key points returned by the backend.');
      }
    } catch (err) {
      setError(err.message || 'Failed to extract key points.');
    } finally {
      setIsLoading(false);
    }
  };

  const copyAllPoints = async () => {
    if (keyPoints.length === 0) return;
    const text = keyPoints.map((p, i) => `${i + 1}. ${p}`).join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    } catch {
      // Fallback
    }
  };

  const copySinglePoint = async (point, idx) => {
    try {
      await navigator.clipboard.writeText(point);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="tab-content-wrapper">
      <div className="controls-card">
        <form onSubmit={handleSubmit}>
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

          <div className="form-group">
            <div className="slider-label-row">
              <label className="form-label">Number of Key Points</label>
              <span className="slider-value-badge">{numberOfPoints} points</span>
            </div>
            <input
              type="range"
              min="1"
              max="20"
              value={numberOfPoints}
              onChange={(e) => setNumberOfPoints(e.target.value)}
              className="slider-input"
              disabled={isLoading}
            />
            <div className="slider-ticks">
              <span>1</span>
              <span>5</span>
              <span>10</span>
              <span>15</span>
              <span>20</span>
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
              disabled={isLoading || !file}
              className="btn-primary"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Extracting Key Points...</span>
                </>
              ) : (
                <>
                  <ListOrdered size={18} />
                  <span>Extract Key Points</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {keyPoints.length > 0 && (
        <div className="summary-card">
          <div className="summary-header">
            <div className="summary-title-group">
              <CheckSquare size={18} className="icon-sparkle" />
              <h3 className="summary-title">Extracted Key Points ({keyPoints.length})</h3>
            </div>
            <div className="summary-actions">
              <button
                onClick={copyAllPoints}
                className={`btn-action ${copiedAll ? 'btn-copied' : ''}`}
                title="Copy all points"
              >
                {copiedAll ? <Check size={16} /> : <Copy size={16} />}
                <span>{copiedAll ? 'All Copied' : 'Copy All'}</span>
              </button>
            </div>
          </div>

          <div className="keypoints-list">
            {keyPoints.map((point, idx) => (
              <div key={idx} className="keypoint-item">
                <div className="keypoint-num">{idx + 1}</div>
                <div className="keypoint-text">{point}</div>
                <button
                  type="button"
                  onClick={() => copySinglePoint(point, idx)}
                  className="point-copy-btn"
                  title="Copy this point"
                >
                  {copiedIdx === idx ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
