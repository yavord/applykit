import { useState, type DragEvent } from 'react';

import {
  EMPTY_ENTRY,
  FIELD_LABELS,
  LONG_FIELDS,
  dropIndex,
  moveItem,
  removeItem,
  SECTION_LABELS,
  SECTION_SPECS,
  serializeScalar,
  type FieldSpec,
  type Scalar,
  type SectionKind,
} from '../resume/sections';
import FieldInput from './FieldInput';

type Content = Record<string, unknown> | unknown[];

interface Props {
  kind: SectionKind;
  content: Content;
  onChange: (content: Content) => void;
}

function scalarPair(value: unknown): Scalar {
  return (value ?? '') as Scalar;
}

function serializeList(list: unknown[], index: number, text: string): Scalar[] {
  return list.map((item, i) => (i === index ? serializeScalar(item as Scalar, text) : item as Scalar));
}

function serializeObj(
  list: Record<string, unknown>[],
  index: number,
  key: string,
  text: string,
): Record<string, unknown>[] {
  return list.map((item, i) =>
    i === index ? { ...item, [key]: serializeScalar(item[key] as Scalar, text) } : item,
  );
}

function entryTitle(entry: Record<string, unknown>, index: number): string {
  for (const key of ['title', 'name', 'degree', 'group']) {
    const v = entry[key];
    if (typeof v === 'string' && v !== '') return v;
  }
  return `Entry ${index + 1}`;
}

function singleLabel(key: string): string {
  return key === 'bullets' ? 'bullet' : 'item';
}

function iconBtn(label: string, title: string, onClick: () => void, danger?: boolean) {
  return (
    <button
      type="button"
      className={`icon-btn${danger ? ' icon-btn-danger' : ''}`}
      aria-label={title}
      title={title}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function addBtn(label: string, onClick: () => void) {
  return (
    <button type="button" className="btn btn-ghost" onClick={onClick}>
      {label}
    </button>
  );
}

function ScalarList({
  label,
  list,
  long,
  bare = false,
  bulleted = false,
  onUpdate,
}: {
  label: string;
  list: Scalar[];
  long?: boolean;
  bare?: boolean;
  bulleted?: boolean;
  onUpdate: (next: Scalar[]) => void;
}) {
  const drag = useDragOrder(list, onUpdate, long ? 'y' : 'x');

  return (
    <div className="field">
      {!bare && <label>{label}</label>}
      <div className={`list${long ? '' : ' list-inline'}${bulleted ? ' bullet-list' : ''}`}>
        {list.map((item, i) => (
          <div className={drag.rowClass(i, 'list-item')} key={i} {...drag.rowProps(i)}>
            <FieldInput
              label={bare ? undefined : label}
              value={item}
              long={long}
              onChange={(text) => onUpdate(serializeList(list, i, text))}
            />
            <div className="item-actions">
              <span {...drag.grabProps(i)}>⠿</span>
              {iconBtn('✕', 'Remove', () => onUpdate(removeItem(list, i)), true)}
            </div>
          </div>
        ))}
        {!long && addBtn(`Add ${singleLabel(label)}`, () => onUpdate([...list, '']))}
      </div>
      {long && addBtn(`Add ${singleLabel(label)}`, () => onUpdate([...list, '']))}
    </div>
  );
}

function ScalarFields({
  keys,
  values,
  onField,
}: {
  keys: string[];
  values: Record<string, unknown>;
  onField: (key: string, value: Scalar) => void;
}) {
  return (
    <div className="fields-grid">
      {keys
        .filter((k) => !LONG_FIELDS[k])
        .map((key) => (
          <FieldInput
            key={key}
            label={FIELD_LABELS[key]}
            value={scalarPair(values[key])}
            onChange={(text) => onField(key, serializeScalar(scalarPair(values[key]), text))}
          />
        ))}
    </div>
  );
}

const DRAG_REORDER_TITLE = 'Drag to reorder';

function useDragOrder<T>(list: T[], onUpdate: (next: T[]) => void, axis: 'x' | 'y' = 'y') {
  const [from, setFrom] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);

  const splitPos = (i: number, e: DragEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pos = axis === 'x' ? e.clientX : e.clientY;
    const half = axis === 'x' ? rect.left + rect.width / 2 : rect.top + rect.height / 2;
    return i + (pos > half ? 1 : 0);
  };

  return {
    // Attach to each draggable row. First half of row i = insert before i, second half = after i.
    rowProps: (i: number) => ({
      onDragOver: (e: DragEvent<HTMLElement>) => {
        e.preventDefault(); // without this the drop is blocked
        setOver(splitPos(i, e));
      },
      onDrop: (e: DragEvent<HTMLElement>) => {
        e.preventDefault();
        const pos = splitPos(i, e);
        if (from !== null) onUpdate(moveItem(list, from, dropIndex(from, pos)));
        setFrom(null);
        setOver(null);
      },
    }),
    // Attach to the grip span inside each row's actions.
    grabProps: (i: number) => ({
      draggable: true,
      title: DRAG_REORDER_TITLE,
      className: `drag-handle${from === i ? ' dragging' : ''}`,
      onDragStart: (e: DragEvent<HTMLSpanElement>) => {
        e.dataTransfer.setData('text/plain', String(i)); // required for Firefox to start a drag
        e.dataTransfer.effectAllowed = 'move';
        setFrom(i);
      },
      onDragEnd: () => {
        setFrom(null);
        setOver(null);
      },
    }),
    rowClass: (i: number, base: string) =>
      `${base}${from === i ? ' dragging' : ''}${over === i ? ' drag-before' : ''}${over === i + 1 ? ' drag-after' : ''}`,
  };
}

function LongField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Scalar;
  onChange: (value: Scalar) => void;
}) {
  return (
    <div className="field">
      <FieldInput
        label={label}
        value={value}
        long
        onChange={(text) => onChange(serializeScalar(value, text))}
      />
    </div>
  );
}

