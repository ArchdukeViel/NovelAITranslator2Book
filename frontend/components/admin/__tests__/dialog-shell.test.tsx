import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogShell } from "@/components/admin/dialog-shell";

describe("DialogShell architectural modal contract", () => {
  beforeEach(() => {
    document.body.style.overflow = "auto";
  });

  afterEach(() => {
    cleanup();
    document.body.style.overflow = "auto";
  });

  it("renders null when open is false", () => {
    render(
      <DialogShell open={false} title="Test Modal">
        <div>Modal Content</div>
      </DialogShell>
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("Modal Content")).not.toBeInTheDocument();
  });

  it("renders title, description, content, and accessible ARIA attributes when open", () => {
    render(
      <DialogShell
        open={true}
        title="Admin Confirm"
        description="Please confirm your action"
        footer={<button type="button">Confirm Action</button>}
      >
        <p>Sensitive operation details</p>
      </DialogShell>
    );

    const dialog = screen.getByRole("dialog", { name: "Admin Confirm" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Please confirm your action")).toBeInTheDocument();
    expect(screen.getByText("Sensitive operation details")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm Action" })).toBeInTheDocument();
  });

  it("dismisses on Escape key and stops event propagation", () => {
    const handleClose = vi.fn();
    render(
      <DialogShell open={true} title="Escape Test" onClose={handleClose}>
        <div>Body</div>
      </DialogShell>
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("dismisses when clicking the backdrop, but NOT when clicking dialog contents", async () => {
    const user = userEvent.setup({ delay: null });
    const handleClose = vi.fn();
    render(
      <DialogShell open={true} title="Backdrop Test" onClose={handleClose}>
        <button type="button">Inside Dialog</button>
      </DialogShell>
    );

    // Clicking content inside the modal does NOT close
    await user.click(screen.getByRole("button", { name: "Inside Dialog" }));
    expect(handleClose).not.toHaveBeenCalled();

    // Clicking backdrop closes the modal
    const backdrop = screen.getByRole("dialog").parentElement;
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("dismisses when clicking the close button", async () => {
    const user = userEvent.setup({ delay: null });
    const handleClose = vi.fn();
    render(
      <DialogShell open={true} title="Close Button Test" onClose={handleClose}>
        <div>Content</div>
      </DialogShell>
    );

    const closeBtn = screen.getByRole("button", { name: "Close dialog" });
    await user.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("locks document body scroll when open and restores it when unmounted", () => {
    const { unmount } = render(
      <DialogShell open={true} title="Scroll Lock Test">
        <div>Content</div>
      </DialogShell>
    );

    expect(document.body.style.overflow).toBe("hidden");

    unmount();
    expect(document.body.style.overflow).toBe("auto");
  });
});
