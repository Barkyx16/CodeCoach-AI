/**
 * What's new: the curated entries (Volume 11, prompt 10; docs/WHATS_NEW.md). Each one is a change
 * that is in the app as built, written for the learner: what got better, where to find it, and what
 * it doesn't do. An entry is shown only when its `release` is at most the build's (release.json),
 * so an entry written ahead of its release stays hidden until the build that ships it. Drafts and
 * plans aren't kept here at all (docs/WHATS_NEW.md, "Drafts").
 *
 * Plain text only: no markup, no URLs. An entry opens a page through `opens`, a command id from the
 * command palette (app/commands.ts), so the link is one of the router's real pages with the same
 * career and server rules; an entry whose page isn't offered to this learner shows why instead.
 */

export interface ReleaseEntry {
  /** Stable id: lowercase letters, digits and dashes. */
  id: string;
  /** The release it shipped in (release.json's number at the time). */
  release: number;
  title: string;
  /** The concrete improvement, in the learner's words. */
  what: string;
  /** Where to find it. */
  where: string;
  /** A command id (app/commands.ts): the page "Open" goes to. */
  opens: string;
  /** What it doesn't do yet, when that matters. */
  limit?: string;
  /** Only for careers with coding practice. */
  audience?: "coding";
  /** Needs the server to run code (capabilities.execution_enabled). */
  needs?: "code-runner";
}

/** What each release was about, newest first. */
export const RELEASES: { release: number; title: string }[] = [
  { release: 2, title: "A more useful personal workspace" },
  { release: 1, title: "Practice labs and career tools" },
];

