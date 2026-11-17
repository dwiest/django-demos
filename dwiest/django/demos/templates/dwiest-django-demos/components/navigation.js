<script>
// Native details work without JavaScript; enhance only site/application menus.
(() => {
  if (window.wwNavigationReady) return;
  window.wwNavigationReady = true;
  document.querySelectorAll('.ww-apps').forEach(root => {
    const tabs = Array.from(root.querySelectorAll('[data-app-category]'));
    if (!tabs.length) return;
    const panels = Array.from(root.querySelectorAll('[data-app-panel]'));
    const select = tab => {
      tabs.forEach(item => {
        const active = item === tab;
        item.setAttribute('aria-selected', String(active));
        item.tabIndex = active ? 0 : -1;
      });
      panels.forEach(panel => {
        panel.hidden = panel.dataset.appPanel !== tab.dataset.appCategory;
      });
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => select(tab));
      tab.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        else if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = tabs.length - 1;
        else return;
        event.preventDefault();
        select(tabs[next]);
        tabs[next].focus();
      });
    });
    select(tabs.find(tab => tab.dataset.appCategory === root.dataset.initialCategory) || tabs[0]);
    root.classList.add('ww-tabs-ready');
  });
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

