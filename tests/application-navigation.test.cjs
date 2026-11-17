const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');

const fixture = fs.readFileSync(process.env.APPLICATION_NAVIGATION_FIXTURE, 'utf8');
const script = fs.readFileSync('dwiest/django/demos/templates/dwiest-django-demos/components/navigation.js', 'utf8').replace(/<\/?script>/g, '');

function page() {
  const dom = new JSDOM(fixture, { runScripts: 'outside-only' });
  dom.window.eval(script);
  return dom;
}

test('actual rendered categories select exactly one panel and support keyboard navigation', () => {
  const dom = page();
  const d = dom.window.document;
  const tabs = [...d.querySelectorAll('[role=tab]')];
  assert.deepEqual(tabs.map(t => t.textContent), ['Applications', 'Desktop toys', 'Services']);
  assert.equal(d.querySelectorAll('[role=tabpanel]:not([hidden])').length, 1);
  assert.equal(tabs[0].getAttribute('aria-selected'), 'true');
  tabs[1].click();
  assert.equal(tabs[1].getAttribute('aria-selected'), 'true');
  assert.equal(d.querySelector('[data-app-panel=toys]').hidden, false);
  assert.equal(d.querySelector('[data-app-panel=applications]').hidden, true);
  assert.equal(d.querySelector('[data-app-panel=toys] .ww-apps-grid a').textContent, 'Spinning Sticks');
  assert.equal(d.querySelector('[data-app-panel=toys] .ww-app-count').textContent, '13 toys');
  tabs[1].dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
  assert.equal(d.activeElement, tabs[2]);
  assert.equal(tabs[2].tabIndex, 0);
  assert.equal(tabs[1].tabIndex, -1);
  tabs[2].dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Home', bubbles: true}));
  assert.equal(d.activeElement, tabs[0]);
  tabs[0].dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'End', bubbles: true}));
  assert.equal(d.activeElement, tabs[2]);
  tabs[2].dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
  assert.equal(d.activeElement, tabs[0]);
  tabs[0].dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true}));
  assert.equal(d.activeElement, tabs[2]);
  dom.window.close();
});

test('Escape restores focus, outside click and focus exit dismiss menus, unrelated details stay open', () => {
  const dom = page();
  const d = dom.window.document;
  const apps = d.querySelector('.ww-apps');
  apps.open = true;
  d.querySelector('[data-app-category=toys]').focus();
  d.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  assert.equal(apps.open, false);
  assert.equal(d.activeElement, apps.querySelector('summary'));
  apps.open = true;
  d.getElementById('outside').click();
  assert.equal(apps.open, false);
  apps.open = true;
  d.getElementById('outside').focus();
  assert.equal(apps.open, false);
  assert.equal(d.getElementById('filters').open, true);
  apps.open = true;
  d.getElementById('account').open = true;
  d.getElementById('account').dispatchEvent(new dom.window.Event('toggle'));
  assert.equal(apps.open, false);
  dom.window.close();
});

test('without JavaScript, Home and links from every available category remain accessible', () => {
  const dom = new JSDOM(fixture);
  const d = dom.window.document;
  assert.equal(d.querySelector('.ww-apps-home').getAttribute('href'), '/django/home/');
  assert.equal(d.querySelectorAll('[data-app-panel][hidden]').length, 0);
  for (const title of ['Bookmarks', 'Pixel Fireworks', 'Voicemail']) {
    assert.ok([...d.querySelectorAll('nav a')].some(a => a.textContent === title));
  }
  dom.window.close();
});
