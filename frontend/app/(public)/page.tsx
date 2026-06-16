import { redirect } from "next/navigation";

export default function PublicIndexPage() {
  redirect("/home");
}
