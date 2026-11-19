(() => {
  'use strict';
  function duration(value) {
    const total = Math.max(0, Math.floor(value));
    const hours = Math.floor(total / 3600), minutes = Math.floor(total % 3600 / 60), seconds = total % 60;
    const parts = [];
    if (hours) parts.push(hours + ' hour' + (hours === 1 ? '' : 's'));
    if (minutes || hours) parts.push(minutes + ' minute' + (minutes === 1 ? '' : 's'));
    parts.push(seconds + ' second' + (seconds === 1 ? '' : 's'));
    return parts.join(', ');
  }
  const timer = document.querySelector('#job-elapsed');
  let started = timer && timer.dataset ? Number(timer.dataset.started) : 0;
  let stopped = false;
  function tick() {
    if (stopped) return;
    if (timer && started) timer.textContent = duration(Date.now() / 1000 - started);
    window.setTimeout(tick, 1000);
  }
  if (started) tick();
  const panel = document.querySelector('[data-job-poll]');
  if (!panel) return;
  const status = document.querySelector('#job-state');
  const stage = document.querySelector('#job-stage');
  const error = document.querySelector('#job-poll-error');
  window.addEventListener('pagehide', () => { stopped = true; });
  async function poll() {
    if (stopped) return;
    try {
      const response = await fetch(panel.dataset.jobPoll, {credentials: 'same-origin', redirect: 'error', cache: 'no-store'});
      if (!response.ok) throw new Error('Status could not be refreshed. Check your session or refresh this page.');
      const result = await response.json();
      if (result.job.started_at && !started) { started = Number(result.job.started_at); tick(); }
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
