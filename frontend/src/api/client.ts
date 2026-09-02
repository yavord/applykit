import type { components } from './schema';

export type ResumeOut = components['schemas']['ResumeOut'];
export type ResumeSectionOut = components['schemas']['ResumeSectionOut'];
export type ResumeSectionIn = components['schemas']['ResumeSectionIn'];

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, 'Cannot reach the local server. Is it running on 127.0.0.1:8000?');
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* non-JSON error body; keep statusText */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
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
