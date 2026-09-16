import React, { useState } from 'react';
import { PlaySquare, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { summarizeYouTube } from '../services/api';
import SummaryResult from './SummaryResult';

export default function YouTubeSummarizer({ onError }) {
  const [url, setUrl] = useState('');
  const [length, setLength] = useState('medium');
  const [format, setFormat] = useState('paragraph');
  const [executive, setExecutive] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;

    const cleanUrl = url.trim();
    if (!cleanUrl) {
      setError('Please enter a YouTube video URL.');
      return;
    }

    if (!cleanUrl.includes('youtube.com') && !cleanUrl.includes('youtu.be')) {
      setError('Please provide a valid YouTube URL (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...)');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSummary(null);

    try {
      const response = await summarizeYouTube({
        url: cleanUrl,
        length,
        format,
        executive,
      });

      if (response && response.summary) {
        setSummary(response.summary);
      } else {
        setError('Received an empty summary for this YouTube video.');
      }
    } catch (err) {
      setError(err.message || 'Failed to summarize YouTube video transcript.');
      if (onError) onError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper">
      <div className="controls-card">
        <div className="section-heading">
          <h2>YouTube Video Transcript Summarizer</h2>
          <p>
            Paste any YouTube video or Shorts link to automatically extract the closed-caption transcript and generate a structured AI summary.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {/* YouTube URL input */}
          <div className="form-group">
            <label className="form-label" htmlFor="youtube-url-input">
              YouTube Video URL
            </label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <div style={{ position: 'absolute', left: '1rem', color: '#ff4444', display: 'flex', alignItems: 'center' }}>
                <PlaySquare size={22} />
              </div>
              <input
                id="youtube-url-input"
                type="url"
                className="input-textarea"
                style={{
                  paddingLeft: '3rem',
                  paddingTop: '0.85rem',
                  paddingBottom: '0.85rem',
                  minHeight: 'auto',
                  height: '48px',
                  width: '100%',
                  fontSize: '0.95rem'
                }}
                placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setError(null);
                }}
                disabled={isLoading}
              />
            </div>
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
              disabled={isLoading || !url.trim()}
              className="btn-primary"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Fetching Transcript & Summarizing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  <span>Summarize YouTube Video</span>
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
          title="YouTube Video Summary"
          metaInfo={`TRANSCRIPT • ${length.toUpperCase()} • ${format.toUpperCase()}${executive ? ' • EXECUTIVE' : ''}`}
        />
      )}
    </div>
  );
}
