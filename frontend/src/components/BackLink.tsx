import { Link, useNavigate } from "react-router-dom";

import { useCameFrom } from "@/hooks/useCameFrom";

import { Icon } from "./Icon";

/**
 * "Back to History" that behaves like the browser's Back button (so filters, page and scroll
 * position come back exactly), shown only when this page was opened from that list.
 */
export function BackLink({ fallback }: { fallback?: { to: string; label: string } }) {
  const came = useCameFrom();
  const navigate = useNavigate();
  if (came && !came.previous) {
    return <Link to={came.from} className="back-link"><Icon name="arrow" size={14} className="back-link__icon" />{came.label}</Link>;
  }
  if (came) {
    return (
      <a href={came.from} className="back-link" onClick={(e) => { e.preventDefault(); navigate(-1); }}>
        <Icon name="arrow" size={14} className="back-link__icon" />{came.label}
      </a>
    );
  }
  return fallback ? <Link to={fallback.to} className="back-link"><Icon name="arrow" size={14} className="back-link__icon" />{fallback.label}</Link> : null;
}
