import { authClient } from "./auth-client";

export type NoteStatus = "queued" | "transcribing" | "ready" | "failed";

export type NoteError = { code: string; message: string } | null;

export type Note = {
  id: string;
  title: string;
  status: NoteStatus;
  filename: string;
  content_type: string;
  size_bytes: number;
  duration_seconds: number | null;
  language_code: string;
  transcript: string | null;
  summary: string | null;
  error: NoteError;
  audio_url: string | null;
  created_at: string;
  updated_at: string;
};

export type NoteSummary = Omit<Note, "transcript" | "summary">;

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let cachedToken: { value: string; expiresAt: number } | null = null;

async function accessToken(): Promise<string> {
  if (cachedToken && cachedToken.expiresAt > Date.now()) return cachedToken.value;

  const { data, error } = await authClient.token();
  if (error || !data?.token) {
    throw new Error(error?.message ?? "No session token");
  }

  cachedToken = { value: data.token, expiresAt: Date.now() + 60_000 };
  return data.token;
}

export function forgetToken(): void {
  cachedToken = null;
}

export async function authHeaders(): Promise<Record<string, string>> {
  return { Authorization: `Bearer ${await accessToken()}` };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...(await authHeaders()), ...init.headers },
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string; detail?: string };
    return body.error ?? body.detail ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export function audioUrl(note: Note): string | null {
  return note.audio_url ? `${API_URL}${note.audio_url}` : null;
}

/** The audio element cannot send an Authorization header, so the bytes are
fetched with the session token and handed to the player as an object URL. */
export async function fetchAudio(path: string | null): Promise<string | null> {
  if (!path) return null;

  const response = await fetch(`${API_URL}${path}`, { headers: await authHeaders() });
  if (!response.ok) throw new Error(await readError(response));
  return URL.createObjectURL(await response.blob());
}

export async function uploadNote(
  file: File,
  title: string | undefined,
  languageCode: string | undefined,
  durationSeconds?: number | null,
): Promise<Note> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  if (languageCode) form.append("language_code", languageCode);
  if (durationSeconds != null) {
    form.append("duration_seconds", durationSeconds.toFixed(3));
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/notes`, {
      method: "POST",
      body: form,
      headers: await authHeaders(),
    });
  } catch {
    throw new Error(
      `Could not reach the API at ${API_URL}. Check that the backend is running and allows this origin.`,
    );
  }

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as Note;
}

export const listNotes = () => request<NoteSummary[]>("/api/notes");

export const getNote = (id: string) => request<Note>(`/api/notes/${id}`);

export const renameNote = (id: string, title: string) =>
  request<Note>(`/api/notes/${id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title }),
  });

export const deleteNote = (id: string) =>
  request<void>(`/api/notes/${id}`, { method: "DELETE" });

export const retryNote = (id: string) =>
  request<Note>(`/api/notes/${id}/retry`, { method: "POST" });
