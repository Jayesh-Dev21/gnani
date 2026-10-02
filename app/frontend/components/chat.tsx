"use client";

import { useEffect, useRef, useState } from "react";

import { addSession, deleteSession, useSessions } from "@/lib/notes";

import { Composer } from "./composer";
import { SessionCard } from "./session-card";
import { Sidebar } from "./sidebar";

export function Chat() {
  const notes = useSessions();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const selected =
    notes.find((note) => note.id === selectedId) ?? notes[0] ?? null;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [selected?.id]);

  function startNew() {
    setSelectedId(null);
    document.getElementById("composer-file")?.click();
  }

  function remove(id: string) {
    deleteSession(id);
    setSelectedId(null);
  }

  return (
    <div className="flex min-h-0 flex-1">
      <div className="hidden md:block">
        <Sidebar
          notes={notes}
          onNew={startNew}
          onSelect={setSelectedId}
          selectedId={selected?.id ?? null}
        />
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto px-6">
          <div className="mx-auto max-w-3xl">
            {selected ? (
              <SessionCard key={selected.id} note={selected} onDelete={remove} />
            ) : (
              <div className="py-24">
                <h1 className="max-w-md text-3xl leading-tight font-medium tracking-tight">
                  Upload a recording, get a transcript you can read.
                </h1>
                <p className="micro mt-6 max-w-sm leading-relaxed normal-case tracking-normal">
                  Audio stays on the server. Transcription runs in the background,
                  so long recordings keep working while you wait.
                </p>
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <Composer
          onUploaded={(note) => {
            addSession(note);
            setSelectedId(note.id);
          }}
        />
      </div>
    </div>
  );
}
