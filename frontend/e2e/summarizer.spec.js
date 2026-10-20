import { test, expect } from '@playwright/test';

test.describe('AI Summarizer — End-to-End Application Suite', () => {

  test.beforeEach(async ({ page }) => {
    // Ensure deterministic backend health check response for UI stability
    await page.route('**/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'Running' }),
      });
    });

    await page.goto('/');
  });

  // ============================================================
  // 1. APPLICATION LOADS SUCCESSFULLY
  // ============================================================
  test('1. Application loads successfully with navbar, tabs, and connected status', async ({ page }) => {
    // Check Brand Title & Subtitle
    await expect(page.locator('.brand-title')).toHaveText('AI Summarizer');
    await expect(page.locator('.brand-subtitle')).toContainText('FastAPI');

    // Check Backend Connection Pill
    const statusPill = page.locator('.status-pill');
    await expect(statusPill).toBeVisible();
    await expect(statusPill).toHaveClass(/status-online/);
    await expect(statusPill).toContainText('Backend Connected');

    // Check Main Navigation Tabs
    const expectedTabs = [
      'Single Document',
      'Key Points',
      'Multi-Document',
      'Compare Documents',
      'Audio / Video',
      'Update Summary',
      'Hierarchical',
      'YouTube Video',
    ];

    for (const tabText of expectedTabs) {
      await expect(page.locator('.tab-btn', { hasText: tabText })).toBeVisible();
    }

    // Default active tab should be Single Document
    await expect(page.locator('.tab-btn-active')).toContainText('Single Document');
    await expect(page.locator('button[type="submit"]')).toContainText('Generate Summary');
  });

  // ============================================================
  // 2. SINGLE-DOCUMENT SUMMARIZATION FLOW
  // ============================================================
  test('2. Single-document summarization flow completes with deterministic mock', async ({ page }) => {
    const mockSummary = 'Artificial intelligence accelerates workflow productivity across engineering and enterprise domains.';

    // Deterministic API mock
    await page.route('**/summarize', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: mockSummary }),
      });
    });

    // Upload sample text file
    const fileChooserInput = page.locator('input[type="file"]').first();
    await fileChooserInput.setInputFiles({
      name: 'annual_report.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Annual performance report details scalable cloud adoption and cost efficiency.'),
    });

    // Verify selected file card
    await expect(page.locator('.selected-file-card')).toBeVisible();
    await expect(page.locator('.file-name')).toHaveText('annual_report.txt');
    await expect(page.locator('.badge-file-ext')).toHaveText('TXT');

    // Click submit button
    const submitBtn = page.locator('button[type="submit"]');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Verify summary result card rendered
    const summaryCard = page.locator('.summary-card');
    await expect(summaryCard).toBeVisible();
    await expect(page.locator('.summary-title')).toHaveText('Summary of annual_report.txt');
    await expect(page.locator('.summary-content')).toContainText(mockSummary);
  });

  // ============================================================
  // 3. LOADING INDICATOR AND DISABLED SUBMIT BUTTON
  // ============================================================
  test('3. Submit button shows loading spinner and is disabled during active request', async ({ page }) => {
    let unblockRoute;
    const holdRoutePromise = new Promise((resolve) => {
      unblockRoute = resolve;
    });

    // Delay response to reliably assert transient in-flight loading state
    await page.route('**/summarize', async (route) => {
      await holdRoutePromise;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: 'Summary finished.' }),
      });
    });

    // Select valid document
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: 'notes.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Meeting notes regarding project roadmap.'),
    });

    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();

    // While request is in-flight: button must be disabled and display spinner
    await expect(submitBtn).toBeDisabled();
    await expect(submitBtn).toContainText('Processing with Groq LLM...');
    await expect(submitBtn.locator('.spin')).toBeVisible();

    // Release delayed response
    unblockRoute();

    // After completion: loading state clears
    await expect(page.locator('.summary-card')).toBeVisible();
    await expect(submitBtn).toContainText('Generate Summary');
  });

  // ============================================================
  // 4. SUMMARY RESULT RENDERING (METADATA & MARKDOWN TABLE)
  // ============================================================
  test('4. Summary result renders word count, reading time, and structured Markdown table', async ({ page }) => {
    const tableMarkdown = `| Metric | Q1 Result | Q2 Target |\n| --- | --- | --- |\n| Revenue | $4.2M | $5.0M |\n| Latency | 42ms | 35ms |`;

    await page.route('**/summarize', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: tableMarkdown }),
      });
    });

    // Switch to Table output format
    await page.locator('.pill-btn', { hasText: 'Table' }).click();
    await expect(page.locator('.pill-btn', { hasText: 'Table' })).toHaveClass(/pill-active/);

    // Switch to Short length
    await page.locator('.pill-btn', { hasText: 'Short' }).click();
    await expect(page.locator('.pill-btn', { hasText: 'Short' })).toHaveClass(/pill-active/);

    // Upload file and submit
    await page.locator('input[type="file"]').first().setInputFiles({
      name: 'metrics.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Revenue reached $4.2M and latency was 42ms.'),
    });

    await page.locator('button[type="submit"]').click();

    // Verify metadata bar
    const metaBar = page.locator('.summary-meta-bar');
    await expect(metaBar).toBeVisible();
    await expect(metaBar).toContainText('words');
    await expect(metaBar).toContainText('characters');
    await expect(metaBar).toContainText('min read');
    await expect(metaBar).toContainText('SHORT • TABLE');

    // Verify rendered HTML table
    const table = page.locator('.summary-table');
    await expect(table).toBeVisible();
    await expect(table.locator('th').first()).toHaveText('Metric');
    await expect(table.locator('td').first()).toHaveText('Revenue');
  });

  // ============================================================
  // 5. COPY FUNCTIONALITY
  // ============================================================
  test('5. Copy button copies summary text to clipboard and toggles feedback icon', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);

    const testSummary = 'Deterministic text verified for clipboard copy action testing.';

    await page.route('**/summarize', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: testSummary }),
      });
    });

    await page.locator('input[type="file"]').first().setInputFiles({
      name: 'clipboard_test.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Clipboard source text content.'),
    });

    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.summary-card')).toBeVisible();

    // Click Copy button
    const copyBtn = page.locator('.btn-action', { hasText: 'Copy' });
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();

    // Verify copied button state feedback
    await expect(page.locator('.btn-action', { hasText: 'Copied' })).toBeVisible();
    await expect(page.locator('.btn-copied')).toBeVisible();

    // Verify clipboard contents
    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText).toBe(testSummary);
  });

  // ============================================================
  // 6. INVALID OR UNSUPPORTED INPUT HANDLING
  // ============================================================
  test('6. Validates unsupported extensions and 0-byte empty files client-side', async ({ page }) => {
    // 1. Submit button disabled when no file is chosen
    const submitBtn = page.locator('button[type="submit"]');
    await expect(submitBtn).toBeDisabled();

    // 2. Unsupported format (.exe) rejection
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: 'installer.exe',
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('MZbinarycontent'),
    });

    // Alert banner must appear immediately with unsupported message
    const alertError = page.locator('.alert-banner.alert-error');
    await expect(alertError).toBeVisible();
    await expect(alertError).toContainText('unsupported format');
    await expect(submitBtn).toBeDisabled();

    // 3. Empty file (0 bytes) rejection
    await fileInput.setInputFiles({
      name: 'empty.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(''),
    });

    await expect(alertError).toBeVisible();
    await expect(alertError).toContainText('is empty (0 bytes)');
    await expect(submitBtn).toBeDisabled();

    // 4. Valid file selection removes error and enables submit
    await fileInput.setInputFiles({
      name: 'valid.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Valid text content for processing.'),
    });

    await expect(alertError).not.toBeVisible();
    await expect(page.locator('.selected-file-card')).toBeVisible();
    await expect(submitBtn).toBeEnabled();

    // 5. Removing file restores dropzone and disables submit
    await page.locator('.remove-file-btn').click();
    await expect(page.locator('.selected-file-card')).not.toBeVisible();
    await expect(page.locator('.dropzone')).toBeVisible();
    await expect(submitBtn).toBeDisabled();
  });

  // ============================================================
  // 7. API FAILURE MESSAGING
  // ============================================================
  test('7. Displays clear, user-actionable error banners on backend API failures (400 and 500)', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]').first();
    const submitBtn = page.locator('button[type="submit"]');

    // Case A: Rate limit 500 error from Groq
    await page.route('**/summarize', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Groq API rate limit reached during summarization. Please wait a moment and try again.',
        }),
      });
    });

    await fileInput.setInputFiles({
      name: 'doc1.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Text payload.'),
    });

    await submitBtn.click();

    const alertError = page.locator('.alert-banner.alert-error');
    await expect(alertError).toBeVisible();
    await expect(alertError).toContainText('Groq API rate limit reached during summarization');
    await expect(page.locator('.summary-card')).not.toBeVisible();

    // Case B: Document oversized 400 guard directing to Hierarchical summarizer
    await page.route('**/summarize', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Document exceeds 60,000 characters (~15,000 words) for direct summarization. Please use the Hierarchical Summarizer (Map-Reduce) feature for large documents.',
        }),
      });
    });

    await submitBtn.click();
    await expect(alertError).toBeVisible();
    await expect(alertError).toContainText('Hierarchical Summarizer');

    // Case C: Network drop / connection failure
    await page.route('**/summarize', async (route) => {
      await route.abort('failed');
    });

    await submitBtn.click();
    await expect(alertError).toBeVisible();
  });

});
