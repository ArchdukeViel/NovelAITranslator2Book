import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AdminShell } from "@/components/admin/admin-shell";
import { AdminAuthGuard } from "@/components/admin/admin-auth-guard";

// Session cookie issued by the backend (HTTP-only, signed). The backend
// require_role("owner") check remains the authoritative security boundary;
// this presence check only prevents rendering private chrome for visitors
// who cannot possibly hold a session.
const ADMIN_SESSION_COOKIE = "novelai_session";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = (await cookies()).get(ADMIN_SESSION_COOKIE);
  if (!session?.value) {
    redirect("/");
  }

  return (
    <AdminAuthGuard>
      <AdminShell>{children}</AdminShell>
    </AdminAuthGuard>
  );
}
