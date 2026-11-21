import type { Kit, KitTemplate } from "@/api/types";

/** What a template never keeps, said where one is made (docs/TEMPLATES.md). */
export const NOT_KEPT = "Never kept: what you've ticked, the meeting link, location, interviewers, notes, examples, or anything about this interview.";
export const SNAPSHOT = "A template is a copy of these words, not a link: changing this kit won't change it, and changing it won't change any kit.";

/**
 * Applying a kit template (Volume 11, prompt 7; docs/TEMPLATES.md): its items join this kit's form
 * as new items of the kit's own (new ids, yours, not done, not hidden or excluded). One whose words
 * are already in the kit (in any case) isn't added twice. Nothing is saved: the kit's Save does
 * that, like any other change, and the template isn't linked to the kit afterwards.
 */
export function applyTemplate(kit: Pick<Kit, "checklist" | "questions">, template: Pick<KitTemplate, "checklist" | "questions">) {
  const has = (list: { text: string }[]) => new Set(list.map((x) => x.text.trim().toLowerCase()));
  const ticks = has(kit.checklist);
  const asks = has(kit.questions);
  const checklist = [...kit.checklist];
  const questions = [...kit.questions];
  let addedChecklist = 0;
  let addedQuestions = 0;
  for (const c of template.checklist) {
    const key = c.text.trim().toLowerCase();
    if (ticks.has(key)) continue;
    ticks.add(key);
    checklist.push({ id: freshId(), text: c.text, origin: "yours", done: false, hidden: false });
    addedChecklist += 1;
  }
  for (const q of template.questions) {
    const key = q.text.trim().toLowerCase();
    if (asks.has(key)) continue;
    asks.add(key);
    questions.push({ id: freshId(), text: q.text, group: q.group ?? "other", origin: "yours", excluded: false, note: null });
    addedQuestions += 1;
  }
  return { checklist, questions, addedChecklist, addedQuestions };
}

const freshId = () => `t-${crypto.randomUUID().slice(0, 8)}`; // as the kit's own new items are made
