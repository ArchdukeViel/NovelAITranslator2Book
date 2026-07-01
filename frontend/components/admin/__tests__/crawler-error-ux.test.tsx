import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddNovelForm } from "@/components/admin/crawler/add-novel-form";
import { AddNovelRunDialog } from "@/components/admin/crawler/add-novel-run-dialog";
import { ImportNowPanel } from "@/components/admin/crawler/import-now-panel";
import { PreliminaryCrawlResultModal } from "@/components/admin/crawler/preliminary-crawl-result-modal";
import { ReadinessBadge } from "@/components/admin/glossary/readiness-badge";
import { TranslationModal } from "@/components/admin/library/translation-modal";
import CrawlerPage from "@/app/(admin)/admin/crawler/page";
import { ApiError } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

const owner = {
  user_id: 1,
  email: "admin@example.com",
  role: "owner",
  is_authenticated: true,
  is_owner: true,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("crawler error UX", () => {
  describe("AddNovelForm", () => {
    it("displays error banner when preliminary crawl fails", () => {
      render(
        <AddNovelForm
          value="https://example.com/novel"
          detectedSource="web"
          canSubmit={true}
          pending={false}
          error={new Error("Network error")}
          onChange={() => {}}
          onSubmit={() => {}}
        />
      );

      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  describe("ImportNowPanel", () => {
    it("displays error banner when import fails", () => {
      render(
        <ImportNowPanel
          novelId="test-novel"
          adapterKey="web"
          source="https://example.com"
          maxUnits="10"
          adapters={["web"]}
          pending={false}
          error={new Error("Adapter not found")}
          onNovelIdChange={() => {}}
          onAdapterKeyChange={() => {}}
          onSourceChange={() => {}}
          onMaxUnitsChange={() => {}}
          onSubmit={() => {}}
        />
      );

      expect(screen.getByText(/adapter not found/i)).toBeInTheDocument();
    });
  });

  describe("PreliminaryCrawlResultModal", () => {
    const mockResult = {
      novel_id: "test-novel",
      title: "Test Novel",
      translated_title: "Test Novel",
      author: "Test Author",
      translated_author: "Test Author",
      synopsis: "Test synopsis",
      translated_synopsis: "Test synopsis",
      chapters: 5,
      source_key: "web",
      chapter_list: [
        { chapter_id: "1", title: "Chapter 1", chapter_number: 1 },
        { chapter_id: "2", title: "Chapter 2", chapter_number: 2 },
      ],
    };

    it("disables confirm button and shows helper copy when queue/run error exists", () => {
      render(
        <PreliminaryCrawlResultModal
          open={true}
          result={mockResult}
          selectedChapterIds={new Set(["1"])}
          selectedCount={1}
          allSelected={false}
          pending={false}
          error={new Error("Queue failed")}
          onToggleAll={() => {}}
          onToggleChapter={() => {}}
          onConfirm={() => {}}
          onCancel={() => {}}
        />
      );

      expect(
        screen.getByText(/an error occurred while queueing the chapters\. please cancel and restart the process to try again\./i)
      ).toBeInTheDocument();

      const confirmButton = screen.getByRole("button", { name: /add novel/i });
      expect(confirmButton).toBeDisabled();
    });

    it("enables confirm button when no error exists", () => {
      render(
        <PreliminaryCrawlResultModal
          open={true}
          result={mockResult}
          selectedChapterIds={new Set(["1"])}
          selectedCount={1}
          allSelected={false}
          pending={false}
          error={null}
          onToggleAll={() => {}}
          onToggleChapter={() => {}}
          onConfirm={() => {}}
          onCancel={() => {}}
        />
      );

      expect(
        screen.queryByText(/an error occurred while queueing the chapters/i)
      ).not.toBeInTheDocument();

      const confirmButton = screen.getByRole("button", { name: /add novel/i });
      expect(confirmButton).not.toBeDisabled();
    });

    it("shows glossary-first onboarding actions when bootstrap candidates exist", async () => {
      const user = userEvent.setup();
      const onApproveGlossary = vi.fn();
      const onSkipGlossary = vi.fn();

      render(
        <PreliminaryCrawlResultModal
          open={true}
          result={{ ...mockResult, bootstrap_candidate_count: 3 }}
          selectedChapterIds={new Set(["1"])}
          selectedCount={1}
          allSelected={false}
          pending={false}
          error={null}
          onToggleAll={() => {}}
          onToggleChapter={() => {}}
          onConfirm={() => {}}
          onCancel={() => {}}
          onApproveGlossary={onApproveGlossary}
          onSkipGlossary={onSkipGlossary}
        />
      );

      expect(screen.getByText(/glossary readiness/i)).toBeInTheDocument();
      expect(screen.getByText(/3 candidate term\(s\) detected/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /review glossary before translating/i })).toHaveAttribute(
        "href",
        "/admin/novels/test-novel/glossary"
      );

      await user.click(screen.getByRole("button", { name: /approve all and set ready/i }));
      await user.click(screen.getByRole("button", { name: /skip glossary for now/i }));

      expect(onApproveGlossary).toHaveBeenCalledTimes(1);
      expect(onSkipGlossary).toHaveBeenCalledTimes(1);
    });

    it("shows only skip button and no-candidates notice when zero bootstrap candidates", () => {
      render(
        <PreliminaryCrawlResultModal
          open={true}
          result={{ ...mockResult, bootstrap_candidate_count: 0 }}
          selectedChapterIds={new Set(["1"])}
          selectedCount={1}
          allSelected={false}
          pending={false}
          error={null}
          onToggleAll={() => {}}
          onToggleChapter={() => {}}
          onConfirm={() => {}}
          onCancel={() => {}}
        />
      );

      expect(screen.getByText(/glossary readiness/i)).toBeInTheDocument();
      expect(screen.getByText(/no candidate terms were detected during onboarding/i)).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /review glossary before translating/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /approve all and set ready/i })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /skip glossary for now/i })).toBeInTheDocument();
    });
  });

  describe("ReadinessBadge", () => {
    it("links pending novels to the novel-scoped glossary route", () => {
      render(
        <ReadinessBadge
          novelId="novel/with space"
          glossaryStatus="glossary_pending"
          glossaryRevision={2}
          glossaryPendingCount={4}
        />
      );

      const link = screen.getByRole("link", { name: /glossary pending/i });
      expect(link).toHaveAttribute("href", "/admin/novels/novel%2Fwith%20space/glossary");
      expect(link).toHaveTextContent("4 to review");
    });

    it("shows ready and skipped states without review links", () => {
      const { rerender } = render(
        <ReadinessBadge
          novelId="novel-ready"
          glossaryStatus="glossary_ready"
          glossaryRevision={5}
          glossaryPendingCount={0}
        />
      );

      expect(screen.getByText("Glossary r5")).toBeInTheDocument();
      expect(screen.queryByRole("link")).not.toBeInTheDocument();

      rerender(
        <ReadinessBadge
          novelId="novel-skipped"
          glossaryStatus="glossary_skipped"
          glossaryRevision={0}
          glossaryPendingCount={0}
        />
      );

      expect(screen.getByText("Glossary skipped")).toBeInTheDocument();
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });
  });

  describe("TranslationModal", () => {
    it("shows glossary readiness in the novel detail modal", () => {
      render(
        <TranslationModal
          open={true}
          novelId="novel/with space"
          title="Translated Title"
          author="Translated Author"
          synopsis="Translated synopsis"
          glossaryStatus="glossary_pending"
          glossaryRevision={7}
          glossaryPendingCount={3}
          language="English"
          languages={["English", "Indonesian"]}
          chapters={[]}
          selectedChapterIds={new Set()}
          selectedCount={0}
          allSelected={false}
          loading={false}
          loadError={null}
          runError={null}
          pending={false}
          onLanguageChange={() => {}}
          onToggleAll={() => {}}
          onToggleChapter={() => {}}
          onCancel={() => {}}
          onConfirm={() => {}}
        />
      );

      const link = screen.getByRole("link", { name: /glossary pending/i });
      expect(link).toHaveAttribute("href", "/admin/novels/novel%2Fwith%20space/glossary");
      expect(screen.getByText(/3 to review/i)).toBeInTheDocument();
    });
  });

  describe("AddNovelRunDialog", () => {
    it("shows 'Detecting chapters' label during preliminary pending", () => {
      render(
        <AddNovelRunDialog
          preliminaryPending={true}
          runState="idle"
          crawlProgress={50}
          runProgress={0}
          detectedSource="web"
          runLabel="test"
          resultTitle="Test"
          addedChapterCount={0}
          selectedChapterCount={0}
          onExitSuccess={() => {}}
        />
      );
      expect(screen.getByText(/detecting chapters/i)).toBeInTheDocument();
    });

    it("shows 'Scraping selected chapters' label during running state", () => {
      render(
        <AddNovelRunDialog
          preliminaryPending={false}
          runState="running"
          crawlProgress={0}
          runProgress={50}
          detectedSource="web"
          runLabel="test"
          resultTitle="Test"
          addedChapterCount={1}
          selectedChapterCount={1}
          onExitSuccess={() => {}}
        />
      );
      expect(screen.getByText(/scraping selected chapters/i)).toBeInTheDocument();
    });
  });

  describe("CrawlerPage error dialog", () => {
    it("displays friendly summary, collapsible details, and activity log button for SCRAPE_ACTIVITY_STILL_RUNNING", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
        const url = String(input);
        if (url.includes("/api/auth/me")) {
          return Promise.resolve(jsonResponse(owner));
        }
        if (url.includes("/api/activity")) return Promise.resolve(jsonResponse({ activity: [] }));
        if (url.includes("/api/requests")) return Promise.resolve(jsonResponse({ requests: [] }));
        if (url.includes("/api/worker")) return Promise.resolve(jsonResponse({ running: false }));
        if (url.includes("/api/sources/health")) return Promise.resolve(jsonResponse({ sources: [] }));
        if (url.includes("/admin/input-adapters")) return Promise.resolve(jsonResponse(["web"]));

        if (url.includes("/preliminary-crawl") && init?.method === "POST") {
          return Promise.reject(new ApiError({
            status: 504,
            code: "SCRAPE_ACTIVITY_STILL_RUNNING",
            message: "The scrape request timed out while the activity was still running.",
            explanation: "The backend may still be scraping chapters. Check Activity Log for this novel; the activity can finish after the browser request times out.",
            details: { activity: { id: "act-123" } }
          }));
        }
        return Promise.resolve(jsonResponse({}));
      });

      renderWithQuery(<CrawlerPage />);

      const input = screen.getByPlaceholderText(/novel link or novel id/i);
      await userEvent.type(input, "https://example.com/novel");

      const addButton = screen.getByRole("button", { name: /add novel/i });
      await userEvent.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeInTheDocument();
      });

      // Test A: Friendly summary (check that the dialog contains the explanation)
      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveTextContent(/the backend may still be scraping chapters/i);

      // Test B: Collapsible technical details
      expect(screen.getByText(/show technical details/i)).toBeInTheDocument();

      // Test C: Activity Log guidance (it's a button that navigates, not a link)
      const activityLogButton = screen.getByRole("button", { name: /view activity log/i });
      expect(activityLogButton).toBeInTheDocument();
    });
  });
});
