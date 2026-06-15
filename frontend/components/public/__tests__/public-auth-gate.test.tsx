import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LoginView } from "@/components/public/login-view";

describe("public auth gate", () => {
  it("renders public login with Google OAuth and without credential fields", () => {
    const html = renderToStaticMarkup(<LoginView onClose={() => undefined} />);

    expect(html).toContain("Continue with Google");
    expect(html).toContain("Guest reading is still available.");
    expect(html).toContain("Library, progress, reviews, and requests are available after sign-in.");
    expect(html).not.toContain("type=\"email\"");
    expect(html).not.toContain("type=\"password\"");
    expect(html).not.toContain("token");
    expect(html).not.toContain("secret");
    expect(html).not.toContain("Password / Token");
    expect(html).not.toContain("/api/auth/login");
  });

  it("does not expose owner bootstrap login through the public API client", () => {
    const publicApi = readFileSync("lib/public-api.ts", "utf8");
    const publicHooks = readFileSync("hooks/public/index.ts", "utf8");

    expect(publicApi).not.toContain("/api/auth/login");
    expect(publicApi).not.toContain("authApi.login");
    expect(publicHooks).not.toContain("useLogin");
    expect(publicHooks).toContain("useAuthMe");
    expect(publicHooks).toContain("useLogout");
    expect(publicHooks).toContain("useStartGoogleOAuth");
  });
});
