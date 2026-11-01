import Markdown from "react-markdown";

import type { ProblemDetail } from "@/api/types";
import { DifficultyBadge, TopicTag } from "@/components/Badge";
import { formatArgs, formatValue } from "@/lib/format";

/** Problem text is Markdown from our own seed files; react-markdown renders no raw HTML. */
export function ProblemStatement({ problem }: { problem: ProblemDetail }) {
  return (
    <article className="statement" aria-labelledby="problem-title">
      <header className="statement__header">
        <h1 id="problem-title" className="statement__title">{problem.title}</h1>
        <div className="row">
          <DifficultyBadge difficulty={problem.difficulty} />
          {problem.topics.map((t) => <TopicTag key={t} topic={t} />)}
        </div>
      </header>

      <div className="statement__body markdown">
        <Markdown>{problem.statement}</Markdown>
      </div>

      <section className="statement__section">
        <h2 className="section-title">Examples</h2>
        {problem.examples.map((ex, i) => (
          <div className="example" key={i}>
            <div><span className="example__label">Input</span> <code>{ex.input}</code></div>
            <div><span className="example__label">Output</span> <code>{ex.output}</code></div>
            {ex.explanation && <p className="subtle">{ex.explanation}</p>}
          </div>
        ))}
      </section>

      <section className="statement__section">
        <h2 className="section-title">Constraints</h2>
        <ul className="constraints">
          {problem.constraints.map((c) => <li key={c}><code>{c}</code></li>)}
        </ul>
      </section>

      <section className="statement__section">
        <h2 className="section-title">Method signature</h2>
        <code className="signature">
          {problem.signature.returns} {problem.signature.method}(
          {problem.signature.params.map((p) => `${p.type} ${p.name}`).join(", ")})
        </code>
      </section>

      <section className="statement__section">
        <h2 className="section-title">Test cases</h2>
        <p className="subtle">
          {problem.public_tests.length} public · {problem.hidden_test_count} hidden. Hidden tests check edge cases
          and are never shown.
        </p>
        <ul className="test-list">
          {problem.public_tests.map((t) => (
            <li key={t.id}><code>{formatArgs(t.input)}</code> → <code>{formatValue(t.expected_output)}</code></li>
          ))}
        </ul>
      </section>
    </article>
  );
}
