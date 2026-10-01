"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { authClient } from "@/lib/auth-client";

export function TopBar({ email }: { email: string }) {
  const router = useRouter();

  async function signOut() {
    await authClient.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="flex items-center justify-between border-b border-rule px-6 py-4">
      <div className="flex items-baseline gap-3">
        <span className="text-sm font-medium tracking-tight">Audio Notes</span>
        <span className="micro hidden sm:inline">upload · transcribe · read</span>
      </div>
      <nav className="flex items-center gap-6">
        <Link className="micro hover:text-ink" href="/notes">
          Saved
        </Link>
        <Link className="micro hover:text-ink" href="/architecture">
          Architecture
        </Link>
        <span className="nums hidden text-[11px] text-muted md:inline">{email}</span>
        <button className="micro hover:text-ink" onClick={signOut} type="button">
          Sign out
        </button>
      </nav>
    </header>
  );
}