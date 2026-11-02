import { LoadingState } from "@/components/States";
import { DEFAULT_TRACK, usePracticeTrack } from "@/features/careers/practiceTrack";

import { InterviewStartPage } from "./InterviewStartPage";
import { QuestionInterviewPage } from "./QuestionInterviewPage";

/** /interviews: a coding interview for jobs with coding problems, else a round of the job's own questions. */
export function InterviewsPage() {
  const { track, career, careersLoading } = usePracticeTrack();
  if (careersLoading && track !== DEFAULT_TRACK) return <LoadingState label="Loading interview…" />;
  const hasCoding = career ? career.has_coding : track === DEFAULT_TRACK;
  return hasCoding ? <InterviewStartPage /> : <QuestionInterviewPage />;
}
