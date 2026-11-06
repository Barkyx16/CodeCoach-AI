/**
 * What a piece of feedback is, said the same way everywhere it appears (Volume 4 prompt 06): fixed
 * checks on an answer's structure, a practice interviewer's reply, a person's opinion, the judge's
 * test results, or the coach's reading of them. One short line, always visible.
 */
export type FeedbackKindName = "structure" | "interviewer" | "opinion" | "results" | "explanation";

const KINDS: Record<FeedbackKindName, { label: string; text: string }> = {
  structure: {
    label: "Answer structure",
    text: "Fixed checks on how your answer is built, using your own words. Not a judgement of whether the content is clinically or technically right.",
  },
  interviewer: {
    label: "Practice interviewer",
    text: "A simulated interviewer's reply, to rehearse with. It isn't an assessment of you.",
  },
  opinion: {
    label: "Opinion",
    text: "What a person thought. CodeCoach doesn't check it.",
  },
  results: {
    label: "Test results",
    text: "From running your code against the tests: what passed and failed, not an opinion.",
  },
  explanation: {
    label: "Coach's explanation",
    text: "The coach's reading of the public test results and compiler output. Check it against them.",
  },
};

export function FeedbackKind({ kind }: { kind: FeedbackKindName }) {
  const k = KINDS[kind];
  return (
    <p className="feedback-kind subtle">
      <span className="badge badge--neutral feedback-kind__label">{k.label}</span> {k.text}
    </p>
  );
}
