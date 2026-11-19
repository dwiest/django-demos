/* Direct-to-S3 upload; only metadata and authenticated operations pass through Django. */
(() => {
  'use strict';
  async function jsonRequest(url, payload, token, key) {
    const headers = {'Content-Type': 'application/json', 'X-CSRFToken': token};
    if (key) headers['Idempotency-Key'] = key;
    const response = await fetch(url, {method: 'POST', credentials: 'same-origin', redirect: 'error', headers, body: JSON.stringify(payload)});
    let result;
    try { result = await response.json(); } catch (_) { throw new Error('The server did not return upload details. Check your session and retry.'); }
    if (!response.ok) {
      const error = new Error(result.message || 'The request failed. Retry the same operation.');
      error.status = response.status;
      throw error;
    }
    return result;
  }
  function sendFile(upload, file, progress) {
    return new Promise((resolve, reject) => {
      const data = new FormData();
      Object.entries(upload.fields).forEach(([key, value]) => data.append(key, value));
      data.append('file', file); // S3 requires the file field last.
      const xhr = new XMLHttpRequest();
      xhr.open('POST', upload.url);
      xhr.timeout = 3600000;
      xhr.upload.onprogress = event => { if (event.lengthComputable) progress.value = Math.round(event.loaded / event.total * 100); };
      xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error('Storage rejected the upload. Retry; if it continues, check the S3 upload configuration.'));
      xhr.onerror = () => reject(new Error('Upload interrupted. Check your connection and retry.'));
      xhr.ontimeout = () => reject(new Error('Upload timed out. Retry with a stable connection.'));
      xhr.send(data);
    });
  }
  const form = document.querySelector('#media-upload');
  if (form) {
    const fileInput = document.querySelector('#media-file');
    const name = document.querySelector('#media-name');
    const days = document.querySelector('#media-days');
    const forever = document.querySelector('#media-forever');
    const status = document.querySelector('#upload-status');
    const error = document.querySelector('#upload-error');
    const progress = document.querySelector('#upload-progress');
    const review = document.querySelector('#upload-review');
    const submit = document.querySelector('#upload-submit');
    let pending;
    forever.addEventListener('change', () => { days.disabled = forever.checked; days.required = !forever.checked; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const file = fileInput.files[0];
      if (!file) return;
      error.hidden = true;
      review.hidden = true;
      if (file.size < 1 || file.size > 1073741824) { error.textContent = 'Choose a file between 1 byte and 1 GiB.'; error.hidden = false; return; }
      const payload = {original_name: file.name, display_name: name.value.trim() || file.name, size: file.size,
        retention_days: forever.checked ? null : Number(days.value)};
      const signature = JSON.stringify(payload) + ':' + file.lastModified;
      if (!pending || pending.signature !== signature || pending.file !== file) {
        pending = {signature, file, key: Array.from(crypto.getRandomValues(new Uint8Array(16)), x => x.toString(16).padStart(2, '0')).join(''), uploaded: false};
      }
      const token = form.querySelector('[name=csrfmiddlewaretoken]').value;
      form.querySelectorAll('input,button').forEach(input => { input.disabled = true; });
      progress.hidden = false;
      try {
        status.textContent = 'Preparing upload…';
        const registered = await jsonRequest(form.dataset.register, payload, token, pending.key);
        if (registered.upload && !pending.uploaded) {
          progress.value = 0;
          status.textContent = 'Uploading file…';
          await sendFile(registered.upload, file, progress);
          pending.uploaded = true;
        }
        status.textContent = 'Verifying and saving file…';
        const completed = await jsonRequest(form.dataset.completeTemplate.replace('FILE_ID', registered.file.file_id), {}, token);
        status.textContent = 'Upload verified. Your file is ready.';
        progress.value = 100;
        review.href = completed.detail_url;
        review.textContent = 'Review file';
        review.className = 'button primary';
        review.hidden = false;
        submit.textContent = 'Uploaded';
      } catch (exc) {
        if (exc.status === 410) pending = undefined;
        status.textContent = 'Upload not yet verified.';
        error.textContent = exc.message;
        error.hidden = false;
        form.querySelectorAll('input,button').forEach(input => { input.disabled = false; });
        days.disabled = forever.checked;
        submit.textContent = 'Retry upload';
      }
    });
  }
  document.querySelectorAll('form[data-complete]').forEach(verify => verify.addEventListener('submit', async event => {
    event.preventDefault();
    const status = verify.querySelector('[data-status]');
    const button = verify.querySelector('button');
    button.disabled = true;
    status.textContent = 'Verifying upload…';
    try {
      const result = await jsonRequest(verify.dataset.complete, {}, verify.querySelector('[name=csrfmiddlewaretoken]').value);
      window.location.assign(result.detail_url);
    } catch (exc) { status.textContent = exc.message; button.disabled = false; }
  }));
})();