function EntryList({
  spec,
  entries,
  onChange,
}: {
  spec: FieldSpec;
  entries: Record<string, unknown>[];
  onChange: (next: Record<string, unknown>[]) => void;
}) {
  const drag = useDragOrder(entries, onChange);

  return (
    <>
      {entries.map((entry, i) => {
        const setEntry = (next: Record<string, unknown>) =>
          onChange(entries.map((e, j) => (j === i ? next : e)));
        const setField = (key: string, value: Scalar) =>
          setEntry({ ...entry, [key]: value });
        const onList = (key: string, next: Scalar[]) => setEntry({ ...entry, [key]: next });

        return (
          <div className={drag.rowClass(i, 'entry')} key={i} {...drag.rowProps(i)}>
            <div className="entry-head">
              <span className="entry-title">{entryTitle(entry, i)}</span>
              <div className="entry-actions">
                <span {...drag.grabProps(i)}>⠿</span>
                {iconBtn('✕', 'Remove', () => onChange(removeItem(entries, i)), true)}
              </div>
            </div>

            <ScalarFields keys={spec.inputs} values={entry} onField={setField} />

            {spec.long && (
              <LongField
                label={FIELD_LABELS[spec.long]}
                value={scalarPair(entry[spec.long])}
                onChange={(value) => setField(spec.long!, value)}
              />
            )}

            {spec.scalarLists.map((key) => (
              <ScalarList
                key={key}
                label={FIELD_LABELS[key]}
                bare={key === 'bullets' || key === 'skills'}
                bulleted={key === 'bullets'}
                list={(entry[key] ?? []) as Scalar[]}
                long={key !== 'skills'}
                onUpdate={(next) => onList(key, next)}
              />
            ))}
          </div>
        );
      })}
    </>
  );
}

function ObjectList({
  label,
  objKeys,
  list,
  onUpdate,
}: {
  label: string;
  objKeys: string[];
  list: Record<string, unknown>[];
  onUpdate: (next: Record<string, unknown>[]) => void;
}) {
  const drag = useDragOrder(list, onUpdate, 'x');

  return (
    <div className="field">
      <label>{label}</label>
      <div className="list list-inline">
        {list.map((item, i) => (
          <div className={drag.rowClass(i, 'list-item')} key={i} {...drag.rowProps(i)}>
            <div className="fields-grid">
              {objKeys.map((k) => (
                <FieldInput
                  key={k}
                  label={FIELD_LABELS[k]}
                  value={scalarPair(item[k])}
                  onChange={(text) => onUpdate(serializeObj(list, i, k, text))}
                />
              ))}
            </div>
            <div className="item-actions">
              <span {...drag.grabProps(i)}>⠿</span>
              {iconBtn('✕', 'Remove', () => onUpdate(removeItem(list, i)), true)}
            </div>
          </div>
        ))}
        {addBtn(`Add ${singleLabel(label)}`, () =>
          onUpdate([...list, Object.fromEntries(objKeys.map((k) => [k, '']))]),
        )}
      </div>
    </div>
  );
}

export default function SectionEditor({ kind, content, onChange }: Props) {
  const spec = SECTION_SPECS[kind];

  if (kind !== 'contact' && kind !== 'summary') {
    const entries = content as Record<string, unknown>[];
    return (
      <div className="card section-card">
        <h2 className="section-title">{SECTION_LABELS[kind]}</h2>

        <EntryList spec={spec} entries={entries} onChange={onChange} />

        {addBtn(
          'Add entry',
          () =>
            onChange([
              ...entries,
              JSON.parse(
                JSON.stringify(
                  EMPTY_ENTRY[kind as Exclude<typeof kind, 'contact' | 'summary'>],
                ),
              ),
            ]),
        )}
      </div>
    );
  }

  const dict = content as Record<string, unknown>;

  return (
    <div className="card section-card">
      <h2 className="section-title">{SECTION_LABELS[kind]}</h2>

      <ScalarFields keys={spec.inputs} values={dict} onField={(key, value) => onChange({ ...dict, [key]: value })} />

      {spec.long && (
        <LongField
          label={FIELD_LABELS[spec.long]}
          value={scalarPair(dict[spec.long])}
          onChange={(value) => onChange({ ...dict, [spec.long!]: value })}
        />
      )}

      {spec.scalarLists.map((key) => (
        <ScalarList
          key={key}
          label={FIELD_LABELS[key]}
          list={(dict[key] ?? []) as Scalar[]}
          onUpdate={(next) => onChange({ ...dict, [key]: next })}
        />
      ))}

      {Object.entries(spec.objectLists).map(([key, objKeys]) => (
        <ObjectList
          key={key}
          label={FIELD_LABELS[key]}
          objKeys={objKeys}
          list={(dict[key] ?? []) as Record<string, unknown>[]}
          onUpdate={(next) => onChange({ ...dict, [key]: next })}
        />
      ))}
    </div>
  );
}
