"use client";

import { useEffect, useState } from "react";

import type { Note } from "@/lib/api";
import { fetchAudio } from "@/lib/api";

import { AudioPlayer } from "./audio-player";

export function PlaybackBar({
  note,
  seekRequest,
}: {
  note: Note;
  seekRequest: { seconds: number; n: number } | null;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audioPath = note.audio_url;

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    void (async () => {
      try {
        const fetched = await fetchAudio(audioPath);
        if (cancelled || !fetched) return;
        objectUrl = fetched;
        setSrc(fetched);
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Audio unavailable");
        }
      }
    })();

    return () => {
      cancelled = true;
      // Only a blob URL is ours to release; a signed storage URL is not.
      if (objectUrl?.startsWith("blob:")) URL.revokeObjectURL(objectUrl);
    };
  }, [audioPath]);

  return (
    <div className="border-t border-rule bg-paper px-4 py-3 sm:px-6">
      <div className="mx-auto flex max-w-3xl items-center gap-3 sm:gap-4">
        <div className="w-24 min-w-0 shrink-0 sm:w-48">
          <p className="truncate text-[13px] font-medium">{note.title}</p>
          <p className="nums mt-0.5 text-[11px] text-muted">
            {note.status} · {note.language_code}
          </p>
        </div>

        {error ? (
          <p className="text-[13px] text-muted">Audio unavailable: {error}</p>
        ) : src ? (
          <AudioPlayer label={`Audio for ${note.title}`} seekTo={seekRequest} src={src} />
        ) : (
          <p className="micro">Loading audio</p>
        )}
      </div>
    </div>
  );
}