import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { renderApp } from "../render";
import { API, server } from "../server";

it("dismisses navigation with Escape and returns focus to its toggle", async () => {
  const { user } = renderApp("/", { signedIn: true });
  const toggle = screen.getByRole("button", { name: "Open navigation" });
  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  await user.keyboard("{Escape}");
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(toggle).toHaveFocus();
});

it("reports a failed guest session instead of leaving an unhandled rejection", async () => {
  server.use(http.post(`${API}/api/v1/auth/guest`, () => HttpResponse.error()));
  const { user, router } = renderApp("/login");
  await user.click(screen.getByRole("button", { name: "Continue as guest" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach the CodeCoach server");
  expect(router.state.location.pathname).toBe("/login");
  expect(screen.getByRole("button", { name: "Continue as guest" })).toBeEnabled();
});
