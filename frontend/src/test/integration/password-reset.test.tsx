import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { renderApp } from "../render";
import { API, server } from "../server";

const TOKEN = "t".repeat(43);
const sent = { status: "accepted", message: "If an account exists for that email, we've sent a link to reset the password." };

function openResetLink(token: string | null) {
  window.history.replaceState(null, "", token ? `/reset-password#token=${token}` : "/reset-password");
  return renderApp("/reset-password");
}

describe("Password reset", () => {
  it("is reachable from the sign-in page and answers neutrally", async () => {
    let body: unknown = null;
    server.use(http.post(`${API}/api/v1/auth/password-reset`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(sent, { status: 202 });
    }));
    const { user, router } = renderApp("/login");
    await user.click(await screen.findByRole("link", { name: "Forgot your password?" }));
    expect(router.state.location.pathname).toBe("/forgot-password");
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByRole("status")).toHaveTextContent("If an account exists for that email");
    expect(body).toEqual({ email: "ada@example.com" });
  });

  it("sets the new password from the link, removes the token from the address bar, then asks to sign in", async () => {
    let body: unknown = null;
    server.use(http.post(`${API}/api/v1/auth/password-reset/confirm`, async ({ request }) => {
      body = await request.json();
      return new HttpResponse(null, { status: 204 });
    }));
    const { user, router } = openResetLink(TOKEN);
    await waitFor(() => expect(window.location.hash).toBe("")); // not left in history or screenshots
    await user.type(await screen.findByLabelText("New password"), "BatteryStaple99");
    await user.type(screen.getByLabelText("Confirm new password"), "BatteryStaple99");
    await user.click(screen.getByRole("button", { name: "Set new password" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(body).toEqual({ token: TOKEN, new_password: "BatteryStaple99" });
    expect(await screen.findByText("Your password was changed. Sign in with the new one.")).toBeInTheDocument();
  });

  it("won't submit until the two passwords match", async () => {
    const { user } = openResetLink(TOKEN);
    await user.type(await screen.findByLabelText("New password"), "BatteryStaple99");
    await user.type(screen.getByLabelText("Confirm new password"), "BatteryStaple98");
    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set new password" })).toBeDisabled();
  });

  it("explains an expired link and offers a new one", async () => {
    server.use(http.post(`${API}/api/v1/auth/password-reset/confirm`, () => HttpResponse.json(
      { error: { code: "invalid_reset_token", message: "This reset link is invalid or has expired.", request_id: "r", details: null } },
      { status: 400 })));
    const { user } = openResetLink(TOKEN);
    await user.type(await screen.findByLabelText("New password"), "BatteryStaple99");
    await user.type(screen.getByLabelText("Confirm new password"), "BatteryStaple99");
    await user.click(screen.getByRole("button", { name: "Set new password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(screen.getByRole("link", { name: "Request a new link" })).toHaveAttribute("href", "/forgot-password");
  });

  it("shows the password rules from the server next to the field", async () => {
    server.use(http.post(`${API}/api/v1/auth/password-reset/confirm`, () => HttpResponse.json({ error: {
      code: "validation_error", message: "Request validation failed", request_id: "r",
      details: [{ loc: ["body", "new_password"], msg: "Value error, password needs upper- and lower-case letters and at least one digit", type: "value_error" }],
    } }, { status: 422 })));
    const { user } = openResetLink(TOKEN);
    await user.type(await screen.findByLabelText("New password"), "alllowercase1");
    await user.type(screen.getByLabelText("Confirm new password"), "alllowercase1");
    await user.click(screen.getByRole("button", { name: "Set new password" }));
    expect(await screen.findByText("password needs upper- and lower-case letters and at least one digit")).toBeInTheDocument();
  });

  it("handles a link without a token", async () => {
    openResetLink(null);
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
  });
});
