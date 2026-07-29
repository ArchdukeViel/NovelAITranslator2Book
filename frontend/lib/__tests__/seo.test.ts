import { describe, it, expect, beforeEach } from "vitest";
import {
  getSiteUrl,
  buildCanonicalUrl,
  buildNovelPageTitle,
  buildChapterPageTitle,
  buildDescription,
  escapeHtml,
  escapeJson,
  isNovelIndexable,
  isChapterIndexable,
  robotsDirective,
  buildNovelJsonLd,
  buildChapterJsonLd,
  serializeJsonLd,
} from "@/lib/seo";

// ---------------------------------------------------------------------------
// Setup: predictable env for each test
// ---------------------------------------------------------------------------

const ORIGINAL_SITE_URL = process.env.NEXT_PUBLIC_SITE_URL;

beforeEach(() => {
  process.env.NEXT_PUBLIC_SITE_URL = "https://dokushodo.example.com";
});

// ---------------------------------------------------------------------------
// getSiteUrl / buildCanonicalUrl
// ---------------------------------------------------------------------------

describe("getSiteUrl", () => {
  it("returns configured SITE_URL", () => {
    expect(getSiteUrl()).toBe("https://dokushodo.example.com");
  });

  it("falls back to localhost when unset", () => {
    delete process.env.NEXT_PUBLIC_SITE_URL;
    expect(getSiteUrl()).toBe("http://localhost:3000");
  });
});

describe("buildCanonicalUrl", () => {
  it("builds absolute URL from pathname", () => {
    expect(buildCanonicalUrl("/novels/my-novel")).toBe(
      "https://dokushodo.example.com/novels/my-novel",
    );
  });

  it("strips trailing slash on base but not path", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "https://example.com/";
    expect(buildCanonicalUrl("/novels/test")).toBe(
      "https://example.com/novels/test",
    );
  });

  it("passes through caller-encoded pathname unchanged", () => {
    expect(buildCanonicalUrl("/novels/my%20novel")).toBe(
      "https://dokushodo.example.com/novels/my%20novel",
    );
  });

  it("ensures leading slash", () => {
    expect(buildCanonicalUrl("novels/no-slash")).toBe(
      "https://dokushodo.example.com/novels/no-slash",
    );
  });
});

// ---------------------------------------------------------------------------
// buildNovelPageTitle
// ---------------------------------------------------------------------------

describe("buildNovelPageTitle", () => {
  it("formats with novel title", () => {
    expect(buildNovelPageTitle("My Novel")).toBe(
      "My Novel | Dokushodo",
    );
  });

  it("trims whitespace", () => {
    expect(buildNovelPageTitle("  Spaced Title  ")).toBe(
      "Spaced Title | Dokushodo",
    );
  });

  it("uses fallback when title is null", () => {
    expect(buildNovelPageTitle(null)).toBe(
      "Untitled Novel | Dokushodo",
    );
  });

  it("uses fallback when title is undefined", () => {
    expect(buildNovelPageTitle(undefined)).toBe(
      "Untitled Novel | Dokushodo",
    );
  });

  it("uses fallback when title is empty string", () => {
    expect(buildNovelPageTitle("")).toBe(
      "Untitled Novel | Dokushodo",
    );
  });
});

// ---------------------------------------------------------------------------
// buildChapterPageTitle
// ---------------------------------------------------------------------------

describe("buildChapterPageTitle", () => {
  it("formats with chapter and novel title", () => {
    expect(
      buildChapterPageTitle("Chapter 1", "My Novel"),
    ).toBe("Chapter 1 - My Novel | Dokushodo");
  });

  it("trims both titles", () => {
    expect(
      buildChapterPageTitle("  Ch 1  ", "  Novel  "),
    ).toBe("Ch 1 - Novel | Dokushodo");
  });

  it("uses fallback when chapter title is null", () => {
    expect(
      buildChapterPageTitle(null, "My Novel"),
    ).toBe("Untitled Chapter - My Novel | Dokushodo");
  });

  it("uses fallback when novel title is null", () => {
    expect(
      buildChapterPageTitle("Chapter 1", null),
    ).toBe("Chapter 1 - Untitled Novel | Dokushodo");
  });

  it("uses fallback when both are null", () => {
    expect(
      buildChapterPageTitle(null, null),
    ).toBe("Untitled Chapter - Untitled Novel | Dokushodo");
  });
});

// ---------------------------------------------------------------------------
// buildDescription
// ---------------------------------------------------------------------------

describe("buildDescription", () => {
  it("returns the text when within limit", () => {
    const short = "A short synopsis.";
    expect(buildDescription(short)).toBe(short);
  });

  it("strips HTML tags", () => {
    expect(
      buildDescription("<p>Story about <b>dragons</b>.</p>"),
    ).toBe("Story about dragons.");
  });

  it("removes unterminated tag delimiters", () => {
    expect(buildDescription("Safe <script alert(1)")).toBe(
      "Safe script alert(1)",
    );
  });

  it("removes nested tags that re-form after one pass", () => {
    expect(
      buildDescription("<scrip<script>removed</script>t>alert(1)</script>"),
    ).toBe("alert(1)");
  });

  it("collapses whitespace", () => {
    expect(
      buildDescription("Line1\n\n  Line2\nLine3"),
    ).toBe("Line1 Line2 Line3");
  });

  it("truncates to 160 chars with ellipsis", () => {
    const long = "A".repeat(200);
    const result = buildDescription(long);
    expect(result).toHaveLength(160);
    expect(result.endsWith("\u2026")).toBe(true);
  });

  it("returns fallback for null", () => {
    expect(buildDescription(null)).toBe(
      "Read translated Japanese web novels on Dokushodo.",
    );
  });

  it("returns fallback for undefined", () => {
    expect(buildDescription(undefined)).toBe(
      "Read translated Japanese web novels on Dokushodo.",
    );
  });

  it("returns fallback for empty string", () => {
    expect(buildDescription("")).toBe(
      "Read translated Japanese web novels on Dokushodo.",
    );
  });

  it("returns fallback for whitespace-only", () => {
    expect(buildDescription("   ")).toBe(
      "Read translated Japanese web novels on Dokushodo.",
    );
  });
});

