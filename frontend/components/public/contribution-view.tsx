import { AlertCircle } from "lucide-react";

export function ContributionView() {
  return (
    <section
      aria-labelledby="contribution-disabled-title"
      className="rounded-md border border-border bg-muted/50 p-6"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="space-y-2">
          <h1 id="contribution-disabled-title" className="text-2xl font-bold">
            Contribution credentials are not available yet.
          </h1>
          <p className="text-sm text-muted-foreground">
            This feature requires a future gated backend.
          </p>
          <p className="text-sm font-medium text-foreground">
            Do not submit API keys here.
          </p>
        </div>
      </div>
    </section>
  );
}
