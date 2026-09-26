/**
 * API Service for AI Summarizer Frontend
 * Communicates with FastAPI backend running on http://127.0.0.1:8000
 */

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

/**
 * Format backend error responses into user-friendly error messages
 */
async function handleResponseError(response) {
  let errorMessage = `Server error (${response.status})`;

  try {
    const errorData = await response.json();
    if (errorData.detail) {
      if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        // FastAPI validation errors (e.g. 422)
        errorMessage = errorData.detail
          .map((err) => `${err.loc ? err.loc.join(' -> ') : 'Field'}: ${err.msg}`)
          .join('; ');
      } else {
        errorMessage = JSON.stringify(errorData.detail);
      }
    }
  } catch {
    // If response body is not JSON
    if (response.status === 413) {
      errorMessage = 'File is too large. Maximum supported size is 10 MB.';
    } else if (response.status === 400) {
      errorMessage = 'Bad request. Please verify the uploaded file and parameters.';
    } else if (response.status === 500) {
      errorMessage = 'Internal server error while processing the request.';
    }
  }

  return new Error(errorMessage);
}

/**
 * Check backend health
 */
export async function checkBackendHealth() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      return { online: true, status: data.status };
    }
    return { online: false, status: 'Error' };
  } catch {
    return { online: false, status: 'Offline' };
  }
}

/**
 * Single document summarization
 * POST /summarize
 */
export async function summarizeDocument({ file, length, format, executive }) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('length', length || 'medium');
  formData.append('format', format || 'paragraph');
  formData.append('executive', executive ? 'true' : 'false');

  try {
    const response = await fetch(`${API_BASE_URL}/summarize`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data; // { summary: "..." }
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`);
    }
    throw err;
  }
}

/**
 * Key Points extraction
 * POST /key-points
 */
export async function extractKeyPoints({ file, numberOfPoints }) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('number_of_points', numberOfPoints || 5);

  try {
    const response = await fetch(`${API_BASE_URL}/key-points`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data; // { key_points: [...] }
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`);
    }
    throw err;
  }
}

/**
 * Multiple document summarization
 * POST /summarize-multiple
 */
export async function summarizeMultipleDocuments({ files, length, format, executive }) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  formData.append('length', length || 'medium');
  formData.append('format', format || 'paragraph');
  formData.append('executive', executive ? 'true' : 'false');

  try {
    const response = await fetch(`${API_BASE_URL}/summarize-multiple`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data; // { summary: "..." }
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`);
    }
    throw err;
  }
}

/**
 * Document comparison
 * POST /compare
 */
export async function compareDocuments({ fileA, fileB }) {
  const formData = new FormData();
  formData.append('file_a', fileA);
  formData.append('file_b', fileB);

  try {
    const response = await fetch(`${API_BASE_URL}/compare`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data; // { summary: "..." }
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`);
    }
    throw err;
  }
}

/**
 * Audio / Video summarization
 * POST /summarize-media
 */
export async function summarizeMedia({ file, length, format, executive }) {
  const formData = new FormData();

  formData.append('file', file);
  formData.append('length', length || 'medium');
  formData.append('format', format || 'paragraph');
  formData.append('executive', executive ? 'true' : 'false');

  try {
    const response = await fetch(`${API_BASE_URL}/summarize-media`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();

    return data; // { summary: "..." }
  } catch (err) {
    if (
      err.name === 'TypeError' &&
      err.message.includes('fetch')
    ) {
      throw new Error(
        `Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`
      );
    }

    throw err;
  }
}

/**
 * Update / Delta summary
 * POST /update-summary
 */
export async function updateSummary({ previousSummary, currentText }) {
  const formData = new FormData();
  formData.append('previous_summary', previousSummary);
  formData.append('current_text', currentText);

  try {
    const response = await fetch(`${API_BASE_URL}/update-summary`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data; // { summary: "..." }
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(
        `Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`
      );
    }
    throw err;
  }
}

/**
 * Hierarchical document summarization (Map-Reduce)
 * POST /summarize-hierarchical
 */
export async function summarizeHierarchical({ file, length, format, executive, chunkSize }) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('length', length || 'medium');
  formData.append('format', format || 'paragraph');
  formData.append('executive', executive ? 'true' : 'false');
  if (chunkSize) {
    formData.append('chunk_size', chunkSize);
  }

  try {
    const response = await fetch(`${API_BASE_URL}/summarize-hierarchical`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data; // { final_summary: "...", section_summaries: [...], total_sections: N }
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(
        `Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`
      );
    }
    throw err;
  }
}

/**
 * YouTube video transcript summarization
 * POST /summarize-youtube
 */
export async function summarizeYouTube({ url, length, format, executive }) {
  const formData = new FormData();
  formData.append('url', url);
  formData.append('length', length || 'medium');
  formData.append('format', format || 'paragraph');
  formData.append('executive', executive ? 'true' : 'false');

  try {
    const response = await fetch(`${API_BASE_URL}/summarize-youtube`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data; // { summary: "..." }
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(
        `Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`
      );
    }
    throw err;
  }
}

/**
 * Check faithfulness of summary against source material
 * POST /check-faithfulness
 */
export async function checkFaithfulness({ file, sourceText, summaryText, useLlm }) {
  const formData = new FormData();
  formData.append('summary_text', summaryText);
  if (file) {
    formData.append('file', file);
  }
  if (sourceText) {
    formData.append('source_text', sourceText);
  }
  formData.append('use_llm', useLlm ? 'true' : 'false');

  try {
    const response = await fetch(`${API_BASE_URL}/check-faithfulness`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw await handleResponseError(response);
    }

    const data = await response.json();
    return data;
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(
        `Could not reach backend at ${API_BASE_URL}. Please ensure the backend server is running.`
      );
    }
    throw err;
  }
}