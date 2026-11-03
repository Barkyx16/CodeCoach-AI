import { useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useCareers } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";

export const DEFAULT_TRACK = "software-engineer";
/** Every URL key the question explorer owns; changing career clears them. */
export const EXPLORER_KEYS = ["q", "difficulty", "kind", "skill", "status", "sort", "shown"];

/**
 * Which career the practice pages show: the signed-in user's own track, or (signed out) the
 * `?career=` in the URL. Changing it saves to the profile when signed in.
 */
export function usePracticeTrack() {
  const { user, setUser } = useAuth();
  const [params, setParams] = useSearchParams();
  const careers = useCareers();
  const track = user?.career_track || params.get("career") || DEFAULT_TRACK;
  const career = careers.data?.find((c) => c.slug === track);

  async function setTrack(slug: string) {
    const next = new URLSearchParams(params);
    for (const key of ["view", "topic", ...EXPLORER_KEYS]) next.delete(key);
    if (user) {
      setUser(await api.updateProfile({ career_track: slug }));
      next.delete("career");
    } else {
      next.set("career", slug);
    }
    setParams(next, { replace: true });
  }

  return { track, career, careersLoading: careers.isPending, setTrack };
}

