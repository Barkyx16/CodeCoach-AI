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
        a: "Learn has short lessons that teach before you're tested. Interview runs a timed mock interview for your job. Plan builds a practice plan around your goals, and Roles prepares you for a specific job posting you paste in. Scenarios are short branching situations, and a few are work queues: put several tasks in order and say why.",
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
    id: "debugging-lab",
    title: "The debugging lab",
    items: [
      {
        q: "What's the debugging lab?",
        a: "Coding exercises that start from a Java program with a known bug. The page says what the code should do and which public cases fail; you reproduce it, find the cause and fix it. Any fix that passes the tests counts, whatever it looks like. Optional notes stay in this browser. The explanation and one correct repair appear only when you ask, or once your fix passes, and asking isn't recorded. Without a judge on the server, attempts are saved but can't be checked. It's for careers with coding practice.",
        links: [{ to: "/problems?view=debugging", label: "Debugging lab" }],
      },
    ],
  },
  {
    id: "code-review-practice",
    title: "Code review practice",
    items: [
      {
        q: "What's code review practice?",
        a: "You review someone else's code: a short Java solution written for one of the coding problems. For each point, cite the lines, say what's wrong, what happens because of it, and what to change; no severity rating is needed. Then send your review, or ask to see the authored one first. The comparison goes by where each finding points, not its wording: it notes which findings line up with an authored defect (each shown by a public test), which with a preference, and which nothing in the authored review supports. It can't judge whether your explanation is right, and there's no score. Not every exercise has a bug. Drafts are saved to your account; reviews you send keep the code they reviewed. It's for careers with coding practice, and no AI is involved.",
        links: [{ to: "/problems?view=code-review", label: "Code review practice" }],
      },
    ],
  },
  {
    id: "test-design",
    title: "Test design",
    items: [
      {
        q: "What's test design practice?",
        a: "A small specification with a trusted reference implementation and a few faulty versions, each with one known defect. You write test cases (inputs and the output the specification calls for), run them, and the report says which faulty versions each case tells apart from the reference. The answer always comes from running the reference, never from your expected output or from AI: a case whose expected output disagrees with the specification isn't counted against anything. Coverage counts only these written-for-practice versions, not every possible bug, and the exercises are separate from the coding problems' hidden tests. Without a judge on the server your cases are saved but not run. It's for careers with coding practice.",
        links: [{ to: "/problems?view=test-design", label: "Test design" }],
      },
    ],
  },
  {
    id: "work-samples",
    title: "Work samples",
    items: [
      {
        q: "What are work samples?",
        a: "Short pieces of real-looking work written from a made-up brief: an incident status update, a reply to a customer, a project handoff note. The brief names the reader, the purpose and the facts you can use. Feedback comes from fixed checks against that brief, not AI: the parts it asks for, the points you covered (quoting your sentence) or missed, any time, amount or reference that isn't in the facts, claims the facts don't support, and words wrong for the reader. Different wording and structure are fine. A revision is a new attempt; the first one is kept. Nothing is sent anywhere, and it's practice evidence, not a credential. Briefs exist so far for software engineers, IT support, customer service, and project and product managers.",
        links: [{ to: "/work-samples", label: "Work samples" }],
      },
    ],
  },
  {
    id: "compare-samples",
    title: "Compare sample answers",
    items: [
      {
        q: "How do sample-answer lessons work?",
        a: "Each lesson shows one interview question and two made-up answers with neutral labels. Mark the sentences that help or hurt an answer, using the Strength and Gap buttons (they work from the keyboard), and write a short reason for each. Then compare with an authored explanation tied to what interviewers look for: it quotes the exact text you read, says what each answer supports and what stays uncertain, and names other good ways to answer. Picking a better answer is optional, and some lessons have no single best one. A reason that differs from the explanation is shown side by side, not marked wrong. You can read the explanation early; your reading then says so. Feedback is fixed rules, not AI, and nothing here changes your plan or scores.",
        links: [{ to: "/compare", label: "Compare sample answers" }],
      },
    ],
  },
  {
    id: "offer-rehearsal",
    title: "Rehearse an offer conversation",
    items: [
      {
        q: "What does the offer rehearsal practise, and what can't it tell me?",
        a: "It practises three parts of an offer conversation with a made-up offer: asking about terms the offer leaves unclear, making a request with a reason, and answering a counteroffer, including asking for time or declining. You can type or speak, stop at any point, and try a different approach later; your earlier rehearsal is kept. The other person is a script, not AI: it only states what the fictional card says, says when something is unknown, and never agrees to anything. The debrief shows your request with the card's own arithmetic, the terms still unknown, anything you said that the card doesn't support, and one thing to try next. It can't predict what a real employer would offer, and it doesn't give salary, tax or legal advice. Nothing is sent to anyone and no application changes.",
        links: [{ to: "/offers", label: "Offer conversations" }],
      },
      {
        q: "How does comparing offers work?",
        a: "You enter each offer's terms yourself (nothing is imported or looked up) with your own factors such as schedule, commute or learning. Pay is put on a yearly basis only when you've entered the basis (payments a year, or hours and weeks), currencies are converted only with a rate and date you enter, and anything missing stays unknown rather than zero. Guaranteed pay, conditional bonuses and equity are kept apart; equity and benefits are never valued and tax isn't estimated. Your ratings are subjective. Optional weights can order the offers, with every point explained, but that's your weighting, not a recommendation. Comparisons are private, never change an application, and Copy as text shows exactly what it copies first.",
        links: [{ to: "/offers/compare", label: "Compare offers" }],
      },
    ],
  },
  {
    id: "getting-around",
    title: "Getting around",
    items: [
      {
        q: "Is there a quick way to open a page?",
        a: "Press Ctrl+K (Cmd+K on a Mac), or the Go to button in the header. Type part of a page's name, like \"notes\", \"plan\" or \"interview\", move with the arrow keys and press Enter; Esc closes it and puts you back where you were. It lists pages you can open right now, for your career; it opens pages only (it doesn't start, send or delete anything), and a page with unsaved changes still asks before you leave it. Inside the code editor, Ctrl+K belongs to the editor. It finds pages, not what's in your notes or answers. What you type stays in your browser; the last few pages you opened from it are kept on this device for your account and removed when you sign out.",
      },
    ],
  },
  {
    id: "history",
    title: "Finding your history",
    items: [
      {
        q: "Where are my past answers and submissions?",
        a: "History lists everything you've done, with filters for career, activity, status, skill or topic, and dates. Each question page also shows your past answers as numbered tries (a revision is saved as a new try; earlier ones never change), and finished interviews open a review with every answer and its feedback.",
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
        q: "What's kept on this device, and can I remove it without losing saved work?",
        a: "Your data (Settings, Privacy & data) lists what's waiting in this browser for your account: answers and code not sent yet, unsaved changes to saved work, and short records of actions waiting for a reply. Each says whether it exists only here or your account keeps the last saved version. Choose the ones to remove and review them first; only those go, from this browser only, and your account, your sign-in and everything else stay. A page open in another tab won't put a removed copy back. The same page counts what's saved to your account without opening any of it, and says where your words go when they're processed, including what isn't known about outside services.",
        links: [{ to: "/settings/data", label: "Your data" }],
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
