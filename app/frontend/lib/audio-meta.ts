/** Read an audio file's duration in the browser, before it is uploaded. */

export function readAudioDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();

    const finish = (seconds: number | null) => {
      URL.revokeObjectURL(url);
      audio.removeAttribute("src");
      resolve(seconds);
    };

    audio.preload = "metadata";
    audio.onloadedmetadata = () => {
      const { duration } = audio;
      // Some containers report Infinity until they have decoded further.
      finish(Number.isFinite(duration) && duration > 0 ? duration : null);
    };
    audio.onerror = () => finish(null);
    audio.src = url;
  });
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "";
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
}
