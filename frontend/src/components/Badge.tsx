import type { Difficulty, SubmissionStatus } from "@/api/types";

export function Badge({ tone = "neutral", children }: { tone?: string; children: React.ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  return <Badge tone={`difficulty-${difficulty}`}>{difficulty[0]?.toUpperCase() + difficulty.slice(1)}</Badge>;
}

const STATUS_LABELS: Record<SubmissionStatus, { label: string; tone: string }> = {
  QUEUED: { label: "Queued", tone: "info" },
  RUNNING: { label: "Running", tone: "info" },
  PASSED: { label: "Passed", tone: "success" },
  FAILED: { label: "Failed", tone: "danger" },
  COMPILE_ERROR: { label: "Compile error", tone: "danger" },
  RUNTIME_ERROR: { label: "Runtime error", tone: "danger" },
  TIME_LIMIT: { label: "Time limit", tone: "warning" },
  MEMORY_LIMIT: { label: "Memory limit", tone: "warning" },
  INTERNAL_ERROR: { label: "Judge error", tone: "warning" },
};

export function StatusBadge({ status }: { status: SubmissionStatus }) {
  const meta = STATUS_LABELS[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function TopicTag({ topic }: { topic: string }) {
  return <span className="topic-tag">{topic.replace(/-/g, " ")}</span>;
}
