/* Featured photo choices are independent of the product detail link. */
document.querySelectorAll('[data-product-card]').forEach((card) => {
  const image = card.querySelector('.store-image');
  if (!image) return;
  card.querySelectorAll('[data-card-photo]').forEach((button) => {
    button.addEventListener('click', () => {
      image.src = button.dataset.src;
      image.alt = button.dataset.alt;
      card.querySelectorAll('[data-card-photo]').forEach((other) => {
        other.setAttribute('aria-pressed', String(other === button));
      });
    });
  });
});

/* Share explicit purchase choices in this tab. Only mapped photos select variants. */
document.querySelectorAll('[data-variant-selection]').forEach((form) => {
  const select = form.querySelector('select[name="variant"]');
  if (!select) return;
  const key = 'store.variant.' + form.dataset.variantSelection;
  const root = form.closest('[data-product-card], [data-product-options]');
  const photos = root ? Array.from(root.querySelectorAll('[data-photo-variant]')) : [];
  const valid = (value) => Array.from(select.options).some((option) => option.value === value && !option.disabled);
  const remember = () => {
    try {
      if (select.value) sessionStorage.setItem(key, select.value);
      else sessionStorage.removeItem(key);
    } catch (_) { /* Storage is optional. */ }
  };
  const showPhoto = () => {
    const photo = photos.find((item) => item.dataset.photoVariant === select.value && select.value);
    if (photo) photo.click();
  };
  photos.forEach((photo) => photo.addEventListener('click', (event) => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const value = photo.dataset.photoVariant;
    if (value && valid(value)) {
      select.value = value;
      remember();
    }
  }));
  select.addEventListener('change', () => { remember(); showPhoto(); });
  form.addEventListener('submit', remember);
  try {
    const saved = sessionStorage.getItem(key);
    if (form.dataset.bound !== 'true' && saved && valid(saved)) {
      select.value = saved;
    }
  } catch (_) { /* Purchase controls work when browser storage is blocked. */ }
  showPhoto();
});
