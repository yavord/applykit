import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { type ApiError, exportUrl, getExportBlob, getPages } from '../api/client';
import {
  ALIGN_LABELS,
  BOUNDS,
  downloadQuery,
  EDUCATION_ORDERS,
  type ExportSettings,
  FONT_FAMILIES,
  FONT_LABELS,
  FORMAT_LABELS,
  FORMATS,
  HEADER_ALIGNS,
  type IntField,
  ORDER_LABELS,
  previewQuery,
  SIZE_WINDOW,
  SKILLS_LABELS,
  SKILLS_LAYOUTS,
} from '../resume/exportSettings';

const PREVIEW_DEBOUNCE_MS = 300;

interface Props {
  resumeId: number;
  settings: ExportSettings;
  dirty: boolean;
  canUndo: boolean;
  onChange: (next: ExportSettings) => void;
  onReset: () => void;
  onFit: () => void;
  onUndo: () => void;
  onClose: () => void;
}

/** Latest value after `ms` of quiet; the preview key settles between drags. */
function useDebounced<T>(value: T, ms: number): T {
  const [state, setState] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setState(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);

  return state;
}

/** Integer window [value - 2, value + 2] clamped to bounds; re-centers on change. */
function sizeOptions(value: number, [lo, hi]: readonly [number, number]): number[] {
  const first = Math.max(lo, value - SIZE_WINDOW);
  const last = Math.min(hi, value + SIZE_WINDOW);
  return Array.from({ length: last - first + 1 }, (_, i) => first + i);
}

function enumField<T extends string>({
  id,
  label,
  options,
  labels,
  value,
  onSelect,
}: {
  id: string;
  label: string;
  options: readonly T[];
  labels: Record<T, string>;
  value: T;
  onSelect: (value: T) => void;
}) {
  return (
    <div className="drawer-field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onSelect(e.target.value as T)}>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {labels[opt]}
          </option>
        ))}
      </select>
    </div>
  );
}

