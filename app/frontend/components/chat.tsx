"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getNote } from "@/lib/api";
import type { Note } from "@/lib/api";
import { useSessions } from "@/lib/notes";

import { Composer } from "./composer";
import { PlaybackBar } from "./playback-bar";
import { SessionCard } from "./session-card";
import { Sidebar } from "./sidebar";

export function Chat() {
  const { notes, error, refresh, rename, remove, retry } = useSessions();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [note, setNote] = useState<Note | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const openNote = useCallback(async (id: string) => {
    try {
      setNote(await getNote(id));
    } catch {
      setNote(null);
    }
  }, []);

  const target = notes.find((entry) => entry.id === selectedId) ?? notes[0] ?? null;
  const targetId = target?.id ?? null;

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading a note is an external system read
    if (!targetId) setNote(null);
  }, [targetId]);

  // The list polls while a note is in flight; re-read the open note when its
  // status moves so the transcript and any error arrive without a second timer.
  const targetStatus = target?.status ?? null;

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a status change is an external system read
    if (targetId) void openNote(targetId);
  }, [targetId, targetStatus, openNote]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [note?.id]);

  function startNew() {
    setSelectedId(null);
    setNote(null);
  }

  return (
    <div className="flex min-h-0 flex-1">
      <div className="hidden md:block">
        <Sidebar
          notes={notes}
          onNew={startNew}
          onSelect={setSelectedId}
          selectedId={target?.id ?? null}
        />
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto px-6">
          <div className="mx-auto max-w-3xl">
            {error ? (
              <p className="py-6 text-[13px]" role="alert">
                {error}
              </p>
            ) : null}

            {note ? (
              <SessionCard
                key={note.id}
                note={note}
                onDelete={async (id) => {
                  await remove(id);
                  setSelectedId(null);
                  setNote(null);
                }}
                onRename={rename}
                onRetry={retry}
              />
            ) : (
              !error && (
                <div className="py-24">
                  <h1 className="max-w-md text-3xl leading-tight font-medium tracking-tight">
                    Upload a recording, get a transcript you can read.
                  </h1>
                  <p className="micro mt-6 max-w-sm leading-relaxed normal-case tracking-normal">
                    Audio stays on the server. Transcription runs in the background,
                    so long recordings keep working while you wait.
                  </p>
                </div>
              )
            )}
            <div ref={endRef} />
          </div>
        </div>

        {note ? (
          <PlaybackBar note={note} />
        ) : (
          <Composer
            onUploaded={async (created) => {
              await refresh();
              setSelectedId(created.id);
            }}
          />
        )}
      </div>
    </div>
  );
}
