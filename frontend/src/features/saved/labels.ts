import { useCareers } from "@/api/queries";
import type { Collection, CollectionItem } from "@/api/types";

/** "Interview question · Registered Nurse" or "Coding problem", for saved-item rows. */
export function useItemKind(): (type: string, track: string) => string {
  const careers = useCareers();
  return (type, track) => {
    if (type === "drill") return "Communication drill";
    if (type !== "question") return "Coding problem";
    const title = careers.data?.find((c) => c.slug === track)?.title;
    return title ? `Interview question · ${title}` : "Interview question";
  };
}

/** Where an item opens when practiced from a queue: its page, tagged with the queue it came from. */
export function queueHref(c: Pick<Collection, "id" | "name">, item: CollectionItem): string | null {
  if (!item.available || !item.href) return null;
  return `${item.href}${item.href.includes("?") ? "&" : "?"}queue=${encodeURIComponent(c.id)}`;
}
