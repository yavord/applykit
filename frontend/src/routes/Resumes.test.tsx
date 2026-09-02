import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createHashRouter, RouterProvider } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as client from '../api/client';
import Resumes from './Resumes';

vi.mock('../api/client', () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  return {
    ApiError,
    getResume: vi.fn(),
    saveSections: vi.fn(),
    activateResume: vi.fn(),
    listResumes: vi.fn(),
    importResume: vi.fn(),
    deleteResume: vi.fn(),
  };
});

const mocked = vi.mocked(client);

function renderResumes() {
  window.location.hash = '#/resumes';
  const router = createHashRouter([{ path: '/resumes', element: <Resumes /> }]);
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const activeResume = {
  id: 1,
  name: 'Active CV',
  is_active: true,
  revision: 1,
  source_kind: 'pdf' as const,
  sections: [],
  created_at: '2026-08-02T12:00:00',
  updated_at: '2026-09-01T12:00:00',
};

const inactiveResume = {
  id: 2,
  name: 'Draft CV',
  is_active: false,
  revision: 3,
  source_kind: 'docx' as const,
  sections: [],
  created_at: '2026-08-02T12:00:00',
  updated_at: '2026-09-01T12:00:00',
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('Resumes', () => {
  it('shows the empty state with an import CTA', async () => {
    mocked.listResumes.mockResolvedValue([]);
    renderResumes();

    expect(await screen.findByText('No resumes yet')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Import your first resume' }),
    ).toBeInTheDocument();
  });

  it('stays open and shows the ApiError message on a 409 import', async () => {
    mocked.listResumes.mockResolvedValue([]);
    mocked.importResume.mockRejectedValue(
      new mocked.ApiError(409, 'A resume named "Smoke CV" already exists'),
    );
    renderResumes();

    fireEvent.click(screen.getByRole('button', { name: 'Import resume' }));
    const file = new File(['x'], 'smoke.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText('File'), { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Import' }));

    expect(
      await screen.findByText('A resume named "Smoke CV" already exists'),
    ).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
  it('imports a file dropped on the dropzone', async () => {
    mocked.listResumes.mockResolvedValue([]);
    renderResumes();

    fireEvent.click(screen.getByRole('button', { name: 'Import resume' }));
    const file = new File(['x'], 'smoke.pdf', { type: 'application/pdf' });
    fireEvent.drop(screen.getByText('Choose a file'), { dataTransfer: { files: [file] } });

    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('smoke');
  });

  it('disables Delete for the active resume with a title', async () => {
    mocked.listResumes.mockResolvedValue([activeResume, inactiveResume]);
    renderResumes();

    await screen.findByText('Active CV');
    const deletes = screen.getAllByRole('button', { name: 'Delete' });
    expect(deletes[0]).toBeDisabled();
    expect(deletes[0]).toHaveAttribute('title', 'Switch active resume first');
    expect(deletes[1]).toBeEnabled();
  });

  it('shows Last Modified and Created instead of Source and Sections', async () => {
    mocked.listResumes.mockResolvedValue([activeResume]);
    renderResumes();

    await screen.findByText('Active CV');
    expect(screen.queryByText('Source')).not.toBeInTheDocument();
    expect(screen.queryByText('Sections')).not.toBeInTheDocument();
    expect(screen.getByText('Last Modified')).toBeInTheDocument();
    expect(screen.getByText('Created')).toBeInTheDocument();
    expect(screen.getByText('Sep 1, 2026')).toBeInTheDocument();
    expect(screen.getByText('Aug 2, 2026')).toBeInTheDocument();
    expect(screen.queryByText('Actions')).not.toBeInTheDocument();

    const headers = screen
      .getAllByRole('columnheader')
      .map((th) => th.textContent)
      .filter(Boolean);
    expect(headers).toEqual(['Name', 'Last Modified', 'Created', 'Revision']);

    const row = screen.getByText('Active CV').closest('tr')!;
    const cells = [...row.querySelectorAll('td')].map((td) => td.textContent);
    expect(cells.slice(1, 4)).toEqual(['Sep 1, 2026', 'Aug 2, 2026', 'Revision 1']);
  });

  it('deletes an inactive resume via two-step confirm', async () => {
    mocked.listResumes.mockResolvedValue([inactiveResume]);
    mocked.deleteResume.mockResolvedValue(undefined);
    renderResumes();

    const deleteBtn = await screen.findByRole('button', { name: 'Delete' });
    fireEvent.click(deleteBtn);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => expect(mocked.deleteResume).toHaveBeenCalledWith(2));
  });
});
