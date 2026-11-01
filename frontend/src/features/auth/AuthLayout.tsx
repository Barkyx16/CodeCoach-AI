import type { ReactNode } from "react";
import { BrandMark } from "@/components/BrandMark";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="page auth">
      <aside className="auth__story" aria-label="Practice with CodeCoach AI">
        <BrandMark />
        <p className="eyebrow">A LITTLE PRACTICE. EVERY DAY.</p>
        <h2>Your next interview<br />starts here.</h2>
        <p className="muted">A focused place to sharpen your Java, explain your thinking, and make progress you can see.</p>
        <ul><li>Real problems. Clear contracts.</li><li>Coaching at your own pace.</li><li>Feedback you can come back to.</li></ul>
      </aside>
      {children}
    </div>
  );
}
