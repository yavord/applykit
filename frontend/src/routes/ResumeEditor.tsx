import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useBlocker, useParams } from 'react-router';
import {
  type ApiError,
  activateResume,
  getResume,
  type ResumeSectionOut,
  saveSections,
} from '../api/client';
import SectionEditor from '../components/SectionEditor';
import { SECTION_LABELS, type SectionKind } from '../resume/sections';

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

export default function ResumeEditor() {
  const { id } = useParams();
  const resumeId = Number(id);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['resume', resumeId],
    queryFn: () => getResume(resumeId),
    enabled: Number.isFinite(resumeId),
  });

  const [draft, setDraft] = useState<ResumeSectionOut[]>([]);

  useEffect(() => {
    if (query.data) setDraft(clone(query.data.sections));
  }, [query.data]);

  const dirty = query.data ? JSON.stringify(draft) !== JSON.stringify(query.data.sections) : false;

  const blocker = useBlocker(dirty);

  const save = useMutation({
    mutationFn: (sections: ResumeSectionOut[]) =>
      saveSections(
        resumeId,
        sections.map((s, i) => ({ kind: s.kind, position: i, content: s.content })),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(['resume', resumeId], data);
    },
  });

  const activate = useMutation({
    mutationFn: () => activateResume(resumeId),
    onSuccess: (data) => {
      queryClient.setQueryData(['resume', resumeId], data);
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
  });

  const cancel = () => {
    if (query.data) setDraft(clone(query.data.sections));
  };

  if (query.isPending) {
    return (
      <div className="page">
        <div className="card section-card">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      </div>
    );
  }

  if (query.isError) {
    const err = query.error as ApiError;
    return (
      <div className="page">
        <p className="error error-banner" role="alert">
          {err.status === 404 ? 'Resume not found' : err.message}
        </p>
        {err.status === 404 ? (
          <Link to="/resumes" className="btn">
            ← Resumes
          </Link>
        ) : (
          <button type="button" className="btn" onClick={() => query.refetch()}>
            Retry
          </button>
        )}
      </div>
    );
  }

  const resume = query.data;

  return (
    <div className="page">
      <div className="editor-head">
        <Link to="/resumes" className="back">
          ← Resumes
        </Link>
        <h1>{resume.name}</h1>
        <span className="revision">Revision {resume.revision}</span>
        {resume.is_active ? (
          <span className="badge badge-active">Active</span>
        ) : (
          <button
            type="button"
            className="btn"
            disabled={activate.isPending}
            onClick={() => activate.mutate()}
          >
            {activate.isPending ? '…' : 'Set active'}
          </button>
        )}
        <div className="editor-actions">
          <a className="btn" href={`/api/resumes/${resumeId}/export.pdf`}>
            Export PDF
          </a>
          <a className="btn" href={`/api/resumes/${resumeId}/export.docx`}>
            Export DOCX
          </a>
          <button
            type="button"
            className="btn"
            disabled={!dirty || save.isPending}
            onClick={cancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!dirty || save.isPending}
            onClick={() => save.mutate(draft)}
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      {save.isError && (
        <p className="error error-banner" role="alert">
          {(save.error as ApiError).message}
        </p>
      )}

      {draft.map((section) =>
        SECTION_LABELS[section.kind as SectionKind] ? (
          <SectionEditor
            key={`${section.kind}-${section.position}`}
            kind={section.kind as SectionKind}
            content={section.content as Record<string, unknown> | unknown[]}
            onChange={(content) =>
              setDraft(draft.map((s) => (s === section ? { ...s, content } : s)))
            }
          />
        ) : null,
      )}

      {blocker.state === 'blocked' && (
        <div className="overlay">
          <div className="dialog" role="alertdialog" aria-modal="true" aria-label="Unsaved changes">
            <h2>Discard unsaved changes?</h2>
            <p>Your edits have not been saved.</p>
            <div className="dialog-actions">
              <button type="button" className="btn" onClick={() => blocker.reset()}>
                Stay
              </button>
              <button type="button" className="btn btn-primary" onClick={() => blocker.proceed()}>
                Leave anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
