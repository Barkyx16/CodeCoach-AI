import { Link } from "react-router-dom";

import { EmptyState } from "@/components/States";

export function NotFoundPage() {
  return (
    <div className="page">
      <EmptyState pageTitle title="Page not found" action={<Link to="/problems">Browse problems</Link>}>
        That page doesn't exist. It may have moved.
      </EmptyState>
    </div>
  );
}
