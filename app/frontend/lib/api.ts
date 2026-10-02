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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string; detail?: string };
    return body.error ?? body.detail ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function uploadNote(
  file: File,
  title: string | undefined,
  languageCode: string | undefined,
): Promise<Note> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  if (languageCode) form.append("language_code", languageCode);

  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/notes`, { method: "POST", body: form });
  } catch {
    throw new Error(
      `Could not reach the API at ${API_URL}. Check that the backend is running and allows this origin.`,
    );
  }

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as Note;
}