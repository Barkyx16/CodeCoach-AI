import { useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useCareers } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";

export const DEFAULT_TRACK = "software-engineer";
/** Every URL key the question explorer owns; changing career clears them. */
export const EXPLORER_KEYS = ["q", "difficulty", "kind", "skill", "status", "sort", "shown"];

/**
 * Which career the practice pages show: the `?career=` in the URL when it names a known career (a
 * breadcrumb like "Registered Nurse questions", or a copied link, opens that career's library, for
 * anyone), else the signed-in user's own track, else the default. An unknown or removed career
 * falls back to the user's own. Changing it saves to the profile when signed in.
 */
export function usePracticeTrack() {
  const { user, setUser } = useAuth();
  const [params, setParams] = useSearchParams();
  const careers = useCareers();
  const asked = params.get("career");
  const known = asked && (!careers.data || careers.data.some((c) => c.slug === asked)) ? asked : null;
  const track = known || user?.career_track || DEFAULT_TRACK;
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

