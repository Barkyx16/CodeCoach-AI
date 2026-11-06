import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCameFrom } from "@/hooks/useCameFrom";
import { Icon } from "@/components/Icon";
import { FocusToggle } from "@/features/display/FocusToggle";
import { appPath } from "@/lib/links";

export function WorkspaceFrame({ title, children }: { title: string; children: ReactNode }) {
  const came = useCameFrom();
  const navigate = useNavigate();
  return <div className="workspace-shell">
    <div className="workspace-context">
      <nav className="workspace-context__path focus-hide" aria-label="Breadcrumb">{came && <><a href={appPath(came.from) ?? "/"} onClick={(e) => { e.preventDefault(); navigate(-1); }}>{came.label}</a><span aria-hidden="true">/</span></>}<Link to="/problems"><Icon name="book" size={15} />All problems</Link><span aria-hidden="true">/</span><span className="workspace-context__title" aria-current="page">{title}</span></nav>
      <div className="workspace-context__meta"><span className="workspace-mode"><span />Practice</span><span>Java 21</span><kbd>Ctrl / ⌘ + Enter</kbd><FocusToggle /></div>
    </div>
    {children}
  </div>;
}
