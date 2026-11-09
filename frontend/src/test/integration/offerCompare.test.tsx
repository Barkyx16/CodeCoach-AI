/**
 * Private offer comparisons (Volume 10, prompt 9; docs/OFFER_COMPARISON.md): the fictional example
 * with unknowns said in words, figures that show their working and follow edits, a refused save
 * showing both versions, unsaved changes kept on this device, amounts hidden on screen, Copy as text
 * previewing exactly what it copies, text shown as text, weights labelled as not a recommendation,
 * and an application linked without anything being sent to it.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ComparisonDoc, OfferComparison } from "@/api/types";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const offerA = {
  id: "a", label: "Harbour Point (fictional)", application_id: null, source_note: "A phone call", terms_as_of: "2026-11-02", currency: "USD",
  pay_amount: 21.5, pay_period: "hour" as const, months_paid: null, hours_per_week: 40, weeks_per_year: null, guaranteed_extra: null,
  guaranteed_note: "", bonus_amount: 1000, bonus_note: "If targets are met", equity_note: "", benefits_note: "",
};
const offerB = { ...offerA, id: "b", label: "Northfield (fictional)", currency: "GBP", pay_amount: 31000, pay_period: "year" as const, hours_per_week: null, guaranteed_extra: 0, bonus_amount: null, bonus_note: "", source_note: "" };
const doc: ComparisonDoc = { title: "Fictional example: two offers with gaps", offers: [offerA, offerB], factors: [
  { id: "commute", label: "Commute", weight: 2, ratings: { a: { state: "rated", value: 2, note: "" }, b: { state: "unknown", value: null, note: "" } } },
], conversions: [], weights_on: false, show_in: null };
const unknown = (why: string) => ({ value: null, currency: "USD", formula: null, assumptions: [], unknown: why });
const derived = (hourly: { value: number | null; formula: string | null; unknown: string | null }, weighted = false) => ({
  offers: [
    { id: "a", annual_pay: { ...unknown(""), ...hourly, assumptions: hourly.value ? ["40 hours a week and 52 paid weeks a year (you entered these); no overtime"] : [] },
      annual_pay_converted: null, guaranteed_first_year: unknown("Yearly pay is unknown, so guaranteed first-year cash is too."), guaranteed_first_year_converted: null,
      conditional_bonus: { value: 1000, currency: "USD", text: "Up to 1,000 USD, conditional: not counted in guaranteed pay" }, equity: "Not entered" },
    { id: "b", annual_pay: { value: 31000, currency: "GBP", formula: "31,000 GBP a year, as entered", assumptions: [], unknown: null }, annual_pay_converted: null,
      guaranteed_first_year: { value: 31000, currency: "GBP", formula: "31,000 GBP yearly pay + 0 GBP guaranteed one-off = 31,000 GBP", assumptions: [], unknown: null },
      guaranteed_first_year_converted: null, conditional_bonus: { value: null, currency: "GBP", text: "Not entered (unknown, not zero)" }, equity: "Not entered" },
  ],
  mixed_currencies: true, currency_note: "These offers are in GBP, USD. They're shown in their own currencies; add a dated rate to see one currency.",
  not_estimated: "Tax, take-home pay, the value of equity or benefits, whether a bonus pays out, and future raises aren't estimated.",
  weighted: weighted ? { rows: [{ id: "a", label: offerA.label, total: 4, counted: 1, contributions: [{ factor: "Commute", weight: 2, rating: 2, points: 4, formula: "weight 2 × your rating 2 = 4" }], not_counted: [] },
    { id: "b", label: offerB.label, total: 0, counted: 0, contributions: [], not_counted: [{ factor: "Commute", reason: "unknown" }] }], order: ["a", "b"],
    explanation: "Each point is your weight × your rating (1 to 5).", uneven: "The offers have different numbers of rated factors, so the totals aren't like for like.",
    label: "Your weighted ordering: it reflects only your weights and ratings, not a recommendation or an objectively best offer." } : null,
});
const initial = derived({ value: null, formula: null, unknown: "Enter the weeks paid a year to put hourly pay on a yearly basis." });
const comparison = (over: Partial<OfferComparison> = {}): OfferComparison => ({
  id: "cmp-1", revision: 1, doc, derived: initial, applications: {}, created_at: "2026-11-09T10:00:00Z", updated_at: "2026-11-09T10:00:00Z", ...over,
});

let saves: { doc: ComparisonDoc; expected_revision: number }[] = [];
let previews: ComparisonDoc[] = [];
let appWrites = 0;
let conflictNext = false;
function serve() {
  saves = []; previews = []; appWrites = 0; conflictNext = false;
  let current = comparison();
  server.use(
    http.get(`${API}/api/v1/me/offer-comparisons`, () => HttpResponse.json([])),
    http.post(`${API}/api/v1/me/offer-comparisons`, () => HttpResponse.json(current, { status: 201 })),
    http.get(`${API}/api/v1/me/offer-comparisons/cmp-1`, () => HttpResponse.json(current)),
    http.post(`${API}/api/v1/me/offer-comparisons/preview`, async ({ request }) => {
      const body = (await request.json()) as ComparisonDoc;
      previews.push(body);
      const weeks = body.offers?.[0]?.weeks_per_year;
      return HttpResponse.json({ derived: weeks ? derived({ value: 44720, formula: "21.50 USD an hour × 40 hours a week × 52 weeks = 44,720 USD a year", unknown: null }, body.weights_on ?? false) : derived({ value: null, formula: null, unknown: "Enter the weeks paid a year to put hourly pay on a yearly basis." }, body.weights_on ?? false) });
    }),
    http.put(`${API}/api/v1/me/offer-comparisons/cmp-1`, async ({ request }) => {
      const body = (await request.json()) as (typeof saves)[number];
      if (conflictNext) {
        conflictNext = false;
        current = comparison({ revision: 2, doc: { ...doc, title: "Renamed in another tab" } });
        return HttpResponse.json({ error: { code: "stale_revision", message: "Saved elsewhere.", details: { current_revision: 2, current } } }, { status: 409 });
      }
      saves.push(body);
      current = comparison({ revision: body.expected_revision + 1, doc: body.doc });
      return HttpResponse.json(current);
    }),
    http.get(`${API}/api/v1/me/applications`, () => HttpResponse.json([{ id: "app-1", employer: "Northfield", role_title: "Support analyst", stage: "offer" }])),
    http.all(`${API}/api/v1/me/applications/*`, () => { appWrites += 1; return HttpResponse.json({}); }),
  );
}
const KEY = `offer-compare-draft:${baseUser.id}:cmp-1`;

describe("offer comparisons", () => {
  it("starts from the fictional example, says what's unknown, and the figures follow an edit", async () => {
    serve();
    const { user, router } = renderApp("/offers/compare", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Start with a fictional example" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/offers/compare/cmp-1"));
    const figures = await screen.findByRole("region", { name: "How the numbers are worked out" });
    expect(within(figures).getByRole("region", { name: `Figures for ${offerA.label}` })).toHaveTextContent("Unknown: Enter the weeks paid a year to put hourly pay on a yearly basis.");
    expect(figures).toHaveTextContent("These offers are in GBP, USD.");
    expect(figures).toHaveTextContent("Up to 1,000 USD, conditional: not counted in guaranteed pay");
    expect(figures).toHaveTextContent("Not entered (unknown, not zero)");
    await user.type(screen.getAllByLabelText("Weeks paid a year")[0]!, "52");
    await waitFor(() => expect(figures).toHaveTextContent("21.50 USD an hour × 40 hours a week × 52 weeks = 44,720 USD a year"));
    expect(figures).toHaveTextContent("Assumes 40 hours a week and 52 paid weeks a year (you entered these); no overtime.");
    expect(previews.at(-1)!.offers![0]!.weeks_per_year).toBe(52);
  });

  it("a save refused because another tab saved first shows both versions, and keeping mine saves over it", async () => {
    serve();
    const { user } = renderApp("/offers/compare/cmp-1", { signedIn: true });
    const title = await screen.findByLabelText("Comparison name");
    await user.clear(title);
    await user.type(title, "My two offers");
    conflictNext = true;
    await user.click(screen.getByRole("button", { name: "Save" }));
    const conflict = await screen.findByText(/Renamed in another tab/);
    expect(conflict).toBeInTheDocument();
    expect(saves).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Keep mine as the newest" }));
    await waitFor(() => expect(saves).toHaveLength(1));
    expect(saves[0]!.expected_revision).toBe(2);
    expect(saves[0]!.doc.title).toBe("My two offers");
    expect(await screen.findByText("Saved as version 3. Only you can see it.")).toBeInTheDocument();
  });

  it("keeps unsaved changes on this device through a reload, and hides amounts on request", async () => {
    serve();
    const first = renderApp("/offers/compare/cmp-1", { signedIn: true });
    await first.user.type((await screen.findAllByLabelText("Bonus conditions"))[1]!, "Not described");
    expect(JSON.parse(localStorage.getItem(KEY)!).doc.offers[1].bonus_note).toBe("Not described");
    first.unmount();
    serve();
    const second = renderApp("/offers/compare/cmp-1", { signedIn: true });
    const banner = await screen.findByRole("region", { name: "Unsaved changes" });
    await second.user.click(within(banner).getByRole("button", { name: "Restore them" }));
    expect(screen.getAllByLabelText("Bonus conditions")[1]).toHaveValue("Not described");
    await second.user.click(screen.getByRole("checkbox", { name: "Hide amounts on screen" }));
    expect(document.querySelector(".oc-page")).toHaveClass("is-hidden");
  });

  it("Copy as text shows exactly what it copies; text is text; an application is linked without being touched", async () => {
    serve();
    const { user } = renderApp("/offers/compare/cmp-1", { signedIn: true });
    const name = (await screen.findAllByLabelText("Name"))[0]!;
    const hostile = '<img src=x onerror="window.__ocPwned=1"> Bigco';
    await user.clear(name);
    await user.type(name, hostile);
    await user.selectOptions(screen.getAllByLabelText("Linked application (optional)")[0]!, "app-1");
    await user.click(screen.getByRole("button", { name: "Copy as text…" }));
    const dialog = screen.getByRole("dialog", { name: "Copy as text: exactly this" });
    const shown = within(dialog).getByText((_, el) => el?.tagName === "PRE").textContent!;
    expect(shown).toContain(hostile);
    expect(shown).toContain("Commute: 2 of 5 (my rating)");
    expect(dialog).toHaveTextContent("Nothing is sent, shared or published.");
    await user.click(within(dialog).getByRole("button", { name: "Copy" }));
    expect(await screen.findByText("Copied to your clipboard.")).toBeInTheDocument();
    expect(await navigator.clipboard.readText()).toBe(shown); // user-event's clipboard: exactly the preview
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect((window as { __ocPwned?: number }).__ocPwned).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saves).toHaveLength(1));
    expect(saves[0]!.doc.offers![0]!.application_id).toBe("app-1");
    expect(appWrites).toBe(0);
  });

  it("weights order the offers only when turned on, with every point explained and no recommendation", async () => {
    serve();
    const { user } = renderApp("/offers/compare/cmp-1", { signedIn: true });
    await screen.findByRole("region", { name: "How the numbers are worked out" });
    expect(screen.queryByRole("region", { name: "Your weighted ordering" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Use my weights to order the offers (you can turn this off)" }));
    const weighted = await screen.findByRole("region", { name: "Your weighted ordering" });
    expect(weighted).toHaveTextContent("not a recommendation or an objectively best offer");
    expect(weighted).toHaveTextContent("Commute: weight 2 × your rating 2 = 4");
    expect(weighted).toHaveTextContent("Commute: not counted (unknown)");
    expect(weighted).toHaveTextContent("the totals aren't like for like");
  });
});
