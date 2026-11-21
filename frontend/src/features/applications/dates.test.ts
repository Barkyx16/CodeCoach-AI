import { daysBetween, dueLabel, todayIn } from "./dates";
import { draftMessage } from "./drafts";
import { sortApps } from "./sorting";
import type { ApplicationSummary } from "@/api/types";

describe("dates in the learner's time zone", () => {
  it("is already tomorrow in Tokyo and still today in Chicago", () => {
    const now = new Date("2026-11-03T23:30:00Z");
    expect(todayIn("Asia/Tokyo", now)).toBe("2026-11-04");
    expect(todayIn("America/Chicago", now)).toBe("2026-11-03");
    expect(todayIn("UTC", now)).toBe("2026-11-03");
  });

  it("counts calendar days across daylight-saving changes and month ends", () => {
    expect(daysBetween("2026-03-07", "2026-03-09")).toBe(2); // US spring forward on the 8th
    expect(daysBetween("2026-10-31", "2026-11-02")).toBe(2); // fall back on the 1st
    expect(daysBetween("2026-12-31", "2027-01-01")).toBe(1);
  });

  it("describes due dates neutrally", () => {
    expect(dueLabel("2026-11-03", "2026-11-03")).toBe("Due today");
    expect(dueLabel("2026-11-04", "2026-11-03")).toBe("Due tomorrow");
    expect(dueLabel("2026-11-10", "2026-11-03")).toBe("Due in 7 days");
    expect(dueLabel("2026-11-02", "2026-11-03")).toBe("Was due yesterday");
    expect(dueLabel("2026-10-30", "2026-11-03")).toBe("Was due 4 days ago");
  });
});

describe("message drafts", () => {
  it("use only the facts given, and placeholders for the rest", () => {
    const d = draftMessage({ kind: "thank_you", role: "Ward nurse", employer: "Mercy General" });
    expect(d.subject).toBe("Thank you: Ward nurse interview");
    expect(d.body).toBe("Hello,\n\nThank you for your time talking with me about the Ward nurse role at Mercy General.\n\nKind regards,\n\n[Your name]");
    const f = draftMessage({ kind: "follow_up", role: "RN", employer: "Mercy", recipient: "Ms Lee", when: "on 1 November", point: "I'm still very interested.", sender: "Ada" });
    expect(f.body).toContain("Dear Ms Lee,");
    expect(f.body).toContain("my application for the RN role at Mercy on 1 November.");
    expect(f.body).toContain("I'm still very interested.");
    expect(f.body.endsWith("Ada")).toBe(true);
  });
});

describe("sorting the list", () => {
  const app = (over: Partial<ApplicationSummary>): ApplicationSummary => ({
    id: "x", employer: "E", role_title: "R", stage: "saved", applied_on: null, next_action: "", next_action_due: null,
    target: null, archived: false, next_event: null, updated_at: "2026-11-01T00:00:00Z", ...over,
  });
  it("keeps unknown dates last whichever way it sorts", () => {
    const list = [app({ id: "a", applied_on: null }), app({ id: "b", applied_on: "2026-10-01" }), app({ id: "c", applied_on: "2026-09-01" })];
    expect(sortApps(list, "applied", "asc").map((a) => a.id)).toEqual(["c", "b", "a"]);
    expect(sortApps(list, "applied", "desc").map((a) => a.id)).toEqual(["b", "c", "a"]);
    expect(sortApps([app({ id: "o", stage: "offer" }), app({ id: "s", stage: "saved" })], "stage", "asc").map((a) => a.id)).toEqual(["s", "o"]);
  });
});
