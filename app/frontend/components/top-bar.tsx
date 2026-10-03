"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { authClient } from "@/lib/auth-client";

import { ThemeToggle } from "./theme-toggle";

export function TopBar({ email }: { email: string }) {
  const router = useRouter();

  async function signOut() {
    await authClient.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="flex items-center justify-between border-b border-rule px-4 py-4 sm:px-6">
      <div className="flex items-baseline gap-3">
        <span className="text-sm font-medium tracking-tight">Audio Notes</span>
      </div>
      <nav className="flex items-center gap-3 sm:gap-6">
        <ThemeToggle />
        <Link className="micro hover:text-ink" href="/notes">
          Saved
        </Link>
        <Link className="micro hidden hover:text-ink min-[420px]:inline" href="/architecture">
          Architecture
        </Link>
        <details className="relative">
          <summary
            aria-label="Account menu"
            className="flex h-7 w-7 cursor-pointer list-none items-center justify-center rounded-full border border-rule text-[11px] uppercase hover:border-ink [&::-webkit-details-marker]:hidden"
          >
            {email.slice(0, 1)}
          </summary>
          <div className="absolute right-0 z-10 mt-2 w-56 border border-rule bg-paper p-3">
            <p className="nums truncate text-[11px] text-muted">{email}</p>
            <button
              className="micro mt-3 block hover:text-ink"
              onClick={signOut}
              type="button"
            >
              Sign out
            </button>
          </div>
        </details>
      </nav>
    </header>
  );
}