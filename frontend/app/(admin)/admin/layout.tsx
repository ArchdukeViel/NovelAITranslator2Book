import { AdminShell } from "@/components/admin/admin-shell";
import { AdminAuthGuard } from "@/components/admin/admin-auth-guard";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminAuthGuard>
      <AdminShell>{children}</AdminShell>
    </AdminAuthGuard>
  );
}
