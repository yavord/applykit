export type Scalar = string | { v: string; uncertain: boolean };

export type SectionKind =
  | 'contact'
  | 'summary'
  | 'skills'
  | 'experience'
  | 'education'
  | 'projects'
  | 'certifications';

export const SECTION_LABELS: Record<SectionKind, string> = {
  contact: 'Contact',
  summary: 'Summary',
  skills: 'Skills',
  experience: 'Work Experience',
  education: 'Education',
  projects: 'Projects',
  certifications: 'Certifications',
};

export const SECTION_ORDER: SectionKind[] = [
  'contact',
  'summary',
  'skills',
  'experience',
  'education',
  'projects',
  'certifications',
];

/** Palette hue per section kind — the .hue-* utility classes in
    globals.css. contact & experience share the brand blue; skills &
    certifications share magenta (both are tag-style lists). */
export type HueName = 'blue' | 'cyan' | 'magenta' | 'teal' | 'orange';

export const SECTION_HUES: Record<SectionKind, HueName> = {
  contact: 'blue',
  summary: 'cyan',
  skills: 'magenta',
  experience: 'blue',
  education: 'teal',
  projects: 'orange',
  certifications: 'magenta',
};

/** Field labels; display order per kind = listed order. */
export const FIELD_LABELS: Record<string, string> = {
  name: 'Name',
  subtitle: 'Headline',
  email: 'Email',
  phone: 'Phone',
  location: 'Location',
  tags: 'Tags',
  links: 'Links',
  text: 'Summary',
  group: 'Group',
  skills: 'Skills',
  title: 'Title',
  organization: 'Organization',
  start: 'Start',
  end: 'End',
  summary: 'Description',
  bullets: 'Bullet points',
  degree: 'Degree',
  institution: 'Institution',
  gpa: 'GPA',
  achievements: 'Achievements',
  coursework: 'Coursework',
  dates: 'Dates',
  url: 'URL',
  issuer: 'Issuer',
  date: 'Date',
};

/** Keys rendered as multiline textareas. */
export const LONG_FIELDS: Record<string, true> = { text: true, summary: true };

export interface FieldSpec {
  inputs: string[];
  long?: string;
  scalarLists: string[];
  objectLists: Record<string, string[]>;
}

export const SECTION_SPECS: Record<SectionKind, FieldSpec> = {
  contact: {
    inputs: ['name', 'subtitle', 'email', 'phone', 'location'],
    scalarLists: ['tags'],
    objectLists: { links: ['name', 'url'] },
  },
  summary: { inputs: [], long: 'text', scalarLists: [], objectLists: {} },
  skills: { inputs: ['group'], scalarLists: ['skills'], objectLists: {} },
  experience: {
    inputs: ['title', 'organization', 'location', 'start', 'end'],
    long: 'summary',
    scalarLists: ['bullets'],
    objectLists: {},
  },
  education: {
    inputs: ['degree', 'institution', 'location', 'start', 'end', 'gpa'],
    scalarLists: ['achievements', 'coursework'],
    objectLists: {},
  },
  projects: {
    inputs: ['title', 'organization', 'dates', 'url'],
    scalarLists: ['bullets'],
    objectLists: {},
  },
  certifications: { inputs: ['name', 'issuer', 'date', 'url'], scalarLists: [], objectLists: {} },
};

type Entry = Record<string, unknown>;

/** Fresh entry for list-kind sections; clone before use, never share refs. */
export const EMPTY_ENTRY: Record<Exclude<SectionKind, 'contact' | 'summary'>, Entry> = {
  skills: { group: '', skills: [] },
  experience: {
    title: '',
    organization: '',
    location: '',
    start: '',
    end: '',
    summary: '',
    bullets: [],
  },
  education: {
    degree: '',
    institution: '',
    location: '',
    start: '',
    end: '',
    gpa: '',
    achievements: [],
    coursework: [],
  },
  projects: { title: '', organization: '', dates: '', url: '', bullets: [] },
  certifications: { name: '', issuer: '', date: '', url: '' },
};

export function isMarker(v: unknown): v is { v: string; uncertain: boolean } {
  if (typeof v !== 'object' || v === null) return false;
  const marker = v as Record<string, unknown>;
  return typeof marker.v === 'string' && marker.uncertain === true;
}

export function scalarInputValue(v: Scalar): string {
  return isMarker(v) ? v.v : v;
}

export function serializeScalar(original: Scalar, edited: string): Scalar {
  if (isMarker(original) && original.v === edited) return original;
  return edited;
}

export function moveItem<T>(arr: T[], from: number, to: number): T[] {
  if (from < 0 || from >= arr.length || to < 0 || to >= arr.length || from === to) return arr;
  const next = [...arr];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}
/** Final index for a drop at insertion position `pos` (0..n) of a list of n items. */
export function dropIndex(from: number, pos: number): number {
  return pos - (from < pos ? 1 : 0);
}

export function removeItem<T>(arr: T[], index: number): T[] {
  if (index < 0 || index >= arr.length) return arr;
  return arr.filter((_, i) => i !== index);
}

export function insertItem<T>(arr: T[], index: number, item: T): T[] {
  const next = [...arr];
  next.splice(index, 0, item);
  return next;
}
