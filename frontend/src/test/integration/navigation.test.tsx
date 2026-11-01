import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { renderApp } from "../render";
import { API, server } from "../server";

it("moves focus to the content and updates the title after route navigation", async () => {
  const { user } = renderApp("/", { signedIn: true });
  await user.click(screen.getByRole("link", { name: "Analytics" }));
  expect(await screen.findByRole("heading", { name: "Analytics" })).toBeInTheDocument();
  expect(document.getElementById("main")).toHaveFocus();
  expect(document.title).toBe("Analytics | CodeCoach AI");
});

it("supports arrow, Home and End navigation through the product tour", async () => {
  const { user } = renderApp("/");
  const code = screen.getByRole("tab", { name: "Write your solution" });
  await user.click(code);
  await user.keyboard("{ArrowRight}");
  expect(screen.getByRole("tab", { name: "Find your next step" })).toHaveFocus();
  expect(screen.getByRole("tabpanel", { name: "Find your next step" })).toHaveTextContent("The coaching ladder");
  await user.keyboard("{Home}");
  expect(screen.getByRole("tab", { name: "Understand the problem" })).toHaveFocus();
  await user.keyboard("{ArrowLeft}");
  expect(screen.getByRole("tab", { name: "Find your next step" })).toHaveAttribute("aria-selected", "true");
  await user.keyboard("{Home}{End}");
  expect(screen.getByRole("tab", { name: "Find your next step" })).toHaveFocus();
});

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
