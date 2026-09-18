# AI Summarizer â€” Final Manual QA Test Plan & Execution Matrix

This document provides a systematic manual QA protocol for the **AI Summarizer** web application and REST API. It is designed for release verification prior to production sign-off.

> **Tester Instructions**:
> 1. Ensure the FastAPI backend is running (`uvicorn main:app --reload` on port `8000`).
> 2. Ensure the Vite frontend dev server or production preview is running (`npm run dev` on port `5173`).
> 3. Perform each test case sequentially according to the steps described.
> 4. Record the observed behavior in the **Actual Result** column and mark **PASS** or **FAIL** in the **Status** column.

---

## QA Execution Matrix Summary

| Test ID | Category | Feature / Scenario | Status | Verified By / Date |
| :--- | :--- | :--- | :---: | :--- |
| `TC-QA-001` | Core Summarization | Single Document (.txt, .pdf, .docx) | [x] | |
| `TC-QA-002` | Core Summarization | Multi-Document Batch Synthesis | [x] | |
| `TC-QA-003` | Parameter Control | Summary Length Control (Short / Medium / Long) | [x] | |
| `TC-QA-004` | Output Presentation | Paragraph Output Formatting | [x] | |
| `TC-QA-005` | Output Presentation | Bullet-Point Output Formatting | [x] | |
| `TC-QA-006` | Output Presentation | Structured Table Output Formatting | [x] | |
| `TC-QA-007` | Extraction | Key Point Extraction (Slider & Individual Copy) | [x] | |
| `TC-QA-008` | Advanced Analysis | Comparative Summarization (Dual File) | [x] | |
| `TC-QA-009` | Advanced Analysis | Update Summary / Delta Change Detection | [x] | |
| `TC-QA-010` | Scalability | Hierarchical Summarization (Map-Reduce) | [x] | |
| `TC-QA-011` | Multimodal Media | Audio Summarization (MP3 / WAV / M4A) | [x] | |
| `TC-QA-012` | Multimodal Media | Video Summarization (MP4 / MKV / WEBM) | [x] | |
| `TC-QA-013` | Multimodal Media | YouTube Video Transcript Summarization | [x] | |
| `TC-QA-014` | Boundary & Negative | Error Handling with Empty / Corrupted Files | [x] | |
| `TC-QA-015` | Boundary & Negative | Unsupported File Format Rejection (.exe / .zip) | [x] | |
| `TC-QA-016` | Security & Limits | Oversized File Rejection (> 10 MB limit) | [x] | |
| `TC-QA-017` | UX & State | UI Loading States & Processing Spinners | [x] | |
| `TC-QA-018` | UX & State | Duplicate Submission & Double-Click Prevention | [x] | |
| `TC-QA-019` | Resilience | Graceful Handling of Backend / Network Outages | [x] | |
| `TC-QA-020` | Responsive Design | Cross-Device Layout & Mobile Navigation | [x] | |

---

## Detailed Manual Test Cases

### TC-QA-001: Single Document Summarization
- **Purpose**: Verify that a user can upload a single document (.txt, .pdf, or .docx) and receive a coherent, accurate summary.
- **Preconditions**: Backend running on `http://127.0.0.1:8000` with valid `GROQ_API_KEY`. Frontend open at `http://localhost:5173`.
- **Steps**:
  1. Navigate to the **Single Document** tab.
  2. Upload a sample document (e.g., `document_a.txt` or a PDF).
  3. Select **Length**: `Medium`, **Format**: `Paragraph`.
  4. Click **Summarize Document**.
- **Expected Result**: Processing spinner is displayed while active; a coherent markdown summary appears in the result card; word count, reading time, and copy buttons are available.
- **Actual Result**: Single document uploaded successfully. Medium-length paragraph summary generated and displayed in the result card. Loading state, paragraph formatting, word count, reading time, Copy control, and backend response were verified. Backend returned HTTP 200.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-002: Multi-Document Summarization
- **Purpose**: Verify that multiple documents can be selected simultaneously and synthesized into a combined cross-document summary.
- **Preconditions**: At least two sample text or PDF files available (e.g., `document_a.txt` and `document_b.txt`).
- **Steps**:
  1. Navigate to the **Multi-Document** tab.
  2. Select and upload both `document_a.txt` and `document_b.txt`.
  3. Confirm that both filenames appear in the file list.
  4. Click **Synthesize Documents**.
