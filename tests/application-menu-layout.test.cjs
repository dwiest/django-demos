const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

test('shared page styles cannot resize the Apps panel when switching tabs', async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}),
  });
  try {
    const fixture = fs.readFileSync(process.env.APPLICATION_NAVIGATION_FIXTURE, 'utf8');
    const componentRoot = 'dwiest/django/demos/templates/dwiest-django-demos/components/';
    const staticRoot = 'dwiest/django/demos/static/dwiest-django-demos/';
    const navigation = fs.readFileSync(componentRoot + 'navigation.css', 'utf8');
    const pageStyles = ['bookmarks/ui.css', 'demo_ui.css']
      .map(name => fs.readFileSync(staticRoot + name, 'utf8')).join('\n');
    const html = fixture.replace('<body>',
      '<body>' + navigation + '<style>' + pageStyles + '</style>' +
      '<div class="ww-site-header"><div class="ww-site-inner">')
      .replace('</body>', '</div></div></body>');
    for (const [width, height] of [[320,568],[390,844],[650,844],[660,844],[1024,600],[1352,826],[1920,1080]]) {
      const page = await browser.newPage();
      await page.setViewportSize({ width, height });
      await page.setContent(html);
      await page.locator('.ww-apps > summary').click();
      let initial;
      for (const category of ['applications', 'toys', 'services', 'applications']) {
        await page.locator('[data-app-category="' + category + '"]').click();
        const box = await page.locator('.ww-apps-panel').boundingBox();
        const bounds = [box.x, box.y, box.width, box.height];
        if (!initial) initial = bounds;
        else assert.deepEqual(bounds, initial, width + 'px: ' + category + ' resized the menu');
        assert.ok(box.x >= 0 && box.x + box.width <= width + 1);
        assert.ok(box.y + box.height <= height + 1);
        assert.equal(await page.getByRole('tabpanel').count(), 1);
        if (category === 'toys') {
          const panel = page.getByRole('tabpanel');
          assert.equal(await panel.getByRole('heading', { name: 'Desktop toys', exact: true }).count(), 0);
          const link = await panel.getByRole('link', { name: 'View all toys →' }).boundingBox();
          const arcade = await panel.getByRole('heading', { name: 'Arcade', exact: true }).boundingBox();
          assert.ok(Math.abs(link.y + link.height / 2 - arcade.y - arcade.height / 2) < 1);
          if (width > 650) {
            const ambient = await panel.getByRole('heading', { name: 'Ambient', exact: true }).boundingBox();
            assert.ok(Math.abs(link.y + link.height / 2 - ambient.y - ambient.height / 2) < 1);
          }
        }
        for (const link of await page.locator('.ww-app-panel[hidden] a').all()) {
          await link.evaluate(element => element.focus());
          assert.equal(await link.evaluate(element => element === document.activeElement), false);
        }
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }
});
