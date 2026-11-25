import { Link } from "react-router-dom";

import { useWhiteboardPrompts } from "@/api/queries";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";

/** Whiteboard prompts: explain a design with a small diagram and your reasoning. */
export function WhiteboardPage() {
  const prompts = useWhiteboardPrompts();
  return (
    <div className="page whiteboard-list">
      <div className="page__header">
        <div>
          <p className="eyebrow">WHITEBOARD</p>
          <h1 className="page__title">Explain a design</h1>
          <p className="page__subtitle">Sketch the parts of a system and how they connect, then explain your choices. It works fully from the keyboard, and the feedback is about what your design addresses, never how it looks.</p>
        </div>
      </div>
      {prompts.isPending ? <LoadingState label="Loading prompts…" /> : prompts.isError ? <ErrorState error={prompts.error} onRetry={() => void prompts.refetch()} /> : (
        <>
          <p className="subtle">{prompts.data.note}</p>
          <ul className="stack">
            {prompts.data.prompts.map((p) => (
              <li key={p.id}>
                <Card className="stack-sm">
                  <h2 className="section-title"><Link to={`/whiteboard/${p.id}`}>{p.title}</Link></h2>
                  <p>{p.objective}</p>
                </Card>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
