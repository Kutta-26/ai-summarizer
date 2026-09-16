import React, { useState } from 'react';
import { Upload, X, Sparkles, Loader2, FileAudio, FileVideo } from 'lucide-react';
import { summarizeMedia } from '../services/api';
import SummaryResult from './SummaryResult';

const ALLOWED_MEDIA_TYPES = [
  'audio/*',
  'video/*',
];

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export default function MediaSummarizer() {
  const [file, setFile] = useState(null);
  const [length, setLength] = useState('medium');
  const [format, setFormat] = useState('paragraph');
  const [executive, setExecutive] = useState(false);

  const [summary, setSummary] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const validateFile = (selectedFile) => {
    if (!selectedFile) {
      return 'Please select an audio or video file.';
    }

    if (
      !selectedFile.type.startsWith('audio/') &&
      !selectedFile.type.startsWith('video/')
    ) {
      return 'Unsupported file type. Please upload an audio or video file.';
    }

    if (selectedFile.size === 0) {
      return 'The selected media file is empty.';
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      return 'Media file is too large. Maximum supported size is 10 MB.';
    }

    return '';
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0];

    setError('');
    setSummary('');

    const validationError = validateFile(selectedFile);

    if (validationError) {
      setFile(null);
      setError(validationError);
      return;
    }

    setFile(selectedFile);
  };

  const handleRemoveFile = () => {
    setFile(null);
    setSummary('');
    setError('');
  };

  const handleGenerateSummary = async () => {
    if (isLoading) return;
    if (!file) {
      setError('Please select an audio or video file first.');
      return;
    }

    setError('');
    setSummary('');
    setIsLoading(true);


    try {
      const result = await summarizeMedia({
        file,
        length,
        format,
        executive,
      });

      setSummary(result.summary || '');
    } catch (err) {
      setError(
        err.message || 'Failed to summarize the media file.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const isAudio = file?.type?.startsWith('audio/');

  return (
    <div className="summarizer-card">

      <div className="section-heading">
        <h2>Audio / Video Summarizer</h2>
        <p>
          Upload an audio or video file and generate an AI-powered summary.
        </p>
      </div>

      {/* Upload Area */}
      <div className="upload-section">

        <label
          htmlFor="media-file-input"
          className="upload-area"
        >
          <input
            id="media-file-input"
            type="file"
            accept="audio/*,video/*"
            onChange={handleFileChange}
            disabled={isLoading}
            hidden
          />

          <Upload size={34} />

          <span className="upload-title">
            Click to choose a file
          </span>

          <span className="upload-subtitle">
            Upload audio or video (Up to 10 MB)
          </span>
        </label>

        {/* Selected File */}
        {file && (
          <div className="selected-file-card">

            <div className="selected-file-icon">
              {isAudio ? (
                <FileAudio size={22} />
              ) : (
                <FileVideo size={22} />
              )}
            </div>

            <div className="selected-file-info">
              <strong>{file.name}</strong>
              <span>{formatFileSize(file.size)}</span>
            </div>

            <button
              type="button"
              className="icon-button"
              onClick={handleRemoveFile}
              disabled={isLoading}
              title="Remove file"
            >
              <X size={18} />
            </button>

          </div>
        )}

      </div>

      {/* Error */}
      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="controls-grid">

        <div className="control-group">
          <label>Summary Length</label>

          <div className="segmented-control">

            {['short', 'medium', 'long'].map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setLength(option)}
                disabled={isLoading}
                className={
                  length === option
                    ? 'segment-active'
                    : ''
                }
              >
                {option.charAt(0).toUpperCase() + option.slice(1)}
              </button>
            ))}

          </div>
        </div>

        <div className="control-group">
          <label>Output Format</label>

          <div className="segmented-control">

            {['paragraph', 'bullets', 'table'].map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setFormat(option)}
                disabled={isLoading}
                className={
                  format === option
                    ? 'segment-active'
                    : ''
                }
              >
                {option.charAt(0).toUpperCase() + option.slice(1)}
              </button>
            ))}

          </div>
        </div>


      </div>

      {/* Executive Summary */}
      <label className="checkbox-row">

        <input
          type="checkbox"
          checked={executive}
          onChange={(event) =>
            setExecutive(event.target.checked)
          }
        />

        <span>
          <strong>Executive Summary</strong>
          {' '}— Generate high-level strategic overview
        </span>

      </label>

      {/* Generate Button */}
      <button
        type="button"
        className="generate-button"
        onClick={handleGenerateSummary}
        disabled={!file || isLoading}
      >

        {isLoading ? (
          <>
            <Loader2
              size={18}
              className="spin"
            />
            Processing Media...
          </>
        ) : (
          <>
            <Sparkles size={18} />
            Generate Summary
          </>
        )}

      </button>

      {/* Result */}
      {summary && (
        <SummaryResult
          summary={summary}
          title={`Media Summary: ${file ? file.name : 'Audio/Video'}`}
          metaInfo={`AUDIO/VIDEO • ${length.toUpperCase()} • ${format.toUpperCase()}${executive ? ' • EXECUTIVE' : ''}`}
        />
      )}

    </div>
  );
}