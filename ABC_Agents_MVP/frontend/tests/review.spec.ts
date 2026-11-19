import { test, expect } from '@playwright/test';

test('mock demo from upload to independent rounds and report export', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('Simulated data. No model calls are made.')).toBeVisible();
  await page.getByRole('button', { name: 'Load demo' }).click();
  const project = page.getByLabel('Project name');
  await expect(project).toHaveValue('AI Security Alarm Verification Service');
  await project.fill('AI Security Alarm Verification Service');
  await page.locator('input[type=file]').first().setInputFiles({
    name: 'baseline.md', mimeType: 'text/markdown',
    buffer: Buffer.from('# Test note\nNo measured baseline is available.'),
  });
  await expect(page.getByText('baseline.md')).toBeVisible();
  await page.getByRole('button', { name: 'Save assessment' }).click();
  await page.getByRole('button', { name: 'Start review' }).click();
  await expect(page.locator('.agent-grid h2')).toHaveText(['Sufficiency', 'Orchestrator', 'Necessity']);
  await expect(page.getByRole('button', { name: 'Decision report' })).toBeVisible();
  await expect(page.locator('.agent-B .round summary')).toHaveText(['Round 1', 'Round 2']);
  await expect(page.locator('.agent-C .round summary')).toHaveText(['Round 1', 'Round 2']);
  await expect(page.locator('.agent-C .callout').first()).toContainText('Cross-examination');
  await page.getByRole('button', { name: 'Decision report' }).click();
  await expect(page.locator('.report-section')).toHaveCount(10);
  await expect(page.locator('.decision-banner')).toContainText('Gather more evidence');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export JSON' }).click();
  const file = await download;
  const stream = await file.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk);
  const report = JSON.parse(Buffer.concat(chunks).toString());
  expect(report.mode).toBe('mock');
  expect(report.audit.filter((record: { round: number | null }) => record.round === 1)).toHaveLength(2);
  expect(report.decision.state).toBe('evidence_required');
  expect(report.necessity.willingness_to_pay).toBe('unknown');
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.report-section').last()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Export JSON' })).toBeHidden();
  await page.emulateMedia({ media: 'screen' });
  await page.getByRole('button', { name: '中文' }).click();
  await expect(page.getByRole('heading', { name: '决策报告' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  expect(errors).toEqual([]);
});
