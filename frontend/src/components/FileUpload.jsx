import React, { useRef, useState } from 'react';
import { UploadCloud, File, X, Check } from 'lucide-react';

export default function FileUpload({
  file,
  files,
  onFileSelect,
  onFileRemove,
  onError,
  multiple = false,
  accept = '.txt,.pdf,.docx',
  maxSizeBytes = 10 * 1024 * 1024,
  label = 'Upload Document',
  helperText = 'Supports TXT, PDF, DOCX (Max 10MB)',
  disabled = false,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const validateIncomingFile = (f) => {
    if (!f) return 'No file selected.';
    if (f.size === 0) return `File "${f.name}" is empty (0 bytes).`;
    if (f.size > maxSizeBytes) {
      const maxMb = Math.round(maxSizeBytes / (1024 * 1024));
      return `File "${f.name}" exceeds the maximum allowed size of ${maxMb} MB.`;
    }
    if (accept) {
      const allowedExts = accept.split(',').map((e) => e.trim().toLowerCase());
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      if (!allowedExts.includes(ext)) {
        return `File "${f.name}" has an unsupported format. Allowed formats: ${accept}`;
      }
    }
    return null;
  };

  const processFiles = (rawFiles) => {
    if (!rawFiles || rawFiles.length === 0) return;

    if (multiple) {
      const validFiles = [];
      for (const f of rawFiles) {
        const error = validateIncomingFile(f);
        if (error) {
          if (onError) onError(error);
          return;
        }
        validFiles.push(f);
      }
      onFileSelect(validFiles);
    } else {
      const target = rawFiles[0];
      const error = validateIncomingFile(target);
      if (error) {
        if (onError) onError(error);
        return;
      }
      onFileSelect(target);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleInputChange = (e) => {
    if (disabled) return;
    if (e.target.files && e.target.files.length > 0) {
      processFiles(Array.from(e.target.files));
    }
  };

  // Single file display
  if (!multiple && file) {
    const ext = file.name.split('.').pop()?.toUpperCase() || 'FILE';
    return (
      <div className="selected-file-card">
        <div className="file-icon-box">
          <File size={22} className="icon-blue" />
        </div>
        <div className="file-info">
          <div className="file-name" title={file.name}>
            {file.name}
          </div>
          <div className="file-meta">
            <span className="badge-file-ext">{ext}</span>
            <span>{formatFileSize(file.size)}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => onFileRemove()}
          className="remove-file-btn"
          title="Remove file"
        >
          <X size={18} />
        </button>
      </div>
    );
  }

  // Multiple files list if multiple is active
  if (multiple && files && files.length > 0) {
    return (
      <div className="multi-files-container">
        <div className="multi-files-header">
          <span>Selected Documents ({files.length})</span>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="btn-link"
          >
            + Add More
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={accept}
            onChange={handleInputChange}
            style={{ display: 'none' }}
          />
        </div>
        <div className="files-list">
          {files.map((f, idx) => (
            <div key={`${f.name}-${idx}`} className="file-chip">
              <span className="file-chip-name">{f.name}</span>
              <span className="file-chip-size">({formatFileSize(f.size)})</span>
              <button
                type="button"
                onClick={() => onFileRemove(idx)}
                className="chip-remove-btn"
                title="Remove file"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`dropzone ${isDragging ? 'dropzone-active' : ''} ${disabled ? 'dropzone-disabled' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      style={disabled ? { opacity: 0.6, cursor: 'not-allowed' } : undefined}
    >
      <input
        ref={inputRef}
        type="file"
        multiple={multiple}
        accept={accept}
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />
      <div className="dropzone-content">
        <div className="upload-icon-wrapper">
          <UploadCloud size={32} />
        </div>
        <p className="dropzone-prompt">
          <span className="highlight-text">Click to choose a file</span> or drag & drop here
        </p>
        <p className="dropzone-helper">{helperText}</p>
      </div>
    </div>
  );
}
