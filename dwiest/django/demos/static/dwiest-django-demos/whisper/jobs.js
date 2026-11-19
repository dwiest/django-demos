(() => {
  'use strict';
  const panel = document.querySelector('[data-job-poll]');
  if (!panel) return;
  const status = document.querySelector('#job-state');
  const stage = document.querySelector('#job-stage');
  const error = document.querySelector('#job-poll-error');
  let stopped = false;
  window.addEventListener('pagehide', () => { stopped = true; });
  async function poll() {
    if (stopped) return;
    try {
      const response = await fetch(panel.dataset.jobPoll, {credentials: 'same-origin', redirect: 'error', cache: 'no-store'});
      if (!response.ok) throw new Error('Status could not be refreshed. Check your session or refresh this page.');
      const result = await response.json();
      status.textContent = result.job.status;
      stage.textContent = 'Stage: ' + result.job.stage;
      error.textContent = '';
      if (['completed', 'failed', 'cancelled', 'deleting', 'deleted'].includes(result.job.status)) {
        stopped = true;
        window.location.reload();
        return;
      }
    } catch (exc) { error.textContent = exc.message; }
    if (!stopped) window.setTimeout(poll, 5000);
  }
  window.setTimeout(poll, 3000);
})();
