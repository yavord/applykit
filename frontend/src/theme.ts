const THEME_KEY = 'applykit-theme';

export function getStoredTheme(): boolean {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === null) return true;
  return stored !== 'light';
}

export function applyTheme(dark: boolean): void {
  if (dark) document.documentElement.dataset.dark = '';
  else delete document.documentElement.dataset.dark;
}

export function toggleTheme(): boolean {
  const next = !getStoredTheme();
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next ? 'dark' : 'light');
  return next;
}
