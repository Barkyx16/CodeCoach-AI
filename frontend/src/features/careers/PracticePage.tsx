import { useSearchParams } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { LoadingState } from "@/components/States";
import { ProblemListPage } from "@/features/problems/ProblemListPage";

import { DEFAULT_TRACK, usePracticeTrack } from "./practiceTrack";
import { QuestionLibrary } from "./QuestionLibrary";

/** /problems: coding problems for jobs that have them (unless ?view=questions), interview questions otherwise. */
export function PracticePage() {
  const { isRestoring } = useAuth();
  const { track, career, careersLoading } = usePracticeTrack();
  const [params] = useSearchParams();
  // While the session is being restored we don't know whose career to show yet; showing the
  // default career's list first would flash the wrong questions.
  if (isRestoring || (careersLoading && track !== DEFAULT_TRACK)) return <LoadingState label="Loading practice…" />;
  const hasCoding = career ? career.has_coding : track === DEFAULT_TRACK;
  return hasCoding && params.get("view") !== "questions" ? <ProblemListPage /> : <QuestionLibrary />;
}
