import { useSearchParams } from "react-router-dom";

import { useCareers } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";

export const DEFAULT_TRACK = "software-engineer";
/** Every URL key the question explorer owns; changing career clears them. */
export const EXPLORER_KEYS = ["q", "difficulty", "kind", "skill", "status", "sort", "shown"];

/**
 * A `?career=` value as a career slug: trimmed and lower-cased ("Registered-Nurse" is
 * registered-nurse); anything that can't be a slug is no career at all.
 */
export function careerSlug(raw: string | null): string | null {
  const slug = raw?.trim().toLowerCase() ?? "";
  return /^[a-z0-9][a-z0-9-]{0,63}$/.test(slug) ? slug : null;
}

/**
 * Which career a public page shows (Volume 9, prompt 4; NAVIGATION.md "Browsing a career"): the
 * `?career=` in the URL when it names a known career (a breadcrumb like "Registered Nurse
 * questions", or a copied link, opens that career's library, for anyone), else the signed-in
 * learner's own career, else the default. An unknown, removed or malformed value falls back to
 * the learner's own and says so. Browsing never changes the account: the plan, goals, dashboard
 * and analytics follow the learner's own career, changed only in Settings. The parameter only
 * chooses public content; it gives no access to anyone's records.
 */
export function useBrowseCareer() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const careers = useCareers();
  const raw = params.get("career");
  const asked = careerSlug(raw);
  // Before the list arrives, trust a well-formed value (no flash of the wrong career).
  const known = asked && (!careers.data || careers.data.some((c) => c.slug === asked)) ? asked : null;
  const own = user?.career_track || null;
  const track = known || own || DEFAULT_TRACK;
  const career = careers.data?.find((c) => c.slug === track);
  return {
    track,
    career,
    own,
    ownCareer: own ? careers.data?.find((c) => c.slug === own) : undefined,
    /** A career other than the learner's own was asked for (or any, when signed out). */
    browsing: Boolean(known) && known !== own,
    /** `?career=` was given but names no career here (shown once the list has loaded). */
    unknown: raw !== null && Boolean(careers.data) && !known ? raw : null,
    /** The query that keeps this career on links within the browse context ("" for your own). */
    keep: known && known !== own ? `career=${known}` : "",
    careersLoading: careers.isPending,
    /** A `?career=` is waiting for the list of careers to say whether it's known. */
    pending: raw !== null && careers.isPending,
  };
}

/**
 * The practice library's career: as useBrowseCareer. Choosing another one in the library browses
 * it (the URL changes); it never saves to the profile. Choosing your own goes back to your own.
 */
export function usePracticeTrack() {
  const browse = useBrowseCareer();
  const [params, setParams] = useSearchParams();

  function setTrack(slug: string) {
    const next = new URLSearchParams(params);
    for (const key of ["view", "topic", ...EXPLORER_KEYS]) next.delete(key);
    if (slug === browse.own) next.delete("career");
    else next.set("career", slug);
    setParams(next, { replace: true });
  }

  return { ...browse, setTrack };
}

/** `path` with the browse context kept: `/learn` → `/learn?career=registered-nurse` while browsing. */
export function withCareer(path: string, keep: string): string {
  if (!keep) return path;
  return `${path}${path.includes("?") ? "&" : "?"}${keep}`;
}
