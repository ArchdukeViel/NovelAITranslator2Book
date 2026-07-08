import { readFileSync } from "node:fs";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SchedulerSummaryPanel } from "@/components/admin/scheduler-summary";
import type { SchedulerSummary } from "@/lib/api-types";

afterEach(cleanup);

describe("scheduler API methods", () => {
  it("exports schedulerHealth method", () => {
    const adminApi = readFileSync("lib/api.ts", "utf8");
    expect(adminApi).toContain("schedulerHealth");
    expect(adminApi).toContain("/admin/translation/scheduler-health");
  });

  it("exports SchedulerHealthResponse type", () => {
    const apiTypes = readFileSync("lib/api-types.ts", "utf8");
    expect(apiTypes).toContain("SchedulerHealthResponse");
    expect(apiTypes).toContain("SchedulerHealthModel");
  });

  it("exports SchedulerSummary type", () => {
    const apiTypes = readFileSync("lib/api-types.ts", "utf8");
    expect(apiTypes).toContain("SchedulerSummary");
  });
});

describe("SchedulerSummaryPanel", () => {
  it("renders nothing when summary is empty", () => {
    const { container } = render(
      <SchedulerSummaryPanel summary={{ chapters_with_decisions: 0 } as SchedulerSummary} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders chapter count and no issues when clean", () => {
    render(
      <SchedulerSummaryPanel
        summary={{
          chapters_with_decisions: 5,
          fallback_count: 0,
          no_capacity_count: 0,
          checkpoint_blocked_count: 0,
          memory_pressure_count: 0,
          peak_exact_memory_bytes: 0,
          skip_reason_counts: {},
          selected_model_counts: { "gemini:g-1": 5 },
          provider_counts: { gemini: 5 },
        }}
      />
    );
    expect(screen.getByText("Scheduler Summary")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("No scheduler issues")).toBeTruthy();
  });

  it("renders fallback warnings", () => {
    render(
      <SchedulerSummaryPanel
        summary={{
          chapters_with_decisions: 3,
          fallback_count: 2,
          no_capacity_count: 0,
          checkpoint_blocked_count: 0,
          memory_pressure_count: 1,
          peak_exact_memory_bytes: 0,
          skip_reason_counts: { preferred_model_cooling_down: 2 },
          selected_model_counts: { "gemini:g-1": 1, "gemini:g-2": 2 },
          provider_counts: { gemini: 3 },
        }}
      />
    );
    expect(screen.getByText("Scheduler Summary")).toBeTruthy();
    expect(screen.getByText("2 fallback(s)")).toBeTruthy();
    expect(screen.getByText("1 memory pressure")).toBeTruthy();
    expect(screen.getByText("2 fallback(s)")).toBeTruthy();
    expect(screen.getByText("Fallback")).toBeTruthy();
  });

  it("displays selected models breakdown", () => {
    render(
      <SchedulerSummaryPanel
        summary={{
          chapters_with_decisions: 2,
          fallback_count: 0,
          no_capacity_count: 0,
          checkpoint_blocked_count: 0,
          memory_pressure_count: 0,
          peak_exact_memory_bytes: 0,
          skip_reason_counts: {},
          selected_model_counts: { "gemini:g-1": 1, "openai:gpt-4": 1 },
          provider_counts: { gemini: 1, openai: 1 },
        }}
      />
    );
    expect(screen.getByText("Selected Models")).toBeTruthy();
    expect(screen.getByText("gemini:g-1: 1")).toBeTruthy();
    expect(screen.getByText("openai:gpt-4: 1")).toBeTruthy();
  });

  it("renders provider breakdown", () => {
    render(
      <SchedulerSummaryPanel
        summary={{
          chapters_with_decisions: 2,
          fallback_count: 1,
          no_capacity_count: 0,
          checkpoint_blocked_count: 0,
          memory_pressure_count: 0,
          peak_exact_memory_bytes: 0,
          skip_reason_counts: {},
          selected_model_counts: { "gemini:g-1": 1, "openai:gpt-4": 1 },
          provider_counts: { gemini: 1, openai: 1 },
        }}
      />
    );
    expect(screen.getByText("By Provider")).toBeTruthy();
    expect(screen.getByText("gemini: 1")).toBeTruthy();
    expect(screen.getByText("openai: 1")).toBeTruthy();
  });

  it("displays peak memory when present", () => {
    render(
      <SchedulerSummaryPanel
        summary={{
          chapters_with_decisions: 1,
          fallback_count: 0,
          no_capacity_count: 0,
          checkpoint_blocked_count: 0,
          memory_pressure_count: 1,
          peak_exact_memory_bytes: 52428800,
          skip_reason_counts: {},
          selected_model_counts: { "gemini:g-1": 1 },
          provider_counts: { gemini: 1 },
        }}
      />
    );
    expect(screen.getByText(/50\.0 MB/)).toBeTruthy();
    expect(screen.getByText(/1 pressure/)).toBeTruthy();
  });
});