// ---------------------------------------------------------------------------
// escapeHtml
// ---------------------------------------------------------------------------

describe("escapeHtml", () => {
  it("escapes & < > \" '", () => {
    expect(
      escapeHtml('<script>alert("xss") & "quoted"</script>'),
    ).toBe(
      "&lt;script&gt;alert(&quot;xss&quot;) &amp; &quot;quoted&quot;&lt;/script&gt;",
    );
  });

  it("passes safe text through", () => {
    expect(escapeHtml("Hello world")).toBe("Hello world");
  });
});

// ---------------------------------------------------------------------------
// escapeJson
// ---------------------------------------------------------------------------

describe("escapeJson", () => {
  it("escapes backslash, quote, newline, carriage return, tab", () => {
    expect(
      escapeJson('Say "hello"\nline2\tend'),
    ).toBe('Say \\"hello\\"\\nline2\\tend');
  });

  it("passes safe text through", () => {
    expect(escapeJson("plain text")).toBe("plain text");
  });
});

// ---------------------------------------------------------------------------
// isNovelIndexable
// ---------------------------------------------------------------------------

describe("isNovelIndexable", () => {
  it("allows published novels", () => {
    expect(isNovelIndexable("published")).toBe(true);
  });

  it("blocks unpublished novels", () => {
    expect(isNovelIndexable("unpublished")).toBe(false);
  });

  it("blocks unknown status", () => {
    expect(isNovelIndexable("unknown")).toBe(false);
  });

  it("blocks private novels", () => {
    expect(isNovelIndexable("private")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isChapterIndexable
// ---------------------------------------------------------------------------

describe("isChapterIndexable", () => {
  it("allows published translated chapters", () => {
    expect(isChapterIndexable("published", true)).toBe(true);
  });

  it("blocks untranslated chapters", () => {
    expect(isChapterIndexable("published", false)).toBe(false);
  });

  it("blocks unpublished novel chapters even if translated", () => {
    expect(isChapterIndexable("unpublished", true)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// robotsDirective
// ---------------------------------------------------------------------------

describe("robotsDirective", () => {
  it("returns index,follow when indexable", () => {
    expect(robotsDirective(true)).toBe("index,follow");
  });

  it("returns noindex,nofollow when not indexable", () => {
    expect(robotsDirective(false)).toBe("noindex,nofollow");
  });
});

// ---------------------------------------------------------------------------
// buildNovelJsonLd
// ---------------------------------------------------------------------------

describe("buildNovelJsonLd", () => {
  it("builds Book JSON-LD with all fields", () => {
    const result = buildNovelJsonLd(
      "My Novel",
      "A great story.",
      "https://example.com/novels/my-novel",
      "Author Name",
    );
    expect(result).toEqual({
      "@context": "https://schema.org",
      "@type": "Book",
      name: "My Novel",
      description: "A great story.",
      url: "https://example.com/novels/my-novel",
      author: "Author Name",
    });
  });

  it("omits optional fields when absent", () => {
    const result = buildNovelJsonLd("Minimal Novel");
    expect(result).toEqual({
      "@context": "https://schema.org",
      "@type": "Book",
      name: "Minimal Novel",
    });
    expect(result.description).toBeUndefined();
    expect(result.url).toBeUndefined();
    expect(result.author).toBeUndefined();
  });

  it("uses fallback title for empty name", () => {
    const result = buildNovelJsonLd("");
    expect(result.name).toBe("Untitled Novel");
  });

  it("omits null description", () => {
    const result = buildNovelJsonLd("Test", null);
    expect(result.description).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// buildChapterJsonLd
// ---------------------------------------------------------------------------

describe("buildChapterJsonLd", () => {
  it("builds Chapter JSON-LD with all fields", () => {
    const result = buildChapterJsonLd(
      "Chapter 1",
      "My Novel",
      "The opening chapter.",
      "https://example.com/novels/my-novel/chapter/1",
    );
    expect(result).toEqual({
      "@context": "https://schema.org",
      "@type": "Chapter",
      name: "Chapter 1",
      description: "The opening chapter.",
      url: "https://example.com/novels/my-novel/chapter/1",
      isPartOf: {
        "@type": "Book",
        name: "My Novel",
      },
    });
  });

  it("omits optional fields when absent", () => {
    const result = buildChapterJsonLd("Ch 1", "Novel");
    expect(result.description).toBeUndefined();
    expect(result.url).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// serializeJsonLd
// ---------------------------------------------------------------------------

describe("serializeJsonLd", () => {
  it("wraps JSON in script tag", () => {
    const data = { "@context": "https://schema.org", "@type": "Book", name: "Test" };
    const result = serializeJsonLd(data);
    expect(result).toBe(
      `<script type="application/ld+json">{"@context":"https://schema.org","@type":"Book","name":"Test"}</script>`,
    );
  });

  it("properly escapes JSON strings in output", () => {
    const data = { name: 'He said "hello"' };
    const result = serializeJsonLd(data);
    expect(result).toContain('\\"hello\\"');
  });
});
