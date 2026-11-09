/**
 * Field errors that guide the next action (Volume 9, prompt 3; NAVIGATION.md "Field errors").
 * A refused save's validation errors go beside the fields they name (aria-invalid, linked with
 * aria-describedby), with a summary that takes focus on the longer forms. An error is shown only
 * while its field still holds the value that was refused; a refusal that arrives after the learner
 * carried on typing doesn't pull focus. A retry sends what the form holds now. Anything that isn't
 * a validation error (offline, not allowed) is shown as before, never as a field error.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { ApiError } from "@/api/client";
import type { Application, GoalsInput, Target } from "@/api/types";
import { readable, validationMessages } from "@/hooks/useFieldErrors";

import { nurseGoals, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const now = new Date().toISOString();
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const refused = (details: { loc: (string | number)[]; msg: string; type: string }[]) =>
  HttpResponse.json({ error: { code: "validation_error", message: "Request validation failed", request_id: "r-1", details } }, { status: 422 });
const describedBy = (el: HTMLElement) => (el.getAttribute("aria-describedby") ?? "").split(" ").map((id) => document.getElementById(id)?.textContent ?? "");

afterEach(() => localStorage.clear());

describe("the wording", () => {
  it("says what's wrong and how to fix it for the common refusals, and keeps the server's own words otherwise", () => {
    expect(readable("missing", "Field required")).toBe("This is required: fill it in.");
    expect(readable("string_too_short", "String should have at least 1 character")).toBe("This can't be empty: fill it in.");
    expect(readable("string_too_long", "String should have at most 2000 characters")).toBe("Too long: use at most 2,000 characters.");
    expect(readable("too_long", "List should have at most 8 items after validation, not 9")).toBe("Too many: choose at most 8.");
    expect(readable("date_from_datetime_parsing", "Input should be a valid date or datetime, invalid character in year")).toBe("Not a date: choose a day, or leave it empty.");
    expect(readable("literal_error", "Input should be 'new', 'early', 'mid' or 'senior'")).toBe("Not one of the choices: choose one from the list.");
    expect(readable("value_error", "Value error, Links must start with https:// or http:// (they're never opened by CodeCoach).")).toBe("Links must start with https:// or http:// (they're never opened by CodeCoach).");
    expect(readable("value_error", "Value error, must not be blank")).toBe("Must not be blank.");
  });

  it("ties each error to the form's own field, keeps the first per field, and leaves the rest for the form's message", () => {
    const error = new ApiError(422, "validation_error", "Request validation failed", [
      { loc: ["body", "title"], msg: "String should have at most 120 characters", type: "string_too_long" },
      { loc: ["body", "title"], msg: "Second", type: "value_error" },
      { loc: ["body", "confidence", "triage"], msg: "Input should be less than or equal to 5", type: "less_than_equal" },
      { loc: ["body"], msg: "Value error, the dates are in the wrong order", type: "value_error" },
    ]);
    expect(validationMessages(error, ["title", "confidence"] as const)).toEqual({
      byField: { title: "Too long: use at most 120 characters.", confidence: "Input should be less than or equal to 5." },
      other: ["The dates are in the wrong order."],
    });
    // Anything else isn't a field error.
    expect(validationMessages(new ApiError(403, "forbidden", "Not allowed"), ["title"] as const)).toBeNull();
    expect(validationMessages(new ApiError(0, "network_error", "Offline"), ["title"] as const)).toBeNull();
    expect(validationMessages(new Error("x"), ["title"] as const)).toBeNull();
  });
});

describe("goals", () => {
  it("a refused save shows each error beside its field and a summary that takes focus; fixing a field clears its error; a retry sends what the form holds now", async () => {
    asNurse();
    const sent: GoalsInput[] = [];
    server.use(
      http.get(`${API}/api/v1/me/goals`, () => HttpResponse.json(nurseGoals)),
      http.put(`${API}/api/v1/me/goals`, async ({ request }) => {
        const body = (await request.json()) as GoalsInput;
        sent.push(body);
        if (sent.length === 1) {
          return refused([
            { loc: ["body", "specialty"], msg: "String should have at most 120 characters", type: "string_too_long" },
            { loc: ["body", "target_date"], msg: "Input should be a valid date or datetime, invalid character in year", type: "date_from_datetime_parsing" },
            { loc: ["body", "track"], msg: "Value error, that job isn't available any more", type: "value_error" },
          ]);
        }
        return HttpResponse.json({ ...nurseGoals, ...body, saved: true });
      }),
    );
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { user, router } = renderApp("/plan/goals", { signedIn: true });
    const specialty = await screen.findByLabelText(/Specialty or focus/);
    await user.type(specialty, "Urgências"); // not only ASCII
    await user.click(screen.getByRole("button", { name: "Save goals" }));

    const summary = await screen.findByRole("group", { name: /This wasn't saved\. Check 2 fields:/ });
    await waitFor(() => expect(summary).toHaveFocus());
    expect(within(summary).getByRole("link", { name: "Specialty or focus" }).closest("li")).toHaveTextContent("Specialty or focus: Too long: use at most 120 characters.");
    expect(within(summary).getByRole("link", { name: "Interview date" }).closest("li")).toHaveTextContent("Interview date: Not a date: choose a day, or leave it empty.");
    expect(summary).toHaveTextContent("That job isn't available any more."); // not tied to a field: in the summary
    expect(specialty).toHaveAttribute("aria-invalid", "true");
    expect(describedBy(specialty)).toContain("Too long: use at most 120 characters.");
    // The error is the field's description, not part of its name (read once, after the name).
    expect(specialty).toHaveAccessibleName("Specialty or focus (optional)");
    expect(specialty).toHaveAccessibleDescription("Too long: use at most 120 characters.");
    const date = screen.getByLabelText(/Interview date/);
    expect(date).toHaveAttribute("aria-invalid", "true");
    expect(specialty).toHaveValue("Urgências"); // nothing typed is lost
    expect(screen.queryByText("Request validation failed")).not.toBeInTheDocument(); // no second, vaguer message
    expect(router.state.location.pathname).toBe("/plan/goals");
    expect(screen.getByText("Unsaved changes, kept on this device.")).toBeInTheDocument(); // still unsaved, still kept
    await user.click(screen.getByRole("link", { name: "CodeCoach AI home" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/Your changes to your goals aren't saved/)); // and leaving still asks
    expect(router.state.location.pathname).toBe("/plan/goals");
    confirm.mockClear();

    // Keyboard: a summary link puts focus in its field.
    within(summary).getByRole("link", { name: "Specialty or focus" }).focus();
    await user.keyboard("{Enter}");
    expect(specialty).toHaveFocus();
    await user.type(specialty, " pediátricas");
    expect(specialty).not.toHaveAttribute("aria-invalid");
    expect(specialty).toHaveFocus(); // the error clearing doesn't move focus
    expect(describedBy(specialty).join(" ")).not.toContain("Too long");
    expect(screen.getByRole("group", { name: /Check 1 field:/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save goals" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/dashboard"));
    expect(sent).toHaveLength(2);
    expect(sent[1]!.specialty).toBe("Urgências pediátricas"); // the current value, not the refused one
    expect(confirm).not.toHaveBeenCalled(); // the accepted save moves on without asking
    confirm.mockRestore();
  });

  it("a summary link to a group of choices puts focus on its first choice", async () => {
    asNurse();
    server.use(
      http.get(`${API}/api/v1/me/goals`, () => HttpResponse.json(nurseGoals)),
      http.put(`${API}/api/v1/me/goals`, () => refused([
        { loc: ["body", "focus_areas"], msg: "List should have at most 8 items after validation, not 9", type: "too_long" },
      ])),
    );
    const { user } = renderApp("/plan/goals", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Save goals" }));
    const summary = await screen.findByRole("group", { name: /Check 1 field:/ });
    expect(summary).toHaveTextContent("Where you want help: Too many: choose at most 8.");
    const group = screen.getByRole("group", { name: /Where do you want help/ });
    expect(describedBy(group)).toContain("Too many: choose at most 8.");
    within(summary).getByRole("link", { name: "Where you want help" }).focus();
    await user.keyboard("{Enter}");
    expect(within(group).getAllByRole("checkbox")[0]).toHaveFocus();
  });
});

describe("a new target job", () => {
  function targetsServer(create: (body: Record<string, unknown>) => Promise<Response> | Response) {
    server.use(
      http.get(`${API}/api/v1/targets`, () => HttpResponse.json([])),
      http.post(`${API}/api/v1/targets`, async ({ request }) => create((await request.json()) as Record<string, unknown>)),
    );
  }

  it("a refusal that arrives after the learner carried on typing: the edited field shows no old error, focus stays where they type, the untouched field's error is shown", async () => {
    asNurse();
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    const bodies: Record<string, unknown>[] = [];
    targetsServer(async (body) => {
      bodies.push(body);
      if (bodies.length === 1) {
        await held;
        return refused([
          { loc: ["body", "title"], msg: "Value error, must not be blank", type: "value_error" },
          { loc: ["body", "notes"], msg: "String should have at most 2000 characters", type: "string_too_long" },
        ]);
      }
      return HttpResponse.json({ id: "t-9" }, { status: 201 });
    });
    const { user } = renderApp("/targets", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Add a target role" }));
    const title = screen.getByLabelText(/Role title/);
    await user.type(title, "ED Nurse");
    await user.type(screen.getByLabelText("Job description"), "Triage incoming patients");
    await user.type(screen.getByLabelText(/Notes about the interview/), "Panel of three");
    await user.click(screen.getByRole("button", { name: "Find requirements" }));
    await user.type(title, " (nights)"); // carries on while the save is on its way
    release();

    const summary = await screen.findByRole("group", { name: /Check 1 field:/ });
    expect(summary).toHaveTextContent("Notes about the interview: Too long: use at most 2,000 characters.");
    expect(summary).not.toHaveTextContent("Role title");
    expect(title).not.toHaveAttribute("aria-invalid");
    expect(screen.getByLabelText(/Notes about the interview/)).toHaveAttribute("aria-invalid", "true");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(title).toHaveFocus(); // not pulled out of the field they're typing in
    expect(title).toHaveValue("ED Nurse (nights)"); // the edit made during the save survives
    expect(screen.getByLabelText("Job description")).toHaveValue("Triage incoming patients");
  });

  it("offline or not allowed is shown as before: no field is marked, no summary", async () => {
    asNurse();
    let reply: () => Response = () => HttpResponse.json({ error: { code: "forbidden", message: "You can't add a target job here.", request_id: "r" } }, { status: 403 });
    targetsServer(() => reply());
    const { user } = renderApp("/targets", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Add a target role" }));
    await user.type(screen.getByLabelText(/Role title/), "ED Nurse");
    await user.type(screen.getByLabelText("Job description"), "Triage incoming patients");
    await user.click(screen.getByRole("button", { name: "Find requirements" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You can't add a target job here.");
    expect(screen.queryByRole("group", { name: /This wasn't saved/ })).not.toBeInTheDocument();
    expect(document.querySelectorAll("[aria-invalid='true']")).toHaveLength(0);

    reply = () => HttpResponse.error(); // the connection drops
    await user.click(screen.getByRole("button", { name: "Find requirements" }));
    await waitFor(() => expect(screen.getByRole("alert")).not.toHaveTextContent("You can't add a target job here."));
    expect(screen.queryByRole("group", { name: /This wasn't saved/ })).not.toBeInTheDocument();
    expect(document.querySelectorAll("[aria-invalid='true']")).toHaveLength(0);
  });
});

describe("the job posting editor", () => {
  it("a refused posting edit shows its errors in the editor, which stays open with the text", async () => {
    asNurse();
    const round = { track: "registered-nurse", question_ids: ["e-good-0"], duration_minutes: 10, purpose: "practice", difficulty: null };
    const t = {
      id: "t-1", title: "ED Nurse", employer: "Mercy General", track: "registered-nurse", career_title: "Registered Nurse",
      interview_date: null, archived: false, selected: true, requirements: 0, gaps: 0, created_at: now, updated_at: now,
      description: "Responsibilities:\n- Triage", notes: null, extractor: "rule-based (no AI)", requirement_list: [],
      next_activity: { kind: "question", title: "Q", href: "/careers/registered-nurse/questions/e-good-0", why: "Why.", answered: false, best_score: null },
      targeted_session: { title: "Short", scope: "1.", round }, mock_interview: { title: "Mock", scope: "1.", round },
      recent_attempts: [], experience: [], days_to_interview: null,
    } as Target;
    server.use(
      http.get(`${API}/api/v1/targets`, () => HttpResponse.json([])),
      http.get(`${API}/api/v1/targets/t-1`, () => HttpResponse.json(t)),
      http.patch(`${API}/api/v1/targets/t-1`, () => refused([
        { loc: ["body", "interview_date"], msg: "Input should be a valid date", type: "date_parsing" },
      ])),
    );
    const { user } = renderApp("/targets/t-1", { signedIn: true });
    const card = (await screen.findByRole("heading", { name: "The posting" })).closest(".card") as HTMLElement;
    await user.click(within(card).getByRole("button", { name: "Edit" }));
    await user.click(within(card).getByLabelText("Job description"));
    await user.keyboard("{Control>}{End}{/Control}");
    await user.paste("\n- Noches de fin de semana\n- Nuits"); // pasted, several lines
    await user.click(within(card).getByRole("button", { name: "Save" }));
    const summary = await within(card).findByRole("group", { name: /Check 1 field:/ });
    await waitFor(() => expect(summary).toHaveFocus());
    expect(summary).toHaveTextContent("Interview date: Not a date: choose a day, or leave it empty.");
    expect(within(card).getByLabelText("Interview date")).toHaveAttribute("aria-invalid", "true");
    expect(within(card).getByLabelText("Job description")).toHaveValue("Responsibilities:\n- Triage\n- Noches de fin de semana\n- Nuits");
  });
});

describe("an application's details", () => {
  it("a link only the server checks: the error goes beside the link and focus into it; a corrected link is what's sent next", async () => {
    asNurse();
    const app: Application = {
      id: "a1", employer: "Mercy General", role_title: "Ward nurse", stage: "applied", applied_on: null, next_action: "Call",
      next_action_due: null, target: null, archived: false, next_event: null, updated_at: now, link: null, notes: "",
      notes_revision: 1, stories: [], events: [], history: [], created_at: now,
    };
    let current = app;
    const bodies: Partial<Application>[] = [];
    server.use(
      http.get(`${API}/api/v1/me/applications/:id`, () => HttpResponse.json(current)),
      http.patch(`${API}/api/v1/me/applications/:id`, async ({ request }) => {
        const body = (await request.json()) as Partial<Application>;
        bodies.push(body);
        if (!String(body.link ?? "").startsWith("http")) {
          return refused([{ loc: ["body", "link"], msg: "Value error, Links must start with https:// or http:// (they're never opened by CodeCoach).", type: "value_error" }]);
        }
        current = { ...current, ...body, updated_at: new Date().toISOString() } as Application;
        return HttpResponse.json(current);
      }),
    );
    const { user } = renderApp("/applications/a1", { signedIn: true });
    const link = await screen.findByLabelText("Link to the posting");
    // A real URL, so the browser's own check lets it through; only the server says no.
    await user.type(link, "ftp://mercy.example/jobs/1");
    await user.click(screen.getByRole("button", { name: "Save details" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    await waitFor(() => expect(link).toHaveAttribute("aria-invalid", "true"));
    expect(describedBy(link)).toContain("Links must start with https:// or http:// (they're never opened by CodeCoach).");
    await waitFor(() => expect(link).toHaveFocus());
    expect(screen.queryByText("Request validation failed")).not.toBeInTheDocument();
    expect(screen.queryByText("Saved.")).not.toBeInTheDocument();

    await user.clear(link);
    await user.type(link, "https://mercy.example/jobs/1");
    expect(link).not.toHaveAttribute("aria-invalid");
    await user.click(screen.getByRole("button", { name: "Save details" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(bodies.at(-1)?.link).toBe("https://mercy.example/jobs/1");
  });
});
