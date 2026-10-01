import type { Note } from "@/lib/api";

export function AudioPlayer({ note }: { note: Note }) {
  if (!note.audio_url) return null;

  return (
    <audio
      className="w-full"
      controls
      preload="metadata"
      src={note.audio_url}
      aria-label={`Audio for ${note.title}`}
    />
  );
}