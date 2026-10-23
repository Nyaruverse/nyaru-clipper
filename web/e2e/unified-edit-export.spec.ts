import { expect, test } from '@playwright/test';

test('edits a Workstation result through the actual Companion API and retains 4999 cues', async ({page, request, context}, testInfo) => {
  const jobsResponse = await request.get('/companion-api/jobs');
  expect(jobsResponse.ok()).toBe(true);
  const jobs: unknown = await jobsResponse.json();
  expect(Array.isArray(jobs)).toBe(true);
  if (!Array.isArray(jobs)) throw new Error('Fixture jobs must be a list');
  const first: unknown = jobs[0];
  if (typeof first !== 'object' || first === null || !('id' in first) || typeof first.id !== 'string') {
    throw new Error('Fixture task ID is missing');
  }
  const url = `/companion-api/jobs/${first.id}/subtitle-document`;
  const beforeResponse = await request.get(url);
  const {parseDocument} = await import('../src/companion/subtitleDocument');
  const before = parseDocument(await beforeResponse.json());
  expect(before.cues).toHaveLength(5000);
  const editedText = `已保存的工作站修改 ${before.revision + 1}`;
  const second = await context.newPage();
  await second.goto('/');
  await second.getByRole('button', {name: '编辑当前字幕', exact: true}).click();
  await expect(second.getByLabel('本条原文')).toBeVisible();
  await page.goto('/');
  await page.getByRole('button', {name: '编辑当前字幕', exact: true}).click();
  await expect(page.getByLabel('本条原文')).toBeVisible({timeout: 30_000});
  await page.getByLabel('本条原文').fill(editedText);
  await expect.poll(async () => {
    const response = await request.get(url);
    const draft = parseDocument(await response.json());
    return draft.cues[0]?.text;
  }, {timeout: 30_000}).toBe(editedText);
  const saved = parseDocument(await (await request.get(url)).json());
  expect(saved.cues.slice(1)).toEqual(before.cues.slice(1));
  expect(saved.revision).toBe(before.revision + 1);
  await page.reload();
  await page.getByRole('button', {name: '编辑当前字幕', exact: true}).click();
  await expect(page.getByLabel('本条原文')).toHaveValue(editedText);
  await page.getByRole('button', {name: '导出', exact: true}).click();
  await expect(page.getByRole('link', {name: '完整双语字幕 SRT'})).toHaveAttribute('href', /subtitles\.zh-ja\.srt/);
  const screenshot = testInfo.outputPath('workstation-edited.png');
  await page.screenshot({path: screenshot, fullPage: true});
  await testInfo.attach('Workstation editor', {path: screenshot, contentType: 'image/png'});
  const staleResponse = second.waitForResponse(response => response.url().endsWith(url) && response.request().method() === 'POST');
  await second.getByLabel('本条原文').fill('stale second client');
  expect((await staleResponse).status()).toBe(409);
  await expect(second.getByLabel('本条原文')).toHaveValue('stale second client');
  await expect(second.getByRole('alert').filter({hasText: '字幕版本冲突'})).toBeVisible();
  expect(parseDocument(await (await request.get(url)).json()).cues[0]?.text).toBe(editedText);
  await second.close();
});
