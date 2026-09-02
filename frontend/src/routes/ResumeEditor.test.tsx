import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createHashRouter, RouterProvider } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as client from '../api/client';
import ResumeEditor from './ResumeEditor';

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

function renderEditor() {
  window.location.hash = '#/resumes/1';
  const router = createHashRouter([{ path: '/resumes/:id', element: <ResumeEditor /> }]);
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const markerName = { v: 'Jane Doe', uncertain: true };

const resume = {
  id: 1,
  name: 'Test Resume',
  is_active: true,
  revision: 2,
  source_kind: 'pdf' as const,
  sections: [
    { kind: 'contact', position: 0, content: { name: markerName, email: 'jane@example.com' } },
    { kind: 'summary', position: 1, content: { text: 'A summary' } },
  ],
  created_at: '2026-08-02T12:00:00',
  updated_at: '2026-09-01T12:00:00',
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.getResume.mockResolvedValue(resume as never);
});

describe('ResumeEditor', () => {
  it('renders a marker field with uncertain styling and badge', async () => {
    renderEditor();

    const input = await screen.findByLabelText('Name (unverified)');
    expect(input).toHaveClass('uncertain');
    expect(screen.getByText('Uncertain')).toBeInTheDocument();
    expect(input).toHaveValue('Jane Doe');
  });

  it('saves a plain string for an edited marker and preserves untouched values', async () => {
    mocked.saveSections.mockResolvedValue({ ...resume, revision: 3 });
    renderEditor();

    const input = await screen.findByLabelText('Name (unverified)');
    fireEvent.change(input, { target: { value: 'Jane Smith' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(mocked.saveSections).toHaveBeenCalledTimes(1));
    const sent = mocked.saveSections.mock.calls[0][1] as {
      content: Record<string, unknown>;
    }[];
    expect(sent[0].content.name).toBe('Jane Smith');
    expect(sent[0].content.email).toBe('jane@example.com');
    expect(sent[1].content.text).toBe('A summary');
  });

  it('disables Save while pristine and while pending', async () => {
    renderEditor();

    await screen.findByLabelText('Name (unverified)');
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();

    mocked.saveSections.mockReturnValue(new Promise(() => {}) as never);
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'x@y.z' } });
    const save = screen.getByRole('button', { name: 'Save' });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    expect(await screen.findByRole('button', { name: 'Saving…' })).toBeDisabled();
  });

  it('shows the ApiError detail on 400 and keeps the draft', async () => {
    mocked.saveSections.mockRejectedValue(new mocked.ApiError(400, 'Bad shape'));
    renderEditor();

    const input = await screen.findByLabelText('Name (unverified)');
    fireEvent.change(input, { target: { value: 'Jane Smith' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Bad shape')).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toHaveValue('Jane Smith');
  });

  it('restores original values on Cancel', async () => {
    renderEditor();

    const input = await screen.findByLabelText('Name (unverified)');
    fireEvent.change(input, { target: { value: 'Jane Smith' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => expect(screen.getByLabelText('Name (unverified)')).toHaveValue('Jane Doe'));
  });

  it('hides Set active and Cancel for an active resume', async () => {
    renderEditor();

    await screen.findByLabelText('Name (unverified)');
    expect(screen.queryByRole('button', { name: 'Set active' })).not.toBeInTheDocument();
    expect(screen.getByText('Active', { selector: '.badge' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  });
});
