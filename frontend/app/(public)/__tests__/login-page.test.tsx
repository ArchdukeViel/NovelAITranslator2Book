import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import LoginPage from "@/app/(public)/login/page";

const navMocks = vi.hoisted(() => ({
  query: "",
  push: vi.fn(),
  replace: vi.fn(),
}));

const authMocks = vi.hoisted(() => ({
  passwordLogin: vi.fn(),
  register: vi.fn(),
  startGoogleOAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navMocks.push,
    replace: navMocks.replace,
  }),
  useSearchParams: () => new URLSearchParams(navMocks.query),
}));

vi.mock("@/hooks/public/use-auth", () => ({
  usePasswordLogin: () => ({
    mutateAsync: authMocks.passwordLogin,
    isPending: false,
  }),
  useRegister: () => ({
    mutateAsync: authMocks.register,
    isPending: false,
  }),
  useStartGoogleOAuth: () => authMocks.startGoogleOAuth,
}));

function renderLoginPage(query = "") {
  navMocks.query = query;
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <LoginPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  navMocks.query = "";
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status: 302, type: "opaqueredirect" })
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("public login route modes", () => {
  it("/login defaults to sign-in mode", () => {
    renderLoginPage();

    expect(screen.getByRole("heading", { name: "Sign in to Dokushodo" })).toBeInTheDocument();
    expect(screen.getByText("Sign in with email")).toBeInTheDocument();
    expect(screen.queryByLabelText("Confirm password")).not.toBeInTheDocument();
  });

  it("/login?mode=signin shows sign-in mode", () => {
    renderLoginPage("mode=signin");

    expect(screen.getByRole("heading", { name: "Sign in to Dokushodo" })).toBeInTheDocument();
    expect(screen.getByText("Sign in with email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create one" })).toBeInTheDocument();
  });

  it("/login?mode=signup shows sign-up mode", () => {
    renderLoginPage("mode=signup");

    expect(screen.getByRole("heading", { name: "Create your Dokushodo account" })).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
    expect(screen.getByText("Create account")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("unknown mode safely defaults to sign-in mode", () => {
    renderLoginPage("mode=forgot-password");

    expect(screen.getByRole("heading", { name: "Sign in to Dokushodo" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Confirm password")).not.toBeInTheDocument();
  });

  it("mode switch links update the login query", async () => {
    const user = userEvent.setup();
    renderLoginPage("mode=signin");

    await user.click(screen.getByRole("button", { name: "Create one" }));

    await waitFor(() => {
      expect(navMocks.replace).toHaveBeenCalledWith("/login?mode=signup", { scroll: false });
    });
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
  });

  it("does not expose forbidden public auth options or owner language", () => {
    renderLoginPage("mode=signup");
    const bodyText = document.body.textContent?.toLowerCase() ?? "";

    expect(bodyText).not.toContain("owner");
    expect(bodyText).not.toContain("admin");
    expect(bodyText).not.toContain("secret");
    expect(bodyText).not.toContain("bootstrap");
    expect(bodyText).not.toContain("github");
    expect(bodyText).not.toContain("discord");
    expect(bodyText).not.toContain("magic-link");
    expect(bodyText).not.toContain("password reset");
    expect(bodyText).not.toContain("email verification");
  });
});
