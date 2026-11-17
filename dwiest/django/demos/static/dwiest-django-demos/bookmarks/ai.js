document.addEventListener('submit', event => {
  const button = event.submitter;
  if (!button || !(button.matches('[data-ai-analyze]') || button.matches('[data-ai-apply]'))) return;
  const form = event.target;
  if (form.dataset.aiBusy) { event.preventDefault(); return; }
  form.dataset.aiBusy = 'true';
  const status = form.querySelector('[data-ai-status]');
  if (status) status.textContent = button.matches('[data-ai-analyze]') ? 'Retrieving and analyzing the article…' : 'Applying your approved changes…';
  // Disable after the browser captures the submitter's action value.
  setTimeout(() => { form.querySelectorAll('button').forEach(item => { item.disabled = true; }); }, 0);
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('[data-ai-busy]').forEach(form => {
    delete form.dataset.aiBusy;
    form.querySelectorAll('button').forEach(button => { button.disabled = false; });
    const status = form.querySelector('[data-ai-status]');
    if (status) status.textContent = '';
  });
});

// Warn as the URL changes, without blocking an explicit analysis attempt.
const editor = document.querySelector('[data-editor]');
const siteRules = document.getElementById('ai-site-blacklist');
if (editor && siteRules) {
  const domains = JSON.parse(siteRules.textContent);
  const warning = editor.querySelector('[data-ai-site-warning]');
  const attempted = editor.querySelector('[data-ai-last-attempt]');
  const urlInput = editor.elements.url;
  const refresh = () => {
    let domain;
    try {
      const value = urlInput.value.trim();
      const parsed = new URL(value.includes('://') ? value : 'https://' + value);
      const host = parsed.hostname.toLowerCase().replace(/\.$/, '').replace(/^www\./, '');
      if (['http:', 'https:'].includes(parsed.protocol)) {
        domain = domains.find(entry => host === entry || host.endsWith('.' + entry));
      }
    } catch (_) { /* An incomplete URL has no site warning. */ }
    if (warning) {
      warning.hidden = !domain;
      warning.textContent = domain ? domain + ' is on your AI site blacklist. You can still use Analyze to retry.' : '';
    }
    if (attempted) attempted.hidden = !attempted.textContent.trim() || urlInput.value.trim() !== attempted.dataset.attemptUrl;
  };
  urlInput.addEventListener('input', refresh);
  urlInput.addEventListener('change', refresh);
  editor.addEventListener('input', refresh);
  window.addEventListener('pageshow', refresh);
  refresh();
}

const enrichment = document.querySelector('[data-enrichment][data-active]');
if (enrichment) {
  let busy = false;
  const check = async () => {
    if (busy) return;
    busy = true;
    try {
      const response = await fetch(location.pathname, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': enrichment.querySelector('[name=csrfmiddlewaretoken]').value},
        body: 'action=advance',
      });
      if (!response.ok) throw new Error('Progress check failed. Reload the page to try again.');
      const data = await response.json();
      if (data.terminal) { location.reload(); return; }
      document.querySelector('[data-enrichment-status]').textContent = data.status;
      document.querySelector('[data-enrichment-message]').textContent = data.message || '';
      const fields = {
        retrieval: data.retrieval_job_id || 'Not submitted yet',
        analysis: data.analysis_job_id || 'Not submitted yet',
        remote: data.remote_status || 'Not checked yet',
        updated: data.updated_at || '',
        lease: data.lease_until || 'None',
        retry: data.retry_after || 'None',
      };
      for (const [name, value] of Object.entries(fields)) {
        const target = document.querySelector('[data-enrichment-' + name + ']');
        if (target) {
          const href = name === 'retrieval' ? data.retrieval_url : name === 'analysis' ? data.analysis_url : '';
          if (href && href.startsWith('/') && !href.startsWith('//')) {
            const link = document.createElement('a'); link.href = href; link.textContent = value; target.replaceChildren(link);
          } else target.textContent = value;
        }
      }
      const seconds = Math.max(3, Math.min(90, Number(data.poll_after_seconds) || 3));
      setTimeout(check, seconds * 1000);
    } catch (error) {
      document.querySelector('[data-enrichment-message]').textContent = error.message;
    } finally { busy = false; }
  };
  enrichment.addEventListener('submit', event => {
    if (event.submitter?.value === 'advance') { event.preventDefault(); check(); }
  });
  check();
}

// Grow long titles/URLs without changing their validation or submitted values.
const autosize = field => {
  field.style.height = 'auto';
  field.style.height = Math.max(field.scrollHeight + 2, 42) + 'px';
};
document.querySelectorAll('textarea[data-autosize]').forEach(field => {
  field.addEventListener('input', () => autosize(field));
  autosize(field);
  if (window.ResizeObserver) new ResizeObserver(() => {
    if (field.clientWidth !== Number(field.dataset.lastWidth)) {
      field.dataset.lastWidth = field.clientWidth; autosize(field);
    }
  }).observe(field);
});

