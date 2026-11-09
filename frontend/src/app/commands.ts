/**
 * The command palette's commands (Volume 10, prompt 1): a quick way to the app's pages, not a
 * search engine. Every command opens a page the router already has; none deletes, sends, submits,
 * records or spends anything (a page reached this way still asks before it does). Which commands
 * there are, and what they're called, follows the real sign-in, career and server state; a page the
 * server can't serve right now is listed with the reason instead of a link that leads nowhere.
 * Access is still decided by the page and the API, never by this list.
 *
 * Typed text is matched here, in the browser, against labels and a few aliases: it's never sent,
 * logged or stored. Recently used commands are kept per account as command ids only (never a
 * record's title), at most RECENT_LIMIT, and removed when that account signs out on this device.
 */

export type CommandSection = "Practice" | "Progress" | "Job search" | "Your library" | "Account";

export interface Command {
  id: string;
  label: string;
  /** One line on where it goes. Not searched. */
  detail: string;
  to: string;
  section: CommandSection;
  aliases: string[];
  /** Why it can't be opened right now; such a command isn't a link. */
  unavailable?: string;
  /** A state the page will show (e.g. code isn't run on this server); it still opens. */
  note?: string;
}

export interface CommandContext {
  signedIn: boolean;
  isAdmin: boolean;
  /** The career shown has coding practice (problems, the coding interview, the whiteboard). */
  coding: boolean;
  /** The server runs code (capabilities.execution_enabled); unknown counts as yes. */
  executionEnabled: boolean;
  /** A demo server: no accounts are created there. */
  demoMode: boolean;
}

type Spec = Omit<Command, "aliases"> & { aliases?: string[]; when?: (c: CommandContext) => boolean };

const signedIn = (c: CommandContext) => c.signedIn;

