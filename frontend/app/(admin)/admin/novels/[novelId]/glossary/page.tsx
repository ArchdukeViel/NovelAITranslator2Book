import { AdminGlossaryShell } from "@/components/admin/glossary/admin-glossary-shell";

export default async function AdminNovelGlossaryPage({
  params,
}: {
  params: Promise<{ novelId: string }>;
}) {
  const { novelId } = await params;
  return <AdminGlossaryShell novelId={novelId} />;
}