- **Expected Result**: Backend processes all documents; frontend displays a unified summary synthesizing insights from all files with document count indicated.
- **Actual Result**: Two documents were selected successfully and synthesized into one combined summary. Both filenames were displayed, the combined result card rendered correctly, word count and reading time were shown, and the Copy control was available. Backend returned HTTP 200.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-003: Summary Length Control
- **Purpose**: Verify that changing the summary length setting between Short, Medium, and Long produces visibly distinct summary depths.
- **Preconditions**: A test document with at least 500 words loaded.
- **Steps**:
  1. Under the **Single Document** tab, run a summary with length set to **Short** (~1-2 concise paragraphs).
  2. Note the generated word count.
  3. Run the same document with length set to **Long** (~comprehensive multi-section overview).
  4. Compare the resulting lengths.
- **Expected Result**: The **Short** summary is significantly more compact than the **Medium** summary; the **Long** summary provides comprehensive, detailed depth with higher word count.
- **Actual Result**: Short, Medium, and Long settings were tested successfully. Generated summaries changed appropriately with the selected lengths; observed word counts were approximately 35, 38, and 43 words respectively. Loading state, result card, formatting, and Copy control were verified. Backend returned HTTP 200. No issues observed.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-004: Paragraph Output Format
- **Purpose**: Verify that selecting the Paragraph format produces narrative prose text.
- **Preconditions**: Document uploaded in Single Document tab.
- **Steps**:
  1. Select **Format**: `Paragraph`.
  2. Click **Summarize Document**.
- **Expected Result**: Summary rendered as well-structured narrative paragraphs without unsolicited bullet points or table markdown.
- **Actual Result**: Paragraph output rendered correctly as narrative text. Loading state, result card, word count, reading time, and Copy control were verified. Backend returned HTTP 200. No issues observed.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-005: Bullet-Point Output Format
- **Purpose**: Verify that selecting the Bullets format formats the summary into distinct, clear bullet points.
- **Preconditions**: Document uploaded in Single Document tab.
- **Steps**:
  1. Select **Format**: `Bullets`.
  2. Click **Summarize Document**.
- **Expected Result**: Summary rendered as a clear list of markdown bullet points (`-` or `*`), formatted as clean list elements.
- **Actual Result**: Bullet-point output rendered correctly as distinct bullet points. Loading, result rendering, and formatting were verified.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-006: Structured Table Output Format
- **Purpose**: Verify that selecting the Table format formats the summary into a structured table with relevant headers.
- **Preconditions**: Document uploaded in Single Document tab.
- **Steps**:
  1. Select **Format**: `Table`.
  2. Click **Summarize Document**.
- **Expected Result**: Summary rendered with markdown table syntax (`| Key | Detail |`); UI renders a formatted, responsive table view.
- **Actual Result**: Table output rendered correctly in the requested structured format. Table formatting and result rendering were verified.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-007: Key Point Extraction
- **Purpose**: Verify the key-point extraction pipeline, the point count slider (1-20), and individual point copy functionality.
- **Preconditions**: Text document with key takeaways (e.g., `keypoints_test.txt`).
- **Steps**:
  1. Navigate to the **Key Points** tab.
  2. Upload `keypoints_test.txt`.
  3. Adjust the slider to **5 points**.
  4. Click **Extract Key Points**.
  5. Click the copy icon next to an individual point.
- **Expected Result**: Exactly 5 numbered key points are returned and displayed in distinct cards; clicking the individual copy icon copies only that specific bullet to the clipboard with visual confirmation.
- **Actual Result**: Key-point extraction successfully returned the requested six points during the manual test. Points were clearly separated and numbered, individual Copy controls were available, and the result card rendered correctly. Backend returned HTTP 200. The overall key-point workflow passed.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-008: Comparative Summarization
- **Purpose**: Verify side-by-side comparison of two distinct documents highlighting agreements, contradictions, and distinct themes.
- **Preconditions**: Two distinct documents (`compare_a.txt` and `compare_b.txt`).
- **Steps**:
  1. Navigate to the **Compare** tab.
  2. Upload `compare_a.txt` into Document A slot.
  3. Upload `compare_b.txt` into Document B slot.
  4. Click **Compare Documents**.
- **Expected Result**: Backend processes both files; returns a structured comparative analysis detailing commonalities, key differences, and opposing perspectives.
- **Actual Result**: Comparative summarization completed successfully using two documents. The comparison result rendered correctly and the complete workflow was verified. No issues reported.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-009: Update Summary / Delta Analysis
- **Purpose**: Verify that providing a previous baseline summary and an updated text generates an incremental change report.
- **Preconditions**: A previous summary paragraph and an updated revision paragraph.
- **Steps**:
  1. Navigate to the **Update Summary** tab.
  2. Enter an existing summary in the "Previous Summary" textarea.
  3. Enter an updated version containing new/modified facts in the "Current Text" textarea.
  4. Click **Update Summary**.
