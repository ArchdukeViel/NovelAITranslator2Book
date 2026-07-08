import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GlossaryFreshnessBadge } from "@/components/admin/glossary-freshness-badge";
import { RetranslateStaleDialog } from "@/components/admin/library/retranslate-stale-dialog";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("GlossaryFreshnessBadge", () => {
  it("renders nothing when freshness is unknown", () => {
    const { container } = render(<GlossaryFreshnessBadge freshness="unknown" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when freshness is null", () => {
    const { container } = render(<GlossaryFreshnessBadge freshness={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders green badge for fresh", () => {
    render(<GlossaryFreshnessBadge freshness="fresh" />);
    expect(screen.getByText("Fresh")).toBeInTheDocument();
  });

  it("renders amber badge for stale with reason", () => {
    render(
      <GlossaryFreshnessBadge
        freshness="stale"
        staleReason="revision_mismatch"
        currentRevision={12}
        versionRevision={10}
      />
    );
    expect(screen.getByText(/Stale/)).toBeInTheDocument();
    expect(screen.getByText(/v10.*v12/)).toBeInTheDocument();
  });

  it("renders neutral badge for legacy_unknown", () => {
    render(<GlossaryFreshnessBadge freshness="legacy_unknown" />);
    expect(screen.getByText("Legacy")).toBeInTheDocument();
  });
});

describe("RetranslateStaleDialog", () => {
  it("shows no-stale message when counts are zero", () => {
    render(
      <RetranslateStaleDialog
        open={true}
        novelId="n1"
        title="Test Novel"
        staleCount={0}
        legacyCount={0}
        pending={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByText(/No stale.*found/)).toBeInTheDocument();
  });

  it("shows stale count when there are stale chapters", () => {
    render(
      <RetranslateStaleDialog
        open={true}
        novelId="n1"
        title="Test Novel"
        staleCount={5}
        legacyCount={0}
        pending={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText(/Retranslate 5 chapters/)).toBeInTheDocument();
  });

  it("shows legacy option when legacy count > 0", () => {
    render(
      <RetranslateStaleDialog
        open={true}
        novelId="n1"
        title="Test Novel"
        staleCount={3}
        legacyCount={2}
        pending={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByText(/legacy/i)).toBeInTheDocument();
  });

  it("calls onConfirm with options when confirm button clicked", async () => {
    const onConfirm = vi.fn();
    render(
      <RetranslateStaleDialog
        open={true}
        novelId="n1"
        title="Test Novel"
        staleCount={3}
        legacyCount={0}
        pending={false}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />
    );
    await userEvent.click(screen.getByText(/Retranslate 3 chapters/));
    expect(onConfirm).toHaveBeenCalledWith({ includeLegacy: false, activate: false });
  });

  it("calls onCancel when cancel button clicked", async () => {
    const onCancel = vi.fn();
    render(
      <RetranslateStaleDialog
        open={true}
        novelId="n1"
        title="Test Novel"
        staleCount={3}
        legacyCount={0}
        pending={false}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />
    );
    await userEvent.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("disables retranslate button while pending", () => {
    render(
      <RetranslateStaleDialog
        open={true}
        novelId="n1"
        title="Test Novel"
        staleCount={3}
        legacyCount={0}
        pending={true}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByText(/Scheduling/)).toBeDisabled();
  });
});
