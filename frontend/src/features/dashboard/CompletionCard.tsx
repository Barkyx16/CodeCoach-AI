import { Link } from "react-router-dom";
import { Card } from "@/components/Card";

export function CompletionCard({ solved, total }: { solved: number; total: number }) {
  const fraction = total > 0 ? Math.min(solved / total, 1) : 0;
  return <Card className="completion-card">
    <svg width="108" height="108" viewBox="0 0 108 108" role="img" aria-label={`${solved} of ${total} problems solved`}>
      <circle cx="54" cy="54" r="44" fill="none" stroke="var(--viz-track)" strokeWidth="7" />
      <circle cx="54" cy="54" r="44" fill="none" stroke="var(--viz-solved)" strokeWidth="7" strokeLinecap={solved ? "round" : "butt"} pathLength="100" strokeDasharray={`${fraction * 100} 100`} transform="rotate(-90 54 54)" />
      <text x="54" y="54" textAnchor="middle" dominantBaseline="central" fill="var(--color-text)" fontSize="22" fontWeight="600">{Math.round(fraction * 100)}%</text>
    </svg>
    <div className="stack"><h2 className="section-title">The next problem is progress</h2><p><strong>{solved}</strong> of {total} problems solved. Every attempt is a chance to understand the next idea.</p><Link to="/analytics">See your practice insights <span aria-hidden="true">→</span></Link></div>
  </Card>;
}