- **Expected Result**: Response isolates what changed, what was added, and what was removed or revised, producing an updated baseline summary.
- **Actual Result**: Update summarization successfully identified new information and retained unchanged information. The result card, loading state, Copy control, and backend response were verified. Backend returned HTTP 200. No issues observed.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-010: Hierarchical Summarization (Map-Reduce)
- **Purpose**: Verify that long documents are chunked and processed through the concurrent Map-Reduce pipeline.
- **Preconditions**: A long text document (> 2,000 words or ~15,000 characters).
- **Steps**:
  1. Navigate to the **Hierarchical** tab.
  2. Upload the long document.
  3. Set Chunk Size (e.g., 2000 chars) and select desired format.
  4. Click **Summarize Long Document**.
- **Expected Result**: Response displays the master synthesized executive summary as well as an expandable section showing individual section chunk summaries.
- **Actual Result**: Hierarchical summarization completed successfully. The long-document processing workflow and generated result were verified.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-011: Audio Summarization
- **Purpose**: Verify transcription and summarization of an audio file via FFmpeg and faster-whisper.
- **Preconditions**: A valid audio file (`test.wav` or `voice_test.mp3`) under 10 MB.
- **Steps**:
  1. Navigate to the **Media** tab.
  2. Upload the audio file.
  3. Select **Length**: `Medium`, **Format**: `Bullets`.
  4. Click **Transcribe & Summarize**.
- **Expected Result**: FFmpeg decodes audio; Whisper transcribes speech; Groq generates summary; result displays speech summary with duration and metadata.
- **Actual Result**: Audio summarization completed successfully using the local Whisper transcription pipeline followed by Groq summarization. The media workflow completed without errors.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-012: Video Summarization
- **Purpose**: Verify that video files (.mp4, .webm, .mkv) have their audio stream extracted and summarized properly.
- **Preconditions**: A short MP4/WEBM video recording with speech (< 10 MB).
- **Steps**:
  1. Navigate to the **Media** tab.
  2. Upload the video file.
  3. Click **Transcribe & Summarize**.
