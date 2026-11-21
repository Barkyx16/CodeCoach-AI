/** "sbar, escalation ,  triage" -> ["sbar", "escalation", "triage"] (the server normalizes further). */
export function parseTags(text: string): string[] {
  return text.split(",").map((t) => t.trim()).filter(Boolean).slice(0, 12);
}
