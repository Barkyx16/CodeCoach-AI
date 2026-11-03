/**
 * Help content. Every answer describes what the app actually does today and links to the real
 * page. Keep it in step with the features: a test checks every link points at a real route.
 */
export interface HelpLink {
  to: string;
  label: string;
  external?: boolean;
}

export interface HelpItem {
  q: string;
  a: string;
  links?: HelpLink[];
}

export interface HelpTopic {
  id: string;
  title: string;
  items: HelpItem[];
}

export const REPO_URL = "https://github.com/Barkyx16/CodeCoach-AI";

export const HELP_TOPICS: HelpTopic[] = [
  {
    id: "choosing",
    title: "Choosing what to practise",
    items: [
      {
        q: "Where do I start?",
        a: "Practice lists the interview questions for the job you chose, and coding problems for jobs that involve code. Filter by difficulty, format or skill, or search by keyword. Your job is set in Settings and can be changed any time; earlier practice is kept.",
        links: [{ to: "/problems", label: "Practice" }, { to: "/settings", label: "Settings" }],
      },
      {
        q: "What else is there besides single questions?",
        a: "Learn has short lessons that teach before you're tested. Interview runs a timed mock interview for your job. Plan builds a practice plan around your goals, and Roles prepares you for a specific job posting you paste in. Scenarios are short branching situations.",
        links: [{ to: "/learn", label: "Learn" }, { to: "/interviews", label: "Interview" }, { to: "/plan", label: "Plan" }, { to: "/targets", label: "Roles" }, { to: "/scenarios", label: "Scenarios" }],
      },
    ],
  },
  {
    id: "saving",
    title: "Saving your work",
    items: [
      {
        q: "Is my answer saved while I type?",
        a: "Yes, as a draft in this browser. Answer and code drafts stay on this device until you send them; nothing is sent until you choose Get feedback or Submit. Signing out deletes this account's drafts from the device, after a warning.",
      },
      {
        q: "How do I keep a question or problem for later?",
        a: "Use Bookmark on its page, or add it to one of your collections. Saved lists them, and a collection can be practised in order as a queue. Notes keeps your own private notes, saved to your account as you type.",
        links: [{ to: "/saved", label: "Saved" }, { to: "/notes", label: "Notes" }],
      },
      {
        q: "Can I practise offline?",
        a: "Pages you've chosen to Save for offline can be read without a connection, and drafts stay on the device. Feedback, judging and interviews need the server, so they pause until you're back online.",
        links: [{ to: "/offline", label: "Saved for offline" }],
      },
    ],
  },
  {
    id: "feedback",
    title: "Understanding feedback",
    items: [
      {
        q: "Where does feedback on written answers come from?",
        a: "From CodeCoach's built-in rubric coach. It checks your answer against what a strong answer covers and lists what to add. It isn't an AI model, it can miss good points phrased unusually, and a score is practice feedback, not a hiring decision.",
      },
      {
        q: "How is code checked?",
        a: "Submit runs your code against hidden tests on the server's judge, and the verdict comes only from those tests. If code can't be judged on this server, the page says so and the button saves your attempt instead. Hints and code reviews from the coach explain; they never change a verdict.",
      },
      {
        q: "Something in a question or its feedback looks wrong.",
        a: "Use Report an issue on that question or problem, or Report a problem with this feedback under an answer. Your reports page shows what happened to each one.",
        links: [{ to: "/reports", label: "Your reports" }],
      },
    ],
  },
  {
    id: "voice",
    title: "Using voice",
    items: [
      {
        q: "Can I answer out loud?",
        a: "In mock interviews, yes, if your browser supports speech recognition (Chrome, Edge and Safari do; Firefox doesn't). The browser turns your speech into text, which you can edit before sending. CodeCoach never receives audio, only the text you choose to send, and the microphone test is never recorded. You can always type instead.",
        links: [{ to: "/interviews", label: "Interview" }],
      },
      {
        q: "Who processes my speech?",
        a: "Your browser's own speech service: Chrome and Edge send audio to their vendor's speech servers, and Safari may process it on your device. The microphone listens only after you press Speak answer and stops when you press Stop listening; typing works without it.",
      },
    ],
  },
  {
    id: "history",
    title: "Finding your history",
    items: [
      {
        q: "Where are my past answers and submissions?",
        a: "History lists everything you've done, with filters for career, activity, status, skill or topic, and dates. Each question page also shows your past answers, and finished interviews open a review with every answer and its feedback.",
        links: [{ to: "/history", label: "History" }],
      },
      {
        q: "How do I see my progress?",
        a: "Dashboard shows a summary for your job; Analytics breaks it down by skill or topic over time.",
        links: [{ to: "/dashboard", label: "Dashboard" }, { to: "/analytics", label: "Analytics" }],
      },
    ],
  },
  {
    id: "account",
    title: "Your account and data",
    items: [
      {
        q: "Can I download or delete my data?",
        a: "In Settings, Privacy & data has Download my data (everything as one file), and Danger zone deletes your account and everything in it. Display & reading sets the theme, text size, contrast and motion on this device.",
        links: [{ to: "/settings", label: "Settings" }],
      },
      {
        q: "What's a guest session?",
        a: "A temporary account with no email or password. It works like any account, but guest accounts are deleted after a period without activity. Create an account from Settings to keep everything you've done.",
      },
    ],
  },
  {
    id: "support",
    title: "Getting more help",
    items: [
      {
        q: "Can I contact someone?",
        a: "CodeCoach is an open-source portfolio project: there's no support team, live chat or email support, and no promised response time. Problems with specific content go through Report an issue; other bugs can be raised on the project's GitHub repository.",
        links: [{ to: REPO_URL, label: "CodeCoach on GitHub", external: true }],
      },
    ],
  },
];

/** Topics (with only their matching items) for a search; every word must appear somewhere. */
export function searchHelp(query: string): HelpTopic[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return HELP_TOPICS;
  return HELP_TOPICS.map((t) => ({
    ...t,
    items: t.items.filter((i) => {
      const text = `${t.title} ${i.q} ${i.a} ${(i.links ?? []).map((l) => l.label).join(" ")}`.toLowerCase();
      return words.every((w) => text.includes(w));
    }),
  })).filter((t) => t.items.length > 0);
}
