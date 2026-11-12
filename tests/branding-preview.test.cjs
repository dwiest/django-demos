// Run with: node --test tests/branding-preview.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');

test('repeated and alternating previews get fresh sandboxed frames', async () => {
  let frame;
  const newFrame = () => ({
    sandbox: '', srcdoc: '',
    cloneNode() { return newFrame(); },
    replaceWith(next) { frame = next; },
    removeAttribute(name) { delete this[name]; },
  });
  frame = newFrame();
  const listeners = {};
  const close = {addEventListener(type, fn) { this.click = fn; }};
  const dialog = {
    dataset: {previewUrl: '/preview/'},
    querySelector(selector) { return selector === 'iframe' ? frame : close; },
    addEventListener(type, fn) { listeners[type] = fn; },
    showModal() { this.open = true; },
    close() { this.open = false; listeners.close(); },
  };
  const buttons = ['store', 'email'].map(kind => ({
    dataset: {brandingPreview: kind},
    addEventListener(type, fn) { this.click = fn; },
    focus() { this.focused = true; },
  }));
  const error = {textContent: ''};
  const title = {};
  const document = {
    querySelector(selector) {
      if (selector === '[data-branding-dialog]') return dialog;
      if (selector === '[data-preview-error]') return error;
      if (selector === '#branding-preview-title') return title;
      return {};
    },
    querySelectorAll() { return buttons; },
  };
  let requests = 0;
  runInNewContext(readFileSync('dwiest/django/demos/static/dwiest-django-demos/store/branding-preview.v2.js', 'utf8'), {
    document,
    FormData: class { set(key, value) { this[key] = value; } },
    fetch: async (url, options) => {
      requests++;
      return {ok: true, text: async () => `<p>${options.body.preview_kind} draft ${requests}</p>`};
    },
  });
  const frames = new Set([frame]);
  for (const index of [0, 0, 1, 1, 0, 1]) {
    await buttons[index].click();
    assert.equal(dialog.open, true);
    assert.equal(frames.has(frame), false);
    frames.add(frame);
    assert.match(frame.srcdoc, new RegExp(`${buttons[index].dataset.brandingPreview} draft ${requests}`));
    assert.equal(frame.sandbox, '');
    assert.equal(error.textContent, '');
    close.click();
    assert.equal(dialog.open, false);
    assert.equal(buttons[index].focused, true);
  }
  assert.equal(requests, 6);
});
