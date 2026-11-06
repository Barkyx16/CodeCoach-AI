import { useCriteria } from "@/api/queries";

/** What the coach looks for, shown before answering: qualitative points and fixed checks, labelled apart. */
export function CriteriaPanel({ track, questionId }: { track: string; questionId: string }) {
  const c = useCriteria(track, questionId);
  if (!c.data) return null;
  return (
    <details className="card criteria-panel">
      <summary>How your answer is evaluated</summary>
      <div className="stack-sm">
        <h3 className="section-title">Points the coach looks for in your words</h3>
        <p className="subtle">Built-in rules look for these; they can miss a good answer phrased differently.</p>
        <ul className="criteria-list">
          {c.data.criteria.map((x) => (
            <li key={x.label}>
              <strong>{x.label}</strong>
              <ul className="mini-list subtle">{x.levels.map((l) => <li key={l.level}>{l.text}</li>)}</ul>
            </li>
          ))}
        </ul>
        <h3 className="section-title">Fixed checks, the same for every answer</h3>
        <ul className="mini-list">{c.data.checks.map((ch) => <li key={ch.text}>{ch.text}</li>)}</ul>
        <p className="subtle">{c.data.disclaimer} Coach: {c.data.coach}, rubric {c.data.rubric_version}.</p>
      </div>
    </details>
  );
}
