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
