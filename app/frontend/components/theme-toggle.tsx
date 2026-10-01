"use client";

import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();

  return (
    <button
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="micro hover:text-ink"
      onClick={toggle}
      type="button"
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}