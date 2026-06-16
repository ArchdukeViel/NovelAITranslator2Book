import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";

interface StaticPageProps {
  title: string;
  description: string;
  sections?: { title: string; body: string }[];
}

export function StaticPage({ description, sections = [], title }: StaticPageProps) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-3xl font-semibold tracking-normal">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      </header>
      <div className="space-y-4">
        {sections.map((section) => (
          <Panel key={section.title}>
            <PanelHeader>
              <PanelTitle>{section.title}</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <p className="text-sm text-muted-foreground">{section.body}</p>
            </PanelBody>
          </Panel>
        ))}
      </div>
    </main>
  );
}
