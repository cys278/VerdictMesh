(() => {
  const key = 'verdictmesh-theme';
  const root = document.documentElement;
  const button = document.getElementById('theme-toggle');
  if (!button) return;

  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let saved = null;

  try {
    saved = localStorage.getItem(key);
  } catch (_) {
    // Storage may be disabled.
  }

  function apply(theme) {
    root.dataset.theme = theme;
    button.setAttribute('aria-pressed', String(theme === 'dark'));
    button.setAttribute(
      'aria-label',
      theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
    );
    button.title = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';

    const icon = button.querySelector('.theme-icon');
    const label = button.querySelector('.theme-label');
    if (icon) icon.textContent = theme === 'dark' ? '☀' : '☾';
    if (label) label.textContent = theme === 'dark' ? 'Light' : 'Dark';
  }

  apply(
    saved === 'light' || saved === 'dark'
      ? saved
      : system.matches ? 'dark' : 'light'
  );

  button.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem(key, next);
    } catch (_) {
      // Keep this tab working.
    }
    apply(next);
  });

  system.addEventListener('change', event => {
    let preference = null;
    try {
      preference = localStorage.getItem(key);
    } catch (_) {
      // Storage may be disabled.
    }
    if (!preference) apply(event.matches ? 'dark' : 'light');
  });
})();