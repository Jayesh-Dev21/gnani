"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { authClient } from "@/lib/auth-client";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-up");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending) return;

    setPending(true);
    setError(null);
    const result =
      mode === "sign-up"
        ? await authClient.signUp.email({ email, password, name: email })
        : await authClient.signIn.email({ email, password });

    if (result.error) {
      setError(result.error.message ?? "Something went wrong");
      setPending(false);
      return;
    }

    router.replace("/");
    router.refresh();
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-16">
      <div className="w-full max-w-sm">
        <p className="micro">Audio Notes</p>
        <h1 className="mt-3 text-2xl font-medium tracking-tight">
          {mode === "sign-up" ? "Create an account" : "Sign in"}
        </h1>

        <form className="mt-8 flex flex-col gap-4" onSubmit={submit}>
          <div className="flex flex-col gap-1">
            <label className="micro" htmlFor="email">
              Email
            </label>
            <input
              autoComplete="email"
              className="field"
              id="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="micro" htmlFor="password">
              Password
            </label>
            <input
              autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
              className="field"
              id="password"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </div>

          {error ? (
            <p className="text-[13px]" role="alert">
              {error}
            </p>
          ) : null}

          <button className="btn btn-primary" disabled={pending} type="submit">
            {pending ? "Working" : mode === "sign-up" ? "Create account" : "Sign in"}
          </button>
        </form>

        <button
          className="micro mt-6 hover:text-ink"
          onClick={() => {
            setMode(mode === "sign-up" ? "sign-in" : "sign-up");
            setError(null);
          }}
          type="button"
        >
          {mode === "sign-up" ? "Have an account? Sign in" : "No account? Sign up"}
        </button>

        <p className="micro mt-10 leading-relaxed normal-case tracking-normal">
          <Link className="underline underline-offset-4 hover:text-ink" href="/architecture">
            How this system works
          </Link>
        </p>
      </div>
    </main>
  );
}