import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { jwt } from "better-auth/plugins";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import * as authSchema from "./db/auth-schema";

const client = postgres(process.env.DATABASE_URL ?? "", { max: 1 });

export const auth = betterAuth({
  database: drizzleAdapter(drizzle(client, { schema: authSchema }), {
    provider: "pg",
    schema: {
      user: authSchema.user,
      session: authSchema.session,
      account: authSchema.account,
      verification: authSchema.verification,
      jwks: authSchema.jwks,
    },
  }),
  emailAndPassword: {
    enabled: true,
  },
  plugins: [jwt()],
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: process.env.BETTER_AUTH_URL,
  trustedOrigins: (
    process.env.BETTER_AUTH_TRUSTED_ORIGINS ??
    "http://localhost:3000,http://127.0.0.1:3000"
  )
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
});