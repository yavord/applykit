import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type DragEvent, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { type ApiError, importResume } from '../api/client';

interface Props {
  onClose: () => void;
}

export default function ImportDialog({ onClose }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    fileInput.current?.focus();
  }, []);

  const mutation = useMutation({
    mutationFn: ({ f, n }: { f: File; n?: string }) => importResume(f, n),
    onSuccess: (resume) => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      navigate(`/resumes/${resume.id}`);
    },
  });

  const pickFile = (f: File | null) => {
    setFile(f);
    if (f && name === '') setName(f.name.replace(/\.[^.]*$/, ''));
  };
  const onDragOver = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault(); // without this the drop is blocked
    setDragging(true);
  };

  const onDragLeave = (e: DragEvent<HTMLLabelElement>) => {
    if (e.currentTarget.contains(e.relatedTarget as Node)) return; // child move
    setDragging(false);
  };

  const onDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files[0] ?? null);
  };

  return (
    <div className="overlay">
      <div className="dialog" role="dialog" aria-modal="true" aria-label="Import resume">
        <h2>Import resume</h2>

        <div className="field">
          <label htmlFor="import-file">File</label>
          <label
            className={`file-drop${dragging ? ' dragging' : ''}`}
            htmlFor="import-file"
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <span className="file-drop-name">{file ? file.name : 'Choose a file'}</span>
            <input
              id="import-file"
              ref={fileInput}
              className="file-drop-input"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        <div className="field">
          <label htmlFor="import-name">Name</label>
          <input
            id="import-name"
            type="text"
            value={name}
            placeholder={file ? file.name.replace(/\.[^.]*$/, '') : 'Resume name'}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {mutation.isError && (
          <p className="error" role="alert">
            {(mutation.error as ApiError).message}
          </p>
        )}

        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={mutation.isPending || !file}
            onClick={() => file && mutation.mutate({ f: file, n: name })}
          >
            {mutation.isPending ? 'Importing…' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
