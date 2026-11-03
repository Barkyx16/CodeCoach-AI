import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "./fixtures";

// Sharing an answer with a reviewer, end to end against the real backend. The "reviewer" is a
// separate browser context on this machine: nobody real is contacted.

const ANSWER = "Last winter a patient's vitals dropped suddenly. I checked his airway and breathing first. "
  + "My manager's number is 555-0100. I called the rapid response team and gave an SBAR handoff. "
  + "As a result he was stable within 30 minutes and I documented everything.";
const PRIVATE_SENTENCE = "My manager's number is 555-0100.";

async function signUpNurse(page: Page, tag: string): Promise<string> {
  const email = `${tag}-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  await expect(page).toHaveURL(/\/dashboard$/);
  return email;
}

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

test("share a chosen part of an answer, review it in another browser, then revoke it everywhere", async ({ page, browser, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const ownerEmail = await signUpNurse(page, "owner");
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: "Feedback" })).toBeVisible();

  // Choose: leave out the private sentence, include the automated feedback, add a note.
  await page.getByRole("link", { name: "Ask someone for feedback" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Share an answer with someone you trust" })).toBeVisible();
  const preview = page.getByRole("region", { name: "Preview: what your reviewer sees" });
  await expect(preview.getByText(PRIVATE_SENTENCE)).toBeVisible();
  await page.getByRole("checkbox", { name: new RegExp(PRIVATE_SENTENCE.replace(/[.]/g, "\\.")) }).uncheck();
  await page.getByRole("checkbox", { name: /Include CodeCoach's automated feedback/ }).check();
  await page.getByLabel(/Note to your reviewer/).fill("Is my escalation clear?");
  await expect(preview.getByText(PRIVATE_SENTENCE)).toHaveCount(0);
  await expect(preview.getByText("Is my escalation clear?")).toBeVisible();
  await expect(preview.getByText("[…] 1 sentence not shared")).toBeVisible();
  const previewText = await preview.locator(".shared-snapshot").innerText();
  await axe(page, "share composer");

  await expect(page.getByRole("button", { name: "Create link" })).toBeDisabled();
  await page.getByRole("checkbox", { name: /anyone who has the link/ }).check();
  await page.getByRole("button", { name: "Create link" }).click();
  const link = await page.getByRole("textbox", { name: "Private link" }).inputValue();
  expect(link).toMatch(/\/shared#t=[A-Za-z0-9_-]{43}$/);
  await page.getByRole("button", { name: "Copy link" }).click();
  await expect(page.getByText(/Copied\./)).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(link);
  const token = link.split("#t=")[1]!;

  // A different browser, not signed in: exactly the preview, nothing else.
  const reviewerContext = await browser.newContext();
  const reviewer = await reviewerContext.newPage();
  const urls: string[] = [];
  reviewer.on("request", (r) => urls.push(r.url()));
  reviewer.on("dialog", () => { throw new Error("a dialog opened: injected script ran"); });
  await reviewer.goto(link);
  await expect(reviewer.getByRole("heading", { level: 1, name: "A practice answer to review" })).toBeVisible();
  const copy = reviewer.getByRole("region", { name: "The shared answer" });
  expect(await copy.locator(".shared-snapshot").innerText()).toBe(previewText);
  const body = await reviewer.locator("body").innerText();
  expect(body).not.toContain(PRIVATE_SENTENCE);
  expect(body).not.toContain(ownerEmail);
  expect(urls.filter((u) => u.includes(token)), "the secret never goes into a request URL").toEqual([]);
  await expect(reviewer.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
  await axe(reviewer, "reviewer page");

  // Structured feedback with an injection attempt, sent twice quickly: stored once, shown as text.
  await reviewer.getByLabel(/Your name/).fill("Sam <img src=x onerror=alert(1)>");
  await reviewer.getByLabel("What was clear?").fill("<script>alert('x')</script> The SBAR part was clear.");
  await reviewer.getByLabel("One useful next step").fill("Start with the outcome.");
  await reviewer.getByLabel("Sentence").selectOption("3"); // "4. I called the rapid response team…"
  await reviewer.getByLabel("Your comment").fill("Who did you call first?");
  await reviewer.getByRole("button", { name: "Add comment" }).click();
  await reviewer.getByRole("button", { name: "Send feedback" }).dblclick();
  await expect(reviewer.getByRole("heading", { name: "Thanks, your feedback was sent" })).toBeVisible();
  await expect(reviewer.getByText("<script>alert('x')</script> The SBAR part was clear.")).toBeVisible();

  // The owner sees one response, from a person, kept apart from the automated feedback.
  await page.getByRole("link", { name: "See this share and its feedback" }).click();
  const item = page.getByRole("article", { name: /Feedback from Sam/ });
  await expect(item).toHaveCount(1);
  await expect(item.getByText("(guest, name not verified)", { exact: false })).toBeVisible();
  await expect(item.getByText("Who did you call first?")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Feedback from people \(1 response\)/ })).toBeVisible();
  await item.getByRole("button", { name: "Useful" }).click();
  await expect(item.getByRole("button", { name: "Useful" })).toHaveAttribute("aria-pressed", "true");
  await axe(page, "share detail");

  // Another account can't open the owner's share page.
  const otherContext = await browser.newContext();
  const other = await otherContext.newPage();
  await signUpNurse(other, "other");
  await other.goto(page.url());
  await expect(other.getByText(/Share not found/)).toBeVisible();
  await otherContext.close();

  // Revoke: the reviewer's page, a reload and the API all refuse; nothing comes from a cache.
  await page.getByRole("button", { name: "Turn the link off" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Turn it off" }).click();
  await expect(page.getByText("Link turned off", { exact: true })).toBeVisible();
  await reviewer.reload();
  await expect(reviewer.getByRole("heading", { level: 1, name: "This link was turned off" })).toBeVisible();
  await expect(reviewer.getByText("The SBAR part")).toHaveCount(0);
  const api = await reviewer.request.post("http://localhost:8000/api/v1/shared/open", { data: { token } });
  expect(api.status()).toBe(410);
  expect(await api.text()).not.toContain("rapid response");
  expect(api.headers()["cache-control"] ?? "").not.toContain("max-age");
  await reviewerContext.close();
});

test("the reviewer page reflows at 320px in the light theme", async ({ page, browser }) => {
  await signUpNurse(page, "narrow");
  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  await page.getByRole("textbox", { name: "Your answer" }).fill(ANSWER);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await page.getByRole("link", { name: "Ask someone for feedback" }).click();
  await page.getByRole("checkbox", { name: /anyone who has the link/ }).check();
  await page.getByRole("button", { name: "Create link" }).click();
  const link = await page.getByRole("textbox", { name: "Private link" }).inputValue();

  const ctx = await browser.newContext({ viewport: { width: 320, height: 700 } });
  const reviewer = await ctx.newPage();
  await reviewer.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await reviewer.goto(link);
  await expect(reviewer.getByRole("heading", { level: 1, name: "A practice answer to review" })).toBeVisible();
  await expect(reviewer.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await reviewer.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(reviewer, "reviewer page, light, 320px");
  await page.setViewportSize({ width: 320, height: 700 });
  await page.getByRole("link", { name: "See this share and its feedback" }).click();
  await expect(page.getByRole("heading", { name: /Feedback from people/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await ctx.close();
});
