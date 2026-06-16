import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16 text-center">
      <h1 className="text-3xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        The page you are looking for does not exist.
      </p>
      <Link className="mt-6 inline-flex text-sm font-medium underline" href="/home">
        Return home
      </Link>
    </main>
  );
}
