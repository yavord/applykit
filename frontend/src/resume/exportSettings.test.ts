import { describe, expect, it } from 'vitest';
import {
  BOUNDS,
  DEFAULT_SETTINGS,
  downloadQuery,
  type ExportSettings,
  fromParams,
  type IntField,
  previewQuery,
  toParams,
  toQuery,
} from './exportSettings';

describe('DEFAULT_SETTINGS', () => {
  it('mirrors the 16 contract defaults', () => {
    expect(DEFAULT_SETTINGS).toEqual({
      format: 'pdf',
      font_family: 'work_sans',
      name_size: 24,
      header_size: 14,
      subheader_size: 12,
      body_size: 11,
      header_align: 'left',
      education_order: 'degree_first',
      skills_layout: 'grouped',
      section_spacing: 4,
      entry_spacing: 3,
      line_spacing: 12,
      margin_top: 36,
      margin_bottom: 36,
      margin_side: 36,
      align_justify: false,
    });
  });
});

describe('toQuery', () => {
  it('serializes defaults in the canonical key order', () => {
    expect(toQuery(DEFAULT_SETTINGS)).toBe(
      'format=pdf&font_family=work_sans&name_size=24&header_size=14&subheader_size=12' +
        '&body_size=11&header_align=left&education_order=degree_first&skills_layout=grouped' +
        '&section_spacing=4&entry_spacing=3&line_spacing=12&margin_top=36&margin_bottom=36' +
        '&margin_side=36&align_justify=false',
    );
    expect(Object.keys(toParams(DEFAULT_SETTINGS))).toHaveLength(16);
  });
});

describe('fromParams', () => {
  const custom: ExportSettings = {
    format: 'docx',
    font_family: 'times_new_roman',
    name_size: 18,
    header_size: 12,
    subheader_size: 10,
    body_size: 10,
    header_align: 'right',
    education_order: 'institution_first',
    skills_layout: 'column',
    section_spacing: 2,
    entry_spacing: 6,
    line_spacing: 15,
    margin_top: 20,
    margin_bottom: 25,
    margin_side: 50,
    align_justify: true,
  };

  it('round-trips a fully non-default setting', () => {
    expect(fromParams(toParams(custom))).toEqual(custom);
  });

  it('fills missing keys with defaults', () => {
    expect(fromParams({})).toEqual(DEFAULT_SETTINGS);
  });

  it.each([
    [{ body_size: '99' }, /out of range \[8, 14\]: 99/],
    [{ line_spacing: '9' }, /out of range \[10, 15\]: 9/],
    [{ nope: '1' }, /unknown export setting: nope/],
    [{ align_justify: 'yes' }, /must be 'true' or 'false', got 'yes'/],
    [{ format: 'rtf' }, /must be one of pdf, docx, got 'rtf'/],
  ])('rejects %s', (params, message) => {
    expect(() => fromParams(params)).toThrow(message);
  });
});

describe('BOUNDS', () => {
  it('covers exactly the int fields', () => {
    expect(Object.keys(BOUNDS).sort()).toEqual(
      [
        'name_size',
        'header_size',
        'subheader_size',
        'body_size',
        'section_spacing',
        'entry_spacing',
        'line_spacing',
        'margin_top',
        'margin_bottom',
        'margin_side',
      ].sort(),
    );
  });

  it('keeps every default inside its own bounds', () => {
    for (const [field, [lo, hi]] of Object.entries(BOUNDS)) {
      const value = DEFAULT_SETTINGS[field as IntField];
      expect(value).toBeGreaterThanOrEqual(lo);
      expect(value).toBeLessThanOrEqual(hi);
    }
  });
});

describe('query helpers', () => {
  it('lets downloadQuery carry format=docx', () => {
    expect(downloadQuery(DEFAULT_SETTINGS, 'docx')).toContain('format=docx');
  });

  it('forces the preview format to pdf', () => {
    const docx = { ...DEFAULT_SETTINGS, format: 'docx' } as ExportSettings;
    expect(downloadQuery(docx, 'pdf')).toContain('format=pdf');
    expect(previewQuery(docx)).toContain('format=pdf');
    expect(previewQuery(docx)).not.toContain('format=docx');
  });
});
