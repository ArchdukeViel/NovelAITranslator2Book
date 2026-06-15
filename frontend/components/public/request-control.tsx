"use client";

export function RequestControl() {
  return (
    <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
      <h3 className="text-sm font-medium">Requests are not available yet.</h3>
      <p className="text-sm text-muted-foreground">
        Public accounts are not available yet. Novel and chapter requests will
        return in a later public-auth phase.
      </p>
      <button
        className="inline-flex h-9 items-center justify-center rounded-md border px-4 text-sm font-medium opacity-60"
        disabled
        type="button"
      >
        Submit Request Unavailable
      </button>
    </section>
  );
}
