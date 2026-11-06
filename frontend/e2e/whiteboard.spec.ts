import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { chooseJob, expect, test, type Page } from "./fixtures";

// Whiteboard practice against the real API: a diagram built with the keyboard only, one with the
// pointer, undo/redo, recovery after a reload, strict imports, feedback that names elements,
// a failed request that keeps everything, and phone-sized use.

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpCoder(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`wb-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "software-engineer");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function addComponent(page: Page, name: string, kind: string) {
  await page.getByLabel("New component").fill(name);
  await page.getByRole("combobox", { name: /^Kind(?! of)/ }).selectOption(kind);
  await page.getByLabel("New component").press("Enter");
}

const EXPLAIN = "I put a cache in front of the database because redirects outnumber new links a hundred to one, so most lookups never reach it.";

test("keyboard only: build, connect, undo, save, get feedback that names the elements", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await signUpCoder(page);
  await page.getByRole("navigation", { name: "More ways to practice" }).getByRole("link", { name: "Explain a design on a whiteboard" }).click();
  await page.getByRole("link", { name: "Design a URL shortener" }).click();
  await addComponent(page, "Browser", "client");
  await addComponent(page, "Shorten API", "service");
  await addComponent(page, "Redis cache", "cache");
  await addComponent(page, "URL database", "database");
  const connect = async (from: string, to: string, what: string) => {
    await page.getByRole("combobox", { name: /^From/ }).selectOption({ label: from });
    await page.getByRole("combobox", { name: /^To/ }).selectOption({ label: to });
    await page.getByLabel("What flows").fill(what);
    await page.getByLabel("What flows").press("Enter");
  };
  await connect("Browser", "Shorten API", "create / redirect");
  await connect("Shorten API", "Redis cache", "lookup");
  await connect("Shorten API", "URL database", "store mapping");
  await page.getByRole("button", { name: "Delete URL database" }).press("Enter");
  const outline = page.locator(".wb-outline");
  await expect(outline.getByText("Shorten API → URL database")).toHaveCount(0);
  await page.getByRole("button", { name: "Undo" }).press("Enter");
  await expect(outline.getByText("Shorten API → URL database")).toBeVisible();
  await page.getByLabel("Group of n2").fill("Read path");
  await page.getByLabel("Group of n3").fill("Read path");
  await expect(page.locator(".wb-group text")).toHaveText("Read path");
  await page.getByRole("group", { name: "Move Redis cache" }).getByRole("button", { name: "Down" }).press("Enter");
  await page.getByText("The diagram in words").click();
  await expect(page.locator(".wb-summary")).toContainText("Shorten API → Redis cache: lookup (e2)");
  await page.getByLabel("Capacity estimates").fill("About 100 new links per second and 10,000 redirects per second.");
  await page.getByLabel(/Explain one decision/).fill(EXPLAIN);
  await page.getByRole("button", { name: "Save draft" }).press("Enter");
  await expect(page.getByText("Saved to your account.")).toBeVisible();
  await axe(page, "whiteboard editor");

  await page.getByRole("button", { name: "Get feedback" }).press("Enter");
  const fb = page.getByRole("region", { name: /Feedback on the attempt/ });
  await expect(fb).toContainText("4 components in 1 group and 3 connections, all named and connected.");
  await expect(fb.locator(".wb-rubric li").filter({ hasText: "Handling far more reads than writes" })).toContainText("component n3");
  await expect(fb.locator(".wb-rubric li").filter({ hasText: "What happens when part of it fails" })).toContainText("Not found");
  await fb.locator(".wb-rubric li").filter({ hasText: "Handling far more reads" }).getByRole("button", { name: "Show on the diagram" }).click();
  await expect(page.locator('.wb-node--highlight[data-id="n3"]')).toBeVisible();
  await expect(fb).toContainText("never judges how the diagram looks");

  // Edit after the attempt: the feedback says it's about the version that was sent.
  await addComponent(page, "Read replica", "database");
  await expect(fb).toContainText("Your diagram has changed since this attempt");
});

test("pointer drag, recovery after a reload, strict imports, and a failed request that keeps the diagram", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await signUpCoder(page);
  await page.goto("/whiteboard/sd-rate-limiter");
  await addComponent(page, "Client", "client");
  await addComponent(page, "Gateway", "service");
  const node = page.locator('.wb-node[data-id="n1"]');
  const before = await node.getAttribute("transform");
  const box = (await node.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 160, { steps: 8 });
  await page.mouse.up();
  await expect(node).not.toHaveAttribute("transform", before!);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(node).toHaveAttribute("transform", before!);

  // Zoom changes the view, and fit brings everything back.
  const canvas = page.getByRole("img", { name: /Diagram with 2 components/ });
  const fitted = await canvas.getAttribute("viewBox");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.getByText("Zoom 125%")).toBeVisible();
  await expect(canvas).not.toHaveAttribute("viewBox", fitted!);
  await page.getByRole("button", { name: "Fit to content" }).click();
  await expect(canvas).toHaveAttribute("viewBox", fitted!);

  // A save that fails keeps everything on the page and says so.
  await page.route("**/api/v1/me/whiteboard/sd-rate-limiter/draft", (r) => (r.request().method() === "PUT" ? r.abort() : r.continue()));
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.locator(".inline-error")).toBeVisible();
  await expect(page.getByText("Unsaved changes, kept on this device")).toBeVisible();
  await page.unroute("**/api/v1/me/whiteboard/sd-rate-limiter/draft");

  // Not saved yet: a reload offers the copy kept on this device.
  await page.reload();
  await expect(page.getByText("You have unsaved changes to this diagram on this device.")).toBeVisible();
  await page.getByRole("button", { name: "Restore them" }).click();
  await expect(page.getByLabel("Name of n2")).toHaveValue("Gateway");

  // A file with anything unexpected is refused before it's loaded.
  const bad = join(tmpdir(), `bad-${Date.now()}.json`);
  writeFileSync(bad, JSON.stringify({ nodes: [{ id: "n1", label: "<script>x</script>", kind: "iframe", x: 0, y: 0 }], extra: true }));
  await page.getByLabel("Import a diagram file").setInputFiles(bad);
  await expect(page.locator(".inline-error")).toBeVisible();
  await expect(page.getByLabel("Name of n2")).toHaveValue("Gateway"); // nothing was replaced

  // Feedback fails on the network: everything stays.
  await page.getByLabel(/Explain one decision/).fill("I keep the counters in Redis because every server behind the load balancer has to see the same count for a client.");
  await page.route("**/api/v1/me/whiteboard/sd-rate-limiter/attempts", (r) => r.abort());
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.locator(".inline-error")).toBeVisible();
  await expect(page.getByLabel("Name of n1")).toHaveValue("Client");
  await page.unroute("**/api/v1/me/whiteboard/sd-rate-limiter/attempts");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: /Feedback on the attempt/ })).toBeVisible();

  // Export: a preview of exactly what the file holds, then a clearly named download.
  await page.getByRole("button", { name: "Export JSON…" }).click();
  await expect(page.getByLabel("What the file will contain")).toContainText('"label": "Gateway"');
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download codecoach-whiteboard-sd-rate-limiter.json" }).click()]);
  expect(download.suggestedFilename()).toBe("codecoach-whiteboard-sd-rate-limiter.json");
});

test("the whiteboard works in the dark theme, and someone else's attempt stays private", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "dark" })));
  await signUpCoder(page);
  await page.goto("/whiteboard/sd-url-shortener");
  await addComponent(page, "API", "service");
  await page.getByLabel(/Explain one decision/).fill(EXPLAIN);
  const sent = page.waitForResponse((r) => r.url().endsWith("/whiteboard/sd-url-shortener/attempts") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Get feedback" }).click();
  const { id } = (await (await sent).json()) as { id: string };
  await expect(page.getByRole("region", { name: /Feedback on the attempt/ })).toBeVisible();
  await axe(page, "whiteboard with feedback, dark");
  // Straight to the API: signed out gets 401, and another account gets 404 (not even "forbidden").
  const API = "http://localhost:8000";
  expect((await request.get(`${API}/api/v1/me/whiteboard/attempts/${id}`)).status()).toBe(401);
  const other = await request.post(`${API}/api/v1/auth/register`, { data: { email: `wb-other-${Date.now()}@example.com`, password: "CorrectHorse42" } });
  const { access_token } = (await other.json()) as { access_token: string };
  const peek = await request.get(`${API}/api/v1/me/whiteboard/attempts/${id}`, { headers: { Authorization: `Bearer ${access_token}` } });
  expect(peek.status()).toBe(404);
  const mine = await request.get(`${API}/api/v1/me/whiteboard/sd-url-shortener/draft`, { headers: { Authorization: `Bearer ${access_token}` } });
  expect(((await mine.json()) as { revision: number }).revision).toBe(0);
});

test("the whiteboard works at 320px in the light theme", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await signUpCoder(page);
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/whiteboard/sd-notifications");
  await addComponent(page, "Order service", "service");
  await addComponent(page, "Event queue", "queue");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "whiteboard at 320px, light");
});
