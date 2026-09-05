import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Button } from "@/components/ui/button";

afterEach(cleanup);

describe("Button default type (REQ-11, AC-11)", () => {
  it('renders with type="button" when no type prop is given', () => {
    render(<Button>Cancel</Button>);
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveAttribute("type", "button");
  });

  it("allows explicit submit and reset overrides", () => {
    render(
      <>
        <Button type="submit">Save</Button>
        <Button type="reset">Reset</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "submit");
    expect(screen.getByRole("button", { name: "Reset" })).toHaveAttribute("type", "reset");
  });
});
