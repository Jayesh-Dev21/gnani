"use client";

import { deleteSession, downloadTranscript, useSessions } from "@/lib/notes";

export function SavedNotes() {
  const notes = useSessions();

  if (notes.length === 0) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-24">
        <p className="micro">Nothing saved yet</p>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 overflow-y-auto px-6 py-10">
      <h1 className="text-2xl font-medium tracking-tight">Saved transcripts</h1>
      <p className="micro mt-2">
        {notes.length} recording{notes.length === 1 ? "" : "s"}
      </p>

      <ul className="mt-10">
        {notes.map((note) => (
          <li
            className="flex flex-wrap items-center justify-between gap-4 border-t border-rule py-4"
            key={note.id}
          >
            <div className="min-w-0">
              <p className="truncate font-medium">{note.title}</p>
              <p className="nums mt-1 text-[11px] text-muted">
                {new Date(note.created_at).toLocaleString()} · {note.status} ·{" "}
                {note.language_code}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                className="btn"
                onClick={() => downloadTranscript(note)}
                type="button"
              >
                Download
              </button>
              <button
                className="btn"
                onClick={() => deleteSession(note.id)}
                type="button"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}