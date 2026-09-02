import { describe, expect, it } from 'vitest';
import { dropIndex, insertItem, isMarker, moveItem, removeItem, serializeScalar } from './sections';

const marker = { v: '123 Main St', uncertain: true };

describe('isMarker', () => {
  it('accepts a valid marker', () => {
    expect(isMarker(marker)).toBe(true);
  });

  it('rejects plain strings and non-objects', () => {
    expect(isMarker('plain')).toBe(false);
    expect(isMarker(null)).toBe(false);
    expect(isMarker(42)).toBe(false);
  });

  it('rejects malformed objects', () => {
    expect(isMarker({ v: 5, uncertain: true })).toBe(false);
    expect(isMarker({ v: 'x', uncertain: false })).toBe(false);
    expect(isMarker({ uncertain: true })).toBe(false);
  });
});

describe('serializeScalar', () => {
  it('preserves an untouched marker', () => {
    expect(serializeScalar(marker, '123 Main St')).toBe(marker);
  });

  it('resolves a marker to a plain string when edited', () => {
    expect(serializeScalar(marker, '456 Oak Ave')).toBe('456 Oak Ave');
  });

  it('passes plain strings through', () => {
    expect(serializeScalar('hello', 'hello')).toBe('hello');
  });
});

describe('moveItem', () => {
  it('moves an item forward', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 2)).toEqual(['b', 'c', 'a']);
  });

  it('moves an item backward', () => {
    expect(moveItem(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b']);
  });

  it('returns the same array for out-of-range or no-op moves', () => {
    expect(moveItem(['a', 'b'], 0, 0)).toEqual(['a', 'b']);
    expect(moveItem(['a', 'b'], -1, 1)).toEqual(['a', 'b']);
    expect(moveItem(['a', 'b'], 0, 5)).toEqual(['a', 'b']);
  });
});
describe('dropIndex', () => {
  it('maps a drop before a later row', () => {
    expect(moveItem(['a', 'b', 'c'], 0, dropIndex(0, 2))).toEqual(['b', 'a', 'c']);
  });

  it('maps a drop before an earlier row', () => {
    expect(moveItem(['a', 'b', 'c'], 2, dropIndex(2, 0))).toEqual(['c', 'a', 'b']);
  });

  it('maps a drop after the last row', () => {
    expect(moveItem(['a', 'b', 'c'], 0, dropIndex(0, 3))).toEqual(['b', 'c', 'a']);
  });

  it('keeps the row in place when dropped on itself', () => {
    expect(moveItem(['a', 'b', 'c'], 1, dropIndex(1, 1))).toEqual(['a', 'b', 'c']);
  });
});

describe('removeItem', () => {
  it('removes an item', () => {
    expect(removeItem(['a', 'b', 'c'], 1)).toEqual(['a', 'c']);
  });

  it('ignores out-of-range indices', () => {
    expect(removeItem(['a', 'b'], 2)).toEqual(['a', 'b']);
    expect(removeItem(['a', 'b'], -1)).toEqual(['a', 'b']);
  });
});

describe('insertItem', () => {
  it('inserts at the index', () => {
    expect(insertItem(['a', 'c'], 1, 'b')).toEqual(['a', 'b', 'c']);
  });

  it('appends when index is the array length', () => {
    expect(insertItem(['a'], 1, 'b')).toEqual(['a', 'b']);
  });
});
