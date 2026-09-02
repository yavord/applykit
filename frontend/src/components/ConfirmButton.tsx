import { useRef, useState } from 'react';

interface Props {
  onConfirm: () => void;
  disabled?: boolean;
  disabledTitle?: string;
  children: string;
}

const REVERT_MS = 4000;

export default function ConfirmButton({ onConfirm, disabled, disabledTitle, children }: Props) {
  const [confirming, setConfirming] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const cancel = () => {
    setConfirming(false);
    if (timer.current) window.clearTimeout(timer.current);
  };

  const arm = () => {
    setConfirming(true);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(cancel, REVERT_MS);
  };

  const confirm = () => {
    cancel();
    onConfirm();
  };

  return (
    <button
      type="button"
      className="btn btn-delete"
      disabled={disabled}
      title={disabled ? disabledTitle : undefined}
      onClick={confirming ? confirm : arm}
      onBlur={cancel}
    >
      {confirming ? 'Confirm delete' : children}
    </button>
  );
}