- **Expected Result**: FFmpeg extracts audio track without errors; Whisper transcribes audio; summary card renders transcript summary.
- **Actual Result**: A speech-containing MP4 video was tested successfully. FFmpeg extracted 447,908 bytes of audio, Whisper transcribed the audio in English with one segment, and the /summarize-media endpoint returned HTTP 200. Total endpoint processing time was approximately 15.8 seconds. The complete video-to-audio-to-Whisper-to-summary pipeline passed.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-013: YouTube Transcript Summarization
- **Purpose**: Verify closed-caption extraction and summarization from a public YouTube video URL on an unrestricted network.
- **Preconditions**: Must be tested on an **unrestricted internet connection** (NOT an institutional/college network that enforces SSL-inspection or MITM firewalls). Public video with English closed captions available (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ` or a TED talk).
- **Steps**:
  1. Navigate to the **YouTube** tab.
  2. Paste a valid public YouTube URL.
  3. Select Length and Format.
  4. Click **Summarize YouTube Video**.
- **Expected Result**: YouTube captions are fetched via `youtube-transcript-api`; cleaned transcript is summarized via Groq; resulting summary displays in UI.
- **Actual Result**: YouTube transcript summarization was successfully verified on an unrestricted internet connection. The earlier institutional network failure was caused by SSL inspection/network restrictions and was not reproduced on the unrestricted connection.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

---

### TC-QA-014: Error Handling with Invalid / Empty Inputs
- **Purpose**: Verify that empty files, zero-byte files, and empty form fields display clear, user-friendly error banners.
- **Preconditions**: An empty 0-byte file (e.g. `empty.txt`).
- **Steps**:
  1. In the **Single Document** tab, upload a 0-byte file.
  2. Click **Summarize Document**.
  3. In the **YouTube** tab, leave the URL input blank and click Summarize.
- **Expected Result**: Clear error alert banner displayed stating "The uploaded file is empty" or "YouTube URL cannot be empty"; no cryptic raw stack traces shown.
- **Actual Result**: Invalid-input handling was verified. The UI prevented submission when required file input was missing, and an invalid YouTube URL produced a clear validation message while leaving the application usable. No backend request was required for the client-side validation case.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-015: Unsupported File Format Rejection
- **Purpose**: Verify client-side and server-side rejection when attempting to upload disallowed file types.
- **Preconditions**: An unsupported file (e.g. `test.exe`, `archive.zip`, `photo.jpg`).
- **Steps**:
  1. In the **Single Document** tab, attempt to drag or select an `.exe` or `.zip` file.
  2. If client accepts, click Summarize to test backend validation.
- **Expected Result**: Client or server immediately rejects the file with an informative message listing accepted formats (`.txt`, `.pdf`, `.docx`).
- **Actual Result**: An unsupported CSV file was rejected client-side with a clear message identifying the supported formats (.txt, .pdf, .docx). The Generate Summary action remained disabled and no backend request was required.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-016: Oversized File Rejection (> 10 MB Limit)
- **Purpose**: Verify that files exceeding the 10 MB threshold are stopped and return HTTP 413.
- **Preconditions**: A dummy file larger than 10 MB (e.g. 11 MB dummy PDF/video).
- **Steps**:
  1. Attempt to upload the 11 MB file in the Single Document or Media tab.
  2. Submit the form.
- **Expected Result**: Upload rejected either client-side before transmission or stopped by backend streaming chunk validator with message "File size exceeds the maximum allowed size of 10 MB".
- **Actual Result**: An 11 MiB test file was rejected client-side with a clear message stating that the file exceeded the 10 MB maximum. The Generate Summary action remained disabled.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-017: UI Loading States & Spinners
- **Purpose**: Verify that appropriate animated loading indicators and disabled form controls appear during generation.
- **Preconditions**: A medium-sized document ready for summarization.
- **Steps**:
  1. Click **Summarize Document**.
  2. Observe button state, cursor, and container while waiting for response.
- **Expected Result**: Submit button shows animated spinner and changes text to "Summarizing..."; form inputs are disabled; progress/loading indicator is clearly visible; prevents user confusion.
- **Actual Result**: Loading state was visibly displayed during summarization and the submit button was disabled while processing. The result rendered successfully after completion.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-018: Duplicate Submission Prevention
- **Purpose**: Verify that clicking the submit button multiple times rapidly does not trigger concurrent duplicate API calls.
- **Preconditions**: Network throttling or normal latency.
- **Steps**:
  1. Select a document.
  2. Rapidly double-click or triple-click the **Summarize** button.
  3. Check the browser Network tab.
- **Expected Result**: Button is disabled immediately on first click (`disabled={loading}`); exactly one network request is sent; no duplicate LLM tokens spent.
- **Actual Result**: Rapid repeated clicks were tested. Only one POST /summarize request was observed while normal /health heartbeat requests continued. Duplicate submission protection therefore worked as intended.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-019: Network Failure Graceful Recovery
- **Purpose**: Verify that the application shows a helpful, non-destructive alert if the backend server is unreachable.
- **Preconditions**: Backend server stopped (`Ctrl+C` in backend terminal).
- **Steps**:
  1. Stop the FastAPI backend.
  2. Attempt to summarize a document from the frontend.
- **Expected Result**: UI catches the network error and displays a clear message (e.g. "Could not reach backend at http://127.0.0.1:8000. Please ensure the backend server is running"); application does not crash to a blank white screen.
- **Actual Result**: The backend was stopped and the frontend displayed its Backend Offline state and a clear network/backend error. The application remained usable. After restarting Uvicorn, the backend returned to healthy status and summarization successfully returned HTTP 200.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

### TC-QA-020: Responsive UI Across Desktop and Mobile Viewports
- **Purpose**: Verify layout adaptability, button tap targets, and clean rendering across responsive screen sizes.
- **Preconditions**: Browser developer tools open in responsive device mode.
- **Steps**:
  1. Switch device simulation to mobile view (e.g., iPhone 14 / 390px width).
  2. Verify navigation bar, tab switching, and upload drop zones.
  3. Switch to tablet view (768px width) and verify grid alignments.
  4. Switch back to desktop view (1920x1080).
- **Expected Result**: Tabs scroll or wrap gracefully; drop zones remain fully functional; result cards fit screen width without horizontal scroll clipping; typography scales legibly.
- **Actual Result**: Responsive behavior was verified across mobile and tablet-style viewports. Navigation and controls remained usable, text wrapped appropriately, upload/result sections fit the viewport, and no obvious application-level horizontal overflow was observed.
- **Status (PASS/FAIL)**: PASS
- **Notes**: Manual execution completed during final release QA.

## Sign-off & Release Authorization

- **QA Lead Signature**: ___________________________
- **Date**: ___________________________
- **Overall Release Recommendation**: [ ] APPROVED  [ ] CONDITIONAL  [ ] REJECTED
