export function initList() {
  const list = document.getElementById('bookmark-list');
  if (!list) return;
  let density = 'compact';
  try { density = localStorage.getItem('bookmarks.density') || density; } catch {}
  const rows = [...list.querySelectorAll('[data-bookmark-row]')];
  const updateRow = row => {
    const disclosure = row.querySelector('[data-bookmark-disclosure]');
    if (!disclosure) return;
    const expanded = list.classList.contains('expanded') || row.classList.contains('is-expanded');
    disclosure.hidden = list.classList.contains('expanded');
    disclosure.setAttribute('aria-expanded', String(expanded));
    const title = row.querySelector('.bookmark-title')?.textContent.trim() || 'bookmark';
    disclosure.setAttribute('aria-label', (expanded ? 'Hide' : 'Show') + ' details for ' + title);
    disclosure.textContent = expanded ? '▾' : '▸';
  };
  const toggleRow = row => {
    if (list.classList.contains('expanded')) return;
    row.classList.toggle('is-expanded');
    if (!row.classList.contains('is-expanded')) row.querySelectorAll('details[open]').forEach(details => { details.open = false; });
    updateRow(row);
  };
  rows.forEach(row => {
    row.querySelector('[data-bookmark-disclosure]')?.addEventListener('click', () => toggleRow(row));
    row.addEventListener('click', event => {
      if (event.target.closest('a, button, input, select, textarea, label, summary, details, form, [contenteditable]')) return;
      // Selecting article text should not unexpectedly hide it.
      if (window.getSelection()?.toString().trim()) return;
      toggleRow(row);
    });
  });
  const applyDensity = value => {
    density = value === 'expanded' ? 'expanded' : 'compact';
    list.classList.toggle('expanded', density === 'expanded');
    rows.forEach(updateRow);
    document.querySelectorAll('[data-density]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.density === density)));
    try { localStorage.setItem('bookmarks.density', density); } catch {}
  };
  document.querySelectorAll('[data-density]').forEach(button => button.addEventListener('click', () => applyDensity(button.dataset.density)));
  list.classList.add('is-enhanced');
  applyDensity(density);
  list.querySelectorAll('[data-row-action]').forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.submitter || form.querySelector('button');
    const data = new FormData(form); data.set('action', button.value);
    button.disabled = true;
    const status = document.getElementById('action-status');
    try {
      const response = await fetch(form.action, { method: 'POST', body: data, headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Save failed');
      const saved = await response.json();
      button.value = saved.unread ? 'read' : 'unread';
      button.title = saved.unread ? 'Mark as read' : 'Mark as unread'; button.setAttribute('aria-label', button.title);
      button.querySelector('span').textContent = saved.unread ? '●' : '○';
      // Reload when an unread-only result disappears, so count and pagination stay correct.
      if (!saved.unread && document.querySelector('[name=hide_read]')?.checked) { location.reload(); return; }
      status.textContent = saved.unread ? 'Marked as unread.' : 'Marked as read.';
    } catch { status.textContent = 'Could not change read status. Please try again.'; }
    finally { button.disabled = false; status.hidden = false; }
  }));
}