const SPECS: ((c: CommandContext) => Spec)[] = [
  // Practice
  (c) => c.coding
    ? { id: "problems", label: "Coding problems", detail: "Problems to solve in the code editor, by difficulty", to: "/problems", section: "Practice",
      aliases: ["library", "practice", "code", "leetcode", "algorithms"],
      ...(c.executionEnabled ? {} : { note: "Code isn't run on this server: attempts are saved, not judged." }) }
    : { id: "questions", label: "Interview questions", detail: "Every question for your job, by difficulty", to: "/problems", section: "Practice",
      aliases: ["library", "practice", "questions", "answer"] },
  (c) => ({ id: "questions-coding-career", label: "Interview questions", detail: "Written and spoken questions for your job", to: "/problems?view=questions", section: "Practice",
    aliases: ["library", "behavioral", "questions", "answer"], when: () => c.coding }),
  (c) => ({ id: "debugging", label: "Debugging lab", detail: "Fix programs with a known bug", to: "/problems?view=debugging", section: "Practice",
    aliases: ["debug", "bug", "fix", "broken code"], when: () => c.coding }),
  (c) => ({ id: "code-review", label: "Code review practice", detail: "Review someone else's code, then compare", to: "/problems?view=code-review", section: "Practice",
    aliases: ["code review", "reviewer", "pull request", "critique"], when: () => c.signedIn && c.coding }),
  (c) => ({ id: "test-design", label: "Test design", detail: "Write cases that tell faulty versions apart", to: "/problems?view=test-design", section: "Practice",
    aliases: ["testing", "test cases", "unit tests", "edge cases", "boundary"], when: () => c.signedIn && c.coding }),
  () => ({ id: "interview", label: "Start or resume a mock interview", detail: "Questions in a row, like the real thing; a round in progress is offered first", to: "/interviews", section: "Practice",
    aliases: ["mock interview", "interview", "resume", "round"], when: signedIn }),
  () => ({ id: "learn", label: "Lessons", detail: "Short lessons with guided help", to: "/learn", section: "Practice", aliases: ["learn", "units", "course"] }),
  () => ({ id: "work-samples", label: "Work samples", detail: "Write a short piece of work from a brief", to: "/work-samples", section: "Practice",
    aliases: ["work sample", "incident update", "handoff", "customer reply", "memo"], when: signedIn }),
  () => ({ id: "compare", label: "Compare sample answers", detail: "Mark what makes an answer useful, then see why", to: "/compare", section: "Practice",
    aliases: ["sample answers", "example answers", "compare answers", "what makes a good answer"], when: signedIn }),
  () => ({ id: "offer-compare", label: "Compare offers", detail: "Your terms and priorities side by side, privately", to: "/offers/compare", section: "Practice",
    aliases: ["offer comparison", "compare offers", "salary comparison", "job offers"], when: signedIn }),
  () => ({ id: "offers", label: "Rehearse an offer conversation", detail: "Clarify, ask with a reason, answer a counteroffer", to: "/offers", section: "Practice",
    aliases: ["negotiation", "negotiate", "salary", "offer", "counteroffer", "pay"], when: signedIn }),
  () => ({ id: "drills", label: "Communication drills", detail: "Quick exercises in how you say it", to: "/drills", section: "Practice", aliases: ["drill", "speaking", "voice"], when: signedIn }),
  () => ({ id: "scenarios", label: "Scenarios", detail: "Choose what to do and see what follows", to: "/scenarios", section: "Practice", aliases: ["branching", "situations", "simulator"], when: signedIn }),
  (c) => ({ id: "whiteboard", label: "Whiteboard: explain a design", detail: "Sketch a system and explain your choices", to: "/whiteboard", section: "Practice",
    aliases: ["system design", "diagram", "architecture", "board"], when: () => c.signedIn && c.coding }),
  () => ({ id: "reviews", label: "Reviews due", detail: "Answers to practise again, when they're due", to: "/reviews", section: "Practice", aliases: ["review", "spaced", "due"], when: signedIn }),
  // Progress
  () => ({ id: "dashboard", label: "Dashboard", detail: "Today's plan and where you stand", to: "/dashboard", section: "Progress", aliases: ["home", "today"], when: signedIn }),
  () => ({ id: "plan", label: "My plan", detail: "What to practise this week, and why", to: "/plan", section: "Progress", aliases: ["roadmap", "schedule plan", "baseline"], when: signedIn }),
  () => ({ id: "goals", label: "Goals", detail: "Your target date, focus areas and formats", to: "/plan/goals", section: "Progress", aliases: ["target date", "focus"], when: signedIn }),
  () => ({ id: "analytics", label: "Analytics", detail: "Scores and trends over time", to: "/analytics", section: "Progress", aliases: ["stats", "progress", "scores", "trends"], when: signedIn }),
  () => ({ id: "history", label: "History", detail: "Every answer and round, with feedback", to: "/history", section: "Progress", aliases: ["past", "attempts", "feedback", "submissions"], when: signedIn }),
  // Job search
  () => ({ id: "targets", label: "Target roles", detail: "Roles you're after and what each one asks for", to: "/targets", section: "Job search", aliases: ["roles", "jobs", "postings"], when: signedIn }),
  () => ({ id: "applications", label: "Applications", detail: "Track where you've applied", to: "/applications", section: "Job search", aliases: ["applied", "tracker", "companies"], when: signedIn }),
  () => ({ id: "schedule", label: "Schedule", detail: "Interviews and practice on your calendar", to: "/schedule", section: "Job search", aliases: ["calendar", "agenda", "upcoming"], when: signedIn }),
  () => ({ id: "reflections", label: "Interview reflections", detail: "What happened in real interviews, and what's next", to: "/reflections", section: "Job search", aliases: ["debrief", "after interview"], when: signedIn }),
  // Your library
  () => ({ id: "stories", label: "Stories", detail: "Your examples, ready for any question", to: "/stories", section: "Your library", aliases: ["star", "examples"], when: signedIn }),
  () => ({ id: "story-new", label: "Write a new story", detail: "Opens an empty story; nothing is saved until you save it", to: "/stories/new", section: "Your library", aliases: ["new story", "star", "add story"], when: signedIn }),
  () => ({ id: "notes", label: "Notes", detail: "What you've noted while practising", to: "/notes", section: "Your library", aliases: ["notebook"], when: signedIn }),
  () => ({ id: "saved", label: "Saved", detail: "Bookmarks and collections", to: "/saved", section: "Your library", aliases: ["bookmarks", "collections", "queue"], when: signedIn }),
  () => ({ id: "shares", label: "Shared answers", detail: "Links you've shared and the feedback they got", to: "/shares", section: "Your library", aliases: ["share", "reviewer", "feedback links"], when: signedIn }),
  (c) => ({ id: "triage", label: "Triage reports", detail: "Reports about questions (admin)", to: "/admin/reports", section: "Your library", aliases: ["admin", "reports"], when: () => c.signedIn && c.isAdmin }),
  // Account
  () => ({ id: "settings", label: "Settings", detail: "Account, career, display and data", to: "/settings", section: "Account", aliases: ["account", "preferences", "career", "theme", "export"], when: signedIn }),
  () => ({ id: "your-data", label: "Your data", detail: "What's stored, where, and clearing this device", to: "/settings/data", section: "Account",
    aliases: ["privacy", "data", "storage", "clear drafts", "device data", "what's stored"], when: signedIn }),
  () => ({ id: "restore", label: "Restore from a backup", detail: "Preview a backup file first; nothing is added until you confirm", to: "/settings/restore", section: "Account", aliases: ["import", "backup"], when: signedIn }),
  () => ({ id: "help", label: "Help", detail: "How things work, and keyboard shortcuts", to: "/help", section: "Account", aliases: ["guide", "faq", "shortcuts"] }),
  (c) => ({ id: "sign-in", label: "Sign in", detail: "To an account you already have", to: "/login", section: "Account", aliases: ["log in", "login"], when: () => !c.signedIn && !c.demoMode }),
  (c) => ({ id: "register", label: "Create account", detail: "Free; pick your job to get its questions", to: "/register", section: "Account", aliases: ["sign up", "register"], when: () => !c.signedIn,
    ...(c.demoMode ? { unavailable: "This demo server doesn't create accounts. The guided demo shows the app without one." } : {}) }),
  (c) => ({ id: "demo", label: "Guided demo", detail: "Try the app with a sample learner, no account needed", to: "/demo", section: "Account", aliases: ["demo", "try"], when: () => !c.signedIn && c.demoMode }),
];