export const ENTRIES: ReleaseEntry[] = [
  // Release 2
  {
    id: "continue-your-work", release: 2, opens: "dashboard",
    title: "Continue your work",
    what: "The dashboard lists a few of your own saved records to pick up again, newest first, with drafts kept on this device and actions still being finished shown separately.",
    where: "Dashboard, Continue your work.",
    limit: "Six kinds of record so far: drills, labs and reflections aren't listed yet.",
  },
  {
    id: "your-shortcuts", release: 2, opens: "dashboard",
    title: "Your shortcuts",
    what: "Keep up to eight pages one click away on the dashboard, and arrange them with the keyboard or by touch.",
    where: "Dashboard, Your shortcuts, then Edit shortcuts.",
    limit: "Kept in this browser for your account: another device starts with the defaults. Pages only, not single records.",
  },
  {
    id: "search-saved-work", release: 2, opens: "workspace-search",
    title: "Search your saved work",
    what: "Find your own notes, stories, interview-day kits and applications by the words in them. Only your own are searched.",
    where: "Library, Search; or Go to…, Search your saved work.",
    limit: "Words are matched as typed (\"stories\" doesn't find \"story\"). Application notes and kit contents aren't searched yet.",
  },
  {
    id: "archive", release: 2, opens: "stories",
    title: "Archive to keep lists short",
    what: "Archive notes, stories, applications, target roles and offer comparisons you're not using. Nothing is deleted, and Restore brings back the same record.",
    where: "Archive on the record or in its list; archived ones are in each list's archived view.",
    limit: "There's no Undo button: Restore is the undo.",
  },
  {
    id: "several-at-once", release: 2, opens: "saved",
    title: "Several saved items at once",
    what: "Add several bookmarks to a collection in one go, or take several items out of a collection, and see what happened to each one.",
    where: "Library, Saved, then choose the items.",
    limit: "Collections only: nothing is deleted, and adding or removing again reverses it.",
  },
  {
    id: "where-a-story-is-used", release: 2, opens: "stories",
    title: "Where a story is used",
    what: "A story's page lists the interview kits, applications and reflections that point at it, and an application links stories one at a time, so another tab's link isn't undone.",
    where: "Open a story, then Where it's used.",
    limit: "Stories only: notes, targets and offer comparisons have no such list.",
  },
  {
    id: "kit-templates", release: 2, opens: "kit-templates",
    title: "Kit templates",
    what: "Save an interview kit's checklist and questions as a template, then start the next interview's kit from it, without the first one's ticks, links or notes.",
    where: "An interview kit, then Templates. Your templates are under Kit templates.",
    limit: "Kits only. Templates aren't restored from a backup file yet.",
  },
  {
    id: "practice-packet", release: 2, opens: "packet",
    title: "Practice packet",
    what: "Choose bookmarked questions, notes and stories, preview them in your order, then save the packet as a text file or print it.",
    where: "Go to…, then Practice packet.",
    limit: "Coding problems, kits, reflections and lessons aren't offered. A PDF is your browser's Save as PDF.",
  },
  {
    id: "changed-elsewhere", release: 2, opens: "stories",
    title: "Stories changed in another tab",
    what: "When a story is saved in another tab or on another device, a page with nothing unsaved shows the newer version, and a page with unsaved text keeps your text and lets you compare.",
    where: "Any story's page, and your stories list.",
    limit: "Stories only. Another device catches up when you come back to the tab or reconnect.",
  },

  // Release 1
  {
    id: "go-to", release: 1, opens: "help",
    title: "Go to any page by typing",
    what: "Press Ctrl+K (Cmd+K on a Mac), or the Go to… button, and type part of a page's name.",
    where: "Go to… at the top of every page. Help lists the keyboard shortcuts.",
  },
  {
    id: "debugging-lab", release: 1, opens: "debugging", audience: "coding", needs: "code-runner",
    title: "Debugging lab",
    what: "Start from a program with a known bug: reproduce it with the public cases, work out the cause and fix it.",
    where: "Go to…, then Debugging lab.",
    limit: "Three Java exercises.",
  },
  {
    id: "code-review-practice", release: 1, opens: "code-review", audience: "coding",
    title: "Review someone else's code",
    what: "Write your findings on a short solution first, then compare them with an authored review.",
    where: "Go to…, then Code review practice.",
    limit: "Short Java solutions to the existing problems.",
  },
  {
    id: "test-design", release: 1, opens: "test-design", audience: "coding", needs: "code-runner",
    title: "Test design",
    what: "Write test cases for a small specification and see which faulty versions each case tells apart.",
    where: "Go to…, then Test design.",
    limit: "Java only, and only the authored faulty versions are checked.",
  },
  {
    id: "work-samples", release: 1, opens: "work-samples",
    title: "Work samples",
    what: "Write a short piece of work from a fictional brief, and see whether it covers what the brief asks using only its facts.",
    where: "Go to…, then Work samples.",
    limit: "Briefs are written for six careers so far; anyone can open them. Fixed checks, no AI.",
  },
  {
    id: "compare-sample-answers", release: 1, opens: "compare",
    title: "Compare sample answers",
    what: "Mark the sentences that help or hurt two sample answers, say why, then see an authored explanation.",
    where: "Go to…, then Compare sample answers.",
  },
  {
    id: "offer-rehearsal", release: 1, opens: "offers",
    title: "Rehearse an offer conversation",
    what: "Clarify the terms of a fictional offer, ask for something with a reason, and answer a counteroffer. Nothing is sent to anyone.",
    where: "Go to…, then Rehearse an offer conversation.",
    limit: "Two fictional cases, checked by fixed rules.",
  },
  {
    id: "offer-comparison", release: 1, opens: "offer-compare",
    title: "Compare offers privately",
    what: "Put two or three offers you enter by hand side by side, next to what matters to you.",
    where: "Go to…, then Compare offers. Offer conversations link to it too.",
    limit: "Terms you type in only, up to three offers.",
  },
  {
    id: "your-data", release: 1, opens: "your-data",
    title: "Your data",
    what: "See what's saved to your account and what's kept in this browser, and remove chosen copies from this device.",
    where: "Settings, Privacy & data, See your data; or Go to…, Your data.",
    limit: "Counts, not a list of records: Download my data is the complete copy.",
  },
];