// Render arbitrary JSON using text nodes only, including adversarial article data.
document.querySelectorAll('[data-json-view]').forEach(view => {
  const raw = view.querySelector('[data-json-raw]').textContent;
  const value = JSON.parse(raw);
  const pre = view.querySelector('[data-json-pre]');
  const tableView = view.querySelector('[data-json-table]');
  const table = document.createElement('table');
  const head = document.createElement('thead'), heading = document.createElement('tr');
  for (const label of ['Key', 'Value']) { const th = document.createElement('th'); th.textContent = label; heading.append(th); }
  head.append(heading); table.append(head);
  const body = document.createElement('tbody');
  function row(path, item) {
    if (item !== null && typeof item === 'object' && Object.keys(item).length) {
      for (const [key, child] of Object.entries(item)) row(path ? path + '.' + key : key, child);
    } else {
      const tr = document.createElement('tr'), key = document.createElement('th'), content = document.createElement('td');
      key.scope = 'row'; key.textContent = path || '(value)';
      content.textContent = typeof item === 'string' ? item : JSON.stringify(item);
      tr.append(key, content); body.append(tr);
    }
  }
  row('', value); table.append(body); tableView.append(table);
  view.querySelector('[data-json-mode]').addEventListener('change', event => {
    const mode = event.target.value;
    pre.hidden = mode === 'table'; tableView.hidden = mode !== 'table';
    pre.textContent = mode === 'raw' ? raw : JSON.stringify(value, null, 2);
  });
});

const reviewTags = document.querySelector('[data-tag-editor]');
if (reviewTags) {
  const form = document.querySelector('[data-ai-review]');
  const source = form.elements.tags;
  const current = JSON.parse(document.getElementById('review-current-tags').textContent);
  const available = new Set([...document.querySelectorAll('#available-tags option')].map(option => option.value.toLocaleLowerCase()));
  const baseline = new Map(current.map(name => [name.toLocaleLowerCase(), name]));
  let tags = [...new Map(source.value.split(/\r?\n/).map(s => s.trim()).filter(Boolean).map(s => [s.toLocaleLowerCase(), s])).values()];
  const list = reviewTags.querySelector('[data-tag-items]'), removed = reviewTags.querySelector('[data-tag-removed]');
  const input = reviewTags.querySelector('input'), feedback = reviewTags.querySelector('[data-tag-feedback]');
  function button(label, action) {
    const control = document.createElement('button'); control.type = 'button'; control.className = 'button secondary'; control.textContent = label;
    control.addEventListener('click', action); return control;
  }
  function draw() {
    tags.sort((a, b) => a.localeCompare(b, undefined, {sensitivity: 'base'}));
    source.value = tags.join('\n'); list.replaceChildren(); removed.replaceChildren();
    const selected = new Set(tags.map(name => name.toLocaleLowerCase()));
    for (const name of tags) {
      const item = document.createElement('li');
      const added = !baseline.has(name.toLocaleLowerCase());
      const label = document.createElement('span'); label.textContent = name;
      const state = document.createElement('small');
      state.textContent = added ? (available.has(name.toLocaleLowerCase()) ? 'Added assignment' : 'New tag') : 'Kept';
      item.dataset.change = added ? 'added' : 'kept'; item.append(label, state, button('Remove ' + name, () => {
        tags = tags.filter(tag => tag !== name); draw(); feedback.textContent = 'Removed ' + name + '.';
        input.focus();
      })); list.append(item);
    }
    for (const [key, name] of baseline) if (!selected.has(key)) {
      const item = document.createElement('p'); item.dataset.change = 'removed';
      const label = document.createElement('span'); label.textContent = 'Removed: ' + name + ' ';
      item.append(label, button('Undo removal of ' + name, () => { tags.push(name); draw(); feedback.textContent = 'Restored ' + name + '.'; input.focus(); })); removed.append(item);
    }
    feedback.textContent = tags.length + ' selected tag' + (tags.length === 1 ? '' : 's') + '. Changes apply only when Tags is selected and you approve.';
  }
  function add() {
    const name = input.value.trim();
    if (!name) return;
    if (name.includes('\n') || name.length > 255 || tags.length >= 30) { feedback.textContent = 'Use one tag name of at most 255 characters; choose at most 30 tags.'; return; }
    if (tags.some(tag => tag.toLocaleLowerCase() === name.toLocaleLowerCase())) { feedback.textContent = 'That tag is already selected.'; return; }
    const canonical = [...document.querySelectorAll('#available-tags option')].find(option => option.value.toLocaleLowerCase() === name.toLocaleLowerCase());
    tags.push(canonical ? canonical.value : name); input.value = ''; draw(); input.focus();
  }
  reviewTags.querySelector('[data-add-tag]').addEventListener('click', add);
  input.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); add(); } });
  // Keep the original textarea as a no-JavaScript fallback and the server field.
  source.hidden = true; source.closest('.field').querySelector('label').hidden = true;
  reviewTags.hidden = false; draw();
}
