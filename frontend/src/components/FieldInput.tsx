import { useId } from 'react';
import { isMarker, type Scalar, scalarInputValue } from '../resume/sections';

interface Props {
  label?: string;
  value: Scalar;
  long?: boolean;
  onChange: (text: string) => void;
}

export default function FieldInput({ label, value, long, onChange }: Props) {
  const id = useId();
  const marker = isMarker(value);
  const className = marker ? 'uncertain' : undefined;
  const aria = marker && label ? `${label} (unverified)` : undefined;

  const common = {
    id,
    className,
    value: scalarInputValue(value),
    title: marker ? 'Uncertain — please verify' : undefined,
    'aria-label': aria,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange(e.target.value),
  };

  return (
    <div className="field">
      {label && (
        <label htmlFor={id}>
          {label}
          {marker && <span className="badge badge-uncertain">Uncertain</span>}
        </label>
      )}
      {long ? <textarea {...common} /> : <input {...common} />}
    </div>
  );
}
