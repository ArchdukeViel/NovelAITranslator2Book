import { redirect } from "next/navigation";

export default function AdminNovelsRedirectPage() {
  redirect("/admin/library");
}
