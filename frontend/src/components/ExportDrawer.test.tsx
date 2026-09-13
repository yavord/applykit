import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import * as client from '../api/client';
import { DEFAULT_SETTINGS, toQuery } from '../resume/exportSettings';
import ExportDrawer from './ExportDrawer';

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
    exportUrl: vi.fn(
      (id: number, fmt: string, query: string) => `/api/resumes/${id}/export.${fmt}?${query}`,
    ),
    getExportBlob: vi.fn(),
    getPages: vi.fn(),
  };
});

const mocked = vi.mocked(client);
type Props = Parameters<typeof ExportDrawer>[0];

beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview') as typeof URL.createObjectURL;
  URL.revokeObjectURL = vi.fn() as typeof URL.revokeObjectURL;
});

beforeEach(() => {
  vi.clearAllMocks();
  mocked.getPages.mockResolvedValue(2);
  mocked.getExportBlob.mockResolvedValue(new Blob(['%PDF']));
});

function renderDrawer(partial: Partial<Props> = {}) {
  const handlers = {
    onChange: vi.fn(),
    onReset: vi.fn(),
    onFit: vi.fn(),
    onUndo: vi.fn(),
    onClose: vi.fn(),
  };
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ExportDrawer
        resumeId={1}
        settings={DEFAULT_SETTINGS}
        dirty={false}
        canUndo={false}
        {...handlers}
        {...partial}
      />
    </QueryClientProvider>,
  );
  return handlers;
}

describe('ExportDrawer', () => {
  it('renders groups, the page badge and the preview iframe', async () => {
    renderDrawer();

    expect(screen.getByText('Fonts')).toBeInTheDocument();
    expect(screen.getByText('Layout')).toBeInTheDocument();
    expect(screen.getByText('Spacing & margins')).toBeInTheDocument();

    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledTimes(1));
    expect(screen.getByTitle('Resume preview')).toHaveAttribute('src', 'blob:preview');
    expect(await screen.findByText('1/2')).toBeInTheDocument();
  });

  it('downloads via the format menu', () => {
    const handlers = renderDrawer();

    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    expect(screen.getByRole('menuitem', { name: 'PDF' })).toHaveAttribute(
      'href',
      `/api/resumes/1/export.pdf?${toQuery(DEFAULT_SETTINGS)}`,
    );
    const word = screen.getByRole('menuitem', { name: 'Word (.docx)' });
    expect(word).toHaveAttribute('href', expect.stringContaining('/api/resumes/1/export.docx?'));
    expect(word).toHaveAttribute('href', expect.stringContaining('format=docx'));

    fireEvent.click(word);
    expect(handlers.onChange).toHaveBeenCalledWith({ ...DEFAULT_SETTINGS, format: 'docx' });
  });

  it('reports int control changes through onChange', () => {
    const handlers = renderDrawer();

    fireEvent.change(screen.getByLabelText('Line spacing'), { target: { value: '14' } });

    expect(handlers.onChange).toHaveBeenCalledWith({ ...DEFAULT_SETTINGS, line_spacing: 14 });
  });

  it('resets formatting and disables Undo fit without history', () => {
    const handlers = renderDrawer();

    fireEvent.click(screen.getByRole('button', { name: 'Reset formatting' }));
    expect(handlers.onReset).toHaveBeenCalledTimes(1);

    expect(screen.getByRole('button', { name: 'Undo fit' })).toBeDisabled();
  });

  it('enables Undo fit with history and fires it', () => {
    const handlers = renderDrawer({ canUndo: true });

    const undo = screen.getByRole('button', { name: 'Undo fit' });
    expect(undo).toBeEnabled();
    fireEvent.click(undo);
    expect(handlers.onUndo).toHaveBeenCalledTimes(1);
  });

  it('hides the unsaved hint while clean', () => {
    renderDrawer();
    expect(screen.queryByText('Unsaved edits are not exported.')).not.toBeInTheDocument();
  });

  it('shows the unsaved hint while dirty', () => {
    renderDrawer({ dirty: true });
    expect(screen.getByText('Unsaved edits are not exported.')).toBeInTheDocument();
  });

  it('falls back to a dash badge and a note when pages fail', async () => {
    mocked.getPages.mockRejectedValue(new mocked.ApiError(422, 'PDF only'));
    renderDrawer();

    await waitFor(() => {
      expect(screen.getByText('–')).toBeInTheDocument();
      expect(screen.getByText('PDF only')).toBeInTheDocument();
    });
  });

  it('closes on Escape and fits on demand', () => {
    const handlers = renderDrawer();

    fireEvent.keyDown(screen.getByRole('dialog', { name: 'Export settings' }), {
      key: 'Escape',
    });
    expect(handlers.onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Fit to one page' }));
    expect(handlers.onFit).toHaveBeenCalledTimes(1);
  });
});
