"use client";

import { useCallback, useEffect, useState } from "react";

import { deleteNote, listNotes, renameNote, retryNote } from "./api";
import type { Note, NoteSummary } from "./api";

function formatStamp(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
}

export function useSessions() {
  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setNotes(await listNotes());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load notes");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial load from the API is an external system read
    void refresh();
  }, [refresh]);

  // Transcription runs as a job, so the status field is the only source of
  // progress. Poll only while something is actually in flight.
  const inFlight = notes.some(
    (note) =>
      note.status === "queued" ||
      note.status === "transcribing" ||
      note.status === "summarising",
  );

  useEffect(() => {
    if (!inFlight) return;
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [inFlight, refresh]);

  return {
    notes,
    error,
    refresh,
    rename: async (id: string, title: string) => {
      await renameNote(id, title);
      await refresh();
    },
    remove: async (id: string) => {
      await deleteNote(id);
      await refresh();
    },
    retry: async (id: string, target?: "transcription" | "summary") => {
      await retryNote(id, target);
      await refresh();
    },
  };
}

export function downloadTranscript(note: Note): void {
  const transcript = note.segments?.length
    ? note.segments
        .map((segment) => `[${formatStamp(segment.start)}] ${segment.text}`)
        .join("\n")
    : (note.transcript ?? "(no transcript yet)");
  const body = [
    `# ${note.title}`,
    "",
    `Recorded: ${note.created_at}`,
    `Language: ${note.language_code}`,
    "",
    "## Transcript",
    "",
    transcript,
    "",
    "## Summary",
    "",
    note.summary ?? "(no summary yet)",
    "",
  ].join("\n");

  const url = URL.createObjectURL(new Blob([body], { type: "text/markdown" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${note.title.replace(/[^\w-]+/g, "-").toLowerCase()}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}