export function commandsFor(context: CommandContext): Command[] {
  return SPECS.map((make) => make(context))
    .filter((s) => !s.when || s.when(context))
    .map(({ when: _when, aliases, ...rest }) => ({ ...rest, aliases: aliases ?? [] }));
}

const fold = (text: string) => text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
/** A word without a plural ending, so "story" finds "Stories" and "notes" finds "Notes". */
const stem = (w: string) => (w.length > 4 && w.endsWith("ies") ? `${w.slice(0, -3)}y` : w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w);
const words = (text: string) => fold(text).split(" ").filter(Boolean);
const startsAny = (forms: string[], typed: string) => forms.some((w) => w.startsWith(typed) || stem(w).startsWith(stem(typed)));

/** Commands whose label or aliases have a word starting with each typed word (plural endings
 * ignored), best first: label matches, then aliases, then the list's own order. Not a substring
 * search: "story" shouldn't find "History". An empty query lists everything. */
export function searchCommands(commands: Command[], query: string): Command[] {
  const typed = words(query);
  if (!typed.length) return commands;
  const scored: { command: Command; score: number; order: number }[] = [];
  commands.forEach((command, order) => {
    const label = words(command.label);
    const aliasWords = command.aliases.flatMap(words);
    let score = 0;
    for (const t of typed) {
      if (startsAny(label, t)) score += 3;
      else if (startsAny(aliasWords, t)) score += 2;
      else return; // every word has to match somewhere
    }
    if (fold(command.label).startsWith(typed.join(" "))) score += 2;
    scored.push({ command, score, order });
  });
  return scored.sort((a, b) => b.score - a.score || a.order - b.order).map((s) => s.command);
}

export const RECENT_LIMIT = 5;
export const recentKey = (userId: string) => `palette-recent:${userId}`;

/** This account's recently used command ids on this device, newest first (unknown ids ignored). */
export function readRecent(userId: string): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(recentKey(userId)) ?? "[]") as unknown;
    return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string" && /^[a-z-]{1,40}$/.test(x)).slice(0, RECENT_LIMIT) : [];
  } catch {
    return [];
  }
}

export function rememberRecent(userId: string, id: string): void {
  try {
    const next = [id, ...readRecent(userId).filter((x) => x !== id)].slice(0, RECENT_LIMIT);
    window.localStorage.setItem(recentKey(userId), JSON.stringify(next));
  } catch {
    /* storage blocked: nothing is remembered */
  }
}

/** Ctrl+K (Cmd+K on a Mac), not while text is being composed (an input method's candidates) and
 * not inside the code editor, where Ctrl+K starts the editor's own two-key shortcuts. */
export function isPaletteShortcut(event: KeyboardEvent): boolean {
  if (event.key.toLowerCase() !== "k" || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return false;
  if (event.isComposing || event.keyCode === 229) return false;
  const target = event.target as Element | null;
  return !target?.closest?.(".monaco-editor");
}
