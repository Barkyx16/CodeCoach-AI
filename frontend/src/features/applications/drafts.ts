/**
 * Editable message drafts built only from facts the learner typed. Nothing is invented (no
 * achievements, no promises, no names), nothing is stored, and nothing is ever sent: the learner
 * copies or downloads the text and sends it themselves, if they want to.
 */

export interface DraftFacts {
  kind: "follow_up" | "thank_you";
  role: string;
  employer: string;
  recipient?: string;
  /** When they interviewed or applied, as the learner wants to say it ("on Tuesday"). */
  when?: string;
  /** One thing the learner wants to mention, in their words. */
  point?: string;
  sender?: string;
}

export function draftMessage(f: DraftFacts): { subject: string; body: string } {
  const greeting = f.recipient?.trim() ? `Dear ${f.recipient.trim()},` : "Hello,";
  const when = f.when?.trim() ? ` ${f.when.trim()}` : "";
  const point = f.point?.trim() ? `\n\n${f.point.trim()}` : "";
  const sign = f.sender?.trim() ? `\n\n${f.sender.trim()}` : "\n\n[Your name]";
  if (f.kind === "thank_you") {
    return {
      subject: `Thank you: ${f.role} interview`,
      body: `${greeting}\n\nThank you for your time${when} talking with me about the ${f.role} role at ${f.employer}.${point}\n\nKind regards,${sign}`,
    };
  }
  return {
    subject: `Following up: ${f.role} application`,
    body: `${greeting}\n\nI'm writing to follow up on my application for the ${f.role} role at ${f.employer}${when}. I'd be glad to answer any questions.${point}\n\nKind regards,${sign}`,
  };
}
