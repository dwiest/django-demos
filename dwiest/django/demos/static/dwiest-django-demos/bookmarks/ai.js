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
        if (target) target.textContent = value;
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
