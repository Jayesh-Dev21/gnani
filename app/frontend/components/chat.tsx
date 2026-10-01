"use client";

import { useEffect, useRef } from "react";

import { addSession, useSessions } from "@/lib/notes";

import { Composer } from "./composer";
import { SessionCard } from "./session-card";

export function Chat() {
  const notes = useSessions();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [notes.length]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-6">
        <div className="mx-auto max-w-3xl">
          {notes.length === 0 ? (
            <div className="py-24">
              <h1 className="max-w-md text-3xl leading-tight font-medium tracking-tight">
                Upload a recording, get a transcript you can read.
              </h1>
              <p className="micro mt-6 max-w-sm leading-relaxed normal-case tracking-normal">
                Audio stays on the server. Transcription runs in the background, so long
                recordings keep working while you wait.
              </p>
            </div>
          ) : (
            [...notes]
              .reverse()
              .map((note) => <SessionCard key={note.id} note={note} />)
          )}
          <div ref={endRef} />
        </div>
      </div>

      <Composer onUploaded={addSession} />
    </div>
  );
}