(() => {
  const dialog = document.querySelector('[data-branding-dialog]');
  if (!dialog) return;
  const form = document.querySelector('.branding-settings-layout form');
  let frame = dialog.querySelector('iframe');
  const error = document.querySelector('[data-preview-error]');
  const buttons = [...document.querySelectorAll('[data-branding-preview]')];
  let opener;
  buttons.forEach(button => button.addEventListener('click', async () => {
    error.textContent = '';
    buttons.forEach(item => { item.disabled = true; });
    try {
      const data = new FormData(form);
      data.set('preview_kind', button.dataset.brandingPreview);
      const response = await fetch(dialog.dataset.previewUrl, {method: 'POST', body: data, credentials: 'same-origin'});
      if (!response.ok) {
        if (response.status === 400) {
          const result = await response.json();
          error.textContent = result.errors.join('\n');
          return;
        }
        throw new Error('Preview unavailable');
      }
      const html = await response.text();
      // Sandboxing disables scripts, forms and navigation inside the draft.
      // Use a new browsing context for every draft, including identical previews.
      // Reusing a hidden srcdoc frame can leave it showing the blank close document.
      const nextFrame = frame.cloneNode(false);
      nextFrame.srcdoc = html;
      frame.replaceWith(nextFrame);
      frame = nextFrame;
      document.querySelector('#branding-preview-title').textContent = button.dataset.brandingPreview === 'store' ? 'Store preview' : 'Email preview';
      opener = button;
      dialog.showModal();
    } catch (exception) {
      error.textContent = 'Could not load the preview. Please try again.';
    } finally {
      buttons.forEach(item => { item.disabled = false; });
    }
  }));
  dialog.querySelector('[data-preview-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => { frame.removeAttribute('srcdoc'); if (opener) opener.focus(); });
})();
