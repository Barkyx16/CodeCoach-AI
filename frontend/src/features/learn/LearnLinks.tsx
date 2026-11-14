import { Link } from "react-router-dom";

import { useRelatedUnits } from "@/api/queries";
import { Icon } from "@/components/Icon";

/** "Learn first" links to units that prepare for this question or problem (nothing if none). */
export function LearnLinks({ query, from }: { query: { track?: string; question_id?: string; problem_slug?: string }; from: { from: string; fromLabel: string } }) {
  const related = useRelatedUnits(query);
  if (!related.data?.length) return null;
  return (
    <section className="card stack-sm learn-links" aria-labelledby="learn-links-title">
      <h2 className="section-title" id="learn-links-title"><Icon name="book" size={16} />Learn first</h2>
      <ul className="mini-list">
        {related.data.map((u) => <li key={u.id}><Link to={`/learn/${u.id}`} state={from}>{u.title}</Link></li>)}
      </ul>
    </section>
  );
}
