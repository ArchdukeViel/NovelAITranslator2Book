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
    const { container } = render(
      <GlossaryFreshnessBadge freshness="unknown" />,
    );
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
      />,
    );
    expect(screen.getByText(/Stale/)).toBeInTheDocument();
    expect(screen.getByText(/v10.*v12/)).toBeInTheDocument();
  });
});

describe("RetranslateStaleDialog", () => {
  it("explains the canonical stale-retranslation policy", () => {
    render(
      <RetranslateStaleDialog
        open={true}
        title="Test Novel"
        pending={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/older glossary revision/)).toBeInTheDocument();
    expect(screen.getByText(/confidence policy/)).toBeInTheDocument();
  });

  it("calls onConfirm when confirm button clicked", async () => {
    const onConfirm = vi.fn();
    render(
      <RetranslateStaleDialog
        open={true}
        title="Test Novel"
        pending={false}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByText("Retranslate stale chapters"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onCancel when cancel button clicked", async () => {
    const onCancel = vi.fn();
    render(
      <RetranslateStaleDialog
        open={true}
        title="Test Novel"
        pending={false}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("disables retranslate button while pending", () => {
    render(
      <RetranslateStaleDialog
        open={true}
        title="Test Novel"
        pending={true}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/Scheduling/)).toBeDisabled();
  });
});
