"use client";

import { useState } from "react";

import type { Note } from "@/lib/api";
import { formatDuration } from "@/lib/audio-meta";
import { downloadTranscript } from "@/lib/notes";

function canRegenerate(note: Note): boolean {
  // Never while work is in flight: a second job would race the first one.
  if (note.status === "queued" || note.status === "transcribing" || note.status === "summarising") {
    return false;
  }
  // A ready note with no summary is exactly the case where the user is stuck
  // waiting for something that never arrived, so it needs the glyph too.
  return note.status === "failed" || !note.summary;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

export function SessionCard({
  note,
  onDelete,
  onRename,
  onRetry,
}: {
  note: Note;
  onDelete: (noteId: string) => void | Promise<void>;
  onRename: (noteId: string, title: string) => void | Promise<void>;
  onRetry: (noteId: string) => void | Promise<void>;
}) {
  // What the reload glyph does depends on how far the note got: a note with a
  // transcript only needs its summary re-run, anything earlier needs transcribing.
  const regenerate = canRegenerate(note)
    ? {
        label: note.transcript
          ? "Regenerate summary"
          : note.status === "failed"
            ? "Retry transcription"
            : "Start transcription",
      }
    : null;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.title);
  const [busy, setBusy] = useState(false);

  async function commitRename() {
    setEditing(false);
    if (draft.trim() && draft !== note.title) {
      setBusy(true);
      try {
        await onRename(note.id, draft);
      } finally {
        setBusy(false);
      }
    }
  }

  return (
    <article className="reveal border-t border-rule py-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        {editing ? (
          <input
            autoFocus
            className="field max-w-sm"
            onBlur={commitRename}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") commitRename();
              if (event.key === "Escape") setEditing(false);
            }}
            value={draft}
          />
        ) : (
          <h2 className="text-lg font-medium tracking-tight">{note.title}</h2>
        )}
        <span className="micro">{note.status}</span>
      </div>

      <div className="mt-1 flex items-center gap-2">
        <p className="nums text-[11px] text-muted">
          {note.filename} · {formatBytes(note.size_bytes)}
          {note.duration_seconds ? ` · ${formatDuration(note.duration_seconds)}` : ""} ·{" "}
          {note.language_code} · {new Date(note.created_at).toLocaleString()}
        </p>
        {regenerate ? (
          <button
            aria-label={regenerate.label}
            className="shrink-0 text-[13px] leading-none text-muted hover:text-ink"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onRetry(note.id);
              } finally {
                setBusy(false);
              }
            }}
            title={regenerate.label}
            type="button"
          >
            ↻
          </button>
        ) : null}
      </div>

      <div className="mt-5 border-l-2 border-ink pl-4">
        <p className="micro">Transcript</p>
        <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-wrap">
          {note.transcript ?? "No transcript yet."}
        </p>
      </div>

      <div className="mt-5 border-l-2 border-rule pl-4">
        <p className="micro">Summary</p>
        {note.summary ? (
          <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-wrap text-muted">
            {note.summary}
          </p>
        ) : (
          <p className="mt-2 text-[15px] text-muted">
            {note.status === "summarising" ? "Writing the summary…" : "No summary yet."}
          </p>
        )}
      </div>

      {note.status === "queued" || note.status === "transcribing" ? (
        <p className="micro mt-4 normal-case tracking-normal">
          {note.status === "queued"
            ? "Waiting for a worker to pick this up."
            : "Transcribing in the background. This can take a couple of minutes for long recordings."}
        </p>
      ) : null}

      {note.status === "summarising" ? (
        <p className="micro mt-4 normal-case tracking-normal">
          Transcript is ready. Writing the summary.
        </p>
      ) : null}

      {note.error ? (
        <p className="mt-4 text-[13px]" role="alert">
          {note.error.message}
        </p>
      ) : null}

      <div className="mt-6 flex gap-2">
        <button
          className="btn"
          disabled={busy}
          onClick={() => downloadTranscript(note)}
          type="button"
        >
          Download
        </button>
        <button
          className="btn"
          disabled={busy}
          onClick={() => {
            setDraft(note.title);
            setEditing(true);
          }}
          type="button"
        >
          Rename
        </button>
        <button className="btn" disabled={busy} onClick={() => onDelete(note.id)} type="button">
          Delete
        </button>
      </div>
    </article>
  );
}
