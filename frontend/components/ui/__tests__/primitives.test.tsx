import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Panel, PanelHeader, PanelTitle, PanelBody } from "@/components/ui/panel";

describe("UI Primitives Component Contracts", () => {
  describe("Button", () => {
    it("renders default button and handles click events", async () => {
      const user = userEvent.setup({ delay: null });
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Click Me</Button>);

      const btn = screen.getByRole("button", { name: "Click Me" });
      expect(btn).toBeInTheDocument();
      await user.click(btn);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it("respects disabled attribute and does not trigger clicks", async () => {
      const user = userEvent.setup({ delay: null });
      const handleClick = vi.fn();
      render(<Button disabled onClick={handleClick}>Disabled Button</Button>);

      const btn = screen.getByRole("button", { name: "Disabled Button" });
      expect(btn).toBeDisabled();
      await user.click(btn);
      expect(handleClick).not.toHaveBeenCalled();
    });

    it("applies variant and size classes", () => {
      const { rerender } = render(<Button variant="destructive" size="sm">Delete</Button>);
      const btn = screen.getByRole("button", { name: "Delete" });
      expect(btn.className).toContain("bg-destructive");
      expect(btn.className).toContain("h-8");

      rerender(<Button variant="outline" size="icon" aria-label="Icon Action">X</Button>);
      const iconBtn = screen.getByRole("button", { name: "Icon Action" });
      expect(iconBtn.className).toContain("border-border");
      expect(iconBtn.className).toContain("w-9");
    });

    it("expands coarse-pointer hit area to 44px without changing visuals", () => {
      const { rerender } = render(<Button size="sm">Compact</Button>);
      const smBtn = screen.getByRole("button", { name: "Compact" });
      expect(smBtn.className).toContain("h-8");
      expect(smBtn.className).toContain("pointer-coarse:after:-inset-1.5");

      rerender(<Button size="icon" aria-label="Icon Action">X</Button>);
      const iconBtn = screen.getByRole("button", { name: "Icon Action" });
      expect(iconBtn.className).toContain("pointer-coarse:after:-inset-1");
    });
  });

  describe("Badge", () => {
    it("renders default neutral tone badge", () => {
      render(<Badge>Default Badge</Badge>);
      const badge = screen.getByText("Default Badge");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("border-border");
    });

    it("renders specified tone variants (green, amber, red, blue)", () => {
      const { rerender } = render(<Badge tone="green">Success</Badge>);
      expect(screen.getByText("Success").className).toContain("border-success");

      rerender(<Badge tone="amber">Pending</Badge>);
      expect(screen.getByText("Pending").className).toContain("border-warning");

      rerender(<Badge tone="red">Failed</Badge>);
      expect(screen.getByText("Failed").className).toContain("border-destructive");

      rerender(<Badge tone="blue">Info</Badge>);
      expect(screen.getByText("Info").className).toContain("border-info");
    });
  });

  describe("Input", () => {
    it("renders text input and accepts typing", async () => {
      const user = userEvent.setup({ delay: null });
      render(<Input placeholder="Search query" />);

      const input = screen.getByPlaceholderText("Search query");
      expect(input).toBeInTheDocument();
      await user.type(input, "Fantasy Novel");
      expect(input).toHaveValue("Fantasy Novel");
    });

    it("respects disabled state", () => {
      render(<Input disabled placeholder="Disabled input" />);
      const input = screen.getByPlaceholderText("Disabled input");
      expect(input).toBeDisabled();
    });

    it("links error text to the field", () => {
      render(<Input aria-label="Email" id="email" error="Enter an email like you@example.com" />);
      const input = screen.getByLabelText("Email");
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(input).toHaveAttribute("aria-describedby", "email-error");
      expect(input.className).toContain("text-base");
      expect(screen.getByText("Enter an email like you@example.com")).toBeInTheDocument();
    });

    it("links helper text to the field", () => {
      render(<Input aria-label="Name" id="name" helperText="Use your legal name." />);
      const input = screen.getByLabelText("Name");
      expect(input).not.toHaveAttribute("aria-invalid");
      expect(input).toHaveAttribute("aria-describedby", "name-helper");
      expect(screen.getByText("Use your legal name.")).toBeInTheDocument();
    });
  });

  describe("Textarea", () => {
    it("links error text to the field", () => {
      render(
        <Textarea aria-label="Message" id="message" error="Describe the issue in a few words." />
      );
      const field = screen.getByLabelText("Message");
      expect(field).toHaveAttribute("aria-invalid", "true");
      expect(field).toHaveAttribute("aria-describedby", "message-error");
      expect(screen.getByText("Describe the issue in a few words.")).toBeInTheDocument();
    });
  });

  describe("Panel", () => {
    it("renders structured panel with header, title, and body", () => {
      render(
        <Panel data-testid="panel-root">
          <PanelHeader>
            <PanelTitle>Panel Heading</PanelTitle>
          </PanelHeader>
          <PanelBody>Panel content goes here.</PanelBody>
        </Panel>
      );

      expect(screen.getByTestId("panel-root")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Panel Heading" })).toBeInTheDocument();
      expect(screen.getByText("Panel content goes here.")).toBeInTheDocument();
    });
  });
});
