import type { Collection, CollectionItem } from "@/api/types";

/**
 * Copying or moving chosen items to another collection (Volume 17, prompt 6; docs/BULK_ACTIONS.md,
 * "Copy or move items"): the item's key as the server names it, and what the form says before
 * anything is sent.
 */

type Named = Pick<CollectionItem, "item_type" | "track" | "ref_id">;

/** "type:track:ref", the server's key for an item (the track only for a question). */
export const itemKey = (i: Named) => `${i.item_type}:${i.item_type === "question" ? i.track ?? "" : ""}:${i.ref_id}`;

const quoted = (titles: string[], most = 4) => {
  const q = titles.map((t) => `“${t}”`);
  if (q.length > most) return `${q.slice(0, most).join(", ")} and ${q.length - most} more`;
  return q.length > 1 ? `${q.slice(0, -1).join(", ")} and ${q[q.length - 1]}` : q[0] ?? "";
};

const items = (n: number) => `${n} ${n === 1 ? "item" : "items"}`;

/** What the form says once the other collection is known: what it already has and its room, what
 * arrives with each item, and for a move what leaves this collection and what its queue will skip.
 * `maxItems` is the server's limit as it serves it; unread, the room isn't stated (the server decides). */
export function transferWords({ source, chosen, dest, move, maxItems }: {
  source: Collection; chosen: CollectionItem[]; dest: Collection; move: boolean; maxItems?: number;
}): string[] {
  const n = chosen.length;
  const there = new Set(dest.item_list.map(itemKey));
  const already = chosen.filter((i) => there.has(itemKey(i))).length;
  const fresh = n - already;
  const room = maxItems === undefined ? undefined : Math.max(0, maxItems - dest.items);
  const to = `“${dest.name}”`;
  const out: string[] = [];
  if (n === 1) out.push(already ? `${to} already has it: it won't be doubled.` : `${to} doesn't have it yet.`);
  else if (already) out.push(`${to} already has ${already} of these ${n}: ${already === 1 ? "it" : "they"} won't be doubled.`);
  else out.push(`${to} has none of these ${n} yet.`);
  if (fresh > 0 && room !== undefined) {
    if (room === 0) out.push(`It's full (${dest.items} of ${maxItems}): ${fresh === 1 ? "this one won't fit and will say so" : `none of the ${fresh} new ones will fit, and each will say so`}.`);
    else if (room < fresh) out.push(`It has room for ${room} more: ${fresh - room} of these won't fit and will say so.`);
    else out.push(`It has room for ${room} more.`);
  }
  out.push(`Each goes at the end of ${to}, in this collection's order, at the version it was added at and with its “Mark reviewed”. ${move ? "A queue mark isn't carried." : "Queue marks stay here."}`);
  if (!move) {
    out.push(`“${source.name}” doesn't change.`);
    return out;
  }
  out.push(`Leaves “${source.name}”, each once it's in ${to}: ${quoted(chosen.map((i) => i.title))}.`);
  const left = source.items - n;
  if (!source.queue_started) {
    out.push(`This collection's queue hasn't started; it will hold ${items(left)}.`);
  } else {
    const at = `Its queue (at item ${source.queue_position + 1} of ${source.items})`;
    const ahead = chosen.filter((i) => i.position >= source.queue_position && !i.queue_done);
    if (ahead.length) out.push(`${at} will skip ${ahead.length === 1 ? "1 not reached yet" : `${ahead.length} not reached yet`}: ${quoted(ahead.map((i) => i.title))}.`);
    else out.push(`${at} has already passed ${n === 1 ? "it" : "them"}.`);
  }
  const done = chosen.filter((i) => i.queue_done);
  if (done.length) out.push(`${done.length === 1 ? `${quoted([done[0]!.title])} was` : `${done.length} were`} marked done in this queue; that mark isn't carried to ${to}.`);
  return out;
}
