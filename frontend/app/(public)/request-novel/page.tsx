import { redirect } from "next/navigation";

export default function LegacyRequestNovelPage() {
  redirect("/account/request-novels");
}
