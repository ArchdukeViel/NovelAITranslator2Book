import { readFileSync } from "node:fs";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { GlossaryQAPanel } from "@/components/admin/glossary-qa-panel";
import type { GlossaryQAResult } from "@/lib/api-types";

afterEach(cleanup);

describe("glossary QA API methods", () => {
  it("exports lintTranslatedChapter method", () => {
    const api = readFileSync("lib/api.ts", "utf8");
    expect(api).toContain("lintTranslatedChapter");
    expect(api).toContain("/translated/lint");
  });

  it("exports approveTranslationChange method", () => {
    const api = readFileSync("lib/api.ts", "utf8");
    expect(api).toContain("approveTranslationChange");
    expect(api).toContain("/approve-translation-change");
  });

  it("exports GlossaryQAResult type", () => {
    const types = readFileSync("lib/api-types.ts", "utf8");
    expect(types).toContain("GlossaryQAResult");
    expect(types).toContain("GlossaryQAIssue");
    expect(types).toContain("GlossaryOverride");
  });
});

describe("GlossaryQAPanel", () => {
  const baseResult: GlossaryQAResult = {
    status: "passed",
    novel_id: "n",
    platform_novel_id: 1,
    chapter_id: "c",
    glossary_revision: 5,
    checked_terms: 3,
    issue_count: 0,
    has_errors: false,
    has_warnings: false,
    source_context: "provided",
    notes: [],
    issues: [],
    cap_reached: false,
    cap_limit: null,
  };

  it("renders passed status", () => {
    render(<GlossaryQAPanel result={baseResult} />);
    expect(screen.getByText("Passed")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
  });

  it("renders blocked status with override button", () => {
    const blocked: GlossaryQAResult = {
      ...baseResult,
      status: "blocked",
      has_errors: true,
      issue_count: 1,
      issues: [
        {
          issue_id: "gqa_1_missing_required_term_魔王",
          entry_id: 1,
          canonical_term: "魔王",
          approved_translation: "Demon King",
          matched_variant: null,
          severity: "error",
          code: "missing_required_term",
          owner_locked: true,
          context_hint: "Add approved translation: Demon King.",
        },
      ],
    };
    render(<GlossaryQAPanel result={blocked} canOverride />);
    expect(screen.getByText("Blocked")).toBeTruthy();
    expect(screen.getByText("魔王")).toBeTruthy();
    expect(screen.getByText("Demon King")).toBeTruthy();
    expect(screen.getByText("locked")).toBeTruthy();
  });

  it("renders warning status", () => {
    const warning: GlossaryQAResult = {
      ...baseResult,
      status: "warning",
      has_warnings: true,
      issue_count: 1,
      issues: [
        {
          issue_id: "gqa_1_missing_approved_translation_魔王",
          entry_id: 1,
          canonical_term: "魔王",
          approved_translation: "Demon King",
          matched_variant: null,
          severity: "warning",
          code: "missing_approved_translation",
          owner_locked: false,
          context_hint: "Add approved translation: Demon King.",
        },
      ],
    };
    render(<GlossaryQAPanel result={warning} />);
    expect(screen.getByText("Warning")).toBeTruthy();
  });

  it("renders advisory status", () => {
    const advisory: GlossaryQAResult = {
      ...baseResult,
      status: "advisory",
      notes: ["Glossary not available for this novel."],
    };
    render(<GlossaryQAPanel result={advisory} />);
    expect(screen.getByText("Advisory")).toBeTruthy();
    expect(screen.getByText("Glossary not available for this novel.")).toBeTruthy();
  });

  it("renders overridden status", () => {
    const overridden: GlossaryQAResult = {
      ...baseResult,
      status: "overridden",
      has_errors: true,
      issue_count: 1,
    };
    render(<GlossaryQAPanel result={overridden} />);
    expect(screen.getByText("Overridden")).toBeTruthy();
  });

  it("shows approve-change button when canApprove", () => {
    const blocked: GlossaryQAResult = {
      ...baseResult,
      status: "blocked",
      has_errors: true,
      issue_count: 1,
      issues: [
        {
          issue_id: "gqa_1_non_approved_translation_魔王",
          entry_id: 1,
          canonical_term: "魔王",
          approved_translation: "Demon King",
          matched_variant: "Dark Lord",
          severity: "warning",
          code: "non_approved_translation",
          owner_locked: false,
          context_hint: "Replace 'Dark Lord' with approved translation.",
        },
      ],
    };
    render(<GlossaryQAPanel result={blocked} canApprove />);
    expect(screen.getByText("Approve change")).toBeTruthy();
  });

  it("shows cap_reached warning", () => {
    const capped: GlossaryQAResult = {
      ...baseResult,
      cap_reached: true,
      cap_limit: 50,
    };
    render(<GlossaryQAPanel result={capped} />);
    expect(screen.getByText(/Term cap reached/)).toBeTruthy();
  });
});
