// Mirror of app/resumes/services/settings.py — the same 16 keys, defaults and
// bounds. The backend stays the single source of truth; keep this in lockstep.

export const FORMATS = ['pdf', 'docx'] as const;
export type ExportFormat = (typeof FORMATS)[number];

export const FONT_FAMILIES = ['work_sans', 'times_new_roman', 'helvetica'] as const;
export type FontFamily = (typeof FONT_FAMILIES)[number];

export const HEADER_ALIGNS = ['left', 'center', 'right'] as const;
export type HeaderAlign = (typeof HEADER_ALIGNS)[number];

export const EDUCATION_ORDERS = ['degree_first', 'institution_first'] as const;
export type EducationOrder = (typeof EDUCATION_ORDERS)[number];

export const SKILLS_LAYOUTS = ['inline', 'grouped', 'column'] as const;
export type SkillsLayout = (typeof SKILLS_LAYOUTS)[number];

export interface ExportSettings {
  format: ExportFormat;
  font_family: FontFamily;
  name_size: number;
  header_size: number;
  subheader_size: number;
  body_size: number;
  header_align: HeaderAlign;
  education_order: EducationOrder;
  skills_layout: SkillsLayout;
  section_spacing: number;
  entry_spacing: number;
  line_spacing: number;
  margin_top: number;
  margin_bottom: number;
  margin_side: number;
  align_justify: boolean;
}

export type IntField =
  | 'name_size'
  | 'header_size'
  | 'subheader_size'
  | 'body_size'
  | 'section_spacing'
  | 'entry_spacing'
  | 'line_spacing'
  | 'margin_top'
  | 'margin_bottom'
  | 'margin_side';

export const DEFAULT_SETTINGS: ExportSettings = {
  format: 'pdf',
  font_family: 'times_new_roman',
  name_size: 24,
  header_size: 12,
  subheader_size: 12,
  body_size: 10,
  header_align: 'center',
  education_order: 'institution_first',
  skills_layout: 'grouped',
  section_spacing: 4,
  entry_spacing: 3,
  line_spacing: 11,
  margin_top: 36,
  margin_bottom: 36,
  margin_side: 44,
  align_justify: false,
};

/** Inclusive [min, max] per int field; mirrors `_INT_FIELDS` in settings.py. */
export const BOUNDS: Record<IntField, readonly [number, number]> = {
  name_size: [16, 30],
  header_size: [10, 20],
  subheader_size: [8, 18],
  body_size: [8, 14],
  section_spacing: [0, 10],
  entry_spacing: [0, 10],
  line_spacing: [10, 15],
  margin_top: [10, 50],
  margin_bottom: [10, 50],
  margin_side: [30, 50],
};

/** Options per element size: current ±2, clamped to bounds. */
export const SIZE_WINDOW = 2;

export const FORMAT_LABELS: Record<ExportFormat, string> = {
  pdf: 'PDF',
  docx: 'Word (.docx)',
};

export const FONT_LABELS: Record<FontFamily, string> = {
  work_sans: 'Work Sans',
  times_new_roman: 'Times New Roman',
  helvetica: 'Helvetica',
};

export const ALIGN_LABELS: Record<HeaderAlign, string> = {
  left: 'Left',
  center: 'Center',
  right: 'Right',
};

export const ORDER_LABELS: Record<EducationOrder, string> = {
  degree_first: 'Degree → Institution',
  institution_first: 'Institution → Degree',
};

export const SKILLS_LABELS: Record<SkillsLayout, string> = {
  inline: 'Inline',
  grouped: 'Grouped',
  column: 'Column',
};

/** Serialization in dataclass field order; mirrors `settings_to_params`. */
export function toParams(s: ExportSettings): Record<string, string> {
  return {
    format: s.format,
    font_family: s.font_family,
    name_size: String(s.name_size),
    header_size: String(s.header_size),
    subheader_size: String(s.subheader_size),
    body_size: String(s.body_size),
    header_align: s.header_align,
    education_order: s.education_order,
    skills_layout: s.skills_layout,
    section_spacing: String(s.section_spacing),
    entry_spacing: String(s.entry_spacing),
    line_spacing: String(s.line_spacing),
    margin_top: String(s.margin_top),
    margin_bottom: String(s.margin_bottom),
    margin_side: String(s.margin_side),
    align_justify: s.align_justify ? 'true' : 'false',
  };
}

export function toQuery(s: ExportSettings): string {
  return new URLSearchParams(toParams(s)).toString();
}

function enumValue<T extends string>(options: readonly T[], key: string, raw: string): T {
  if (options.includes(raw as T)) return raw as T;
  throw new Error(`export setting '${key}' must be one of ${options.join(', ')}, got '${raw}'`);
}

/** Strict parse of a params record (e.g. a /fit response); throws on unknown or invalid. */
export function fromParams(params: Record<string, string>): ExportSettings {
  const s: ExportSettings = { ...DEFAULT_SETTINGS };

  for (const [key, raw] of Object.entries(params)) {
    if (key === 'format') {
      s.format = enumValue(FORMATS, key, raw);
    } else if (key === 'font_family') {
      s.font_family = enumValue(FONT_FAMILIES, key, raw);
    } else if (key === 'header_align') {
      s.header_align = enumValue(HEADER_ALIGNS, key, raw);
    } else if (key === 'education_order') {
      s.education_order = enumValue(EDUCATION_ORDERS, key, raw);
    } else if (key === 'skills_layout') {
      s.skills_layout = enumValue(SKILLS_LAYOUTS, key, raw);
    } else if (key === 'align_justify') {
      if (raw !== 'true' && raw !== 'false') {
        throw new Error(`export setting '${key}' must be 'true' or 'false', got '${raw}'`);
      }
      s.align_justify = raw === 'true';
    } else if (key in BOUNDS) {
      const [lo, hi] = BOUNDS[key as IntField];
      const value = Number(raw);
      if (!/^-?\d+$/.test(raw) || value < lo || value > hi) {
        throw new Error(`export setting '${key}' out of range [${lo}, ${hi}]: ${raw}`);
      }
      s[key as IntField] = value;
    } else {
      throw new Error(`unknown export setting: ${key}`);
    }
  }

  return s;
}

/** Query for an export (the only place format=docx may appear). */
export function downloadQuery(s: ExportSettings, fmt: ExportFormat): string {
  return toQuery({ ...s, format: fmt });
}

/** Query for /pages, /fit and the preview; always pdf. */
export function previewQuery(s: ExportSettings): string {
  return toQuery({ ...s, format: 'pdf' });
}
