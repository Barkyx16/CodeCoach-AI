/** Browser tab titles per route (WCAG 2.4.2): what the page is, never "Page not found" for a real page. */
const TITLES: Record<string, string> = {
  "/": "Java interview practice", "/login": "Sign in", "/register": "Create account",
  "/forgot-password": "Reset your password", "/reset-password": "Choose a new password", "/verify-email": "Confirm your email",
  "/problems": "Practice library", "/dashboard": "Dashboard", "/analytics": "Analytics",
  "/history": "History", "/settings": "Settings", "/interviews": "Mock interviews", "/interviews/questions": "Interview question round", "/plan": "Your plan", "/plan/goals": "Your goals", "/targets": "Target roles", "/reviews": "Review queue",
  "/learn": "Lessons", "/scenarios": "Scenarios", "/notes": "Notes", "/notes/new": "New note", "/saved": "Saved",
  "/offline": "Saved for offline", "/help": "Help", "/stories": "Your stories", "/stories/new": "Write a story", "/welcome": "Welcome", "/reports": "Your reports", "/admin/reports": "Content reports", "/share/new": "Ask for feedback", "/shares": "Shared for feedback", "/shared": "Shared answer",
};

/** Dynamic routes, most specific first; each must match a route in router.tsx. */
const PATTERNS: [RegExp, string][] = [
  [/^\/careers\/[^/]+\/questions\/[^/]+$/, "Interview question"],
  [/^\/problems\/[^/]+$/, "Coding workspace"],
  [/^\/interviews\/[^/]+\/retry\/[^/]+$/, "Retry a question"],
  [/^\/interviews\/[^/]+$/, "Mock interview"],
  [/^\/targets\/[^/]+$/, "Target role"],
  [/^\/history\/(submissions|coaching)\/[^/]+$/, "History item"],
  [/^\/learn\/[^/]+$/, "Lesson"],
  [/^\/scenarios\/attempts\/[^/]+$/, "Scenario attempt"],
  [/^\/scenarios\/[^/]+$/, "Scenario"],
  [/^\/notes\/[^/]+$/, "Note"],
  [/^\/stories\/[^/]+$/, "Story"],
  [/^\/shares\/[^/]+$/, "Shared answer and feedback"],
  [/^\/admin\/reports\/[^/]+$/, "Content report"],
  [/^\/saved\/collections\/[^/]+\/practice$/, "Practice queue"],
  [/^\/saved\/collections\/[^/]+$/, "Collection"],
];

export function routeTitle(pathname: string): string {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return TITLES[path] ?? PATTERNS.find(([re]) => re.test(path))?.[1] ?? "Page not found";
}
