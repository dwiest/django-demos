import { initTagPicker } from './tags.js';
export function initEditor(form) {
  const baseline = JSON.parse(document.getElementById('editor-baseline').textContent);
  const controls = form.querySelector('.dirty-controls');
  const refreshTags = initTagPicker(form.querySelector('[data-tag-picker]'));
  let dirty = false, submitting = false;
  const state = () => {
    const result = {};
    for (const name of ['url','title','description','article_date','status']) result[name] = form.elements[name].value;
    result.unread = form.elements.unread.checked;
    result.tag_ids = [...form.querySelectorAll('[name=tag_ids]:checked')].map(input => input.value).sort();
    return result;
  };
  for (const name of ['url','title','description']) baseline[name] = baseline[name].replace(/\r\n?/g, '\n');
  baseline.tag_ids.sort();
  const refresh = () => {
    dirty = JSON.stringify(state()) !== JSON.stringify(baseline);
    controls.hidden = !dirty;
    const link = form.querySelector('[data-open-link]');
    try {
      const url = new URL(form.elements.url.value);
      link.hidden = !['https:', 'http:'].includes(url.protocol);
      if (!link.hidden) link.href = url.href;
    } catch { link.hidden = true; }
  };
  form.addEventListener('input', refresh); form.addEventListener('change', refresh);
  form.querySelector('[data-reset]').addEventListener('click', () => {
    if (!confirm('Discard the changes made in this editor?')) return;
    for (const name of ['url','title','description','article_date','status']) form.elements[name].value = baseline[name];
    form.elements.unread.checked = baseline.unread;
    form.querySelectorAll('[name=tag_ids]').forEach(input => input.checked = baseline.tag_ids.includes(input.value));
    const search = form.querySelector('[data-tag-search]'); search.value = ''; search.dispatchEvent(new Event('input'));
    refreshTags(); refresh(); form.elements.url.focus();
  });
  // Let the browser handle departures, including Cancel, Back, reload and closing.
  window.addEventListener('beforeunload', event => {
    if (dirty && !submitting) { event.preventDefault(); event.returnValue = ''; }
  });
  form.addEventListener('submit', () => { submitting = true; });
  form.querySelectorAll('.field').forEach(field => {
    if (field.querySelector('.error')) field.querySelector('.control')?.setAttribute('aria-invalid', 'true');
  });
  form.querySelector('[data-error-summary]')?.focus();
  refresh();
}
