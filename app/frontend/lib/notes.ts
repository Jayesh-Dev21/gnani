"use client";

import { useCallback, useEffect, useState } from "react";

import { deleteNote, listNotes, renameNote } from "./api";
import type { Note, NoteSummary } from "./api";

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
  };
}

export function downloadTranscript(note: Note): void {
  const body = [
    `# ${note.title}`,
    "",
    `Recorded: ${note.created_at}`,
    `Language: ${note.language_code}`,
    "",
    "## Transcript",
    "",
    note.transcript ?? "(no transcript yet)",
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
