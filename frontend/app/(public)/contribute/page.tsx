import { ContributionView } from "@/components/public/contribution-view";

export default function ContributePage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-3xl font-semibold tracking-normal">Contribute</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Public provider/API key contribution is intentionally gated until the secure backend lifecycle exists.
        </p>
      </header>
      <ContributionView />
    </main>
  );
}
