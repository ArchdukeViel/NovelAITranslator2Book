import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import type { Metadata } from "next";

// Mock all page modules to avoid evaluating React components in jsdom.
// We only need the `metadata` named export from each module.
vi.mock("@/app/(public)/about/page", () => ({ metadata: { title: "About", description: "Dokushodo is a public reader for translated web novels with owner-controlled ingestion and translation workflows." } }));
vi.mock("@/app/(public)/privacy/page", () => ({ metadata: { title: "Privacy", description: "Privacy policy for Dokushodo." } }));
vi.mock("@/app/(public)/terms/page", () => ({ metadata: { title: "Terms", description: "Terms of service for Dokushodo." } }));
vi.mock("@/app/(public)/dmca/page", () => ({ metadata: { title: "DMCA", description: "DMCA policy for Dokushodo.", robots: { index: false, follow: false } } }));
vi.mock("@/app/(public)/contact/page", () => ({ metadata: { title: "Contact", description: "Contact information for Dokushodo.", robots: { index: false, follow: false } } }));
vi.mock("@/app/(public)/cookie-policy/page", () => ({ metadata: { title: "Cookie Policy", description: "Cookie policy for Dokushodo." } }));
vi.mock("@/app/(public)/ranking/page", () => ({ metadata: { title: "Ranking", description: "Ranking page for Dokushodo." } }));
vi.mock("@/app/(public)/auth/callback/page", () => ({ metadata: { title: "Signing In", description: "OAuth callback page.", robots: { index: false, follow: false } } }));
vi.mock("@/app/(public)/error/page", () => ({ metadata: { title: "Error", description: "Error page.", robots: { index: false, follow: false } } }));
vi.mock("@/app/(public)/maintenance/page", () => ({ metadata: { title: "Maintenance", description: "Maintenance page.", robots: { index: false, follow: false } } }));
vi.mock("@/app/not-found", () => ({ metadata: { title: "Not Found", description: "Page not found.", robots: { index: false, follow: false } } }));
vi.mock("@/app/(public)/page", () => ({ metadata: { title: "Home", description: "Home page." } }));
vi.mock("@/app/layout", () => ({ metadata: { title: { template: "%s | Novel AI", default: "Novel AI" }, description: "Novel AI is a web-based Japanese novel crawling, translation, editing, and reader platform.", openGraph: { siteName: "Novel AI" }, twitter: { card: "summary" } } }));
vi.mock("@/app/(public)/layout", () => ({ metadata: { title: { default: "Dokushodo", template: "%s | Dokushodo" }, description: "Dokushodo public reader.", openGraph: { siteName: "Dokushodo" }, robots: { index: true, follow: true } } }));
vi.mock("@/app/(public)/account/layout", () => ({ metadata: { title: "Account", description: "Account layout.", robots: { index: false, follow: false } } }));
vi.mock("@/app/(public)/browse-novels/page", () => ({
  generateMetadata: async ({ searchParams }: { searchParams: Promise<Record<string, string>> }) => {
    const params = await searchParams;
    const q = (params.q ?? "").trim();
    if (q) {
      return { title: `Search results for "${q}"`, description: `Search results for ${q} on Dokushodo.` };
    }
    return { title: "Browse Novels", description: "Browse novels on Dokushodo." };
  },
}));

// ---------------------------------------------------------------------------
// Server-component pages that export static metadata
// ---------------------------------------------------------------------------

import { metadata as aboutMeta } from "@/app/(public)/about/page";
import { metadata as privacyMeta } from "@/app/(public)/privacy/page";
import { metadata as termsMeta } from "@/app/(public)/terms/page";
import { metadata as dmcaMeta } from "@/app/(public)/dmca/page";
import { metadata as contactMeta } from "@/app/(public)/contact/page";
import { metadata as cookiePolicyMeta } from "@/app/(public)/cookie-policy/page";
import { metadata as rankingMeta } from "@/app/(public)/ranking/page";
import { metadata as authCallbackMeta } from "@/app/(public)/auth/callback/page";
import { metadata as errorMeta } from "@/app/(public)/error/page";
import { metadata as maintenanceMeta } from "@/app/(public)/maintenance/page";
import { metadata as notFoundMeta } from "@/app/not-found";
import { metadata as redirectIndexMeta } from "@/app/(public)/page";

// ---------------------------------------------------------------------------
// Layout metadata
// ---------------------------------------------------------------------------

import { metadata as rootLayoutMeta } from "@/app/layout";
import { metadata as publicLayoutMeta } from "@/app/(public)/layout";
import { metadata as accountLayoutMeta } from "@/app/(public)/account/layout";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getRobots(m: Metadata): { index?: boolean | null; follow?: boolean | null } | null {
  if (!m.robots) return null;
  if (typeof m.robots === "string") return null;
  // m.robots is Robots object
  return m.robots as { index?: boolean | null; follow?: boolean | null };
}

// ---------------------------------------------------------------------------
// generateMetadata
// ---------------------------------------------------------------------------

import { generateMetadata as browseGenerateMeta } from "@/app/(public)/browse-novels/page";

