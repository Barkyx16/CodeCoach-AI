import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCameFrom } from "@/hooks/useCameFrom";
import { Icon } from "@/components/Icon";
import { FocusToggle } from "@/features/display/FocusToggle";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";

/** The coding library, whatever the learner's own career (a nurse's /problems is nursing questions). */
export const CODING_LIBRARY = `/problems?career=${DEFAULT_TRACK}`;

export function WorkspaceFrame({ title, children }: { title: string; children: ReactNode }) {
  const came = useCameFrom();
  const navigate = useNavigate();
  const back = came && (came.previous
    ? <a href={came.from} onClick={(e) => { e.preventDefault(); navigate(-1); }}>{came.label}</a>
    : <Link to={came.from}>{came.label}</Link>);
  return <div className="workspace-shell">
    <div className="workspace-context">
      <nav className="workspace-context__path focus-hide" aria-label="Breadcrumb">{back && <>{back}<span aria-hidden="true">/</span></>}<Link to={CODING_LIBRARY}><Icon name="book" size={15} />Coding problems</Link><span aria-hidden="true">/</span><span className="workspace-context__title" aria-current="page">{title}</span></nav>
      <div className="workspace-context__meta"><span className="workspace-mode"><span />Practice</span><span>Java 21</span><kbd>Ctrl / ⌘ + Enter</kbd><FocusToggle /></div>
    </div>
    {children}
  </div>;
}
