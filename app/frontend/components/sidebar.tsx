"use client";

import type { NoteSummary } from "@/lib/api";

function formatDate(value: string): string {
  const date = new Date(value);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString([], { day: "2-digit", month: "short" });
}

export function Sidebar({
  notes,
  selectedId,
  onSelect,
  onNew,
}: {
  notes: NoteSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-rule">
      <div className="px-4 py-4">
        <button className="btn w-full" onClick={onNew} type="button">
          New recording
        </button>
      </div>

      <div className="flex items-center justify-between px-4 pb-2">
        <p className="micro">Transcripts</p>
        <span className="nums text-[11px] text-muted">{notes.length}</span>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {notes.length === 0 ? (
          <p className="micro px-2 py-3 leading-relaxed normal-case tracking-normal">
            Nothing yet. Upload a recording to start.
          </p>
        ) : (
          <ul className="flex flex-col">
            {notes.map((note) => {
              const active = note.id === selectedId;
              return (
                <li key={note.id}>
                  <button
                    className={`flex w-full flex-col items-start gap-1 border-l-2 px-3 py-2 text-left transition-colors ${
                      active
                        ? "border-ink bg-rule/40"
                        : "border-transparent hover:border-rule hover:bg-rule/20"
                    }`}
                    onClick={() => onSelect(note.id)}
                    type="button"
                  >
                    <span className="w-full truncate text-[13px] font-medium">
                      {note.title}
                    </span>
                    <span className="nums text-[11px] text-muted">
                      {formatDate(note.created_at)} · {note.status}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </nav>
    </aside>
  );
}