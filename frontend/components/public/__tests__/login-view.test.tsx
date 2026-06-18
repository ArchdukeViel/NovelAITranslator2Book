import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps } from "react";

import { LoginView } from "@/components/public/login-view";

const mockPasswordLogin = vi.fn();
const mockRegister = vi.fn();
const mockStartGoogleOAuth = vi.fn();

vi.mock("@/hooks/public/use-auth", () => ({
  usePasswordLogin: () => ({
    mutateAsync: mockPasswordLogin,
    isPending: false,
  }),
  useRegister: () => ({
    mutateAsync: mockRegister,
    isPending: false,
  }),
  useStartGoogleOAuth: () => mockStartGoogleOAuth,
}));

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  vi.clearAllMocks();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status: 302, type: "opaqueredirect" })
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderLogin(
  onClose = vi.fn(),
  onSuccess = vi.fn(),
  props: Partial<ComponentProps<typeof LoginView>> = {}
) {
  return render(
    <QueryClientProvider client={queryClient}>
      <LoginView onClose={onClose} onSuccess={onSuccess} {...props} />
    </QueryClientProvider>
  );
}

describe("LoginView public auth options", () => {
  it("shows Google, email sign in, sign-up text link, and guest reading note", () => {
    renderLogin();

    expect(screen.getByText("Continue with Google")).toBeInTheDocument();
    expect(screen.getByText("Sign in with email")).toBeInTheDocument();
    expect(screen.getByText("No account yet?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create one" })).toBeInTheDocument();
    expect(
      screen.getByText("Guest reading is always available without sign-in.")
    ).toBeInTheDocument();
    expect(screen.queryByText("Email sign in")).not.toBeInTheDocument();
    expect(screen.queryByText("Email sign up")).not.toBeInTheDocument();
  });

  it("does not show public owner, admin, secret, or bootstrap wording", () => {
    renderLogin();
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
    expect(screen.queryByLabelText(/secret/i)).not.toBeInTheDocument();
  });
});

describe("LoginView email sign in", () => {
  it("validates email before submitting", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Email"), "not-an-email");
    await user.type(screen.getByLabelText("Password"), "long-enough-password");
    await user.click(screen.getByText("Sign in with email"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a valid email address."
    );
    expect(mockPasswordLogin).not.toHaveBeenCalled();
  });

  it("validates password before submitting", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Email"), "reader@example.com");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByText("Sign in with email"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Password must be at least 10 characters."
    );
    expect(mockPasswordLogin).not.toHaveBeenCalled();
  });

  it("submits password login and calls onSuccess", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    mockPasswordLogin.mockResolvedValueOnce({
      user_id: 7,
      email: "reader@example.com",
      role: "user",
      is_authenticated: true,
      is_owner: false,
    });

    renderLogin(vi.fn(), onSuccess);

    await user.type(screen.getByLabelText("Email"), " reader@example.com ");
    await user.type(screen.getByLabelText("Password"), "long-enough-password");
    await user.click(screen.getByText("Sign in with email"));

    await waitFor(() => {
      expect(mockPasswordLogin).toHaveBeenCalledWith({
        email: "reader@example.com",
        password: "long-enough-password",
      });
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it("shows a safe error on failed password login", async () => {
    const user = userEvent.setup();
    mockPasswordLogin.mockRejectedValueOnce(new Error("401 Unauthorized"));

    renderLogin();

    await user.type(screen.getByLabelText("Email"), "reader@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByText("Sign in with email"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password."
    );
  });
});

describe("LoginView email sign up", () => {
  it("shows confirm password field in sign-up mode", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: "Create one" }));

    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
    expect(screen.getByText("Create account")).toBeInTheDocument();
    expect(screen.getByText("Already have an account?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("opens directly in sign-up mode when requested", () => {
    renderLogin(vi.fn(), vi.fn(), { initialMode: "signup" });

    expect(screen.getByRole("heading", { name: "Create your Dokushodo account" })).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
    expect(screen.getByText("Create account")).toBeInTheDocument();
  });

  it("validates mismatched passwords before submitting", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: "Create one" }));
    await user.type(screen.getByLabelText("Email"), "reader@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough-password");
    await user.type(
      screen.getByLabelText("Confirm password"),
      "different-password"
    );
    await user.click(screen.getByText("Create account"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Passwords do not match."
    );
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("submits registration and calls onSuccess", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    mockRegister.mockResolvedValueOnce({
      user_id: 8,
      email: "reader@example.com",
      role: "user",
      is_authenticated: true,
      is_owner: false,
    });

    renderLogin(vi.fn(), onSuccess);

    await user.click(screen.getByRole("button", { name: "Create one" }));
    await user.type(screen.getByLabelText("Email"), "reader@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough-password");
    await user.type(
      screen.getByLabelText("Confirm password"),
      "long-enough-password"
    );
    await user.click(screen.getByText("Create account"));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith({
        email: "reader@example.com",
        password: "long-enough-password",
      });
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it("shows a safe error on failed registration", async () => {
    const user = userEvent.setup();
    mockRegister.mockRejectedValueOnce(new Error("409 Conflict"));

    renderLogin();

    await user.click(screen.getByRole("button", { name: "Create one" }));
    await user.type(screen.getByLabelText("Email"), "reader@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough-password");
    await user.type(
      screen.getByLabelText("Confirm password"),
      "long-enough-password"
    );
    await user.click(screen.getByText("Create account"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not create that account. Check your details and try again."
    );
  });
});

describe("LoginView Google OAuth", () => {
  it("shows unavailable message but keeps email/password usable when Google returns 503", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 503 }));

    renderLogin();

    await user.click(screen.getByText("Continue with Google"));

    expect(
      await screen.findByText(
        "Google sign-in is not available right now. You can still use email and password."
      )
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeEnabled();
    expect(screen.getByLabelText("Password")).toBeEnabled();
  });

  it("does not redirect when Google is unavailable", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 503 }));

    renderLogin();

    await user.click(screen.getByText("Continue with Google"));

    await waitFor(() => {
      expect(mockStartGoogleOAuth).not.toHaveBeenCalled();
    });
  });

  it("redirects to Google OAuth when available", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ status: 302, type: "opaqueredirect" })
    );

    renderLogin();

    await user.click(screen.getByText("Continue with Google"));

    await waitFor(() => {
      expect(mockStartGoogleOAuth).toHaveBeenCalled();
    });
  });
});
