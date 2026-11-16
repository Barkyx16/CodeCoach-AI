/**
 * A History row opens one attempt (Volume 17, prompt 2): the page reads `?attempt=` once, loads that
 * attempt, shows it and brings it into view; one that can't be read is said, not shown as empty.
 */
import { render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";

import { LINKED_MISSING, useLinkedAttempt } from "@/hooks/useLinkedAttempt";

function Page({ load }: { load: (id: string) => Promise<{ id: string; text: string }> }) {
  const [shown, setShown] = useState<{ id: string; text: string } | null>(null);
  const linked = useLinkedAttempt(load, setShown, "result");
  return (
    <div>
      <p>state: {linked}</p>
      {linked === "missing" && <p role="status">{LINKED_MISSING}</p>}
      {shown && <h2 id="result" tabIndex={-1}>{shown.text}</h2>}
    </div>
  );
}

describe("Opening the attempt a link names", () => {
  it("loads it once and shows it", async () => {
    const asked: string[] = [];
    const load = (id: string) => { asked.push(id); return Promise.resolve({ id, text: `Attempt ${id}` }); };
    render(<MemoryRouter initialEntries={["/whiteboard/p?attempt=a-2"]}><Page load={load} /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Attempt a-2" })).toBeInTheDocument();
    expect(screen.getByText("state: shown")).toBeInTheDocument();
    expect(asked).toEqual(["a-2"]);
  });

  it("says when it can't be opened", async () => {
    render(<MemoryRouter initialEntries={["/compare/l?attempt=gone"]}><Page load={() => Promise.reject(new Error("404"))} /></MemoryRouter>);
    expect(await screen.findByRole("status")).toHaveTextContent(LINKED_MISSING);
  });

  it("does nothing without a link", () => {
    const load = vi.fn();
    render(<MemoryRouter initialEntries={["/work-samples/b"]}><Page load={load} /></MemoryRouter>);
    expect(screen.getByText("state: none")).toBeInTheDocument();
    expect(load).not.toHaveBeenCalled();
  });
});
