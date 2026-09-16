import React, { useState, useEffect } from 'react';

import Navbar from './components/Navbar';
import SingleSummarizer from './components/SingleSummarizer';
import KeyPointsTab from './components/KeyPointsTab';
import MultiSummarizer from './components/MultiSummarizer';
import CompareTab from './components/CompareTab';
import MediaSummarizer from './components/MediaSummarizer';
import UpdateSummaryTab from './components/UpdateSummaryTab';
import HierarchicalSummarizer from './components/HierarchicalSummarizer';
import YouTubeSummarizer from './components/YouTubeSummarizer';

import { checkBackendHealth, API_BASE_URL } from './services/api';

import {
  FileText,
  ListOrdered,
  Files,
  GitCompare,
  Video,
  AlertTriangle,
  RefreshCw,
  Layers,
  PlaySquare
} from 'lucide-react';


export default function App() {

  const [activeTab, setActiveTab] = useState('single');

  const [isBackendOnline, setIsBackendOnline] = useState(false);

  const [isCheckingHealth, setIsCheckingHealth] = useState(false);


  // ============================================================
  // BACKEND HEALTH CHECK
  // ============================================================

  const verifyHealth = async () => {

    setIsCheckingHealth(true);

    const health = await checkBackendHealth();

    setIsBackendOnline(health.online);

    setIsCheckingHealth(false);
  };


  // ============================================================
  // INITIAL HEALTH CHECK + PERIODIC CHECK
  // ============================================================

  useEffect(() => {

    verifyHealth();

    // Check backend every 15 seconds
    const interval = setInterval(
      verifyHealth,
      15000
    );

    return () => clearInterval(interval);

  }, []);


  // ============================================================
  // APPLICATION TABS
  // ============================================================

  const tabs = [

    {
      id: 'single',
      label: 'Single Document',
      icon: FileText,
      desc: 'Summarize TXT, PDF, DOCX'
    },

    {
      id: 'keypoints',
      label: 'Key Points',
      icon: ListOrdered,
      desc: 'Extract key takeaways'
    },

    {
      id: 'multi',
      label: 'Multi-Document',
      icon: Files,
      desc: 'Synthesize multiple files'
    },

    {
      id: 'compare',
      label: 'Compare Documents',
      icon: GitCompare,
      desc: 'Analyze differences'
    },

    {
      id: 'media',
      label: 'Audio / Video',
      icon: Video,
      desc: 'Summarize audio & video'
    },

    {
      id: 'update',
      label: 'Update Summary',
      icon: RefreshCw,
      desc: 'What changed since last summary?'
    },

    {
      id: 'hierarchical',
      label: 'Hierarchical',
      icon: Layers,
      desc: 'Map-Reduce for long documents'
    },

    {
      id: 'youtube',
      label: 'YouTube Video',
      icon: PlaySquare,
      desc: 'Summarize video transcript'
    }

  ];


  // ============================================================
  // RENDER
  // ============================================================

  return (

    <div className="app-container">

      {/* ======================================================
          NAVBAR
      ====================================================== */}

      <Navbar
        isOnline={isBackendOnline}
        isCheckingHealth={isCheckingHealth}
        onCheckHealth={verifyHealth}
      />


      <main className="main-content">


        {/* ====================================================
            BACKEND OFFLINE WARNING
        ==================================================== */}

        {!isBackendOnline && (
          <div className="backend-offline-banner">
            <AlertTriangle size={18} />
            <span>
              Backend is currently offline or unreachable at{' '}
              <code>{API_BASE_URL}</code>.
              Ensure FastAPI backend server is running.
            </span>
          </div>
        )}


        {/* ====================================================
            TAB NAVIGATION
        ==================================================== */}

        <nav className="tabs-nav">

          {tabs.map((tab) => {

            const Icon = tab.icon;

            const isActive =
              activeTab === tab.id;

            return (

              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={
                  `tab-btn ${
                    isActive
                      ? 'tab-btn-active'
                      : ''
                  }`
                }
              >

                <Icon
                  size={18}
                  className="tab-icon"
                />

                <div className="tab-text-group">

                  <span className="tab-label">
                    {tab.label}
                  </span>

                  <span className="tab-desc">
                    {tab.desc}
                  </span>

                </div>

              </button>

            );

          })}

        </nav>


        {/* ====================================================
            ACTIVE TAB CONTENT
        ==================================================== */}

        <div className="tab-body">

          {/* Single Document */}
          {activeTab === 'single' && (
            <SingleSummarizer />
          )}


          {/* Key Points */}
          {activeTab === 'keypoints' && (
            <KeyPointsTab />
          )}


          {/* Multi Document */}
          {activeTab === 'multi' && (
            <MultiSummarizer />
          )}


          {/* Compare Documents */}
          {activeTab === 'compare' && (
            <CompareTab />
          )}


          {/* Audio / Video */}
          {activeTab === 'media' && (
            <MediaSummarizer />
          )}

          {/* Update Summary */}
          {activeTab === 'update' && (
            <UpdateSummaryTab />
          )}

          {/* Hierarchical Document */}
          {activeTab === 'hierarchical' && (
            <HierarchicalSummarizer />
          )}

          {/* YouTube Transcript */}
          {activeTab === 'youtube' && (
            <YouTubeSummarizer />
          )}

        </div>

      </main>


      {/* ======================================================
          FOOTER
      ====================================================== */}

      <footer className="app-footer">

        <p>
          AI Summarizer &bull; Advanced AI Internship Project
          &bull; Powered by Groq LLM & FastAPI
        </p>

      </footer>

    </div>

  );

}