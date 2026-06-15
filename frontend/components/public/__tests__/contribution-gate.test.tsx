import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ContributionView } from "@/components/public/contribution-view";

describe("public contribution credential gate", () => {
  it("renders an unavailable state without credential controls", () => {
    const html = renderToStaticMarkup(<ContributionView />);

    expect(html).toContain("Contribution credentials are not available yet.");
    expect(html).toContain("This feature requires a future gated backend.");
    expect(html).toContain("Do not submit API keys here.");
    expect(html).not.toContain("type=\"password\"");
    expect(html).not.toContain("textarea");
    expect(html).not.toContain("Submit Credential");
    expect(html).not.toContain("Validate");
    expect(html).not.toContain("Remove");
  });

  it("does not expose active contribution API calls or hook exports", () => {
    const publicApi = readFileSync("lib/public-api.ts", "utf8");
    const publicHooks = readFileSync("hooks/public/index.ts", "utf8");

    expect(publicApi).not.toContain("/api/user/contributions");
    expect(publicApi).not.toContain("submitContribution");
    expect(publicApi).not.toContain("removeContribution");
    expect(publicHooks).not.toContain("useContribution");
  });
});
