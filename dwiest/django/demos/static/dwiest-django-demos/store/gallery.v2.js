/* Keep ordinary image links as a fallback for browsers without modal dialogs. */
document.querySelectorAll('[data-photo-gallery]').forEach((gallery) => {
  const preview = gallery.querySelector('.store-image');
  const opener = gallery.querySelector('[data-photo-open]');
  const dialog = document.querySelector('[data-photo-dialog]');
  if (!preview || !opener || !dialog || typeof dialog.showModal !== 'function') return;
  const links = Array.from(gallery.querySelectorAll('[data-photo-link]'));
  const photos = links.length ? links.map((link) => ({url: link.href, alt: link.dataset.alt})) :
    [{url: opener.href, alt: preview.alt}];
  const full = dialog.querySelector('[data-photo-full]');
  const stage = dialog.querySelector('[data-photo-stage]');
  const zoom = dialog.querySelector('[data-photo-zoom]');
  const previous = dialog.querySelector('[data-photo-prev]');
  const next = dialog.querySelector('[data-photo-next]');
  const error = dialog.querySelector('[data-photo-error]');
  let index = 0;
  let returnFocus;
  let scrollOverflow;
  const plainClick = (event) => event.button === 0 &&
    !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey;
  const setZoom = (enabled) => {
    stage.classList.toggle('is-zoomed', enabled);
    full.setAttribute('aria-pressed', String(enabled));
    full.setAttribute('aria-label', enabled ? 'Zoom image out' : 'Zoom image in');
    zoom.setAttribute('aria-pressed', String(enabled));
    zoom.textContent = enabled ? 'Zoom out' : 'Zoom in';
    stage.scrollTop = stage.scrollLeft = 0;
  };
  const select = (position) => {
    index = (position + photos.length) % photos.length;
    const photo = photos[index];
    preview.src = opener.href = photo.url;
    preview.alt = photo.alt;
    links.forEach((link, i) => {
      if (i === index) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    setZoom(false);
    error.hidden = true;
    full.hidden = false;
    full.src = photo.url;
    full.alt = photo.alt;
    dialog.querySelector('[data-photo-count]').textContent = `${index + 1} of ${photos.length}`;
  };
  const open = (trigger) => {
    returnFocus = trigger;
    dialog.showModal();
    scrollOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
  };
  links.forEach((link, position) => {
    link.addEventListener('click', (event) => {
      if (!plainClick(event)) return;
      event.preventDefault();
      select(position);
      // Variant selection uses programmatic thumbnail clicks; only user clicks open the viewer.
      if (event.isTrusted) open(link);
    });
  });
  opener.addEventListener('click', (event) => {
    if (!plainClick(event)) return;
    event.preventDefault();
    select(index);
    open(opener);
  });
  previous.hidden = next.hidden = photos.length < 2;
  previous.addEventListener('click', () => select(index - 1));
  next.addEventListener('click', () => select(index + 1));
  dialog.querySelector('[data-photo-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => {
    document.documentElement.style.overflow = scrollOverflow;
    setZoom(false);
    if (returnFocus && returnFocus.isConnected) returnFocus.focus();
  });
  dialog.addEventListener('keydown', (event) => {
    if (stage.classList.contains('is-zoomed')) return; // Arrow keys pan the zoomed image.
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      select(index + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  const toggleZoom = () => setZoom(!stage.classList.contains('is-zoomed'));
  zoom.addEventListener('click', toggleZoom);
  full.addEventListener('click', toggleZoom);
  full.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggleZoom();
    }
  });
  full.addEventListener('error', () => { full.hidden = true; error.hidden = false; });
  // Mark the initial cover without loading a second copy until the viewer opens.
  links.forEach((link) => {
    if (link.href === preview.src) link.setAttribute('aria-current', 'true');
  });
});
