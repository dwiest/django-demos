/* Enhance the GET form; all controls also work without JavaScript. */
(() => {
  const form = document.querySelector('.store-discovery');
  if (!form || typeof form.requestSubmit !== 'function') return;
  form.querySelectorAll('select').forEach((select) => {
    select.addEventListener('change', () => form.requestSubmit());
  });
  // Keep a compact explicit action for typed searches (Enter works too).
  form.querySelector('.store-discovery-apply').textContent = 'Search';
})();
