import { defineConfig } from "drizzle-kit";

export default defineConfig({
  schema: "./lib/db/auth-schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: {
    url:
      process.env.DATABASE_URL ??
      "postgresql://audio_notes:audio_notes@localhost:5432/audio_notes",
  },
});