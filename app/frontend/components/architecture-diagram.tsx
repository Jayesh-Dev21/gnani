import type { ReactNode } from "react";

/**
 * A deliberately plain box diagram: boxes, hairlines and a few labels, no library
 * and no layout engine. It uses the same colour tokens as the rest of the
 * interface, so it flips with the theme.
 *
 * Wires are orthogonal and only travel through the empty channels between boxes,
 * so nothing crosses a label.
 */

const BOX = "fill-none stroke-[var(--rule)]";
const TITLE = "fill-[var(--ink)] text-[11px] tracking-[0.12em] uppercase";
const LINE = "fill-[var(--muted)] text-[10px]";
const WIRE = "stroke-[var(--muted)] opacity-50"
const LABEL = "fill-[var(--muted)] text-[9px] tracking-[0.1em] uppercase"

function Box({
  x,
  y,
  w,
  title,
  lines,
  children,
}: {
  x: number;
  y: number;
  w: number;
  title: string;
  lines: string[];
  children?: ReactNode;
}) {
  return (
    <g>
      <rect className={BOX} height={20 + lines.length * 14} width={w} x={x} y={y} />
      <text className={TITLE} x={x + 10} y={y + 19}>
        {title}
      </text>
      {lines.map((line, index) => (
        <text className={LINE} key={line} x={x + 10} y={y + 35 + index * 14}>
          {line}
        </text>
      ))}
      {children}
    </g>
  );
}

export function ArchitectureDiagram() {
  return (
    <figure className="mt-6">
      <svg
        aria-label="Flow: a browser reaches nginx on one EC2 instance, which proxies to the Next.js frontend and the FastAPI. The API writes to Postgres and stores audio in R2. A worker claims notes from the queue, reads the audio out of R2, and calls Gnani for speech to text and Groq for the summary."
        className="w-full"
        role="img"
        viewBox="0 0 700 470"
      >
        <defs>
          <marker
            id="arrow"
            markerHeight="6"
            markerWidth="6"
            orient="auto-start-reverse"
            refX="5"
            refY="3"
            viewBox="0 0 6 6"
          >
            <path d="M0,0 L6,3 L0,6 z" fill="currentColor" opacity="0.45" />
          </marker>
        </defs>

        <Box lines={["TLS at the edge", "22, 80, 443 only"]} title="Browser" w={150} x={20} y={20} />
        <Box lines={["reverse proxy", "deploy/nginx.conf"]} title="Nginx · EC2" w={160} x={250} y={20} />
        <Box lines={["Next.js on 3000", "Better Auth"]} title="Frontend" w={170} x={490} y={20} />
        <Box lines={["private bucket", "presigned URLs"]} title="Cloudflare R2" w={150} x={20} y={150} />
        <Box lines={["FastAPI on 8000", "verifies JWTs", "streams audio"]} title="API" w={170} x={490} y={150} />
        <Box lines={["Gnani Batch STT", "Groq summary"]} title="Providers" w={150} x={20} y={300} />
        <Box lines={["notes, sessions", "queue tables"]} title="Postgres" w={160} x={250} y={300} />
        <Box lines={["claims a note", "lease + heartbeat", "sweeps orphans"]} title="Worker" w={170} x={490} y={300} />

        <g fill="none" markerEnd="url(#arrow)">
          {/* browser -> nginx -> frontend */}
          <path className={WIRE} d="M170 47 H250" />
          <path className={WIRE} d="M410 47 H490" />
          {/* nginx -> api, down the right channel */}
          <path className={WIRE} d="M330 62 V112 H575 V150" />
          {/* api -> r2, straight across the empty middle */}
          <path className={WIRE} d="M490 176 H170" />
          {/* api -> postgres */}
          <path className={WIRE} d="M555 218 V262 H330 V300" />
          {/* worker -> postgres (claims + writes rows) */}
          <path className={WIRE} d="M490 326 H410" />
          {/* worker -> providers, along the bottom channel */}
          <path className={WIRE} d="M545 358 V396 H95 V348" />
          {/* worker -> r2, up the left channel into the bucket's bottom edge */}
          <path className={WIRE} d="M620 358 V430 H140 V198" />
        </g>

        <text className={LABEL} x={352} y={106}>
          /api
        </text>
        <text className={LABEL} x={300} y={258}>
          rows
        </text>
        <text className={LABEL} x={420} y={322}>
          claim
        </text>
        <text className={LABEL} x={330} y={190}>
          audio
        </text>
        <text className={LABEL} x={300} y={392}>
          transcript
        </text>
        <text className={LABEL} x={300} y={432}>
          fetch
        </text>
      </svg>
      <figcaption className="mt-3 text-[11px] leading-relaxed text-muted">
        Only nginx is reachable from outside. The browser talks to the frontend and the API;
        the API and the worker both read and write Postgres and R2, and only the worker calls
        Gnani and Groq.
      </figcaption>
    </figure>
  );
}