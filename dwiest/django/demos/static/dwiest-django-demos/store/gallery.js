/* Links still open individual photos when JavaScript is unavailable. */
document.querySelectorAll('[data-photo-gallery]').forEach((gallery) => {
  const image = gallery.querySelector('.store-image');
  if (!image) return;
  gallery.querySelectorAll('[data-photo-link]').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      image.src = link.href;
      image.alt = link.dataset.alt;
      gallery.querySelectorAll('[data-photo-link]').forEach((other) => other.removeAttribute('aria-current'));
      link.setAttribute('aria-current', 'true');
    });
  });
});
