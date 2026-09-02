import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import {
  type ApiError,
  activateResume,
  deleteResume,
  listResumes,
  type ResumeOut,
} from '../api/client';
import ConfirmButton from '../components/ConfirmButton';
import ImportDialog from '../components/ImportDialog';

function formatDate(iso: string): string {
  // API sends naive-UTC ISO without timezone marker; parse as UTC, show local.
  const value = iso.endsWith('Z') ? iso : `${iso}Z`;
  return new Date(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function RowActions({ resume }: { resume: ResumeOut }) {
  const queryClient = useQueryClient();
  const [activateError, setActivateError] = useState('');
  const [deleteError, setDeleteError] = useState('');

  const activate = useMutation({
    mutationFn: () => activateResume(resume.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
    onError: (e) => setActivateError((e as ApiError).message),
  });

  const remove = useMutation({
    mutationFn: () => deleteResume(resume.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
    onError: (e) => setDeleteError((e as ApiError).message),
  });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        {!resume.is_active && (
          <button
            type="button"
            className="btn"
            disabled={activate.isPending}
            onClick={() => activate.mutate()}
          >
            {activate.isPending ? '…' : 'Set active'}
          </button>
        )}
        <ConfirmButton
          onConfirm={() => remove.mutate()}
          disabled={resume.is_active}
          disabledTitle="Switch active resume first"
        >
          Delete
        </ConfirmButton>
      </div>
      {activateError && <p className="error">{activateError}</p>}
      {deleteError && <p className="error">{deleteError}</p>}
    </div>
  );
}

export default function Resumes() {
  const [importing, setImporting] = useState(false);

  const query = useQuery({ queryKey: ['resumes'], queryFn: listResumes });

  return (
    <div className="page">
      <div className="page-head">
        <h1>Resumes</h1>
        <button type="button" className="btn btn-primary" onClick={() => setImporting(true)}>
          Import resume
        </button>
      </div>

      {query.isPending && (
        <div className="card">
          <div className="table-wrap">
            <table className="table">
              <tbody>
                {[0, 1, 2].map((i) => (
                  <tr key={i}>
                    <td>
                      <div className="skeleton" />
                    </td>
                    <td>
                      <div className="skeleton" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {query.isError && (
        <p className="error error-banner" role="alert">
          {(query.error as ApiError).message}{' '}
          <button type="button" className="btn" onClick={() => query.refetch()}>
            Retry
          </button>
        </p>
      )}

      {query.isSuccess && query.data.length === 0 && (
        <div className="card">
          <p>No resumes yet</p>
          <button type="button" className="btn btn-primary" onClick={() => setImporting(true)}>
            Import your first resume
          </button>
        </div>
      )}

      {query.isSuccess && query.data.length > 0 && (
        <div className="card">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Last Modified</th>
                  <th scope="col">Created</th>
                  <th scope="col">Revision</th>
                  <th scope="col" className="th-actions" />
                </tr>
              </thead>
              <tbody>
                {query.data.map((r) => (
                  <tr key={r.id}>
                    <td className="td-name">
                      <Link to={`/resumes/${r.id}`}>{r.name}</Link>
                      {r.is_active && <span className="badge badge-active">Active</span>}
                    </td>
                    <td className="td-date">{formatDate(r.updated_at)}</td>
                    <td className="td-date">{formatDate(r.created_at)}</td>
                    <td className="td-rev">Revision {r.revision}</td>
                    <td className="td-actions">
                      <RowActions resume={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {importing && <ImportDialog onClose={() => setImporting(false)} />}
    </div>
  );
}
