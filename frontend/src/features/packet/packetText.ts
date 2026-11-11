import type { Packet } from "@/api/types";

/** Labels for what a section is (docs/PACKET.md): never blurred between yours, authored and automated. */
export const SOURCE_LABEL: Record<Packet["items"][number]["sections"][number]["kind"], string> = {
  question: "From the question library",
  your_answer: "Yours",
  your_note: "Yours",
  your_story: "Yours",
  automated_feedback: "Automated feedback",
};
export const TYPE_LABEL: Record<Packet["items"][number]["type"], string> = { question: "Question", note: "Your note", story: "Your story" };

export const LOCAL_FILE = "Made on your device from the preview you saw. It isn't stored in your account, sent or shared.";

function stamp(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}

/**
 * The packet as plain text, from the preview exactly (nothing is fetched again): the downloaded
 * file is what was shown. Titles for choices that couldn't be included come from the page.
 */
export function packetText(p: Packet, titleOf: (type: string, id: string) => string): string {
  const out: string[] = [p.title, `Practice packet · assembled ${stamp(p.assembled_at)} · fingerprint ${p.digest}`, LOCAL_FILE, ""];
  p.items.forEach((item, i) => {
    out.push(`${i + 1}. ${item.title} (${TYPE_LABEL[item.type]})`, "");
    for (const n of item.notes ?? []) out.push(`   Note: ${n}`, "");
    for (const s of item.sections) {
      out.push(`## ${s.heading} [${SOURCE_LABEL[s.kind]}]`, `(${s.provenance})`, s.text, "");
    }
  });
  if (p.unavailable.length) {
    out.push("Not included:");
    for (const u of p.unavailable) out.push(`- ${titleOf(u.type, u.id)}: ${u.reason}`);
    out.push("");
  }
  if (p.redacted) out.push(`Email addresses and phone numbers removed from your own text: ${p.redacted}.`);
  if (p.shortened) out.push("Some text was shortened: a packet holds a bounded amount.");
  return out.join("\n").replace(/\n{3,}/g, "\n\n").trimEnd() + "\n";
}

export function packetFilename(p: Packet): string {
  const slug = p.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "practice-packet";
  return `${slug}-${p.assembled_at.slice(0, 10)}.txt`;
}
