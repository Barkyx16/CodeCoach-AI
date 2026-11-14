import { screen, waitFor, within } from "@testing-library/react";

import type { Career } from "@/api/types";
import { matchCareers } from "@/features/careers/careerSearch";

import { renderApp } from "../render";

const job = (slug: string, title: string, category: string): Career => ({
  slug, title, category, summary: "", has_coding: false, question_count: 0, answer_feedback: "not_measured",
});
const CATALOGUE = [
  job("nurse-practitioner", "Nurse Practitioner", "Healthcare"),
  job("registered-nurse", "Registered Nurse", "Healthcare"),
  job("pharmacist", "Pharmacist", "Healthcare"),
  job("barista", "Barista", "Customer Service & Hospitality"),
  job("cafe-manager", "Café Manager", "Customer Service & Hospitality"),
];

describe("matching jobs to what was typed", () => {
  const titles = (q: string) => matchCareers(CATALOGUE, q).map((c) => c.title);

  it("finds a job from the start of any word, best match first", () => {
    expect(titles("nurse")).toEqual(["Nurse Practitioner", "Registered Nurse"]); // the title that starts with it first
    expect(titles("reg nur")).toEqual(["Registered Nurse"]); // every word must match
    expect(titles("PHARM")).toEqual(["Pharmacist"]);
  });

  it("also matches the industry, ranked below title matches, and ignores accents", () => {
    expect(titles("hospitality")).toEqual(["Barista", "Café Manager"]);
    expect(titles("cafe")).toEqual(["Café Manager"]);
  });

  it("matches only at the start of a word, and finds nothing for nonsense", () => {
    expect(titles("urse")).toEqual([]);
    expect(titles("zzz")).toEqual([]);
    expect(titles("  ")).toEqual(CATALOGUE.map((c) => c.title)); // nothing typed: every job
  });
});

describe("the job search box", () => {
  async function openBox() {
    const r = renderApp("/register");
    const box = await screen.findByRole("combobox", { name: "Job you're preparing for" });
    await waitFor(() => expect(box).toBeEnabled());
    return { ...r, box };
  }

  it("lists every job by industry when opened, and narrows as you type", async () => {
    const { user, box } = await openBox();
    expect(box).toHaveAttribute("aria-expanded", "false");
    await user.click(box);
    expect(box).toHaveAttribute("aria-expanded", "true");
    const list = screen.getByRole("listbox", { name: "Jobs" });
    expect(within(list).getByRole("group", { name: "Healthcare" })).toBeInTheDocument();
    expect(within(list).getAllByRole("option")).toHaveLength(3);

    await user.type(box, "nur");
    expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["Registered NurseHealthcare"]);
    expect(screen.getByRole("status")).toHaveTextContent("1 job matches");
  });

  it("chooses with the arrow keys and Enter, without submitting the form", async () => {
    const { user, box } = await openBox();
    await user.click(box);
    await user.type(box, "barista");
    expect(box).toHaveAttribute("aria-activedescendant", expect.stringContaining("barista"));
    await user.keyboard("{Enter}");
    expect(box).toHaveValue("Barista");
    expect(box).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument(); // still on the form
  });

  it("Escape closes and keeps the job already chosen; a click chooses too", async () => {
    const { user, box } = await openBox();
    await user.click(box);
    await user.click(screen.getByRole("option", { name: /Software Engineer/ }));
    expect(box).toHaveValue("Software Engineer");

    await user.click(box);
    await user.keyboard("bar");
    await user.keyboard("{Escape}");
    expect(box).toHaveValue("Software Engineer"); // typing alone never changes the job
    expect(box).toHaveAttribute("aria-expanded", "false");
  });

  it("says when nothing matches", async () => {
    const { user, box } = await openBox();
    await user.click(box);
    await user.type(box, "astronaut");
    expect(screen.getByText(/No job matches “astronaut”/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("0 jobs match");
    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });
});
