/** Default stand-in for the first-session introduction (tests override what they check). */
import { http, HttpResponse } from "msw";

import type { Onboarding } from "@/api/types";

const API = "http://localhost:8000";

/** A learner who has already chosen how to start: no welcome, no banners, no tour running. */
export function onboardingState(over: Partial<Onboarding> = {}): Onboarding {
  return {
    tour_status: "not_started", tour_kind: null, tour_step: 0, tour_steps: 5, start_choice: "library",
    welcome_due: false, resume_due: false, career_intro: null, first_activity_at: null, format: "coding",
    starter: { kind: "problem", track: "software-engineer", ref: "two-sum", title: "Two Sum", difficulty: "easy", href: "/problems/two-sum", minutes: 15 },
    ...over,
  };
}

export const onboardingHandlers = [
  // Empty lists for pages that link to your targets and stories (tests override what they check).
  http.get(`${API}/api/v1/targets`, () => HttpResponse.json([])),
  http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json([])),
  http.get(`${API}/api/v1/me/onboarding`, () => HttpResponse.json(onboardingState())),
  http.patch(`${API}/api/v1/me/onboarding`, () => HttpResponse.json(onboardingState())),
];
