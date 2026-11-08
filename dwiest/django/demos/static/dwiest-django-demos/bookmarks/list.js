export function initList() {
  const list = document.getElementById('bookmark-list');
  if (!list) return;
  let density = 'compact';
  try { density = localStorage.getItem('bookmarks.density') || density; } catch {}
  const applyDensity = value => {
    list.classList.toggle('expanded', value === 'expanded');
    document.querySelectorAll('[data-density]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.density === value)));
    try { localStorage.setItem('bookmarks.density', value); } catch {}
  };
  document.querySelectorAll('[data-density]').forEach(button => button.addEventListener('click', () => applyDensity(button.dataset.density)));
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