describe("metadata — site-wide", () => {
  it("root layout has site-wide description and OpenGraph", () => {
    const m = rootLayoutMeta;
    expect(typeof m.description).toBe("string");
    expect(m.description?.toString().length).toBeGreaterThan(10);
    expect(m.openGraph).toBeDefined();
    expect(m.openGraph?.siteName).toBe("Novel AI");
    expect(m.twitter).toBeDefined();
    if (typeof m.twitter === "object" && m.twitter && "card" in m.twitter) {
      expect((m.twitter as { card?: string }).card).toBe("summary");
    }
  });

  it("root layout uses title template for child overrides", () => {
    const m = rootLayoutMeta as Metadata & { title: { template: string } };
    expect(typeof m.title).toBe("object");
    if (m.title && typeof m.title === "object" && "template" in m.title) {
      expect(m.title.template).toContain("Novel AI");
    }
  });
});

describe("metadata — public layout", () => {
  it("public layout has default title and template", () => {
    const m = publicLayoutMeta as Metadata & { title: { default: string; template: string } };
    expect(typeof m.title).toBe("object");
    if (m.title && typeof m.title === "object" && "default" in m.title && "template" in m.title) {
      expect(m.title.default).toBe("Dokushodo");
      expect(m.title.template).toBe("%s | Dokushodo");
    }
  });

  it("public layout has OpenGraph site name", () => {
    expect(publicLayoutMeta.openGraph?.siteName).toBe("Dokushodo");
  });

  it("public layout defaults to index,follow", () => {
    const r = getRobots(publicLayoutMeta);
    expect(r?.index).toBe(true);
    expect(r?.follow).toBe(true);
  });
});

describe("metadata — page titles use correct patterns", () => {
  interface TitleMetadata {
    title?: string | { default?: string; template?: string; absolute?: string };
  }

  const cases: { label: string; meta: Metadata; expectedTitle?: string }[] = [
    { label: "about", meta: aboutMeta, expectedTitle: "About" },
    { label: "privacy", meta: privacyMeta, expectedTitle: "Privacy" },
    { label: "terms", meta: termsMeta, expectedTitle: "Terms" },
    { label: "dmca", meta: dmcaMeta, expectedTitle: "DMCA" },
    { label: "contact", meta: contactMeta, expectedTitle: "Contact" },
    { label: "cookie-policy", meta: cookiePolicyMeta, expectedTitle: "Cookie Policy" },
    { label: "ranking", meta: rankingMeta, expectedTitle: "Ranking" },
    { label: "auth/callback", meta: authCallbackMeta, expectedTitle: "Signing In" },
    { label: "error", meta: errorMeta, expectedTitle: "Error" },
    { label: "maintenance", meta: maintenanceMeta, expectedTitle: "Maintenance" },
  ];

  for (const c of cases) {
    it(`${c.label} has correct title`, () => {
      const m = c.meta as TitleMetadata;
      expect(m.title).toBe(c.expectedTitle);
    });
  }

  it("root redirect has an appropriate title", () => {
    const redirectIndex = redirectIndexMeta as TitleMetadata;
    expect(redirectIndex.title).toBe("Home");
  });

  it("page descriptions are non-empty and specific", () => {
    const checks = [
      { label: "about", meta: aboutMeta },
      { label: "privacy", meta: privacyMeta },
      { label: "terms", meta: termsMeta },
      { label: "dmca", meta: dmcaMeta },
      { label: "contact", meta: contactMeta },
      { label: "cookie-policy", meta: cookiePolicyMeta },
      { label: "ranking", meta: rankingMeta },
      { label: "auth/callback", meta: authCallbackMeta },
      { label: "maintenance", meta: maintenanceMeta },
    ];
    for (const c of checks) {
      expect(typeof c.meta.description).toBe("string");
      expect((c.meta.description as string).length).toBeGreaterThan(5);
    }
  });
});

describe("metadata — robots / noindex", () => {
  it("auth callback is noindex", () => {
    const r = getRobots(authCallbackMeta);
    expect(r?.index).toBe(false);
    expect(r?.follow).toBe(false);
  });

  it("contact page is noindex (placeholder contact route)", () => {
    const r = getRobots(contactMeta);
    expect(r?.index).toBe(false);
    expect(r?.follow).toBe(false);
  });

  it("dmca page is noindex (pending policy)", () => {
    const r = getRobots(dmcaMeta);
    expect(r?.index).toBe(false);
    expect(r?.follow).toBe(false);
  });

  it("error page is noindex", () => {
    const r = getRobots(errorMeta);
    expect(r?.index).toBe(false);
    expect(r?.follow).toBe(false);
  });

  it("maintenance page is noindex", () => {
    const r = getRobots(maintenanceMeta);
    expect(r?.index).toBe(false);
    expect(r?.follow).toBe(false);
  });

  it("not-found is noindex at root and (public) route", () => {
    const r = getRobots(notFoundMeta);
    expect(r?.index).toBe(false);
    expect(r?.follow).toBe(false);
  });

  it("account layout is noindex (scoped to /account)", () => {
    const r = getRobots(accountLayoutMeta);
    expect(r?.index).toBe(false);
    expect(r?.follow).toBe(false);
  });

});

