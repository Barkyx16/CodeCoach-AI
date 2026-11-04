import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { hint } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// When Claude can't give a usable answer, the built-in coach answers, and the page says so plainly
// (Volume 4 brief 06): an answer is never taken for Claude's when it isn't.

describe("Coaching fallback", () => {
  it("a hint from the built-in coach after Claude failed says so", async () => {
    server.use(http.post(`${API}/api/v1/ai/hint`, () => HttpResponse.json({ ...hint(1), provider: "offline (fallback)" })));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Get a hint" }));
    expect(await screen.findByText("Hint text for level 1")).toBeInTheDocument();
    const notice = screen.getByText(/Claude couldn.t give a usable answer this time/);
    expect(notice).toHaveAttribute("role", "status");
  });

  it("a hint Claude gave carries no such notice", async () => {
    server.use(http.post(`${API}/api/v1/ai/hint`, () => HttpResponse.json({ ...hint(1), provider: "anthropic" })));
    const { user } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Get a hint" }));
    expect(await screen.findByText("Hint text for level 1")).toBeInTheDocument();
    expect(screen.queryByText(/Claude couldn't give a usable answer/)).not.toBeInTheDocument();
  });
});