function sizeField({
  id,
  label,
  field,
  value,
  onSelect,
}: {
  id: string;
  label: string;
  field: IntField;
  value: number;
  onSelect: (value: number) => void;
}) {
  const [lo, hi] = BOUNDS[field];
  return (
    <div className="drawer-field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onSelect(Number(e.target.value))}>
        {sizeOptions(value, [lo, hi]).map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
    </div>
  );
}

function rangeField({
  id,
  label,
  field,
  value,
  onChange,
}: {
  id: string;
  label: string;
  field: IntField;
  value: number;
  onChange: (value: number) => void;
}) {
  const [lo, hi] = BOUNDS[field];
  return (
    <div className="drawer-range">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="range"
        min={lo}
        max={hi}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="drawer-range-value">{value}</span>
    </div>
  );
}

export default function ExportDrawer({
  resumeId,
  settings,
  dirty,
  canUndo,
  onChange,
  onReset,
  onFit,
  onUndo,
  onClose,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);

  // Clicking the backdrop closes; panel clicks are ignored via containment.
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const target = e.target as Element | null;
      if (target && !target.closest('.drawer')) onClose();
    };
    window.addEventListener('mousedown', onDown);
    return () => window.removeEventListener('mousedown', onDown);
  }, [onClose]);

  const key = useDebounced(previewQuery(settings), PREVIEW_DEBOUNCE_MS);
  const preview = useQuery({
    queryKey: ['export-preview', resumeId, key],
    queryFn: () => getExportBlob(resumeId, key),
  });
  const pages = useQuery({
    queryKey: ['export-pages', resumeId, key],
    queryFn: () => getPages(resumeId, key),
  });

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!preview.data) return;
    const url = URL.createObjectURL(preview.data);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url); // one live object URL at a time
  }, [preview.data]);

  // Escape closes the format menu first, then the drawer.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (menuOpen) setMenuOpen(false);
      else onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuOpen, onClose]);

  const badge = pages.isPending ? '…' : pages.isError ? '–' : `1/${pages.data}`;

  return (
    <div className="drawer-overlay">
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Export settings">
        <header className="drawer-head">
          <h2>Export settings</h2>
          <span className="drawer-pages">{badge}</span>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </header>

        {dirty && <p className="drawer-note">Unsaved edits are not exported.</p>}
        {pages.isError && (
          <p className="drawer-note drawer-error" role="alert">
            {(pages.error as ApiError).message}
          </p>
        )}

        <div className="drawer-body">
          <div className="drawer-controls">
            <div className="drawer-group hue-cyan">
              <h3>Fonts</h3>
              {enumField({
                id: 'export-font_family',
                label: 'Font',
                options: FONT_FAMILIES,
                labels: FONT_LABELS,
                value: settings.font_family,
                onSelect: (font_family) => onChange({ ...settings, font_family }),
              })}
              {sizeField({
                id: 'export-name_size',
                label: 'Name',
                field: 'name_size',
                value: settings.name_size,
                onSelect: (name_size) => onChange({ ...settings, name_size }),
              })}
              {sizeField({
                id: 'export-header_size',
                label: 'Section headers',
                field: 'header_size',
                value: settings.header_size,
                onSelect: (header_size) => onChange({ ...settings, header_size }),
              })}
              {sizeField({
                id: 'export-subheader_size',
                label: 'Sub-headers',
                field: 'subheader_size',
                value: settings.subheader_size,
                onSelect: (subheader_size) => onChange({ ...settings, subheader_size }),
              })}
              {sizeField({
                id: 'export-body_size',
                label: 'Body text',
                field: 'body_size',
                value: settings.body_size,
                onSelect: (body_size) => onChange({ ...settings, body_size }),
              })}
            </div>

            <div className="drawer-group hue-magenta">
              <h3>Layout</h3>
              {enumField({
                id: 'export-header_align',
                label: 'Header alignment',
                options: HEADER_ALIGNS,
                labels: ALIGN_LABELS,
                value: settings.header_align,
                onSelect: (header_align) => onChange({ ...settings, header_align }),
              })}
              {enumField({
                id: 'export-education_order',
                label: 'Education order',
                options: EDUCATION_ORDERS,
                labels: ORDER_LABELS,
                value: settings.education_order,
                onSelect: (education_order) => onChange({ ...settings, education_order }),
              })}
              {enumField({
                id: 'export-skills_layout',
                label: 'Skills layout',
                options: SKILLS_LAYOUTS,
                labels: SKILLS_LABELS,
                value: settings.skills_layout,
                onSelect: (skills_layout) => onChange({ ...settings, skills_layout }),
              })}
            </div>

            <div className="drawer-group hue-teal">
              <h3>Spacing &amp; margins</h3>
              {rangeField({
                id: 'export-section_spacing',
                label: 'Section spacing',
                field: 'section_spacing',
                value: settings.section_spacing,
                onChange: (section_spacing) => onChange({ ...settings, section_spacing }),
              })}
              {rangeField({
                id: 'export-entry_spacing',
                label: 'Entry spacing',
                field: 'entry_spacing',
                value: settings.entry_spacing,
                onChange: (entry_spacing) => onChange({ ...settings, entry_spacing }),
              })}
              {rangeField({
                id: 'export-line_spacing',
                label: 'Line spacing',
                field: 'line_spacing',
                value: settings.line_spacing,
                onChange: (line_spacing) => onChange({ ...settings, line_spacing }),
              })}
              {rangeField({
                id: 'export-margin_top',
                label: 'Top margin',
                field: 'margin_top',
                value: settings.margin_top,
                onChange: (margin_top) => onChange({ ...settings, margin_top }),
              })}
              {rangeField({
                id: 'export-margin_bottom',
                label: 'Bottom margin',
                field: 'margin_bottom',
                value: settings.margin_bottom,
                onChange: (margin_bottom) => onChange({ ...settings, margin_bottom }),
              })}
              {rangeField({
                id: 'export-margin_side',
                label: 'Side margins',
                field: 'margin_side',
                value: settings.margin_side,
                onChange: (margin_side) => onChange({ ...settings, margin_side }),
              })}
              <div className="drawer-check">
                <input
                  id="export-align_justify"
                  type="checkbox"
                  checked={settings.align_justify}
                  onChange={(e) => onChange({ ...settings, align_justify: e.target.checked })}
                />
                <label htmlFor="export-align_justify">Align text left &amp; right</label>
              </div>
            </div>
          </div>

          <div className="drawer-preview">
            {preview.isError ? (
              <p className="error">{(preview.error as ApiError).message}</p>
            ) : (
              <iframe title="Resume preview" src={previewUrl ?? undefined} />
            )}
          </div>
        </div>

        <footer className="drawer-foot">
          <div className="drawer-foot-row">
            <button type="button" className="btn" onClick={onFit}>
              Fit to one page
            </button>
            <button type="button" className="btn" onClick={onUndo} disabled={!canUndo}>
              Undo fit
            </button>
          </div>
          <div className="drawer-foot-row">
            <button type="button" className="btn btn-ghost" onClick={onReset}>
              Reset formatting
            </button>
            <div className="drawer-download">
              <button
                type="button"
                className="btn btn-primary"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen(!menuOpen)}
              >
                Download
              </button>
              {menuOpen && (
                <div className="menu" role="menu">
                  {FORMATS.map((fmt) => (
                    <a
                      key={fmt}
                      className="menu-item"
                      role="menuitem"
                      href={exportUrl(resumeId, fmt, downloadQuery(settings, fmt))}
                      onClick={() => {
                        onChange({ ...settings, format: fmt });
                        setMenuOpen(false);
                      }}
                    >
                      {FORMAT_LABELS[fmt]}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </footer>
      </aside>
    </div>
  );
}
