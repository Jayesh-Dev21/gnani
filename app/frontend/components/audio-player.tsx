"use client";

import { useEffect, useRef, useState } from "react";

function PlayIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5.5v13l11-6.5-11-6.5Z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M7 5h3.2v14H7zM13.8 5H17v14h-3.2z" />
    </svg>
  );
}

function VolumeIcon({ level }: { level: "high" | "low" | "muted" }) {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M4 9.5h3.2L11.5 6v12L7.2 14.5H4z" strokeLinejoin="round" />
      {level === "muted" ? (
        <path d="M15 9.5l4 5m0-5l-4 5" strokeLinecap="round" />
      ) : level === "low" ? (
        <path d="M14.5 10.5a3 3 0 0 1 0 3" strokeLinecap="round" />
      ) : (
        <path
          d="M14.5 9a4.5 4.5 0 0 1 0 6M17 7a7.5 7.5 0 0 1 0 10"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function AudioPlayer({
  src,
  label,
  seekTo,
}: {
  src: string;
  label: string;
  seekTo: { seconds: number; n: number } | null;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onLoaded = () => setDuration(audio.duration);
    const onTime = () => setCurrentTime(audio.currentTime);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onEnded = () => setPlaying(false);

    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);

    return () => {
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
    };
  }, []);

  // A transcript timestamp asks for a jump. Seeking before metadata loads is
  // applied once the duration is known.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !seekTo) return;
    const jump = () => {
      audio.currentTime = Math.max(0, seekTo.seconds);
      setCurrentTime(audio.currentTime);
    };
    if (Number.isFinite(audio.duration) && audio.duration > 0) jump();
    else audio.addEventListener("loadedmetadata", jump, { once: true });
    return () => audio.removeEventListener("loadedmetadata", jump);
  }, [seekTo]);

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) await audio.play();
    else audio.pause();
  }

  function seek(value: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = value;
    setCurrentTime(value);
  }

  function changeVolume(value: number) {
    const audio = audioRef.current;
    setVolume(value);
    if (!audio) return;
    audio.volume = value;
    if (value > 0) {
      audio.muted = false;
      setMuted(false);
    }
  }

  function toggleMute() {
    const audio = audioRef.current;
    if (!audio) return;
    const next = !muted;
    audio.muted = next;
    setMuted(next);
  }

  const level = muted || volume === 0 ? "muted" : volume < 0.5 ? "low" : "high";

  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <audio aria-label={label} preload="metadata" ref={audioRef} src={src} className="audio-source" />

      <button
        aria-label={playing ? "Pause" : "Play"}
        className="flex h-8 w-8 shrink-0 items-center justify-center border border-rule text-ink hover:border-ink"
        onClick={toggle}
        type="button"
      >
        {playing ? <PauseIcon /> : <PlayIcon />}
      </button>

      <span className="nums shrink-0 text-[11px] text-muted">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>

      <input
        aria-label="Seek"
        className="min-w-0 flex-1 accent-ink"
        disabled={duration === 0}
        max={duration || 0}
        min={0}
        onChange={(event) => seek(Number(event.target.value))}
        step={0.01}
        style={{
          background: `linear-gradient(to right, var(--ink) ${duration ? (currentTime / duration) * 100 : 0}%, var(--rule) ${duration ? (currentTime / duration) * 100 : 0}%)`,
        }}
        type="range"
        value={currentTime}
      />

      <div className="group/volume flex shrink-0 items-center gap-2">
        <button
          aria-label={muted ? "Unmute" : "Mute"}
          className="flex h-8 w-6 shrink-0 items-center justify-center text-muted hover:text-ink"
          onClick={toggleMute}
          type="button"
        >
          <VolumeIcon level={level} />
        </button>

        <input
          aria-label="Volume"
          className="w-0 shrink-0 accent-ink opacity-0 transition-[width,opacity] duration-200 ease-out group-focus-within/volume:w-20 group-focus-within/volume:opacity-100 group-hover/volume:w-20 group-hover/volume:opacity-100"
          max={1}
          min={0}
          onChange={(event) => changeVolume(Number(event.target.value))}
          step={0.01}
          style={{
            background: `linear-gradient(to right, var(--ink) ${volume * 100}%, var(--rule) ${volume * 100}%)`,
          }}
          type="range"
          value={muted ? 0 : volume}
        />
      </div>
    </div>
  );
}