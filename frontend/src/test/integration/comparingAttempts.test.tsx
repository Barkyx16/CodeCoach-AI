import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { CareerAnalytics, ChartAttempt, ChartAttempts } from "@/api/types";
import { comparisonWith, nurseAnalytics, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

/**
 * The progress chart adopts the comparison contract (Volume 12, prompt 6; docs/COMPARING_ATTEMPTS.md):
 * only its cohort is counted and the counts are shown, fewer than two comparable answers draw no
 * trend, and every answer in the range is listed and reachable with the server's comparison,
 * word for word.
 */
const nurse = { ...baseUser, career_track: "registered-nurse" };
const today = new Date().toISOString().slice(0, 10);
const monday = (() => {
  const d = new Date(`${today}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  return d.toISOString().slice(0, 10);
})();
const SERIES = "Graded by fixed rules, rubric v10, scored 0-100";

const attempt = (over: Partial<ChartAttempt>): ChartAttempt => ({
  answer_id: "a-1", question_id: "e-good-0", question_title: "What good patient assessment looks like",
  href: "/careers/registered-nurse/questions/e-good-0?answer=a-1", created_at: `${today}T09:00:00Z`,
  score: 64, scoring: "scored", scale: "0-100", series: SERIES, not_counted: null, comparison: null, ...over,
});

function setup(analytics: Partial<CareerAnalytics>, pages: ChartAttempt[][] = [[]]) {
  const asked: { since: string | null; offset: string | null }[] = [];
  const total = pages.flat().length;
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
    http.get(`${API}/api/v1/me/careers/:track/analytics`, () => HttpResponse.json({ ...nurseAnalytics, ...analytics })),
    http.get(`${API}/api/v1/me/careers/:track/analytics/attempts`, ({ request }) => {
      const url = new URL(request.url);
      const offset = Number(url.searchParams.get("offset") ?? 0);
      asked.push({ since: url.searchParams.get("since"), offset: url.searchParams.get("offset") });
      const index = pages.findIndex((_, i) => pages.slice(0, i).flat().length === offset);
      const body: ChartAttempts = {
        total, in_chart: pages.flat().filter((a) => a.series).length, offset, items: pages[index] ?? [],
      };
      return HttpResponse.json(body);
    }),
  );
  return asked;
}

describe("The progress chart and the comparison contract", () => {
  it("counts only its cohort, shows the count, and names what it leaves out", async () => {
    setup({
      answers: 4,
      trends: [{ evaluator: SERIES, attempts: 2, points: [{ week_start: monday, answers: 2, average_score: 70 }] }],
      not_in_trend: [{ rule: "scoring", reason: "too short to score", count: 1 }, { rule: "rubric", reason: "which rubric graded it wasn't recorded", count: 1 }],
    });
    renderApp("/analytics", { signedIn: true });
    expect(await screen.findByText(`${SERIES}: 2 answers counted.`, { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/Not in the trend: 1 answer \(too short to score\); 1 answer \(which rubric graded it wasn't recorded\)\./)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /Average score per week/ })).toBeInTheDocument();
  });

  it("with fewer than two comparable answers, says so instead of drawing a trend", async () => {
    setup({
      answers: 2,
      trends: [{ evaluator: SERIES, attempts: 1, points: [{ week_start: monday, answers: 1, average_score: 64 }] }],
      not_in_trend: [{ rule: "scoring", reason: "too short to score", count: 1 }],
    });
    renderApp("/analytics", { signedIn: true });
    expect(await screen.findByText("Not enough comparable answers to show a trend: 1 in this range. It takes two.")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /Average score per week/ })).not.toBeInTheDocument();
  });

  it("lists every answer in the range, reachable, with the server's comparison word for word", async () => {
    const why = "Partly comparable: scored under different rubrics (v9 and v10): compare what you wrote, not the numbers. (Comparison rules v1)";
    const first = [
      attempt({ answer_id: "a-3", score: 81, comparison: comparisonWith("a-2", "partially_comparable", { explanation: why }) }),
      attempt({ answer_id: "a-2", score: 30, scoring: "too_short", series: null, not_counted: "too short to score", comparison: comparisonWith("a-1", "partially_comparable") }),
    ];
    const second = [attempt({ answer_id: "a-1", href: "/careers/registered-nurse/questions/e-good-0?answer=a-1" })];
    setup({ answers: 3 }, [first, second]);
    const { user } = renderApp("/analytics", { signedIn: true });
    await user.click(await screen.findByText("Answers in this range, and which the trend counts"));
    const list = await screen.findByText(/2 of 3 answers are in the trend/);
    const section = list.closest("details") as HTMLElement;
    const rows = await within(section).findAllByRole("listitem");
    expect(rows[0]).toHaveTextContent(`81/100 · In the trend`);
    expect(rows[0]).toHaveTextContent(`Compared with your answer before it: ${why}`);
    expect(rows[1]).toHaveTextContent("Too short to score · Not in the trend: too short to score");
    expect(rows[1]).not.toHaveTextContent("30/100"); // no number for an answer too short to score
    // Every answer stays reachable: the next page, then a link to each one's own page.
    await user.click(within(section).getByRole("button", { name: "Show more" }));
    await waitFor(() => expect(within(section).getAllByRole("listitem")).toHaveLength(3));
    const last = within(section).getAllByRole("listitem")[2]!;
    expect(last).toHaveTextContent("Your first answer to this question.");
    expect(within(last).getByRole("link", { name: "What good patient assessment looks like" })).toHaveAttribute("href", "/careers/registered-nurse/questions/e-good-0?answer=a-1");
    expect(within(section).queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("the range filter changes the listed cohort too", async () => {
    const asked = setup({}, [[attempt({})]]);
    const { user } = renderApp("/analytics?range=30", { signedIn: true });
    await user.click(await screen.findByText("Answers in this range, and which the trend counts"));
    await waitFor(() => expect(asked.length).toBeGreaterThan(0));
    const since = asked.at(-1)!.since!;
    const days = Math.round((Date.parse(today) - Date.parse(since)) / 86_400_000);
    expect(days).toBeGreaterThanOrEqual(29);
    expect(days).toBeLessThanOrEqual(31);
  });

  it("a score on another scale is shown on its own scale, never converted", async () => {
    setup({}, [[attempt({ score: 3, scale: "0-4", series: null, not_counted: "its score scale isn't this chart's" })]]);
    const { user } = renderApp("/analytics", { signedIn: true });
    await user.click(await screen.findByText("Answers in this range, and which the trend counts"));
    expect(await screen.findByText(/3\/4 · Not in the trend/)).toBeInTheDocument();
    expect(screen.queryByText(/75\/100/)).not.toBeInTheDocument();
  });
});
