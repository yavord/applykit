import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useBlocker, useParams } from 'react-router';
import {
  type ApiError,
  activateResume,
  fitResume,
  getResume,
  type ResumeSectionOut,
  saveSections,
} from '../api/client';
import ExportDrawer from '../components/ExportDrawer';
import SectionEditor from '../components/SectionEditor';
import {
  DEFAULT_SETTINGS,
  type ExportSettings,
  fromParams,
  previewQuery,
} from '../resume/exportSettings';
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

  const [settings, setSettings] = useState<ExportSettings>(DEFAULT_SETTINGS);
  const [undoStack, setUndoStack] = useState<ExportSettings[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fit = useMutation({
    mutationFn: () => fitResume(resumeId, previewQuery(settings)),
    onSuccess: (data) => {
      const next = fromParams(data.settings);
      // Record the pre-fit state so the user can walk back a failed attempt.
      if (previewQuery(next) !== previewQuery(settings)) setUndoStack((s) => [...s, settings]);
      setSettings(next);
    },
  });

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

  const reset = () => {
    setSettings({ ...DEFAULT_SETTINGS, format: settings.format });
    setUndoStack([]);
  };

  const undo = () => {
    const next = undoStack.at(-1);
    if (!next) return;
    setSettings(next);
    setUndoStack(undoStack.slice(0, -1));
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
          <button type="button" className="btn" onClick={() => setDrawerOpen(true)}>
            Export
          </button>
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

      {fit.isError && (
        <p className="error error-banner" role="alert">
          {(fit.error as ApiError).message}
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

      {drawerOpen && (
        <ExportDrawer
          resumeId={resumeId}
          settings={settings}
          dirty={dirty}
          canUndo={undoStack.length > 0}
          onChange={setSettings}
          onReset={reset}
          onFit={() => fit.mutate()}
          onUndo={undo}
          onClose={() => setDrawerOpen(false)}
        />
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
