import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ScheduleEntry, ScheduleSettings } from "@/api/types";
import { browserTimeZone, todayIn } from "@/features/applications/dates";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));
const device = browserTimeZone();
const today = todayIn(device);

function entry(over: Partial<ScheduleEntry> = {}): ScheduleEntry {
  const start = new Date(Date.now() + 5 * 60_000);
  return {
    id: "e1", uid: "u1@codecoach", kind: "question", ref: "registered-nurse/m-pressure-0", title: "Patient assessment under pressure",
    href: "/careers/registered-nurse/questions/m-pressure-0", all_day: false, on_date: todayIn(device, start), local_time: "18:30", timezone: device,
    starts_at: start.toISOString(), ends_at: null, duration_min: 30, status: "scheduled", done_at: null, available: true, conflicts: [],
    sequence: 0, notes: "", created_at: new Date().toISOString(), follows_interview: false, ...over,
  };
}

function fake(settings: Partial<ScheduleSettings> = {}, entries: ScheduleEntry[] = []) {
  const state = { settings: { timezone: null, reminders: false, reminder_minutes: 10, quiet_start: null, quiet_end: null, ...settings } as ScheduleSettings, entries: [...entries] };
  const sent: { method: string; url: string; body: unknown }[] = [];
  server.use(
    http.get(`${API}/api/v1/me/schedule/settings`, () => HttpResponse.json(state.settings)),
    http.put(`${API}/api/v1/me/schedule/settings`, async ({ request }) => {
      const body = (await request.json()) as Partial<ScheduleSettings>;
      sent.push({ method: "PUT", url: request.url, body });
      state.settings = { ...state.settings, ...body };
      return HttpResponse.json(state.settings);
    }),
    http.get(`${API}/api/v1/me/schedule/schedulable`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/schedule/export.ics`, ({ request }) => {
      sent.push({ method: "GET", url: request.url, body: null });
      return new HttpResponse("BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n", { headers: { "Content-Type": "text/calendar" } });
    }),
    http.get(`${API}/api/v1/me/schedule`, () => HttpResponse.json(state.entries)),
    http.post(`${API}/api/v1/me/schedule`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      sent.push({ method: "POST", url: request.url, body });
      if (body.local_time === "01:30" && body.fold === null) {
        return HttpResponse.json({ error: { code: "ambiguous_time", message: "01:30 happens twice in America/Chicago on 2026-11-01 (the clocks go back). Say which one you mean.", request_id: "r", details: { first_offset: "-0500", second_offset: "-0600" } } }, { status: 400 });
      }
      const e = entry({ id: `e${state.entries.length + 1}`, on_date: String(body.on_date), all_day: Boolean(body.all_day) });
      state.entries.push(e);
      return HttpResponse.json(e, { status: 201 });
    }),
  );
  return { sent, state };
}

describe("the schedule", () => {
  it("schedules an activity from its page, with the time zone shown and a single entry per click", async () => {
    asUser();
    const { sent } = fake();
    const { user } = renderApp("/schedule?kind=question&ref=registered-nurse%2Fm-pressure-0&title=Patient%20assessment%20under%20pressure", { signedIn: true });
    expect(await screen.findByText(/uses this device's time zone/)).toBeInTheDocument();
    expect(screen.getByLabelText("What")).toHaveValue("question|registered-nurse/m-pressure-0");
    await user.click(screen.getByRole("button", { name: "Add to schedule" }));
    expect(await screen.findByText(/Added “Patient assessment under pressure”/)).toBeInTheDocument();
    const post = sent.find((r) => r.method === "POST")!.body as Record<string, unknown>;
    expect(post).toMatchObject({ kind: "question", ref: "registered-nurse/m-pressure-0", on_date: today, all_day: false, local_time: "18:00", timezone: device, duration_min: 30 });
    expect(typeof post.client_request_id).toBe("string");
  });

  it("asks which one when a time happens twice", async () => {
    asUser();
    const { sent } = fake({ timezone: "America/Chicago" });
    const { user } = renderApp("/schedule?kind=question&ref=registered-nurse%2Fm-pressure-0&title=Q", { signedIn: true });
    const form = await screen.findByRole("form", { name: "Add to schedule" });
    await user.clear(within(form).getByLabelText("Start time"));
    await user.type(within(form).getByLabelText("Start time"), "01:30");
    await user.click(within(form).getByRole("button", { name: "Add to schedule" }));
    expect(await within(form).findByText(/happens twice/)).toBeInTheDocument();
    await user.click(within(form).getByLabelText(/The first one \(UTC-05:00\)/));
    await user.click(within(form).getByRole("button", { name: "Add to schedule" }));
    await waitFor(() => expect(sent.filter((r) => r.method === "POST").at(-1)!.body).toMatchObject({ fold: 0, local_time: "01:30" }));
  });

  it("explains overlaps without moving anything, and downloads the week as a calendar file", async () => {
    asUser();
    const a = entry({ id: "a", title: "Mock interview prep", conflicts: ["b"] });
    const b = entry({ id: "b", title: "Two Sum", kind: "problem", conflicts: ["a"] });
    const { sent } = fake({}, [a, b]);
    const createUrl = vi.fn(() => "blob:x");
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() });
    const { user } = renderApp("/schedule", { signedIn: true });
    expect(await screen.findByText(/Overlaps with Two Sum\. Nothing was moved/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Download this week (.ics)" }));
    await waitFor(() => expect(sent.some((r) => r.url.includes("/export.ics?from=") && r.url.includes("&to="))).toBe(true));
    expect(createUrl).toHaveBeenCalled();
    expect(screen.getByText(/may not reach it/)).toBeInTheDocument();
  });

  it("says when the device is in another time zone, and keeps entries where they are", async () => {
    asUser();
    const { sent } = fake({ timezone: device === "Asia/Tokyo" ? "Europe/London" : "Asia/Tokyo" });
    const { user } = renderApp("/schedule", { signedIn: true });
    expect(await screen.findByText(/Timed entries stay at the same moment wherever you are/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: new RegExp(`Show times in ${device.replace(/_/g, " ")}`) }));
    await waitFor(() => expect(sent.find((r) => r.method === "PUT")?.body).toEqual({ timezone: device }));
  });
});

describe("reminders", () => {
  it("appear in the app only when turned on, and can be dismissed", async () => {
    asUser();
    fake({ timezone: device, reminders: true, reminder_minutes: 10 }, [entry()]);
    const { user } = renderApp("/dashboard", { signedIn: true });
    const reminder = await screen.findByText(/In [45] minutes:/);
    expect(reminder.closest(".reminder")).toHaveTextContent("Patient assessment under pressure");
    await user.click(within(reminder.closest(".reminder") as HTMLElement).getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(screen.queryByText(/In [45] minutes:/)).toBeNull());
  });

  it("stay silent when off, or when the activity is already done", async () => {
    asUser();
    fake({ timezone: device, reminders: false }, [entry()]);
    const { unmount } = renderApp("/dashboard", { signedIn: true });
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/minutes:/)).toBeNull();
    unmount();
    fake({ timezone: device, reminders: true }, [entry({ done_at: new Date().toISOString() })]);
    renderApp("/dashboard", { signedIn: true });
    await screen.findByRole("heading", { level: 1 });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText(/minutes:/)).toBeNull();
  });

  it("interview preparation is a fixed time unless the learner keeps it relative to the interview", async () => {
    let body: unknown = null;
    const prep = entry({ id: "p1", kind: "application_event", ref: "e1", title: "Prepare: Panel interview (Mercy General)", href: "/applications/a1/events/e1/kit", sequence: 3 });
    asUser();
    fake({}, [prep]);
    server.use(
      http.put(`${API}/api/v1/me/schedule/p1/follows-interview`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...prep, follows_interview: true });
      }),
    );
    const { user } = renderApp("/schedule", { signedIn: true });
    expect(await screen.findByText(/A fixed time: it stays here if the interview moves/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep it relative to the interview" }));
    await waitFor(() => expect(body).toEqual({ follows: true, expected_sequence: 3 }));
  });
});