describe("metadata — browse-novels", () => {
  it("generateMetadata returns browse title when no query", async () => {
    const result = await browseGenerateMeta({ searchParams: Promise.resolve({}) });
    expect(result.title).toBe("Browse Novels");
    expect(result.description).toContain("Dokushodo");
  });

  it("generateMetadata returns search title when query present", async () => {
    const result = await browseGenerateMeta({
      searchParams: Promise.resolve({ q: "isekai" }),
    });
    expect(result.title).toBe('Search results for "isekai"');
    expect(result.description).toContain("isekai");
  });

  it("generateMetadata trims whitespace from query", async () => {
    const result = await browseGenerateMeta({
      searchParams: Promise.resolve({ q: "  tensei  " }),
    });
    expect(result.title).toBe('Search results for "tensei"');
  });

  it("generateMetadata returns browse title for empty query", async () => {
    const result = await browseGenerateMeta({
      searchParams: Promise.resolve({ q: "" }),
    });
    expect(result.title).toBe("Browse Novels");
  });

  it("generateMetadata returns browse title for whitespace-only query", async () => {
    const result = await browseGenerateMeta({
      searchParams: Promise.resolve({ q: "   " }),
    });
    expect(result.title).toBe("Browse Novels");
  });
});

describe("metadata — safety and honesty", () => {
  it("no metadata mentions fake ranking availability", () => {
    const metas = [
      rankingMeta,
      aboutMeta,
    ];
    for (const m of metas) {
      const desc = (m.description as string)?.toLowerCase() || "";
      expect(desc).not.toContain("daily ranking");
      expect(desc).not.toContain("weekly ranking");
      expect(desc).not.toContain("monthly ranking");
    }
  });

  it("no metadata mentions fake update frequency", () => {
    const metas = [
      aboutMeta,
      publicLayoutMeta,
    ];
    for (const m of metas) {
      const desc = (m.description as string)?.toLowerCase() || "";
      // Should not claim regular updates or daily content
      expect(desc).not.toContain("daily updates");
      expect(desc).not.toContain("daily chapter");
    }
  });

  it("no metadata contains old placeholder language", () => {
    const metas = [
      aboutMeta,
      privacyMeta,
      termsMeta,
      dmcaMeta,
      contactMeta,
      cookiePolicyMeta,
      rankingMeta,
      authCallbackMeta,
      errorMeta,
      maintenanceMeta,
    ];
    for (const m of metas) {
      const title = (m.title as string)?.toLowerCase() || "";
      const desc = (m.description as string)?.toLowerCase() || "";
      expect(title).not.toContain("preview");
      expect(title).not.toContain("under construction");
      expect(desc).not.toContain("preview");
      expect(desc).not.toContain("under construction");
      expect(desc).not.toContain("data is not live yet");
    }
  });

  it("contact page copy does not sound like scaffold placeholder", () => {
    const sourceText = readFileSync(
      "app/(public)/contact/page.tsx",
      "utf8"
    );
    expect(sourceText).not.toContain("confirms where contact information will live");
    expect(sourceText).not.toContain("channels are pending");
    expect(sourceText).toContain("single owner/admin");
    expect(sourceText).toContain("takedown request");
  });

  it("dmca page copy does not sound like scaffold placeholder", () => {
    const sourceText = readFileSync(
      "app/(public)/dmca/page.tsx",
      "utf8"
    );
    expect(sourceText).not.toContain("pending final policy copy");
    expect(sourceText).toContain("owner/admin reviews");
  });

  it("error page does not describe itself as documentation", () => {
    const sourceText = readFileSync(
      "app/(public)/error/page.tsx",
      "utf8"
    );
    expect(sourceText).not.toContain("documents the generic error surface");
    expect(sourceText).not.toContain("app-level error boundary");
    expect(sourceText).toContain("Something went wrong");
    expect(sourceText).toContain("Browse catalog");
  });

  it("not-found page has secondary CTA and icon", () => {
    const sourceText = readFileSync(
      "app/not-found.tsx",
      "utf8"
    );
    expect(sourceText).toContain("Browse catalog");
    expect(sourceText).toContain("BookOpen");
    expect(sourceText).not.toContain("only /home link without icon");
  });

  it("settings page does not contain backend jargon", () => {
    const sourceText = readFileSync(
      "app/(public)/account/settings/page.tsx",
      "utf8"
    );
    expect(sourceText.toLowerCase()).not.toContain("backend");
    expect(sourceText).not.toContain("Google OAuth");
  });

  it("request-novel page does not contain backend or API jargon", () => {
    const sourceText = readFileSync(
      "app/(public)/request-novel/page.tsx",
      "utf8"
    );
    expect(sourceText.toLowerCase()).not.toContain("backend");
    expect(sourceText).not.toContain("behavior phase");
  });

  it("contribute page does not contain backend jargon", () => {
    const sourceText = readFileSync(
      "app/(public)/contribute/page.tsx",
      "utf8"
    );
    expect(sourceText.toLowerCase()).not.toContain("backend");
    expect(sourceText).not.toContain("lifecycle");
    expect(sourceText).not.toContain("gated");
  });
});
