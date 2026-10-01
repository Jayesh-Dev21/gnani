import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

const SECTIONS = [
  {
    heading: "Upload to transcript",
    body: `The browser streams the audio file to the FastAPI backend as multipart form data — never through a Next.js server action, which would buffer the whole body and block the request. The backend validates the type and size, writes the file under a generated key, inserts a notes row with status queued, and returns 201 with the note. Nothing waits on speech recognition; the response is immediate.\n\nA background worker claims queued notes, writes transcribing before it starts, and submits the file to Gnani's Batch STT API: create a job, start it, poll every ten seconds or slower until a terminal status, list the job's files, then download the transcript URL. When the transcript lands the worker writes it and the note becomes ready. The browser polls the note endpoint while the status is non-terminal and renders from the status field — polling is the only source of progress truth, no websockets or SSE.`,
  },
  {
    heading: "Where files live",
    body: `Audio goes to storage, never to the database and never to the repo. The notes row stores the object key, size, content type and duration. In development that storage is a local disk path behind a single module; production swaps in object storage with short-lived signed URLs, and nothing outside that module knows the difference. The browser plays audio with the native audio element, which uses HTTP range requests for seeking — so no audio is routed through the application server in production, and no chunking is written by hand.`,
  },
  {
    heading: "Long audio",
    body: `Gnani's synchronous endpoint caps audio at sixty seconds, which a two-minute recording blows straight through. Batch STT takes files up to four hours, so the app sends whole files and never chunks them — chunking would only add mid-word splice artefacts. Uploaded files are capped at ten megabytes today because development sends audio to Gnani by direct multipart upload, which has a per-file byte limit; with a real bucket the app switches to Gnani's cloud-storage source, which has no byte limit, and that cap becomes a configuration value rather than a hard limit.`,
  },
  {
    heading: "Synchronous vs background",
    body: `Only three things are synchronous: authentication, file validation, and the write of the notes row. Transcription runs in a worker process, separate from the API container, because a single transcription takes minutes — far longer than a request should ever hold a connection. The queue is Postgres-backed, so the API container defers a job by inserting a row and the worker claims it with a lock; if the API dies between the commit and the enqueue, a sweep on worker start re-enqueues any queued note that has no job. Retries with backoff are bounded: after the last attempt the note becomes failed with a real error code and message instead of hanging in queued forever.`,
  },
  {
    heading: "Failure and progress",
    body: `A note is always in exactly one of four states — queued, transcribing, ready, failed — and every transition is written to the database before the work begins, so a crashed worker leaves a truthful state rather than a spinner that never resolves. Failed notes store the provider's reason translated into something a user can act on, and the UI shows that message rather than a generic failure. Health is split in two: a liveness endpoint that never touches Postgres, storage or Gnani, so a dependency blip does not make Docker restart a healthy API, and readiness for everything else.`,
  },
  {
    heading: "Auth",
    body: `Better Auth runs inside Next.js and owns signup, login and sessions against its own tables. FastAPI is a resource server: it verifies the session token against Better Auth's published keys, rejects anything it did not issue, and scopes every query to the verified user id. It has no password hashing, no session table and no login endpoint. In local development a header-based bypass exists behind an environment flag, and the app refuses to start if that flag is set in production.`,
  },
  {
    heading: "What I would change with more time",
    body: `The transcript store is a client-side list right now, so notes live in one browser until the database lands. Storage would move to S3 or R2 with signed URLs, and Gnani's cloud-storage source would replace the direct multipart path. Transcripts would be chunked for display on very long recordings so the page does not render a single enormous block, and diarization would be exposed for two-speaker recordings. Summarisation is the one requirement still stubbed: the summary field exists and stays null rather than showing something invented. I would add request-level metrics and a queue dashboard before tuning anything else, because at this volume the interesting failures are timeouts and rate limits, not throughput.`,
  },
];

export default function ArchitecturePage() {
  return (
    <>
      <header className="flex items-center justify-between border-b border-rule px-6 py-4">
        <Link className="text-sm font-medium tracking-tight" href="/">
          Audio Notes
        </Link>
        <div className="flex items-center gap-6">
          <ThemeToggle />
          <span className="micro">Architecture</span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 overflow-y-auto px-6 py-12">
        <h1 className="max-w-xl text-3xl leading-tight font-medium tracking-tight">
          How the system works, end to end.
        </h1>
        <p className="micro mt-4">Next.js · FastAPI · Postgres · Gnani Batch STT</p>

        <div className="mt-12">
          {SECTIONS.map((section) => (
            <section className="border-t border-rule py-8" key={section.heading}>
              <h2 className="micro">{section.heading}</h2>
              <p className="mt-3 text-[15px] leading-relaxed whitespace-pre-wrap">
                {section.body}
              </p>
            </section>
          ))}
        </div>
      </main>
    </>
  );
}