import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { NovelRail } from "@/components/public/novel-rail";

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

function DummyCard({ n }: { n: number }) {
  return (
    <div
      role="listitem"
      className="h-40 w-40 flex-shrink-0 snap-start bg-gray-200"
    >
      Card {n}
    </div>
  );
}

describe("NovelRail", () => {
  it("renders region with aria label and heading", () => {
    render(
      <NovelRail title="Trending" ariaLabel="Trending novels">
        <DummyCard n={1} />
      </NovelRail>
    );
    expect(screen.getByRole("region")).toHaveAttribute(
      "aria-label",
      "Trending novels"
    );
    expect(screen.getByRole("heading", { name: "Trending" })).toBeInTheDocument();
  });

  it("renders See all link when seeAllHref provided", () => {
    render(
      <NovelRail title="New" ariaLabel="New novels" seeAllHref="/novels">
        <DummyCard n={1} />
      </NovelRail>
    );
    const link = screen.getByRole("link", { name: /see all/i });
    expect(link).toHaveAttribute("href", "/novels");
  });

  it("does not render See all link without seeAllHref", () => {
    render(
      <NovelRail title="New" ariaLabel="New novels">
        <DummyCard n={1} />
      </NovelRail>
    );
    expect(screen.queryByRole("link", { name: /see all/i })).not.toBeInTheDocument();
  });

  it("renders children as list items", () => {
    render(
      <NovelRail title="X" ariaLabel="X">
        <DummyCard n={1} />
        <DummyCard n={2} />
      </NovelRail>
    );
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Card 1");
    expect(items[1]).toHaveTextContent("Card 2");
  });

  it("has a focusable scroller with role list", () => {
    render(
      <NovelRail title="X" ariaLabel="X">
        <DummyCard n={1} />
      </NovelRail>
    );
    const scroller = screen.getByRole("list");
    expect(scroller).toHaveAttribute("tabindex", "0");
  });

  it("scrolls one card with arrow keys", () => {
    render(<NovelRail title="X" ariaLabel="X"><DummyCard n={1} /></NovelRail>);
    const scroller = screen.getByRole("list");
    const card = screen.getByRole("listitem");
    Object.defineProperty(card, "offsetWidth", { value: 160 });
    const scrollBy = vi.fn();
    Object.defineProperty(scroller, "scrollBy", { value: scrollBy });

    fireEvent.keyDown(scroller, { key: "ArrowRight" });

    expect(scrollBy).toHaveBeenCalledWith({ left: 176, behavior: "smooth" });
  });

  it("uses instant scrolling for reduced motion", () => {
    vi.mocked(window.matchMedia).mockReturnValue({
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });
    render(<NovelRail title="X" ariaLabel="X"><DummyCard n={1} /></NovelRail>);
    const scroller = screen.getByRole("list");
    const card = screen.getByRole("listitem");
    Object.defineProperty(card, "offsetWidth", { value: 160 });
    const scrollBy = vi.fn();
    Object.defineProperty(scroller, "scrollBy", { value: scrollBy });

    fireEvent.keyDown(scroller, { key: "ArrowLeft" });

    expect(scrollBy).toHaveBeenCalledWith({ left: -176, behavior: "auto" });
  });
});
