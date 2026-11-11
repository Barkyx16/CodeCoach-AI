/**
 * The test renderer runs the app with the app's own query defaults (main.tsx), turning off only
 * retries. Otherwise every query would refetch on focus in tests and a page that should refresh on
 * return (docs/FRESHNESS.md) could stop doing so without a test noticing.
 */
import { makeQueryClient } from "@/app/queryClient";

import { renderApp } from "./render";

it("renders with the app's query defaults, only retries turned off", () => {
  const app = makeQueryClient().getDefaultOptions();
  const { queryClient } = renderApp("/login");
  const used = queryClient.getDefaultOptions();
  expect(used.queries).toEqual({ ...app.queries, retry: false });
  expect(used.queries?.refetchOnWindowFocus).toBe(false);
  expect(used.mutations).toEqual(app.mutations);
});
