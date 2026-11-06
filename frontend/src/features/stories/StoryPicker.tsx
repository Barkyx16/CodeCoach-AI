import { useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useStories, useStory } from "@/api/queries";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

import { COMPETENCY_LABEL } from "./labels";
import { draftFromStory } from "./storyForm";

/**
 * Practise a question with one of your stories. Choosing one can start your draft from it (never
 * without asking when there's already a draft); the answer you send is its own record that points
 * at the story. The story itself is never changed by practising it.
 */
export function StoryPicker({ track, questionId, draft, setDraft, storyId, setStoryId }: {
  track: string;
  questionId: string;
  draft: string;
  setDraft: (v: string) => void;
  storyId: string | null;
  setStoryId: (id: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const stories = useStories({}, open || !!storyId);
  const chosen = useStory(storyId ?? undefined);
  const qc = useQueryClient();
  const listId = useId();
  const [linkError, setLinkError] = useState<unknown>(null);
  const ref = `${track}/${questionId}`;

  if (storyId && chosen.data) {
    const s = chosen.data;
    const linked = s.questions.some((q) => q.ref === ref);
    return (
      <div className="story-picker story-picker--chosen stack-sm" role="region" aria-label="Story you're practising">
        <p><strong>Practising your story:</strong> <Link to={`/stories/${s.id}`}>{s.title}</Link></p>
        <p className="subtle">Your answer is saved as a separate practice and points to this story. The story isn't changed.</p>
        <span className="row">
          {draft.trim() !== draftFromStory(s) && (
            <Button size="sm" onClick={() => {
              if (!draft.trim() || window.confirm("Replace what's in the answer box with a draft built from your story?")) setDraft(draftFromStory(s));
            }}>Start my answer from this story</Button>
          )}
          {!linked && (
            <Button size="sm" variant="ghost" onClick={async () => {
              setLinkError(null);
              try {
                const next = await api.updateStory(s.id, { clear_target: false, reason: "edited", expected_revision: s.revision, question_refs: [...s.questions.map((q) => q.ref), ref] });
                qc.setQueryData(["me", "story", s.id], next);
              } catch (e) {
                setLinkError(e);
              }
            }}>Link this question to the story</Button>
          )}
          {linked && <span className="subtle">This question is linked to the story.</span>}
          <Button size="sm" variant="ghost" onClick={() => setStoryId(null)}>Stop using this story</Button>
        </span>
        <InlineError error={linkError} />
      </div>
    );
  }

  return (
    <details className="story-picker" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Practise with one of your stories</summary>
      {stories.isPending ? <p className="subtle">Loading your stories…</p>
        : stories.isError ? <InlineError error={stories.error} />
        : stories.data.length === 0 ? <p>You haven't written any stories yet. <Link to="/stories/new">Write one</Link> from your own experience.</p>
        : (
          <fieldset className="stack-sm">
            <legend className="visually-hidden">Choose a story</legend>
            <ul className="story-picker__list" id={listId}>
              {stories.data.map((s) => (
                <li key={s.id}>
                  <label className="checkbox">
                    <input type="radio" name={`${listId}-story`} onChange={() => setStoryId(s.id)} />
                    <span>{s.title}{s.competencies.length > 0 && <span className="subtle"> · {s.competencies.map((c) => COMPETENCY_LABEL[c]).join(", ")}</span>}</span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        )}
    </details>
  );
}
