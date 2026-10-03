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
  // Title + one line per entry with room to spare: the old formula put the
  // last baseline a pixel below the box edge and long labels ran past the sides.
  const height = 30 + lines.length * 15;
  return (
    <g>
      <rect className={BOX} height={height} width={w} x={x} y={y} />
      <text className={TITLE} x={x + 12} y={y + 20}>
        {title}
      </text>
      {lines.map((line, index) => (
        <text className={LINE} key={line} x={x + 12} y={y + 40 + index * 15}>
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
        viewBox="0 0 720 480"
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

        <Box lines={["TLS at the edge", "22, 80, 443 only"]} title="Browser" w={170} x={20} y={20} />
        <Box lines={["reverse proxy", "deploy/nginx.conf"]} title="Nginx · EC2" w={180} x={270} y={20} />
        <Box lines={["Next.js on 3000", "Better Auth"]} title="Frontend" w={190} x={510} y={20} />
        <Box lines={["private bucket", "presigned URLs"]} title="Cloudflare R2" w={170} x={20} y={160} />
        <Box lines={["FastAPI on 8000", "verifies JWTs", "streams audio"]} title="API" w={190} x={510} y={160} />
        <Box lines={["Gnani Batch STT", "Groq summary"]} title="Providers" w={170} x={20} y={320} />
        <Box lines={["notes, sessions", "queue tables"]} title="Postgres" w={180} x={270} y={320} />
        <Box lines={["claims a note", "lease + heartbeat", "sweeps orphans"]} title="Worker" w={190} x={510} y={320} />

        <g fill="none" markerEnd="url(#arrow)">
          {/* browser -> nginx -> frontend */}
          <path className={WIRE} d="M190 47 H270" />
          <path className={WIRE} d="M450 47 H510" />
          {/* nginx -> api, down the right channel */}
          <path className={WIRE} d="M360 80 V118 H605 V160" />
          {/* api -> r2, straight across the empty middle */}
          <path className={WIRE} d="M510 198 H190" />
          {/* api -> postgres */}
          <path className={WIRE} d="M605 235 V272 H360 V320" />
          {/* worker -> postgres (claims + writes rows) */}
          <path className={WIRE} d="M510 358 H450" />
          {/* worker -> providers, along the bottom channel */}
          <path className={WIRE} d="M600 395 V436 H105 V368" />
          {/* worker -> r2, up the left channel into the bucket's bottom edge */}
          <path className={WIRE} d="M645 395 V466 H150 V220" />
        </g>

        <text className={LABEL} x={470} y={110}>
          /api
        </text>
        <text className={LABEL} x={330} y={266}>
          rows
        </text>
        <text className={LABEL} x={462} y={352}>
          claim
        </text>
        <text className={LABEL} x={330} y={190}>
          audio
        </text>
        <text className={LABEL} x={330} y={428}>
          transcript
        </text>
        <text className={LABEL} x={300} y={468}>
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