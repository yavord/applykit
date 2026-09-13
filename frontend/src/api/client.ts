import type { ExportFormat } from '../resume/exportSettings';
import type { components } from './schema';

export type ResumeOut = components['schemas']['ResumeOut'];
export type ResumeSectionOut = components['schemas']['ResumeSectionOut'];
export type ResumeSectionIn = components['schemas']['ResumeSectionIn'];
export type PagesOut = components['schemas']['PagesOut'];
export type FitOut = components['schemas']['FitOut'];

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiError(res: Response): Promise<ApiError> {
  let detail = res.statusText;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') detail = body.detail;
  } catch {
    /* non-JSON error body; keep statusText */
  }
  return new ApiError(res.status, detail);
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, 'Cannot reach the local server. Is it running on 127.0.0.1:8000?');
  }

  if (!res.ok) throw await apiError(res);

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function requestBlob(url: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    throw new ApiError(0, 'Cannot reach the local server. Is it running on 127.0.0.1:8000?');
  }

  if (!res.ok) throw await apiError(res);
  return await res.blob();
}

export function listResumes(): Promise<ResumeOut[]> {
  return request<ResumeOut[]>('/api/resumes');
}

export function getResume(id: number): Promise<ResumeOut> {
  return request<ResumeOut>(`/api/resumes/${id}`);
}

export function importResume(file: File, name?: string): Promise<ResumeOut> {
  const body = new FormData();
  body.append('file', file);
  if (name) body.append('name', name);

  return request<ResumeOut>('/api/resumes/import', { method: 'POST', body });
}

export function saveSections(id: number, sections: ResumeSectionIn[]): Promise<ResumeOut> {
  return request<ResumeOut>(`/api/resumes/${id}/sections`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sections }),
  });
}

export function activateResume(id: number): Promise<ResumeOut> {
  return request<ResumeOut>(`/api/resumes/${id}/activate`, { method: 'POST' });
}

export function deleteResume(id: number): Promise<void> {
  return request<void>(`/api/resumes/${id}`, { method: 'DELETE' });
}

export function exportUrl(id: number, fmt: ExportFormat, query: string): string {
  return `/api/resumes/${id}/export.${fmt}?${query}`;
}

export function getExportBlob(id: number, query: string): Promise<Blob> {
  return requestBlob(`/api/resumes/${id}/export.pdf?${query}`);
}

export function getPages(id: number, query: string): Promise<number> {
  return request<PagesOut>(`/api/resumes/${id}/pages?${query}`).then((out) => out.pages);
}

export function fitResume(id: number, query: string): Promise<FitOut> {
  return request<FitOut>(`/api/resumes/${id}/fit?${query}`, { method: 'POST' });
}
