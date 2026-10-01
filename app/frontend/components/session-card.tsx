"use client";

import { useState } from "react";

import type { Note } from "@/lib/api";
import { deleteSession, downloadTranscript, renameSession } from "@/lib/notes";

import { AudioPlayer } from "./audio-player";

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

export function SessionCard({ note }: { note: Note }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.title);

  function commitRename() {
    setEditing(false);
    renameSession(note.id, draft);
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

      <p className="nums mt-1 text-[11px] text-muted">
        {note.filename} · {formatBytes(note.size_bytes)} · {note.language_code} ·{" "}
        {new Date(note.created_at).toLocaleString()}
      </p>

      <div className="mt-4">
        <AudioPlayer note={note} />
      </div>

      <div className="mt-5 border-l-2 border-ink pl-4">
        <p className="micro">Transcript</p>
        <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-wrap">
          {note.transcript ?? "No transcript yet."}
        </p>
      </div>

      <div className="mt-5 border-l-2 border-rule pl-4">
        <p className="micro">Summary</p>
        <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-wrap text-muted">
          {note.summary ?? "No summary yet."}
        </p>
      </div>

      {note.error ? (
        <p className="mt-4 text-[13px]" role="alert">
          {note.error.code}: {note.error.message}
        </p>
      ) : null}

      <div className="mt-6 flex gap-2">
        <button className="btn" onClick={() => downloadTranscript(note)} type="button">
          Download
        </button>
        <button
          className="btn"
          onClick={() => {
            setDraft(note.title);
            setEditing(true);
          }}
          type="button"
        >
          Rename
        </button>
        <button className="btn" onClick={() => deleteSession(note.id)} type="button">
          Delete
        </button>
      </div>
    </article>
  );
}