import { useState } from "react";

import { api } from "@/api/endpoints";
import { useTargetMutation } from "@/api/queries";
import type { Requirement, RequirementSetIn, RevisionPreview, Target } from "@/api/types";
import { Button } from "@/components/Button";
import { ChangeList } from "@/features/targets/RequirementVersions";

/** One requirement's own correction or removal, saved as a change to the whole set: a cosmetic
 * correction saves at once; a substantive change or a removal shows what it affects first. */
export function useRequirementChange(t: Target, r: Requirement, onSaved: () => void) {
  const [pending, setPending] = useState<{ body: RequirementSetIn; preview: RevisionPreview } | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const save = useTargetMutation((body: RequirementSetIn) => api.saveRequirements(t.id, body));
  async function propose(change: Partial<Pick<Requirement, "text" | "category" | "removed">>) {
    const body: RequirementSetIn = {
      expected_revision: t.requirements_revision,
      items: t.requirement_list.map((x) => ({ id: x.id, category: x.category, text: x.text, removed: x.removed, ...(x.id === r.id ? change : {}) })),
      same_as: [],
    };
    setChecking(true);
    setError(null);
    try {
      const preview = await api.previewRequirements(t.id, body);
      if ((preview.counts.changed ?? 0) + (preview.counts.removed ?? 0) === 0) {
        save.mutate(body, { onSuccess: onSaved });
      } else {
        setPending({ body, preview });
      }
    } catch (e) {
      setError(e);
    } finally {
      setChecking(false);
    }
  }
  const review = pending && (
    <div className="stack-sm requirement__review" role="region" aria-label={`Before saving: ${r.text}`}>
      <ChangeList preview={pending.preview} />
      <span className="row">
        <Button size="sm" variant="primary" loading={save.isPending} onClick={() => save.mutate(pending.body, { onSuccess: () => { setPending(null); onSaved(); } })}>
          Save this change
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setPending(null)}>Don't save</Button>
      </span>
    </div>
  );
  return { propose, review, busy: checking || save.isPending, error: error ?? save.error };
}
