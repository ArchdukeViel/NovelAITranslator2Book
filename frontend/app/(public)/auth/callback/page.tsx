import { StaticPage } from "@/components/public/static-page";

export default function AuthCallbackPage() {
  return (
    <StaticPage
      title="Authentication Callback"
      description="Sign-in is completed by the backend. If you arrived here directly, return to login and try again."
    />
  );
}
