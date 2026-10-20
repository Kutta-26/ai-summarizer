import { test, expect } from '@playwright/test';

/**
 * Live Integration Test Suite
 *
 * Requirements:
 * 1. Docker Compose services must be running:
 *    - Backend at http://localhost:8000
 *    - Frontend at http://localhost:3000
 * 2. GROQ_API_KEY must be configured in backend/.env or environment.
 *
 * To execute live tests:
 *    $env:LIVE_E2E="true"; npx playwright test e2e/live-summarizer.spec.js
 */
test.describe('AI Summarizer — Live Backend End-to-End Integration', () => {

  test('Live single-document summarization with Groq Cloud LLM', async ({ page }) => {
    test.skip(
      process.env.LIVE_E2E !== 'true',
      'Skipping live API test. Set LIVE_E2E="true" with active GROQ_API_KEY to run live end-to-end tests.'
    );

    await page.goto('/');

    // Verify backend status is online
    const statusPill = page.locator('.status-pill');
    await expect(statusPill).toContainText('Backend Connected', { timeout: 10000 });

    // Upload real sample text
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: 'live_test.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(
        'Artificial intelligence and cloud computing have enabled scalable automated text analysis across enterprises.'
      ),
    });

    // Select Short and Paragraph
    await page.locator('.pill-btn', { hasText: 'Short' }).click();
    await page.locator('.pill-btn', { hasText: 'Paragraph' }).click();

    // Submit request to live backend
    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();

    // Await live LLM response (up to 30s)
    const summaryCard = page.locator('.summary-card');
    await expect(summaryCard).toBeVisible({ timeout: 30000 });

    const summaryContent = page.locator('.summary-content');
    await expect(summaryContent).not.toBeEmpty();
    const text = await summaryContent.innerText();
    expect(text.length).toBeGreaterThan(15);
  });

});
