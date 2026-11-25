import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/endpoints";
import { useContentMeta } from "@/api/queries";

/**
 * An answer belongs to the version of the question it was written for. When the question has
 * been corrected since, say so and offer the wording that was answered; never re-grade.
 */
export function AnsweredVersion({ track, questionId, version }: { track: string; questionId: string; version: number }) {
  const meta = useContentMeta("question", `${track}/${questionId}`);
  const changed = meta.data && meta.data.version > version;
  const original = useQuery({
    queryKey: ["question-version", track, questionId, version],
    queryFn: () => api.questionVersion(track, questionId, version),
    enabled: Boolean(changed),
    staleTime: Infinity,
  });
  if (!changed) return null;
  return (
    <details className="answered-version">
      <summary>Answered version {version} of this question (it's now version {meta.data!.version})</summary>
      <p className="subtle">This answer and its score stay as they were. The question read:</p>
      {original.data ? <blockquote className="answered-version__quote"><strong>{original.data.title}.</strong> {original.data.prompt}</blockquote>
        : <p className="subtle">Loading the original wording…</p>}
    </details>
  );
}
