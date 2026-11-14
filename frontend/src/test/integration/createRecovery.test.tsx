/**
 * A guest start or registration whose reply was lost (Volume 8, prompt 6; RECOVERY.md).
 * The page first asks for this browser's create anchor (an HttpOnly cookie the server checks), then
 * sends the create. When the reply is lost it uses the session only if that cookie arrived and is
 * the account being made; otherwise it resends once, and the server (by the anchor) returns what
 * the first request made. If that reply is lost too, the page says the outcome is unknown.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { chooseCareer } from "../careerPicker";
import { tokenResponse, user as ada } from "../fixtures";
import { renderApp } from "../render";
import { API, cookieJar, server } from "../server";

const guest = { ...ada, id: "guest-1", email: null, is_guest: true, display_name: "Guest" };

/** Records the order of auth calls; `replies` decides each create's answer in turn. */
function createServer(path: "guest" | "register", replies: (Response | "lost-after-commit" | "lost")[], made = path === "guest" ? guest : ada) {
  const calls: string[] = [];
  let n = 0;
  server.use(
    http.post(`${API}/api/v1/auth/create-anchor`, () => { calls.push("anchor"); return new HttpResponse(null, { status: 204 }); }),
    http.post(`${API}/api/v1/auth/${path}`, () => {
      calls.push(path);
      const reply = replies[n++] ?? replies.at(-1)!;
      if (reply === "lost-after-commit") { cookieJar.hasSession = true; return HttpResponse.error(); } // the cookie arrived, the body didn't
      if (reply === "lost") return HttpResponse.error();
      cookieJar.hasSession = true;
      return reply;
    }),
    http.post(`${API}/api/v1/auth/refresh`, () => {
      calls.push("refresh");
      return cookieJar.hasSession
        ? HttpResponse.json(tokenResponse({ user: made }))
        : HttpResponse.json({ error: { code: "invalid_refresh", message: "Please sign in again.", request_id: "r", details: null } }, { status: 401 });
    }),
  );
  return calls;
}

/** The calls from pressing the button on (the page's own session check on load comes before). */
const afterAnchor = (calls: string[]) => calls.slice(calls.indexOf("anchor"));
const resumed = (u: typeof ada) => HttpResponse.json(tokenResponse({ user: u }), { status: 200, headers: { "X-Account-Resumed": u.is_guest ? "guest" : "register" } });

async function fillRegister(user: ReturnType<typeof renderApp>["user"]) {
  await user.type(await screen.findByLabelText("Email"), ada.email!);
  await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
  await chooseCareer(user, screen.getByLabelText("Job you're preparing for"), "registered-nurse");
}
const createButton = () => within(screen.getByRole("form", { name: "Create your account" })).getByRole("button", { name: "Create account" });

it("a guest start whose reply was lost is sent again once and resumes the guest the server made", async () => {
  const calls = createServer("guest", ["lost", resumed(guest)]);
  const { user, router } = renderApp("/login");
  await user.click(await screen.findByRole("button", { name: "Continue as guest" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/welcome"));
  // The anchor before the create; no session cookie came back, so one quiet resend.
  expect(afterAnchor(calls)).toEqual(["anchor", "guest", "refresh", "guest"]);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("when the lost reply's session cookie did arrive, that session is used and nothing is sent again", async () => {
  const calls = createServer("guest", ["lost-after-commit"]);
  const { user, router } = renderApp("/login");
  await user.click(await screen.findByRole("button", { name: "Continue as guest" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/welcome"));
  expect(calls.filter((c) => c === "guest")).toHaveLength(1);
  expect(await screen.findByText("Guest")).toBeInTheDocument();
});

it("a session that isn't the account being made is not taken for it", async () => {
  // This browser still holds another account's cookie, and the guest start's reply is lost: the
  // page doesn't treat Ada's session as the guest; it resends, and the guest it gets replaces it.
  const calls = createServer("guest", ["lost", resumed(guest)], ada);
  const { user, router } = renderApp("/login");
  const button = await screen.findByRole("button", { name: "Continue as guest" }); // signed out on load
  cookieJar.hasSession = true;
  await user.click(button);
  await waitFor(() => expect(router.state.location.pathname).toBe("/welcome"));
  expect(calls.filter((c) => c === "guest")).toHaveLength(2);
  expect(await screen.findByText("Guest")).toBeInTheDocument();
});

it("a registration whose reply was lost is resumed by the resend, then goes on to verification", async () => {
  const calls = createServer("register", ["lost", resumed(ada)]);
  const { user, router } = renderApp("/register");
  await fillRegister(user);
  await user.click(createButton());
  await waitFor(() => expect(router.state.location.pathname).toBe("/verify-email"));
  expect(afterAnchor(calls)).toEqual(["anchor", "register", "refresh", "register"]);
});

it("if the resend's reply is lost too, the page says the account may exist and how to finish, without guessing", async () => {
  const calls = createServer("register", ["lost", "lost", resumed(ada)]);
  const { user, router } = renderApp("/register");
  await fillRegister(user);
  await user.click(createButton());
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("We couldn't confirm your account was created. It may have been.");
  expect(alert).toHaveTextContent(/press the same button again/);
  expect(alert).not.toHaveTextContent(/already exists|email is taken/i); // nothing said about the address
  expect(router.state.location.pathname).toBe("/register");
  expect(calls.filter((c) => c === "register")).toHaveLength(2); // one quiet retry, never a loop
  // Pressing it again later: the same browser's anchor finds the account.
  await user.click(createButton());
  await waitFor(() => expect(router.state.location.pathname).toBe("/verify-email"));
  expect(calls.filter((c) => c === "register")).toHaveLength(3);
});

it("an answer that isn't a lost reply is shown as before, without a resend", async () => {
  const calls = createServer("register", [HttpResponse.json({ error: { code: "email_taken", message: "An account with this email already exists", request_id: "r", details: null } }, { status: 409 })]);
  const { user } = renderApp("/register");
  await fillRegister(user);
  await user.click(createButton());
  expect(await screen.findByText("An account with this email already exists")).toBeInTheDocument();
  expect(afterAnchor(calls)).toEqual(["anchor", "register"]);
});

it("without an anchor (the call failed) the create still goes ahead, as before this change", async () => {
  const calls = createServer("guest", [HttpResponse.json(tokenResponse({ user: guest }), { status: 201 })]);
  server.use(http.post(`${API}/api/v1/auth/create-anchor`, () => { calls.push("anchor-failed"); return HttpResponse.error(); }));
  const { user, router } = renderApp("/login");
  await user.click(await screen.findByRole("button", { name: "Continue as guest" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/welcome"));
  expect(calls.slice(calls.indexOf("anchor-failed"))).toEqual(["anchor-failed", "guest"]);
});
