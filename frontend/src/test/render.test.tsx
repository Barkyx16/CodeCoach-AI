/**
 * The test renderer runs the app with the app's own query defaults (main.tsx), turning off only
 * retries. Otherwise every query would refetch on focus in tests and a page that should refresh on
 * return (docs/FRESHNESS.md) could stop doing so without a test noticing.
 */
import { screen, within } from "@testing-library/react";

import { makeQueryClient } from "@/app/queryClient";

import { renderApp } from "./render";

it("renders with the app's query defaults, only retries turned off", async () => {
  const app = makeQueryClient().getDefaultOptions();
  const { queryClient } = renderApp("/login");
  const used = queryClient.getDefaultOptions();
  expect(used.queries).toEqual({ ...app.queries, retry: false });
  expect(used.queries?.refetchOnWindowFocus).toBe(false);
  expect(used.mutations).toEqual(app.mutations);
  // The session check settles before the test ends (the header shows "Sign in" only once it has):
  // once seen in a full run, it finished after the test environment was gone and React's state
  // update had no window to read.
  expect(await within(screen.getByRole("banner")).findByRole("link", { name: "Sign in" }, { timeout: 3000 })).toBeInTheDocument();
});
