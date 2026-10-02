"use client";

import { useTheme } from "@/lib/theme";

function Sun() {
  return (
    <svg
      aria-hidden="true"
      className="h-[15px] w-[15px]"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <circle cx="12" cy="12" r="4.25" />
      <path
        d="M12 2.75v2.5M12 18.75v2.5M2.75 12h2.5M18.75 12h2.5M5.4 5.4l1.77 1.77M16.83 16.83l1.77 1.77M18.6 5.4l-1.77 1.77M7.17 16.83l-1.77 1.77"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Moon() {
  return (
    <svg
      aria-hidden="true"
      className="h-[15px] w-[15px]"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path
        d="M20 14.2A8.2 8.2 0 0 1 9.8 4a8.4 8.4 0 1 0 10.2 10.2Z"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      aria-label={`Switch to ${next} mode`}
      className="flex h-7 w-7 items-center justify-center text-muted hover:text-ink"
      onClick={toggle}
      title={`Switch to ${next} mode`}
      type="button"
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </button>
  );
}