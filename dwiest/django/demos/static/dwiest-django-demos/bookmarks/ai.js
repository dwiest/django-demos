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
