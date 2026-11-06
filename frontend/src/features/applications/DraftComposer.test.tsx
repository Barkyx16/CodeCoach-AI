import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ApplicationEvent } from "@/api/types";

import { formatDay } from "./dates";
import { DraftComposer } from "./DraftComposer";

const ev = (over: Partial<ApplicationEvent> = {}): ApplicationEvent => ({
  id: "e1", kind: "interview", title: "Panel interview", on_date: "2026-12-15", local_time: "10:00", timezone: "Europe/London",
  starts_at: "2026-12-15T10:00:00Z", notes: "", created_at: "2026-11-01T00:00:00Z", ...over,
});
const draft = () => screen.getByLabelText(/^Draft/) as HTMLTextAreaElement;

describe("message drafts", () => {
  it("mentions a recorded interview only when chosen, with its source, and the time only when asked", async () => {
    const user = userEvent.setup();
    render(<DraftComposer role="Ward nurse" employer="Synthetic Hospital" events={[ev(), ev({ id: "e2", title: "Phone screen", on_date: null, local_time: null, timezone: null, starts_at: null })]} />);
    expect(draft().value).not.toMatch(/on \w/); // nothing chosen, nothing said
    const pick = screen.getByRole("combobox", { name: "Interview" });
    expect([...(pick as HTMLSelectElement).options].map((o) => o.text)).toEqual(["Don't mention one", `Panel interview · ${formatDay("2026-12-15")}`]); // undated ones aren't offered
    await user.selectOptions(pick, "e1");
    expect(draft().value).toContain(`Thank you for your time on ${formatDay("2026-12-15")} talking with me`);
    expect(screen.getByText(/From your recorded event “Panel interview”\. A recorded time doesn't mean it happened/)).toBeInTheDocument();
    const time = screen.getByRole("checkbox", { name: "Include the time" });
    expect(time).not.toBeChecked();
    await user.click(time);
    expect(draft().value).toContain("at 10:00 (Europe/London)");
  });

  it("never replaces edited text silently: the learner updates it or keeps it", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<DraftComposer role="Ward nurse" employer="Synthetic Hospital" events={[ev()]} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Interview" }), "e1");
    await user.type(draft(), " Thanks again.");
    const mine = draft().value;
    // The interview is rescheduled (new data from the server) after the learner edited the draft.
    rerender(<DraftComposer role="Ward nurse" employer="Synthetic Hospital" events={[ev({ on_date: "2026-12-16" })]} />);
    expect(draft().value).toBe(mine);
    expect(screen.getByText(/The details behind this draft changed since you edited it/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep my text" }));
    expect(screen.queryByText(/The details behind this draft changed/)).toBeNull();
    expect(draft().value).toBe(mine);
    // A renamed role later: asked again; this time the learner updates it.
    rerender(<DraftComposer role="Senior ward nurse" employer="Synthetic Hospital" events={[ev({ on_date: "2026-12-16" })]} />);
    await user.click(screen.getByRole("button", { name: "Update the draft (replaces your edits)" }));
    expect(draft().value).toContain(`Senior ward nurse role at Synthetic Hospital`);
    expect(draft().value).toContain(formatDay("2026-12-16"));
    expect(draft().value).not.toContain("Thanks again.");
  });

  it("before any edit the draft simply follows the details, and a removed interview is just not mentioned", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<DraftComposer role="Ward nurse" employer="Synthetic Hospital" events={[ev()]} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Interview" }), "e1");
    rerender(<DraftComposer role="Ward nurse" employer="Synthetic Hospital" events={[]} />);
    expect(draft().value).not.toContain(formatDay("2026-12-15"));
    expect(screen.queryByText(/The details behind this draft changed/)).toBeNull();
  });

  it("copying that fails says so and keeps the text", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: () => Promise.reject(new Error("denied")) } });
    render(<DraftComposer role="Ward nurse" employer="Synthetic Hospital" />);
    const before = draft().value;
    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(await screen.findByText(/Couldn't copy here: select the text and copy it yourself/)).toBeInTheDocument();
    expect(draft().value).toBe(before);
  });
});
