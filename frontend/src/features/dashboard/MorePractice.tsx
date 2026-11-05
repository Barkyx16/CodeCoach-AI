import { Link } from "react-router-dom";

import { Icon, type IconName } from "@/components/Icon";

const FORMATS: { to: string; title: string; detail: string; icon: IconName; codingOnly?: boolean }[] = [
  { to: "/drills", title: "Communication drills", detail: "Quick exercises in how you say it", icon: "mic" },
  { to: "/whiteboard", title: "Explain a design on a whiteboard", detail: "Talk through a system, step by step", icon: "code", codingOnly: true },
  { to: "/scenarios", title: "Branching scenarios", detail: "Choose what to do and see what follows", icon: "list" },
  { to: "/learn", title: "Short lessons", detail: "A few minutes, with guided help", icon: "book" },
];

/** Other practice formats: one link per format, no badges, counts or nudges. */
export function MorePractice({ coding }: { coding: boolean }) {
  return (
    <nav className="more-practice" aria-labelledby="more-practice-title">
      <h2 className="dashboard__section-title" id="more-practice-title">More ways to practice</h2>
      <ul className="more-practice__list">
        {FORMATS.filter((f) => coding || !f.codingOnly).map((f) => (
          <li key={f.to}>
            <Link to={f.to} className="format-link" aria-describedby={`format-${f.to.slice(1)}`}>
              <span className="format-link__icon" aria-hidden="true"><Icon name={f.icon} size={18} /></span>
              <span className="format-link__text">
                <span className="format-link__title">{f.title}</span>
                <span className="format-link__detail" id={`format-${f.to.slice(1)}`} aria-hidden="true">{f.detail}</span>
              </span>
              <Icon name="arrow" size={16} className="format-link__arrow" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
