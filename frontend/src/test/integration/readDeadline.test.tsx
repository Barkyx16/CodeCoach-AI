/**
 * A read that never answers (Volume 9, prompt 9; NAVIGATION.md "The 63-second stall"): every GET
 * has a deadline, after which it's a temporary failure ("read_timeout") with Try again, so a page
 * never loads forever. Writes have none (their outcome would be unknown; Volume 8 handles those).
 * A caller's own cancel stays a cancel. A stalled side read never costs the learner their work.
 */
import { act, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { ApiError, apiRequest, setReadDeadlineForTests } from "@/api/client";

import { makeNote, noteStore } from "../notes";
import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const never = () => new Promise<Response>(() => {});

beforeEach(() => setReadDeadlineForTests(150));
afterEach(() => setReadDeadlineForTests(null));

describe("the client", () => {
  it("gives up a read that never answers as a temporary failure", async () => {
    server.use(http.get(`${API}/api/v1/topics`, never));
    const error = await apiRequest("/api/v1/topics", { auth: false }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("read_timeout");
    expect((error as ApiError).status).toBe(0);
  });

  it("also when the answer starts but its body never finishes", async () => {
    // A browser's fetch: the headers arrive at once, the body stalls, and aborting the request's
    // signal errors the body. (MSW holds a response until its body is complete, so it can't show this.)
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
      const signal = (init as RequestInit | undefined)?.signal;
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode("[{"));
          signal?.addEventListener("abort", () => controller.error(new DOMException("The operation was aborted.", "AbortError")));
        },
      });
      return new Response(body, { status: 200, headers: { "Content-Type": "application/json" } });
    });
    try {
      const error = await apiRequest("/api/v1/topics", { auth: false }).catch((e: unknown) => e);
      expect((error as ApiError).code).toBe("read_timeout");
    } finally {
      spy.mockRestore();
    }
  });

  it("never gives up a write: its outcome would be unknown", async () => {
    server.use(http.post(`${API}/api/v1/telemetry`, never));
    let settled = false;
    void apiRequest("/api/v1/telemetry", { method: "POST", body: {}, auth: false }).then(() => { settled = true; }, () => { settled = true; });
    await new Promise((resolve) => setTimeout(resolve, 500)); // over three deadlines
    expect(settled).toBe(false);
  });

  it("a caller's own cancel stays a cancel, not a timeout", async () => {
    server.use(http.get(`${API}/api/v1/topics`, never));
    const controller = new AbortController();
    const pending = apiRequest("/api/v1/topics", { auth: false, signal: controller.signal }).catch((e: unknown) => e);
    controller.abort();
    const error = await pending;
    expect(error).not.toBeInstanceOf(ApiError);
    expect((error as Error).name).toBe("AbortError"); // a DOMException, from whichever realm aborted it
  });

  it("a read that answers in time is untouched", async () => {
    server.use(http.get(`${API}/api/v1/topics`, () => HttpResponse.json([{ slug: "arrays", count: 3 }])));
    await expect(apiRequest("/api/v1/topics", { auth: false })).resolves.toEqual([{ slug: "arrays", count: 3 }]);
  });
});

describe("on a page", () => {
  it("a note whose read never answers: an error with Try again (after one retry), and Try again loads it", async () => {
    asNurse();
    const note = makeNote({ title: "Shift handover", body: "SBAR first." });
    noteStore.notes.push(note);
    let hang = true;
    server.use(http.get(`${API}/api/v1/me/notes/:id`, async () => { if (hang) await never(); }));
    const { user } = renderApp(`/notes/${note.id}`, { signedIn: true });
    expect(await screen.findByText("The server is taking too long", {}, { timeout: 4000 })).toBeInTheDocument();
    hang = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByDisplayValue("Shift handover")).toBeInTheDocument());
  });

  it("a side read that stalls costs nothing: the answer being written stays, and can still be sent", async () => {
    asNurse();
    server.use(http.get(`${API}/api/v1/me/notes`, never));
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    const box = await screen.findByLabelText("Your answer");
    await user.type(box, "I checked the airway first.");
    await new Promise((resolve) => setTimeout(resolve, 600)); // the notes read has run out of time, twice
    expect(box).toHaveValue("I checked the airway first.");
    expect(screen.getByRole("button", { name: "Get feedback" })).toBeEnabled();
  });

  it("leaving a page while its read hangs: the next page shows no error from it", async () => {
    asNurse();
    const note = makeNote({ title: "Shift handover" });
    noteStore.notes.push(note);
    server.use(http.get(`${API}/api/v1/me/notes/:id`, never));
    const { router } = renderApp(`/notes/${note.id}`, { signedIn: true });
    await act(() => router.navigate("/notes"));
    expect(await screen.findByRole("heading", { name: "Your notes" })).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(screen.queryByText("The server is taking too long")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });
});
