<script>
// Native details work without JavaScript; enhance only site/application menus.
(() => {
  if (window.wwNavigationReady) return;
  window.wwNavigationReady = true;
  const menus = () => document.querySelectorAll('details[data-nav-menu]');
  document.addEventListener('toggle', event => {
    if (!event.target.matches('details[data-nav-menu][open]')) return;
    menus().forEach(menu => { if (menu !== event.target) menu.open = false; });
  }, true);
  document.addEventListener('click', event => {
    menus().forEach(menu => {
      if (!menu.contains(event.target) || event.target.closest('a[href]')) menu.open = false;
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const menu = document.querySelector('details[data-nav-menu][open]');
    if (!menu) return;
    event.preventDefault();
    menu.open = false;
    menu.querySelector('summary').focus();
  });
  document.addEventListener('focusin', event => {
    menus().forEach(menu => { if (!menu.contains(event.target)) menu.open = false; });
  });
})();
</script>
