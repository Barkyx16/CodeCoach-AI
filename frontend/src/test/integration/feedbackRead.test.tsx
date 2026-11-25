/**
 * What an interview's feedback read (Volume 15, prompt 8; docs/COACH_CONTEXT.md, "What the feedback
 * read"): the review lists each part by label and size, with what was replaced, and says whether it
 * was checked; an interview scored before this says it wasn't recorded.
 */
import { render, screen } from "@testing-library/react";

import type { FeedbackRead } from "@/api/types";
import { FeedbackReadSection } from "@/features/review/FeedbackRead";

const timedOut: FeedbackRead = {
  recorded: true, ending: "time_expired", checked: false, fingerprint: "v1:abc", read_by: "Claude, by Anthropic: an outside service CodeCoach sends this to",
  text: "You didn't check this before it was scored: time ran out.",
  items: [
    { label: "The conversation so far", chars: 1234, notes: [] },
    { label: "Your code", chars: 210, notes: ["1 secret-looking string replaced with [REDACTED]."] },
    { label: "How it ended", chars: 27, notes: [] },
  ],
};

describe("What the feedback read", () => {
  it("lists what a timed-out interview's feedback read and says it wasn't checked", () => {
    render(<FeedbackReadSection read={timedOut} />);
    const section = screen.getByRole("region", { name: "What the feedback read" });
    expect(section).toHaveTextContent("You didn't check this before it was scored: time ran out.");
    expect(section).toHaveTextContent("The conversation so far · 1,234 characters");
    expect(section).toHaveTextContent("Your code · 210 characters · 1 secret-looking string replaced with [REDACTED].");
    expect(section).toHaveTextContent("Read by: Claude, by Anthropic");
  });

  it("says a checked one was checked", () => {
    render(<FeedbackReadSection read={{ ...timedOut, ending: "finished", checked: true, text: "You checked this before it was scored." }} />);
    expect(screen.getByText("You checked this before it was scored.")).toBeInTheDocument();
  });

  it("says when what it read wasn't recorded, rather than rebuilding it", () => {
    render(<FeedbackReadSection read={{ recorded: false, ending: null, checked: null, items: [], fingerprint: null, read_by: null, text: "What it read wasn't recorded then." }} />);
    expect(screen.getByRole("region", { name: "What the feedback read" })).toHaveTextContent("What it read wasn't recorded then.");
    expect(screen.queryByRole("listitem")).toBeNull();
  });
});
