import type { TestDesignReport, TestDesignRun } from "@/api/types";
import { Badge } from "@/components/Badge";

const STATUS: Record<TestDesignReport["cases"][number]["status"], { text: string; tone: string }> = {
  counted: { text: "Counted", tone: "success" },
  duplicate: { text: "Duplicate", tone: "neutral" },
  disagrees: { text: "Disagrees with the specification", tone: "warning" },
  not_finished: { text: "Not finished", tone: "neutral" },
  reference_failed: { text: "Couldn't be checked", tone: "neutral" },
};

const list = (keys: string[]) => keys.join(", ");

/**
 * What a run showed, from the outputs the sandbox produced. Each case says what the reference
 * returned and which faulty versions (by letter) gave something else. Only versions a case told
 * apart are named; the others stay hidden unless the learner asks. Coverage is over these
 * authored versions only, and the report says so.
 */
export function RunReport({ run }: { run: TestDesignRun }) {
  if (run.status === "queued" || run.status === "running") {
    return <p role="status" className="subtle">{run.status === "queued" ? "Waiting for the judge…" : "Running your cases…"}</p>;
  }
  if (!run.report) return <p role="status">{run.status_detail}</p>;
  const report = run.report as unknown as TestDesignReport;
  return (
    <div className="stack td-report">
      <section className="card stack-sm" aria-label="What your cases show">
        <h3 className="section-title">What your cases show</h3>
        <p className="td-report__headline"><strong>{report.summary[0]}</strong></p>
        {report.summary.slice(1).map((line) => <p key={line} className={line.startsWith("This counts only") ? "subtle" : undefined}>{line}</p>)}
        {run.current_version != null && run.current_version !== run.exercise_version && (
          <p className="subtle">This run was against version {run.exercise_version}; the exercise is version {run.current_version} now.</p>
        )}
      </section>
      <section className="stack-sm" aria-label="Case by case">
        <h3 className="section-title">Case by case</h3>
        <ol className="stack-sm td-cases">
          {report.cases.map((c) => (
            <li key={c.case} className="card stack-sm">
              <p className="row">
                <strong>Case {c.case}</strong>
                {c.label_text && <Badge tone="info">{c.label_text}</Badge>}
                <Badge tone={STATUS[c.status].tone}>{STATUS[c.status].text}</Badge>
              </p>
              {c.status !== "duplicate" && c.status !== "not_finished" && <p>The reference returns <code>{c.reference_output}</code>.</p>}
              {c.status === "counted" && (
                <p>{c.distinguishes.length ? <>Tells apart version{c.distinguishes.length === 1 ? "" : "s"} <strong>{list(c.distinguishes)}</strong>
                  {c.new.length > 0 && c.new.length < c.distinguishes.length && <> (new: {list(c.new)})</>}.</> : "Tells apart no faulty version."}</p>
              )}
              <ul className="mini-list">{c.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </li>
          ))}
        </ol>
      </section>
      <section className="stack-sm" aria-label="The faulty versions">
        <h3 className="section-title">The faulty versions</h3>
        <ul className="mini-list td-versions">
          {report.variants.map((v) => (
            <li key={v.key}>
              <strong>Version {v.key}</strong>:{" "}
              {v.caught_by.length
                ? <>{v.title}. Told apart by case{v.caught_by.length === 1 ? "" : "s"} {v.caught_by.join(", ")}.</>
                : "not told apart by these cases."}
            </li>
          ))}
        </ul>
        {report.gap && (
          <div className="banner banner--info stack-sm" role="note">
            <p><strong>One gap to investigate (version {report.gap.variant})</strong></p>
            <p>{report.gap.hint}</p>
          </div>
        )}
      </section>
    </div>
  );
}
