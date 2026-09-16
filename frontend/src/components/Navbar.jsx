import React from 'react';
import { FileText, Cpu, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

export default function Navbar({ isOnline, isCheckingHealth, onCheckHealth }) {
  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="brand-icon">
          <FileText size={24} className="icon-blue" />
        </div>
        <div>
          <h1 className="brand-title">AI Summarizer</h1>
          <p className="brand-subtitle">FastAPI &bull; Groq OSS LLM &bull; Multi-format Engine</p>
        </div>
      </div>

      <div className="navbar-status">
        <div className={`status-pill ${isOnline ? 'status-online' : 'status-offline'}`}>
          {isOnline ? (
            <>
              <span className="status-dot"></span>
              <CheckCircle2 size={15} />
              <span>Backend Connected</span>
            </>
          ) : (
            <>
              <AlertCircle size={15} />
              <span>Backend Offline</span>
            </>
          )}
        </div>

        <button
          onClick={onCheckHealth}
          className="icon-button"
          title="Refresh Backend Status"
          disabled={isCheckingHealth}
        >
          <RefreshCw size={15} className={isCheckingHealth ? 'spin' : ''} />
        </button>
      </div>
    </header>
  );
}
