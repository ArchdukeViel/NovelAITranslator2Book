export default function HistoryPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-4 text-2xl font-semibold">Reading History</h1>
      <section className="rounded-md border border-border bg-muted/40 p-4">
        <p className="text-sm font-medium">Public accounts are not available yet.</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Reading history will be available after the public-auth phase. Guest
          reading is still available.
        </p>
      </section>
    </div>
  );
}
