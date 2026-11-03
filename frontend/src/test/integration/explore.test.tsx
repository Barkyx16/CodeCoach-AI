import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { store } from "../explore";
import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const rows = () => within(screen.getByRole("region", { name: "Question list" })).getAllByRole("listitem");

describe("Question explorer", () => {
  it("filters by format with counts, explains the filters, and removes them from chips", async () => {
    asNurse();
    const { user, router } = renderApp("/problems", { signedIn: true });
    const format = await screen.findByLabelText("Format");
    await within(format).findByRole("option", { name: "Behavioral (1)" });
    await user.selectOptions(format, "behavioral");
    await waitFor(() => expect(router.state.location.search).toContain("kind=behavioral"));
    await waitFor(() => expect(rows()).toHaveLength(1));
    expect(screen.getByText("A time patient assessment mattered")).toBeInTheDocument();
    expect(await screen.findByText("1 question · Difficulty: Easy · Format: Behavioral · Sorted by library order")).toHaveAttribute("role", "status");
    // Tab counts follow the other filters: no behavioral questions are easy except the one shown.
    const tabs = screen.getByRole("tablist", { name: "Difficulty" });
    expect(within(tabs).getByRole("tab", { name: "Medium 1" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove Format: Behavioral" }));
    await waitFor(() => expect(router.state.location.search).not.toContain("kind="));
    await waitFor(() => expect(rows()).toHaveLength(2));
  });

  it("restores every filter from the URL, and Back undoes a filter change", async () => {
    asNurse();
    const { user, router } = renderApp("/problems?difficulty=medium&skill=Judgment+under+pressure", { signedIn: true });
    expect(await screen.findByText("Patient assessment under pressure")).toBeInTheDocument();
    expect(screen.getByLabelText("Skill")).toHaveValue("Judgment under pressure");
    expect(screen.getByRole("button", { name: "Remove Skill: Judgment under pressure" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Your practice"), "attempted");
    await waitFor(() => expect(router.state.location.search).toContain("status=attempted"));
    expect(await screen.findByText("No medium questions match")).toBeInTheDocument();
    await router.navigate(-1);
    await waitFor(() => expect(router.state.location.search).not.toContain("status="));
    expect(await screen.findByText("Patient assessment under pressure")).toBeInTheDocument();
  });

  it("explains an empty result and offers ways to widen it", async () => {
    asNurse();
    const { user } = renderApp("/problems?q=zzz+quantum", { signedIn: true });
    expect(await screen.findByText("No easy questions match")).toBeInTheDocument();
    expect(screen.getByText(/Try fewer or more general words\./)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() => expect(rows()).toHaveLength(2));
  });

  it("bookmarks optimistically, rolls back with a recoverable error when saving fails", async () => {
    asNurse();
    store.failBookmarks = true;
    const { user } = renderApp("/problems", { signedIn: true });
    const toggle = await screen.findByRole("button", { name: "Bookmark “A time patient assessment mattered”" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Couldn't bookmark “A time patient assessment mattered”. Nothing was changed.");
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "false"));
    store.failBookmarks = false;
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Bookmark “A time patient assessment mattered”" })).toHaveAttribute("aria-pressed", "true"));
    expect(store.bookmarks.map((b) => b.ref_id)).toEqual(["e-time-0"]);
    // The bookmark filter now finds it.
    await user.selectOptions(screen.getByLabelText("Your practice"), "bookmarked");
    await waitFor(() => expect(rows()).toHaveLength(1));
  });

  it("signed-out visitors browse without personal filters or bookmarks, and are told why", async () => {
    renderApp("/problems?career=registered-nurse&status=bookmarked");
    expect(await screen.findByText("A time patient assessment mattered")).toBeInTheDocument();
    expect(rows()).toHaveLength(2); // a personal filter in the URL is ignored, not an error
    expect(screen.queryByLabelText("Your practice")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Bookmark/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Sign in to filter by what you've answered or bookmarked/)).toBeInTheDocument();
    expect(screen.getByText(/Time estimates aren't shown/)).toBeInTheDocument();
  });
});

describe("Collections and the practice queue", () => {
  it("adds a question to a new collection from its page and refuses a duplicate", async () => {
    asNurse();
    const { user } = renderApp("/careers/registered-nurse/questions/e-time-0", { signedIn: true });
    const save = await screen.findByRole("region", { name: "Save for later" });
    await within(save).findByRole("option", { name: "New collection…" });
    await user.type(within(save).getByLabelText("New collection name"), "Night shift prep");
    await user.click(within(save).getByRole("button", { name: "Add" }));
    expect(await within(save).findByText("Added to “Night shift prep”.")).toBeInTheDocument();
    expect(await within(save).findByRole("option", { name: "Night shift prep (already added)" })).toBeDisabled();
    expect(within(save).getByRole("link", { name: "Night shift prep" })).toHaveAttribute("href", "/saved/collections/c-1");
    await user.click(within(save).getByRole("button", { name: "Bookmark" }));
    await waitFor(() => expect(within(save).getByRole("button", { name: "Bookmarked" })).toHaveAttribute("aria-pressed", "true"));
  });

  it("reorders with buttons (focus stays on the moved item), renames and deletes after confirming", async () => {
    asNurse();
    const { user, router } = renderApp("/saved", { signedIn: true });
    await user.type(await screen.findByLabelText("New collection"), "Week 1");
    await user.click(screen.getByRole("button", { name: "Create collection" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/saved/collections/c-1"));
    expect(await screen.findByText("This collection is empty")).toBeInTheDocument();
    for (const id of ["e-good-0", "e-time-0", "m-pressure-0"]) {
      await fetch(`${API}/api/v1/me/collections/c-1/items`, { method: "POST", body: JSON.stringify({ item_type: "question", track: "registered-nurse", ref_id: id }) });
    }
    await router.navigate("/saved");
    await user.click(await screen.findByRole("link", { name: "Week 1" }));
    const list = await screen.findByRole("list", { name: "Items in order" });
    const down = within(list).getByRole("button", { name: "Move “What good patient assessment looks like” down" });
    down.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(within(list).getAllByRole("listitem")[1]).toHaveTextContent("What good patient assessment looks like"));
    await waitFor(() => expect(within(list).getByRole("button", { name: "Move “What good patient assessment looks like” down" })).toHaveFocus());
    expect(screen.getByText("Moved “What good patient assessment looks like” to position 2 of 3.")).toBeInTheDocument();
    expect(store.collections[0]!.item_list.map((i) => i.ref_id)).toEqual(["e-time-0", "e-good-0", "m-pressure-0"]);

    await user.click(screen.getByRole("button", { name: "Rename" }));
    const name = screen.getByLabelText("Collection name");
    await user.clear(name);
    await user.type(name, "Week 1: assessment");
    await user.click(screen.getByRole("button", { name: "Save name" }));
    expect(await screen.findByRole("heading", { name: "Week 1: assessment" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("alertdialog", { name: "Delete “Week 1: assessment”?" });
    expect(dialog).toHaveTextContent("The questions, your answers and your bookmarks stay.");
    await user.click(within(dialog).getByRole("button", { name: "Delete collection" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/saved"));
    expect(await screen.findByText(/No collections yet/)).toBeInTheDocument();
  });

  it("practices a collection in order; done marks are separate from mastery", async () => {
    asNurse();
    for (const id of ["e-good-0", "e-time-0"]) {
      if (!store.collections.length) await fetch(`${API}/api/v1/me/collections`, { method: "POST", body: JSON.stringify({ name: "Queue" }) });
      await fetch(`${API}/api/v1/me/collections/c-1/items`, { method: "POST", body: JSON.stringify({ item_type: "question", track: "registered-nurse", ref_id: id }) });
    }
    const { user, router } = renderApp("/saved/collections/c-1", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Start this collection" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/saved/collections/c-1/practice"));
    expect(await screen.findByText("Item 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Queue progress" })).toHaveTextContent("“Done” only moves this queue along; your scores and mastery come from your answers.");
    await user.click(screen.getByRole("link", { name: "Answer this question" }));
    await waitFor(() => expect(router.state.location.search).toBe("?queue=c-1"));
    const bar = await screen.findByRole("region", { name: "Practice queue" });
    expect(bar).toHaveTextContent("Queue · item 1 of 2");
    await user.click(within(bar).getByRole("button", { name: "Mark done and go to next" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/careers/registered-nurse/questions/e-time-0"));
    expect(await screen.findByRole("region", { name: "Practice queue" })).toHaveTextContent("item 2 of 2");
    expect(store.collections[0]!.item_list[0]!.queue_done).toBe(true);
    expect(store.collections[0]!.queue_position).toBe(1);
  });

  it("shows a retired item as unavailable with a way to remove it, never a substitute", async () => {
    asNurse();
    await fetch(`${API}/api/v1/me/collections`, { method: "POST", body: JSON.stringify({ name: "Old" }) });
    await fetch(`${API}/api/v1/me/collections/c-1/items`, { method: "POST", body: JSON.stringify({ item_type: "question", track: "registered-nurse", ref_id: "e-good-0" }) });
    Object.assign(store.collections[0]!.item_list[0]!, {
      ref_id: "retired-1", title: "A question that's no longer in the library", href: null, available: false,
      unavailable_reason: "This question was retired or removed from the library. Your saved spot is kept until you remove it.",
    });
    const { user } = renderApp("/saved/collections/c-1", { signedIn: true });
    expect(await screen.findByText(/This question was retired or removed from the library\. .* Nothing was swapped in for it\./)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "A question that's no longer in the library" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove “A question that's no longer in the library” from this collection" }));
    expect(await screen.findByText("This collection is empty")).toBeInTheDocument();
  });
});
