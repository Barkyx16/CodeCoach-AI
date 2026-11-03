import { Link } from "react-router-dom";

/** Other practice formats, as plain links: no badges, counts or nudges. */
export function MorePractice({ coding }: { coding: boolean }) {
  return (
    <nav className="more-practice" aria-label="More ways to practice">
      <span className="subtle">More ways to practice:</span>
      <ul>
        {coding && <li><Link to="/whiteboard">Explain a design on a whiteboard</Link></li>}
        <li><Link to="/scenarios">Branching scenarios</Link></li>
        <li><Link to="/learn">Short lessons</Link></li>
      </ul>
    </nav>
  );
}
