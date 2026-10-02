"use client";

import { useRef, useState } from "react";

import { uploadNote } from "@/lib/api";
import type { Note } from "@/lib/api";
import { formatDuration, readAudioDuration } from "@/lib/audio-meta";

const MAX_UPLOAD_MB = 10;

const DEFAULT_LANGUAGE = "en-IN";

const LANGUAGES = [
  { value: DEFAULT_LANGUAGE, label: "English (default)" },
  { value: "bn-IN", label: "Bengali" },
  { value: "en-IN", label: "English" },
  { value: "gu-IN", label: "Gujarati", note: "not on Batch STT" },
  { value: "hi-IN", label: "Hindi" },
  { value: "kn-IN", label: "Kannada" },
  { value: "ml-IN", label: "Malayalam" },
  { value: "mr-IN", label: "Marathi" },
  { value: "pa-IN", label: "Punjabi", note: "not on Batch STT" },
  { value: "ta-IN", label: "Tamil" },
  { value: "te-IN", label: "Telugu" },
];

export function Composer({ onUploaded }: { onUploaded: (note: Note) => void | Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState(DEFAULT_LANGUAGE);
  const [duration, setDuration] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function pick(selected: File | null) {
    setError(null);
    if (!selected) {
      setFile(null);
      setDuration(null);
      return;
    }
    if (!selected.type.startsWith("audio/")) {
      setError(`${selected.name} is not audio.`);
      return;
    }
    if (selected.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`${selected.name} is larger than ${MAX_UPLOAD_MB}MB.`);
      return;
    }
    setFile(selected);
    if (!title) setTitle(selected.name.replace(/\.[^.]+$/, ""));
    // Read the duration here rather than after the upload: it is free locally and
    // it tells the user how long a recording is before anything is sent anywhere.
    setDuration(null);
    void readAudioDuration(selected).then(setDuration);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || pending) return;

    setPending(true);
    setError(null);
    try {
      const note = await uploadNote(
        file,
        title || undefined,
        language || undefined,
        duration,
      );
      onUploaded(note);
      setFile(null);
      setTitle("");
      setDuration(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <form
      className="border-t border-rule bg-paper px-6 py-4"
      onSubmit={submit}
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-3">
        {error ? (
          <p className="reveal text-[13px] text-ink" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <label className="micro" htmlFor="composer-file">
              Audio file
            </label>
            <input
              ref={inputRef}
              accept="audio/*"
              className="peer sr-only"
              id="composer-file"
              onChange={(event) => pick(event.target.files?.[0] ?? null)}
              type="file"
            />
            <label
              className="field peer-focus-visible:outline-2 peer-focus-visible:-outline-offset-1 peer-focus-visible:outline-ink flex cursor-pointer items-center justify-between gap-3"
              htmlFor="composer-file"
            >
              <span className="shrink-0 text-[11px] tracking-[0.12em] uppercase">
                Browse
              </span>
              <span className="truncate text-[13px] text-muted">
                {file ? file.name : "No file selected"}
              </span>
            </label>
          </div>

          <div className="flex w-full flex-col gap-1 sm:w-48">
            <label className="micro" htmlFor="composer-title">
              Name
            </label>
            <input
              className="field"
              id="composer-title"
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Untitled recording"
              value={title}
            />
          </div>

          <div className="flex w-full flex-col gap-1 sm:w-44">
            <label className="micro" htmlFor="composer-language">
              Language
            </label>
            <select
              className="field"
              id="composer-language"
              onChange={(event) => setLanguage(event.target.value)}
              value={language}
            >
              {LANGUAGES.map((option) => (
                <option
                  disabled={Boolean(option.note)}
                  key={option.value}
                  title={option.note}
                  value={option.value}
                >
                  {option.label}
                  {option.note ? ` (${option.note})` : ""}
                </option>
              ))}
            </select>
          </div>

          <button className="btn btn-primary btn-lg" disabled={!file || pending} type="submit">
            {pending ? "Uploading" : "Transcribe"}
          </button>
        </div>

        <p className="micro">
          {file
            ? [
                file.name,
                `${(file.size / 1024 / 1024).toFixed(2)}MB`,
                formatDuration(duration) || "reading duration…",
              ].join(" · ")
            : `Up to ${MAX_UPLOAD_MB}MB · wav mp3 m4a flac ogg webm`}
        </p>
      </div>
    </form>
  );
}