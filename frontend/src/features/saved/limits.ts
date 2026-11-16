/** The server's limit on collections per account (backend/app/services/explore.py, MAX_COLLECTIONS),
 * so the page can say it before a copy would pass it. The server still decides: past it, it refuses
 * with `too_many_collections` and the count. */
export const MAX_COLLECTIONS = 50;

/** The server's limit on items per collection (backend/app/services/explore.py, MAX_ITEMS), so the
 * copy-or-move form can say how much room the other collection has. The server still decides: past it,
 * each item that doesn't fit says so ("full"). */
export const MAX_ITEMS = 200;
