import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { applyTheme, getStoredTheme } from './theme';

describe('getStoredTheme', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('defaults to dark with empty storage', () => {
    expect(getStoredTheme()).toBe(true);
  });

  it('defaults to dark with invalid storage', () => {
    localStorage.setItem('applykit-theme', 'garbage');
    expect(getStoredTheme()).toBe(true);
  });

  it('reads stored light as false', () => {
    localStorage.setItem('applykit-theme', 'light');
    expect(getStoredTheme()).toBe(false);
  });

  it('reads stored dark as true', () => {
    localStorage.setItem('applykit-theme', 'dark');
    expect(getStoredTheme()).toBe(true);
  });
});

describe('applyTheme', () => {
  it('sets data-dark when dark', () => {
    applyTheme(true);
    expect(document.documentElement.dataset.dark).toBeDefined();
  });

  it('removes data-dark when light', () => {
    applyTheme(true);
    applyTheme(false);
    expect(document.documentElement.dataset.dark).toBeUndefined();
  });
});
