import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { useCameFrom } from "@/hooks/useCameFrom";

import { SupportReportPanel } from "./SupportReport";

/**
 * A support report on its own page (from Help): what's in it, what never is, and the report itself.
 * A failure next to a control opens the same report in place instead, so typed work isn't left.
 */
export function SupportReportPage() {
  const came = useCameFrom();
  return (
    <div className="page support-report-page">
      <BackLink fallback={{ to: "/help", label: "Help" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">HELP</p>
          <h1 className="page__title">Support report</h1>
          <p className="page__subtitle">
            A small file that helps someone work out what went wrong. It stays on this device: copying or saving it sends
            nothing, and sharing it afterwards is your choice.
          </p>
        </div>
      </div>
      <div className="support-report-page__layout">
        <Card className="stack-sm">
          <SupportReportPanel problem={null} pagePath={came?.from} standalone />
        </Card>
        <aside className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">What's in it</h2>
            <ul className="support-report-page__list">
              <li>Which version of CodeCoach this is, and whether it's a production build.</li>
              <li>The page (its kind, with record numbers and anything after “?” or “#” removed).</li>
              <li>The time and your time zone.</li>
              <li>Your browser's family and main version, your operating system's family, your language and whether the browser thinks it's online.</li>
              <li>Whether you're signed in, as a guest, or signed out: never which account.</li>
              <li>What the server said about the code judge, the AI coach and email.</li>
              <li>Up to five requests that failed in this session: the kind of request, its status, its error code and the server's reference.</li>
              <li>What you write in the box, if anything.</li>
            </ul>
          </Card>
          <Card className="stack-sm">
            <h2 className="section-title">What's never in it</h2>
            <p>Your answers, code, notes, transcripts, stories, applications, target jobs, recordings or screenshots; your
              email address, name or account number; passwords, tokens, cookies or anything the browser sends with a request.</p>
          </Card>
        </aside>
      </div>
    </div>
  );
}
