import { Link } from "react-router-dom";

import { useStoryUsedIn } from "@/api/queries";
import { Card } from "@/components/Card";
import { ErrorState, LoadingState } from "@/components/States";
import { formatDay } from "@/features/applications/dates";
import { STAGE_LABEL } from "@/features/applications/labels";

export const BACK_TO_STORY = "Back to your story";

/**
 * Where this story is used (Volume 11, prompt 6; docs/BACKLINKS.md): your interview kits,
 * applications and reflections that point at it, one level only, at most a handful of each with a
 * count of all. Titles and dates, nothing copied from them; each opens with a way back here.
 */
export function UsedIn({ storyId }: { storyId: string }) {
  const used = useStoryUsedIn(storyId);
  const back = { from: `/stories/${storyId}`, fromLabel: BACK_TO_STORY };
  const d = used.data;
  const none = d && d.kits_total + d.applications_total + d.reflections_total === 0;
  const more = (shown: number, total: number) =>
    total > shown ? <p className="subtle">The newest {shown} of {total}.</p> : null;
  return (
    <Card className="stack-sm used-in">
      <h2 className="section-title">Where it's used</h2>
      {used.isPending ? <LoadingState label="Finding where it's used…" />
        : used.isError ? <ErrorState error={used.error} onRetry={() => void used.refetch()} />
        : none ? (
          <p className="subtle">Not in any interview kit, application or reflection yet. Choose it in an application's
            “Linked preparation” or in an interview kit.</p>
        ) : (
          <>
            {d!.kits_total > 0 && (
              <section className="stack-sm" aria-labelledby="used-in-kits">
                <h3 className="used-in__title" id="used-in-kits">Interview kits ({d!.kits_total})</h3>
                <ul className="mini-list">
                  {d!.kits.map((k) => (
                    <li key={k.event_id}>
                      <Link to={`/applications/${k.application_id}/events/${k.event_id}/kit`} state={back}>{k.event_title}</Link>
                      <span className="subtle"> · {k.role_title} at {k.employer}{k.event_on ? ` · ${formatDay(k.event_on)}` : ""}{k.application_archived ? " · application archived" : ""}</span>
                    </li>
                  ))}
                </ul>
                {more(d!.kits.length, d!.kits_total)}
              </section>
            )}
            {d!.applications_total > 0 && (
              <section className="stack-sm" aria-labelledby="used-in-apps">
                <h3 className="used-in__title" id="used-in-apps">Applications ({d!.applications_total})</h3>
                <ul className="mini-list">
                  {d!.applications.map((a) => (
                    <li key={a.id}>
                      <Link to={`/applications/${a.id}`} state={back}>{a.role_title} at {a.employer}</Link>
                      <span className="subtle"> · {STAGE_LABEL[a.stage]}{a.archived ? " · archived" : ""}</span>
                    </li>
                  ))}
                </ul>
                {more(d!.applications.length, d!.applications_total)}
              </section>
            )}
            {d!.reflections_total > 0 && (
              <section className="stack-sm" aria-labelledby="used-in-reflections">
                <h3 className="used-in__title" id="used-in-reflections">Reflections ({d!.reflections_total})</h3>
                <ul className="mini-list">
                  {d!.reflections.map((r) => (
                    <li key={r.event_id}>
                      <Link to={`/applications/${r.application_id}/events/${r.event_id}/reflection`} state={back}>{r.event_title}</Link>
                      <span className="subtle"> · {r.role_title} at {r.employer}{r.event_on ? ` · ${formatDay(r.event_on)}` : ""}</span>
                    </li>
                  ))}
                </ul>
                {more(d!.reflections.length, d!.reflections_total)}
              </section>
            )}
          </>
        )}
      <p className="subtle">These point to this story; nothing is copied into them, and only you can see them.</p>
    </Card>
  );
}
