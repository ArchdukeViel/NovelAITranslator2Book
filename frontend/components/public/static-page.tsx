interface StaticPageProps {
  title: string;
  description: string;
  sections?: { title: string; body: string }[];
}

export function StaticPage({
  description,
  sections = [],
  title,
}: StaticPageProps) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
      <header>
        <p className="font-metadata text-xs uppercase tracking-[0.24em] text-accent">
          Dokushodo
        </p>
        <h1 className="mt-4 font-literary text-4xl font-medium leading-tight tracking-normal text-foreground md:text-5xl">
          {title}
        </h1>
        <p className="mt-6 text-base leading-8 text-muted-foreground">
          {description}
        </p>
      </header>

      {sections.length > 0 && (
        <ol className="mt-16 space-y-10">
          {sections.map((section, index) => (
            <section
              key={section.title}
              className="grid gap-3 border-t border-border/50 pt-8 sm:grid-cols-[5rem_minmax(0,1fr)] sm:gap-8"
            >
              <p className="font-metadata text-xs uppercase tracking-[0.18em] text-muted-foreground">
                {String(index + 1).padStart(2, "0")}
              </p>
              <div>
                <h2 className="font-literary text-2xl font-medium tracking-normal">
                  {section.title}
                </h2>
                <p className="mt-4 text-sm leading-7 text-muted-foreground">
                  {section.body}
                </p>
              </div>
            </section>
          ))}
        </ol>
      )}
    </main>
  );
}
