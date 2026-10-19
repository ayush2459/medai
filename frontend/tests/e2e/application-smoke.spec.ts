import { test, expect } from '@playwright/test';

test('frontend loads without a browser-level failure', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));

  const response = await page.goto('/');
  expect(response, 'Frontend server must be running on port 5173').not.toBeNull();
  expect(response!.status()).toBeLessThan(500);

  await expect(page.locator('body')).not.toBeEmpty();
  await page.waitForLoadState('domcontentloaded');

  expect(errors, 'Uncaught browser JavaScript errors').toEqual([]);
});

test('local navigation links do not produce server errors', async ({ page }) => {
  const response = await page.goto('/');
  expect(response).not.toBeNull();
  expect(response!.status()).toBeLessThan(500);

  const links = await page.locator('a[href]').evaluateAll(anchors =>
    anchors.map(a => (a as HTMLAnchorElement).getAttribute('href'))
      .filter((href): href is string =>
        !!href && href.startsWith('/') && !href.startsWith('//'))
  );

  const paths = [...new Set(links)].slice(0, 30);
  for (const path of paths) {
    const result = await page.request.get(path);
    expect(
      result.status(),
      `${path} returned HTTP ${result.status()}`
    ).toBeLessThan(500);
  }
});
