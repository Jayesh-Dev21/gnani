"use client";

import { useSyncExternalStore } from "react";

import type { Note } from "./api";

const STORAGE_KEY = "audio-notes.sessions.v1";
const EMPTY: Note[] = [];

const listeners = new Set<() => void>();
let cache: Note[] | null = null;

function readStorage(): Note[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const notes = raw ? (JSON.parse(raw) as Note[]) : [];
    return notes.sort((a, b) => b.created_at.localeCompare(a.created_at));
  } catch {
    return EMPTY;
  }
}

function getSnapshot(): Note[] {
  cache ??= readStorage();
  return cache;
}

function getServerSnapshot(): Note[] {
  return EMPTY;
}

function subscribe(listener: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) {
      cache = null;
      emit();
    }
  };

  listeners.add(listener);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

function emit(): void {
  for (const listener of listeners) listener();
}

function commit(notes: Note[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
  cache = notes;
  emit();
}

export function useSessions(): Note[] {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function addSession(note: Note): void {
  commit([note, ...getSnapshot()]);
}

export function renameSession(noteId: string, title: string): void {
  commit(
    getSnapshot().map((note) =>
      note.id === noteId ? { ...note, title: title.trim() || note.title } : note,
    ),
  );
}

export function deleteSession(noteId: string): void {
  commit(getSnapshot().filter((note) => note.id !== noteId));
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