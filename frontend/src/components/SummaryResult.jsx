import React, { useState } from 'react';
import { Copy, Check, Download, AlignLeft, Sparkles } from 'lucide-react';

export default function SummaryResult({ summary, title = "Generated Summary", metaInfo }) {
  const [copied, setCopied] = useState(false);

  if (!summary) return null;

  const wordCount = summary.trim() ? summary.trim().split(/\s+/).length : 0;
  const charCount = summary.length;
  const readingTimeMinutes = Math.max(1, Math.ceil(wordCount / 200));

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textArea = document.createElement('textarea');
      textArea.value = summary;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    const element = document.createElement('a');
    const file = new Blob([summary], { type: 'text/plain;charset=utf-8' });
    element.href = URL.createObjectURL(file);
    element.download = `summary-${Date.now()}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="summary-card">
      <div className="summary-header">
        <div className="summary-title-group">
          <Sparkles size={18} className="icon-sparkle" />
          <h3 className="summary-title">{title}</h3>
        </div>

        <div className="summary-actions">
          <button
            onClick={handleCopy}
            className={`btn-action ${copied ? 'btn-copied' : ''}`}
            title="Copy summary to clipboard"
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          <button
            onClick={handleDownload}
            className="btn-action"
            title="Download summary as TXT"
          >
            <Download size={16} />
            <span>Download</span>
          </button>
        </div>
      </div>

      <div className="summary-meta-bar">
        <span className="meta-badge">{wordCount} words</span>
        <span className="meta-badge">{charCount} characters</span>
        <span className="meta-badge">~{readingTimeMinutes} min read</span>
        {metaInfo && <span className="meta-badge meta-custom">{metaInfo}</span>}
      </div>

      <div className="summary-body">
        <div className="summary-content markdown-output">
          {summary.split('\n\n').map((paragraph, pIdx) => {
            const trimmed = paragraph.trim();
            if (!trimmed) return null;

            // Render table if it looks like markdown table
            if (trimmed.includes('|') && trimmed.includes('---')) {
              const rows = trimmed.split('\n').filter((r) => r.trim());
              const headerRow = rows[0].split('|').filter((c) => c.trim());
              const bodyRows = rows.slice(2).map((r) => r.split('|').filter((c) => c.trim()));

              return (
                <div key={pIdx} className="table-responsive">
                  <table className="summary-table">
                    <thead>
                      <tr>
                        {headerRow.map((h, hIdx) => (
                          <th key={hIdx}>{h.trim()}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {bodyRows.map((row, rIdx) => (
                        <tr key={rIdx}>
                          {row.map((cell, cIdx) => (
                            <td key={cIdx}>{cell.trim()}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            }

            // Render bullet points
            if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || /^\d+\.\s/.test(trimmed)) {
              const lines = trimmed.split('\n');
              return (
                <ul key={pIdx} className="summary-list">
                  {lines.map((line, lIdx) => {
                    const cleanLine = line.replace(/^(\s*[-*]|\s*\d+\.)\s*/, '').trim();
                    if (!cleanLine) return null;
                    return <li key={lIdx}>{cleanLine}</li>;
                  })}
                </ul>
              );
            }

            // Default paragraph
            return (
              <p key={pIdx} className="summary-paragraph">
                {trimmed}
              </p>
            );
          })}
        </div>
      </div>
    </div>
  );
}
