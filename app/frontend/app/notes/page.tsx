import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { SavedNotes } from "@/components/saved-notes";
import { TopBar } from "@/components/top-bar";
import { auth } from "@/lib/auth";

export default async function NotesPage() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/login");

  return (
    <>
      <TopBar email={session.user.email} />
      <SavedNotes />
    </>
  );
}