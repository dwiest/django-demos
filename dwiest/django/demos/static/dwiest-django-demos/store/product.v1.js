/* Start new product visits below the masthead; preserve anchors and history restores. */
window.addEventListener('load', () => {
  const navigation = performance.getEntriesByType('navigation')[0];
  if (window.location.hash || (navigation && navigation.type !== 'navigate')) return;
  document.getElementById('product-start')?.scrollIntoView({block: 'start', behavior: 'instant'});
}, {once: true});
